# -*- coding: utf-8 -*-
"""A reconstrucao: da fila crua do aparelho para execucoes com hora.

Observado ao vivo no R1, com o player tocando: as 08:49:41 a faixa mudou e a
ultima linha do HISTORY_TABLE virou a faixa nova no mesmo segundo, com o pcm
ainda aberto e a musica tocando por mais quarenta e cinco. A linha entra
quando a faixa COMECA.

Entao a hora de cada p1 e o COMECO da faixa, e o espaco ate a linha seguinte e
quanto ela tocou. Uma faixa pulada se denuncia por ter a proxima linha logo em
seguida. A ultima de cada sessao nao tem seguinte, e quem a fecha e o marcador
f1 — a hora em que o daemon viu o audio parar.

O modulo teve um modo FIM, herdado de uma medicao antiga que estava olhando
para a linha da faixa ANTERIOR. Ele continua implementado, e a secao 11 existe
para garantir que trocar de modo nao quebra a leitura — mas o padrao e o
INICIO, que e o que o aparelho faz.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
# O idioma e fixado aqui: as verificacoes olham o texto que sai, e o
# padrao muda conforme o idioma do computador de quem roda o teste.
from r1lastfm import idioma as _idioma
_idioma.definir("en")
from r1lastfm import fila as F

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


T0 = 1785500000


def p1(rowid, fim, art, tit, dur, alb="Alb", aa="", ano=2020, path="a:\\x.flac"):
    """Uma linha da fila. `fim` e quando a faixa acabou."""
    return f"p1\t{rowid}\t{fim}\t{art}\t{tit}\t{alb}\t{aa}\t{dur}\t{ano}\t{path}\t"


print("=" * 74)
print("1. sessao normal: cada linha e uma faixa que comecou")
print("=" * 74)
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3,   "yui", "Again", 257),        # a proxima em +257: inteira
    p1(2, T0 + 260, "FLOW", "Go!!!", 240),       # a proxima em +240: inteira
    p1(3, T0 + 500, "TOP", "Migraine", 238),     # o audio parou em +238
    f"f1\t{T0 + 738}",
])
regs, ruins = F.ler(texto)
check("leu todas as linhas", len(regs) == 5 and ruins == 0,
      f"{len(regs)}, {ruins} ruins")
rec = F.reconstruir(regs, agora=T0 + 900)
check("as 3 contam", len(rec.execucoes) == 3, F.resumo(rec))
if len(rec.execucoes) == 3:
    a, b, c = rec.execucoes
    check("Again: a hora e a da propria linha", a.timestamp == T0 + 3,
          f"{a.timestamp - T0}s")
    check("Again: ouvida inteira", a.listened == 257, f"{a.listened}s")
    check("Go!!!: ouvida inteira", b.listened == 240, f"{b.listened}s")
    check("a ultima da sessao conta, fechada pelo f1",
          c.listened == 238, f"{c.listened}s")
    check("em ordem crescente de hora",
          a.timestamp < b.timestamp < c.timestamp)

print()
print("=" * 74)
print("2. faixa pulada: a linha SEGUINTE aparece cedo demais")
print("=" * 74)
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3,   "A", "Inteira", 257),
    p1(2, T0 + 260, "B", "Pulei em 40s", 300),   # a proxima 40s depois
    p1(3, T0 + 300, "C", "Inteira2", 240),
    f"f1\t{T0 + 540}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
titulos = [p.track for p in rec.execucoes]
check("a pulada ficou de fora", "Pulei em 40s" not in titulos, str(titulos))
check("as inteiras entraram",
      titulos == ["Inteira", "Inteira2"], str(titulos))
fora = [t for _p, t in rec.descartadas]
check("com o motivo explicado",
      any("40s of 300s" in m for m in fora), str(fora))

print()
print("=" * 74)
print("3. a primeira faixa da sessao ja nao depende de vizinho anterior")
print("=" * 74)
# Este era o defeito relatado: a primeira da sessao nao tinha anterior, ficava
# com folga zero e era recusada sempre — "ouvi o disco inteiro e apareceu 0s".
# Com a hora da linha sendo o comeco, ela nao precisa de nada atras.
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3, "A", "Primeira", 257),
    f"f1\t{T0 + 260}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
check("a primeira faixa conta", len(rec.execucoes) == 1, F.resumo(rec))
if rec.execucoes:
    check("e ouvida inteira", rec.execucoes[0].listened == 257,
          f"{rec.execucoes[0].listened}s")
# E se o audio parou antes de ela ter cabido, nao conta.
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3, "A", "Nao coube", 257),
    f"f1\t{T0 + 63}",                        # parou 60s depois de comecar
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
check("mas nao se o audio parou 60s depois", len(rec.execucoes) == 0,
      F.resumo(rec))

print()
print("=" * 74)
print("4. um reinicio nao empresta tempo por cima da fronteira")
print("=" * 74)
# A faixa de antes do desligamento nao pode ser fechada pelo que aconteceu
# oito horas depois: o marcador da propria sessao e quem manda.
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3, "A", "Antes", 257),
    f"f1\t{T0 + 260}",
    f"b1\t{T0 + 30000}",                       # desligou e ligou 8h depois
    p1(2, T0 + 30003, "B", "Depois", 240),
    f"f1\t{T0 + 30053}",                       # o audio parou 50s depois
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 31000)
titulos = [p.track for p in rec.execucoes]
check("a de antes conta", "Antes" in titulos, str(titulos))
check("a de depois so tocou 50s e fica de fora",
      "Depois" not in titulos, str(titulos))
check("contou o reinicio", rec.reinicios == 1, str(rec.reinicios))

print()
print("=" * 74)
print("5. linhas repetidas (queda de energia) nao viram scrobble dobrado")
print("=" * 74)
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 260, "A", "Uma", 257),
    p1(2, T0 + 500, "B", "Duas", 240),
    p1(1, T0 + 260, "A", "Uma", 257),          # rowid 1 repetido
    p1(2, T0 + 500, "B", "Duas", 240),
    p1(3, T0 + 745, "C", "Tres", 240),
    f"i1\t{T0 + 745}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
titulos = [p.track for p in rec.execucoes]
check("cada rowid so uma vez", len(titulos) == len(set(titulos)), str(titulos))
check("3 execucoes distintas", len(rec.execucoes) == 3, str(titulos))

print()
print("=" * 74)
print("6. o que ja foi enviado nao vai de novo")
print("=" * 74)
rec = F.reconstruir(F.ler(texto)[0], ja_enviados={1, 2}, agora=T0 + 900)
check("so o rowid 3 sobrou", [p.track for p in rec.execucoes] == ["Tres"],
      str([p.track for p in rec.execucoes]))

print()
print("=" * 74)
print("7. relogio errado no aparelho")
print("=" * 74)
texto = "\n".join([
    "b1\t100",
    "c1\t100",
    p1(1, 400, "A", "ComHoraRuim", 257),
    f"b1\t{T0}",
    p1(2, T0 + 260, "C", "ComHoraBoa", 257),
    p1(3, T0 + 500, "D", "Boa2", 240),
    f"i1\t{T0 + 500}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
titulos = [p.track for p in rec.execucoes]
check("marcou que o relogio estava errado", rec.relogio_suspeito)
check("a de hora ruim ficou de fora", "ComHoraRuim" not in titulos, str(titulos))
check("as de hora boa entraram",
      titulos == ["ComHoraBoa", "Boa2"], str(titulos))

print()
print("=" * 74)
print("8. faixa antiga demais para o Last.fm")
print("=" * 74)
velho = T0 - 20 * 86400
texto = "\n".join([
    f"b1\t{velho}",
    p1(1, velho + 260, "A", "Antiga", 257),
    p1(2, velho + 500, "B", "Antiga2", 240),
    f"i1\t{velho + 500}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0)
check("nenhuma enviada", len(rec.execucoes) == 0, F.resumo(rec))
check("motivo diz quantos dias",
      any("days" in m for _p, m in rec.descartadas),
      str([m for _p, m in rec.descartadas][:1]))

print()
print("=" * 74)
print("9. caracteres escapados voltam inteiros")
print("=" * 74)
linha = ("p1\t1\t%d\tArtista\\tcom tab\tTitulo\\ncom quebra\t"
         "Album\\\\com barra\t\t200\t2020\ta:\\\\M\\\\x.flac\t" % (T0 + 260))
texto = f"b1\t{T0}\n{linha}\ni1\t{T0 + 260}"
regs, ruins = F.ler(texto)
check("linha entendida", len(regs) == 3 and ruins == 0, f"{ruins} ruins")
p = regs[1]
check("tab desescapado", p.artista == "Artista\tcom tab", repr(p.artista))
check("quebra desescapada", p.titulo == "Titulo\ncom quebra", repr(p.titulo))
check("barra desescapada", p.album == "Album\\com barra", repr(p.album))
check("caminho desescapado", p.caminho == "a:\\M\\x.flac", repr(p.caminho))

print()
print("=" * 74)
print("10. faixas curtas e sem duracao")
print("=" * 74)
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 100, "A", "Vinheta de 20s", 20),     # menos de 30s: fora
    p1(2, T0 + 400, "B", "Sem duracao", 0),         # duracao desconhecida
    f"i1\t{T0 + 400}",
])
rec = F.reconstruir(F.ler(texto)[0], agora=T0 + 900)
titulos = [p.track for p in rec.execucoes]
check("faixa de 20s nao conta", "Vinheta de 20s" not in titulos, str(titulos))
check("sem duracao conhecida, entra", "Sem duracao" in titulos, str(titulos))

print()
print("=" * 74)
print("11. o modo FIM, herdado, ainda le sem quebrar")
print("=" * 74)
# O modo FIM veio de uma medicao antiga que estava olhando para a linha da
# faixa ANTERIOR: 194s nao era o atraso da linha nova, era a duracao da que
# tinha acabado. Ele nao e mais o padrao, mas continua no modulo, e trocar de
# modo nao pode explodir nem devolver lixo.
texto = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 260, "yui", "Again", 257),
    p1(2, T0 + 500, "FLOW", "Go!!!", 240),
    f"i1\t{T0 + 500}",
])
rec = F.reconstruir(F.ler(texto)[0], modo=F.FIM, agora=T0 + 900)
check("leu no modo FIM sem quebrar", len(rec.execucoes) >= 1, F.resumo(rec))
if rec.execucoes:
    check("no modo FIM a hora e a linha menos a duracao",
          rec.execucoes[0].timestamp == T0 + 260 - 257,
          f"{rec.execucoes[0].timestamp - T0}s")
check("mas o padrao do modulo e INICIO, que e o que o aparelho faz",
      F.PADRAO == F.INICIO, F.PADRAO)

print()
print("=" * 74)
print("12. lixo na fila nao derruba nada")
print("=" * 74)
texto = "\n".join([
    f"b1\t{T0}",
    "isto nao e uma linha valida",
    "p1\tsem\tnumeros\taqui",
    "",
    "p1\t9",
    p1(1, T0 + 260, "A", "Boa", 257),
    "\x00\x01binario",
    f"i1\t{T0 + 260}",
])
regs, ruins = F.ler(texto)
check("as ruins foram contadas, nao explodiram", ruins == 4, f"{ruins} ruins")
rec = F.reconstruir(regs, agora=T0 + 900)
check("a boa foi aproveitada", len(rec.execucoes) == 1, F.resumo(rec))

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
