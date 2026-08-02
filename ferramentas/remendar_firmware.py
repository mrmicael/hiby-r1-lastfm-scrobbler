#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adds the auto-start hook to a stock HiBy R1 firmware package.

Why this exists
---------------
Nothing in the stock R1 firmware ever runs `/usr/data/init.sh`. That was
checked against the real 1.6 package, not guessed: its `/usr/bin/hiby_player.sh`
is fourteen lines long and does not contain the string `/usr/data` anywhere,
and no other script, init file or binary in that image executes anything from
writable storage. `/` is mounted `squashfs (ro)`, so it cannot be patched while
the player is running either.

So on stock firmware the collector installs fine and works fine — it just never
comes up by itself after a reboot. The `init.sh` convention everyone builds on
was introduced by *modded* firmwares, which ship a patched `hiby_player.sh`.

This script makes that patch out of **your own** firmware file. It takes the
stock `r1.upt`, adds one line to `hiby_player.sh`, and writes a new `.upt` you
can flash from the player's own update menu. After that the collector — and
anything else that uses `init.sh` — starts on every boot, with no PC involved.

No HiBy firmware is redistributed here. You supply the package; this only
edits it.

What it changes
---------------
Exactly one file, and inside it exactly one line:

    USER_INIT="/usr/data/init.sh"
    [ -f "$USER_INIT" ] && sh "$USER_INIT" >/dev/null 2>&1 &

inserted right before the player is launched. Everything else in the image is
copied through untouched, and the script proves that at the end by unpacking
its own output and diffing it against the input.

Requirements
------------
Linux tools: `unsquashfs`/`mksquashfs` (squashfs-tools), `genisoimage` (or
`mkisofs`), and `7z` or `bsdtar` to read the ISO. On Windows run this inside
WSL. On Debian/Ubuntu:

    sudo apt install squashfs-tools genisoimage p7zip-full

Usage
-----
    python3 remendar_firmware.py r1.upt r1-autostart.upt

Then copy the output to the root of the SD card and use the player's firmware
update menu.

**Flashing firmware carries risk and is not reversible from software.** Keep
the stock `r1.upt` so you can go back, and do not do it on a low battery.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# DESATIVADO — o pacote que este script gera NÃO INSTALA.
#
# Foi publicado, alguém instalou, e o aparelho ficou preso na tela "Upgrading…"
# indefinidamente. Recuperar exigiu tirar o cartão, pôr o firmware bom nele e
# ligar segurando power + volume acima. Ninguém perdeu o aparelho, mas foi por
# pouco, e foi por minha causa.
#
# O que eu conferia — a cadeia de md5 dos pedaços, o conteúdo do squashfs, as
# permissões, a sintaxe do lançador — estava certo e continua certo. O erro
# está em outro lugar: alguma coisa na forma do pacote ISO em si, que eu nunca
# comparei com a do original. Verificar o recheio e não a embalagem foi
# exatamente o tipo de conferência que dá confiança sem dar garantia.
#
# Fica travado até eu achar a diferença e instalar um pacote gerado por ele
# num aparelho de verdade. "Compilou e passou nas minhas conferências" não é o
# padrão para uma coisa que pode deixar alguém sem player.
DESATIVADO = (
    "This script is disabled.\n\n"
    "The package it produced does not install: a device that tried it sat on\n"
    "the \"Upgrading...\" screen forever and had to be recovered by putting a\n"
    "known-good firmware on the card and powering on with power + volume-up.\n"
    "Nobody lost a player, but only because that recovery exists.\n\n"
    "The md5 chain, the squashfs contents, the permissions and the launcher\n"
    "syntax were all verified and were all correct. The problem is somewhere\n"
    "in the shape of the ISO container itself, which I never compared against\n"
    "the original — I checked what was inside the package and not the package.\n\n"
    "It stays disabled until that is found AND a package it generates has\n"
    "been installed on a real device.\n\n"
    "Meanwhile, to get the collector running after a reboot, use \"Start now\"\n"
    "in the app, or:\n"
    "  adb shell \"setsid /usr/data/scrobble/r1scrobbled </dev/null "
    ">/dev/null 2>&1 &\"\n"
)

