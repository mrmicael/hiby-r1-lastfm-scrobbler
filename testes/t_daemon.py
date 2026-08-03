# -*- coding: utf-8 -*-
"""O daemon roda de verdade, num aparelho falso, com o shell real do R1.

Nao e teste de leitura de codigo: o r1scrobbled e iniciado dentro do WSL com
as raizes trocadas, um script vai reescrevendo o banco como se o player
estivesse tocando musica, e a fila resultante e conferida.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, sqlite3, sys, time

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
os.makedirs(WORK, exist_ok=True)
r = Runner(log=Log(os.path.join(WORK, "t_daemon.log")), wsl_distro="Ubuntu")
# Os dois programas do aparelho sao C portatil: compilados para este
# PC, respondem exatamente o mesmo que no MIPS do R1.
compilar_para_o_pc(r, "r1collect")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


ESQUEMA = """CREATE TABLE HISTORY_TABLE (id INTEGER, path TEXT, name TEXT,
 album TEXT, artist TEXT, genre TEXT, year INTEGER, size INTEGER,
 sample_rate INTEGER, bit_rate INTEGER, album_artist TEXT)"""


def banco(path, faixas):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute(ESQUEMA)
    for i, (art, nome, alb, dur) in enumerate(faixas, 1):
        con.execute("INSERT INTO HISTORY_TABLE (id,path,name,album,artist,"
                    "genre,year,size,sample_rate,bit_rate,album_artist) "
                    "VALUES (0,?,?,?,?,?,2020,?,44100,320000,NULL)",
                    (f"a:\\m\\{nome}.flac\0", nome + "\0", alb + "\0",
                     art + "\0", "Unknown\0", dur * 320000 // 8))
    con.commit()
    con.close()


home = r.posix("cd && pwd", mutating=False, quiet=True).stdout.strip()
T = f"{home}/.cache/r1lastfm/dtest"

print("=" * 74)
print("1. sintaxe do daemon nos tres shells (dash, sh, busybox ash)")
print("=" * 74)
sh_win = os.path.join(PROJ, "r1lastfm", "r1scrobbled.sh")
# O git no Windows pode ter deixado CRLF; o busybox trata \r como parte do
# comando e da "Illegal option -".
with open(sh_win, "rb") as fh:
    dados = fh.read()
check("sem CRLF no script", b"\r\n" not in dados,
      f"{dados.count(chr(13).encode())} CR encontrados")
p = r.to_posix_path(sh_win)
tem_bb = "SIM" in r.posix("command -v busybox >/dev/null 2>&1 && echo SIM || echo NAO",
                          mutating=False, quiet=True).stdout
shells = ["dash", "sh"] + (["busybox ash"] if tem_bb else [])
for shell in shells:
    res = r.posix(f"{shell} -n {p} 2>&1", mutating=False, quiet=True)
    check(f"valido em '{shell}'", res.ok, res.stdout.strip()[:70])

print()
print("=" * 74)
print("2. o daemon rodando de verdade enquanto o 'player' toca")
print("=" * 74)
FAIXAS = [
    ("yui", "Again", "again", 257),
    ("FLOW", "Go!!!", "Go!!!", 240),
    ("twenty one pilots", "Migraine", "Vessel", 238),
    ("yui", "Again", "again", 257),          # repetida: rowid novo
]
db_local = os.path.join(WORK, "sim.db")

# Cada "faixa tocada" e o banco reescrito com uma linha a mais. E assim que o
# player se comporta: rowid cresce a cada reproducao.
# sim0 e o historico VAZIO: e assim que o daemon comeca num aparelho novo, e
# so assim as quatro reproducoes contam. Com historico preexistente a primeira
# rodada vira marco zero — o que o teste 6 cobre.
for n in range(0, len(FAIXAS) + 1):
    banco(os.path.join(WORK, f"sim{n}.db"), FAIXAS[:n])

script = f"""
set -e
rm -rf {T}
mkdir -p {T}/usr/data/scrobble {T}/tmp {T}/mp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/usr/data/scrobble/r1collect
chmod 755 {T}/usr/data/scrobble/r1collect

