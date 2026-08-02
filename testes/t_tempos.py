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
check("RAWFEAR: NAO e enviada como terminada", rf["status"] == "skipped",
      rf["status"])

print()
print("=" * 74)
print("2. a mesma sequencia depois que o audio para")
print("=" * 74)
# O daemon viu o audio parar 3 minutos depois de RAWFEAR comecar: ela tocou
# 180 de 202 segundos — passa da metade, entao conta.
fila = (f"b1\t{CW - 60}\n" + p1(1, CW, "City Walls", 322) + "\n"
        + p1(2, RF, "RAWFEAR", 202) + "\n" + f"f1\t{RF + 180}\n")
r = rodar(fila, "parou")
check("RAWFEAR: 180s dos 202s", r["RAWFEAR"]["seconds_heard"] == "180",
      r["RAWFEAR"]["seconds_heard"])
check("RAWFEAR: agora sim vai", r["RAWFEAR"]["status"] == "pending",
      r["RAWFEAR"]["status"])
check("City Walls nao mudou", r["City Walls"]["seconds_heard"] == "322")

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
check("e nao e enviada", r["Recem comecada"]["status"] == "skipped",
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

import shutil
shutil.rmtree(BASE, ignore_errors=True)
print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
