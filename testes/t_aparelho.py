# -*- coding: utf-8 -*-
"""Os comandos que mexem no /usr/data/init.sh do aparelho, rodados de verdade.

Este e o unico lugar em que o scrobbler escreve num arquivo que nao e dele, e
esse arquivo carrega a configuracao dos outros mods. Entao os comandos exatos
que iriam para o aparelho sao executados aqui, no busybox ash, contra um
init.sh de mentira, e o resultado e conferido byte a byte.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import os, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from r1lastfm.applog import Log
from r1lastfm.runner import Runner
from r1lastfm import aparelho as AP

SCRATCH = os.path.dirname(os.path.abspath(__file__))
r = Runner(log=Log(os.path.join(SCRATCH, "t_aparelho.log")), wsl_distro="Ubuntu")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


home = r.posix("cd && pwd", mutating=False, quiet=True).stdout.strip()
T = f"{home}/.cache/r1lastfm/aptest"
INIT = f"{T}/init.sh"

# Um init.sh parecido com o que os ajustes portados geram de verdade.
ORIGINAL = """#!/bin/sh
# /usr/data/init.sh — rodado no boot pelo supervisor do firmware patcheado.
LOG=/tmp/.r1_init.log
exec >>"$LOG" 2>&1
echo "--- init.sh $(date) ---"

# desempenho
echo 2048 > /sys/block/mmcblk0/queue/read_ahead_kb 2>/dev/null

# mono
if [ -e "/data/mnt/sd_0/_MONO_" ]; then
    cp -f /usr/data/asound.conf.mono /usr/data/asound.conf
else
    cp -f /usr/data/asound.conf.stereo /usr/data/asound.conf
fi
/usr/data/mono_watch.sh &

echo "--- init.sh fim ---"
exit 0
"""

# Os comandos EXATOS que o instalador manda para o aparelho, vindos do
# proprio modulo — nao copiados. Uma copia aqui envelheceria sozinha e
# passaria a aprovar o que o produto nao faz: foi assim que o bloco colado
# depois do `exit 0` do init.sh passou despercebido, e o daemon nunca subiu
# no boot.
add = AP.comando_ligar(INIT)
# O de remover usa `exit 0` porque cada adb shell e um shell so seu; aqui ele
# roda dentro de um script maior, entao vai num subshell.
rem = AP.comando_desligar(INIT)
ver = f"grep -qF '{AP.MARCA_INI}' {INIT} 2>/dev/null && echo SIM || echo NAO"

script = f"""
rm -rf {T}; mkdir -p {T}
cat > {INIT} <<'ORIGEOF'
{ORIGINAL}ORIGEOF
cp {INIT} {T}/original.sh

echo "=== antes: o init.sh sabe do scrobbler? ==="
{ver}

echo "=== acrescentando ==="
{add}
{ver}
echo "linhas: $(wc -l < {INIT})"

echo "=== acrescentando DE NOVO (nao pode duplicar; e o que ligar_no_boot evita) ==="
if grep -qF '{AP.MARCA_INI}' {INIT}; then echo "ja tem, nao acrescenta"; else {add}; fi
echo "ocorrencias do daemon: $(grep -c r1scrobbled {INIT})"

echo "=== o bloco esta ANTES do exit? (senao nunca roda) ==="
linha_bloco=$(grep -n "r1scrobbled" {INIT} | head -1 | cut -d: -f1)
linha_exit=$(grep -n "^[[:space:]]*exit" {INIT} | head -1 | cut -d: -f1)
echo "bloco na linha $linha_bloco, exit na linha $linha_exit"
if [ -z "$linha_exit" ] || [ "$linha_bloco" -lt "$linha_exit" ]; then
    echo "ALCANCAVEL"
else
    echo "INALCANCAVEL"
fi

echo "=== e roda mesmo? ==="
# A prova de fogo: roda o init.sh inteiro com o daemon trocado por um `touch`.
# Nao adianta olhar a saida padrao — o init.sh de verdade faz
# `exec >>"$LOG" 2>&1` logo no comeco, entao nada dele chega ao terminal. E o
# `&` do sed significa "o texto casado", nao o caractere; por isso a troca usa
# um padrao sem ele.
rm -f {T}/PROVA
sed "s#^\[ -x /usr/data/scrobble/r1scrobbled \].*#touch {T}/PROVA#" {INIT} > {T}/prova.sh
sh {T}/prova.sh >/dev/null 2>&1
[ -f {T}/PROVA ] && echo "EXECUTOU" || echo "NAO EXECUTOU"

echo "=== o init.sh ainda e valido para o shell do R1? ==="
busybox ash -n {INIT} && echo SINTAXE_OK || echo SINTAXE_RUIM

echo "=== removendo ==="
( {rem} )
{ver}

echo "=== voltou EXATAMENTE ao original? ==="
if cmp -s {INIT} {T}/original.sh; then echo IDENTICO; else echo DIFERENTE; diff {T}/original.sh {INIT}; fi

echo "=== remover de novo, com o bloco ja ausente ==="
( {rem} )
echo "rc=$?"
if cmp -s {INIT} {T}/original.sh; then echo AINDA_IDENTICO; else echo ESTRAGOU; fi

echo "=== e se o init.sh nem existir? ==="
rm -f {INIT}
( {rem} )
echo "rc_sem_arquivo=$?"
[ -f {INIT} ] && echo "criou arquivo (nao devia)" || echo "nao criou nada"

echo "=== nao deixou .bak para tras? ==="
ls {T}/*.bak 2>/dev/null && echo "SOBROU BAK" || echo "sem bak"
"""

res = r.posix_script(script, name="init-sh", mutating=False, quiet=True,
                     timeout=120)
saida = res.stdout
print("\n".join("   " + l for l in saida.splitlines()))
print()

blocos = saida.split("===")
check("comeca sem o bloco", "NAO" in saida.split("sabe do scrobbler? ===")[1][:20])
check("acrescentou", "SIM" in saida.split("acrescentando ===")[1][:60],
      saida.split("acrescentando ===")[1][:50].replace(chr(10), " "))
check("nao duplicou", "ocorrencias do daemon: 1" in saida,
      " ".join(l for l in saida.splitlines() if "ocorrencias" in l))
check("o bloco fica ANTES do exit", "ALCANCAVEL" in saida,
      " ".join(l for l in saida.splitlines() if "linha" in l))
check("e realmente executa quando o init.sh roda", "EXECUTOU" in saida
      and "NAO EXECUTOU" not in saida,
      "o bloco existe no arquivo mas nunca roda" if "NAO EXECUTOU" in saida else "")
check("o init.sh continua valido no busybox ash", "SINTAXE_OK" in saida)
check("removeu", "NAO" in saida.split("removendo ===")[1][:20])
check("voltou identico ao original", "IDENTICO" in saida and "DIFERENTE" not in saida)
check("remover duas vezes nao estraga", "AINDA_IDENTICO" in saida)
check("sem o arquivo, sai limpo", "rc_sem_arquivo=0" in saida)
check("nao inventa um init.sh do nada", "nao criou nada" in saida)
check("nao deixa .bak", "sem bak" in saida)

print()
print("=" * 74)
print("o bloco que vai para o aparelho")
print("=" * 74)
print("\n".join("   " + l for l in AP.BLOCO.splitlines()))

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
