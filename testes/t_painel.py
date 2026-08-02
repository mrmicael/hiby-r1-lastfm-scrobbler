# -*- coding: utf-8 -*-
"""O registro ao vivo mostra o que o log escreve?

Este teste existe por causa de um bug que sobreviveu a tudo: a janela chamava
`logpane.write(...)` e o metodo se chama `append`. Uma excecao dentro de um
callback do `after()` do Tk nao derruba nada — o Tk 8.6 a engole, e o painel
simplesmente ficava vazio. Eu olhei para ele em varias capturas de tela sem
perceber. Dois usuarios acharam, cada um no seu sistema, quando o Tk 9.0
passou a mostrar o erro.

A licao nao e "chamar o metodo certo". E que ligar duas pontas e afirmar que
elas estao ligadas nao e a mesma coisa: aqui a ponta e exercitada de verdade,
escrevendo no log e conferindo o que aparece na tela.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import inspect, os, sys, tempfile

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from r1lastfm.applog import Log
from r1lastfm.ambiente import Ambiente
from r1lastfm.config import Config
from r1lastfm.runner import Runner
from r1lastfm.gui import widgets as W
from r1lastfm.gui.app import App

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


BASE = tempfile.mkdtemp(prefix="t_painel-")
log = Log(os.path.join(BASE, "t_painel.log"))
runner = Runner(log=log, dry_run=True, wsl_distro="Ubuntu")
cfg = Config(base=BASE, runner=runner, ambiente=Ambiente(runner=runner))
cfg.criar_pastas()

app = App(cfg, log)
app.withdraw()
app.update()

print("=" * 74)
print("1. o que a janela chama existe mesmo no painel")
print("=" * 74)
# A checagem que teria pego o bug sem precisar de tela: os nomes que o
# codigo da janela invoca no logpane tem de existir na classe.
import ast
fonte = open(os.path.join(_RAIZ, "r1lastfm", "gui", "app.py"),
             encoding="utf-8").read()
arv = ast.parse(fonte)
chamados = set()
for n in ast.walk(arv):
    if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Attribute)
            and n.value.attr == "logpane"):
        chamados.add(n.attr)
existem = {m for m, _ in inspect.getmembers(W.LogPane)}
faltando = sorted(c for c in chamados if c not in existem)
check(f"os {len(chamados)} membros usados existem no LogPane", not faltando,
      "; ".join(faltando))

print()
print("=" * 74)
print("2. escrever no log faz o texto aparecer na tela")
print("=" * 74)
antes = app.logpane.text.get("1.0", "end").strip()
check("o painel comeca vazio", antes == "", repr(antes[:40]))

log.step("uma etapa")
log.ok("deu certo")
log.warn("um aviso")
log.info("uma informacao")
app.update()

texto = app.logpane.text.get("1.0", "end")
linhas = [l for l in texto.splitlines() if l.strip()]
check("as quatro linhas chegaram", len(linhas) == 4, f"{len(linhas)} linha(s)")
for esperado in ("uma etapa", "deu certo", "um aviso", "uma informacao"):
    check(f"contem {esperado!r}", esperado in texto)

print()
print("=" * 74)
print("3. um erro no sink nao pode passar despercebido")
print("=" * 74)
# O que escondeu o bug foi o Tk engolir a excecao. Aqui o sink e chamado
# diretamente, fora do after(), onde um erro estoura de verdade.
try:
    app.logpane.append("info", "chamada direta")
    app.update()
    check("append() aceita a assinatura que o sink usa", True)
except Exception as exc:
    check("append() aceita a assinatura que o sink usa", False, str(exc))

check("e a chamada direta tambem aparece",
      "chamada direta" in app.logpane.text.get("1.0", "end"))

print()
print("=" * 74)
print("4. linhas demais nao fazem o painel crescer sem limite")
print("=" * 74)
for i in range(W.LogPane.MAX_LINES + 200):
    app.logpane.append("info", f"linha {i}")
app.update()
n = int(app.logpane.text.index("end-1c").split(".")[0])
check("o painel se mantem no teto", n <= W.LogPane.MAX_LINES + 50,
      f"{n} linhas com teto de {W.LogPane.MAX_LINES}")

print()
print("=" * 74)
print("5. fechar a janela nao deixa callback pendente")
print("=" * 74)
# O Tk chama o `after` agendado mesmo depois do destroy e reclama com
# "invalid command name ..._tique" na saida de erro. Num programa
# empacotado ninguem ve essa saida — e o mesmo tipo de erro calado que
# escondeu o painel vazio por meses.
import io, contextlib
app.run_async(lambda: __import__("time").sleep(0.4), busy_text="ocupado")
app.update()
check("o relogio ficou agendado", bool(app._tique_id), repr(app._tique_id))
err = io.StringIO()
with contextlib.redirect_stderr(err):
    app.destroy()
    try:
        app.update()
    except Exception:
        pass
sujeira = err.getvalue().strip()
check("nada foi para a saida de erro ao fechar", not sujeira, sujeira[:120])
check("os agendamentos foram cancelados",
      app._tique_id is None and app._drenar_id is None,
      f"tique={app._tique_id} drenar={app._drenar_id}")

import shutil
shutil.rmtree(BASE, ignore_errors=True)

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
