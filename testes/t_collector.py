# -*- coding: utf-8 -*-
"""O leitor de SQLite em C tem de concordar com o SQLite de verdade.

Nao basta funcionar no banco do aparelho: os casos que derrubam leitores
caseiros sao paginas de overflow (textos maiores que uma pagina) e arvores
com paginas interiores (tabelas grandes). Aqui os dois sao construidos de
proposito e comparados registro a registro.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os, random, sqlite3, subprocess, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from comum import compilar_para_o_pc
from r1lastfm.applog import Log
from r1lastfm.runner import Runner

SCRATCH = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SCRATCH, "lastfm")
os.makedirs(WORK, exist_ok=True)
r = Runner(log=Log(os.path.join(WORK, "t_collector.log")), wsl_distro="Ubuntu")
# Os dois programas do aparelho sao C portatil: compilados para este
# PC, respondem exatamente o mesmo que no MIPS do R1.
compilar_para_o_pc(r, "r1collect")
EXE = r.to_posix_path(os.path.join(WORK, "r1collect"))
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


def rodar(db_win, estado_win, fila_win):
    """Emula o que o daemon faz: le o estado, chama o coletor, junta a fila."""
    for p in (estado_win, fila_win):
        if os.path.exists(p):
            os.remove(p)
    with open(estado_win, "w") as fh:
        fh.write("0\n")
    return colher(db_win, estado_win, fila_win)


def colher(db_win, estado_win, fila_win):
    desde = "0"
    if os.path.exists(estado_win):
        desde = (open(estado_win).read().strip() or "0")
    parcial = os.path.join(WORK, "parcial.tsv")
    res = r.posix(f"{EXE} {r.to_posix_path(db_win)} {desde} "
                  f"{r.to_posix_path(parcial)} 2>&1", mutating=False, quiet=True)
    linhas = []
    if res.ok:
        campos = res.stdout.strip().split()
        novas, maior = (campos + ["0", desde])[:2]
        if os.path.exists(parcial):
            with open(parcial, "rb") as fh:
                dados = fh.read()
            if int(novas) > 0:
                with open(fila_win, "ab") as fh:
                    fh.write(dados)
        with open(estado_win, "w") as fh:
            fh.write(str(maior) + "\n")
    if os.path.exists(fila_win):
        with open(fila_win, "rb") as fh:
            for ln in fh.read().decode("utf-8", "replace").splitlines():
                if ln:
                    linhas.append(ln.split("\t"))
    return res, linhas


def desescapa(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            if c == "\\": out.append("\\"); i += 2; continue
            if c == "t":  out.append("\t"); i += 2; continue
            if c == "n":  out.append("\n"); i += 2; continue
            if c == "r":  out.append("\r"); i += 2; continue
            if c == "x":  out.append(chr(int(s[i+2:i+4], 16))); i += 4; continue
        out.append(s[i]); i += 1
    return "".join(out)


ESQUEMA = """CREATE TABLE HISTORY_TABLE (id INTEGER, path TEXT, name TEXT,
 album TEXT, artist TEXT, genre TEXT, year INTEGER, dis_id INTEGER,
 ck_id INTEGER, has_child_file INTEGER, begin_time INTEGER, end_time INTEGER,
 cue_id INTEGER, character TEXT, size INTEGER, sample_rate INTEGER,
 bit_rate INTEGER, bit INTEGER, channel INTEGER, format INTEGER,
 quality INTEGER, album_pic_path TEXT, lrc_path TEXT, track_gain REAL,
 track_peak REAL, ctime INTEGER, mtime INTEGER, pinyin_charater TEXT,
 album_artist TEXT)"""

COLS = ["id", "path", "name", "album", "artist", "genre", "year", "dis_id",
        "ck_id", "has_child_file", "begin_time", "end_time", "cue_id",
        "character", "size", "sample_rate", "bit_rate", "bit", "channel",
        "format", "quality", "album_pic_path", "lrc_path", "track_gain",
        "track_peak", "ctime", "mtime", "pinyin_charater", "album_artist"]


def cria(path, linhas, page_size=1024):
    if os.path.exists(path):
        os.chmod(path, 0o666)   # o teste 8 deixa um 444 para tras
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute(f"PRAGMA page_size={page_size}")
    con.execute("VACUUM")
    con.execute(ESQUEMA)
    con.executemany(
        f"INSERT INTO HISTORY_TABLE ({','.join(COLS)}) "
        f"VALUES ({','.join('?' * len(COLS))})", linhas)
    con.commit()
    con.close()


def linha(path, name, album, artist, size, bitrate, year=2020, aa=None):
    d = dict.fromkeys(COLS, None)
    d.update(id=0, path=path + "\0", name=name + "\0", album=album + "\0",
             artist=artist + "\0", genre="Unknown\0", year=year, size=size,
             bit_rate=bitrate, sample_rate=44100, album_artist=aa,
             track_gain=0.0, track_peak=0.0)
    return tuple(d[c] for c in COLS)


print("=" * 74)
print("1. campo a campo contra o proprio sqlite3")
print("=" * 74)
# Se voce tiver um usrlocal_media.db tirado de um R1, aponte-o em R1_DB_REAL e
# o teste roda contra ele. Sem isso, um banco com o mesmo esquema e montado
# aqui — o que importa e que o leitor em C e o sqlite3 leiam o mesmo.
REAL = _os.environ.get("R1_DB_REAL", "")
if not (REAL and os.path.isfile(REAL)):
    REAL = os.path.join(WORK, "sintetico.db")
    cria(REAL, [
        linha("a:\\Musicas\\a.flac", "Faroeste Caboclo", "Que Pais E Este",
              "Legiao Urbana", 62_000_000, 950_000, 1987),
        linha("a:\\Musicas\\b.mp3", "Track Two", "Album Dois", "Artista Dois",
              7_800_000, 320_000, 2001),
        linha("a:\\Musicas\\c.mp3", "cao unicode \u2605", "\u00c1lbum",
              "Art\u00edsta", 4_000_000, 192_000, 2015),
        linha("a:\\Musicas\\d.wav", "Sem Album", "", "So Artista",
              30_000_000, 1_411_000, 0),
    ])
    print(f"   (banco sintetico: {REAL})")
else:
    print(f"   (banco real: {REAL})")
est = os.path.join(WORK, "e1.txt"); fila = os.path.join(WORK, "f1.tsv")
res, linhas = rodar(REAL, est, fila)
con = sqlite3.connect(f"file:{REAL}?mode=ro", uri=True)
esperado = list(con.execute(
    "SELECT rowid, artist, name, album, album_artist, size, bit_rate, year "
    "FROM HISTORY_TABLE ORDER BY rowid"))
con.close()
check("mesma quantidade de linhas", len(linhas) == len(esperado),
      f"C={len(linhas)} sqlite={len(esperado)}")
for got, exp in zip(linhas, esperado):
    rid, art, nome, alb, aa, tam, taxa, ano = exp
    lim = lambda s: (s or "").rstrip("\x00")
    ok = (int(got[1]) == rid and desescapa(got[3]) == lim(art)
          and desescapa(got[4]) == lim(nome) and desescapa(got[5]) == lim(alb)
          and desescapa(got[6]) == lim(aa) and int(got[8]) == (ano or 0))
    dur_esp = (tam * 8) // taxa if tam and taxa else 0
    ok = ok and int(got[7]) == dur_esp
    check(f"rowid {rid}: {lim(art)[:20]} - {lim(nome)[:24]}", ok)
check("estado ficou no maior rowid",
      open(est).read().strip() == str(esperado[-1][0]))

print()
print("=" * 74)
print("2. rodar de novo nao repete nada")
print("=" * 74)
res2, l2 = colher(REAL, est, fila)
check("zero linhas novas", res2.stdout.strip().split()[0] == "0",
      res2.stdout.strip()[:40])

print()
print("=" * 74)
print("3. estado no meio -> so o que veio depois")
print("=" * 74)
# O corte sai do proprio banco, para o teste valer tanto num sintetico de 4
# linhas quanto num dump real de centenas.
corte = esperado[len(esperado) // 2][0] - 1
with open(est, "w") as fh:
    fh.write(f"{corte}\n")
os.remove(fila)
res3, l3 = colher(REAL, est, fila)
depois = [e for e in esperado if e[0] > corte]
check("respeitou o corte", len(l3) == len(depois),
      f"{len(l3)} vs {len(depois)} (rowid > {corte})")
check("primeiro é o rowid seguinte",
      bool(l3) and bool(depois) and int(l3[0][1]) == depois[0][0])

print()
print("=" * 74)
print("4. paginas de overflow: textos maiores que a pagina")
print("=" * 74)
grande = os.path.join(WORK, "grande.db")
casos = [
    linha("a:\\" + "x" * 3000 + ".flac", "T" * 2500, "A" * 4000,
          "Ç" * 1200, 30000000, 1000000),
    linha("a:\\curto.flac", "n", "al", "ar", 1000000, 128000),
    linha("a:\\" + "y" * 900 + ".flac", "M" * 60, "B" * 60, "C" * 60,
          5000000, 320000),
]
cria(grande, casos, page_size=1024)
est2 = os.path.join(WORK, "e2.txt"); fila2 = os.path.join(WORK, "f2.tsv")
res4, l4 = rodar(grande, est2, fila2)
con = sqlite3.connect(f"file:{grande}?mode=ro", uri=True)
esp4 = list(con.execute("SELECT rowid, artist, name, album, path "
                        "FROM HISTORY_TABLE ORDER BY rowid"))
con.close()
check("leu as 3 linhas", len(l4) == 3, f"leu {len(l4)}")
for got, exp in zip(l4, esp4):
    rid, art, nome, alb, path = exp
    lim = lambda s: (s or "").rstrip("\x00")
    check(f"overflow rowid {rid}: artista {len(lim(art))} chars",
          desescapa(got[3]) == lim(art),
          f"C={len(desescapa(got[3]))} sqlite={len(lim(art))}")
    check(f"overflow rowid {rid}: album {len(lim(alb))} chars",
          desescapa(got[5]) == lim(alb))
    check(f"overflow rowid {rid}: path {len(lim(path))} chars",
          desescapa(got[9]) == lim(path))

print()
print("=" * 74)
print("5. arvore grande: forca paginas interiores")
print("=" * 74)
muitas = os.path.join(WORK, "muitas.db")
random.seed(7)
N = 5000
lst = [linha(f"a:\\d{i}\\f{i}.flac", f"Faixa {i}", f"Album {i%37}",
             f"Artista {i%91}", 3000000 + i, 320000) for i in range(N)]
cria(muitas, lst, page_size=512)
est3 = os.path.join(WORK, "e3.txt"); fila3 = os.path.join(WORK, "f3.tsv")
res5, l5 = rodar(muitas, est3, fila3)
check(f"leu as {N} linhas", len(l5) == N, f"leu {len(l5)}")
con = sqlite3.connect(f"file:{muitas}?mode=ro", uri=True)
esp5 = list(con.execute("SELECT rowid, artist, name FROM HISTORY_TABLE ORDER BY rowid"))
con.close()
iguais = sum(1 for g, e in zip(l5, esp5)
             if int(g[1]) == e[0] and desescapa(g[3]) == e[1].rstrip("\x00")
             and desescapa(g[4]) == e[2].rstrip("\x00"))
check("todas conferem com o sqlite", iguais == N, f"{iguais}/{N}")
check("em ordem de rowid", [int(x[1]) for x in l5] == sorted(int(x[1]) for x in l5))

print()
print("=" * 74)
print("6. caracteres que quebram TSV")
print("=" * 74)
# A ordem em linha() e (path, name, album, artist); na fila e
# (p1, rowid, hora, artist, name, album, album_artist, dur, ano, path) e a
# linha termina em tab, entao o split devolve 11 pedacos.
A, N, AL, P = 3, 4, 5, 9
sujo = os.path.join(WORK, "sujo.db")
cria(sujo, [
    linha("a:\\t\tab.flac", "nome\tcom\ttab", "album\nquebrado",
          "artista\\barra", 4000000, 320000),
    linha("a:\\ctrl.flac", "nome\x01controle", "al", "ar", 4000000, 320000),
    linha("a:\\uni.flac", "Não", "Ünïcödé", "★ 日本語 ção", 4000000, 320000),
], page_size=4096)
est4 = os.path.join(WORK, "e4.txt"); fila4 = os.path.join(WORK, "f4.tsv")
res6, l6 = rodar(sujo, est4, fila4)
check("3 linhas, nenhuma quebrada", len(l6) == 3, f"leu {len(l6)}")
check("nenhuma linha ganhou coluna extra", all(len(x) == 11 for x in l6),
      str([len(x) for x in l6]))
if len(l6) == 3:
    check("tab preservado no valor", desescapa(l6[0][N]) == "nome\tcom\ttab",
          repr(desescapa(l6[0][N])))
    check("quebra de linha preservada", desescapa(l6[0][AL]) == "album\nquebrado",
          repr(desescapa(l6[0][AL])))
    check("barra invertida preservada", desescapa(l6[0][A]) == "artista\\barra",
          repr(desescapa(l6[0][A])))
    check("tab no caminho preservado", desescapa(l6[0][P]) == "a:\\t\tab.flac",
          repr(desescapa(l6[0][P])))
    check("byte de controle preservado",
          desescapa(l6[1][N]) == "nome\x01controle", repr(desescapa(l6[1][N])))
    check("unicode intacto", desescapa(l6[2][A]) == "★ 日本語 ção",
          desescapa(l6[2][A]))

print()
print("=" * 74)
print("7. arquivos ruins nao podem derrubar nem travar o programa")
print("=" * 74)
ruins = []
with open(REAL, "rb") as fh:
    bom = fh.read()
casos_ruins = [
    ("vazio", b""),
    ("assinatura errada", b"NAO E SQLITE" + bom[12:2000]),
    ("truncado no meio", bom[:5000]),
    ("truncado em pagina parcial", bom[:1024 + 37]),
    ("page_size invalido", bom[:16] + b"\x00\x07" + bom[18:20000]),
    ("lixo aleatorio", bytes(random.getrandbits(8) for _ in range(9000))),
]
for nome, dados in casos_ruins:
    p = os.path.join(WORK, "ruim.db")
    with open(p, "wb") as fh:
        fh.write(dados)
    e = os.path.join(WORK, "er.txt"); q = os.path.join(WORK, "fr.tsv")
    res7, _ = rodar(p, e, q)
    saiu = res7.code
    check(f"{nome:28s} -> saida limpa", saiu in (0, 1, 2), f"rc={saiu}")

# byte a byte corrompido: nao pode segfault nem entrar em loop
print("   --- 120 corrupcoes aleatorias de 1 byte ---")
crashes = 0
for i in range(120):
    d = bytearray(bom[:60000])
    for _ in range(4):
        d[random.randrange(100, len(d))] = random.getrandbits(8)
    p = os.path.join(WORK, "fuzz.db")
    with open(p, "wb") as fh:
        fh.write(bytes(d))
    e = os.path.join(WORK, "ef.txt"); q = os.path.join(WORK, "ff.tsv")
    res8, _ = rodar(p, e, q)
    if res8.code not in (0, 1, 2):
        crashes += 1
        print(f"      rc={res8.code} na semente {i}")
check("nenhuma corrupcao derrubou o programa", crashes == 0, f"{crashes} quedas")

print()
print("=" * 74)
print("8. o banco NUNCA e aberto para escrita")
print("=" * 74)
somente_leitura = os.path.join(WORK, "ro.db")
cria(somente_leitura, [linha("a:\\x.flac", "n", "a", "ar", 4000000, 320000)])
antes_mtime = os.path.getmtime(somente_leitura)
antes_tam = os.path.getsize(somente_leitura)
e = os.path.join(WORK, "ero.txt"); q = os.path.join(WORK, "fro.tsv")
r.posix(f"chmod 444 {r.to_posix_path(somente_leitura)}", mutating=False, quiet=True)
res9, l9 = rodar(somente_leitura, e, q)
check("leu mesmo com o arquivo 444", len(l9) == 1, f"rc={res9.code}")
check("mtime do banco intacto", os.path.getmtime(somente_leitura) == antes_mtime)
check("tamanho do banco intacto", os.path.getsize(somente_leitura) == antes_tam)
check("nao deixou journal nem wal",
      not os.path.exists(somente_leitura + "-journal")
      and not os.path.exists(somente_leitura + "-wal"))

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
