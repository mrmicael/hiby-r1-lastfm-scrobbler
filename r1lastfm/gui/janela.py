"""Last.fm scrobbler: authenticate, collect on the device, send both ways.

The two sending paths
---------------------
The R1 records offline always — that costs 1 ms of CPU per cycle and never
touches the network. What comes out of it can reach Last.fm two ways, and they
coexist without fighting because whatever was accepted is written down on the
device:

* **over Wi-Fi, by itself**: every twelve minutes the device checks whether a
  route out already exists. If it does, it sends. It never switches the radio
  on by itself: leaving Wi-Fi on costs hundreds of milliwatts, but riding along
  with one that was already on costs about 0.1% of the battery per send.
* **over the cable, from here**: this program pulls the queue and sends it.
  Costs the device nothing, and works for people who never turn Wi-Fi on.

What is stored, and where
-------------------------
* The Last.fm session key lives in this program's config.json, on this
  computer. It does not give access to your password and can be revoked from
  your Last.fm account at any time.
* The queue and the list of what was already sent live on the device, in
  /usr/data/scrobble. They live there on purpose: using this program from
  another computer then re-sends nothing.

Every string the user sees comes from ``textos.py`` through ``t()`` — see
``idioma.py`` for why.
"""

from __future__ import annotations

import os
import time
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Optional

from .. import aparelho as AP
from .. import compilar as CC
from .. import fila as FQ
from ..adbtool import Adb
from ..ambiente import URL_PLATFORM_TOOLS
from ..config import Config
from ..idioma import t
from ..lastfm import Client, Play, ScrobbleResult, send_all
from ..runner import InstallerError
from . import widgets as W

# Onde se registra uma chave de API do Last.fm. É grátis, leva um minuto, e
# cada pessoa usa a sua: um segredo compartilhado publicado num repositório
# deixaria qualquer um se passar por este aplicativo.
URL_REGISTRO_API = "https://www.last.fm/api/account/create"


def _hhmm(epoch: int) -> str:
    return time.strftime("%d/%m %H:%M", time.localtime(epoch))


def _dur(seg: int) -> str:
    if seg <= 0:
        return "—"
    return f"{seg // 60}:{seg % 60:02d}"


