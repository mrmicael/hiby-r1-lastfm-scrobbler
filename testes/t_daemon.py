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
import re as _re


def medir_custo():
    """Roda o daemon parado e devolve (ms por ciclo, RSS em kB, saida)."""
    res = r.posix_script(script4, name="daemon-cost", mutating=False,
                         quiet=True, timeout=180)
    st = _re.search(r"STAT (\d+) (\d+) (\d+) (\d+)", res.stdout)
    hz_ = _re.search(r"HZ (\d+)", res.stdout)
    rss_ = _re.search(r"RSS_KB (\d+)", res.stdout)
    if not (st and hz_):
        return None, rss_, res
    ticks_ = sum(int(st.group(i)) for i in (1, 2, 3, 4))
    return (ticks_ / int(hz_.group(1))) / CICLOS * 1000, rss_, res


# Duas medidas, e vale a MENOR.
#
# O que se quer medir e o custo de uma volta do laco, e uma maquina ocupada
# so sabe empurrar esse numero para cima: a contencao acrescenta tempo, nunca
# tira. Entao o minimo de duas amostras esta mais perto da verdade do que a
# media, e nao acusa falso quando a suite inteira roda em paralelo — foi
# assim que esta medida deu 6,00 ms numa rodada e 1,17 ms sozinha, dois
# minutos depois, sem uma linha de codigo ter mudado.
por_ciclo_ms, mrss, res4 = medir_custo()
print("\n".join("   " + l for l in res4.stdout.splitlines()[:6]))
if por_ciclo_ms is not None and por_ciclo_ms >= 4.0:
    print(f"   ({por_ciclo_ms:.2f} ms na primeira medida — a maquina pode "
          f"estar ocupada; medindo de novo)")
    segunda, mrss2, res4b = medir_custo()
    if segunda is not None:
        por_ciclo_ms = min(por_ciclo_ms, segunda)
        mrss = mrss2 or mrss
        print(f"   (segunda medida: {segunda:.2f} ms; vale a menor)")
if por_ciclo_ms is not None:
    seg = por_ciclo_ms * CICLOS / 1000
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
    # com 17,8 ms. Quatro milissegundos pegam isso com folga.
    #
    # Numa maquina ocupada a medida sobe: com a suite inteira rodando junto
    # ela deu 6,00 ms, e 1,17 ms sozinha dois minutos depois. Por isso a
    # medicao e repetida e vale a menor — contencao so acrescenta tempo.
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
print("8. pausar no meio da faixa nao a fecha, e o tempo contado e o do audio")
print("=" * 74)
# Dois relatos, uma causa so.
#
#   vi:        faixas subindo no instante em que comecavam, aparecendo como
#              scrobble e como "scrobbling now" ao mesmo tempo.
#   endgame4:  "musicas que eu sei que toquei nao aparecem; outras aparecem".
#
# O tempo ouvido vinha do ESPACO entre carimbos, e espaco nao e musica. Quem
# pausa perde a faixa (o f1 fechava ali, com meia escuta, abaixo do minimo);
# quem liga o aparelho com musica tocando ganha uma faixa que nao ouviu.
#
# Medido no R1 de verdade, com a pausa apertada na mao:
#
#     50s  pcm=1  rowid=261  arq=.../After Dark.flac    tocando
#     50s  pcm=0  rowid=261  arq=.../After Dark.flac    PAUSADO
#     29s  pcm=1  rowid=261  arq=.../After Dark.flac    voltou
#
# O pcm fecha, o ARQUIVO nao — e o rowid nao muda, porque retomar nao escreve
# linha nenhuma no histórico. E so isso que distingue pausa de fim.
#
# Aqui o r1collect e trocado por um recado: `estado` responde o que estiver
# escrito no arquivo de controle, e o resto passa direto para o de verdade.
FALSO = r"""#!/bin/sh
case "$1" in
estado)  cat CTRL 2>/dev/null || { echo "pcm=0"; echo ""; } ;;
tocando) sed -n 2p CTRL 2>/dev/null ;;
*)       exec REAL "$@" ;;
esac
"""
script7 = f"""
pkill -f "{T}/r1scrobbled" 2>/dev/null || true
sleep 1
rm -rf {T}/pausa; mkdir -p {T}/pausa/scrobble {T}/pausa/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/pausa/scrobble/real
chmod 755 {T}/pausa/scrobble/real
cat > {T}/pausa/scrobble/r1collect <<'FIMFALSO'
{FALSO.replace("CTRL", T + "/pausa/ctrl").replace("REAL", T + "/pausa/scrobble/real")}
FIMFALSO
chmod 755 {T}/pausa/scrobble/r1collect

# O historico ja tem uma linha ANTES de o daemon subir, para a partida virar
# marco zero e nao lote: o que interessa aqui e a faixa que vem depois.
cp {r.to_posix_path(WORK)}/sim1.db {T}/pausa/banco.db
printf 'pcm=0\\n\\n' > {T}/pausa/ctrl

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/pausa/scrobble#' \\
    -e 's#^DB=.*#DB={T}/pausa/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/pausa/nada.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/pausa/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/pausa/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/pausa/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/pausa/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/pausa/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#^QUIETOS=8#QUIETOS=3#' \\
    {p} > {T}/pausa/rs
chmod 755 {T}/pausa/rs

busybox ash {T}/pausa/rs &
PID=$!
# Folga ate o daemon estar bem dentro do laco ocioso. O `-nt` do busybox
# compara segundos inteiros: se a copia do banco cair no mesmo segundo em que
# o daemon carimba a marca, a colheita so aconteceria na proxima escrita — e
# nao ha proxima, entao o teste falharia por corrida e nao por defeito.
sleep 8

# A faixa 2 comeca a tocar: linha nova no banco E audio saindo.
printf 'pcm=1\\n{T}/pausa/faixa.flac\\n' > {T}/pausa/ctrl
cp {r.to_posix_path(WORK)}/sim2.db {T}/pausa/banco.db
sleep 6

# PAUSA: o pcm fecha, o arquivo continua aberto. Nada pode fechar a faixa.
printf 'pcm=0\\n{T}/pausa/faixa.flac\\n' > {T}/pausa/ctrl
sleep 6
if [ -f {T}/pausa/scrobble/fila.tsv ]; then
    N=$(grep -c "^t1" {T}/pausa/scrobble/fila.tsv)
else
    N=0
fi
echo "T1_NA_PAUSA=$N"

# VOLTOU: continua contando de onde parou.
printf 'pcm=1\\n{T}/pausa/faixa.flac\\n' > {T}/pausa/ctrl
sleep 5

# PAROU de verdade: o arquivo fecha junto. Agora sim.
printf 'pcm=0\\n\\n' > {T}/pausa/ctrl
sleep 4

kill -TERM $PID 2>/dev/null
sleep 2
echo "=== FILA ==="
cat {T}/pausa/scrobble/fila.tsv
echo "=== LOG ==="
cat {T}/pausa/tmp/log 2>/dev/null || true
"""
res7 = r.posix_script(script7, name="daemon-pausa", mutating=False, quiet=True,
                      timeout=180)
