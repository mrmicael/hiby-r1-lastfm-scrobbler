# -*- coding: utf-8 -*-
"""O r1send em C tem de concordar com o lado do PC, e com o Last.fm.

Sao duas implementacoes das mesmas regras — uma em Python, no instalador, e
outra em C, no aparelho. Se elas divergirem, o scrobble sai errado num lugar
so e ninguem percebe. Entao aqui elas sao comparadas linha a linha.

E o teste decisivo da assinatura nao e contra o Python: e contra o proprio
Last.fm. Com uma chave de sessao falsa mas assinatura correta o servico
responde erro 9 (sessao invalida); se a assinatura estivesse errada ele
responderia 13. Distinguir os dois prova que a assinatura em C esta certa.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import hashlib, json, os, random, sys, urllib.parse, urllib.request

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from comum import compilar_para_o_pc
from r1lastfm.applog import Log
from r1lastfm.runner import Runner
from r1lastfm import fila as FQ
from r1lastfm.lastfm import signature

SCRATCH = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SCRATCH, "lastfm")
os.makedirs(WORK, exist_ok=True)
r = Runner(log=Log(os.path.join(WORK, "t_r1send.log")), wsl_distro="Ubuntu")
# Os dois programas do aparelho sao C portatil: compilados para este
# PC, respondem exatamente o mesmo que no MIPS do R1.
compilar_para_o_pc(r, "r1send")
EXE = r.to_posix_path(os.path.join(WORK, "r1send"))
# As credenciais NAO ficam no repositorio: cada pessoa registra a sua chave
# em https://www.last.fm/api/account/create e a passa pelo ambiente.
KEY = _os.environ.get("LASTFM_API_KEY", "")
SEC = _os.environ.get("LASTFM_API_SECRET", "")
if not (len(KEY) == 32 and len(SEC) == 32):
    print("PULADO: defina LASTFM_API_KEY e LASTFM_API_SECRET para rodar "
          "este teste. Registre uma chave em "
          "https://www.last.fm/api/account/create")
    raise SystemExit(0)
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


def arq(nome, conteudo):
    p = os.path.join(WORK, nome)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(conteudo)
    return p


def rodar(*args):
    linha = " ".join(EXE if a == "@" else
                     (r.to_posix_path(a) if os.path.sep in str(a) else str(a))
                     for a in ("@",) + args)
    return r.posix(linha + " 2>&1", mutating=False, quiet=True)


T0 = 1785500000


def p1(rid, hora, art, tit, dur, alb="Alb", aa=""):
    return f"p1\t{rid}\t{hora}\t{art}\t{tit}\t{alb}\t{aa}\t{dur}\t2020\ta:\\x.flac\t"


print("=" * 74)
print("1. o MD5 em C bate com o hashlib")
print("=" * 74)
# A assinatura e um MD5 de texto colado; testar o MD5 por dentro do proprio
# programa e o que importa, entao um caso conhecido serve de ancora.
casos = [
    ({"a": "1"}, "s"),
    ({"api_key": KEY, "method": "track.scrobble", "sk": "x" * 32}, SEC),
    ({"artist[0]": "Legião Urbana", "track[0]": "Faroeste Caboclo"}, SEC),
    ({"artist[0]": "★ 日本語", "track[0]": "ção ünïcödé"}, SEC),
]
for params, seg in casos:
    esperado = hashlib.md5(
        ("".join(f"{k}{params[k]}" for k in sorted(params)) + seg).encode("utf-8")
    ).hexdigest()
    check(f"assinatura de {list(params)[0][:16]}…",
          signature(params, seg) == esperado)

print()
print("=" * 74)
print("2. a MESMA fila, escolhida pelo C e pelo Python")
print("=" * 74)
# A linha entra quando a faixa COMECA, entao a hora de cada p1 e o comeco
# dela, e o espaco ate a linha SEGUINTE e quanto ela tocou. Uma faixa pulada
# se denuncia por ter a proxima linha logo em seguida.
FILA = "\n".join([
    f"b1\t{T0}",
    p1(1, T0 + 3,    "yui", "Again", 257),                 # tocou 257: inteira
    p1(2, T0 + 260,  "FLOW", "Go!!!", 240),                # tocou 240: inteira
    p1(3, T0 + 500,  "Pulada", "Pulei em 40s", 300),       # tocou 40 de 300
    p1(4, T0 + 540,  "TK from Ling tosite sigure",
       "Acoustic Installation", 362),                      # tocou 365: inteira
    p1(5, T0 + 905,  "SUPER JUNIOR", "라라라라 Be My Girl", 191),
    p1(6, T0 + 1096, "Legião Urbana", "Faroeste Caboclo", 540),
    # O daemon viu o audio parar: a ultima tocou 544s dos 540 dela.
    f"f1\t{T0 + 1640}",
    f"i1\t{T0 + 1640}",
]) + "\n"
f_fila = arq("rs_fila.tsv", FILA)
f_env = arq("rs_env.txt", "")

agora = T0 + 1700
res = rodar("listar", f_fila, f_env)
linhas_c = [l.split("\t") for l in res.stdout.strip().splitlines() if l.strip()]

regs, _ = FQ.ler(FILA)
rec = FQ.reconstruir(regs, agora=agora)
# O C usa a hora do relogio; para comparar, o Python usa a mesma janela.
py = [(p.artist, p.track, p.timestamp, p.duration, p.listened)
      for p in rec.execucoes]
c = [(x[2], x[3], int(x[1]), int(x[5]), int(x[6])) for x in linhas_c]
check("mesma quantidade", len(c) == len(py), f"C={len(c)} py={len(py)}")
for a, b in zip(sorted(c), sorted(py)):
    check(f"{a[0][:22]} — {a[1][:26]}", a == b, f"C={a} py={b}")
check("a pulada ficou de fora nos dois",
      "Pulei em 40s" not in [x[1] for x in c]
      and "Pulei em 40s" not in [x[1] for x in py],
      f"C={[x[1] for x in c]}")
# A hora que vai para o Last.fm tem de ser o INICIO da faixa — e a fila ja
# guarda o inicio, porque a linha do historico entra quando a faixa comeca.
# Antes daqui saia `hora - duracao`, uma faixa inteira ANTES do comeco.
# campos da fila: p1 rowid hora artista titulo album aa dur ano path
TAB = chr(9)
hora_de = {}
for l in FILA.splitlines():
    if l.startswith("p1"):
        cs = l.split(TAB)
        hora_de[int(cs[1])] = int(cs[2])
ok_horas = True
for linha in linhas_c:
    rid, inicio, dur = int(linha[0]), int(linha[1]), int(linha[5])
    if inicio != hora_de[rid]:
        ok_horas = False
        print(f"      rowid {rid}: inicio={inicio}, esperado {hora_de[rid]} "
              f"(o errado de antes seria {hora_de[rid] - dur})")
check("a hora enviada e a da linha, que ja e o inicio", ok_horas,
      f"{len(linhas_c)} faixas conferidas")

print()
print("=" * 74)
print("3. o corpo do POST: o C monta, o Python confere a assinatura")
print("=" * 74)
f_sk = arq("rs_sk.txt", "0" * 32 + "\n")
f_seg = arq("rs_seg.txt", SEC + "\n")
f_key = arq("rs_key.txt", KEY + "\n")
f_corpo = os.path.join(WORK, "rs_corpo.txt")
f_ids = os.path.join(WORK, "rs_ids.txt")
res = rodar("preparar", f_fila, f_env, f_sk, f_seg, f_key, f_corpo, f_ids)
check("preparou", res.ok, res.stdout.strip()[:80])
n = int(res.stdout.strip().splitlines()[-1]) if res.ok else 0
check("montou o lote inteiro", n == len(py), f"{n} de {len(py)}")

with open(f_corpo, encoding="utf-8") as fh:
    corpo = fh.read()
pares = urllib.parse.parse_qs(corpo, keep_blank_values=True,
                              encoding="utf-8", errors="replace")
plano = {k: v[0] for k, v in pares.items()}
sig_c = plano.pop("api_sig", "")
plano.pop("format", None)
check("tem api_sig", len(sig_c) == 32, sig_c[:12])
check("a assinatura do C bate com a do Python",
      sig_c == signature(plano, SEC),
      f"C={sig_c[:12]}… py={signature(plano, SEC)[:12]}…")
# Os indices sao a posicao NO LOTE, e a faixa pulada nao entrou nele — entao
# eles nao correspondem ao rowid. Achar pelo valor evita cravar numero errado.
def indice_de(prefixo, valor):
    for k, v in plano.items():
        if k.startswith(prefixo) and v == valor:
            return k[len(prefixo):-1]
    return None


i_legiao = indice_de("artist[", "Legião Urbana")
i_kor = indice_de("track[", "라라라라 Be My Girl")
check("acentos sobreviveram ao percent-encoding", i_legiao is not None,
      f"artist[{i_legiao}]" if i_legiao else "nao achei 'Legião Urbana'")
check("coreano sobreviveu", i_kor is not None,
      f"track[{i_kor}]" if i_kor else "nao achei o titulo em coreano")
check("method e sk presentes",
      plano.get("method") == "track.scrobble" and plano.get("sk") == "0" * 32)
check("faixa de 540s leva duration",
      i_legiao is not None and plano.get(f"duration[{i_legiao}]") == "540",
      plano.get(f"duration[{i_legiao}]", "ausente"))
check("faixa curta NAO leva duration",
      all(int(v) >= 30 for k, v in plano.items() if k.startswith("duration[")))
with open(f_ids, encoding="utf-8") as fh:
    ids = [int(x) for x in fh.read().split()]
check("os ids do lote batem com as execucoes", len(ids) == n, str(ids))

print()
print("=" * 74)
print("4. contra o Last.fm DE VERDADE: assinatura boa, chave falsa -> erro 9")
print("=" * 74)
print("   (se a assinatura estivesse errada o servico responderia 13)")
req = urllib.request.Request(
    "https://ws.audioscrobbler.com/2.0/", data=corpo.encode("utf-8"),
    headers={"User-Agent": "hiby-r1-scrobbler/1.0",
             "Content-Type": "application/x-www-form-urlencoded"})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        bruto = resp.read()
except urllib.error.HTTPError as exc:
    bruto = exc.read()
obj = json.loads(bruto.decode("utf-8", "replace"))
codigo = obj.get("error")
print(f"   resposta: erro {codigo} — {obj.get('message', '')}")
check("o Last.fm ACEITOU a assinatura em C", codigo == 9,
      f"erro {codigo}: {obj.get('message','')}")
if codigo == 13:
    print("   >>> 13 e 'assinatura invalida': a implementacao em C esta errada.")

print()
print("=" * 74)
print("5. a resposta do Last.fm, interpretada pelo C")
print("=" * 74)
resposta = json.dumps({"scrobbles": {
    "@attr": {"accepted": 2, "ignored": 1},
    "scrobble": [
        {"artist": {"#text": "yui"}, "ignoredMessage": {"code": "0", "#text": ""}},
        {"artist": {"#text": "FLOW"}, "ignoredMessage": {"code": "3",
                                                         "#text": "Too old"}},
        {"artist": {"#text": "TK"}, "ignoredMessage": {"code": "0", "#text": ""}},
    ]}}, ensure_ascii=False)
f_resp = arq("rs_resp.json", resposta)
f_ids3 = arq("rs_ids3.txt", "11\n22\n33\n")
f_env3 = arq("rs_env3.txt", "")
res = rodar("confirmar", f_resp, f_ids3, f_env3)
check("confirmou", res.ok, res.stdout.strip()[:60])
check("2 aceitas, 1 recusada", res.stdout.strip().splitlines()[-1] == "2 1",
      res.stdout.strip())
with open(os.path.join(WORK, "rs_env3.txt"), encoding="utf-8") as fh:
    marcados = sorted(int(x) for x in fh.read().split())
check("marcou so os aceitos (11 e 33)", marcados == [11, 33], str(marcados))

print()
print("=" * 74)
print("6. uma faixa so: a API devolve objeto, nao lista")
print("=" * 74)
um = json.dumps({"scrobbles": {"@attr": {"accepted": 1, "ignored": 0},
                               "scrobble": {"ignoredMessage": {"code": "0"}}}})
f_r = arq("rs_um.json", um)
f_i = arq("rs_um_ids.txt", "77\n")
f_e = arq("rs_um_env.txt", "")
res = rodar("confirmar", f_r, f_i, f_e)
check("tratou o objeto unico", res.ok and res.stdout.strip().endswith("1 0"),
      res.stdout.strip()[:40])

print()
print("=" * 74)
print("7. erro da API nao pode marcar nada como enviado")
print("=" * 74)
err = json.dumps({"error": 9, "message": "Invalid session key"})
f_r = arq("rs_err.json", err)
f_i = arq("rs_err_ids.txt", "5\n6\n")
f_e = arq("rs_err_env.txt", "")
res = rodar("confirmar", f_r, f_i, f_e)
check("saiu com erro", not res.ok, f"rc={res.code}")
conteudo = open(os.path.join(WORK, "rs_err_env.txt"), encoding="utf-8").read()
check("nao marcou nada", conteudo.strip() == "", repr(conteudo))

print()
print("=" * 74)
print("8. o que ja foi enviado nao entra no lote seguinte")
print("=" * 74)
f_env2 = arq("rs_env2.txt", "\n".join(str(i) for i in ids[:3]) + "\n")
res = rodar("preparar", f_fila, f_env2, f_sk, f_seg, f_key,
            os.path.join(WORK, "rs_corpo2.txt"), os.path.join(WORK, "rs_ids2.txt"))
n2 = int(res.stdout.strip().splitlines()[-1]) if res.ok else -1
check("lote menor", n2 == n - 3, f"{n2}, esperado {n - 3}")
res = rodar("preparar", f_fila, arq("rs_env_all.txt",
            "\n".join(str(i) for i in ids) + "\n"), f_sk, f_seg, f_key,
            os.path.join(WORK, "rs_corpo3.txt"), os.path.join(WORK, "rs_ids3b.txt"))
check("com tudo enviado, sai com 'nada a fazer' (rc=3)", res.code == 3,
      f"rc={res.code} saida={res.stdout.strip()[:30]}")

print()
print("=" * 74)
print("9. lotes de no maximo 50")
print("=" * 74)
muitas = [f"b1\t{T0}"]
for i in range(1, 81):
    muitas.append(p1(i, T0 + i * 300, f"Artista {i}", f"Faixa {i}", 280))
muitas.append(f"i1\t{T0 + 81 * 300}")
f_muitas = arq("rs_muitas.tsv", "\n".join(muitas) + "\n")
res = rodar("preparar", f_muitas, arq("rs_env_m.txt", ""), f_sk, f_seg, f_key,
            os.path.join(WORK, "rs_corpo_m.txt"), os.path.join(WORK, "rs_ids_m.txt"))
check("cortou em 50", res.stdout.strip().splitlines()[-1] == "50",
      res.stdout.strip()[:20])
with open(os.path.join(WORK, "rs_corpo_m.txt"), encoding="utf-8") as fh:
    corpo_m = fh.read()
plano_m = {k: v[0] for k, v in urllib.parse.parse_qs(corpo_m).items()}
sig_m = plano_m.pop("api_sig"); plano_m.pop("format", None)
check("assinatura do lote cheio confere", sig_m == signature(plano_m, SEC))
check("indices vao de 0 a 49",
      "artist[0]" in plano_m and "artist[49]" in plano_m
      and "artist[50]" not in plano_m)

print()
print("=" * 74)
print("10. fila corrompida ou vazia nao derruba nada")
print("=" * 74)
for nome, conteudo in (
        ("vazia", ""),
        ("so lixo", "isto nao presta\np1\tfalta\tcampo\n\x00\x01\n"),
        ("campos de menos", "p1\t1\t2\t3\n"),
        ("numeros absurdos", p1(1, 99999999999, "A", "B", -5) + "\n"),
        ("linha gigante", "p1\t1\t%d\t%s\tT\tA\t\t200\t2020\tp\t\n" % (T0, "x" * 9000)),
):
    fx = arq("rs_ruim.tsv", conteudo)
    res = rodar("preparar", fx, arq("rs_ruim_env.txt", ""), f_sk, f_seg, f_key,
                os.path.join(WORK, "rs_ruim_corpo.txt"),
                os.path.join(WORK, "rs_ruim_ids.txt"))
    check(f"{nome:20s} -> saida limpa", res.code in (0, 2, 3), f"rc={res.code}")

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
