# -*- coding: utf-8 -*-
"""O curl compilado e experimentado no aparelho antes de substituir o que la
estava.

Uma receita que parecia mais correta gerava um curl que morria com sinal 11 em
toda requisicao. Quem ligou o envio por WiFi recebeu isto depois de meia hora
compilando:

    Segmentation fault
    CURL_FALHOU rc=139

e nada na mensagem apontava para o binario recem-feito. Pior: ele ja tinha
substituido um curl que funcionava.

O culpado era o --disable-threaded-resolver. O raciocinio era bom: em musl
estatico a thread do resolvedor do curl nao sobe, e toda requisicao morre com
"getaddrinfo() thread failed to start"; desligar o resolvedor em thread parece
resolver. So que o binario resultante segfaulta. O problema de DNS ja e
contornado onde deve — o daemon resolve o nome com o nslookup do busybox e
entrega o endereco pronto com --resolve.

Entao aqui ficam duas coisas: que a bandeira nao voltou para a receita, e que
o instalador experimenta o binario antes de deixa-lo entrar.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import inspect, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from r1lastfm import idioma as _idioma
_idioma.definir("en")
from r1lastfm import aparelho as AP
from r1lastfm.applog import Log
from r1lastfm.runner import InstallerError, Result

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


print("=" * 74)
print("1. a bandeira que quebrava o curl nao esta na receita")
print("=" * 74)
receita = open(_os.path.join(_RAIZ, "r1lastfm", "curlbuild.py"),
               encoding="utf-8").read()
# So o que o configure realmente recebe: o comentario CITA a bandeira de
# proposito, para explicar por que ela nao pode voltar.
linhas_conf = [l for l in receita.splitlines()
               if "--disable-threaded-resolver" in l
               and not l.lstrip().startswith("#")]
check("o configure nao recebe --disable-threaded-resolver",
      not linhas_conf, str(linhas_conf))
check("mas a receita explica por que ela nao volta",
      "SEGFAULTS on every request" in receita)
check("e aponta o contorno de verdade (nslookup + --resolve)",
      "--resolve" in receita and "nslookup" in receita)

print()
print("=" * 74)
print("2. o instalador experimenta o curl ANTES de trocar o que funciona")
print("=" * 74)
fonte = inspect.getsource(AP.instalar_envio)
check("o binario novo entra por um nome temporario",
      'CURL + ".novo"' in fonte)
check("e e executado no aparelho", "--version" in fonte)
check("com uma requisicao de verdade, nao so --version",
      "127.0.0.1:1" in fonte)
check("139 (sinal 11) e tratado como reprovacao", "V=139" in fonte)
check("o temporario e apagado quando reprova", "rm -f {provisorio}" in fonte)
i_mv = fonte.find("mv -f {provisorio}")
i_erro = fonte.find("ap.err.curl.quebrado")
check("e a troca so acontece DEPOIS da prova", 0 < i_erro < i_mv,
      f"erro em {i_erro}, troca em {i_mv}")

print()
print("=" * 74)
print("3. um curl quebrado e recusado, com o aparelho de mentira")
print("=" * 74)


class AdbFalso:
    """Responde como um aparelho onde o curl novo morre com sinal 11."""

    def __init__(self, resposta):
        self.resposta = resposta
        self.comandos = []
        self.pushes = []

    def shell(self, command, *, mutating=True, check=False, timeout=180):
        self.comandos.append(command)
        saida = ""
        if "--version" in command:
            saida = self.resposta
        elif "cacert" in command or "CACERT" in command:
            saida = "SIM"
        elif "-s /data/mnt" in command or "-s /usr/data" in command:
            saida = "SIM"
        return Result(code=0, stdout=saida, stderr="", command=command)

    def raw(self, args, *, mutating=True, check=False, timeout=180,
            on_line=None):
        return Result(code=0, stdout="", stderr="", command="")

    def push(self, local, remote, *, mode=None, on_line=None):
        self.pushes.append((local, remote, mode))
        return Result(code=0, stdout="", stderr="", command="")

    def mkdir(self, path):
        pass

    def chmod(self, path, mode="755"):
        pass

    def start_server(self):
        pass

    def require_device(self):
        pass


import tempfile
BASE = tempfile.mkdtemp(prefix="t_curl-")
log = Log(_os.path.join(BASE, "t_curl.log"))
P = lambda n, tam=100: (open(_os.path.join(BASE, n), "wb").write(b"x" * tam),
                        _os.path.join(BASE, n))[1]
r1send, curl = P("r1send"), P("curl")
cacert = P("cacert.pem", 60000)


def instalar(adb):
    return AP.instalar_envio(adb, log, remetente_local=r1send,
                             curl_local=curl, cacert_local=cacert,
                             session_key="k" * 32, api_key="a" * 32,
                             api_secret="s" * 32)


adb = AdbFalso("V=139 R=139")
try:
    instalar(adb)
    check("um curl que segfaulta e recusado", False, "deixou passar")
except InstallerError as exc:
    check("um curl que segfaulta e recusado", True, exc.message)
    check("a mensagem explica o 139", "139" in exc.detail)
    check("e diz que nada foi substituido",
          "Nothing was replaced" in exc.detail)
    check("e aponta a bandeira culpada",
          "--disable-threaded-resolver" in exc.detail)
check("o curl quebrado NAO virou o oficial",
      not any(c.startswith(f"mv -f {AP.CURL}.novo") for c in adb.comandos),
      str([c[:40] for c in adb.comandos if "mv " in c]))
check("e o temporario foi apagado",
      any("rm -f" in c and ".novo" in c for c in adb.comandos))

print()
adb = AdbFalso("V=0 R=7")     # roda, e nao conecta na porta fechada: sao
try:
    instalar(adb)
    check("um curl que funciona e instalado", True)
    check("e ele foi movido para o lugar certo",
          any(c.startswith(f"mv -f {AP.CURL}.novo") for c in adb.comandos),
          str([c[:50] for c in adb.comandos if "mv " in c]))
except InstallerError as exc:
    check("um curl que funciona e instalado", False, exc.message)

import shutil
shutil.rmtree(BASE, ignore_errors=True)
print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
