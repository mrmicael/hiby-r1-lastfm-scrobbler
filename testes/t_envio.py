# -*- coding: utf-8 -*-
"""O envio automatico do daemon, rodado de verdade no busybox ash.

O curl e trocado por um de mentira que devolve respostas controladas, para
dar para exercitar sucesso, recusa, queda de rede e recuo — sem depender da
internet nem de uma conta real. No fim, uma rodada com a rede de verdade.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, re, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from comum import compilar_para_o_pc
from r1lastfm.applog import Log
from r1lastfm.runner import Runner

SCRATCH = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SCRATCH, "lastfm")
PROJ = _RAIZ
r = Runner(log=Log(os.path.join(WORK, "t_envio.log")), wsl_distro="Ubuntu")
# Os dois programas do aparelho sao C portatil: compilados para este
# PC, respondem exatamente o mesmo que no MIPS do R1.
compilar_para_o_pc(r, "r1collect")
compilar_para_o_pc(r, "r1send")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


home = r.posix("cd && pwd", mutating=False, quiet=True).stdout.strip()
T = f"{home}/.cache/r1lastfm/envtest"
SH = r.to_posix_path(os.path.join(PROJ, "r1lastfm", "r1scrobbled.sh"))
SEND = r.to_posix_path(os.path.join(WORK, "r1send"))
COLE = r.to_posix_path(os.path.join(WORK, "r1collect"))
# As credenciais NAO ficam no repositorio: cada pessoa registra a sua chave
# em https://www.last.fm/api/account/create e a passa pelo ambiente.
KEY = _os.environ.get("LASTFM_API_KEY", "")
SEC = _os.environ.get("LASTFM_API_SECRET", "")
if not (len(KEY) == 32 and len(SEC) == 32):
    print("PULADO: defina LASTFM_API_KEY e LASTFM_API_SECRET para rodar "
          "este teste. Registre uma chave em "
          "https://www.last.fm/api/account/create")
    raise SystemExit(0)

T0 = 1785500000
fila = [f"b1\t{T0}"]
for i in range(1, 7):
    fila.append(f"p1\t{i}\t{T0 + i*300}\tArtista {i}\tFaixa {i}\tAlbum\t\t280\t2020\ta:\\x.flac\t")
fila.append(f"i1\t{T0 + 7*300}")
FILA = "\n".join(fila) + "\n"

OK_JSON = ('{"scrobbles":{"@attr":{"accepted":6,"ignored":0},"scrobble":['
           + ",".join('{"ignoredMessage":{"code":"0","#text":""}}' for _ in range(6))
           + ']}}')
ERRO_JSON = '{"error":9,"message":"Invalid session key - Please re-authenticate"}'

# O daemon com raizes trocadas, tempos curtos e o curl substituido.
preparar = f"""
rm -rf {T}; mkdir -p {T}/scrobble {T}/tmp
cp {SEND} {T}/scrobble/r1send;   chmod 755 {T}/scrobble/r1send
cp {COLE} {T}/scrobble/r1collect; chmod 755 {T}/scrobble/r1collect
printf '%s\\n' '0000000000000000000000000000000f' > {T}/scrobble/sk
printf '%s\\n' '{SEC}' > {T}/scrobble/segredo
printf '%s\\n' '{KEY}' > {T}/scrobble/apikey
printf '%s\\n' 'certificado de mentira' > {T}/scrobble/cacert.pem
: > {T}/scrobble/enviados
cat > {T}/scrobble/fila.tsv <<'FIMFILA'
{FILA}FIMFILA

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/scrobble#' \\
    -e 's#^DB=.*#DB={T}/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/mp.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/tmp/copia.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/tmp/parcial.tsv#' \\
    -e 's#^CORPO=.*#CORPO={T}/tmp/post#' \\
    -e 's#^IDS=.*#IDS={T}/tmp/ids#' \\
    -e 's#^RESP=.*#RESP={T}/tmp/resp#' \\
    -e 's#^LOG=.*#LOG={T}/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/tmp/rodando#' \
    -e 's#^CACERT_SD=.*#CACERT_SD={T}/nao-existe.pem#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^ASSENTAR=5#ASSENTAR=1#' -e 's#^ESPERA_IMEDIATO=45#ESPERA_IMEDIATO=2#' \\
    -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#^QUIETOS=8#QUIETOS=3#' \\
    -e 's#^ENVIO=720#ENVIO=3#' \\
    -e 's#^ENVIO_MAX=7200#ENVIO_MAX=12#' \\
    {SH} > {T}/r1scrobbled
