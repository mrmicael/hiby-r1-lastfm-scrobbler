# -*- coding: utf-8 -*-
"""Testa o cliente Last.fm contra a API de verdade."""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import sys, os, io
for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from r1lastfm.idioma import t
from r1lastfm.lastfm import Client, Play, signature, LastfmError
from r1lastfm.runner import InstallerError

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
    if not ok: falhas.append(rot)

print("=" * 74)
print("1. a assinatura bate com o exemplo da documentacao")
print("=" * 74)
# Exemplo canonico: parametros ordenados, colados, mais o segredo, MD5.
import hashlib
p = {"api_key": "xxx", "method": "auth.getSession", "token": "yyy"}
esperado = hashlib.md5(("api_keyxxxmethodauth.getSessiontokenyyy" + "sss").encode()).hexdigest()
check("ordem e concatenacao", signature(p, "sss") == esperado)
check("format fica fora da assinatura",
      signature(dict(p, format="json"), "sss") == esperado)
check("callback fica fora da assinatura",
      signature(dict(p, callback="cb"), "sss") == esperado)
# acentos precisam ir em UTF-8, nao latin-1
acc = {"artist": "Legião Urbana"}
check("assina em UTF-8",
      signature(acc, "s") == hashlib.md5("artistLegião Urbanas".encode("utf-8")).hexdigest())

print()
print("=" * 74)
print("2. auth.getToken contra a API de verdade")
print("=" * 74)
c = Client(KEY, SEC)
try:
    tok = c.request_token()
    check("token recebido", len(tok) == 32, tok[:8] + "…")
    url = c.auth_url(tok)
    check("URL de aprovacao montada", url.startswith("https://www.last.fm/api/auth/?"))
    print("   ", url)
except InstallerError as e:
    check("auth.getToken", False, e.message)
    tok = None

print()
print("=" * 74)
print("3. um token NAO aprovado tem de dar erro 14, legivel")
print("=" * 74)
if tok:
    try:
        c.finish_auth(tok)
        check("deveria ter recusado", False)
    except LastfmError as e:
        check("erro 14 reconhecido", e.code == 14, e.message)
        # A mensagem sai do catalogo, entao a comparacao e com ele: assim
        # o teste continua valendo em qualquer idioma.
        check("mensagem veio traduzida", t("lfm.code.14") in e.message,
              e.message)

print()
print("=" * 74)
print("4. chave de sessao invalida -> erro 9, tratado")
print("=" * 74)
c2 = Client(KEY, SEC, session_key="0" * 32)
try:
    c2.check_session()
    check("deveria ter recusado", False)
except LastfmError as e:
    check("erro tratado sem traceback", e.code in (9, 4, 13), f"codigo {e.code}: {e.message}")

print()
print("=" * 74)
print("5. as regras de 'isso conta como execucao?'")
print("=" * 74)
casos = [
    (Play("A", "T", 1, duration=200, listened=150), True,  "ouviu 150 de 200"),
    (Play("A", "T", 1, duration=200, listened=99),  False, "ouviu menos da metade"),
    (Play("A", "T", 1, duration=200, listened=100), True,  "exatamente metade"),
    (Play("A", "T", 1, duration=600, listened=245), True,  "4 min de faixa longa"),
    (Play("A", "T", 1, duration=600, listened=239), False, "menos de 4 min"),
    (Play("A", "T", 1, duration=20,  listened=20),  False, "faixa de 20s"),
    (Play("",  "T", 1, duration=200, listened=200), False, "sem artista"),
    (Play("A", "T", 0, duration=200, listened=200), False, "sem hora"),
    (Play("A", "T", 1, duration=0,   listened=0),   True,  "sem duracao conhecida"),
]
for play, esperado, rot in casos:
    pode, motivo = play.scrobblable()
    check(f"{rot:26s} -> {'conta' if esperado else 'nao conta'}", pode == esperado, motivo)

print()
print("=" * 74)
print("6. montagem do lote")
print("=" * 74)
p = Play("Legião Urbana", "Faroeste Caboclo", 1785518448,
         album="Que País É Este", album_artist="Legião Urbana", duration=540)
f = p.fields(0)
check("indices por faixa", f["artist[0]"] == "Legião Urbana")
check("album incluido", f["album[0]"] == "Que País É Este")
check("albumArtist omitido quando igual ao artista", "albumArtist[0]" not in f)
check("duracao incluida", f["duration[0]"] == "540")
curta = Play("A", "T", 1, duration=10).fields(0)
check("duracao curta omitida", "duration[0]" not in curta)

print()
print("=" * 74)
print("7. a resposta com UMA faixa vem como objeto, nao lista")
print("=" * 74)
um = {"scrobbles": {"scrobble": {"ignoredMessage": {"code": "0", "#text": ""}},
                    "@attr": {"accepted": 1, "ignored": 0}}}
r = Client(KEY, SEC)._read_result(um, [Play("A", "T", 1)])
check("objeto unico tratado", r.accepted == 1 and not r.ignored)
varias = {"scrobbles": {"scrobble": [
    {"ignoredMessage": {"code": "0"}},
    {"ignoredMessage": {"code": "3", "#text": "Too old"}}]}}
r = Client(KEY, SEC)._read_result(varias, [Play("A", "T", 1), Play("B", "U", 2)])
check("lista tratada", r.accepted == 1 and len(r.ignored) == 1)
check("motivo traduzido", r.ignored[0][1] == t("lfm.ignore.3"),
      r.ignored[0][1])
curto = {"scrobbles": {"scrobble": [{"ignoredMessage": {"code": "0"}}]}}
r = Client(KEY, SEC)._read_result(curto, [Play("A", "T", 1), Play("B", "U", 2)])
check("resposta curta nao inventa sucesso", r.accepted == 1 and len(r.ignored) == 1)

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