print("\n".join("   " + l for l in res7.stdout.splitlines()[:40]))

check("a faixa foi colhida (sem isto o resto nao quer dizer nada)",
      "1 nova(s), rowid ate 2" in res7.stdout,
      "a colheita nao aconteceu")
na_pausa = next((l.split("=", 1)[1].strip()
                 for l in res7.stdout.splitlines()
                 if l.strip().startswith("T1_NA_PAUSA=")), "?")
check("durante a pausa a faixa NAO foi fechada", na_pausa == "0",
      f"{na_pausa} marcador(es) t1 durante a pausa")

fila7 = res7.stdout.split("=== FILA ===")[1].split("=== LOG ===")[0] \
    if "=== FILA ===" in res7.stdout else ""
t1s = [l.split("\t") for l in fila7.splitlines() if l.startswith("t1")]
check("a faixa foi medida", bool(t1s), f"{len(t1s)} t1: {[x[1:] for x in t1s]}")
if t1s:
    # A medida sai em parcelas para um travamento nao levar tudo, e as
    # parcelas do mesmo rowid SOMAM — e assim que o PC as le.
    check("todas as parcelas sao da mesma faixa",
          {x[1] for x in t1s} == {"2"}, str({x[1] for x in t1s}))
    medido = sum(int(x[2]) for x in t1s)
    # 6s tocando + 6s pausado + 5s tocando. O audio saiu por ~11s; o relogio
    # de parede marcou ~17. Contar 17 seria contar a pausa como musica.
    check("o tempo medido e o do audio, nao o do relogio",
          5 <= medido <= 14, f"{medido}s medidos (parede: ~17s)")
    # A incerteza nao e um numero fixo: e um intervalo do laco para cada
    # fronteira que caiu entre duas olhadas. Aqui foram tres (a faixa
    # comecando, o audio parando na pausa, o audio voltando) mais o fim, e
    # o laco esta em 1s — entao ela tem de ser maior que uma sondagem so.
    incerteza = max(int(x[3]) for x in t1s if len(x) > 3)
    check("a incerteza vai junto e cresce com as pausas", incerteza >= 3,
          f"{incerteza}s de incerteza para 3 fronteiras + o fim")
check("o log conta que o audio voltou", "audio voltou apos" in res7.stdout,
      " ".join(l for l in res7.stdout.splitlines()
               if "voltou" in l)[:70] or "nao apareceu")