# O daemon com as raizes trocadas e os tempos encurtados, para o teste caber
# em segundos em vez de minutos.
sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/usr/data/scrobble#' \\
    -e 's#^DB=/usr/data/usrlocal_media.db#DB={T}/usr/data/usrlocal_media.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/mp/most_played.db#' \\
    -e 's#^COPIA=/tmp/.r1sc.db#COPIA={T}/tmp/.r1sc.db#' \\
    -e 's#^PARCIAL=/tmp/.r1sc.tsv#PARCIAL={T}/tmp/.r1sc.tsv#' \\
    -e 's#^LOG=/tmp/.r1sc.log#LOG={T}/tmp/.r1sc.log#' \
    -e 's#^TICK=/tmp/.r1sc.tick#TICK={T}/tmp/.r1sc.tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/tmp/.r1sc.rodando#' \
    -e 's#^RAPIDO=15#RAPIDO=1#' \\
    -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#^QUIETOS=8#QUIETOS=3#' \\
    {p} > {T}/r1scrobbled
chmod 755 {T}/r1scrobbled

cp {r.to_posix_path(os.path.join(WORK, 'sim0.db'))} {T}/usr/data/usrlocal_media.db

busybox ash {T}/r1scrobbled &
PID=$!
echo "daemon pid $PID"
sleep 3

for n in 1 2 3 4; do
    cp {r.to_posix_path(WORK)}/sim$n.db {T}/usr/data/usrlocal_media.db
    touch {T}/mp/most_played.db
    sleep 3
done

# silencio: o marcador i1 tem de aparecer
sleep 6