chmod 755 {T}/r1scrobbled
"""


def curl_falso(corpo_resposta, rc=0):
    """Um curl que ignora tudo e escreve a resposta combinada."""
    return f"""
cat > {T}/scrobble/curl <<'FIMCURL'
#!/bin/sh
saida=""
while [ $# -gt 0 ]; do
    case "$1" in
        -o) saida="$2"; shift 2;;
        *) shift;;
    esac
done
echo "$@" >> {T}/tmp/curl_chamado
[ -n "$saida" ] && cat > "$saida" <<'FIMRESP'
{corpo_resposta}
FIMRESP
exit {rc}
FIMCURL
chmod 755 {T}/scrobble/curl
"""


def rodar(extra, segundos=8, name="envio", shell="busybox ash"):
    # O shell importa: o shebang do script levaria ao /bin/sh do Ubuntu, que e
    # dash, e dash nao tem `read -t`. O R1 usa busybox ash.
    script = f"""
{preparar}
{extra}
mkdir -p {T}/tmp
touch {T}/banco.db
{shell} {T}/r1scrobbled &
PID=$!
sleep {segundos}
kill -TERM $PID 2>/dev/null || true
sleep 2
echo "=== LOG ==="
cat {T}/tmp/log 2>/dev/null
echo "=== ENVIADOS ==="
cat {T}/scrobble/enviados 2>/dev/null
echo "=== CURL FOI CHAMADO? ==="
wc -l < {T}/tmp/curl_chamado 2>/dev/null || echo 0
"""
    return r.posix_script(script, name=name, mutating=False, quiet=True,
                          timeout=180)


print("=" * 74)
print("1. detecta rota default sem criar processo nenhum")
print("=" * 74)
res = r.posix_script(f"""
{preparar}
. /dev/null
# extrai so a funcao tem_rede do daemon e roda
sed -n '/^tem_rede()/,/^}}/p' {T}/r1scrobbled > {T}/rede.sh
echo 'tem_rede && echo TEM || echo NAO' >> {T}/rede.sh
busybox ash {T}/rede.sh
echo "--- e com um /proc/net/route sem rota default? ---"
sed -n '/^tem_rede()/,/^}}/p' {T}/r1scrobbled | \\
  sed 's#< /proc/net/route#< {T}/route_falso#' > {T}/rede2.sh
