# -*- coding: utf-8 -*-
"""O "tocando agora", do laco do daemon ate o POST — sem aparelho.

Eu testei as pecas na mao, no R1, e cada uma funcionou. Nao testei o laco.
Resultado: o recurso nao funcionou na primeira instalacao de verdade, e nao
havia teste nenhum para acusar. Este arquivo cobre o caminho inteiro.

O "player" de mentira e um script chamado hiby_player que mantem o arquivo de
audio aberto num descritor — que e exatamente o que o player do R1 faz, e o
que a deteccao procura em /proc/PID/fd.

Aqui tambem fica a regressao da trava: guardar o pid num arquivo que sobrevive
ao desligamento fazia o daemon confundir um pid reaproveitado com uma segunda
instancia e sair calado, deixando o scrobbler morto apos cada reinicio.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, re, sqlite3, sys

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
r = Runner(log=Log(os.path.join(WORK, "t_agora.log")), wsl_distro="Ubuntu")
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
T = f"{home}/.cache/r1lastfm/agtest"
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

# Uma biblioteca de mentira, no formato do banco do R1: caminhos "a:\..."
ESQUEMA = """CREATE TABLE MEDIA_TABLE (id INTEGER, path TEXT, name TEXT,
 album TEXT, artist TEXT, genre TEXT, year INTEGER, size INTEGER,
 sample_rate INTEGER, bit_rate INTEGER, album_artist TEXT);
CREATE TABLE HISTORY_TABLE (id INTEGER, path TEXT, name TEXT,
 album TEXT, artist TEXT, genre TEXT, year INTEGER, size INTEGER,
 sample_rate INTEGER, bit_rate INTEGER, album_artist TEXT)"""

FAIXAS = [
    ("Vessel", "Fake You Out.flac", "twenty one pilots", "Fake You Out", 230),
    ("Unravel", "Acoustic Installation.flac",
     "TK from Ling tosite sigure", "Acoustic Installation", 362),
]
banco = os.path.join(WORK, "ag_media.db")
if os.path.exists(banco):
    os.remove(banco)
con = sqlite3.connect(banco)
con.executescript(ESQUEMA)
for alb, arq, art, tit, dur in FAIXAS:
    con.execute("INSERT INTO MEDIA_TABLE (id,path,name,album,artist,genre,"
                "year,size,sample_rate,bit_rate,album_artist) "
                "VALUES (0,?,?,?,?,?,2020,?,44100,320000,NULL)",
                (f"a:\\Musicas\\{alb}\\{arq}\0", tit + "\0", alb + "\0",
                 art + "\0", "Unknown\0", dur * 320000 // 8))
con.commit(); con.close()

OK_NP = ('{"nowplaying":{"artist":{"corrected":"0","#text":"x"},'
         '"track":{"corrected":"0","#text":"y"},'
         '"ignoredMessage":{"code":"0","#text":""}}}')

preparar = f"""
pkill -f "{T}/" 2>/dev/null || true
sleep 1
rm -rf {T}; mkdir -p {T}/scrobble {T}/tmp {T}/mus/Vessel {T}/mus/Unravel
cp {SEND} {T}/scrobble/r1send;    chmod 755 {T}/scrobble/r1send
cp {COLE} {T}/scrobble/r1collect; chmod 755 {T}/scrobble/r1collect
cp {r.to_posix_path(banco)} {T}/banco.db
printf '%s\\n' '0000000000000000000000000000000f' > {T}/scrobble/sk
printf '%s\\n' '{SEC}' > {T}/scrobble/segredo
printf '%s\\n' '{KEY}' > {T}/scrobble/apikey
printf '%s\\n' 'cacert de mentira' > {T}/scrobble/cacert.pem
: > {T}/scrobble/enviados
: > {T}/scrobble/fila.tsv
echo 0 > {T}/scrobble/estado

# os arquivos de audio, e um "player" que os mantem abertos
head -c 40000 /dev/zero > "{T}/mus/Vessel/Fake You Out.flac"
head -c 40000 /dev/zero > "{T}/mus/Unravel/Acoustic Installation.flac"
# Um "player" de mentira: um script cujo nome de comando contem
# hiby_player e que mantem o arquivo de audio aberto num descritor, que e
# exatamente o que o player do R1 faz.
cat > {T}/hiby_player <<'FIMPLAYER'
#!/bin/sh
exec 3< "$1"
sleep 300
FIMPLAYER
chmod 755 {T}/hiby_player

