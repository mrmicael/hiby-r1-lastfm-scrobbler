# -*- coding: utf-8 -*-
"""Quando a faixa acaba, em quanto tempo o scrobble sai?

Antes, o daemon so olhava o relogio de doze em doze minutos: uma faixa que
acabava logo depois de um envio esperava quase o ciclo inteiro. Aqui um
"player" de mentira acrescenta uma linha ao banco enquanto o daemon roda, e o
tempo ate a tentativa de envio e CRONOMETRADO — nao deduzido do codigo.

Vale para os dois casos, porque e o mesmo relogio: arquivo do cartao e Tidal.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, re, sqlite3, sys, time

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from comum import compilar_para_o_pc
from r1lastfm.applog import Log
from r1lastfm.runner import Runner

SCRATCH = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SCRATCH, "lastfm")
PROJ = _RAIZ
os.makedirs(WORK, exist_ok=True)
r = Runner(log=Log(os.path.join(WORK, "t_imediato.log")), wsl_distro="Ubuntu")
compilar_para_o_pc(r, "r1collect")
compilar_para_o_pc(r, "r1send")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


ESQUEMA = """CREATE TABLE HISTORY_TABLE (id INTEGER, path TEXT, name TEXT,
 album TEXT, artist TEXT, genre TEXT, year INTEGER, size INTEGER,
 sample_rate INTEGER, bit_rate INTEGER, album_artist TEXT)"""


def banco(caminho, faixas):
    if os.path.exists(caminho):
        os.remove(caminho)
    con = sqlite3.connect(caminho)
    con.execute(ESQUEMA)
    for art, nome, dur in faixas:
        con.execute("INSERT INTO HISTORY_TABLE (id,path,name,album,artist,"
                    "genre,year,size,sample_rate,bit_rate,album_artist) "
                    "VALUES (0,?,?,?,?,?,2020,?,44100,320000,NULL)",
                    (f"a:\\m\\{nome}.flac\0", nome + "\0", "Alb\0",
                     art + "\0", "Unknown\0", dur * 320000 // 8))
    con.commit()
    con.close()


home = r.posix("cd && pwd", mutating=False, quiet=True).stdout.strip()
T = f"{home}/.cache/r1lastfm/imtest"
SH = r.to_posix_path(os.path.join(PROJ, "r1lastfm", "r1scrobbled.sh"))
SEND = r.to_posix_path(os.path.join(WORK, "r1send"))
COLE = r.to_posix_path(os.path.join(WORK, "r1collect"))

# Dois bancos: o inicial e o "depois que mais uma faixa acabou".
b1 = os.path.join(WORK, "im1.db")
b2 = os.path.join(WORK, "im2.db")
# A linha do historico entra quando a faixa COMECA, e quem a fecha e a linha
# da faixa SEGUINTE. Entao o cenario precisa das duas:
#
#   b2  a faixa curta comeca  -> a linha dela aparece, e ela fica em aberto
#   b3  a proxima comeca      -> fecha a anterior, que agora tem tempo ouvido
#
# Entre uma e outra passa mais que a metade da duracao, senao a faixa foi
# pulada e "nada a enviar" e a resposta certa.
#
# O que este teste mede e o tempo entre o FECHAMENTO e o envio: e ai que o
# scrobble esta pronto para subir.
b3 = os.path.join(WORK, "im3.db")
DUR = 40
ESPERA_TOCANDO = 26    # > DUR/2, entao a faixa conta
banco(b1, [("yui", "Again", 257)])
banco(b2, [("yui", "Again", 257), ("FLOW", "Go", DUR)])
banco(b3, [("yui", "Again", 257), ("FLOW", "Go", DUR),
           ("TOP", "Depois", 200)])

# O daemon roda com as raizes trocadas e um curl de mentira que so anota a
# hora em que foi chamado — e a hora e o que este teste mede.
RAPIDO, LENTO = 3, 3
ENVIO = 720          # o relogio "normal": se o imediato nao funcionar, o
                     # envio so aconteceria daqui a doze minutos
script = f"""
set -e
pkill -f "{T}/" 2>/dev/null || true
sleep 1
rm -rf {T}; mkdir -p {T}/scrobble {T}/tmp
cp {SEND} {T}/scrobble/r1send;    chmod 755 {T}/scrobble/r1send
cp {COLE} {T}/scrobble/r1collect; chmod 755 {T}/scrobble/r1collect
cp {r.to_posix_path(b1)} {T}/banco.db
printf '%s\\n' '0000000000000000000000000000000f' > {T}/scrobble/sk
printf '%s\\n' '00000000000000000000000000000000' > {T}/scrobble/segredo
printf '%s\\n' '00000000000000000000000000000000' > {T}/scrobble/apikey
printf '%s\\n' 'cacert de mentira' > {T}/scrobble/cacert.pem
: > {T}/scrobble/enviados
: > {T}/scrobble/fila.tsv

# curl de mentira: anota a hora com centesimos e devolve uma resposta aceita.
cat > {T}/scrobble/curl <<'FIMCURL'
#!/bin/sh
date +%s.%N >> /tmp/imtest.curl
saida=""
anterior=""
for a in "$@"; do
    [ "$anterior" = "-o" ] && saida="$a"
    anterior="$a"
