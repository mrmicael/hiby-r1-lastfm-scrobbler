# -*- coding: utf-8 -*-
"""O disco ouvido enquanto o daemon estava fora do ar.

Dois usuarios relataram a mesma coisa por caminhos diferentes: "ouvi o album
inteiro e apareceu 0s" e "contou como ouvida inteira assim que comecou". As
duas frases descrevem o mesmo defeito.

O coletor carimba `time(0)` em cada linha nova que encontra. Com o daemon de
pe isso e exato — cada passada acha uma faixa so. Na PRIMEIRA colheita de uma
execucao, nao: o que estava no banco ja estava la antes, e as vinte linhas
chegam com o mesmo segundo. Dai a segunda em diante tinha `visto - anterior`
igual a zero (tempo ouvido zero) e a primeira tinha como anterior a abertura
da sessao, um buraco enorme (credito integral no instante em que comecou).

O daemon passou a marcar esse lote com `a1 <hora> <n>`, e o r1send reconstroi
as horas so ali. Este teste cobre as duas metades: o lote recuperado tem de
virar scrobbles com horas distintas e crescentes, e o que veio depois — onde o
espaco entre as linhas e tempo real — tem de continuar filtrando pulos.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import csv, os, subprocess, sys, tempfile

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from comum import compilar_para_o_pc  # noqa: E402
from r1lastfm.applog import Log       # noqa: E402
from r1lastfm.runner import Runner    # noqa: E402

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


WORK = os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "lastfm")
os.makedirs(WORK, exist_ok=True)
runner = Runner(log=Log(os.path.join(WORK, "t_lote.log")), wsl_distro="Ubuntu")
compilar_para_o_pc(runner, "r1send")
EXE = runner.to_posix_path(os.path.join(WORK, "r1send"))
BASE = tempfile.mkdtemp(prefix="t_lote-")


def linha_p1(rowid, visto, titulo, dur, inicio=""):
    return "\t".join(["p1", str(rowid), str(visto), "Artista", titulo,
                      "Album", "", str(dur), "2020", "a:\\x.flac", str(inicio)])


def rodar(fila_txt, nome):
    fila = os.path.join(BASE, f"fila_{nome}.tsv")
    envi = os.path.join(BASE, f"env_{nome}")
    saida = os.path.join(BASE, f"rel_{nome}.csv")
    with open(fila, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fila_txt)
    open(envi, "w").close()
    runner.posix(f"{EXE} relatorio {runner.to_posix_path(fila)} "
                 f"{runner.to_posix_path(envi)} {runner.to_posix_path(saida)}",
                 mutating=True, quiet=True)
    with open(saida, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# T0 e a hora em que o daemon subiu. As seis faixas ja estavam no banco.
T0 = 1785600000
DUR = 200
# O daemon acorda, olha o banco 30s depois e acha as seis de uma vez.
COLETA = T0 + 30

print("=" * 74)
print("1. o disco que tocou com o daemon fora do ar")
print("=" * 74)
fila = f"b1\t{T0}\n" + f"a1\t{COLETA}\t6\n" + "".join(
    linha_p1(100 + i, COLETA, f"Faixa {i+1}", DUR) + "\n" for i in range(6))
linhas = rodar(fila, "lote")
check("as seis linhas aparecem", len(linhas) == 6, f"{len(linhas)}")
enviaveis = [l for l in linhas if l["status"] == "pending"]
check("as seis viram scrobble", len(enviaveis) == 6,
      f"{len(enviaveis)} de 6; status={[l['status'] for l in linhas]}")
ouvidos = [int(l["seconds_heard"]) for l in linhas]
check("nenhuma com 0s", all(o > 0 for o in ouvidos), str(ouvidos))
check("cada uma com a duracao cheia", all(o == DUR for o in ouvidos), str(ouvidos))

horas = [int(l["started_at_epoch"]) for l in linhas]
check("as horas sao todas diferentes", len(set(horas)) == 6, str(horas))
check("e crescem na ordem da fila", horas == sorted(horas), str(horas))
espacos = [b - a for a, b in zip(horas, horas[1:])]
check("espacadas pela duracao da faixa", all(e == DUR for e in espacos),
      str(espacos))
check("a ultima termina na hora da coleta", horas[-1] + DUR == COLETA,
      f"{horas[-1]} + {DUR} vs coleta {COLETA}")
check("a primeira comecou ANTES de o daemon subir", horas[0] < T0,
      f"{horas[0]} vs {T0}")

print()
print("=" * 74)
print("2. depois do lote, o espaco entre as linhas volta a mandar")
print("=" * 74)
# O daemon esta de pe. Tres faixas de 200s registradas a cada 20s so podem
# ter sido puladas — e pulo nao e scrobble.
fila = (f"b1\t{T0}\n" + f"a1\t{COLETA}\t1\n" + linha_p1(200, COLETA, "Ouvida", DUR) + "\n"
        + "".join(linha_p1(201 + i, COLETA + 20 * (i + 1), f"Pulada {i+1}", DUR) + "\n"
                  for i in range(3)))
linhas = rodar(fila, "pulos")
recup = [l for l in linhas if l["track"] == "Ouvida"]
pulos = [l for l in linhas if l["track"].startswith("Pulada")]
check("a recuperada continua valendo",
      recup and recup[0]["status"] == "pending", str([l["status"] for l in recup]))
check("os tres pulos sao descartados",
      all(l["status"] == "skipped" for l in pulos),
      str([(l["track"], l["seconds_heard"], l["status"]) for l in pulos]))
check("e o tempo ouvido dos pulos e o espaco real, 20s",
      all(int(l["seconds_heard"]) == 20 for l in pulos),
      str([l["seconds_heard"] for l in pulos]))

print()
print("=" * 74)
print("3. sem o marcador a1, nada muda (fila de uma versao antiga)")
print("=" * 74)
# Filas gravadas antes desta correcao nao tem a1. O comportamento tem de ser
# exatamente o de antes: sem informacao, o r1send nao inventa nada.
fila = f"b1\t{T0}\n" + "".join(
    linha_p1(300 + i, COLETA, f"Antiga {i+1}", DUR) + "\n" for i in range(3))
linhas = rodar(fila, "antiga")
check("continuam com o mesmo carimbo",
      len({l["started_at_epoch"] for l in linhas}) < 3,
      str([l["started_at_epoch"] for l in linhas]))
check("e o r1send nao promove nenhuma",
      all(l["status"] == "skipped" for l in linhas[1:]),
      str([(l["track"], l["status"]) for l in linhas]))

print()
print("=" * 74)
print("4. um a1 mentiroso nao derruba nem inventa faixa")
print("=" * 74)
# n maior que o numero de linhas, n negativo, n vazio: o arquivo vem do
# aparelho e pode estar truncado por uma queda de energia no meio da escrita.
for rot, cab in (("n maior que a fila", f"a1\t{COLETA}\t99\n"),
                 ("n negativo", f"a1\t{COLETA}\t-5\n"),
                 ("n vazio", f"a1\t{COLETA}\t\n"),
                 ("a1 sem campos", "a1\n")):
    fila = f"b1\t{T0}\n" + cab + "".join(
        linha_p1(400 + i, COLETA, f"F{i+1}", DUR) + "\n" for i in range(2))
    try:
        linhas = rodar(fila, "torto")
        check(f"{rot}: leu as duas linhas sem quebrar", len(linhas) == 2,
              f"{len(linhas)}")
    except Exception as exc:
        check(f"{rot}: leu as duas linhas sem quebrar", False, str(exc))

import shutil
shutil.rmtree(BASE, ignore_errors=True)
print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