kill -TERM $PID 2>/dev/null || echo "kill falhou"
sleep 3
kill -0 $PID 2>/dev/null && echo "AINDA VIVO" || echo "daemon terminou"
echo "=== FILA ==="
cat {T}/usr/data/scrobble/fila.tsv
echo "=== ESTADO ==="
cat {T}/usr/data/scrobble/estado
echo "=== LOG ==="
cat {T}/tmp/.r1sc.log 2>/dev/null || true
echo "=== SOBROU EM /tmp? ==="
ls -A {T}/tmp/ 2>/dev/null
echo "=== TRAVA REMOVIDA? ==="
[ -f {T}/tmp/.r1sc.rodando ] && echo "ainda existe" || echo "removida"
"""
res = r.posix_script(script, name="daemon-sim", mutating=False, quiet=True,
                     timeout=180)
saida = res.stdout
print("\n".join("   " + l for l in saida.splitlines()[:40]))

fila = []
dentro = False
for ln in saida.splitlines():
    if ln.startswith("=== FILA"):
        dentro = True; continue
    if ln.startswith("==="):
        dentro = False; continue
    if dentro and ln.strip():
        fila.append(ln.split("\t"))

toca = [f for f in fila if f[0] == "p1"]
check("4 reproducoes registradas", len(toca) == 4, f"registrou {len(toca)}")
if len(toca) == 4:
    nomes = [f[4] for f in toca]
    check("na ordem em que tocaram",
          nomes == ["Again", "Go!!!", "Migraine", "Again"], str(nomes))
    check("a repetida virou uma linha nova, nao um duplicado perdido",
          toca[0][1] != toca[3][1], f"rowid {toca[0][1]} e {toca[3][1]}")
    check("duracao calculada", toca[0][7] == "257", toca[0][7])
    check("artista preservado", toca[2][3] == "twenty one pilots")
check("marcador de inicio presente", any(f[0] == "b1" for f in fila))
check("marcador do most_played presente", any(f[0] == "m1" for f in fila),
      f"{sum(1 for f in fila if f[0] == 'm1')} marcadores")
check("marcador de silencio presente", any(f[0] == "i1" for f in fila))
# O f1 e o que fecha a ULTIMA faixa de cada sessao. Sem ele ela fica em
# aberto e nunca sobe — a linha do historico entra quando a faixa comeca,
# entao a unica coisa que diz que ela acabou e o audio ter parado.
#
# Aqui nao ha pcm de verdade, entao o r1collect responde "parado" e o
# daemon fecha a faixa na volta seguinte a colheita. E exatamente o
# caminho que interessa exercitar: o do fechamento.
f1 = [f for f in fila if f[0] == "f1"]
check("marcador de fim de audio presente", bool(f1),
      f"{len(f1)} marcadores f1 — sem ele a ultima faixa nunca fecha")
if f1 and toca:
    check("o f1 vem DEPOIS da faixa que ele fecha",
          int(f1[-1][1]) >= int(toca[-1][2]),
          f"f1={f1[-1][1]} ultima_faixa={toca[-1][2]}")
check("o daemon registrou o fechamento no log",
      "audio parou" in saida,
      f"{saida.count('audio parou')} linha(s) de fechamento")

# O a1 marca o que tocou com o daemon fora do ar. Aqui o daemon sobe com o
# banco ja todo anotado (estado no topo) e as faixas aparecem DEPOIS — sao
# ao vivo, e nenhuma delas pode virar lote.
#
# Eu marcava como lote a primeira colheita de cada execucao, qualquer que
# fosse a hora dela. Numa partida sem nada atrasado, a primeira colheita e a
# proxima faixa que a pessoa tocar, e ela levava credito integral no instante
# em que comecava — a reclamacao que o lote veio resolver, reintroduzida por
# ele. Visto no aparelho: uma faixa de 260s colhida 107s depois da partida,
# reportada como ouvida por inteiro.
a1 = [f for f in fila if f[0] == "a1"]
check("nenhum a1: nada estava atrasado nesta partida", not a1,
      f"{len(a1)} marcador(es) a1 para {len(toca)} faixas ao vivo")
i1 = [f for f in fila if f[0] == "i1"]
if i1 and toca:
    check("o i1 marca o ULTIMO evento, nao a hora de detectar",
          int(i1[-1][1]) - int(toca[-1][2]) <= 2,
          f"i1={i1[-1][1]} ultima_faixa={toca[-1][2]} "
          f"delta={int(i1[-1][1]) - int(toca[-1][2])}s")
check("nao deixou lixo em /tmp", "SOBROU EM /tmp? ===" in saida
      and "r1sc.db" not in saida.split("SOBROU EM /tmp? ===")[1])
check("o daemon obedeceu ao TERM", "daemon terminou" in saida,
      "ainda vivo" if "AINDA VIVO" in saida else "")
check("trava removida ao sair", "removida" in saida)

print()
print("=" * 74)
print("3. duas instancias: a segunda desiste")
print("=" * 74)
script2 = f"""
pkill -f "$(basename {T})/r1scrobbled" 2>/dev/null || true
sleep 1
rm -f {T}/tmp/.r1sc.rodando
busybox ash {T}/r1scrobbled &
PID=$!
sleep 2
antes=$(wc -l < {T}/usr/data/scrobble/fila.tsv)
busybox ash {T}/r1scrobbled
echo "segunda saiu com rc=$?"
sleep 1
depois=$(wc -l < {T}/usr/data/scrobble/fila.tsv)
echo "linhas antes=$antes depois=$depois"
kill -TERM $PID 2>/dev/null || true
sleep 2
"""
res2 = r.posix_script(script2, name="daemon-lock", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res2.stdout.splitlines()[:10]))
check("a segunda instancia saiu limpa", "rc=0" in res2.stdout)
import re
m = re.search(r"linhas antes=(\d+) depois=(\d+)", res2.stdout)
check("a segunda nao escreveu marcador de inicio",
      bool(m) and int(m.group(2)) - int(m.group(1)) <= 1,
      m.group(0) if m else "nao achei")

print()
print("=" * 74)
print("4. copia rasgada nao avanca o estado nem suja a fila")
print("=" * 74)
script3 = f"""
rm -rf {T}/usr/data/scrobble/fila.tsv {T}/usr/data/scrobble/estado
rm -f {T}/usr/data/scrobble/.visto {T}/usr/data/scrobble/.visto2
echo 0 > {T}/usr/data/scrobble/estado

# um banco truncado no meio: o coletor tem de recusar
head -c 3000 {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} > {T}/usr/data/usrlocal_media.db
rm -f {T}/tmp/.r1sc.rodando
busybox ash {T}/r1scrobbled &
PID=$!
sleep 4
echo "--- com o banco quebrado ---"
echo "estado=$(cat {T}/usr/data/scrobble/estado)"
echo "linhas p1=$(grep -c '^p1' {T}/usr/data/scrobble/fila.tsv 2>/dev/null || echo 0)"