printf 'Iface\\tDestination\\tGateway\\n' > {T}/route_falso
printf 'wlan0\\t0000A8C0\\t00000000\\n' >> {T}/route_falso
echo 'tem_rede && echo TEM || echo NAO' >> {T}/rede2.sh
busybox ash {T}/rede2.sh
""", name="rede", mutating=False, quiet=True, timeout=120)
linhas = [l.strip() for l in res.stdout.splitlines() if l.strip() in ("TEM", "NAO")]
print("\n".join("   " + l for l in res.stdout.splitlines()[:8]))
check("acha a rota default deste WSL", linhas and linhas[0] == "TEM", str(linhas))
check("sem rota default, responde NAO", len(linhas) > 1 and linhas[1] == "NAO",
      str(linhas))

print()
print("=" * 74)
print("2. caminho feliz: o Last.fm aceita, os rowid ficam marcados")
print("=" * 74)
res = rodar(curl_falso(OK_JSON), segundos=9, name="envio-ok")
saida = res.stdout
print("\n".join("   " + l for l in saida.splitlines()[:14]))
enviados = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida, re.S)
marcados = sorted(int(x) for x in enviados.group(1).split()) if enviados else []
check("as 6 execucoes foram marcadas", marcados == [1, 2, 3, 4, 5, 6], str(marcados))
check("o log registra o envio", "enviado ao Last.fm" in saida)
check("usou a espera sem fork (a economia de bateria)",
      "espera sem fork" in saida,
      " ".join(l for l in saida.splitlines() if "espera" in l or "sleep" in l)[:80])

print()
print("=" * 74)
print("2b. num shell SEM 'read -t', cai para o sleep em vez de girar solto")
print("=" * 74)
# dash nao tem `read -t`. Um daemon que nao percebesse isso giraria o laco
# sem pausa nenhuma — o pior desfecho possivel para a bateria.
res = rodar(curl_falso(OK_JSON), segundos=9, name="envio-dash", shell="dash")
saida_d = res.stdout
check("detectou a falta do 'read -t'", "usando sleep" in saida_d,
      " ".join(l for l in saida_d.splitlines() if "sleep" in l)[:70])
env_d = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida_d, re.S)
check("e mesmo assim funcionou por completo",
      sorted(int(x) for x in env_d.group(1).split()) == [1, 2, 3, 4, 5, 6]
      if env_d else False,
      (env_d.group(1).replace(chr(10), " ") if env_d else "")[:40])

print()
print("=" * 74)
print("3. o Last.fm recusa: nada pode ser marcado")
print("=" * 74)
res = rodar(curl_falso(ERRO_JSON), segundos=9, name="envio-erro")
saida = res.stdout
enviados = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida, re.S)
marcados = (enviados.group(1).strip() if enviados else "x")
check("nada marcado como enviado", marcados == "", repr(marcados[:40]))
check("o log diz que nao confirmou", "nao confirmou" in saida or "recusou" in saida,
      " / ".join(l for l in saida.splitlines() if "rc=" in l or "recus" in l)[:90])

print()
print("=" * 74)
print("4. curl falha (sem rede de verdade): nada marcado, e recua")
print("=" * 74)
res = rodar(curl_falso("", rc=7), segundos=14, name="envio-semrede")
saida = res.stdout
enviados = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida, re.S)
check("nada marcado", (enviados.group(1).strip() if enviados else "x") == "")
check("registrou a falha do curl", "curl falhou" in saida,
      " ".join(l for l in saida.splitlines() if "curl" in l)[:80])
chamadas = re.search(r"=== CURL FOI CHAMADO\? ===\s*(\d+)", saida)
n = int(chamadas.group(1)) if chamadas else -1
check("recuou em vez de martelar", 0 < n <= 4,
      f"{n} chamadas em 14s com ENVIO=3 (sem recuo seriam ~4+)")

print()
print("=" * 74)
print("5. sem chave de sessao, nem tenta")
print("=" * 74)
res = rodar(curl_falso(OK_JSON) + f"\nrm -f {T}/scrobble/sk\n",
            segundos=8, name="envio-semsk")
saida = res.stdout
chamadas = re.search(r"=== CURL FOI CHAMADO\? ===\s*(\d+)", saida)
check("curl nunca foi chamado",
      chamadas and int(chamadas.group(1)) == 0,
      f"{chamadas.group(1) if chamadas else '?'} chamadas")

print()
print("=" * 74)
print("6. sem cacert, o envio e adiado (nao manda a chave as cegas)")
print("=" * 74)
res = rodar(curl_falso(OK_JSON) + f"\nrm -f {T}/scrobble/cacert.pem\n",
            segundos=8, name="envio-semca")
saida = res.stdout
check("adiou por falta de certificados", "sem cacert" in saida,
      " ".join(l for l in saida.splitlines() if "cacert" in l)[:80])
chamadas = re.search(r"=== CURL FOI CHAMADO\? ===\s*(\d+)", saida)
check("e nao chamou o curl", chamadas and int(chamadas.group(1)) == 0,
      f"{chamadas.group(1) if chamadas else '?'}")

print()
print("=" * 74)
print("7. fila grande: manda em lotes ate acabar")
print("=" * 74)
grande = [f"b1\t{T0}"]
for i in range(1, 121):
    grande.append(f"p1\t{i}\t{T0 + i*300}\tArt {i}\tFx {i}\tAl\t\t280\t2020\ta:\\x.flac\t")
grande.append(f"i1\t{T0 + 121*300}")
GRANDE = "\n".join(grande) + "\n"
# a resposta precisa ter uma confirmacao por faixa do lote
resp50 = ('{"scrobbles":{"scrobble":['
          + ",".join('{"ignoredMessage":{"code":"0"}}' for _ in range(50)) + ']}}')
extra = curl_falso(resp50) + f"""
cat > {T}/scrobble/fila.tsv <<'FIMG'
{GRANDE}FIMG
"""
res = rodar(extra, segundos=12, name="envio-lotes")
saida = res.stdout
enviados = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida, re.S)
marcados = sorted(int(x) for x in enviados.group(1).split()) if enviados else []
# o curl falso sempre responde 50 confirmacoes; o r1send so marca as que
# vieram na lista de ids, entao os dois primeiros lotes marcam 50 cada
check("marcou mais de um lote", len(marcados) > 50, f"{len(marcados)} marcados")
check("sem repetir rowid", len(marcados) == len(set(marcados)),
      f"{len(marcados)} vs {len(set(marcados))} distintos")

print()
print("=" * 74)
print("8. agora com a REDE DE VERDADE (chave falsa -> erro 9 tratado)")
print("=" * 74)
tem_curl = "SIM" in r.posix("command -v curl >/dev/null 2>&1 && echo SIM || echo NAO",
                            mutating=False, quiet=True).stdout
if not tem_curl:
    print("   (sem curl neste WSL; pulando)")
else:
    caminho_curl = r.posix("command -v curl", mutating=False,
                           quiet=True).stdout.strip()
    extra = f"""
