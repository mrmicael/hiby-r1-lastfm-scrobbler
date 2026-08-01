#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrobbler do Last.fm para o HiBy R1.

    python r1lastfm.py              # a interface
    python r1lastfm.py --check      # só as verificações do ambiente
    python r1lastfm.py --dry-run    # abre em modo simulação: mostra os
                                    # comandos sem executar nenhum

Só usa a biblioteca padrão do Python. O adb é necessário; o Zig só faz falta
para quem quiser o envio automático pelo WiFi, e o programa o instala sozinho.
"""

from __future__ import annotations

import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Um console do Windows com codepage legada levanta UnicodeEncodeError num
# simples travessão, e mata o programa no meio do relatório. Trocar o
# caractere é sempre melhor do que abortar.
for _fluxo in (sys.stdout, sys.stderr):
    try:
        _fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

from r1lastfm import __version__
from r1lastfm.applog import default_log_path, init_log
from r1lastfm import idioma
from r1lastfm.config import montar
from r1lastfm.idioma import t
from r1lastfm.runner import InstallerError, Runner


def _sessao(dry_run: bool, lang: str = ""):
    from r1lastfm.config import pasta_de_dados
    base = pasta_de_dados()
    log = init_log(default_log_path(base))
    runner = Runner(log=log, dry_run=dry_run)
    cfg = montar(runner)
    runner.script_dir = os.path.join(cfg.trabalho, "scripts")
    # Ordem de precedência: a opção da linha de comando, o que foi escolhido
    # numa execução anterior, e por fim o idioma do sistema. Um --lang não
    # é gravado: serve para experimentar sem mudar a preferência.
    idioma.definir(lang or cfg.idioma or idioma.do_sistema())
    return cfg, log


def cmd_check(dry_run: bool, lang: str) -> int:
    cfg, log = _sessao(dry_run, lang)
    print(t("cli.check.header", versao=__version__) + "\n")
    checagens = cfg.ambiente.verificar()
    largura = max(len(c.rotulo) for c in checagens)
    simbolo = {"ok": t("check.ok"), "aviso": t("check.warn"),
               "falta": t("check.missing")}
    largo = max(len(v) for v in simbolo.values())
    simbolo = {k: v.ljust(largo) for k, v in simbolo.items()}
    faltando = 0
    for c in checagens:
        print(f"  [{simbolo.get(c.estado, '?')}] {c.rotulo.ljust(largura)}  "
              f"{c.detalhe}")
        if c.dica:
            for linha in c.dica.splitlines():
                print(f"          {linha}")
        if c.estado == "falta" and c.obrigatorio:
            faltando += 1
    print()
    print(t("cli.api.set") if cfg.tem_api else t("cli.api.unset"))
    print(t("cli.log_at", caminho=log.path))
    return 1 if faltando else 0


def cmd_gui(dry_run: bool, lang: str) -> int:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        # Antes de qualquer config: sem Tk não há janela para explicar nada.
        idioma.definir(lang or idioma.do_sistema())
        print(t("cli.no_tk"))
        return 2

    cfg, log = _sessao(dry_run, lang)
    from r1lastfm.gui.app import App
    from r1lastfm.gui.janela import Painel

    log.step(t("cli.version_line", versao=__version__))
    if dry_run:
        log.warn(t("cli.dry_warn"))
    cfg.ambiente.verificar()

    def construir(app) -> None:
        Painel(app.area, cfg, app).pack(fill="both", expand=True)

    app = App(cfg, log, construir=construir)
    try:
        app.mainloop()
    finally:
        log.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    # O parser é montado antes de qualquer config existir, então os textos de
    # ajuda saem no idioma do sistema. Depois disso vale o que foi escolhido.
    idioma.definir(idioma.do_sistema())
    parser = argparse.ArgumentParser(prog="r1lastfm", description=t("cli.desc"))
    parser.add_argument("--check", action="store_true", help=t("cli.check.help"))
    parser.add_argument("--dry-run", action="store_true", help=t("cli.dry.help"))
    parser.add_argument("--lang", default="", choices=sorted(idioma.IDIOMAS),
                        help=t("cli.lang.help"))
    parser.add_argument("--version", action="version",
                        version=f"r1lastfm {__version__}")
    args = parser.parse_args(argv)

    try:
        if args.check:
            return cmd_check(args.dry_run, args.lang)
        return cmd_gui(args.dry_run, args.lang)
    except KeyboardInterrupt:
        print(t("cli.interrupted"))
        return 130
    except InstallerError as exc:
        print(t("cli.error", mensagem=exc.message))
        if exc.detail:
            print(exc.detail)
        return 1


if __name__ == "__main__":
    sys.exit(main())