# agora o banco bom aparece: tem de recuperar sozinho
cp {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} {T}/usr/data/usrlocal_media.db
sleep 4
echo "--- depois do banco bom ---"
echo "estado=$(cat {T}/usr/data/scrobble/estado)"
echo "linhas p1=$(grep -c '^p1' {T}/usr/data/scrobble/fila.tsv 2>/dev/null || echo 0)"
kill -TERM $PID 2>/dev/null || true
sleep 2
"""
res3 = r.posix_script(script3, name="daemon-torn", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res3.stdout.splitlines()[:12]))
partes = res3.stdout.split("--- depois do banco bom ---")
check("banco quebrado: estado ficou em 0 e fila sem p1",
      "estado=0" in partes[0] and "linhas p1=0" in partes[0])
check("banco bom depois: recuperou sozinho",
      len(partes) > 1 and "estado=4" in partes[1] and "linhas p1=4" in partes[1],
      partes[1].strip().replace("\n", " ") if len(partes) > 1 else "")

print()
print("=" * 74)
print("5. quanto o daemon PARADO custa, medido de verdade")
print("=" * 74)
# O daemon roda parado com intervalo de 1 s. Depois de N ciclos, o tempo de
# CPU que o kernel contabilizou para ele (e para os filhos que ele criou)
# divide por N e da o custo de um ciclo. Dai extrapola-se para os intervalos
# reais.
CICLOS = 60
script4 = f"""
pkill -f "{T}/r1scrobbled" 2>/dev/null || true
sleep 1
rm -f {T}/tmp/.r1sc.rodando
# banco parado: nada muda, e o laco fica no caminho ocioso o tempo todo
busybox ash {T}/r1scrobbled &
PID=$!
sleep {CICLOS}
# campos 14..17 de /proc/PID/stat: utime stime cutime cstime, em ticks
read -r resto < /proc/$PID/stat
echo "STAT $(cut -d' ' -f14,15,16,17 /proc/$PID/stat)"
echo "HZ $(getconf CLK_TCK)"
echo "RSS_KB $(awk '/^VmRSS/{{print $2}}' /proc/$PID/status)"
kill -TERM $PID 2>/dev/null || true
sleep 2
"""
res4 = r.posix_script(script4, name="daemon-cost", mutating=False, quiet=True,
                      timeout=180)
print("\n".join("   " + l for l in res4.stdout.splitlines()[:6]))
import re as _re
mst = _re.search(r"STAT (\d+) (\d+) (\d+) (\d+)", res4.stdout)
mhz = _re.search(r"HZ (\d+)", res4.stdout)
mrss = _re.search(r"RSS_KB (\d+)", res4.stdout)
if mst and mhz:
    hz = int(mhz.group(1))
    ticks = sum(int(mst.group(i)) for i in (1, 2, 3, 4))
    seg = ticks / hz
    por_ciclo_ms = seg / CICLOS * 1000
    print(f"\n   {CICLOS} ciclos ociosos consumiram {seg*1000:.0f} ms de CPU")
    print(f"   -> {por_ciclo_ms:.2f} ms por ciclo (inclui o fork do sleep)")
    # o R1 e um MIPS de 1 GHz contra este x86; um fator 8 e conservador
    fator = 8
    for rot, ivl in (("parado (60 s)", 60), ("tocando (15 s)", 15)):
        ciclos_h = 3600 / ivl
        ms_h = por_ciclo_ms * ciclos_h * fator
        print(f"   -> {rot}: {ciclos_h:.0f} ciclos/h = {ms_h:.0f} ms de CPU "
              f"por hora no R1 ({ms_h/36000:.4f}% do tempo)")
    # O que este numero e, e o que ele nao e.
    #
    # Ele AMORTIZA a partida do daemon nos CICLOS ciclos medidos. A partida
    # faz trabalho de custo fixo — descobrir o cartao, escrever a planilha,
    # cronometrar a espera —, entao acrescentar qualquer coisa ali empurra
    # este numero para cima sem que uma volta do laco tenha ficado mais cara.
    # Medindo a inclinacao entre 60 e 180 ciclos, o custo real de uma volta
    # deu 0,417 ms.
    #
    # O que o limite protege e a regressao que importa: um fork por volta. A
    # diferenca entre esperar num fifo e chamar `sleep` e de ~8 ms por ciclo,
    # e qualquer comando externo no caminho ocioso custa a mesma ordem — foi
    # exatamente assim que a consulta do Tidal a cada volta apareceu aqui,
    # com 17,8 ms. Quatro milissegundos pegam isso com folga e nao quebram
    # numa maquina ocupada, onde a mesma medicao ja deu 2,00 e 2,33.
    check("custo por ciclo abaixo de 4 ms (espera sem fork)",
          por_ciclo_ms < 4.0, f"{por_ciclo_ms:.2f} ms")
if mrss:
    kb = int(mrss.group(1))
    print(f"   memoria residente do daemon: {kb} kB")
    # o busybox do WSL e um binario multi-chamada grande; no R1 ele ja esta
    # residente por causa do init, entao o custo real e so o incremento
    check("memoria residente plausivel", kb < 4096, f"{kb} kB")

print()
print("=" * 74)
print("6. primeira execucao: o historico antigo vira marco zero")
print("=" * 74)
# Ao instalar num aparelho que ja tem historico, essas faixas foram ouvidas
# sabe-se la quando. Se entrassem na fila, todas apareceriam com a hora de
# agora e o perfil do Last.fm levaria dezenas de execucoes falsas no mesmo
# minuto. A primeira rodada tem de so anotar onde o historico estava.
script5 = f"""
rm -rf {T}/marco; mkdir -p {T}/marco/scrobble {T}/marco/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/marco/scrobble/r1collect
chmod 755 {T}/marco/scrobble/r1collect
cp {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} {T}/marco/banco.db
sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/marco/scrobble#' \
    -e 's#^DB=.*#DB={T}/marco/banco.db#' \
    -e 's#^MAIS=.*#MAIS={T}/marco/nada.db#' \
    -e 's#^COPIA=.*#COPIA={T}/marco/tmp/c.db#' \
    -e 's#^PARCIAL=.*#PARCIAL={T}/marco/tmp/p.tsv#' \
    -e 's#^LOG=.*#LOG={T}/marco/tmp/log#' \
    -e 's#^TICK=.*#TICK={T}/marco/tmp/tick#' \
    -e 's#^TRAVA=.*#TRAVA={T}/marco/tmp/rodando#' \
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \
    -e 's#^QUIETOS=8#QUIETOS=3#' \
    {p} > {T}/marco/rs
