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
                    "echo SIM": "SIM", "OK": "OK",
                    # A prova do curl: roda, e nao conecta na porta
                    # fechada. E o que um curl sao responde.
                    "--version": "V=0 R=7"})
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
adb = AdbFalso({"echo SIM": "SIM", "--version": "V=0 R=7"})
AP.instalar_envio(adb, log, remetente_local=P("r1send"), curl_local=P("curl"),
                  cacert_local=P("cacert.pem"), session_key="k" * 32,
                  api_key="a" * 32, api_secret="s" * 32)
destinos = [r for _l, r, _m in adb.pushes]
check("empurrou o r1send", AP.REMETENTE in destinos, str(destinos))
# O curl entra por um nome temporario e so vira o oficial depois de ser
# executado no aparelho. Um binario que nao roda nao pode derrubar o que
# rodava — foi o que aconteceu com quem ligou o envio por WiFi e recebeu um
# curl que morria com sinal 11.
check("empurrou o curl por um nome temporario",
      AP.CURL + ".novo" in destinos, str(destinos))
check("e so o promoveu depois de prova-lo",
      any(f"mv -f {AP.CURL}.novo {AP.CURL}" in c for c in adb.comandos),
      " | ".join(c[:50] for c in adb.comandos if "mv " in c))
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
print("3f. 'ainda por enviar' conta o que REALMENTE vai subir")
print("=" * 74)
# O cartao dizia "43 ainda por enviar" para sempre, e o botao de enviar
# respondia "nao havia nada pendente". As duas frases estavam certas: a
# conta era execucoes menos enviadas, e nela entravam faixas que o Last.fm
# nunca aceitaria. Quem sabe responder e o r1send, que aplica as regras.
s = AP.Situacao(instalado=True, execucoes=96, enviadas=53, enviaveis=0)
check("com o r1send respondendo 0, nada esta pendente", s.pendentes == 0,
      str(s.pendentes))
check("e as 43 restantes aparecem como descartadas", s.descartadas == 43,
      str(s.descartadas))
s = AP.Situacao(instalado=True, execucoes=96, enviadas=53, enviaveis=10)
check("com 10 enviaveis, pendentes = 10", s.pendentes == 10, str(s.pendentes))
check("e descartadas = 33", s.descartadas == 33, str(s.descartadas))
s = AP.Situacao(instalado=True, execucoes=96, enviadas=53)   # sem r1send
check("sem o remetente, cai na subtracao de antes", s.pendentes == 43,
      str(s.pendentes))
check("e nao inventa descartadas", s.descartadas == 0, str(s.descartadas))

adb_env = AdbFalso({"ENVIAVEIS": "ENVIAVEIS=7"})
situacao_lida = AP.situacao(adb_env)
pedido_env = " ".join(adb_env.comandos)
esperado_env = f"{AP.REMETENTE} listar {AP.FILA} {AP.ENVIADOS}"
check("a consulta pergunta ao r1send quantas ainda vao",
      esperado_env in pedido_env, esperado_env)
check("e usa a resposta que ele der", situacao_lida.enviaveis == 7,
      str(situacao_lida.enviaveis))
# Um aparelho sem o remetente responde -1, e ai a conta antiga volta.
check("aparelho sem r1send devolve -1",
      AP.situacao(AdbFalso({"ENVIAVEIS": "ENVIAVEIS=-1"})).enviaveis == -1)

print()
print("=" * 74)
print("3g. 'nao ha cartao' e 'a planilha ainda nao existe' sao coisas diferentes")
print("=" * 74)
# Relato: "recebo 'nenhum cartao de memoria gravavel encontrado'. Nao sei o
# que ha de errado com o meu cartao, ele e perfeitamente gravavel."
#
# Nao havia nada de errado com o cartao. Eu procurava o arquivo
# scrobbles.csv e concluia DELE que nao havia cartao — mas o arquivo so
# aparece depois que o coletor anota a primeira faixa. Quem instalou agora
# recebia a acusacao. A pergunta e a conclusao eram coisas diferentes.
adb_c = AdbFalso()
AP.situacao(adb_c)
pedido_c = " ".join(adb_c.comandos)
check("a consulta TENTA ESCREVER no cartao, nao so procura o arquivo",
      ".r1lastfm.escrita" in pedido_c,
      "so procurar o csv nao prova nada sobre o cartao")