print()
print("=" * 74)
print("9. subir com musica tocando: a faixa em curso NAO e lote atrasado")
print("=" * 74)
# Este e o defeito que a vi viu de frente. O daemon acordava, encontrava no
# banco a linha da faixa que estava tocando NAQUELE instante, chamava aquilo
# de "tocou sem ninguem olhando", dava credito integral e mandava na hora.
# A pessoa via a mesma musica como scrobble e como "scrobbling now" —
# porque ela estava mesmo tocando.
script8 = f"""
pkill -f "{T}/pausa/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/subir; mkdir -p {T}/subir/scrobble {T}/subir/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/subir/scrobble/real
chmod 755 {T}/subir/scrobble/real
cat > {T}/subir/scrobble/r1collect <<'FIMFALSO'
{FALSO.replace("CTRL", T + "/subir/ctrl").replace("REAL", T + "/subir/scrobble/real")}
FIMFALSO
chmod 755 {T}/subir/scrobble/r1collect

# Quatro faixas no banco e o estado parado na primeira: tres atrasadas. Mas a
# ultima delas esta tocando agora — ha audio saindo e arquivo local aberto.
cp {r.to_posix_path(WORK)}/sim4.db {T}/subir/banco.db
printf 'pcm=1\\n{T}/subir/faixa.flac\\n' > {T}/subir/ctrl
mkdir -p {T}/subir/scrobble
echo 1 > {T}/subir/scrobble/estado

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/subir/scrobble#' \\
    -e 's#^DB=.*#DB={T}/subir/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/subir/nada.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/subir/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/subir/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/subir/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/subir/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/subir/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    {p} > {T}/subir/rs
chmod 755 {T}/subir/rs

busybox ash {T}/subir/rs &
PID=$!
sleep 5
kill -TERM $PID 2>/dev/null
sleep 2
echo "=== FILA ==="
cat {T}/subir/scrobble/fila.tsv
echo "=== LOG ==="
cat {T}/subir/tmp/log 2>/dev/null || true
"""
res8 = r.posix_script(script8, name="daemon-subir", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res8.stdout.splitlines()[:30]))

fila8 = res8.stdout.split("=== FILA ===")[1].split("=== LOG ===")[0] \
    if "=== FILA ===" in res8.stdout else ""
a1s = [l.split("\t") for l in fila8.splitlines() if l.startswith("a1")]
check("o lote atrasado deixa a faixa em curso de fora",
      len(a1s) == 1 and a1s[0][2] == "2",
      f"a1 disse {a1s[0][2] if a1s else '?'} (as atrasadas de verdade sao 2 "
      f"das 3 linhas novas)")
check("as tres linhas foram para a fila do mesmo jeito",
      len([l for l in fila8.splitlines() if l.startswith("p1")]) == 3,
      f"{len([l for l in fila8.splitlines() if l.startswith('p1')])} p1")
check("o log diz por que a ultima ficou de fora",
      "faixa tocando agora" in res8.stdout,
      " ".join(l for l in res8.stdout.splitlines()
               if "tocando agora" in l)[:70] or "nao apareceu")
# E ao ser fechada pelo TERM ela leva o tempo MEDIDO, nao a faixa inteira.
t1s8 = [l.split("\t") for l in fila8.splitlines() if l.startswith("t1")]
check("e ela e fechada com o pouco que deu para medir",
      len(t1s8) == 1 and int(t1s8[0][2]) <= 15,
      f"{t1s8[0][2] if t1s8 else '?'}s medidos")