chmod 755 {T}/marco/rs

busybox ash {T}/marco/rs &
PID=$!
sleep 4
echo "PRIMEIRA_ESTADO=$(cat {T}/marco/scrobble/estado)"
echo "PRIMEIRA_FILA=$(grep -c '^p1' {T}/marco/scrobble/fila.tsv 2>/dev/null || echo 0)"
kill -TERM $PID 2>/dev/null; sleep 2

# agora uma faixa NOVA aparece: essa tem de ser anotada
cp {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} {T}/marco/banco.db
busybox ash {T}/marco/rs &
PID=$!
sleep 2
rm -f {T}/marco/scrobble/.visto
cp {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} {T}/marco/banco.db
sleep 3
echo "SEGUNDA_ESTADO=$(cat {T}/marco/scrobble/estado)"
echo "SEGUNDA_FILA=$(grep -c '^p1' {T}/marco/scrobble/fila.tsv 2>/dev/null || echo 0)"
echo "--- log ---"
cat {T}/marco/tmp/log
kill -TERM $PID 2>/dev/null; sleep 1
"""
res5 = r.posix_script(script5, name="daemon-marco", mutating=False, quiet=True,
                      timeout=180)
print("\n".join("   " + l for l in res5.stdout.splitlines()[:14]))
import re as _r
pe = _r.search(r"PRIMEIRA_ESTADO=(\d+)", res5.stdout)
pf = _r.search(r"PRIMEIRA_FILA=(\d+)", res5.stdout)
check("o estado pulou para o topo do historico",
      bool(pe) and int(pe.group(1)) == 4, pe.group(1) if pe else "?")
check("e NADA foi anotado como execucao",
      bool(pf) and int(pf.group(1)) == 0, pf.group(1) if pf else "?")
check("o log explica o que aconteceu",
      "historico antigo ignorado" in res5.stdout,
      " ".join(l for l in res5.stdout.splitlines() if "marco" in l)[:80])
check("na segunda vez nao repete o marco",
      res5.stdout.count("historico antigo ignorado") == 1,
      f"{res5.stdout.count('historico antigo ignorado')} vezes")


print()
print("=" * 74)
print("7. o daemon IGNORA HUP e obedece a TERM")
print("=" * 74)
# Este e o bug que chegou ate a instalacao de verdade: o daemon trapeava HUP
# como pedido de parada. Mas HUP e exatamente o sinal que chega quando o shell
# que o iniciou termina — o `adb shell`, ou o supervisor no boot. Ele subia e
# morria segundos depois, com a tela dizendo que estava tudo bem.
script6 = f"""
pkill -f "{T}/r1scrobbled" 2>/dev/null || true
sleep 1
rm -rf {T}/hup; mkdir -p {T}/hup/scrobble {T}/hup/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/hup/scrobble/r1collect
chmod 755 {T}/hup/scrobble/r1collect
cp {r.to_posix_path(os.path.join(WORK, 'sim4.db'))} {T}/hup/banco.db
sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/hup/scrobble#' \
    -e 's#^DB=.*#DB={T}/hup/banco.db#' \
    -e 's#^MAIS=.*#MAIS={T}/hup/nada.db#' \
    -e 's#^COPIA=.*#COPIA={T}/hup/tmp/c.db#' \
    -e 's#^PARCIAL=.*#PARCIAL={T}/hup/tmp/p.tsv#' \
    -e 's#^LOG=.*#LOG={T}/hup/tmp/log#' \
    -e 's#^TICK=.*#TICK={T}/hup/tmp/tick#' \
    -e 's#^TRAVA=.*#TRAVA={T}/hup/tmp/rodando#' \
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \
    {p} > {T}/hup/rs