cat > {T}/scrobble/curl <<'FIMCURL'
#!/bin/sh
saida=""
corpo=""
while [ $# -gt 0 ]; do
    case "$1" in
        -o) saida="$2"; shift 2;;
        --data-binary) corpo="${{2#@}}"; shift 2;;
        *) shift;;
    esac
done
[ -n "$corpo" ] && cat "$corpo" >> {T}/tmp/corpos_enviados
echo "---" >> {T}/tmp/corpos_enviados
[ -n "$saida" ] && cat > "$saida" <<'FIMRESP'
{OK_NP}
FIMRESP
exit 0
FIMCURL
chmod 755 {T}/scrobble/curl

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/scrobble#' \\
    -e 's#^DB=.*#DB={T}/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/nada.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/tmp/copia.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/tmp/parcial.tsv#' \\
    -e 's#^CORPO=/tmp/.r1sc.post#CORPO={T}/tmp/post#' \\
    -e 's#^IDS=.*#IDS={T}/tmp/ids#' \\
    -e 's#^RESP=/tmp/.r1sc.resp#RESP={T}/tmp/resp#' \\
    -e 's#^CORPO_NP=.*#CORPO_NP={T}/tmp/np#' \\
    -e 's#^RESP_NP=.*#RESP_NP={T}/tmp/npresp#' \\
    -e 's#^META=.*#META={T}/tmp/meta#' \\
    -e 's#^LOG=.*#LOG={T}/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/tmp/rodando#' \\
    -e 's#^CACERT_SD=.*#CACERT_SD={T}/nao-existe.pem#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^ASSENTAR=5#ASSENTAR=1#' -e 's#^ESPERA_IMEDIATO=45#ESPERA_IMEDIATO=2#' -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#^QUIETOS=8#QUIETOS=3#' \\
    -e 's#^ENVIO=720#ENVIO=9999#' \\
    -e 's#^AGORA=0#AGORA={{AG}}#' \\
    {SH} > {T}/r1scrobbled
chmod 755 {T}/r1scrobbled
"""


def rodar(ag, segundos=8, trocar_faixa=False, name="agora"):
    # O player de mentira fica preso num `sleep`, e um TERM so seria tratado
    # quando ele terminasse. Para a troca de faixa acontecer de verdade, ele e
    # os filhos precisam morrer na hora — senao os dois ficam vivos e a
    # deteccao continua achando o primeiro.
    troca = f"""