class Painel(ttk.Frame):
    def __init__(self, master, cfg: Config, app):
        super().__init__(master, style="TFrame")
        self.cfg = cfg
        self.app = app
        self.log = app.log
        self.rec: Optional[FQ.Reconstrucao] = None
        self.token = ""
        self.enviados: set[int] = set()
        self.situacao: Optional[AP.Situacao] = None

        scroll = W.ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.body

        self._card_intro(body)
        self._card_api(body)
        self._card_conta(body)
        self._card_coletor(body)
        self._card_wifi(body)
        self._card_fila(body)
        self._card_enviar(body)

        self._refletir_api()
        self._refletir_conta()
        self.after(200, self._ver_aparelho)

    # -- cartões -------------------------------------------------------------

    def _card_intro(self, body) -> None:
        c = W.Card(body, title=t("card.intro.title"))
        c.pack(fill="x", pady=(0, 12))
        W.body_label(c, t("card.intro.body"))
        W.body_label(c, t("card.intro.cost"), style="CardMuted.TLabel")

    def _card_api(self, body) -> None:
        c = W.Card(body, title=t("card.api.title"))
        c.pack(fill="x", pady=(0, 12))
        W.body_label(c, t("card.api.body"))

        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x", pady=(10, 0))
        ttk.Button(linha, text=t("card.api.open"),
                   command=lambda: webbrowser.open(URL_REGISTRO_API)).pack(
                       side="left")
        W.body_label(c, t("card.api.howto"), style="CardMuted.TLabel")

        grade = ttk.Frame(c, style="Card.TFrame")
        grade.pack(fill="x", pady=(10, 0))
        ttk.Label(grade, text=t("card.api.key"), style="Card.TLabel", width=14,
                  anchor="w").grid(row=0, column=0, sticky="w", pady=3)
        self.var_api_key = tk.StringVar()
        ttk.Entry(grade, textvariable=self.var_api_key, width=44).grid(
            row=0, column=1, sticky="w")
        ttk.Label(grade, text=t("card.api.secret"), style="Card.TLabel",
                  width=14, anchor="w").grid(row=1, column=0, sticky="w", pady=3)
        self.var_api_secret = tk.StringVar()
        ttk.Entry(grade, textvariable=self.var_api_secret, width=44).grid(
            row=1, column=1, sticky="w")

        acoes = ttk.Frame(c, style="Card.TFrame")
        acoes.pack(fill="x", pady=(10, 0))
        ttk.Button(acoes, text=t("card.api.save"), style="Accent.TButton",
                   command=self._guardar_api).pack(side="left")
        self.lbl_api = ttk.Label(c, text="", style="Card.TLabel",
                                 wraplength=880, justify="left")
        self.lbl_api.pack(anchor="w", pady=(8, 0))

    def _guardar_api(self) -> None:
        chave = self.var_api_key.get().strip()
        segredo = self.var_api_secret.get().strip()
        # Os dois são hexadecimais de 32 caracteres. Conferir aqui evita uma
        # viagem inteira até o Last.fm para receber "assinatura inválida".
        def parece_chave(v: str) -> bool:
            return len(v) == 32 and all(c in "0123456789abcdefABCDEF" for c in v)

        if not parece_chave(chave) or not parece_chave(segredo):
            self.lbl_api.configure(text=t("card.api.bad"))
            return
        self.cfg.gravar(api_key=chave, api_secret=segredo)
        self.lbl_api.configure(text=t("card.api.saved"))
        self._refletir_conta()

    def _refletir_api(self) -> None:
        if self.cfg.tem_api:
            self.var_api_key.set(self.cfg.api_key)
            self.var_api_secret.set(self.cfg.api_secret)
            self.lbl_api.configure(text=t("card.api.stored"))
        else:
            self.lbl_api.configure(text=t("card.api.missing"))

    def _card_conta(self, body) -> None:
        c = W.Card(body, title=t("card.account.title"))
        c.pack(fill="x", pady=(0, 12))
        self.lbl_conta = ttk.Label(c, text="", style="Card.TLabel",
                                   wraplength=880, justify="left")
        self.lbl_conta.pack(anchor="w")

        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x", pady=(10, 0))
        self.btn_autorizar = ttk.Button(
            linha, text=t("card.account.authorise"), style="Accent.TButton",
            command=self._autorizar_passo1)
        self.btn_autorizar.pack(side="left")
        self.btn_concluir = ttk.Button(
            linha, text=t("card.account.done"), command=self._autorizar_passo2,
            state="disabled")
        self.btn_concluir.pack(side="left", padx=(8, 0))
        self.btn_sair = ttk.Button(linha, text=t("card.account.signout"),
                                   command=self._desconectar)
        self.btn_sair.pack(side="left", padx=(8, 0))

        W.body_label(c, t("card.account.note"), style="CardMuted.TLabel")

    def _card_coletor(self, body) -> None:
        c = W.Card(body, title=t("card.collector.title"))
        c.pack(fill="x", pady=(0, 12))
        self.lbl_dispositivo = ttk.Label(
            c, text=t("card.collector.looking"), style="Card.TLabel",
            wraplength=880, justify="left")
        self.lbl_dispositivo.pack(anchor="w")

        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x", pady=(10, 0))
        for chave, cb, estilo in (
                ("btn.check", self._ver_aparelho, "TButton"),
                ("btn.build", self._compilar, "TButton"),
                ("btn.install", self._instalar, "Accent.TButton"),
                ("btn.iniciar", self._iniciar, "TButton"),
                ("btn.remove", self._remover, "TButton")):
            ttk.Button(linha, text=t(chave), command=cb, style=estilo).pack(
                side="left", padx=(0, 8))
        # O aviso do boot fica num rótulo próprio e em destaque, e não junto
        # da linha de estado: é a diferença entre o programa funcionar e não
        # funcionar, e precisa caber a explicação inteira mais o comando.
        self.lbl_boot = ttk.Label(c, text="", style="CardWarn.TLabel",
                                  wraplength=880, justify="left")
        # O botão do remendo só existe quando ele é a resposta: aparece junto
        # com o aviso, e some com ele. Um botão de "remendar firmware" sempre
        # visível convida ao clique sem ler, e esta é a única coisa aqui que
        # pode inutilizar um aparelho.
        self.btn_firmware = ttk.Button(c, text=t("btn.firmware"),
                                       command=self._remendar_firmware)
        self.lbl_versao = ttk.Label(c, text="", style="CardMuted.TLabel",
                                    wraplength=880, justify="left")
        self.lbl_versao.pack(anchor="w", pady=(8, 0))

        tempos = ttk.Frame(c, style="Card.TFrame")
        tempos.pack(fill="x", pady=(10, 0))
        ttk.Label(tempos, text=t("card.collector.every"),
                  style="Card.TLabel").pack(side="left")
        self.var_rapido = tk.StringVar(value="15")
        ttk.Entry(tempos, textvariable=self.var_rapido, width=5).pack(
            side="left", padx=4)
        ttk.Label(tempos, text=t("card.collector.playing"),
                  style="Card.TLabel").pack(side="left")
        self.var_lento = tk.StringVar(value="60")
        ttk.Entry(tempos, textvariable=self.var_lento, width=5).pack(
            side="left", padx=4)
        ttk.Label(tempos, text=t("card.collector.idle"),
                  style="Card.TLabel").pack(side="left")
        W.body_label(c, t("card.collector.tradeoff"), style="CardMuted.TLabel")

    def _card_wifi(self, body) -> None:
        c = W.Card(body, title=t("card.wifi.title"))
        c.pack(fill="x", pady=(0, 12))
        W.body_label(c, t("card.wifi.body"))
        self.lbl_wifi = ttk.Label(c, text="", style="Card.TLabel",
                                  wraplength=880, justify="left")
        self.lbl_wifi.pack(anchor="w", pady=(8, 0))

        self.var_agora = tk.BooleanVar(value=False)
        # O comando aplica no aparelho na hora. Antes esta caixa só era lida
        # pelo botão de instalar, que fica no cartão ANTERIOR — marcar depois
        # de instalar não fazia efeito nenhum, e nada avisava.
        ttk.Checkbutton(
            c, style="Card.TCheckbutton", variable=self.var_agora,
            command=self._alternar_agora, text=t("card.wifi.now")
        ).pack(anchor="w", pady=(10, 0))
        W.body_label(c, t("card.wifi.now.note"), style="CardMuted.TLabel")

        self.progresso_ca = W.ProgressRow(c)
        self.progresso_ca.pack(fill="x", pady=(10, 0))

        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x", pady=(10, 0))
        ttk.Button(linha, text=t("btn.wifi.enable"), style="Accent.TButton",
                   command=self._ativar_wifi).pack(side="left")
        for chave, cb in (("btn.wifi.curl", self._compilar_curl),
                          ("btn.wifi.cacert", self._baixar_cacert),
                          ("btn.wifi.test", self._enviar_no_aparelho),
                          ("btn.wifi.disable", self._desativar_wifi)):
            ttk.Button(linha, text=t(chave), command=cb).pack(
                side="left", padx=(8, 0))

        W.body_label(c, t("card.wifi.key_note"), style="CardMuted.TLabel")

    def _card_fila(self, body) -> None:
        c = W.Card(body, title=t("card.queue.title"))
        c.pack(fill="both", expand=True, pady=(0, 12))
        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x")
        ttk.Button(linha, text=t("btn.queue.fetch"), style="Accent.TButton",
                   command=self._puxar).pack(side="left")
        # A política de "última faixa da sessão" existia enquanto não se sabia
        # em que momento o player grava a linha. Medido no aparelho, ele grava
        # no FIM — a linha só existe porque a faixa acabou, e não há mais
        # incerteza para o usuário resolver. O modo continua no código, para o
        # caso de outra versão de firmware se comportar de outro jeito.
        self.var_ultima = tk.StringVar(value=FQ.ULTIMA_ASSUME_INTEIRA)

        self.lbl_resumo = ttk.Label(c, text=t("card.queue.empty"),
                                    style="CardMuted.TLabel",
                                    wraplength=880, justify="left")
        self.lbl_resumo.pack(anchor="w", pady=(10, 0))
        W.body_label(c, t("card.queue.note"), style="CardMuted.TLabel")

        cols = ("quando", "artista", "faixa", "album", "ouviu", "estado")
        self.tree = ttk.Treeview(c, columns=cols, show="headings", height=13,
                                 selectmode="extended")
        for col, chave, larg in (("quando", "col.when", 110),
                                 ("artista", "col.artist", 170),
                                 ("faixa", "col.track", 220),
                                 ("album", "col.album", 170),
                                 ("ouviu", "col.listened", 90),
                                 ("estado", "col.state", 210)):
            self.tree.heading(col, text=t(chave))
            self.tree.column(col, width=larg,
                             anchor="center" if col in ("quando", "ouviu") else "w")
        self.tree.pack(fill="both", expand=True, pady=(10, 0))
        self.tree.tag_configure("vai", foreground=W.COL_OK)
        self.tree.tag_configure("fica", foreground=W.COL_MUTED)

    def _card_enviar(self, body) -> None:
        c = W.Card(body, title=t("card.send.title"))
        c.pack(fill="x", pady=(0, 12))
        self.progresso = W.ProgressRow(c)
        self.progresso.pack(fill="x")
        linha = ttk.Frame(c, style="Card.TFrame")
        linha.pack(fill="x", pady=(10, 0))
        self.btn_enviar = ttk.Button(linha, text=t("btn.send"),
                                     style="Accent.TButton", command=self._enviar,
                                     state="disabled")
        self.btn_enviar.pack(side="left")
        ttk.Button(linha, text=t("btn.trim"),
                   command=self._enxugar).pack(side="left", padx=(8, 0))
        self.lbl_envio = ttk.Label(c, text="", style="CardMuted.TLabel",
                                   wraplength=880, justify="left")
        self.lbl_envio.pack(anchor="w", pady=(8, 0))

    # -- conta ---------------------------------------------------------------

    def _chave(self) -> str:
        return str(self.cfg.ler().get("chave_sessao", "") or "")

    def _cliente(self) -> Client:
        return Client(self.cfg.api_key, self.cfg.api_secret, log=self.log,
                      session_key=self._chave())

    def _refletir_conta(self) -> None:
        usuario = str(self.cfg.ler().get("usuario", "") or "")
        if not self.cfg.tem_api:
            # Sem chave de API não há o que autorizar: o Last.fm nem sabe
            # quem está pedindo. Deixar o botão ativo só levaria a um erro
            # cru vindo da API.
            self.lbl_conta.configure(text=t("card.account.need_api"))
            self.btn_autorizar.configure(state="disabled")
            self.btn_sair.configure(state="disabled")
            self._reavaliar_envio()
            return
        if self._chave():
            self.lbl_conta.configure(text=t(
                "card.account.connected",
                usuario=usuario or t("card.account.unknown_user")))
            self.btn_autorizar.configure(state="disabled")
            self.btn_sair.configure(state="normal")
        else:
            self.lbl_conta.configure(text=t("card.account.none"))
            self.btn_autorizar.configure(state="normal")
            self.btn_sair.configure(state="disabled")
        self._reavaliar_envio()

    def _autorizar_passo1(self) -> None:
        cli = Client(self.cfg.api_key, self.cfg.api_secret, log=self.log)

        def work():
            return cli.request_token()

        def done(tok) -> None:
            self.token = str(tok)
            url = cli.auth_url(self.token)
            self.btn_concluir.configure(state="normal")
            self.lbl_conta.configure(text=t("card.account.browser_open", url=url))
            try:
                webbrowser.open(url)
            except Exception:
                pass

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.token"))

    def _autorizar_passo2(self) -> None:
        if not self.token:
            return
        cli = Client(self.cfg.api_key, self.cfg.api_secret, log=self.log)
        tok = self.token

        def work():
            chave = cli.finish_auth(tok)
            return chave, cli.username

        def done(par) -> None:
            chave, usuario = par
            self.cfg.gravar(chave_sessao=chave, usuario=usuario)
            self.token = ""
            self.btn_concluir.configure(state="disabled")
            self.log.ok(t("log.connected", usuario=usuario))
            self._refletir_conta()

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.auth"))

    def _desconectar(self) -> None:
        if not W.confirm(self, t("card.account.signout.title"),
                         t("card.account.signout.body"),
                         ok_text=t("card.account.signout")):
            return
        self.cfg.gravar(chave_sessao="", usuario="")
        self._refletir_conta()

    # -- aparelho ------------------------------------------------------------

    def _adb(self) -> Optional[Adb]:
        caminho = self.cfg.ambiente.adb
        if not caminho:
            W.show_error(self, t("err.adb.title"),
                         t("err.adb.body", url=URL_PLATFORM_TOOLS))
            return None
        return Adb(self.cfg.runner, self.log, caminho)

    def _ver_aparelho(self) -> None:
        adb = self._adb()
        if adb is None:
            return

        def work():
            adb.start_server()
            adb.require_device()
            return AP.situacao(adb)

        def done(s: AP.Situacao) -> None:
            self.situacao = s
            partes = [t("dev.installed") if s.instalado else t("dev.not_installed")]
            if s.instalado:
                partes.append(t("dev.running") if s.rodando else t("dev.stopped"))
                # Não adianta dizer "inicia junto com o player" quando nada
                # neste firmware executa o init.sh. Era o caso de quem
                # instalou num R1 de fábrica: a tela dizia que estava tudo
                # certo e o coletor nunca subia, sem nenhuma pista do porquê.
                if s.init_roda is False:
                    partes.append(t("dev.sem_boot"))
                else:
                    partes.append(t("dev.boots") if s.no_init
                                  else t("dev.no_boot"))
                if s.espera_sem_fork is False:
                    partes.append(t("dev.no_read_t"))
            partes.append(t("dev.counts", execucoes=s.execucoes,
                            pendentes=s.pendentes))
            if s.descartadas:
                partes.append(t("dev.discarded", descartadas=s.descartadas))
            # Onde a planilha está — ou por que não há uma. Perguntaram "cadê
            # o scrobbles.csv?" e a tela não dizia nada a respeito.
            partes.append(t("dev.card", caminho=s.csv_cartao)
                          if s.csv_cartao else t("dev.card.none"))
            self.lbl_dispositivo.configure(text="  ".join(partes))
            self._render_boot(s)
            self._render_versao(s)
            self.var_agora.set(s.tocando_agora)
            self._render_wifi(s)

        def falhou(exc: InstallerError) -> None:
            self.lbl_dispositivo.configure(
                text=t("dev.plug_in", mensagem=exc.message))

        self.app.run_async(work, on_done=done, on_error=falhou,
                           busy_text=t("busy.device"))

    def _render_boot(self, s: AP.Situacao) -> None:
        """Mostra (ou esconde) o aviso de que o firmware não inicia nada.

        Só aparece quando há certeza: instalado, com a linha no init.sh, e o
        lançador do player lido sem citar o init.sh. Se não deu para ler o
        lançador (`init_roda is None`), fica calado — um aviso errado custa
        mais caro do que aviso nenhum.
        """
        if s.instalado and s.no_init and s.init_roda is False:
            self.lbl_boot.configure(text=t("dev.sem_boot.ajuda"))
            self.lbl_boot.pack(anchor="w", pady=(10, 0), before=self.lbl_versao)
            self.btn_firmware.pack(anchor="w", pady=(8, 0),
                                   before=self.lbl_versao)
        else:
            self.lbl_boot.pack_forget()
            self.btn_firmware.pack_forget()

    def _render_versao(self, s: AP.Situacao) -> None:
        if not s.instalado:
            self.lbl_versao.configure(text="")
            return
        if s.desatualizado:
            novidades = [AP.novidade(v)
                         for v in sorted(AP.NOVIDADES, reverse=True)
                         if s.versao < v <= AP.VERSAO]
            texto = t("ver.outdated", tem=s.versao or "?", nova=AP.VERSAO)
            if novidades:
                texto += t("ver.changes", lista="; ".join(novidades))
            self.lbl_versao.configure(text=texto)
        else:
            self.lbl_versao.configure(text=t("ver.current", tem=s.versao))

    def _render_wifi(self, s: AP.Situacao) -> None:
        if not s.instalado:
            self.lbl_wifi.configure(text=t("wifi.install_first"))
            return
        partes = []
        if s.envio_pronto:
            partes.append(t("wifi.active"))
        else:
            faltando = []
            if not s.tem_curl:
                faltando.append(t("wifi.missing.programs"))
            if not s.tem_chave:
                faltando.append(t("wifi.missing.key"))
            if not s.tem_cacert:
                faltando.append(t("wifi.missing.cacert"))
            partes.append(t("wifi.off_missing", faltando=", ".join(faltando)))
        partes.append(t("wifi.radio_up") if s.wifi_agora else t("wifi.radio_down"))
        if s.ultimo_envio:
            partes.append(t("wifi.last_send", quando=s.ultimo_envio))
        self.lbl_wifi.configure(text="  ".join(partes))

    def _caminhos(self) -> tuple[str, str, str, str]:
        """Fontes que vêm junto no repositório, e onde os binários vão parar."""
        fontes = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        daemon = os.path.join(fontes, "r1scrobbled.sh")
        saida_dir = os.path.join(self.cfg.trabalho, "scrobble")
        return fontes, daemon, saida_dir, os.path.join(saida_dir, "r1collect")

    def _zig_dir(self):
        """O Zig — instalando-o na hora se ainda não houver um.

        Roda dentro da thread de trabalho, então pode demorar à vontade. É a
        única dependência pesada do programa, e pedir para a pessoa baixar um
        toolchain à mão seria trocar um download automático e verificado por
        SHA256 por um passo manual que ninguém quer seguir.
        """
        from .. import zigsetup
        achado = zigsetup.find_installed(self.cfg.runner, self.log)
        if achado:
            return achado[0]
        if not self.cfg.runner.posix_available():
            raise InstallerError(t("err.linux.title"), t("err.linux.body"))

        self.log.step(t("zig.installing"))
        alvo = zigsetup.posix_target_key(self.cfg.runner, self.log)
        lancamentos = zigsetup.fetch_releases(alvo, self.log)
        if not lancamentos:
            raise InstallerError(t("err.zig.title"), t("err.zig.body", alvo=alvo))
        pasta, versao = zigsetup.install(
            self.cfg.runner, self.log, lancamentos[0], self.cfg.cache,
            progress=lambda d, tot: self.app.ui(
                lambda: self.progresso_ca.set(d, tot, t("zig.downloading"))),
            cancel=lambda: self.cfg.runner.cancelled)
        self.app.ui(lambda: self.progresso_ca.stop(
            t("zig.installed", versao=versao)))
        return pasta

    def _programa(self, nome: str, fonte: str, rotulo: str):
        """O binário do aparelho: o compilado aqui, o que veio junto, ou nada.

        Compilar exige Zig, e no Windows isso exige WSL — o que transforma
        "baixei e instalei" em "instale uma distribuição Linux primeiro" para
        quem só quer scrobblar. Por isso o repositório traz os dois programas
        já compilados para o MIPS do R1, em bin/.

        Um binário compilado nesta máquina tem preferência: quem mexeu no
        código quer o dele, não o que veio na caixa. E o que for usado passa
        pela mesma checagem de ELF de sempre — nada entra no aparelho sem ser
        conferido, tenha vindo de onde tiver vindo.
        """
        _fontes, _daemon, saida_dir, _col = self._caminhos()
        compilado = os.path.join(saida_dir, nome)
        if os.path.isfile(compilado):
            return compilado
        junto = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "bin", nome)
        if os.path.isfile(junto):
            CC.conferir(junto, self.log, rotulo=rotulo)
            return junto
        # Nem um nem outro: compila, que é o caminho de quem tem Zig.
        CC.compilar(self.cfg.runner, self.log,
                    os.path.join(_fontes, fonte), compilado,
                    zig_dir=self._zig_dir(), rotulo=rotulo)
        return compilado

    def _compilar(self) -> None:
        fontes, _daemon, saida_dir, _col = self._caminhos()
        runner, log = self.cfg.runner, self.log

        def work():
            return CC.compilar_tudo(runner, log, fontes, saida_dir,
                                    zig_dir=self._zig_dir())

        def done(feitos) -> None:
            linhas = [f"{nome}: {os.path.getsize(caminho):,} bytes"
                      for nome, caminho in feitos.items()]
            self.lbl_dispositivo.configure(
                text=t("build.done", lista="   ".join(linhas)))

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.build"))

    # -- envio pelo WiFi -----------------------------------------------------

    def _curl_mipsel(self) -> str:
        """O curl estático para o R1, se já tiver sido compilado."""
        candidatos = [
            self.cfg.curl_local,
            os.path.join(self.cfg.trabalho, "build-curl", "curl"),
        ]
        for p in candidatos:
            if p and os.path.isfile(p):
                return p
        raise InstallerError(
            t("curl.missing.title"),
            t("curl.missing.detail",
              onde="\n".join(f"  • {p}" for p in candidatos if p)))

    def _compilar_curl(self) -> None:
        """Compila o curl estático do R1 — a parte demorada, uma vez só.

        O binário fica no cache deste computador. Quem já tiver um curl mipsel
        estático de outro projeto pode simplesmente copiá-lo para o caminho
        que a mensagem de erro mostra, e pular esta etapa inteira.
        """
        if os.path.isfile(self.cfg.curl_local):
            if not W.confirm(self, t("curl.again.title"),
                             t("curl.again.body", caminho=self.cfg.curl_local),
                             ok_text=t("curl.again.ok")):
                return
        if not W.confirm(self, t("curl.warn.title"), t("curl.warn.body"),
                         ok_text=t("curl.warn.ok")):
            return

        from ..curlbuild import build_static_curl
        cfg, log = self.cfg, self.log
        cfg.criar_pastas()
        runner = cfg.runner

        def work():
            # O curl é compilado pelo mesmo Zig dos outros dois programas;
            # sem pôr a pasta dele no PATH do lado POSIX, o script do build
            # não acha o compilador e falha lá no fim.
            runner.posix_path_extra = self._zig_dir() or runner.posix_path_extra
            return build_static_curl(
                runner, log, cfg.cache, cfg.trabalho,
                on_line=lambda l: self.app.ui(
                    lambda: self.progresso_ca.set(0, 0, l[:70])),
                cancel=lambda: runner.cancelled)

        def done(res) -> None:
            if not res.ok:
                self.progresso_ca.stop(t("curl.failed.short"))
                detalhe = res.hint or ""
                if res.log_path:
                    detalhe += t("curl.failed.log", caminho=res.log_path)
                if res.script_path:
                    detalhe += t("curl.failed.script", caminho=res.script_path)
                W.show_error(
                    self,
                    t("curl.failed.stage",
                      etapa=res.stage or t("curl.failed.start")),
                    t("curl.failed.title"),
                    (detalhe + "\n\n" + res.log_tail).strip())
                return
            # Guardar em curl_local é o que faz _curl_mipsel() achar depois.
            destino = cfg.curl_local
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if res.artifact and os.path.abspath(res.artifact) != os.path.abspath(destino):
                import shutil
                shutil.copy2(res.artifact, destino)
            self.progresso_ca.stop(t("curl.ok.short"))
            self.lbl_wifi.configure(text=t("curl.ok.body", caminho=destino))

        def falhou(exc: InstallerError) -> None:
            self.progresso_ca.stop("")
            self._erro(exc)

        self.app.run_async(work, on_done=done, on_error=falhou,
                           busy_text=t("busy.curl"))

    def _alternar_agora(self) -> None:
        """Aplica a caixa no aparelho imediatamente."""
        ligado = bool(self.var_agora.get())
        adb = self._adb()
        if adb is None:
            self.var_agora.set(not ligado)
            return
        if ligado and not (self.situacao and self.situacao.envio_pronto):
            self.lbl_wifi.configure(text=t("now.needs_wifi"))
            self.var_agora.set(False)
            return
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.definir_agora(adb, log, ligado)
            return AP.situacao(adb)

        def done(sit) -> None:
            self.situacao = sit
            self._render_wifi(sit)
            if ligado:
                self.lbl_wifi.configure(
                    text=self.lbl_wifi.cget("text") + t("now.enabled"))

        def falhou(exc: InstallerError) -> None:
            self.var_agora.set(not ligado)
            self._erro(exc)

        self.app.run_async(work, on_done=done, on_error=falhou,
                           busy_text=t("busy.apply"))

    def _baixar_cacert(self) -> None:
        """Traz o cacert.pem do projeto curl e põe no aparelho.

        Sem ele o R1 não tem como conferir a identidade do servidor, e o envio
        automático fica adiado em vez de mandar a chave de sessão sem
        verificar com quem está falando.
        """
        adb = self._adb()
        if adb is None:
            return
        from ..curlbuild import CACERT_URL
        from ..net import download
        self.cfg.criar_pastas()
        destino = self.cfg.cacert_local
        log = self.log

        def work():
            download(CACERT_URL, destino, log=log, label="cacert.pem",
                     reuse_cache=True,
                     progress=lambda d, tot: self.app.ui(
                         lambda: self.progresso_ca.set(
                             d, tot, t("progress.downloading"))))
            adb.start_server()
            adb.require_device()
            AP.instalar_cacert(adb, log, destino)
            return AP.situacao(adb)

        def done(sit) -> None:
            self.progresso_ca.stop(t("cacert.installed"))
            self._render_wifi(sit)

        def falhou(exc: InstallerError) -> None:
            self.progresso_ca.stop("")
            self._erro(exc)

        self.app.run_async(work, on_done=done, on_error=falhou,
                           busy_text=t("busy.cacert"))

    def _ativar_wifi(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        chave = self._chave()
        if not chave:
            self.lbl_wifi.configure(text=t("wifi.need_account"))
            return
        fontes, _daemon, saida_dir, _col = self._caminhos()
        remetente = os.path.join(saida_dir, "r1send")
        runner, log = self.cfg.runner, self.log
        cacert = self.cfg.cacert_local or ""

        def work():
            adb.start_server()
            adb.require_device()
            remetente_usar = self._programa("r1send", "r1send.c", "r1send")

            # Sem certificados o envio ficaria adiado para sempre. Em vez de
            # instalar e deixar o usuário descobrir isso depois, o pacote é
            # buscado agora: sem ele o aparelho não sabe com quem fala.
            local_ca = cacert
            ja_tem = adb.shell(
                f"{{ [ -s {AP.CACERT_SD} ] || [ -s {AP.CACERT} ]; }} "
                f"&& echo SIM || echo NAO", mutating=False)
            if "SIM" not in ja_tem.stdout:
                from ..curlbuild import CACERT_URL
                from ..net import download
                self.cfg.criar_pastas()
                local_ca = self.cfg.cacert_local
                log.step(t("log.no_cacert_device"))
                download(CACERT_URL, local_ca, log=log, label="cacert.pem",
                         reuse_cache=True,
                         progress=lambda d, tot: self.app.ui(
                             lambda: self.progresso_ca.set(
                                 d, tot, t("progress.certificates"))))

            AP.instalar_envio(adb, log,
                              remetente_local=remetente_usar,
                              curl_local=self._curl_mipsel(),
                              cacert_local=local_ca,
                              session_key=chave,
                              api_key=self.cfg.api_key,
                              api_secret=self.cfg.api_secret)
            return AP.situacao(adb)

        def done(s) -> None:
            self._render_wifi(s)
            self.lbl_envio.configure(text=t("wifi.enabled"))

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.wifi.enable"))

    def _desativar_wifi(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        if not W.confirm(self, t("wifi.disable.title"), t("wifi.disable.body"),
                         ok_text=t("btn.wifi.disable")):
            return
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.desligar_envio(adb, log)
            return True

        self.app.run_async(work, on_done=lambda _v: self._ver_aparelho(),
                           on_error=self._erro,
                           busy_text=t("busy.wifi.disable"))

    def _enviar_no_aparelho(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            return AP.enviar_agora(adb, log)

        def done(saida) -> None:
            self.lbl_wifi.configure(
                text=t("wifi.test_result", saida=str(saida)[:400]))
            self._ver_aparelho()

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.wifi.test"))

    def _instalar(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        fontes, daemon, saida_dir, saida = self._caminhos()
        try:
            rapido = max(5, int(self.var_rapido.get()))
            lento = max(rapido, int(self.var_lento.get()))
        except ValueError:
            W.show_error(self, t("err.intervals.title"), t("err.intervals.body"))
            return
        runner, log = self.cfg.runner, self.log
        # Lido aqui, na thread da interface. Ler variável do Tk de dentro do
        # work() seria ler widget fora da thread principal.
        quer_agora = bool(self.var_agora.get())

        def work():
            adb.start_server()
            adb.require_device()
            coletor = self._programa("r1collect", "collector.c", "r1collect")
            # O remetente vai junto porque é ele quem escreve o
            # scrobbles.csv do cartão — nada a ver com WiFi. Ver o comentário
            # em aparelho.instalar.
            remetente = self._programa("r1send", "r1send.c", "r1send")
            AP.instalar(adb, log, coletor, daemon, rapido=rapido, lento=lento,
                        agora=quer_agora, iniciar_no_boot=True,
                        remetente_local=remetente)
            AP.iniciar_agora(adb, log)
            return AP.situacao(adb)

        def done(_s) -> None:
            self.lbl_envio.configure(text=t("install.done"))
            self._ver_aparelho()

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.install"))

    def _iniciar(self) -> None:
        """Sobe o coletor agora, sem reinstalar nada.

        Existe porque num firmware de fábrica ele não sobe sozinho: nada ali
        executa o /usr/data/init.sh. Com este botão a pessoa pluga o cabo,
        clica, e o coletor roda até o próximo desligamento.
        """
        adb = self._adb()
        if adb is None:
            return
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.iniciar_agora(adb, log)
            return AP.situacao(adb)

        self.app.run_async(work, on_done=lambda _s: self._ver_aparelho(),
                           on_error=self._erro,
                           busy_text=t("busy.iniciar"))

    def _remendar_firmware(self) -> None:
        """Gera um firmware com o gancho do init.sh, a partir do da pessoa.

        O trabalho pesado é do ferramentas/remendar_firmware.py, que é quem
        confere o resultado arquivo por arquivo. Aqui só se pergunta, se
        escolhe e se mostra — e se avisa antes, porque instalar firmware é a
        única coisa deste programa que não tem volta.
        """
        from tkinter import filedialog

        if not W.confirm(self, t("fw.title"), t("fw.body"),
                         ok_text=t("fw.ok"), danger=True):
            return

        entrada = filedialog.askopenfilename(
            parent=self, title=t("fw.pick"),
            filetypes=[("firmware (*.upt)", "*.upt"), ("*", "*")])
        if not entrada:
            return
        saida = filedialog.asksaveasfilename(
            parent=self, title=t("fw.save"), defaultextension=".upt",
            initialfile="r1-autostart.upt",
            filetypes=[("firmware (*.upt)", "*.upt")])
        if not saida:
            return
        # O gerador se recusa a sobrescrever; o seletor já perguntou, então o
        # que a pessoa respondeu ali é o que vale.
        if os.path.exists(saida):
            os.remove(saida)

        runner, log = self.cfg.runner, self.log
        # A ferramenta mora ao lado do pacote, não dentro dele.
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        script = os.path.join(raiz, "ferramentas", "remendar_firmware.py")
        if not os.path.isfile(script):
            W.show_error(self, t("fw.err.title"),
                         t("fw.err.run"), script)
            return

        def work():
            res = runner.posix(
                f"python3 {runner.to_posix_path(script)} "
                f"{runner.to_posix_path(entrada)} "
                f"{runner.to_posix_path(saida)}",
                mutating=True, timeout=1800)
            if not res.ok:
                saida_toda = (res.output or "")
                if "missing tools" in saida_toda:
                    raise InstallerError(t("fw.err.title"), t("fw.err.tools"))
                raise InstallerError(t("fw.err.title"),
                                     t("fw.err.run") + "\n\n" + saida_toda[-1500:])
            return saida

        def done(caminho) -> None:
            log.ok(t("fw.done.title"))
            W.show_error(self, t("fw.done.title"),
                         t("fw.done", caminho=caminho))

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("fw.busy"))

    def _remover(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        escolha = W.choose(
            self, t("remove.title"), t("remove.body"),
            [("guardar", t("remove.keep"), t("remove.keep.note")),
             ("apagar", t("remove.wipe"), t("remove.wipe.note"))])
        if not escolha:
            return
        apagar = escolha == "apagar"
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.desinstalar(adb, log, apagar_fila=apagar)
            return True

        self.app.run_async(work, on_done=lambda _v: self._ver_aparelho(),
                           on_error=self._erro,
                           busy_text=t("busy.remove"))

    # -- fila ----------------------------------------------------------------

    def _puxar(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        destino = os.path.join(self.cfg.trabalho, "scrobble", "fila.tsv")
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.puxar_fila(adb, log, destino)
            return AP.ler_enviados(adb)

        def done(enviados) -> None:
            self.enviados = set(enviados)
            self._reconstruir()

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.queue"))

    def _reconstruir(self) -> None:
        destino = os.path.join(self.cfg.trabalho, "scrobble", "fila.tsv")
        if not os.path.isfile(destino):
            return
        with open(destino, "rb") as fh:
            texto = fh.read().decode("utf-8", "replace")
        regs, ruins = FQ.ler(texto)
        rec = FQ.reconstruir(regs, ultima=self.var_ultima.get(),
                             ja_enviados=self.enviados)
        rec.linhas_invalidas = ruins
        self.rec = rec
        self.lbl_resumo.configure(text=FQ.resumo(rec))

        vai = t("state.will_send")
        self.tree.delete(*self.tree.get_children())
        for play in rec.execucoes:
            self.tree.insert("", "end", tags=("vai",), values=(
                _hhmm(play.timestamp), play.artist, play.track, play.album,
                _dur(play.listened) + "/" + _dur(play.duration), vai))
        for play, motivo in rec.descartadas:
            self.tree.insert("", "end", tags=("fica",), values=(
                _hhmm(play.timestamp), play.artist, play.track, play.album,
                _dur(play.listened) + "/" + _dur(play.duration), motivo))
        self._reavaliar_envio()

    def _reavaliar_envio(self) -> None:
        pronto = bool(self._chave()) and bool(self.rec and self.rec.execucoes)
        self.btn_enviar.configure(state="normal" if pronto else "disabled")

    # -- envio ---------------------------------------------------------------

    def _enviar(self) -> None:
        if not self.rec or not self.rec.execucoes:
            return
        adb = self._adb()
        cli = self._cliente()
        lista = list(self.rec.execucoes)
        log = self.log

        def work():
            # O callback roda na thread de trabalho, então tudo o que toca em
            # Tk tem de passar pelo app.ui.
            return send_all(cli, lista, progress=lambda d, tot: self.app.ui(
                lambda: self.progresso.set(
                    d, tot, t("send.progress", feito=d, total=tot))))

        def done(par) -> None:
            resultado, restantes = par
            partes = [t("send.accepted", n=resultado.accepted)]
            if resultado.ignored:
                partes.append(t("send.refused", n=len(resultado.ignored)))
                for play, motivo in resultado.ignored[:6]:
                    partes.append(t("send.refused.item", artista=play.artist,
                                    faixa=play.track, motivo=motivo))
                if len(resultado.ignored) > 6:
                    partes.append(t("send.refused.more",
                                    n=len(resultado.ignored) - 6))
            if restantes:
                partes.append(t("send.left", n=len(restantes)))
            self.lbl_envio.configure(text="\n".join(partes))
            log.ok(t("send.log", n=resultado.accepted))
            self._marcar(adb, resultado, restantes, lista)

        self.app.run_async(work, on_done=done, on_error=self._erro,
                           busy_text=t("busy.send"))

    def _marcar(self, adb, resultado: ScrobbleResult, restantes, lista) -> None:
        """Registra no aparelho o que foi aceito, para não reenviar depois."""
        if adb is None or not self.rec:
            return
        recusadas = {id(p) for p, _m in resultado.ignored}
        pendentes = {id(p) for p in restantes}
        horas_ok = {p.timestamp for p in lista
                    if id(p) not in recusadas and id(p) not in pendentes}
        # De volta ao rowid: a fila crua tem a hora de cada execução.
        destino = os.path.join(self.cfg.trabalho, "scrobble", "fila.tsv")
        try:
            with open(destino, "rb") as fh:
                regs, _ = FQ.ler(fh.read().decode("utf-8", "replace"))
        except OSError:
            return
        ids = {r.rowid for r in regs if r.tipo == "p1" and r.hora in horas_ok}
        if not ids:
            return
        log = self.log

        def work():
            AP.marcar_enviados(adb, log, ids)
            self.enviados |= ids
            return True

        self.app.run_async(work, on_done=lambda _v: self._reconstruir(),
                           on_error=self._erro,
                           busy_text=t("busy.mark"))

    def _enxugar(self) -> None:
        adb = self._adb()
        if adb is None:
            return
        if not self.enviados:
            self.lbl_envio.configure(text=t("trim.nothing"))
            return
        if not W.confirm(self, t("trim.title"),
                         t("trim.body", n=len(self.enviados)),
                         ok_text=t("trim.ok")):
            return
        enviados = set(self.enviados)
        log = self.log

        def work():
            adb.start_server()
            adb.require_device()
            AP.limpar_fila(adb, log, enviados)
            return True

        self.app.run_async(work, on_done=lambda _v: self._ver_aparelho(),
                           on_error=self._erro,
                           busy_text=t("busy.trim"))

    # -- erros ---------------------------------------------------------------

    def _erro(self, exc: InstallerError) -> None:
        W.show_error(self, t("win.error.title"), exc.message, exc.detail)