PEDACO = 512 * 1024          # o pacote de fábrica usa pedaços de 512 KB
MARCA = "# --- r1lastfm auto-start hook ---"
MARCA_FIM = "# --- end of r1lastfm auto-start hook ---"

# A linha que faz o firmware executar o /usr/data/init.sh. É a mesma coisa que
# os firmwares modificados já fazem; nada aqui é novidade, só não vem de
# fábrica.
GANCHO = f"""{MARCA}
# Runs whatever the user put in /usr/data/init.sh, in the background, before
# the player starts. This is the hook the stock firmware does not have.
USER_INIT="/usr/data/init.sh"
[ -f "$USER_INIT" ] && sh "$USER_INIT" >/dev/null 2>&1 &
{MARCA_FIM}
"""


class Erro(Exception):
    pass


def rodar(*args: str, entrada: bytes | None = None) -> str:
    """Executa e devolve a saída, com o erro legível se falhar."""
    r = subprocess.run(args, input=entrada, capture_output=True)
    if r.returncode != 0:
        raise Erro(f"{args[0]} failed ({r.returncode}):\n"
                   + (r.stderr or b"").decode("utf-8", "replace")[-1500:])
    return (r.stdout or b"").decode("utf-8", "replace")


def existe(prog: str) -> bool:
    return shutil.which(prog) is not None


def md5(caminho: str) -> str:
    h = hashlib.md5()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def md5_bytes(dados: bytes) -> str:
    return hashlib.md5(dados).hexdigest()


def conferir_ferramentas() -> tuple[str, str]:
    """Devolve (leitor de ISO, gerador de ISO), ou explica o que falta."""
    leitor = "7z" if existe("7z") else ("bsdtar" if existe("bsdtar") else "")
    gerador = ("genisoimage" if existe("genisoimage")
               else ("mkisofs" if existe("mkisofs") else ""))
    faltando = []
    if not leitor:
        faltando.append("7z (p7zip-full) or bsdtar (libarchive-tools)")
    if not gerador:
        faltando.append("genisoimage or mkisofs (genisoimage)")
    for p in ("unsquashfs", "mksquashfs"):
        if not existe(p):
            faltando.append(f"{p} (squashfs-tools)")
    if faltando:
        raise Erro("missing tools:\n  " + "\n  ".join(faltando)
                   + "\n\nOn Debian/Ubuntu:\n"
                     "  sudo apt install squashfs-tools genisoimage p7zip-full")
    return leitor, gerador


def ler_iso(upt: str, destino: str, leitor: str) -> None:
    os.makedirs(destino, exist_ok=True)
    if leitor == "7z":
        rodar("7z", "x", "-y", f"-o{destino}", upt)
    else:
        rodar("bsdtar", "-xf", upt, "-C", destino)


def juntar(dir_ota: str, base: str) -> tuple[str, list[str]]:
    """Concatena os pedaços de `base` na ordem e devolve o arquivo montado."""
    nomes = sorted((n for n in os.listdir(dir_ota) if n.startswith(base + ".")),
                   key=lambda n: int(n.split(".")[-2]))
    if not nomes:
        raise Erro(f"no {base}.* chunks inside the package")
    saida = os.path.join(os.path.dirname(dir_ota), base)
    with open(saida, "wb") as out:
        for n in nomes:
            with open(os.path.join(dir_ota, n), "rb") as fh:
                shutil.copyfileobj(fh, out)
    return saida, nomes