print()
print("=" * 74)
print("10. um travamento nao leva junto a medicao da faixa em curso")
print("=" * 74)
# Este aparelho reinicia sozinho — aconteceu duas vezes enquanto esta versao
# era escrita. Num travamento nenhum trap roda, entao a medida guardada so na
# memoria do daemon morre com ele: a faixa fica sem t1 e a conta volta a
# deduzir do relogio, que e exatamente o que se quer evitar. Aconteceu de
# verdade com a faixa 272 no R1, de 293s, que subiu como ouvida por inteiro
# depois de um reinicio no meio dela.
#
# Por isso a medida sai em parcelas. Aqui o daemon leva um KILL — sem chance
# de despedida, como num travamento — e o que ja foi ouvido tem de estar na
# fila mesmo assim.
script9 = f"""
pkill -f "{T}/subir/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/kill; mkdir -p {T}/kill/scrobble {T}/kill/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/kill/scrobble/real
chmod 755 {T}/kill/scrobble/real
cat > {T}/kill/scrobble/r1collect <<'FIMFALSO'
{FALSO.replace("CTRL", T + "/kill/ctrl").replace("REAL", T + "/kill/scrobble/real")}
FIMFALSO
chmod 755 {T}/kill/scrobble/r1collect

cp {r.to_posix_path(WORK)}/sim1.db {T}/kill/banco.db
printf 'pcm=0\\n\\n' > {T}/kill/ctrl

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/kill/scrobble#' \\
    -e 's#^DB=.*#DB={T}/kill/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/kill/nada.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/kill/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/kill/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/kill/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/kill/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/kill/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#^QUIETOS=8#QUIETOS=3#' -e 's#^T1_PASSO=30#T1_PASSO=3#' \\
    {p} > {T}/kill/rs
chmod 755 {T}/kill/rs

busybox ash {T}/kill/rs &
PID=$!
sleep 8
printf 'pcm=1\\n{T}/kill/faixa.flac\\n' > {T}/kill/ctrl
cp {r.to_posix_path(WORK)}/sim2.db {T}/kill/banco.db
sleep 12

# KILL, nao TERM: nada roda na saida, como num travamento de verdade.
kill -KILL $PID 2>/dev/null
sleep 1
echo "=== FILA APOS O KILL ==="
cat {T}/kill/scrobble/fila.tsv
echo "=== PONTO DE CONTROLE ==="
cat {T}/kill/scrobble/medindo 2>/dev/null || echo "(nao existe)"

# A partida seguinte tem de transformar isso numa faixa fechada.
printf 'pcm=0\\n\\n' > {T}/kill/ctrl
busybox ash {T}/kill/rs &
PID2=$!
sleep 5
kill -TERM $PID2 2>/dev/null
sleep 2
echo "=== FILA APOS REINICIAR ==="
cat {T}/kill/scrobble/fila.tsv
echo "=== PONTO DE CONTROLE DEPOIS ==="
cat {T}/kill/scrobble/medindo 2>/dev/null || echo "(apagado)"
echo "=== LOG ==="
cat {T}/kill/tmp/log 2>/dev/null || true
"""
res9 = r.posix_script(script9, name="daemon-kill", mutating=False, quiet=True,
                      timeout=120)
print("\n".join("   " + l for l in res9.stdout.splitlines()[:25]))

def entre(marca, fim="==="):
    if marca not in res9.stdout:
        return ""
    return res9.stdout.split(marca)[1].split(fim)[0]


check("a faixa foi colhida", "1 nova(s), rowid ate 2" in res9.stdout,
      "a colheita nao aconteceu")
check("o daemon morreu sem se despedir",
      "faixa 2 fechada" not in entre("=== FILA APOS O KILL ==="),
      "fechou direitinho — o KILL nao pegou")

apos_kill = entre("=== FILA APOS O KILL ===")
check("a fila nao ganhou linha nenhuma de medicao no meio da faixa",
      not [l for l in apos_kill.splitlines() if l.startswith("t1")],
      "a fila cresceria dez vezes mais rapido, e ela nunca e podada")

ponto = entre("=== PONTO DE CONTROLE ===").strip()
check("mas a medicao estava salva em disco", ponto.startswith("2 "),
      ponto or "(vazio)")
if ponto.startswith("2 "):
    check("e ela vale o que de fato tocou",
          6 <= int(ponto.split()[1]) <= 12,
          f"{ponto.split()[1]}s de ~11s tocados")

apos_reinicio = entre("=== FILA APOS REINICIAR ===")
t1s9 = [l.split("\t") for l in apos_reinicio.splitlines()
        if l.startswith("t1")]
check("a partida seguinte transformou isso em faixa fechada",
      len(t1s9) == 1 and t1s9[0][1] == "2" and t1s9[0][-1] == "fim",
      str([x[1:] for x in t1s9]))
if t1s9:
    check("com o mesmo tempo que estava salvo",
          t1s9[0][2] == ponto.split()[1] if ponto.split() else False,
          f"fila={t1s9[0][2]}s ponto={ponto}")
check("e o ponto de controle foi apagado",
      "(apagado)" in res9.stdout,
      entre("=== PONTO DE CONTROLE DEPOIS ===").strip())
check("o log conta a recuperacao",
      "medicao interrompida recuperada" in res9.stdout,
      " ".join(l for l in res9.stdout.splitlines()
               if "recuperada" in l)[:70] or "nao apareceu")


