# -*- coding: utf-8 -*-
"""A linha do historico entra quando a faixa COMECA. Tudo decorre disso.

Foi observado ao vivo no aparelho: as 08:49:41 o player trocou de faixa e a
ultima linha do HISTORY_TABLE virou a faixa nova no mesmo instante, com o pcm
ainda aberto e a musica tocando por mais quarenta e cinco segundos.

O codigo assumia o contrario ("a linha entra quando a faixa acaba") e por isso
a conta saia deslocada em uma faixa. Uma pessoa relatou as duas metades do
mesmo defeito na mesma mensagem:

    City Walls  --/5:22   heard for 0s of 322s (needed 161s)
    RAWFEAR     3:22/3:22 sending          <- "nao terminou mas mostra como
                                              terminada"

City Walls tocou inteira e ficou com zero porque era a primeira da sessao e
nao tinha anterior; RAWFEAR tinha acabado de comecar e levou o tempo que a
City Walls tocou. Este teste reconstroi exatamente esse par.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import csv, os, sys, tempfile

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from comum import compilar_para_o_pc          # noqa: E402
from r1lastfm.applog import Log               # noqa: E402
from r1lastfm.runner import Runner            # noqa: E402

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


WORK = os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "lastfm")
os.makedirs(WORK, exist_ok=True)
runner = Runner(log=Log(os.path.join(WORK, "t_tempos.log")), wsl_distro="Ubuntu")
compilar_para_o_pc(runner, "r1send")
EXE = runner.to_posix_path(os.path.join(WORK, "r1send"))
BASE = tempfile.mkdtemp(prefix="t_tempos-")


def p1(rowid, visto, titulo, dur, inicio=""):
    return "\t".join(["p1", str(rowid), str(visto), "Twenty One Pilots",
                      titulo, "Breach", "", str(dur), "2025",
                      "a:\\x.flac", str(inicio)])


def rodar(fila_txt, nome):
    fila = os.path.join(BASE, f"f_{nome}.tsv")
    envi = os.path.join(BASE, f"e_{nome}")
    saida = os.path.join(BASE, f"r_{nome}.csv")
    with open(fila, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fila_txt)
    open(envi, "w").close()
    runner.posix(f"{EXE} relatorio {runner.to_posix_path(fila)} "
                 f"{runner.to_posix_path(envi)} {runner.to_posix_path(saida)}",
                 mutating=True, quiet=True)
    with open(saida, encoding="utf-8", newline="") as fh:
        return {l["track"]: l for l in csv.DictReader(fh)}


import time
AGORA = int(time.time())
T0 = AGORA - 3600            # o daemon subiu uma hora atras

print("=" * 74)
print("1. o par relatado: City Walls e RAWFEAR, uma depois da outra")
print("=" * 74)
# City Walls (5:22 = 322s) comeca; oito minutos depois RAWFEAR (3:22 = 202s)
# comeca. Logo City Walls tocou inteira, e RAWFEAR mal comecou.
#
# RAWFEAR fica no passado RECENTE de proposito: no relato ela estava tocando
# naquele momento. Uma faixa comecada ha muito tempo e sem marcador de fim e
# outro caso, coberto na secao 4.
RF = AGORA - 40
CW = RF - 480
fila = (f"b1\t{CW - 60}\n" + p1(1, CW, "City Walls", 322) + "\n"
        + p1(2, RF, "RAWFEAR", 202) + "\n")
r = rodar(fila, "par")

cw = r["City Walls"]
check("City Walls: ouviu os 322s inteiros", cw["seconds_heard"] == "322",
      f"{cw['seconds_heard']}s de {cw['track_seconds']}s")
check("City Walls: vai para o Last.fm", cw["status"] == "pending",
      cw["status"])
check("City Walls: a hora e a que ela COMECOU",
      int(cw["started_at_epoch"]) == CW,
      f"{cw['started_at_epoch']} vs {CW}")

rf = r["RAWFEAR"]
check("RAWFEAR: ainda tocando, nao leva credito nenhum",
      rf["seconds_heard"] == "0", f"{rf['seconds_heard']}s")
# "playing" e nao "skipped": a faixa nao foi pulada, ela nao acabou. As duas
# nao sobem, mas so uma delas e verdade — e e essa que a pessoa le no CSV.
check("RAWFEAR: NAO e enviada como terminada", rf["status"] == "playing",
      rf["status"])
check("RAWFEAR: e nao aparece como enviada", rf["status"] != "sent",
      rf["status"])

print()
print("=" * 74)
print("2. a mesma sequencia depois que o audio para")
print("=" * 74)
# O daemon viu o audio parar depois de RAWFEAR ter tocado quase inteira: 195
# de 202 segundos. A regua e 90% da faixa (182 s aqui), entao conta.
fila = (f"b1\t{CW - 60}\n" + p1(1, CW, "City Walls", 322) + "\n"
        + p1(2, RF, "RAWFEAR", 202) + "\n" + f"f1\t{RF + 195}\n")
r = rodar(fila, "parou")
check("RAWFEAR: 195s dos 202s", r["RAWFEAR"]["seconds_heard"] == "195",
      r["RAWFEAR"]["seconds_heard"])
check("RAWFEAR: agora sim vai", r["RAWFEAR"]["status"] == "pending",
      r["RAWFEAR"]["status"])
check("City Walls nao mudou", r["City Walls"]["seconds_heard"] == "322")

# A beirada, que e o que o usuario pediu: parar aos 180 de 202 (89%) NAO
# conta. Antes a regua era metade, e uma faixa largada no meio subia para o
# perfil como se tivesse sido ouvida inteira.
fila = (f"b1\t{RF - 60}\n" + p1(3, RF, "Quase", 202) + "\n"
        + f"f1\t{RF + 180}\n")
r = rodar(fila, "quase")
check("parar a 89% da faixa nao conta", r["Quase"]["status"] == "skipped",
      f"{r['Quase']['seconds_heard']}s de {r['Quase']['track_seconds']}s "
      f"-> {r['Quase']['status']}")

print()
print("=" * 74)
print("3. faixa pulada continua sendo descartada")
print("=" * 74)
# Tres faixas de 300s, cada linha 20s depois da anterior: cada uma tocou 20s.
fila = f"b1\t{T0}\n" + "".join(
    p1(10 + i, T0 + 60 + 20 * i, f"Pulada {i+1}", 300) + "\n" for i in range(3)
) + f"f1\t{T0 + 60 + 60}\n"
r = rodar(fila, "pulos")
for nome in ("Pulada 1", "Pulada 2", "Pulada 3"):
    check(f"{nome}: 20s, descartada",
          r[nome]["seconds_heard"] == "20" and r[nome]["status"] == "skipped",
          f"{r[nome]['seconds_heard']}s {r[nome]['status']}")

print()
print("=" * 74)
print("4. sem marcador de fim, a ultima fica em aberto (nao e chutada)")
print("=" * 74)
# Uma faixa sozinha, comecada ha 30 segundos, sem f1: nao da para saber se
# tocou. O certo e nao mandar — a leitura seguinte ja vai saber.
fila = f"b1\t{AGORA - 60}\n" + p1(20, AGORA - 30, "Recem comecada", 300) + "\n"
r = rodar(fila, "aberta")
check("nao leva credito", r["Recem comecada"]["seconds_heard"] == "0",
      r["Recem comecada"]["seconds_heard"])
check("e nao e enviada", r["Recem comecada"]["status"] == "playing",
      r["Recem comecada"]["status"])

# Mas se ja passou tempo de sobra e o daemon nao esta mais la para dizer,
# o relogio fecha: a faixa cabe inteira no intervalo ate agora.
fila = f"b1\t{T0}\n" + p1(21, T0 + 60, "Antiga sozinha", 300) + "\n"
r = rodar(fila, "antiga")
check("faixa velha o bastante e fechada pelo relogio",
      r["Antiga sozinha"]["seconds_heard"] == "300",
      r["Antiga sozinha"]["seconds_heard"])

print()
print("=" * 74)
print("4b. o marcador de silencio NAO fecha a faixa")
print("=" * 74)
# Visto no aparelho: uma faixa de 318s com o i1 um segundo depois dela,
# creditada com 1 segundo de 318.
#
# O i1 diz "depois desta hora nada mais aconteceu". Parece um teto e e o
# contrario: e enquanto uma faixa longa toca que nada acontece — nenhuma
# linha nova entra no banco, o daemon fica quieto, e escreve o i1 com a hora
# do ULTIMO evento, que e a hora em que a faixa comecou.
COMECO = AGORA - 400
fila = (f"b1\t{COMECO - 30}\n" + p1(40, COMECO, "Longa", 318) + "\n"
        + f"i1\t{COMECO + 1}\n"       # o silencio comeca logo: ela esta tocando
        + f"m1\t{COMECO + 184}\n")    # atividade DURANTE a faixa
r = rodar(fila, "silencio")
lg = r["Longa"]
check("o i1 nao a fecha em 1 segundo", lg["seconds_heard"] != "1",
      f"{lg['seconds_heard']}s de {lg['track_seconds']}s")
check("ela conta como ouvida", lg["seconds_heard"] == "318",
      f"{lg['seconds_heard']}s")
check("e vai para o Last.fm", lg["status"] == "pending", lg["status"])

# E com o f1, que e medido, ela e fechada onde o audio realmente parou.
fila = (f"b1\t{COMECO - 30}\n" + p1(41, COMECO, "Longa2", 318) + "\n"
        + f"i1\t{COMECO + 1}\n" + f"f1\t{COMECO + 200}\n")
r = rodar(fila, "silencio2")
check("o f1, esse sim, fecha onde o audio parou",
      r["Longa2"]["seconds_heard"] == "200", r["Longa2"]["seconds_heard"])

print()
print("=" * 74)
print("5. a hora enviada nunca fica ANTES de a faixa comecar")
print("=" * 74)
# O bug antigo mandava `visto - duracao`, uma faixa inteira antes do comeco.
fila = (f"b1\t{T0}\n" + p1(30, T0 + 600, "Marcada", 240) + "\n"
        + p1(31, T0 + 900, "Seguinte", 240) + "\n" + f"f1\t{T0 + 1200}\n")
r = rodar(fila, "hora")
check("a hora e a da linha, nao a linha menos a duracao",
      int(r["Marcada"]["started_at_epoch"]) == T0 + 600,
      f"{r['Marcada']['started_at_epoch']} vs {T0 + 600} "
      f"(o errado seria {T0 + 600 - 240})")

print()
print("=" * 74)
print("6. o tempo MEDIDO manda; a deducao pelos carimbos e so reserva")
print("=" * 74)
# O relato da vi: faixas subindo no instante em que comecavam, aparecendo no
# perfil como scrobble e como "scrobbling now" ao mesmo tempo. A causa era
# sempre a mesma — o tempo ouvido vinha do ESPACO entre carimbos, e o espaco
# nao e a musica. Basta uma pausa, ou o daemon subir no meio, para os dois
# numeros divergirem, e quando divergem quem erra e a deducao.
#
# O marcador t1 e o daemon dizendo o que mediu com o pcm na mao:
#     t1 <rowid> <segundos ouvidos> <regua da medicao> [fim]
#
# Sai em parcelas enquanto a faixa toca — um travamento nao pode levar a
# medicao junto — e a ULTIMA leva "fim". Sem esse campo nao daria para separar
# "tocou 35 de 133 e acabou ai" de "esta no segundo 35 e continua".
def t1(rowid, ouvido, regua=15, fim=True):
    return f"t1\t{rowid}\t{ouvido}\t{regua}" + ("\tfim" if fim else "")


# Espaco de 20 minutos entre uma linha e a outra, mas so 44s de audio: a
# pessoa apertou play, saiu, e a musica ficou pausada. Pela deducao antiga
# isso era "ouviu 300 de 300" e subia.
INI = AGORA - 1500
fila = (f"b1\t{INI - 60}\n" + p1(50, INI, "Pausada", 300) + "\n"
        + t1(50, 44) + "\n"
        + p1(51, INI + 1200, "Depois", 300) + "\n" + t1(51, 295) + "\n")
r = rodar(fila, "medido")
check("a medida vence o espaco de 20 minutos",
      r["Pausada"]["seconds_heard"] == "44",
      f"{r['Pausada']['seconds_heard']}s de 300s")
check("e por isso ela NAO sobe", r["Pausada"]["status"] == "skipped",
      r["Pausada"]["status"])
check("a que tocou de verdade sobe", r["Depois"]["status"] == "pending",
      f"{r['Depois']['seconds_heard']}s de 300s")

# Duas medidas do mesmo rowid se SOMAM. E o caso de "ouvi metade, almocei,
# voltei e ouvi o resto": a pausa longa fecha a faixa com o que tinha, e o
# resto chega depois. Somar e o que faz isso contar como a musica inteira.
fila = (f"b1\t{INI - 60}\n" + p1(60, INI, "Em duas partes", 300) + "\n"
        + t1(60, 150) + "\n" + t1(60, 145) + "\n")
r = rodar(fila, "somado")
check("as duas medidas somam", r["Em duas partes"]["seconds_heard"] == "295",
      f"{r['Em duas partes']['seconds_heard']}s")
check("e a faixa inteira sobe", r["Em duas partes"]["status"] == "pending",
      r["Em duas partes"]["status"])

# A regua e a incerteza da medicao, nao folga. 268 de 300 da 89,3%: reprova
# por 2 segundos. Com a regua de 15s — o daemon so descobre que o audio parou
# na volta seguinte — passa, que e o certo para faixa ouvida ate o fim.
fila = (f"b1\t{INI - 60}\n" + p1(70, INI, "Quase", 300) + "\n"
        + t1(70, 268, 15) + "\n")
r = rodar(fila, "regua")
check("a margem da regua salva a faixa ouvida ate o fim",
      r["Quase"]["status"] == "pending",
      f"{r['Quase']['seconds_heard']}s de 300s -> {r['Quase']['status']}")

# Mas ela nao salva um pulo: 150 de 300 nao vira 300 com regua nenhuma.
fila = (f"b1\t{INI - 60}\n" + p1(71, INI, "Pulo", 300) + "\n"
        + t1(71, 150, 60) + "\n")
r = rodar(fila, "regua2")
check("e nao salva um pulo pela metade", r["Pulo"]["status"] == "skipped",
      f"{r['Pulo']['seconds_heard']}s de 300s -> {r['Pulo']['status']}")

# O PISO DA REGRA. A margem e a incerteza de quem pausou muitas vezes, e uma
# incerteza grande nao pode virar licenca: ela nunca derruba a regra em mais
# de dez pontos, entao dos 90% sobra um piso de 80% da faixa tocado.
#
# A faixa aqui tem 200s de proposito. Acima de uns 267s quem manda e o teto
# de 240s (a regra dos "quatro minutos" do Last.fm), e nao os 90% — a margem
# nem chega a ser consultada, e o teste nao estaria testando nada.
#
# A fila alega 600s de incerteza: a margem util e 20 (10% de 200), nao 600.
for medido, esperado in ((159, "skipped"), (160, "pending")):
    fila = (f"b1\t{INI - 60}\n"
            + p1(90 + medido, INI, f"Piso{medido}", 200) + "\n"
            + t1(90 + medido, medido, 600) + "\n")
    r = rodar(fila, f"piso{medido}")
    check(f"com {medido}s de 200s ({medido // 2}%) -> {esperado}",
          r[f"Piso{medido}"]["status"] == esperado,
          r[f"Piso{medido}"]["status"])

print()
print("=" * 74)
print("6b. a faixa que esta tocando agora nao e chamada de 'skipped'")
print("=" * 74)
# A medicao sai em parcelas, entao "ja tem medida" nao quer dizer "acabou".
# Uma faixa no segundo 35 de 133 tem 26% medidos — se a planilha do cartao
# dissesse "skipped" ali, a pessoa leria uma acusacao falsa contra o proprio
# programa no meio da musica que esta ouvindo.
AGORINHA = AGORA - 35
fila = (f"b1\t{AGORINHA - 10}\n" + p1(80, AGORINHA, "Tocando agora", 133) + "\n"
        + t1(80, 30, 15, fim=False) + "\n")
r = rodar(fila, "emcurso")
check("parcela sem 'fim' e faixa em curso, nao pulada",
      r["Tocando agora"]["status"] == "playing",
      f"{r['Tocando agora']['seconds_heard']}s de 133s -> "
      f"{r['Tocando agora']['status']}")

# A MESMA medida, agora com o daemon dizendo que a faixa acabou: 30 de 133 e
# pulo, e ai sim a palavra e skipped.
fila = (f"b1\t{AGORINHA - 10}\n" + p1(81, AGORINHA, "Largada", 133) + "\n"
        + t1(81, 30, 15) + "\n")
r = rodar(fila, "largada")
check("com 'fim', a mesma medida vira pulo",
      r["Largada"]["status"] == "skipped",
      f"{r['Largada']['seconds_heard']}s de 133s -> {r['Largada']['status']}")

# E uma faixa que nunca fechou porque o aparelho travou nao fica "tocando"
# para sempre: passado o tempo dela, acabou de algum jeito.
VELHA = AGORA - 900
fila = (f"b1\t{VELHA - 10}\n" + p1(82, VELHA, "Travou no meio", 133) + "\n"
        + t1(82, 30, 15, fim=False) + "\n")
r = rodar(fila, "travou")
check("faixa velha sem fecho nao fica 'tocando' para sempre",
      r["Travou no meio"]["status"] == "skipped",
      f"{r['Travou no meio']['status']}")

print()
print("=" * 74)
print("6c. duas faixas numa colheita so: a primeira NAO pode sair com zero")
print("=" * 74)
# Relato da vi: "a primeira faixa de qualquer album nunca sobe, sobe a
# seguinte; e ela aparece no scrobbling now".
#
# Com o aparelho ocioso o laco cai para 60s, entao comecar um album pode por
# duas linhas no banco antes da primeira olhada. Todas recebem o mesmo
# carimbo — o da colheita —, o espaco entre elas da ZERO, e todas menos a
# ultima eram descartadas por "nao ouviu nada". O tocando agora nao depende
# disso, e por isso a faixa aparecia la e morria na hora de subir.
#
# A correcao: as anteriores a ultima nao foram vistas comecar, que e a mesma
# situacao do lote atrasado — entao vao com a1 e o PC reconstroi as horas
# para tras pela duracao de cada uma.
COLHEITA = AGORA - 700
fila = (f"b1\t{COLHEITA - 60}\n"
        + f"a1\t{COLHEITA}\t1\n"                 # a primeira, reconstruida
        + p1(95, COLHEITA, "Primeira do album", 240) + "\n"
        + p1(96, COLHEITA, "Segunda", 240) + "\n"   # mesmo carimbo, de proposito
        + t1(96, 235) + "\n")
r = rodar(fila, "colheita2")
pri = r["Primeira do album"]
check("a primeira do album nao sai com zero",
      pri["seconds_heard"] != "0", f"{pri['seconds_heard']}s de 240s")
check("e ela sobe", pri["status"] == "pending",
      f"{pri['seconds_heard']}s -> {pri['status']}")
check("a segunda continua subindo pelo tempo medido",
      r["Segunda"]["status"] == "pending",
      f"{r['Segunda']['seconds_heard']}s -> {r['Segunda']['status']}")
check("e as duas nao levam a MESMA hora",
      pri["started_at_epoch"] != r["Segunda"]["started_at_epoch"],
      f"{pri['started_at_epoch']} vs {r['Segunda']['started_at_epoch']}")

# Sem o a1 — como era antes — a primeira sai com zero e nao sobe. Este e o
# defeito, e fica aqui escrito para nao voltar sem alguem perceber.
fila = (f"b1\t{COLHEITA - 60}\n"
        + p1(97, COLHEITA, "Sem o a1", 240) + "\n"
        + p1(98, COLHEITA, "Seguinte", 240) + "\n" + t1(98, 235) + "\n")
r = rodar(fila, "colheita_sem_a1")
check("sem o a1, a primeira sairia com zero (o defeito relatado)",
      r["Sem o a1"]["seconds_heard"] == "0",
      f"{r['Sem o a1']['seconds_heard']}s -> {r['Sem o a1']['status']}")

print()
print("=" * 74)
print("6d. faixa que acabou sozinha conta, mesmo com silencio no fim")
print("=" * 74)
# Relato: "nao computa musicas que nao estejam 100% escutadas, tipo so 3:21
# de 3:27, sendo que o resto e so silencio".
#
# A duracao vem de tamanho x 8 / taxa, e num arquivo com capa e tags ela
# sobra; silencio no fim encurta o medido. Os dois juntos reprovavam faixa
# ouvida inteira.
#
# O daemon distingue: quem PULA deixa o audio tocando ate o pulo, entao o pcm
# ainda esta aberto quando a linha seguinte entra. Quando a faixa acaba
# sozinha o audio para ANTES, e o t1 sai como "fimnat".
def t1nat(rowid, ouvido, regua=15):
    return f"t1\t{rowid}\t{ouvido}\t{regua}\tfimnat"


INI2 = AGORA - 900
# O relato foi 3:21 de 3:27, mas o caso que a regra existe para resolver e a
# duracao SUPERESTIMADA: capa e tags fazem tamanho x 8 / taxa sobrar. Aqui a
# faixa dura 188s de musica e o banco declara 230 — 82%, que reprova nos 90%
# e passa nos 80% de quem chegou ao fim sozinha.
fila = (f"b1\t{INI2 - 60}\n" + p1(110, INI2, "Com silencio no fim", 230) + "\n"
        + t1nat(110, 188) + "\n")
r = rodar(fila, "fimnat")
check("acabou sozinha: conta mesmo com a duracao sobrando",
      r["Com silencio no fim"]["status"] == "pending",
      f"{r['Com silencio no fim']['seconds_heard']}s de 230s -> "
      f"{r['Com silencio no fim']['status']}")

# A MESMA medida, mas interrompida: 201 de 230 nao chega aos 90% e continua
# sendo pulo. So o fim natural afrouxa a regua.
fila = (f"b1\t{INI2 - 60}\n" + p1(111, INI2, "Pulada no fim", 230) + "\n"
        + t1(111, 188) + "\n")
r = rodar(fila, "fimint")
check("interrompida com a mesma medida continua sendo pulo",
      r["Pulada no fim"]["status"] == "skipped",
      f"{r['Pulada no fim']['seconds_heard']}s de 230s -> "
      f"{r['Pulada no fim']['status']}")

# E "acabou sozinha" nao e cheque em branco: abrir e largar no comeco tambem
# termina com o audio parado, e isso nao pode contar.
fila = (f"b1\t{INI2 - 60}\n" + p1(112, INI2, "Largada no comeco", 260) + "\n"
        + t1nat(112, 20) + "\n")
r = rodar(fila, "fimnat_curto")
check("mas largar no comeco nao vira escuta",
      r["Largada no comeco"]["status"] == "skipped",
      f"{r['Largada no comeco']['seconds_heard']}s -> "
      f"{r['Largada no comeco']['status']}")

# O caso que escapou: entre uma faixa e a proxima ha um instante de silencio,
# e num pulo o daemon pode pega-lo na volta em que olha — o pulo se disfarca
# de fim. Com a regua em metade, uma faixa pulada passada a metade subia ao
# perfil, e foi relatada assim. Com 80% ela nao passa mais.
for medido, esperado in ((155, "skipped"), (208, "pending")):
    fila = (f"b1\t{INI2 - 60}\n"
            + p1(120 + medido, INI2, f"Pulo{medido}", 260) + "\n"
            + t1nat(120 + medido, medido) + "\n")
    r = rodar(fila, f"pulo{medido}")
    check(f"'acabou sozinha' com {medido}s de 260s "
          f"({medido * 100 // 260}%) -> {esperado}",
          r[f"Pulo{medido}"]["status"] == esperado,
          r[f"Pulo{medido}"]["status"])

print()
print("=" * 74)
print("7. as duas implementacoes tem de CONCORDAR sobre o tempo medido")
print("=" * 74)
# O CSV do cartao sai do C e o que sobe ao Last.fm passa pelo Python. Se as
# duas contas divergirem, a pessoa le uma coisa no cartao e ve outra no
# perfil — e foi assim que uma versao anterior mandou faixa que o CSV
# chamava de "skipped".
from r1lastfm import fila as fila_py                      # noqa: E402

CASOS = [
    ("pausada",     p1(50, INI, "Pausada", 300),        t1(50, 44)),
    ("somada",      p1(60, INI, "Em duas partes", 300), t1(60, 150) + "\n"
                                                        + t1(60, 145)),
    ("na_regua",    p1(70, INI, "Quase", 300),          t1(70, 268, 15)),
    ("pulo",        p1(71, INI, "Pulo", 300),           t1(71, 150, 60)),
    ("sem_medida",  p1(72, INI, "Sem t1", 300),         ""),
    ("piso_baixo",  p1(73, INI, "Piso baixo", 200),     t1(73, 159, 600)),
    ("piso_alto",   p1(74, INI, "Piso alto", 200),      t1(74, 160, 600)),
    ("curta",       p1(75, INI, "Curta", 60),           t1(75, 50, 600)),
]
for nome, linha_p1, linhas_t1 in CASOS:
    texto = f"b1\t{INI - 60}\n" + linha_p1 + "\n"
    if linhas_t1:
        texto += linhas_t1 + "\n"
    r = rodar(texto, f"conc_{nome}")
    do_c = list(r.values())[0]
    regs, _ = fila_py.ler(texto)
    rec = fila_py.reconstruir(regs, agora=AGORA)
    py = rec.execucoes + [p for p, _ in rec.descartadas]
    check(f"{nome}: mesmo tempo ouvido nos dois",
          len(py) == 1 and py[0].listened == int(do_c["seconds_heard"]),
          f"C={do_c['seconds_heard']}s py="
          f"{py[0].listened if py else '?'}s")
    sobe_c = do_c["status"] in ("pending", "sent")
    sobe_py = bool(py) and py[0].scrobblable()[0]
    check(f"{nome}: mesma decisao de enviar nos dois",
          sobe_c == sobe_py, f"C={sobe_c} py={sobe_py}")

import shutil
shutil.rmtree(BASE, ignore_errors=True)
print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
