"""Compila os dois programas do aparelho com o Zig, e confere o que saiu.

O R1 é um MIPS32 little-endian rodando busybox sobre um rootfs somente-leitura.
Nada do que existe pronto para baixar serve: o binário tem de ser estático,
o32, e da arquitetura certa. O Zig faz a compilação cruzada sem precisar de um
toolchain instalado.

A verificação do resultado é a parte que vale: um ELF com o ABI errado só
falha quando chega no aparelho, e lá a mensagem é um críptico
"cannot execute binary file".
"""

from __future__ import annotations

import os
import shlex
from typing import Optional

from .applog import Log
from .idioma import t
from .elfcheck import check_curl
from .runner import InstallerError, Runner

# O que o próprio busybox do R1 traz nos cabeçalhos ELF. Um binário nosso tem
# de bater com isto, ou o kernel recusa.
FLAGS_ESPERADAS = 0x70001005

# O Zig renomeia sufixos de ABI entre versões, e "mipsel-linux-musl" (sem
# sufixo) não existe no 0.16 — ele responde:
#
#   error: unable to provide libc for target 'mipsel-linux...-musl'
#   info: zig can provide libc for related target mipsel-linux...-musleabi
#   info: zig can provide libc for related target mipsel-linux...-musleabihf
#
# Ponto flutuante em hardware vem primeiro: o R1 tem FPU, e outros mods que
# compilam para mipsel-linux-gnueabihf rodam nele sem problema. Software é uma reserva boa: um binário totalmente estático é
# coerente consigo mesmo de qualquer jeito.
MIPSEL_CANDIDATOS = (
    "mipsel-linux-musleabihf",
    "mipsel-linux-musleabi",
    "mipsel-linux-musl",
)

# O programa de teste PRECISA incluir um cabeçalho da libc e PRECISA ligar.
# Compilar `int main(void){return 0;}` não usa cabeçalho nenhum, então passa
# para um alvo cuja libc o Zig não sabe servir — foi assim que
# mipsel-linux-musl chegou a ser escolhido, só para falhar centenas de
# arquivos adiante com "'string.h' file not found".
_PROGRAMA_DE_TESTE = r"""#include <string.h>
#include <stdlib.h>
int main(void) {
    char *p = malloc(8);
    if (!p) return 1;
    memset(p, 0, 8);
    free(p);
    return 0;
}
"""


def zig_disponivel(runner: Runner) -> bool:
    res = runner.posix("command -v zig >/dev/null 2>&1 && zig version",
                       mutating=False, quiet=True)
    return res.ok and bool(res.stdout.strip())


def zig_versao(runner: Runner) -> str:
    res = runner.posix("zig version", mutating=False, quiet=True)
    return res.stdout.strip() if res.ok else ""


def alvo_serve(runner: Runner, triple: str, log: Optional[Log] = None) -> bool:
    """Este Zig consegue gerar um estático que usa a libc para este alvo?

    Resolvido compilando um, não lendo `zig targets` — essa saída é JSON em
    algumas versões e ZON no 0.16, e interpretá-la seria perseguir um formato
    entre versões.
    """
    script = (
        'set -e\n'
        'd=$(mktemp -d)\n'
        'trap \'rm -rf "$d"\' EXIT\n'
        "cat > \"$d/t.c\" <<'FIM_DO_TESTE'\n"
        f"{_PROGRAMA_DE_TESTE}"
        "FIM_DO_TESTE\n"
        f'zig cc -target {shlex.quote(triple)} -static "$d/t.c" -o "$d/t.bin"\n'
        '[ -s "$d/t.bin" ]\n'
        'echo ALVO_OK\n'
    )
    res = runner.posix_script(script, name="zig-alvo", mutating=False,
                              quiet=True, timeout=600)
    ok = res.ok and "ALVO_OK" in res.stdout
    if not ok and log:
        # O zig nomeia os alvos que ele consegue servir; é a parte útil.
        for linha in res.output.splitlines():
            if "can provide libc for related target" in linha or "error:" in linha:
                log.info(f"    {linha.strip()[:150]}")
    return ok


