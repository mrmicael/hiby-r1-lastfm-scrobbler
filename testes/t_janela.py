# -*- coding: utf-8 -*-
"""A janela e construida e exercitada de verdade, sem entrar no mainloop.

Nao e teste de importacao: os cartoes sao montados, os campos preenchidos, os
metodos chamados. O que se quer garantir e que nenhum caminho da interface
estoura um traceback na cara de quem esta so instalando um scrobbler.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, os, sys, tempfile, time, tkinter as tk

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

SCRATCH = os.path.dirname(os.path.abspath(__file__))

from r1lastfm import aparelho as AP
from r1lastfm import idioma
from r1lastfm.idioma import t
from r1lastfm.applog import Log
from r1lastfm.config import Config
from r1lastfm.ambiente import Ambiente
from r1lastfm.runner import Runner
from r1lastfm.gui.app import App
from r1lastfm.gui.janela import Painel

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


BASE = os.path.join(SCRATCH, "t_janela_dados")
log = Log(os.path.join(SCRATCH, "t_janela.log"))
runner = Runner(log=log, dry_run=True, wsl_distro="Ubuntu")
cfg = Config(base=BASE, runner=runner, ambiente=Ambiente(runner=runner))
cfg.criar_pastas()
# Comeca sempre do zero: uma execucao anterior nao pode fazer o teste passar.
if os.path.isfile(cfg.arquivo):
    os.remove(cfg.arquivo)

app = App(cfg, log)
app.withdraw()
win = Painel(app.area, cfg, app)
win.pack(fill="both", expand=True)


def bombear(limite=40.0):
    t0 = time.time()
    while app.ocupado and time.time() - t0 < limite:
        app.update()
        time.sleep(0.05)
    app.update()


bombear()

print("=" * 74)
print("1. a janela monta")
print("=" * 74)
check("construiu sem excecao", win.winfo_exists())
check("tem o cartao da chave de API", hasattr(win, "lbl_api"))
check("tem a arvore de execucoes", hasattr(win, "tree"))
check("tem o cartao do envio pelo WiFi", hasattr(win, "lbl_wifi"))
check("tem o interruptor do 'tocando agora'", hasattr(win, "var_agora"))
check("e ele comeca desligado", win.var_agora.get() is False)
check("botao de enviar comeca desabilitado",
      str(win.btn_enviar["state"]) == "disabled")

print()
print("=" * 74)
print("2. a chave de API: sem ela nao da para autorizar nada")
print("=" * 74)
check("comeca sem chave", not cfg.tem_api)
check("autorizar comeca travado",
      str(win.btn_autorizar["state"]) == "disabled")
# As verificacoes comparam com o proprio catalogo, e nao com uma frase
# escrita aqui: assim o teste vale em qualquer idioma, e uma traducao
# trocada por engano aparece na hora.
check("e a tela diz por que",
      win.lbl_conta.cget("text") == t("card.account.need_api"),
      win.lbl_conta.cget("text")[:70])

for rotulo, k, s in (
        ("curta demais", "abc", "f" * 32),
        ("com caractere que nao e hexadecimal", "z" * 32, "f" * 32),
        ("segredo vazio", "0" * 32, ""),
        ("com espaco no meio", "0" * 16 + " " + "0" * 15, "f" * 32)):
    win.var_api_key.set(k)
    win.var_api_secret.set(s)
    win._guardar_api()
    check(f"recusa chave {rotulo}", not cfg.tem_api,
          win.lbl_api.cget("text")[:50])

win.var_api_key.set("  " + "0" * 32 + "  ")     # espacos das pontas sao aparados
win.var_api_secret.set("F" * 32)                 # maiusculas tambem valem
win._guardar_api()
bombear()
check("aceita chave bem formada", cfg.tem_api)
check("aparou os espacos", cfg.api_key == "0" * 32, repr(cfg.api_key))
check("autorizar destravou", str(win.btn_autorizar["state"]) == "normal")
guardado = json.load(open(cfg.arquivo, encoding="utf-8"))
check("gravou so o que devia", sorted(guardado) == ["api_key", "api_secret"],
      str(sorted(guardado)))

print()
print("=" * 74)
print("3. a conta: guardar e apagar a chave de sessao")
print("=" * 74)
check("comeca sem chave de sessao", win._chave() == "", repr(win._chave()))
cfg.gravar(chave_sessao="chavefalsa123", usuario="fulano")
win._refletir_conta()
bombear()
check("leu a chave guardada", win._chave() == "chavefalsa123")
check("mostra o usuario", "fulano" in win.lbl_conta.cget("text"),
      win.lbl_conta.cget("text")[:60])
check("botao autorizar desabilita quando conectado",
      str(win.btn_autorizar["state"]) == "disabled")
cfg.gravar(chave_sessao="", usuario="")
win._refletir_conta()
check("desconectar limpa a sessao", win._chave() == "")
check("mas a chave de API continua", cfg.tem_api)

print()
print("=" * 74)
print("4. uma fila de verdade preenche a tabela")
print("=" * 74)
T0 = int(time.time()) - 3600
destino = os.path.join(cfg.trabalho, "scrobble", "fila.tsv")
os.makedirs(os.path.dirname(destino), exist_ok=True)


def p1(rid, hora, art, tit, dur, alb="Alb"):
    return f"p1\t{rid}\t{hora}\t{art}\t{tit}\t{alb}\t\t{dur}\t2020\ta:\\x.flac\t"


# A hora de cada p1 e o COMECO da faixa (observado ao vivo no R1). O que
# separa uma faixa ouvida de uma pulada e o espaco ate a linha SEGUINTE.
with open(destino, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join([
        f"b1\t{T0}",
        p1(1, T0 + 3,   "yui", "Again", 257),            # tocou 257: inteira
        p1(2, T0 + 260, "FLOW", "Go!!!", 240),           # tocou 240: inteira
        p1(3, T0 + 500, "Pulada", "Pulei em 40s", 300),  # tocou 40: fora
        p1(4, T0 + 540, "TOP", "Migraine", 238),         # tocou 238: inteira
        f"f1\t{T0 + 778}",
    ]) + "\n")

cfg.gravar(chave_sessao="chavefalsa123", usuario="fulano")
win._refletir_conta()
win.enviados = set()
win._reconstruir()
bombear()
linhas = win.tree.get_children()
check("tabela preenchida", len(linhas) == 4, f"{len(linhas)} linhas")
vals = [win.tree.item(i, "values") for i in linhas]
VAI = t("state.will_send")
vai = [v for v in vals if v[5] == VAI]
fica = [v for v in vals if v[5] != VAI]
check("3 vao", len(vai) == 3, str([v[2] for v in vai]))
check("a pulada fica", len(fica) == 1 and fica[0][2] == "Pulei em 40s", str(fica))
check("o motivo aparece na coluna",
      t("play.too_little", ouviu=40, total=300, precisa=150) == fica[0][5],
      fica[0][5])
check("botao de enviar habilitou", str(win.btn_enviar["state"]) == "normal")
check("resumo escrito", t("fila.ready", n=3) in win.lbl_resumo.cget("text"),
      win.lbl_resumo.cget("text"))

print()
print("=" * 74)
print("5. a hora mostrada e a de INICIO da faixa, nao a da gravacao")
print("=" * 74)
# A linha do historico entra quando a faixa comeca, entao a hora dela ja e a
# de inicio — e e essa que a tela mostra e que vai para o Last.fm. O errado
# de antes era mostrar a linha MENOS a duracao, uma faixa inteira mais cedo.
vals = [win.tree.item(i, "values") for i in win.tree.get_children()]
again = [v for v in vals if v[2] == "Again"]
check("Again aparece", bool(again), str([v[2] for v in vals]))
if again:
    esperado = time.strftime("%d/%m %H:%M", time.localtime(T0 + 3))
    check("a hora e a da linha, que ja e o inicio", again[0][0] == esperado,
          f"tela={again[0][0]} esperado={esperado}")
    check("coluna de tempo mostra ouvido/total", again[0][4] == "4:17/4:17",
          again[0][4])
pulada = [v for v in vals if v[2] == "Pulei em 40s"]
if pulada:
    check("a pulada mostra o pouco que tocou", pulada[0][4] == "0:40/5:00",
          pulada[0][4])

print()
print("=" * 74)
print("6. o que ja foi enviado nao reaparece")
print("=" * 74)
win.enviados = {1, 2}
win._reconstruir()
bombear()
vals = [win.tree.item(i, "values") for i in win.tree.get_children()]
vai3 = [v[2] for v in vals if v[5] == VAI]
check("so a Migraine sobrou", vai3 == ["Migraine"], str(vai3))

print()
print("=" * 74)
print("7. fila vazia / ausente nao quebra a tela")
print("=" * 74)
with open(destino, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("")
win.enviados = set()
win._reconstruir()
bombear()
check("tabela vazia sem excecao", len(win.tree.get_children()) == 0)
check("botao de enviar volta a desabilitar",
      str(win.btn_enviar["state"]) == "disabled")
os.remove(destino)
win._reconstruir()
bombear()
check("sem arquivo tambem nao quebra", True)

print()
print("=" * 74)
print("8. intervalos invalidos sao recusados sem traceback")
print("=" * 74)
win.var_rapido.set("abc")
try:
    win._instalar()
    bombear()
    ok = True
except Exception as exc:
    ok = False
    print("      excecao:", exc)
check("campo com letra nao levanta excecao", ok)
win.var_rapido.set("15")

print()
print("=" * 74)
print("8b. o cartao do WiFi diz o que falta, sem inventar")
print("=" * 74)
for sit, chave in (
        (AP.Situacao(instalado=False), "wifi.install_first"),
        (AP.Situacao(instalado=True, tem_curl=False, tem_chave=False,
                     tem_cacert=False), "wifi.missing.programs"),
        (AP.Situacao(instalado=True, envio_pronto=True, tem_curl=True,
                     tem_chave=True, tem_cacert=True, wifi_agora=True),
         "wifi.active"),
        (AP.Situacao(instalado=True, envio_pronto=True, tem_curl=True,
                     tem_chave=True, tem_cacert=True, wifi_agora=False),
         "wifi.radio_down"),
):
    win._render_wifi(sit)
    txt = win.lbl_wifi.cget("text")
    check(f"...{chave}", t(chave) in txt, txt[:70])
s_falta = AP.Situacao(instalado=True, tem_curl=True, tem_chave=False,
                      tem_cacert=True)
win._render_wifi(s_falta)
check("nomeia exatamente o que falta",
      t("wifi.missing.key") in win.lbl_wifi.cget("text")
      and t("wifi.missing.cacert") not in win.lbl_wifi.cget("text"),
      win.lbl_wifi.cget("text")[:80])

print()
print("=" * 74)
print("8c. a tela avisa quando o aparelho esta com versao velha")
print("=" * 74)
win._render_versao(AP.Situacao(instalado=True, versao=AP.VERSAO))
check("versao atual: diz que esta em dia",
      win.lbl_versao.cget("text") == t("ver.current", tem=AP.VERSAO),
      win.lbl_versao.cget("text")[:60])
win._render_versao(AP.Situacao(instalado=True, versao=AP.VERSAO - 1))
txt = win.lbl_versao.cget("text")
check("versao velha: oferece atualizar",
      t("ver.outdated", tem=AP.VERSAO - 1, nova=AP.VERSAO) in txt, txt[:70])
check("e diz o que muda", t("novidade." + str(AP.VERSAO)) in txt, txt[-80:])
win._render_versao(AP.Situacao(instalado=False))
check("sem instalacao, nao fala de versao", win.lbl_versao.cget("text") == "")

check("conta os pendentes certo",
      AP.Situacao(execucoes=10, enviadas=4).pendentes == 6)
check("pendentes nunca fica negativo",
      AP.Situacao(execucoes=2, enviadas=9).pendentes == 0)

print()
print("=" * 74)
print("9. as fontes que a interface vai compilar existem mesmo")
print("=" * 74)
fontes, daemon, saida_dir, col = win._caminhos()
for arq in ("collector.c", "r1send.c"):
    check(f"{arq} no lugar", os.path.isfile(os.path.join(fontes, arq)))
check("r1scrobbled.sh no lugar", os.path.isfile(daemon))
with open(daemon, "rb") as fh:
    check("o daemon nao tem CRLF", b"\r\n" not in fh.read())

print()
print("=" * 74)
print("10. sem curl compilado, a tela explica em vez de estourar")
print("=" * 74)
from r1lastfm.runner import InstallerError
try:
    win._curl_mipsel()
    check("devia ter reclamado", False)
except InstallerError as exc:
    check("vira mensagem legivel", t("btn.wifi.curl") in exc.detail,
          exc.message[:60])
except Exception as exc:
    check("vira mensagem legivel", False, f"{type(exc).__name__}: {exc}")

print()
print("=" * 74)
print("11. sem adb configurado, a tela avisa em vez de estourar")
print("=" * 74)
antes = cfg.ambiente.adb
try:
    cfg.ambiente.adb = None
    # _compilar fica de fora de proposito: compilar nao fala com o aparelho,
    # entao ele nem consulta o adb — e chama-lo aqui so deixaria uma thread de
    # compilacao rodando durante o resto do teste.
    for metodo in (win._ver_aparelho, win._puxar,
                   win._ativar_wifi, win._enviar_no_aparelho):
        try:
            metodo()
            bombear()
        except Exception as exc:
            check(f"{metodo.__name__} sem adb", False, str(exc))
            break
    else:
        check("nenhum caminho estoura sem adb", True)
finally:
    cfg.ambiente.adb = antes

print()
print("=" * 74)
print("12. trocar de idioma remonta a janela inteira")
print("=" * 74)
# O App remonta o conteudo quando o idioma muda. Aqui o mesmo mecanismo e
# exercitado de ponta a ponta: um painel novo, no idioma novo, com o texto
# do catalogo — e a preferencia gravada, para a proxima abertura.
antes_idioma = idioma.atual()
paineis = []


def construir(a):
    p = Painel(a.area, cfg, a)
    p.pack(fill="both", expand=True)
    paineis.append(p)


app.construir = construir
win.destroy()
app.update()

check("nada ficou rodando em segundo plano", not app.ocupado)

# A ordem comeca pelo idioma que NAO esta ativo: pedir o mesmo idioma e um
# no-op de proposito, e nao provaria nada sobre a remontagem.
ordem = [c for c in sorted(idioma.IDIOMAS) if c != idioma.atual()]
ordem += [c for c in sorted(idioma.IDIOMAS) if c == idioma.atual()]
for codigo in ordem:
    paineis.clear()
    app.var_idioma.set(idioma.IDIOMAS[codigo])
    app._trocar_idioma()
    app.update()
    novo = paineis[-1] if paineis else None
    check(f"{codigo}: o painel foi remontado", novo is not None
          and novo.winfo_exists())
    if novo:
        check(f"{codigo}: o rotulo saiu no idioma certo",
              novo.lbl_conta.cget("text") in (
                  t("card.account.connected", usuario="fulano"),
                  t("card.account.none"),
                  t("card.account.need_api")),
              novo.lbl_conta.cget("text")[:50])
    check(f"{codigo}: a escolha ficou gravada", cfg.idioma == codigo,
          repr(cfg.idioma))
    check(f"{codigo}: e o idioma de agora e esse", idioma.atual() == codigo)

# Trocar de idioma no meio de um trabalho seria destruir widgets que a thread
# ainda vai atualizar; a janela tem de recusar em vez de quebrar.
app._busy = True
alvo = "pt" if idioma.atual() == "en" else "en"
app.var_idioma.set(idioma.IDIOMAS[alvo])
app._trocar_idioma()
check("recusa trocar de idioma no meio de um trabalho",
      idioma.atual() != alvo, idioma.atual())
check("e volta a caixa para o idioma de verdade",
      app.var_idioma.get() == idioma.IDIOMAS[idioma.atual()])
app._busy = False
idioma.definir(antes_idioma)

cfg.gravar(chave_sessao="", usuario="")
app.update()
app.destroy()

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
