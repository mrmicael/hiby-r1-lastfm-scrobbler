# -*- coding: utf-8 -*-
"""Todas as funcoes que falam com o aparelho sao chamadas de verdade.

Isto existe por causa de um bug que passou por toda a suite: eu chamava
`adb.shell(..., quiet=True)`, e o Adb nao tem esse parametro. Nenhum teste
pegou porque nenhum deles chegava a executar essas funcoes — precisavam de um
aparelho ligado.

A solucao e um Adb de mentira que aceita exatamente a mesma interface do de
verdade (as assinaturas sao copiadas por inspecao, nao escritas a mao) e
grava o que foi pedido. Assim qualquer erro de chamada aparece aqui.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import inspect, os, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)

# O idioma e fixado aqui: as verificacoes olham o texto que sai, e o
# padrao muda conforme o idioma do computador de quem roda o teste.
from r1lastfm import idioma as _idioma
_idioma.definir("en")
from r1lastfm.adbtool import Adb, Device
from r1lastfm.applog import Log
from r1lastfm.runner import InstallerError, Result
from r1lastfm import aparelho as AP

SCRATCH = os.path.dirname(os.path.abspath(__file__))
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


class AdbFalso:
    """Mesma interface do Adb, sem aparelho.

    As assinaturas sao verificadas contra a classe real: se o Adb mudar, este
    duble para de bater e o teste avisa, em vez de esconder o problema.
    """

    def __init__(self, respostas=None):
        self.comandos = []
        self.pushes = []
        self.respostas = respostas or {}

    def _responder(self, comando):
        for chave, valor in self.respostas.items():
            if chave in comando:
                return valor
        return ""

    def shell(self, command, *, mutating=True, check=False, timeout=180):
        self.comandos.append(command)
        return Result(code=0, stdout=self._responder(command), stderr="",
                      command=f"adb shell {command[:60]}")

    def raw(self, args, *, mutating=True, check=False, timeout=180,
            on_line=None):
        self.comandos.append(" ".join(args))
        return Result(code=0, stdout="", stderr="", command="adb " + " ".join(args))

    def push(self, local, remote, *, mode=None, on_line=None):
        self.pushes.append((local, remote, mode))
        return Result(code=0, stdout="", stderr="", command=f"adb push {remote}")

    def mkdir(self, path):
        self.comandos.append(f"mkdir -p {path}")

    def chmod(self, path, mode="755"):
        self.comandos.append(f"chmod {mode} {path}")

    def start_server(self):
        pass

    def require_device(self):
        return Device(serial="falso", state="device")


print("=" * 74)
print("1. o duble tem a MESMA interface do Adb de verdade")
print("=" * 74)
for nome in ("shell", "raw", "push", "mkdir", "chmod"):
    real = inspect.signature(getattr(Adb, nome))
    falso = inspect.signature(getattr(AdbFalso, nome))
    # `self` de fora, comparando so os parametros
    pr = list(real.parameters.values())[1:]
    pf = list(falso.parameters.values())[1:]
    iguais = [p.name for p in pr] == [p.name for p in pf]
    check(f"Adb.{nome}{real}", iguais,
          "" if iguais else f"duble={[p.name for p in pf]}")

print()
print("=" * 74)
print("2. TODAS as funcoes de aparelho.py sao chamadas de verdade")
print("=" * 74)
log = Log(os.path.join(SCRATCH, "t_adbapi.log"))

# arquivos de mentira para os que exigem caminhos existentes
tmp = os.path.join(SCRATCH, "adbapi")
os.makedirs(tmp, exist_ok=True)
for nome, tamanho in (("r1collect", 100), ("r1scrobbled.sh", 100),
                      ("r1send", 100), ("curl", 100),
                      ("cacert.pem", 60000)):
    with open(os.path.join(tmp, nome), "wb") as fh:
        fh.write(b"x" * tamanho)
P = lambda n: os.path.join(tmp, n)

casos = [
    ("situacao", lambda a: AP.situacao(a)),
    ("instalar", lambda a: AP.instalar(a, log, P("r1collect"),
                                       P("r1scrobbled.sh"), rapido=15,
                                       lento=60, iniciar_no_boot=True)),
    ("instalar(tocando agora)", lambda a: AP.instalar(
        a, log, P("r1collect"), P("r1scrobbled.sh"), rapido=15, lento=60,
        agora=True, iniciar_no_boot=True)),
    ("instalar_envio", lambda a: AP.instalar_envio(
        a, log, remetente_local=P("r1send"), curl_local=P("curl"),
        cacert_local=P("cacert.pem"), session_key="k" * 32,
        api_key="a" * 32, api_secret="s" * 32)),
    ("instalar_cacert", lambda a: AP.instalar_cacert(a, log, P("cacert.pem"))),
    ("desligar_envio", lambda a: AP.desligar_envio(a, log)),
    ("ligar_no_boot", lambda a: AP.ligar_no_boot(a, log)),
    ("desligar_do_boot", lambda a: AP.desligar_do_boot(a, log)),
    ("iniciar_agora", lambda a: AP.iniciar_agora(a, log)),
    ("parar_agora", lambda a: AP.parar_agora(a, log)),
    ("desinstalar", lambda a: AP.desinstalar(a, log, apagar_fila=False)),
    ("desinstalar(apagando)", lambda a: AP.desinstalar(a, log, apagar_fila=True)),
    ("ler_enviados", lambda a: AP.ler_enviados(a)),
    ("marcar_enviados", lambda a: AP.marcar_enviados(a, log, {1, 2, 3})),
    ("limpar_fila", lambda a: AP.limpar_fila(a, log, {1, 2})),
    ("enviar_agora", lambda a: AP.enviar_agora(a, log)),
    ("puxar_fila", lambda a: AP.puxar_fila(a, log, P("baixada.tsv"))),
]
for nome, fn in casos:
    adb = AdbFalso({"[ -f " + AP.FILA: "SIM", "-s " + AP.FILA: "SIM",
                    "echo SIM": "SIM", "OK": "OK"})
    try:
        fn(adb)
        check(f"{nome:24s} chamou sem erro de assinatura", True,
              f"{len(adb.comandos)} comando(s), {len(adb.pushes)} push(es)")
    except InstallerError as exc:
        # erro de negocio e aceitavel; erro de Python nao e
        check(f"{nome:24s} erro tratado, nao de assinatura", True,
              f"InstallerError: {exc.message[:40]}")
    except TypeError as exc:
        check(f"{nome:24s} ERRO DE ASSINATURA", False, str(exc))
    except Exception as exc:
        check(f"{nome:24s} excecao inesperada", False,
              f"{type(exc).__name__}: {exc}")

print()
print("=" * 74)
print("3. o que cada funcao manda para o aparelho faz sentido")
print("=" * 74)
# O aparelho responde que TEM os certificados; sem isso a instalacao e
# recusada de proposito (ver o caso logo abaixo).
adb = AdbFalso({"echo SIM": "SIM"})
AP.instalar_envio(adb, log, remetente_local=P("r1send"), curl_local=P("curl"),
                  cacert_local=P("cacert.pem"), session_key="k" * 32,
                  api_key="a" * 32, api_secret="s" * 32)
destinos = [r for _l, r, _m in adb.pushes]
check("empurrou o r1send", AP.REMETENTE in destinos, str(destinos))
check("empurrou o curl", AP.CURL in destinos, str(destinos))
check("empurrou o cacert", AP.CACERT in destinos, str(destinos))
todos = " ; ".join(adb.comandos)
check("a chave de sessao vira 600", f"chmod 600 {AP.SK}" in todos,
      " | ".join(c for c in adb.comandos if "chmod" in c))
check("a chave de sessao NAO aparece em texto puro no log de comandos",
      todos.count("k" * 32) == 1,
      f"{todos.count('k' * 32)} vez(es) — so o proprio printf pode ter")

adb2 = AdbFalso()
AP.desligar_envio(adb2, log)
check("desativar apaga a chave e o segredo",
      all(x in " ".join(adb2.comandos) for x in (AP.SK, AP.SEGREDO)),
      " | ".join(adb2.comandos))
check("desativar NAO apaga a fila",
      AP.FILA not in " ".join(adb2.comandos), " | ".join(adb2.comandos))

adb3 = AdbFalso()
AP.desinstalar(adb3, log, apagar_fila=False)
cmds = " ".join(adb3.comandos)
check("desinstalar sem apagar preserva a fila", AP.FILA not in cmds)
check("mas apaga a chave de sessao", AP.SK in cmds)

adb4 = AdbFalso()
AP.instalar_cacert(adb4, log, P("cacert.pem"))
check("cacert vai com modo 644",
      any(r == AP.CACERT and m == "644" for _l, r, m in adb4.pushes),
      str(adb4.pushes))

print()
print("=" * 74)
print("3b. a configuracao gravada no aparelho reflete as escolhas")
print("=" * 74)
for liga, esperado in ((False, "AGORA=0"), (True, "AGORA=1")):
    adbc = AdbFalso()
    AP.instalar(adbc, log, P("r1collect"), P("r1scrobbled.sh"),
                rapido=20, lento=90, agora=liga, iniciar_no_boot=False)
    todos = " ".join(adbc.comandos)
    check(f"agora={liga} grava {esperado}", esperado in todos,
          " ".join(c for c in adbc.comandos if "AGORA" in c)[:70])
    check(f"agora={liga}: tempos escolhidos vao junto",
          "RAPIDO=20" in todos and "LENTO=90" in todos)
    check(f"agora={liga}: a versao e gravada",
          f"'{AP.VERSAO}' > {AP.VERSAO_ARQ}" in todos,
          " ".join(c for c in adbc.comandos if "versao" in c)[:60])

print()
print("=" * 74)
print("3c. a Situacao sabe dizer quando esta desatualizada")
print("=" * 74)
check("versao antiga -> desatualizada",
      AP.Situacao(instalado=True, versao=AP.VERSAO - 1).desatualizado)
check("versao atual -> em dia",
      not AP.Situacao(instalado=True, versao=AP.VERSAO).desatualizado)
check("sem versao gravada (instalacao antiga) -> desatualizada",
      AP.Situacao(instalado=True, versao=0).desatualizado)
check("nao instalado nao conta como desatualizado",
      not AP.Situacao(instalado=False, versao=0).desatualizado)
check("cada versao tem uma descricao do que mudou",
      all(v in AP.NOVIDADES for v in range(1, AP.VERSAO + 1)),
      str(sorted(AP.NOVIDADES)))

print()
print("=" * 74)
print("3d. sem certificados no aparelho, a instalacao do envio e RECUSADA")
print("=" * 74)
# Antes isto era so um aviso, e o resultado foi um recurso que parecia
# instalado e nunca funcionava: sem cacert o daemon nao manda nada e nao ha
# como o usuario descobrir por que.
adb_sem_ca = AdbFalso()   # o aparelho responde vazio: nao tem cacert
try:
    AP.instalar_envio(adb_sem_ca, log, remetente_local=P("r1send"),
                      curl_local=P("curl"), cacert_local="",
                      session_key="k" * 32, api_key="a" * 32,
                      api_secret="s" * 32)
    check("deveria ter recusado", False)
except InstallerError as exc:
    check("recusou", "certificate" in exc.message.lower(), exc.message)
    check("e explica que sem isso nada e enviado",
          "never happens" in exc.detail, exc.detail[:80])
    check("e diz qual botao resolve", "Download certificates" in exc.detail)

print()
print("=" * 74)
print("4. um cacert pequeno demais e recusado antes de subir")
print("=" * 74)
with open(P("pequeno.pem"), "wb") as fh:
    fh.write(b"nao sou um pacote de certificados")
adb5 = AdbFalso()
try:
    AP.instalar_cacert(adb5, log, P("pequeno.pem"))
    check("deveria ter recusado", False)
except InstallerError as exc:
    check("recusou com mensagem legivel", "too small" in exc.message.lower(),
          exc.message)
    check("e nao empurrou nada", not adb5.pushes, str(adb5.pushes))

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