def escolher_alvo(runner: Runner, log: Log) -> str:
    """O triple mipsel/musl que este Zig aceita."""
    log.info(t("cc.finding_target"))
    for cand in MIPSEL_CANDIDATOS:
        if alvo_serve(runner, cand, log):
            log.ok(t("cc.target_ok", alvo=cand))
            return cand
        log.info(t("cc.target_no", alvo=cand))
    raise InstallerError(
        t("cc.err.notarget.title"),
        t("cc.err.notarget.body",
          alvos="\n".join(f"    {c}" for c in MIPSEL_CANDIDATOS)))


def e_flags(caminho: str) -> int | None:
    """e_flags do cabeçalho ELF (offset 36 num ELF32 little-endian).

    O elfcheck não expõe este campo, e ele é justamente o que distingue o ABI
    o32/mips32r2 do R1 de outras variantes de MIPS.
    """
    try:
        with open(caminho, "rb") as fh:
            cab = fh.read(40)
    except OSError:
        return None
    if len(cab) < 40 or cab[:4] != b"\x7fELF":
        return None
    if cab[4] != 1 or cab[5] != 1:      # ELF32, little-endian
        return None
    return int.from_bytes(cab[36:40], "little")


def conferir(caminho: str, log: Log, rotulo: str = "Programa") -> None:
    """O binário serve mesmo para este aparelho?

    A conferência é a do módulo elfcheck, não uma cópia dela. Escrever de novo
    aqui já custou um bug: a comparação era com "little" quando o campo vale
    "little-endian", e todo binário correto era recusado com a mensagem
    absurda "little-endian-endian".
    """
    elf = check_curl(caminho)   # mesmo requisito: programa estático de MIPS

    flags = e_flags(caminho)
    if flags is not None and flags != FLAGS_ESPERADAS:
        # Aviso, não erro: um flag diferente pode ainda rodar, e recusar por
        # isso seria pior do que deixar passar com o alerta.
        log.warn(t("cc.flags_warn", tem=f"0x{flags:08x}",
                   esperado=f"0x{FLAGS_ESPERADAS:08x}"))

    if elf.problems:
        raise InstallerError(
            t("cc.err.badelf"),
            "\n".join("• " + p for p in elf.problems))

    # O separador de milhar vira ponto só no número; aplicar o replace na
    # frase inteira trocaria também as vírgulas que separam os campos.
    tam = f"{os.path.getsize(caminho):,}".replace(",", ".")
    log.ok(t("cc.ready", rotulo=rotulo, tam=tam, bits=elf.bits,
               endian=elf.endian, maquina=elf.machine_name))


def compilar(runner: Runner, log: Log, fonte: str, saida: str, *,
             zig_dir: str = "", rotulo: str = "coletor") -> str:
    """Gera um dos programas do aparelho, estático para mipsel."""
    if not os.path.isfile(fonte):
        raise InstallerError(
            t("cc.err.nosource", arquivo=os.path.basename(fonte)), fonte)
    os.makedirs(os.path.dirname(saida) or ".", exist_ok=True)

    antes = runner.posix_path_extra
    if zig_dir:
        runner.posix_path_extra = zig_dir
    try:
        alvo = escolher_alvo(runner, log)
        log.step(t("cc.building", rotulo=rotulo, alvo=alvo))
        # -Os porque o programa passa a vida parado; o que importa é ele ser
        # pequeno na memória de um aparelho com 56 MB.
        cmd = (f"zig cc -target {alvo} -Os -static -Wall -Wextra "
               f"-o {runner.to_posix_path(saida)} {runner.to_posix_path(fonte)}")
        res = runner.posix(cmd, mutating=True)
        if not res.ok:
            raise InstallerError(
                t("cc.err.failed.title", rotulo=rotulo),
                t("cc.err.failed.body",
                  saida=(res.output or "").strip()[:1500]))
    finally:
        runner.posix_path_extra = antes

    if not os.path.isfile(saida):
        raise InstallerError(t("cc.err.nooutput"), saida)
    conferir(saida, log, rotulo=rotulo)
    return saida


def compilar_tudo(runner: Runner, log: Log, base_fontes: str, dir_saida: str,
                  *, zig_dir: str = "") -> dict:
    """Os dois programas do aparelho: o que anota e o que manda."""
    out = {}
    for nome, fonte, rotulo in (
            ("r1collect", "collector.c", "coletor"),
            ("r1send", "r1send.c", "remetente")):
        out[nome] = compilar(
            runner, log,
            os.path.join(base_fontes, fonte),
            os.path.join(dir_saida, nome),
            zig_dir=zig_dir, rotulo=rotulo)
    return out