print()
print("=" * 74)
print("11. reiniciar no meio de uma faixa nao larga o resto dela sem medir")
print("=" * 74)
# Retomar nao escreve linha no historico, entao um daemon que sobe com musica
# tocando e o banco ja todo anotado nao ve nada a fazer — e o resto da faixa
# fica sem ninguem contando.
#
# Visto no R1: a faixa 282 tocou 39s, ficou 14 minutos pausada, voltou e tocou
# mais 82, e foi registrada com os 34s que o daemon ANTERIOR tinha medido. Num
# aparelho que trava sozinho — este trava — isso nao e caso raro, e o relato
# do "algumas musicas nao aparecem" mora exatamente aqui.
script10 = f"""
pkill -f "{T}/kill/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/retomar; mkdir -p {T}/retomar/scrobble {T}/retomar/tmp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/retomar/scrobble/real
chmod 755 {T}/retomar/scrobble/real
cat > {T}/retomar/scrobble/r1collect <<'FIMFALSO'
{FALSO.replace("CTRL", T + "/retomar/ctrl")
      .replace("REAL", T + "/retomar/scrobble/real")}
FIMFALSO
chmod 755 {T}/retomar/scrobble/r1collect

# O banco JA esta todo anotado — nada atrasado — e ha musica tocando.
cp {r.to_posix_path(WORK)}/sim2.db {T}/retomar/banco.db
echo 2 > {T}/retomar/scrobble/estado
printf 'pcm=1\\n{T}/retomar/faixa.flac\\n' > {T}/retomar/ctrl

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/retomar/scrobble#' \\
    -e 's#^DB=.*#DB={T}/retomar/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/retomar/nada.db#' \\
    -e 's#^COPIA=.*#COPIA={T}/retomar/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/retomar/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/retomar/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/retomar/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/retomar/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    {p} > {T}/retomar/rs
chmod 755 {T}/retomar/rs

busybox ash {T}/retomar/rs &
PID=$!
sleep 10
kill -TERM $PID 2>/dev/null
sleep 2
echo "=== FILA ==="
cat {T}/retomar/scrobble/fila.tsv
echo "=== LOG ==="
cat {T}/retomar/tmp/log 2>/dev/null || true
"""
res10 = r.posix_script(script10, name="daemon-retomar", mutating=False,
                       quiet=True, timeout=120)
print("\n".join("   " + l for l in res10.stdout.splitlines()[:20]))

fila10 = res10.stdout.split("=== FILA ===")[1].split("=== LOG ===")[0] \
    if "=== FILA ===" in res10.stdout else ""
check("o daemon adotou a faixa que ja estava tocando",
      "ja estava tocando na partida" in res10.stdout,
      " ".join(l for l in res10.stdout.splitlines()
               if "ja estava tocando" in l)[:70] or "nao adotou")
t1s10 = [l.split("\t") for l in fila10.splitlines() if l.startswith("t1")]
check("e mediu o resto dela", len(t1s10) == 1 and t1s10[0][1] == "2",
      str([x[1:] for x in t1s10]))
if t1s10:
    check("com o tempo que tocou depois da partida",
          5 <= int(t1s10[0][2]) <= 14, f"{t1s10[0][2]}s de ~10s")
check("e NAO inventou lote atrasado nenhum",
      not [l for l in fila10.splitlines() if l.startswith("a1")],
      "apareceu a1 — a faixa viraria passado com credito integral")
check("nem repetiu a linha da faixa",
      not [l for l in fila10.splitlines() if l.startswith("p1")],
      "repetiu o p1 de uma faixa que ja estava na fila")


print()
print("=" * 74)
print("13. o banco do player pode estar no cartao, e o daemon tem de achar")
print("=" * 74)
# Relatado: "instalei a versao 11, o programa diz que esta rodando, toquei
# musica e zero faixas foram colhidas". A causa: o player tem uma opcao,
# `tf_music_db_enable`, que move o banco dele para o cartao — e a partir dai
# o banco da memoria interna nunca mais e atualizado.
#
# Os dois caminhos estao escritos dentro do /usr/bin/hiby_player:
#     /data/usrlocal_media.db                   opcao desligada
#     /data/mnt/sd_0/.temp/usrlocal_media.db    opcao ligada
# O daemon apontava fixo para o primeiro.
script11 = f"""
pkill -f "{T}/retomar/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/nocartao
mkdir -p {T}/nocartao/scrobble {T}/nocartao/tmp {T}/nocartao/sd/.temp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/nocartao/scrobble/r1collect
chmod 755 {T}/nocartao/scrobble/r1collect

# So o banco DO CARTAO existe; o interno nem aparece.
cp {r.to_posix_path(WORK)}/sim2.db {T}/nocartao/sd/.temp/usrlocal_media.db

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/nocartao/scrobble#' \\
    -e 's#^DB_INTERNO=.*#DB_INTERNO={T}/nocartao/naoexiste.db#' \\
    -e 's#^DB=/usr/data.*#DB={T}/nocartao/naoexiste.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/nocartao/nada.db#' \\
    -e 's#^CARTOES=.*#CARTOES="{T}/nocartao/sd"#' \\
    -e 's#^COPIA=.*#COPIA={T}/nocartao/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/nocartao/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/nocartao/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/nocartao/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/nocartao/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    {p} > {T}/nocartao/rs
chmod 755 {T}/nocartao/rs

busybox ash {T}/nocartao/rs &
PID=$!
sleep 8
# Uma faixa nova entra NO BANCO DO CARTAO.
cp {r.to_posix_path(WORK)}/sim3.db {T}/nocartao/sd/.temp/usrlocal_media.db
sleep 6
kill -TERM $PID 2>/dev/null
sleep 2
echo "=== BANCO ESCOLHIDO ==="
cat {T}/nocartao/scrobble/banco 2>/dev/null || echo "(nenhum)"
echo "=== FILA ==="
cat {T}/nocartao/scrobble/fila.tsv
echo "=== LOG ==="
cat {T}/nocartao/tmp/log 2>/dev/null || true
"""
res11 = r.posix_script(script11, name="daemon-banco-sd", mutating=False,
                       quiet=True, timeout=120)