def partir(caminho: str, dir_ota: str, base: str) -> None:
    """Reparte em pedaços de 512 KB com a cadeia de md5 que o pacote usa.

    O nome de cada pedaço carrega um md5, e não é o dele mesmo:

      • o pedaço 0000 leva o md5 do arquivo INTEIRO;
      • o pedaço N leva o md5 do pedaço N-1.

    É uma corrente de conferência — descobri isso comparando os nomes do
    pacote de fábrica com os md5 calculados, e um pacote que não a respeite
    é recusado pelo aparelho.
    """
    inteiro = md5(caminho)
    anterior = inteiro
    with open(caminho, "rb") as fh:
        i = 0
        while True:
            bloco = fh.read(PEDACO)
            if not bloco:
                break
            nome = f"{base}.{i:04d}.{anterior}"
            with open(os.path.join(dir_ota, nome), "wb") as out:
                out.write(bloco)
            anterior = md5_bytes(bloco)
            i += 1
    if i == 0:
        raise Erro(f"{base} came out empty")


def remendar_lancador(raiz: str) -> str:
    """Põe o gancho no hiby_player.sh. Devolve o que foi feito, em texto."""
    alvo = os.path.join(raiz, "usr", "bin", "hiby_player.sh")
    if not os.path.isfile(alvo):
        raise Erro("this package has no /usr/bin/hiby_player.sh — is it an R1 "
                   "firmware?")
    with open(alvo, encoding="utf-8", errors="surrogateescape") as fh:
        texto = fh.read()

    if "/usr/data/init.sh" in texto:
        return "already patched: it already runs /usr/data/init.sh"

    # Antes da linha que sobe o player, para que o init.sh já tenha rodado
    # quando a interface aparecer.
    linhas = texto.splitlines(keepends=True)
    corte = None
    for i, l in enumerate(linhas):
        if "/usr/bin/hiby_player" in l and not l.lstrip().startswith("#"):
            corte = i
            break
    if corte is None:
        # Nenhuma linha reconhecível: põe no fim, que ainda funciona porque o
        # script não termina antes de o player subir.
        corte = len(linhas)
    linhas.insert(corte, GANCHO)
    modo = os.stat(alvo).st_mode & 0o7777
    with open(alvo, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write("".join(linhas))
    # O modo tem de ser o mesmo de antes, e explicitamente: reescrever o
    # arquivo passa pelo umask do sistema, e num umask 002 ele sai 775 em vez
    # de 755. Parece inofensivo e não é — é o lançador do player, e ele vai
    # para um rootfs onde nada disso pode variar.
    os.chmod(alvo, modo)
    return (f"hook inserted at line {corte + 1} of usr/bin/hiby_player.sh "
            f"(mode kept at {modo & 0o777:o})")


def conferir_saida(upt: str, raiz_original: str, leitor: str,
                   trabalho: str) -> None:
    """Desempacota o que acabou de ser gerado e compara com a entrada.

    Um pacote de firmware é a única coisa aqui que pode inutilizar o aparelho,
    então ele não sai daqui sem ser aberto de novo e conferido arquivo por
    arquivo. O que se espera é uma diferença só: o hiby_player.sh.
    """
    conf = os.path.join(trabalho, "conferencia")
    ler_iso(upt, conf, leitor)
    montado, _ = juntar(os.path.join(conf, "ota_v0"), "rootfs.squashfs")
    raiz2 = os.path.join(trabalho, "raiz_conferencia")
    rodar("unsquashfs", "-n", "-f", "-d", raiz2, montado)

    diferentes: list[str] = []
    for base, _dirs, arqs in os.walk(raiz_original):
        for a in arqs:
            p1 = os.path.join(base, a)
            rel = os.path.relpath(p1, raiz_original)
            p2 = os.path.join(raiz2, rel)
            # `lexists` e não `exists`: um rootfs tem links apontando para
            # coisas que só existem com o sistema no ar (/etc/resolv.conf,
            # /dev/stdout, /etc/mtab). Seguir o link diria "sumiu" para todos
            # eles e a conferência acusaria um estrago que não houve.
            if os.path.islink(p1) or os.path.islink(p2):
                if not os.path.islink(p2):
                    diferentes.append(rel + " (symlink became a file)")
                elif os.readlink(p1) != os.readlink(p2):
                    diferentes.append(rel + " (symlink target changed)")
            elif not os.path.lexists(p2):
                diferentes.append(rel + " (missing in output)")
            elif (os.stat(p1).st_mode & 0o7777) != (os.stat(p2).st_mode & 0o7777):
                # Permissão conta tanto quanto conteúdo: um binário que perde
                # o bit de execução é um aparelho que não liga, e a diferença
                # não aparece em nenhum md5.
                diferentes.append(
                    f"{rel} (mode {os.stat(p1).st_mode & 0o777:o} -> "
                    f"{os.stat(p2).st_mode & 0o777:o})")
            elif os.path.getsize(p1) != os.path.getsize(p2) or \
                    md5(p1) != md5(p2):
                diferentes.append(rel)

    esperado = os.path.join("usr", "bin", "hiby_player.sh")
    inesperados = [d for d in diferentes if d != esperado]
    if inesperados:
        raise Erro("the rebuilt image differs in files it should not:\n  "
                   + "\n  ".join(inesperados[:20]))
    if esperado not in diferentes:
        raise Erro("the rebuilt image is identical to the input — the patch "
                   "did not make it in")
    print("  verified: exactly one file differs, and it is the launcher")

    # Dono e permissão do lançador, lidos dos metadados do squashfs e não do
    # disco: um `unsquashfs` sem privilégio grava tudo como o usuário atual, e
    # olhar o disco diria "micae" mesmo quando a imagem está certa. Um rootfs
    # cujo /usr/bin não pertence ao root não sobe, e isso só apareceria depois
    # de gravado no aparelho — tarde demais.
    listagem = rodar("unsquashfs", "-lls", montado, "usr/bin/hiby_player.sh")
    linha = next((l for l in listagem.splitlines()
                  if "hiby_player.sh" in l), "")
    if "root/root" not in linha:
        raise Erro("the launcher inside the image is not owned by root:\n  "
                   + (linha or "(could not read its metadata)"))
    # O modo não é conferido contra um valor fixo: o pacote de fábrica usa 775
    # neste arquivo (e em outros 842), não 755, e uma expectativa chutada de
    # 755 reprovava uma imagem perfeitamente boa. Quem garante o modo é a
    # comparação com a entrada, logo acima — que é a pergunta certa: mudou
    # alguma coisa que eu não quis mudar?
    if not linha.startswith("-rwx"):
        raise Erro("the launcher inside the image is not executable:\n  "
                   + linha)
    print(f"  verified: {linha.split()[0]} root/root, unchanged from the input")

    # E o script tem de ser shell válido: um erro de sintaxe aqui é um
    # aparelho que liga e não abre o player.
    rodar("sh", "-n", os.path.join(raiz2, "usr", "bin", "hiby_player.sh"))
    print("  verified: the patched launcher is valid shell")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Add the /usr/data/init.sh auto-start hook to a stock "
                    "HiBy R1 firmware package.")
    ap.add_argument("entrada", help="the stock r1.upt")
    ap.add_argument("saida", help="the patched .upt to write")
    ap.add_argument("--manter", action="store_true",
                    help="keep the work directory (for inspection)")
    ap.add_argument("--eu-sei-que-esta-quebrado", action="store_true",
                    help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not args.eu_sei_que_esta_quebrado:
        print(DESATIVADO, file=sys.stderr)
        return 2

    if not os.path.isfile(args.entrada):
        print(f"input not found: {args.entrada}", file=sys.stderr)
        return 2
    if os.path.exists(args.saida):
        print(f"output already exists, refusing to overwrite: {args.saida}",
              file=sys.stderr)
        return 2

    try:
        leitor, gerador = conferir_ferramentas()
    except Erro as e:
        print(str(e), file=sys.stderr)
        return 2

    # O umask entra no meio do caminho e estraga tudo em silêncio: o
    # `unsquashfs` cria os arquivos respeitando-o, e num sistema com umask 002
    # — o padrão do Ubuntu — o lançador do player sai 775 em vez de 755. Todos
    # os arquivos do rootfs sairiam com permissão de escrita para o grupo, e
    # isso só apareceria depois de gravado no aparelho.
    os.umask(0o022)

    trabalho = tempfile.mkdtemp(prefix="r1upt-")
    try:
        print(f"reading {args.entrada}")
        iso = os.path.join(trabalho, "iso")
        ler_iso(args.entrada, iso, leitor)
        dir_ota = os.path.join(iso, "ota_v0")
        if not os.path.isdir(dir_ota):
            raise Erro("no ota_v0/ inside the package — is it an R1 firmware?")

        montado, pedacos = juntar(dir_ota, "rootfs.squashfs")
        soma = md5(montado)
        print(f"  rootfs: {len(pedacos)} chunks, "
              f"{os.path.getsize(montado):,} bytes, md5 {soma}")

        # O pacote declara o md5 no nome de um arquivo vazio; se não bater, o
        # que veio já estava corrompido e não adianta seguir.
        marcas = [n for n in os.listdir(dir_ota)
                  if n.startswith("ota_md5_rootfs.squashfs.")]
        if marcas:
            declarado = marcas[0].rsplit(".", 1)[-1]
            if declarado != soma:
                raise Erro(f"the package declares md5 {declarado} for the "
                           f"rootfs but it assembles to {soma}; the input is "
                           f"damaged")
            print("  md5 matches what the package declares")

        raiz = os.path.join(trabalho, "raiz")
        print("unpacking the root filesystem")
        rodar("unsquashfs", "-n", "-f", "-d", raiz, montado)
        original = os.path.join(trabalho, "raiz_original")
        shutil.copytree(raiz, original, symlinks=True)

        print("patching the launcher")
        print("  " + remendar_lancador(raiz))

        print("repacking")
        novo = os.path.join(trabalho, "rootfs.novo")
        # As mesmas opções do original: lzo, blocos de 128 KB, tudo do root.
        # -all-root porque o unsquashfs sem privilégio perde o dono, e um
        # rootfs cujos arquivos pertencem a "micae" não sobe.
        rodar("mksquashfs", raiz, novo, "-comp", "lzo", "-b", "131072",
              "-noappend", "-all-root", "-no-progress", "-quiet")
        print(f"  new rootfs: {os.path.getsize(novo):,} bytes, md5 {md5(novo)}")

        # Fora com os pedaços velhos e a marca velha; entram os novos.
        for n in pedacos:
            os.remove(os.path.join(dir_ota, n))
        for n in list(os.listdir(dir_ota)):
            if n.startswith("ota_md5_rootfs.squashfs."):
                os.remove(os.path.join(dir_ota, n))
        partir(novo, dir_ota, "rootfs.squashfs")
        open(os.path.join(dir_ota, f"ota_md5_rootfs.squashfs.{md5(novo)}"),
             "w").close()
        os.remove(montado)

        print("building the package")
        rodar(gerador, "-quiet", "-R", "-V", "CDROM", "-o", args.saida, iso)
        print(f"  wrote {args.saida} ({os.path.getsize(args.saida):,} bytes)")

        print("checking the result")
        conferir_saida(args.saida, original, leitor, trabalho)

        print()
        print("Done. Copy it to the root of the SD card and use the player's")
        print("firmware update menu. Keep your stock r1.upt: flashing is not")
        print("reversible from software, and that file is the way back.")
        return 0
    except Erro as e:
        print("\nfailed: " + str(e), file=sys.stderr)
        if os.path.exists(args.saida):
            os.remove(args.saida)
        return 1
    finally:
        if args.manter:
            print(f"work directory kept at {trabalho}")
        else:
            shutil.rmtree(trabalho, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
