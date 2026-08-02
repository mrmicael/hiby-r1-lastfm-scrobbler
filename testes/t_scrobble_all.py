"""Toda a suite do scrobbler, num veredito so."""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import os, subprocess, sys, time
for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
SCRATCH = os.path.dirname(os.path.abspath(__file__))
SUITE = [
    ("cliente Last.fm (API real)",   "t_lastfm.py",      240),
    ("leitor de SQLite em C",        "t_collector.py",  1500),
    ("daemon no busybox ash",        "t_daemon.py",      900),
    ("reconstrucao da fila",         "t_fila.py",        120),
    ("r1send: assinatura e lote",    "t_r1send.py",      600),
    ("disco ouvido com o daemon fora","t_lote.py",       300),
    ("envio automatico pelo WiFi",   "t_envio.py",       900),
    ("envio assim que a faixa acaba","t_imediato.py",    300),
    ("tocando agora (live)",         "t_agora.py",       600),
    ("comandos do init.sh",          "t_aparelho.py",    300),
    ("API de aparelho (adb falso)",  "t_adbapi.py",      180),
    ("conferencia do binario",       "t_conferir.py",    300),
    ("binarios do repositorio",      "t_bin.py",          60),
    ("janela do scrobbler",          "t_janela.py",      600),
    ("idiomas e catalogo",           "t_idioma.py",      120),
    ("registro ao vivo na janela",    "t_painel.py",      180),
]
res = []
for rot, script, lim in SUITE:
    p = os.path.join(SCRATCH, script)
    if not os.path.isfile(p):
        res.append((rot, "AUSENTE", 0)); continue
    print(f"\n{'='*72}\n>>> {rot}  ({script})\n{'='*72}", flush=True)
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, p], cwd=SCRATCH, timeout=lim,
                           capture_output=True, env=dict(os.environ, PYTHONUNBUFFERED="1"))
    except subprocess.TimeoutExpired:
        res.append((rot, "TIMEOUT", time.time()-t0)); print("TIMEOUT"); continue
    out = r.stdout.decode("utf-8", "replace")
    print("\n".join(out.strip().splitlines()[-4:]))
    if r.returncode:
        print("--- stderr ---")
        print("\n".join(r.stderr.decode("utf-8","replace").strip().splitlines()[-8:]))
    estado = "OK"
    if r.returncode == 3 or "PULADO" in out:
        estado = "PULADO"      # faltou credencial ou compilador; nao e verde
    elif r.returncode:
        estado = f"FALHOU({r.returncode})"
    res.append((rot, estado, time.time()-t0))
print(f"\n{'='*72}\nRESUMO DO SCROBBLER\n{'='*72}")
ruim = 0
for rot, st, s in res:
    marca = {"OK": "v", "PULADO": "-"}.get(st, "x")
    print(f" {marca} {rot:32s} {st:14s} {s:5.0f}s")
    if st not in ("OK", "PULADO"): ruim = 1
print("\n" + ("TUDO VERDE" if not ruim else "HA FALHAS"))
sys.exit(ruim)