print("\n".join("   " + l for l in res11.stdout.splitlines()[:22]))

escolhido = ""
if "=== BANCO ESCOLHIDO ===" in res11.stdout:
    escolhido = res11.stdout.split("=== BANCO ESCOLHIDO ===")[1] \
                            .split("===")[0].strip()
check("achou o banco no cartao", escolhido.endswith("usrlocal_media.db")
      and "/sd/" in escolhido, escolhido or "(nenhum)")
fila11 = res11.stdout.split("=== FILA ===")[1].split("=== LOG ===")[0] \
    if "=== FILA ===" in res11.stdout else ""
check("e colheu a faixa que entrou nele",
      len([l for l in fila11.splitlines() if l.startswith("p1")]) == 1,
      f"{len([l for l in fila11.splitlines() if l.startswith('p1')])} p1 "
      f"(zero e o defeito relatado)")

# A hora em que a faixa comecou sai da mtime do banco — o instante em que o
# player gravou a linha —, e nao de "quando o daemon percebeu". Sem isso,
# some do comeco de cada faixa ate um intervalo do laco inteiro.
#
# O daemon diz no registro de qual dos dois caminhos veio a hora, porque a
# incerteza sozinha nao serve de prova: as trocas de estado somam a ela, e um
# fallback silencioso ficaria indistinguivel.
check("e a hora de inicio veio da mtime do banco, nao do relogio do daemon",
      "inicio pela mtime do banco" in res11.stdout,
      " ".join(l for l in res11.stdout.splitlines()
               if "inicio pel" in l or "mtime do banco" in l)[:90]
      or "nao apareceu")

print()
print("=" * 74)
print("14. trocar de banco recomeca o marcador, sem despejar o historico")
print("=" * 74)
# Os dois bancos tem numeracao propria. Seguir a numeracao do antigo no novo
# faria o daemon pular tudo ou — pior — reler o historico inteiro e mandar
# dezenas de faixas antigas de uma vez. Aqui o banco muda de lugar com o
# daemon rodando, e o marcador tem de ir para o TOPO do novo.
script12 = f"""
pkill -f "{T}/nocartao/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/troca; mkdir -p {T}/troca/scrobble {T}/troca/tmp {T}/troca/sd/.temp
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/troca/scrobble/real
chmod 755 {T}/troca/scrobble/real
# O r1collect de mentira e o que permite dizer qual banco o "player" tem
# aberto — a terceira linha do `estado`. Com o de verdade, aqui, nao ha player
# nenhum para achar, e o teste nao exercitaria o sinal que decide.
cat > {T}/troca/scrobble/r1collect <<'FIMFALSO'
{FALSO.replace("CTRL", T + "/troca/ctrl")
      .replace("REAL", T + "/troca/scrobble/real")}
FIMFALSO
chmod 755 {T}/troca/scrobble/r1collect

# Comeca no banco interno, com uma faixa. A terceira linha do `estado` e o
# banco que o PLAYER tem aberto — e e ela que manda, nao a hora de
# modificacao: sem o player para responder, o daemon mantem o que ja seguia.
cp {r.to_posix_path(WORK)}/sim1.db {T}/troca/interno.db
printf 'pcm=0\\n\\n{T}/troca/interno.db\\n' > {T}/troca/ctrl

sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/troca/scrobble#' \\
    -e 's#^DB_INTERNO=.*#DB_INTERNO={T}/troca/interno.db#' \\
    -e 's#^DB=/usr/data.*#DB={T}/troca/interno.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/troca/nada.db#' \\
    -e 's#^CARTOES=.*#CARTOES="{T}/troca/sd"#' \\
    -e 's#^COPIA=.*#COPIA={T}/troca/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/troca/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/troca/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/troca/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/troca/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    -e 's#recheca_sd=1800#recheca_sd=3#g' \\
    {p} > {T}/troca/rs
chmod 755 {T}/troca/rs

busybox ash {T}/troca/rs &
PID=$!
sleep 8
# A opcao e ligada na tela do aparelho: o player passa a escrever no cartao,
# e o banco de la ja vem com QUATRO faixas, que sao historico antigo. Quem
# anuncia a troca e o proprio player, pelo arquivo que passou a manter aberto.
cp {r.to_posix_path(WORK)}/sim4.db {T}/troca/sd/.temp/usrlocal_media.db
printf 'pcm=0\\n\\n{T}/troca/sd/.temp/usrlocal_media.db\\n' > {T}/troca/ctrl
sleep 12
kill -TERM $PID 2>/dev/null
sleep 2
echo "=== BANCO ESCOLHIDO ==="
cat {T}/troca/scrobble/banco 2>/dev/null || echo "(nenhum)"
echo "=== MARCADOR ==="
cat {T}/troca/scrobble/estado 2>/dev/null || echo "(nenhum)"
echo "=== FILA ==="
cat {T}/troca/scrobble/fila.tsv
echo "=== LOG ==="
cat {T}/troca/tmp/log 2>/dev/null || true
"""
res12 = r.posix_script(script12, name="daemon-troca-banco", mutating=False,
                       quiet=True, timeout=120)
