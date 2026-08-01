# -*- coding: utf-8 -*-
"""O que todos os testes precisam: a raiz do projeto e os binarios do PC.

Os dois programas do aparelho (collector.c e r1send.c) sao C portatil, sem
nada de especifico do MIPS. Compilar para o PC e roda-los aqui e o que
permite testar a leitura do banco e a assinatura do lote sem depender de ter
um R1 na mesa — e sem depender do Zig, que so faz falta para o alvo real.
"""
from __future__ import annotations

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = os.path.join(RAIZ, "r1lastfm")
TRABALHO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lastfm")
os.makedirs(TRABALHO, exist_ok=True)

if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


# Codigo de saida que o t_scrobble_all.py entende como "pulado", nao "passou".
# Um teste que nao rodou nao pode aparecer verde no resumo.
PULADO = 3


def achar_compilador(runner) -> str:
    """O primeiro compilador C utilizavel do ambiente POSIX.

    O Zig entra na lista porque o proprio programa o instala para gerar os
    binarios do R1 — se ele ja esta ai, serve tambem para compilar para o PC,
    e uma dependencia a menos para quem so quer rodar os testes.
    """
    forcado = os.environ.get("R1_CC", "").strip()
    if forcado:
        return forcado
    from r1lastfm import zigsetup
    achado = zigsetup.find_installed(runner)
    candidatos = ["cc", "gcc", "clang"]
    for c in candidatos:
        res = runner.posix(f"command -v {c}", mutating=False, quiet=True)
        if res.ok and res.stdout.strip():
            return c
    if achado:
        return f"{achado[0]}/zig cc"
    res = runner.posix("command -v zig", mutating=False, quiet=True)
    if res.ok and res.stdout.strip():
        return "zig cc"
    return ""


def compilar_para_o_pc(runner, nome: str) -> str:
    """Compila collector.c ou r1send.c para rodar neste PC.

    Devolve o caminho Windows do binario. Recompila se a fonte for mais nova,
    porque um binario velho passando num teste e pior do que nenhum.
    """
    fonte = {"r1collect": "collector.c", "r1send": "r1send.c"}[nome]
    fonte_win = os.path.join(FONTES, fonte)
    saida_win = os.path.join(TRABALHO, nome)

    if (os.path.isfile(saida_win)
            and os.path.getmtime(saida_win) >= os.path.getmtime(fonte_win)):
        return saida_win

    cc = achar_compilador(runner)
    if not cc:
        print("PULADO: nao ha compilador C no ambiente POSIX.\n"
              "  Dentro do WSL:  sudo apt install -y build-essential\n"
              "  Ou deixe o proprio programa instalar o Zig (botao de "
              "compilar na interface).")
        raise SystemExit(PULADO)

    cmd = (f"{cc} -O1 -Wall -Wextra -o {runner.to_posix_path(saida_win)} "
           f"{runner.to_posix_path(fonte_win)}")
    res = runner.posix(cmd, mutating=True, quiet=True, timeout=600)
    if not res.ok or not os.path.isfile(saida_win):
        raise SystemExit(
            f"nao consegui compilar {fonte} para este PC com '{cc}':\n"
            + (res.output or "")[-1500:])
    return saida_win