chmod 755 {T}/hup/rs

busybox ash {T}/hup/rs &
PID=$!
sleep 3
kill -HUP $PID 2>/dev/null
sleep 3
kill -0 $PID 2>/dev/null && echo "APOS_HUP=vivo" || echo "APOS_HUP=morto"
kill -TERM $PID 2>/dev/null
sleep 3
kill -0 $PID 2>/dev/null && echo "APOS_TERM=vivo" || echo "APOS_TERM=morto"
[ -f {T}/hup/tmp/rodando ] && echo "TRAVA=ficou" || echo "TRAVA=removida"

echo "--- e iniciado como o instalador faz, com o shell saindo em seguida? ---"
rm -f {T}/hup/tmp/rodando
busybox ash -c "setsid busybox ash {T}/hup/rs </dev/null >/dev/null 2>&1 &"
sleep 4
q=$(cat {T}/hup/tmp/rodando 2>/dev/null)
if [ -n "$q" ] && kill -0 $q 2>/dev/null; then
    echo "DESTACADO=vivo"
    kill -TERM $q 2>/dev/null
else
    echo "DESTACADO=morto"
fi
"""
res6 = r.posix_script(script6, name="daemon-hup", mutating=False, quiet=True,
                      timeout=180)
print("\n".join("   " + l for l in res6.stdout.splitlines()[:12]))
check("sobrevive a um SIGHUP", "APOS_HUP=vivo" in res6.stdout,
      "morreu com HUP" if "APOS_HUP=morto" in res6.stdout else "")
check("mas ainda obedece a SIGTERM", "APOS_TERM=morto" in res6.stdout)
check("e limpa a trava ao sair", "TRAVA=removida" in res6.stdout)
check("continua vivo quando o shell que o iniciou termina",
      "DESTACADO=vivo" in res6.stdout,
      "morreu junto com o shell" if "DESTACADO=morto" in res6.stdout else "")


print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