sleep 4
pkill -9 -P $PLAYER 2>/dev/null
kill -9 $PLAYER 2>/dev/null
sleep 1
{T}/hiby_player "{T}/mus/Unravel/Acoustic Installation.flac" &
PLAYER=$!
echo "--- troquei de faixa, e o r1collect ve: $({T}/scrobble/r1collect tocando) ---"
""" if trocar_faixa else ""
    script = f"""
{preparar.replace('{AG}', str(ag))}
{T}/hiby_player "{T}/mus/Vessel/Fake You Out.flac" &
PLAYER=$!
sleep 1
busybox ash {T}/r1scrobbled &
PID=$!
{troca}
sleep {segundos}
kill -TERM $PID 2>/dev/null
pkill -9 -P $PLAYER 2>/dev/null; kill -9 $PLAYER 2>/dev/null
sleep 2
echo "=== LOG ==="
cat {T}/tmp/log 2>/dev/null
echo "=== CORPOS ENVIADOS ==="
cat {T}/tmp/corpos_enviados 2>/dev/null
"""
    return r.posix_script(script, name=name, mutating=False, quiet=True,
                          timeout=180)


print("=" * 74)
print("1. o r1collect acha o 'player' de mentira")
print("=" * 74)
res = r.posix_script(preparar.replace("{AG}", "1") + f"""
{T}/hiby_player "{T}/mus/Vessel/Fake You Out.flac" &
P=$!
sleep 1
{T}/scrobble/r1collect tocando; echo "rc=$?"
{T}/scrobble/r1collect buscar {T}/banco.db "$({T}/scrobble/r1collect tocando)"
echo "buscar rc=$?"
kill $P 2>/dev/null
""", name="agora-detecta", mutating=False, quiet=True, timeout=120)
print("\n".join("   " + l for l in res.stdout.splitlines()[:10]))
check("achou o arquivo aberto", "Fake You Out.flac" in res.stdout,
      res.stdout.strip().splitlines()[0][:60] if res.stdout.strip() else "")
check("achou os metadados", "twenty one pilots" in res.stdout
      and "230" in res.stdout)

print()
print("=" * 74)
print("2. com AGORA=1, o daemon anuncia a faixa")
print("=" * 74)
res = rodar(1, segundos=8, name="agora-ligado")
saida = res.stdout
print("\n".join("   " + l for l in saida.splitlines()[:14]))
check("o log registra o anuncio", "tocando agora:" in saida,
      " ".join(l for l in saida.splitlines() if "tocando" in l)[:70])
check("com o artista e o titulo certos",
      "twenty one pilots — Fake You Out" in saida,
      " ".join(l for l in saida.splitlines() if "tocando agora" in l)[:70])
corpo = saida.split("=== CORPOS ENVIADOS ===")[-1] if "CORPOS" in saida else ""
check("mandou um updateNowPlaying", "track.updateNowPlaying" in corpo,
      corpo.strip()[:90])
check("com o artista codificado", "twenty+one+pilots" in corpo, corpo[:90])
check("e com a duracao", "duration=230" in corpo, corpo[:110])
check("assinado", "api_sig=" in corpo)
so_log = [l for l in saida.splitlines()
          if l.strip().startswith("tocando agora:")]
check("anunciou UMA vez so, nao a cada volta", len(so_log) == 1,
      f"{len(so_log)} anuncios em 8s com RAPIDO=1")

print()
print("=" * 74)
print("3. trocar de faixa gera um anuncio novo")
print("=" * 74)
res = rodar(1, segundos=10, trocar_faixa=True, name="agora-troca")
saida = res.stdout
anuncios = [l for l in saida.splitlines()
            if l.strip().startswith("tocando agora:")]
print("\n".join("   " + l for l in anuncios))
check("dois anuncios", len(anuncios) == 2, f"{len(anuncios)}")
check("o segundo e a faixa nova",
      len(anuncios) > 1 and "Acoustic Installation" in anuncios[1],
      anuncios[1][:70] if len(anuncios) > 1 else "")

print()
print("=" * 74)
print("4. com AGORA=0, nao anuncia nada")
print("=" * 74)
res = rodar(0, segundos=6, name="agora-desligado")
check("nenhum anuncio", "tocando agora:" not in res.stdout)
check("e nenhum POST", "updateNowPlaying" not in res.stdout)

print()
print("=" * 74)
print("5. a trava velha de um boot anterior nao mata o daemon")
print("=" * 74)
# Foi o bug que matou o scrobbler depois de reiniciar o aparelho: o pid
# guardado sobrevivia ao boot e outro processo qualquer herdava o numero.
script5 = f"""
{preparar.replace('{AG}', '0')}
# uma trava com o pid de um processo VIVO que nao e o daemon
sleep 120 &
INTRUSO=$!
echo $INTRUSO > {T}/tmp/rodando
busybox ash {T}/r1scrobbled &
PID=$!
sleep 4
p=$(cat {T}/tmp/rodando 2>/dev/null)
if [ -n "$p" ] && [ -d /proc/$p ] && grep -qa r1scrobbled /proc/$p/cmdline 2>/dev/null; then
    echo "SUBIU=sim"
else
    echo "SUBIU=nao"
fi
[ -s {T}/tmp/log ] && echo "LOG=sim" || echo "LOG=nao"
kill -TERM $PID 2>/dev/null; kill $INTRUSO 2>/dev/null
sleep 1
"""
res5 = r.posix_script(script5, name="agora-trava", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res5.stdout.splitlines()[:8]))
check("o daemon subiu mesmo com a trava ocupada por outro processo",
      "SUBIU=sim" in res5.stdout,
      "ficou preso na trava velha" if "SUBIU=nao" in res5.stdout else "")
check("e deixou registro", "LOG=sim" in res5.stdout)

print()
print("=" * 74)
print("6. mas DUAS instancias de verdade continuam impedidas")
print("=" * 74)
script6 = f"""
{preparar.replace('{AG}', '0')}
busybox ash {T}/r1scrobbled &
PID=$!
sleep 3
antes=$(wc -l < {T}/tmp/log)
busybox ash {T}/r1scrobbled
echo "segunda saiu rc=$?"
sleep 1
depois=$(wc -l < {T}/tmp/log)
echo "linhas de log antes=$antes depois=$depois"
kill -TERM $PID 2>/dev/null
sleep 1
"""
res6 = r.posix_script(script6, name="agora-duas", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res6.stdout.splitlines()[:6]))
m = re.search(r"antes=(\d+) depois=(\d+)", res6.stdout)
check("a segunda instancia desiste", "rc=0" in res6.stdout)
check("e nao escreve no log", bool(m) and m.group(1) == m.group(2),
      m.group(0) if m else "")

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
