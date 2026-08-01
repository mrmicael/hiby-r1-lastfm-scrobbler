"""A janela principal e a máquina de trabalho em segundo plano.

Tudo que fala com o aparelho, com a rede ou com o compilador demora — de
segundos a meia hora. Nada disso pode acontecer na thread da interface, ou a
janela congela e a única leitura honesta da tela passa a ser "travou".

Então há uma regra só, e ela vale sem exceção: **o trabalho roda numa thread,
e nenhum widget é tocado de lá**. Quem precisa mexer na tela de dentro do
trabalho passa por ``app.ui(...)``, que agenda a mudança na thread certa.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ..applog import ERROR, Log
from ..config import Config
from ..idioma import IDIOMAS, atual, definir, t
from ..runner import Cancelled, InstallerError
from . import widgets as W


class App(tk.Tk):
    def __init__(self, cfg: Config, log: Log,
                 construir: Optional[Callable[["App"], None]] = None):
        super().__init__()
        self.cfg = cfg
        self.log = log
        # Quem sabe montar o conteúdo. Guardado porque trocar de idioma
        # remonta tudo: ver _trocar_idioma.
        self.construir = construir
        self._busy = False
        self._busy_text = ""
        self._busy_desde = 0.0
        self._fila: queue.Queue = queue.Queue()

        self.title(t("win.title"))
        self.geometry("1000x860")
        self.minsize(820, 600)
        self.configure(bg=W.COL_BG)
        W.apply_theme(self)

        corpo = ttk.Frame(self, style="TFrame")
        corpo.pack(fill="both", expand=True)

        self.area = ttk.Frame(corpo, style="TFrame")
        self.area.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        self.rodape = ttk.Frame(corpo, style="TFrame")
        self.rodape.pack(fill="x", padx=16, pady=(0, 10))
        self._montar_rodape()

        self.logpane = W.LogPane(corpo, height=8)
        self.logpane.pack(fill="both", expand=False, padx=16, pady=(0, 12))
        self.log.add_sink(
            lambda nivel, msg: self.ui(lambda: self.logpane.write(nivel, msg)))

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(80, self._drenar)
        if self.construir:
            self.construir(self)

    # -- rodapé e idioma ------------------------------------------------------

    def _montar_rodape(self) -> None:
        """A barra de baixo: estado, interromper, registro e idioma."""
        self.status = ttk.Label(self.rodape, text="", style="Muted.TLabel")
        self.status.pack(side="left")
        self.btn_cancelar = ttk.Button(self.rodape, text=t("win.stop"),
                                       command=self.cancelar)
        self.btn_ver_registro = ttk.Button(
            self.rodape, text=t("win.open_log"),
            command=lambda: W.reveal(self.log.path))
        self.btn_ver_registro.pack(side="right")
        self._montar_idioma(self.rodape)

    def _montar_idioma(self, rodape) -> None:
        """O seletor de idioma, no rodapé.

        Trocar de idioma remonta a janela inteira. Poderia-se guardar cada
        widget e reescrever o texto de cada um, mas isso é uma lista que
        envelhece: acrescente um rótulo novo, esqueça de registrá-lo, e ele
        fica em inglês para sempre sem ninguém notar. Reconstruir não tem esse
        problema — o que aparece é sempre o que o código monta agora.
        """
        quadro = ttk.Frame(rodape, style="TFrame")
        quadro.pack(side="right", padx=(0, 12))
        ttk.Label(quadro, text=t("win.language"), style="Muted.TLabel").pack(
            side="left", padx=(0, 6))
        self.var_idioma = tk.StringVar(value=IDIOMAS[atual()])
        caixa = ttk.Combobox(quadro, textvariable=self.var_idioma,
                             values=list(IDIOMAS.values()), state="readonly",
                             width=18)
        caixa.pack(side="left")
        caixa.bind("<<ComboboxSelected>>", self._trocar_idioma)

    def _trocar_idioma(self, _evento=None) -> None:
        escolhido = self.var_idioma.get()
        codigo = next((c for c, nome in IDIOMAS.items() if nome == escolhido),
                      atual())
        if codigo == atual():
            return
        if self._busy:
            # Remontar a janela no meio de um trabalho mataria os rótulos que
            # a thread ainda vai atualizar. Melhor recusar do que quebrar.
            self.var_idioma.set(IDIOMAS[atual()])
            return
        definir(codigo)
        self.cfg.gravar(idioma=codigo)
        self._remontar()

    def _remontar(self) -> None:
        """Reconstrói a janela inteira no idioma novo."""
        for filho in list(self.area.winfo_children()):
            filho.destroy()
        # O rodapé tem os botões e o próprio seletor; refazê-lo é o que
        # traduz "Interromper" e "Abrir o registro".
        for filho in list(self.rodape.winfo_children()):
            filho.destroy()
        self._montar_rodape()
        self.title(t("win.title"))
        if self.construir:
            self.construir(self)

    # -- trabalho em segundo plano -------------------------------------------

    @property
    def ocupado(self) -> bool:
        return self._busy

    def run_async(self, work: Callable[[], object], *,
                  on_done: Optional[Callable[[object], None]] = None,
                  on_error: Optional[Callable[[InstallerError], None]] = None,
                  on_cancel: Optional[Callable[[], None]] = None,
                  allow_cancel: bool = True,
                  busy_text: str = "") -> None:
        if self._busy:
            return
        self._busy = True
        busy_text = busy_text or t("win.working")
        self.cfg.runner.clear_cancel()
        self._busy_text = busy_text
        self._busy_desde = time.time()
        self.status.configure(text=busy_text)
        self._tique()
        if allow_cancel:
            self.btn_cancelar.pack(side="right", padx=(0, 8))

        def alvo() -> None:
            try:
                valor = work()
                self._fila.put(("done", valor, on_done))
            except Cancelled:
                self._fila.put(("cancel", None, on_cancel))
            except InstallerError as exc:
                self._fila.put(("error", exc, on_error))
            except Exception as exc:
                # Um traceback cru na tela não ajuda ninguém, e some quando a
                # janela fecha. Ele vai para o registro, e o usuário recebe
                # uma mensagem com o arquivo onde procurar.
                detalhe = traceback.format_exc()
                self.log.write(ERROR, t("win.unexpected.log", erro=exc))
                self.log.raw(detalhe)
                self._fila.put(("error", InstallerError(
                    t("win.unexpected.title"),
                    t("win.unexpected.detail", erro=exc, traco=detalhe)),
                    on_error))

        threading.Thread(target=alvo, daemon=True).start()

    def _tique(self) -> None:
        """Mostra o tempo correndo enquanto trabalha.

        Compilar o curl leva meia hora em silêncio. Sem um número se movendo,
        a tela parada é indistinguível de um programa travado.
        """
        if not self._busy:
            return
        seg = int(time.time() - self._busy_desde)
        relogio = f"{seg // 60}:{seg % 60:02d}" if seg >= 60 else f"{seg}s"
        self.status.configure(text=f"{self._busy_text}   [{relogio}]")
        self.after(1000, self._tique)

    def cancelar(self) -> None:
        if self._busy:
            self.log.warn(t("win.stopping"))
            self.cfg.runner.request_cancel()

    def _terminou(self) -> None:
        self._busy = False
        self.btn_cancelar.pack_forget()
        self.status.configure(text="")

    def _drenar(self) -> None:
        try:
            while True:
                tipo, carga, tratador = self._fila.get_nowait()
                self._terminou()
                if tipo == "done" and tratador:
                    tratador(carga)
                elif tipo == "error":
                    if tratador:
                        tratador(carga)
                    else:
                        W.show_error(self, t("win.error.title"),
                                     carga.message, carga.detail)
                elif tipo == "cancel" and tratador:
                    tratador()
        except queue.Empty:
            pass
        self.after(80, self._drenar)

    def ui(self, fn: Callable[[], None]) -> None:
        """Agenda uma mudança de tela vinda da thread de trabalho."""
        try:
            self.after(0, fn)
        except RuntimeError:
            pass

    def _fechar(self) -> None:
        if self._busy:
            if not W.confirm(self, t("win.quit.title"), t("win.quit.body"),
                             ok_text=t("win.quit.ok"), danger=True):
                return
        self.log.close()
        self.destroy()