done
[ -n "$saida" ] && printf '%s' \\
  '{{"scrobbles":{{"@attr":{{"accepted":1,"ignored":0}},"scrobble":{{"ignoredMessage":{{"code":"0"}}}}}}}}' \\
  > "$saida"
exit 0
FIMCURL
chmod 755 {T}/scrobble/curl
: > /tmp/imtest.curl

# O daemon, com as raizes apontando para o cenario de mentira.
sed -e 's#^DIR=.*#DIR={T}/scrobble#' \\
    -e 's#^DB=.*#DB={T}/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/naoexiste#' \\
    -e 's#^TIDAL_INI=.*#TIDAL_INI={T}/naoexiste.ini#' \\
    -e 's#^TAT=.*#TAT={T}/naoexiste.tat#' \\
    -e 's#^RAPIDO=.*#RAPIDO={RAPIDO}#' \\
    -e 's#^LENTO=.*#LENTO={LENTO}#' \\
    -e 's#^ENVIO=.*#ENVIO={ENVIO}#' \\
    -e 's#^CACERT_SD=.*#CACERT_SD={T}/scrobble/cacert.pem#' \\
    -e 's#^TRAVA=.*#TRAVA=/tmp/imtest.trava#' \\
    -e 's#^LOG=.*#LOG=/tmp/imtest.log#' \\
    -e 's#^CARTOES=.*#CARTOES="{T}/cartao"#' \\
    {SH} > {T}/r1scrobbled
chmod 755 {T}/r1scrobbled
: > /tmp/imtest.log
mkdir -p {T}/cartao

setsid {T}/r1scrobbled </dev/null >/dev/null 2>&1 &
# Deixa o marco zero passar: a primeira rodada ignora o historico antigo.
sleep 8

# A faixa curta COMECA: o player grava a linha dela.
cp {r.to_posix_path(b2)} {T}/banco.db

# Ela toca por mais da metade da propria duracao...
sleep {ESPERA_TOCANDO}

# ...e AGORA a proxima comeca, o que fecha a anterior. E deste instante que
# o envio tem de partir.
date +%s.%N > /tmp/imtest.fim
cp {r.to_posix_path(b3)} {T}/banco.db

# Espera o suficiente para o envio imediato acontecer, e MUITO menos que os
# doze minutos do relogio normal.
sleep 40
pkill -f "{T}/" 2>/dev/null || true
sleep 1

echo "=== FIM DA FAIXA ==="
cat /tmp/imtest.fim
echo "=== CHAMADAS DO CURL ==="
cat /tmp/imtest.curl 2>/dev/null || echo "(nenhuma)"
echo "=== REGISTRO ==="
cat /tmp/imtest.log
"""

print("=" * 74)
print(f"1. faixa local acaba -> quanto tempo ate o envio (relogio normal: {ENVIO}s)")
print("=" * 74)
res = r.posix_script(script, name="imediato", timeout=300)
saida = res.output

fim = re.search(r"=== FIM DA FAIXA ===\s*\n([\d.]+)", saida)
# So os numeros DENTRO da secao das chamadas. A primeira versao deste teste
# varria a saida inteira e casava com o proprio carimbo do fim da faixa: ela
# comparava o numero consigo mesmo e anunciava, muito convincentemente,
# "atraso medido: 0.0s" — sem que uma unica chamada ao curl tivesse ocorrido.
bloco = re.search(r"=== CHAMADAS DO CURL ===\s*\n(.*?)=== REGISTRO ===",
                  saida, re.S)
curls = re.findall(r"(\d{10}\.\d+)", bloco.group(1)) if bloco else []
check("o daemon rodou e o banco mudou", bool(fim), saida[-300:] if not fim else "")
check("houve envio", bool(curls) and len(curls) >= 1,
      f"{len(curls)} chamada(s) ao curl")

if fim and curls:
    t_fim = float(fim.group(1))
    # A primeira chamada depois do fim da faixa e a que interessa.
    depois = [float(c) for c in curls if float(c) >= t_fim]
    check("o envio veio DEPOIS do fim da faixa", bool(depois),
          f"{len(depois)} de {len(curls)}")
    if depois:
        atraso = min(depois) - t_fim
        print(f"   atraso medido: {atraso:.1f}s")
        # O limite honesto: uma volta do laco para notar + uma para mandar,
        # com folga. O que importa e nao ser os 720s do relogio normal.
        check("saiu em menos de 3 voltas do laco", atraso < RAPIDO * 3 + 5,
              f"{atraso:.1f}s com laco de {RAPIDO}s")
        check("e MUITO antes do relogio normal", atraso < ENVIO / 10,
              f"{atraso:.1f}s contra {ENVIO}s")

check("a faixa foi anotada na fila", "nova(s)" in saida,
      " ".join(l for l in saida.splitlines() if "nova" in l)[:70])
check("e o envio foi confirmado", "enviado ao Last.fm" in saida,
      " ".join(l for l in saida.splitlines() if "enviado" in l)[:70])

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