print("\n".join("   " + l for l in res12.stdout.splitlines()[:22]))


def bloco(saida, marca):
    if marca not in saida:
        return ""
    return saida.split(marca)[1].split("===")[0].strip()


check("passou a seguir o banco do cartao",
      "/sd/" in bloco(res12.stdout, "=== BANCO ESCOLHIDO ==="),
      bloco(res12.stdout, "=== BANCO ESCOLHIDO ===") or "(nenhum)")
check("o marcador foi para o TOPO do banco novo",
      bloco(res12.stdout, "=== MARCADOR ===") == "4",
      f"marcador={bloco(res12.stdout, '=== MARCADOR ===')}, "
      f"esperado 4 (as 4 do banco novo sao historico, nao execucao)")
fila12 = bloco(res12.stdout, "=== FILA ===")
check("e o historico do banco novo NAO foi despejado na fila",
      not [l for l in fila12.splitlines() if l.startswith("p1")],
      f"{len([l for l in fila12.splitlines() if l.startswith('p1')])} p1 — "
      f"cada um seria um scrobble falso")
check("o log explica a troca",
      "A numeracao e outra" in res12.stdout,
      " ".join(l for l in res12.stdout.splitlines()
               if "numeracao" in l)[:80] or "nao apareceu")

print()
print("=" * 74)
print("15. ponto de montagem vazio NAO e um cartao de memoria")
print("=" * 74)
# Achado investigando os travamentos: o cartao do R1 tinha caido do
# barramento, e mesmo assim o daemon anunciava
#
#     registro e planilha no cartao: /usr/data/mnt/sd_0/r1lastfm
#
# porque o ponto de montagem continua existindo com o slot vazio — e um
# diretorio comum na memoria interna, e passa na prova de escrita como
# qualquer outro. O estrago nao e so a mensagem errada: quando o cartao
# volta e monta por cima, os arquivos gravados ali ficam invisiveis, e para
# quem usa a planilha simplesmente sumiu.
script13 = f"""
pkill -f "{T}/troca/rs" 2>/dev/null || true
sleep 1
rm -rf {T}/semsd; mkdir -p {T}/semsd/scrobble {T}/semsd/tmp {T}/semsd/pontovazio
cp {r.to_posix_path(os.path.join(WORK, 'r1collect'))} {T}/semsd/scrobble/r1collect
chmod 755 {T}/semsd/scrobble/r1collect
cp {r.to_posix_path(WORK)}/sim1.db {T}/semsd/banco.db

# O "cartao" e um diretorio gravavel que NAO e ponto de montagem nenhum —
# exatamente o que sobra no R1 quando o cartao cai do barramento.
sed -e 's#^DIR=/usr/data/scrobble#DIR={T}/semsd/scrobble#' \\
    -e 's#^DB_INTERNO=.*#DB_INTERNO={T}/semsd/banco.db#' \\
    -e 's#^DB=/usr/data.*#DB={T}/semsd/banco.db#' \\
    -e 's#^MAIS=.*#MAIS={T}/semsd/nada.db#' \\
    -e 's#^CARTOES=.*#CARTOES="{T}/semsd/pontovazio"#' \\
    -e 's#^COPIA=.*#COPIA={T}/semsd/tmp/c.db#' \\
    -e 's#^PARCIAL=.*#PARCIAL={T}/semsd/tmp/p.tsv#' \\
    -e 's#^LOG=.*#LOG={T}/semsd/tmp/log#' \\
    -e 's#^TICK=.*#TICK={T}/semsd/tmp/tick#' \\
    -e 's#^TRAVA=.*#TRAVA={T}/semsd/tmp/rodando#' \\
    -e 's#^RAPIDO=15#RAPIDO=1#' -e 's#^LENTO=60#LENTO=1#' \\
    {p} > {T}/semsd/rs
chmod 755 {T}/semsd/rs

busybox ash {T}/semsd/rs &
PID=$!
sleep 6
kill -TERM $PID 2>/dev/null
sleep 2
echo "=== LOG ==="
cat {T}/semsd/tmp/log 2>/dev/null || true
echo "=== SUJOU O PONTO DE MONTAGEM? ==="
# Contando, e nao listando: `ls -A` numa pasta vazia nao imprime nada E sai
# com sucesso, entao um `|| echo vazio` nunca dispara e a leitura fica ambigua.
echo "ENTRADAS=$(ls -A {T}/semsd/pontovazio/ 2>/dev/null | wc -l)"
"""
res13 = r.posix_script(script13, name="daemon-sem-sd", mutating=False,
                       quiet=True, timeout=120)