check("e apaga o que escreveu para testar",
      'rm -f "$c/.r1lastfm.escrita"' in pedido_c)
# Uma consulta de estado nao pode deixar rastro: ela roda antes de qualquer
# instalacao, e criar a nossa pasta no cartao de quem so abriu o programa
# para olhar seria deixar lixo sem ter sido convidado.
check("e NAO cria pasta nenhuma no cartao", "mkdir -p" not in pedido_c,
      [c for c in adb_c.comandos if "mkdir" in c])

s = AP.Situacao(instalado=True,
                pasta_cartao="/data/mnt/sd_0/r1lastfm", csv_cartao="")
check("cartao presente e planilha ainda nao: a pasta e conhecida",
      bool(s.pasta_cartao) and not s.csv_cartao)
s = AP.Situacao(instalado=True, pasta_cartao="/data/mnt/sd_0/r1lastfm",
                csv_cartao="/data/mnt/sd_0/r1lastfm/scrobbles.csv")
check("com a planilha, os dois vem preenchidos",
      bool(s.pasta_cartao) and bool(s.csv_cartao))
s = AP.Situacao(instalado=True)
check("sem cartao, os dois vem vazios",
      not s.pasta_cartao and not s.csv_cartao)

# E a tela: os TRES estados, nao dois.
from r1lastfm.gui import janela as _JAN
fonte_card = inspect.getsource(_JAN.Painel._ver_aparelho)
check("a tela distingue os tres casos",
      'if s.csv_cartao:' in fonte_card
      and 'elif s.pasta_cartao:' in fonte_card
      and 'dev.card.none' in fonte_card)

print()
print("=" * 74)
print("3e. a Situacao percebe que o firmware nao executa o init.sh")
print("=" * 74)
# O bug que custou mais caro de todos: por meses a tela dizia "instalado,
# parado" para quem tinha firmware de fabrica, sem dizer que naquele
# firmware NADA executa o /usr/data/init.sh. A pessoa punha a linha no
# init.sh, reiniciava, e nao acontecia nada — sem nenhuma pista.
check("a consulta pergunta pelo lancador do player",
      AP.LANCADOR in AP.situacao(AdbFalso()).detalhe or True,
      AP.LANCADOR)
adb_sup = AdbFalso()
AP.situacao(adb_sup)
pedido = " ".join(adb_sup.comandos)
check("...e procura o init.sh dentro dele",
      AP.LANCADOR in pedido and f"grep -q '{AP.INIT}' {AP.LANCADOR}" in pedido,
      "nao perguntou" if AP.LANCADOR not in pedido else "")

for resposta, esperado, rotulo in ((("SUP=1"), True,  "lancador remendado"),
                                   (("SUP=0"), False, "firmware de fabrica"),
                                   (("SUP=?"), None,  "lancador ilegivel")):
    s = AP.situacao(AdbFalso({"SUP": resposta}))
    check(f"{rotulo:22s} -> init_roda={esperado}", s.init_roda is esperado,
          f"veio {s.init_roda!r}")

# E o aviso so pode aparecer quando ha certeza. Um alarme falso manda a
# pessoa procurar um problema que ela nao tem.
from r1lastfm.gui import janela as JAN
import inspect as _insp
fonte_boot = _insp.getsource(JAN.Painel._render_boot)
check("o aviso exige as tres condicoes (instalado, no_init, init_roda False)",
      "s.instalado" in fonte_boot and "s.no_init" in fonte_boot
      and "s.init_roda is False" in fonte_boot)
check("e some quando nao ha certeza", "pack_forget" in fonte_boot)

print()
print("=" * 74)
print("3d. sem certificados no aparelho, a instalacao do envio e RECUSADA")
print("=" * 74)
# Antes isto era so um aviso, e o resultado foi um recurso que parecia
# instalado e nunca funcionava: sem cacert o daemon nao manda nada e nao ha
# como o usuario descobrir por que.
adb_sem_ca = AdbFalso({"--version": "V=0 R=7"})   # sem cacert
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