cp {caminho_curl} {T}/scrobble/curl; chmod 755 {T}/scrobble/curl
cp /etc/ssl/certs/ca-certificates.crt {T}/scrobble/cacert.pem 2>/dev/null || true
"""
    res = rodar(extra, segundos=10, name="envio-real")
    saida = res.stdout
    print("\n".join("   " + l for l in saida.splitlines()[:12]))
    enviados = re.search(r"=== ENVIADOS ===\n(.*?)=== CURL", saida, re.S)
    check("nada marcado (a chave e falsa mesmo)",
          (enviados.group(1).strip() if enviados else "x") == "")
    check("o erro do Last.fm foi tratado sem quebrar o daemon",
          "nao confirmou" in saida or "recusou" in saida,
          " ".join(l for l in saida.splitlines()
                   if "rc=" in l or "recus" in l)[:100])

print()
print("=" * 74)
print("9. VIAGEM DE CARRO: horas sem WiFi, e ao voltar manda na hora")
print("=" * 74)
# Este e o caso de uso de verdade: ouvir 20 musicas sem rede e, ao chegar em
# casa, ligar o WiFi. Antes disto "sem rede" contava como falha e disparava o
# recuo exponencial — tres horas de viagem levavam o intervalo ao teto de duas
# horas, e os scrobbles ficavam esperando todo esse tempo depois de o WiFi
# voltar. Agora sem rede nao e falha, e a volta da rede dispara o envio.
sem_rota = f"{T}/route_vazio"
extra = curl_falso(OK_JSON) + f"""
printf 'Iface\tDestination\tGateway\n' > {sem_rota}
printf 'wlan0\t0000A8C0\t00000000\n' >> {sem_rota}
# o daemon passa a olhar um /proc/net/route de mentira, que comeca SEM rota
sed -i 's#< /proc/net/route#< {T}/route_atual#' {T}/r1scrobbled
cp {sem_rota} {T}/route_atual
"""
script9 = f"""
{preparar}
{extra}
mkdir -p {T}/tmp
touch {T}/banco.db
busybox ash {T}/r1scrobbled &
PID=$!
# 12 s sem rede nenhuma, com ENVIO=3: seriam 4 tentativas frustradas
sleep 12
echo "CHAMADAS_SEM_REDE=$(wc -l < {T}/tmp/curl_chamado 2>/dev/null || echo 0)"
echo "ENVIADOS_SEM_REDE=$(wc -l < {T}/scrobble/enviados 2>/dev/null || echo 0)"

# chegou em casa: liga o WiFi
cp /proc/net/route {T}/route_atual
echo "--- wifi ligado ---"
sleep 4
echo "ENVIADOS_APOS_WIFI=$(wc -l < {T}/scrobble/enviados 2>/dev/null || echo 0)"
kill -TERM $PID 2>/dev/null; sleep 2
echo "=== LOG ==="
cat {T}/tmp/log
"""
res9 = r.posix_script(script9, name="envio-viagem", mutating=False, quiet=True,
                      timeout=180)
saida9 = res9.stdout
print("\n".join("   " + l for l in saida9.splitlines()[:18]))
import re as _re
def num(chave):
    m = _re.search(chave + r"=(\d+)", saida9)
    return int(m.group(1)) if m else -1
check("sem rede: nao chamou o curl nenhuma vez", num("CHAMADAS_SEM_REDE") == 0,
      str(num("CHAMADAS_SEM_REDE")))
check("sem rede: nada foi marcado como enviado",
      num("ENVIADOS_SEM_REDE") == 0, str(num("ENVIADOS_SEM_REDE")))
check("sem rede NAO virou recuo exponencial",
      "proxima tentativa em" not in saida9,
      " ".join(l for l in saida9.splitlines() if "proxima tentativa" in l)[:60])
check("ao ligar o WiFi, o daemon percebe",
      "wifi apareceu" in saida9,
      " ".join(l for l in saida9.splitlines() if "wifi" in l)[:70])
check("e manda a fila guardada em segundos, sem esperar o relogio",
      num("ENVIADOS_APOS_WIFI") == 6, f"{num('ENVIADOS_APOS_WIFI')} de 6")


print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