print("\n".join("   " + l for l in res13.stdout.splitlines()[:16]))

check("nao inventa um cartao onde nao ha nada montado",
      "sem cartao gravavel" in res13.stdout,
      " ".join(l for l in res13.stdout.splitlines()
               if "cartao" in l)[:90] or "nao disse nada sobre cartao")
check("e nao anuncia planilha no cartao",
      "planilha no cartao" not in res13.stdout,
      "anunciou uma planilha que ficaria escondida quando o cartao voltasse")
entradas = next((l.split("=", 1)[1].strip()
                 for l in res13.stdout.splitlines()
                 if l.strip().startswith("ENTRADAS=")), "?")
check("nem deixa pasta nossa no ponto de montagem vazio",
      entradas == "0", f"{entradas} entrada(s) criadas onde nao ha cartao")

print()
print("=" * 74)
print("12. o awk que enxuga a fila e RODADO, nao so lido")
print("=" * 74)
# `limpar_fila` monta um awk e manda como TEXTO para o shell do aparelho.
# Um erro nele nao levanta excecao nenhuma no PC: a fila simplesmente sai
# errada, e so quem abrisse o arquivo no aparelho perceberia. Entao o awk e
# extraido do comando e executado de verdade, no busybox, que e o mesmo awk
# que vai roda-lo la.
import re as _re                                          # noqa: E402
from r1lastfm import aparelho as AP                       # noqa: E402


class _AdbFalso:
    def __init__(self):
        self.comandos = []

    def shell(self, cmd, **kw):
        self.comandos.append(cmd)
        return type("R", (), {"stdout": "", "stderr": "", "ok": True})()


_adbq = _AdbFalso()
AP.limpar_fila(_adbq, Log(os.path.join(WORK, "t_daemon.log")), {2, 3})
_cmd = next((c for c in _adbq.comandos if "awk" in c), "")
check("a limpeza monta um comando com awk", bool(_cmd), _cmd[:60])

_trecho = _re.search(r"awk -F.*?fila\.tsv\.bak", _cmd)
if _trecho:
    _fila_falsa = "\n".join([
        "b1\t1000",
        "p1\t1\t1010\tA\tFica\tAlb\t\t200\t2020\ta:x.flac\t",
        "t1\t1\t190\t15\tfim",
        "p1\t2\t1210\tB\tSai\tAlb\t\t200\t2020\ta:y.flac\t",
        "t1\t2\t195\t15\tfim",
        "p1\t3\t1410\tC\tSai2\tAlb\t\t200\t2020\ta:z.flac\t",
        "t1\t3\t198\t15\tfim",
        "f1\t1610",
        "",
    ])
    _ent = os.path.join(WORK, "limpafila.tsv")
    with open(_ent, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_fila_falsa)
    # O awk vai para um arquivo antes de rodar: passado na linha de comando,
    # o wsl.exe substitui o $1 e o $2 do programa antes de o shell ver, e o
    # awk recebe um programa sem campo nenhum — que e justamente o modo de
    # este teste passar sem testar nada.
    _prog = _trecho.group(0).replace("fila.tsv.bak", r.to_posix_path(_ent))
    _sh_local = os.path.join(WORK, "limpafila.sh")
    with open(_sh_local, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#!/bin/sh\nbusybox " + _prog + "\n")
    _res = r.posix(f"sh {r.to_posix_path(_sh_local)}", mutating=False,
                   quiet=True)
    _linhas = [l for l in _res.stdout.splitlines() if "\t" in l]
    _tipos = [(l.split("\t")[0], l.split("\t")[1]) for l in _linhas]
    check("as faixas ja enviadas sairam",
          ("p1", "2") not in _tipos and ("p1", "3") not in _tipos, str(_tipos))
    check("e as MEDICOES delas sairam junto",
          ("t1", "2") not in _tipos and ("t1", "3") not in _tipos,
          "sem isto a fila cresceria na propria limpeza: " + str(_tipos))
    check("a faixa nao enviada ficou, com a medicao dela",
          ("p1", "1") in _tipos and ("t1", "1") in _tipos, str(_tipos))
    check("e os marcadores de sessao ficaram",
          ("b1", "1000") in _tipos and ("f1", "1610") in _tipos, str(_tipos))
else:
    check("achei o awk dentro do comando", False, _cmd[:80])


print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
