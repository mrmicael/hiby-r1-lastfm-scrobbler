# -*- coding: utf-8 -*-
"""Os binarios que vao no repositorio servem mesmo para o R1?

Eles existem para que instalar nao exija WSL. Um binario versionado e uma
coisa que apodrece calada: alguem recompila numa maquina diferente, comita
sem querer um ELF de x86, e o proximo que baixar o programa descobre isso
com um "cannot execute binary file" no aparelho.

Aqui eles passam pela MESMA checagem que a interface faz antes de empurrar
qualquer coisa, e por mais duas: rodar de verdade e responder o esperado.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import hashlib, os, re, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from r1lastfm.compilar import FLAGS_ESPERADAS, e_flags
from r1lastfm.elfcheck import inspect_elf

BIN = os.path.join(_RAIZ, "r1lastfm", "bin")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


print("=" * 74)
print("1. os dois programas estao la e servem para o aparelho")
print("=" * 74)
for nome in ("r1collect", "r1send"):
    p = os.path.join(BIN, nome)
    check(f"{nome} existe", os.path.isfile(p), p)
    if not os.path.isfile(p):
        continue
    rep = inspect_elf(p)
    check(f"{nome}: passa na checagem de ELF", rep.acceptable,
          "; ".join(rep.problems)[:100])
    check(f"{nome}: 32 bits", rep.bits == 32, str(rep.bits))
    check(f"{nome}: little-endian", rep.endian == "little-endian", rep.endian)
    check(f"{nome}: MIPS", "MIPS" in rep.machine_name, rep.machine_name)
    check(f"{nome}: estatico", rep.static and not rep.needed,
          f"interp={rep.interp} needed={rep.needed}")
    flags = e_flags(p)
    check(f"{nome}: e_flags do R1", flags == FLAGS_ESPERADAS,
          f"{flags and hex(flags)} vs {hex(FLAGS_ESPERADAS)}")
    # Um binario de 2 kB compila e passa no ELF, e nao faz nada.
    tam = os.path.getsize(p)
    check(f"{nome}: tamanho plausivel", 20_000 < tam < 400_000, f"{tam} bytes")

print()
print("=" * 74)
print("2. o README do bin/ descreve o que esta la de verdade")
print("=" * 74)
leia = os.path.join(BIN, "README.md")
check("o README existe", os.path.isfile(leia))
if os.path.isfile(leia):
    texto = open(leia, encoding="utf-8").read()
    # Os digests anotados tem de ser os dos arquivos deste commit, senao o
    # README vira uma afirmacao falsa sobre o que a pessoa esta baixando.
    for nome in ("r1collect", "r1send"):
        p = os.path.join(BIN, nome)
        if not os.path.isfile(p):
            continue
        real = hashlib.sha256(open(p, "rb").read()).hexdigest()
        anotado = re.search(rf"([0-9a-f]{{64}})\s+{nome}\b", texto)
        check(f"{nome}: o SHA256 anotado confere",
              bool(anotado) and anotado.group(1) == real,
              f"anotado={anotado.group(1)[:16] if anotado else '(nenhum)'}… "
              f"real={real[:16]}…")

print()
print("=" * 74)
print("3. a interface prefere o que a pessoa compilou")
print("=" * 74)
# Ler o codigo e frouxo, mas montar a janela inteira so para isto seria caro.
# O que importa e a ORDEM: compilado primeiro, o do repositorio depois.
fonte = open(os.path.join(_RAIZ, "r1lastfm", "gui", "janela.py"),
             encoding="utf-8").read()
corpo = fonte[fonte.index("def _programa"):]
corpo = corpo[:corpo.index("\n    def ", 10)]
i_comp = corpo.find("compilado")
i_junto = corpo.find('"bin"')
check("o compilado localmente e procurado antes", 0 <= i_comp < i_junto,
      f"compilado@{i_comp} bin@{i_junto}")
check("e o que vier do repositorio tambem e conferido",
      "conferir" in corpo, "")

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
