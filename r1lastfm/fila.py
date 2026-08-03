"""Transforma a fila crua do aparelho em execuções com hora e tempo ouvido.

O R1 não guarda quando uma faixa tocou nem por quanto tempo: o HISTORY_TABLE
só diz *que* ela tocou, e em que ordem. Quem põe hora nisso é o daemon, que
anota o instante em que viu cada linha aparecer. Este módulo faz o resto da
conta.

Quando isso acontece foi medido no aparelho, e a resposta é boa: **o player
grava a linha quando a faixa TERMINA**. Numa faixa de 3min14 a gravação
apareceu 194 s depois do play, que é a duração exata.

Isso simplifica tudo. A existência da linha já diz que a faixa chegou ao fim,
então a hora de início é a da gravação menos a duração, e não há a incerteza
da "última faixa da sessão" — toda linha representa uma faixa concluída.

O tempo ouvido ainda é limitado pelo espaço desde o evento anterior: se você
pulou a faixa no meio, a linha aparece cedo demais para ela ter tocado
inteira, e a conta pega isso.

Um reinício quebra a sequência, e é tratado: o intervalo entre a última faixa
antes de desligar e a primeira depois de ligar não é tempo de escuta. Os
marcadores de início do daemon cortam a conta nesses pontos.

O modo INICIO continua implementado, para o caso de outra versão de firmware
se comportar de outro jeito.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .idioma import t
from .lastfm import FULL_PLAY_SECONDS, MIN_TRACK_SECONDS, Play

# Quando a linha entra no banco em relação à faixa.
#
# A linha entra quando a faixa COMEÇA. Observado ao vivo no aparelho, com o
# player tocando: às 08:49:41 a faixa mudou e a última linha do HISTORY_TABLE
# virou a faixa nova no mesmo segundo, com o pcm ainda aberto e a música
# tocando por mais quarenta e cinco.
#
# O padrão era FIM, com base numa medição antiga que dizia ter visto a linha
# aparecer 194 s depois do play, numa faixa de 3min14. Aquela medição estava
# olhando para a linha da faixa ANTERIOR: 194 s é a duração da faixa que
# acabou de tocar, não o atraso da que começou. O erro era sutil e custou
# caro — enquanto durou, o tempo ouvido saía atribuído à faixa errada.
INICIO = "inicio"   # a linha aparece quando a faixa começa
FIM = "fim"         # a linha aparece quando a faixa termina (não é o caso)
PADRAO = INICIO

# O que fazer com a última faixa de uma sessão, cujo tempo de escuta ninguém
# registrou.
ULTIMA_ASSUME_INTEIRA = "inteira"    # conta como ouvida por completo
ULTIMA_DESCARTA = "descarta"         # não envia
ULTIMA_USA_LIMITE = "limite"         # usa o pouco que dá para provar

# O Last.fm recusa horas com mais de 14 dias. Deixo uma folga de meio dia.
LIMITE_ANTIGO = 13 * 86400


def desescapa(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            d = s[i + 1]
            if d == "\\":
                out.append("\\"); i += 2; continue
            if d == "t":
                out.append("\t"); i += 2; continue
            if d == "n":
                out.append("\n"); i += 2; continue
            if d == "r":
                out.append("\r"); i += 2; continue
            if d == "x" and i + 3 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return "".join(out)


@dataclass
class Registro:
    """Uma linha da fila, ainda crua."""

    tipo: str
    hora: int
    rowid: int = 0
    artista: str = ""
    titulo: str = ""
    album: str = ""
    album_artista: str = ""
    duracao: int = 0
    ano: int = 0
    caminho: str = ""
    # A hora em que a faixa COMEÇOU, quando a linha sabe dizer.
    #
    # O caminho local não sabe: a linha do histórico só aparece quando a faixa
    # acaba, e o começo é deduzido. O Tidal sabe — o daemon vê a troca de
    # faixa acontecer. Zero quer dizer "não sei", que é o caso de toda linha
    # gravada antes deste campo existir.
    inicio_dito: int = 0


@dataclass
class Reconstrucao:
    execucoes: list[Play] = field(default_factory=list)
    descartadas: list[tuple[Play, str]] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    linhas_invalidas: int = 0
    reinicios: int = 0
    relogio_suspeito: bool = False


def ler(texto: str) -> tuple[list[Registro], int]:
    """Lê a fila. Devolve (registros, linhas que não deu para entender)."""
    regs: list[Registro] = []
    ruins = 0
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        campos = linha.split("\t")
        tipo = campos[0]
        try:
            if tipo in ("b1", "f1", "i1", "m1", "c1"):
                regs.append(Registro(tipo=tipo, hora=int(campos[1])))
            elif tipo == "p1":
                # p1 rowid hora artista titulo album album_artista dur ano path
                regs.append(Registro(
                    tipo="p1",
                    rowid=int(campos[1]),
                    hora=int(campos[2]),
                    artista=desescapa(campos[3]),
                    titulo=desescapa(campos[4]),
                    album=desescapa(campos[5]),
                    album_artista=desescapa(campos[6]),
                    duracao=int(campos[7] or 0),
                    ano=int(campos[8] or 0),
                    caminho=desescapa(campos[9]) if len(campos) > 9 else "",
                    inicio_dito=int(campos[10]) if len(campos) > 10
                                and campos[10].strip().isdigit() else 0,
                ))
            else:
                ruins += 1
        except (IndexError, ValueError):
            ruins += 1
    return regs, ruins


def reconstruir(regs: Sequence[Registro], *,
                modo: str = PADRAO,
                ultima: str = ULTIMA_ASSUME_INTEIRA,
                ja_enviados: Iterable[int] = (),
                agora: int | None = None) -> Reconstrucao:
    """Monta as execuções a partir dos registros do aparelho."""
    import time as _t

    agora = int(agora if agora is not None else _t.time())
    enviados = set(ja_enviados)
    out = Reconstrucao()

    # O daemon pode repetir linhas se faltar energia entre gravar a fila e
    # gravar o estado. O rowid resolve: cada reprodução tem o seu.
    vistos: set[int] = set()
    limpos: list[Registro] = []
    for reg in regs:
        if reg.tipo == "p1":
            if reg.rowid in vistos:
                continue
            vistos.add(reg.rowid)
        limpos.append(reg)

    # Corta em sessões: um reinício não é uma pausa entre músicas.
    #
    # A hora do próprio marcador b1 é guardada junto, e não descartada: ela é
    # o limite inferior da primeira faixa da sessão. Sem ela, no modo FIM a
    # primeira faixa ficaria com folga zero e seria recusada sempre.
    sessoes: list[tuple[int, list[Registro]]] = [(0, [])]
    suspeito_ate = -1
    for reg in limpos:
        if reg.tipo == "b1":
            out.reinicios += 1
            if sessoes[-1][1]:
                sessoes.append((reg.hora, []))
            else:
                sessoes[-1] = (reg.hora, sessoes[-1][1])
            continue
        if reg.tipo == "c1":
            out.relogio_suspeito = True
            suspeito_ate = reg.hora
            continue
        sessoes[-1][1].append(reg)
    out.reinicios = max(0, out.reinicios - 1)

    for abertura, sessao in sessoes:
        _uma_sessao(sessao, out, modo, ultima, enviados, agora, suspeito_ate,
                    abertura)

    out.execucoes.sort(key=lambda p: p.timestamp)
    return out


def _uma_sessao(sessao, out, modo, ultima, enviados, agora, suspeito_ate,
                abertura=0):
    toques = [r for r in sessao if r.tipo == "p1"]
    if not toques:
        return
    # A hora em que a sessão parou. Só o f1 conta: ele é o daemon dizendo que
    # viu o pcm fechar, e é medido.
    #
    # O i1 e o m1 ficaram de fora, e tê-los usado foi um erro caro. O i1 diz
    # "depois desta hora nada mais aconteceu", o que parece um teto e é o
    # contrário: enquanto uma faixa longa toca é exatamente quando nada
    # acontece, então o i1 carrega a hora do último evento — a hora em que a
    # faixa começou. Uma faixa de 318 s com o i1 um segundo depois dela saía
    # creditada com 1 segundo. O m1 marca atividade, ou seja, é limite
    # inferior: prova que a faixa ainda tocava, nunca que já tinha parado.
    fechamento = 0
    for r in sessao:
        if r.tipo == "f1":
            fechamento = max(fechamento, r.hora)

    # `abertura` vem do marcador b1. Se por algum motivo não houver um — uma
    # fila cortada pela metade, por exemplo — a primeira faixa fica sem limite
    # inferior, e o único palpite honesto é a duração dela.
    if not abertura:
        abertura = 0

    for i, reg in enumerate(toques):
        if reg.rowid in enviados:
            continue

        if modo == FIM:
            # Medido no R1: a linha entra no banco quando a faixa ACABA. Numa
            # faixa de 3min14 a gravação apareceu exatamente 194 s depois do
            # play.
            #
            # Isso é melhor do que o contrário, porque a própria existência da
            # linha já diz que a faixa chegou ao fim. A hora de início é a da
            # gravação menos a duração, e o tempo ouvido é limitado pelo
            # espaço que houve desde o evento anterior: se você pulou a faixa
            # no meio, a linha aparece cedo demais para ela ter tocado inteira,
            # e a conta pega isso.
            if reg.inicio_dito and reg.inicio_dito <= reg.hora:
                # Sabemos os dois extremos: o tempo ouvido é a subtração, sem
                # depender de qual foi o evento anterior.
                inicio = reg.inicio_dito
                folga = reg.hora - reg.inicio_dito
            else:
                inicio = reg.hora - reg.duracao if reg.duracao else reg.hora
                anterior = toques[i - 1].hora if i else abertura
                folga = reg.hora - anterior if anterior else reg.duracao
            span = min(reg.duracao, folga) if reg.duracao else folga
            certeza = True
        else:
            # A linha entra no início da faixa, então a hora dela É o começo,
            # e o tempo ouvido é o intervalo até a linha seguinte — que é
            # quando a faixa parou de tocar, porque foi quando outra começou.
            #
            # O Tidal continua sendo o caso feliz: lá o daemon vê a troca e
            # diz o começo exato, sem depender de vizinho nenhum.
            if reg.inicio_dito and reg.inicio_dito <= reg.hora:
                inicio = reg.inicio_dito
                span = reg.hora - reg.inicio_dito
                certeza = True
            else:
                inicio = reg.hora
                if i + 1 < len(toques):
                    seguinte = toques[i + 1]
                    span = ((seguinte.inicio_dito or seguinte.hora)
                            - reg.hora)
                    certeza = True
                else:
                    # A última da sessão não tem seguinte que a feche. O f1
                    # diz a hora em que o áudio parou — é medido. O i1 e o m1
                    # são tetos mais frouxos. Sem nenhum deles, ela fica em
                    # aberto: mandar cedo demais é justamente o erro que
                    # fazia uma faixa recém-começada aparecer como ouvida
                    # por inteiro.
                    depois = [r.hora for r in sessao
                              if r.tipo == "f1" and r.hora > reg.hora]
                    if depois:
                        span = min(depois) - reg.hora
                        certeza = True
                    elif reg.duracao and agora - reg.hora >= reg.duracao:
                        # Nenhum marcador, mas já passou tempo de sobra para a
                        # faixa ter cabido inteira. É o caso das filas
                        # gravadas antes de o f1 existir.
                        span = reg.duracao
                        certeza = False
                    else:
                        span = 0
                        certeza = False

        # Ninguém ouve mais do que a faixa dura.
        if reg.duracao:
            span = min(span, reg.duracao)
        span = max(0, span)

        play = Play(
            artist=reg.artista.strip(),
            track=reg.titulo.strip(),
            timestamp=inicio,
            album=reg.album.strip(),
            album_artist=reg.album_artista.strip(),
            duration=reg.duracao,
            listened=span,
            source=reg.caminho,
        )

        if not certeza:
            if ultima == ULTIMA_DESCARTA:
                out.descartadas.append(
                    (play, t("fila.last_of_session")))
                continue
            if ultima == ULTIMA_ASSUME_INTEIRA:
                # Sem uma faixa seguinte nada prova o tempo. Assumir que ela
                # tocou inteira erra para o lado de mandar demais; descartar
                # erraria para o lado de perder a última faixa de toda
                # sessão, o que é bem pior no dia a dia.
                play.listened = play.duration if play.duration else -1
            # Em ULTIMA_USA_LIMITE o span calculado fica como está: é o que
            # os marcadores conseguem provar, e nada além disso.

        if reg.hora <= suspeito_ate:
            out.descartadas.append(
                (play, t("fila.bad_clock")))
            continue
        if play.timestamp > agora + 300:
            out.descartadas.append((play, t("fila.future")))
            continue
        if agora - play.timestamp > LIMITE_ANTIGO:
            dias = (agora - play.timestamp) // 86400
            out.descartadas.append(
                (play, t("fila.too_old", dias=dias, limite=14)))
            continue

        pode, motivo = play.scrobblable()
        if pode:
            out.execucoes.append(play)
        else:
            out.descartadas.append((play, motivo))


def rowids(regs: Sequence[Registro]) -> list[int]:
    return [r.rowid for r in regs if r.tipo == "p1"]


def resumo(rec: Reconstrucao) -> str:
    linhas = [t("fila.ready", n=len(rec.execucoes))]
    if rec.descartadas:
        linhas.append(t("fila.left_out", n=len(rec.descartadas)))
    if rec.reinicios:
        linhas.append(t("fila.reboots", n=rec.reinicios))
    if rec.relogio_suspeito:
        linhas.append(t("fila.clock_warn"))
    if rec.linhas_invalidas:
        linhas.append(t("fila.bad_lines", n=rec.linhas_invalidas))
    return " · ".join(linhas)
