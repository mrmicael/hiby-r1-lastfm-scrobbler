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
# HISTÓRICO — leia antes de confiar nisto.
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
AVISO = (
    "This writes a firmware package you will install on your player.\n"
    "\n"
    "A package from this script has been installed on a real R1 and booted:\n"
    "stock 1.6, with the collector starting by itself and ADB coming up at\n"
    "boot. It works. But installing firmware is still the one thing here that\n"
    "cannot be undone from software, so:\n"
    "\n"
    "  * BEFORE you flash, put a known-good .upt on the memory card.\n"
    "    That is your way back, and you want it there already, not later.\n"
    "  * If an install ever hangs on \"Upgrading...\": power off, then power\n"
    "    on holding power + volume-up. It installs the good firmware from\n"
    "    the card. This is how the one failure during development was\n"
    "    recovered, and it works.\n"
    "  * Do not flash on a low battery, or from a memory card with read\n"
    "    errors.\n"
    "\n"
    "Pass --entendi-o-risco to continue.\n"
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


def partir(caminho: str, dir_ota: str, base: str) -> int:
    """Reparte em pedaços de 512 KB, do jeito exato que o atualizador espera.

    O formato não foi deduzido: está no /etc/ota_bin/local_ota_update.sh, que
    vem dentro do próprio firmware. O laço dele é este, resumido:

        md5_file=ota_md5_$img_name.$pre_md5      # a LISTA de md5
        src_file=$img_name.$num.$pre_md5         # o pedaço
        md5_num1=`sed -n "${num}p" $md5_file`    # linha i+1 da lista
        md5_num2=`md5sum_file $out_file`         # md5 do pedaço
        [ "$md5_num1" != "$md5_num2" ] && falha
        pre_md5=$md5_num2                        # encadeia no proximo nome

    Ou seja, são DUAS coisas, e eu só fazia uma:

      1. o nome de cada pedaço carrega o md5 do ANTERIOR (o do pedaço 0000
         carrega o do arquivo inteiro) — isso eu já fazia;

      2. e existe um arquivo `ota_md5_<nome>.<md5 do inteiro>` com o md5 de
         CADA pedaço, uma linha por pedaço, na ordem. Eu criava esse arquivo
         VAZIO. O `sed -n "1p"` devolvia nada, o atualizador desistia no
         primeiro pedaço, e a tela ficava em "Upgrading…" para sempre.

    Devolve quantos pedaços foram escritos.
    """
    inteiro = md5(caminho)
    anterior = inteiro
    somas: list[str] = []
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
            somas.append(anterior)
            i += 1
    if i == 0:
        raise Erro(f"{base} came out empty")

    # A lista de md5, que é o que faltava.
    with open(os.path.join(dir_ota, f"ota_md5_{base}.{inteiro}"),
              "w", newline="\n") as out:
        out.write("".join(s + "\n" for s in somas))
    return i


def reescrever_manifesto(caminho: str, tamanho: int, soma: str) -> str:
    """Põe o novo md5 e tamanho do rootfs no ota_update.in.

    Este arquivo é o que manda. Foi ele que faltou, e a falta dele prendeu um
    aparelho na tela de atualização:

        img_type=rootfs
        img_name=rootfs.squashfs
        img_size=37507072
        img_md5=9c8b3a941dc2324ed6a641760928959c

    O atualizador do aparelho lê isto, remonta os pedaços, calcula o md5 e
    compara. Eu trocava o md5 no NOME do arquivo-marca e deixava o manifesto
    declarando o md5 do rootfs original — então a conferência dele nunca
    fechava, e ele ficava esperando por uma imagem que não ia chegar.

    Isso estava escrito no /etc/ota_bin/local_ota_update.sh do próprio
    firmware o tempo todo. Eu deduzi o formato pelos nomes dos arquivos em vez
    de ler o programa que os consome, e é exatamente por isso que passei perto
    sem acertar.

    Só as linhas do rootfs mudam; as do kernel ficam como estão, porque o
    kernel não é tocado.
    """
    with open(caminho, encoding="utf-8", errors="surrogateescape") as fh:
        linhas = fh.read().splitlines()

    saida: list[str] = []
    dentro_do_rootfs = False
    trocou_md5 = trocou_tam = False
    for linha in linhas:
        nu = linha.strip()
        if nu.startswith("img_type="):
            dentro_do_rootfs = nu.split("=", 1)[1].strip() == "rootfs"
        if dentro_do_rootfs and nu.startswith("img_md5="):
            saida.append(f"img_md5={soma}")
            trocou_md5 = True
            continue
        if dentro_do_rootfs and nu.startswith("img_size="):
            saida.append(f"img_size={tamanho}")
            trocou_tam = True
            continue
        saida.append(linha)

    if not (trocou_md5 and trocou_tam):
        raise Erro("could not find the rootfs entry in ota_update.in — this "
                   "package is not shaped the way the updater expects, and "
                   "writing it would produce something that cannot install")

    with open(caminho, "w", encoding="utf-8", errors="surrogateescape",
              newline="\n") as fh:
        fh.write("\n".join(saida) + "\n")
    return f"manifest now declares size {tamanho:,} and md5 {soma}"


def instalar_adb_no_boot(raiz: str) -> str:
    """Põe o /etc/init.d/S90adb, que liga o ADB no boot.

    O firmware de fábrica traz o T90adb, mas o rcS só executa os scripts que
    começam com S — então o ADB nunca sobe sozinho. Quem tinha ADB no R1
    tinha um firmware modificado que acrescentava este arquivo, e quem
    instala o 1.6 puro fica sem: sem ADB não dá para instalar o coletor, e
    sem coletor não há scrobbler.

    Este é o mesmo script que já rodava no aparelho onde tudo foi
    desenvolvido, copiado de lá. Ele só sobe o ADB quando o modo USB é Auto
    (0) ou Device (1); em DAC e OTG o gadget USB é de outro dono.
    """
    origem = os.path.join(os.path.dirname(os.path.abspath(__file__)), "S90adb")
    if not os.path.isfile(origem):
        raise Erro(f"the S90adb script is missing from {origem}")
    destino = os.path.join(raiz, "etc", "init.d", "S90adb")
    if os.path.exists(destino):
        return "ADB at boot: already there, left alone"
    shutil.copyfile(origem, destino)
    os.chmod(destino, 0o755)
    return f"ADB at boot: /etc/init.d/S90adb installed ({os.path.getsize(destino)} bytes)"


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


def conferir_manifesto(dir_ota: str) -> None:
    """O que o manifesto promete é o que está no pacote?

    Esta é a conferência que faltava, e a sua falta prendeu um aparelho na
    tela de atualização. Ela faz exatamente o que o atualizador do R1 faz: lê
    o ota_update.in, remonta os pedaços declarados, e compara tamanho e md5.
    Se não fechar aqui, também não vai fechar lá.
    """
    manifesto = os.path.join(dir_ota, "ota_update.in")
    declarado: dict[str, dict[str, str]] = {}
    tipo = ""
    with open(manifesto, encoding="utf-8", errors="surrogateescape") as fh:
        for linha in fh:
            nu = linha.strip()
            if "=" not in nu:
                continue
            chave, _, valor = nu.partition("=")
            if chave == "img_type":
                tipo = valor
                declarado.setdefault(tipo, {})
            elif tipo:
                declarado[tipo][chave] = valor

    if "rootfs" not in declarado or "kernel" not in declarado:
        raise Erro(f"ota_update.in does not declare both a kernel and a "
                   f"rootfs; it declares {sorted(declarado)}")

    for tipo, campos in sorted(declarado.items()):
        nome = campos.get("img_name", "")
        montado, pedacos = juntar(dir_ota, nome)
        try:
            tamanho, soma = os.path.getsize(montado), md5(montado)
            if str(tamanho) != campos.get("img_size"):
                raise Erro(f"{tipo}: the manifest says img_size="
                           f"{campos.get('img_size')} but the chunks assemble "
                           f"to {tamanho}")
            if soma != campos.get("img_md5"):
                raise Erro(f"{tipo}: the manifest says img_md5="
                           f"{campos.get('img_md5')} but the chunks assemble "
                           f"to {soma}.\nThis is the failure that leaves a "
                           f"device on the Upgrading screen: the updater "
                           f"reassembles, compares, and waits forever for an "
                           f"image that will never match.")
        finally:
            if os.path.exists(montado):
                os.remove(montado)

        # E agora o que importa de verdade: repetir o laço do atualizador,
        # passo a passo, como ele está escrito no local_ota_update.sh. Todas
        # as minhas conferências anteriores eram invenção minha sobre o que
        # o formato deveria ser, e por isso passaram enquanto o aparelho
        # travava. Esta segue o programa que consome o arquivo.
        lista = os.path.join(dir_ota, f"ota_md5_{nome}.{soma}")
        if not os.path.isfile(lista):
            raise Erro(f"{tipo}: there is no ota_md5_{nome}.{soma} — the "
                       f"updater copies that file first and reads one md5 "
                       f"per chunk from it")
        with open(lista, encoding="ascii", errors="replace") as fh:
            linhas = [l.strip() for l in fh]
        linhas = [l for l in linhas if l]
        if len(linhas) < len(pedacos):
            raise Erro(f"{tipo}: the md5 list has {len(linhas)} entries for "
                       f"{len(pedacos)} chunks. An empty or short list is "
                       f"what leaves a device on the Upgrading screen: the "
                       f"updater reads line 1, gets nothing, and gives up on "
                       f"the very first chunk.")

        anterior = soma
        total = 0
        for i in range(len(pedacos)):
            esperado = os.path.join(dir_ota, f"{nome}.{i:04d}.{anterior}")
            if not os.path.isfile(esperado):
                raise Erro(f"{tipo}: the updater would look for "
                           f"{os.path.basename(esperado)} and not find it")
            real = md5(esperado)
            if linhas[i] != real:
                raise Erro(f"{tipo}: line {i+1} of the md5 list says "
                           f"{linhas[i]} but chunk {i:04d} is {real}")
            anterior = real
            total += os.path.getsize(esperado)
        if total < int(campos.get("img_size", "0")):
            raise Erro(f"{tipo}: the chunks add up to {total}, less than the "
                       f"declared {campos.get('img_size')} — the updater "
                       f"loops until the total is reached and would never "
                       f"get there")
        print(f"  verified: {tipo} passes the updater's own loop "
              f"({len(pedacos)} chunks, {total:,} bytes, md5 {soma})")


def conferir_recipiente(entrada: str, saida: str) -> None:
    """A ISO gerada tem a mesma forma da de fábrica?

    Esta conferência não existia, e a sua falta custou caro: eu conferia o
    recheio do pacote — o squashfs, arquivo por arquivo — e nunca o pacote.
    O que estava errado era a embalagem. Faltava o Joliet, sem o qual os nomes
    longos dos pedaços somem, e o atualizador do aparelho ficou eternamente na
    tela "Upgrading…" procurando por eles.

    O que se compara aqui são as propriedades que o atualizador enxerga, lidas
    das duas ISOs pelo mesmo comando. Se alguma diferir, nenhum pacote sai.
    """
    if not existe("isoinfo"):
        raise Erro("isoinfo is missing (genisoimage package) and this check "
                   "cannot be skipped: it is the one that would have caught "
                   "the packaging bug that bricked a device")

    def ler(caminho: str) -> dict[str, str]:
        campos: dict[str, str] = {}
        for linha in rodar("isoinfo", "-d", "-i", caminho).splitlines():
            if linha.startswith("Joliet"):
                campos["joliet"] = linha.strip()
            elif linha.startswith("NO Joliet"):
                campos["joliet"] = "absent"
            elif linha.startswith("Rock Ridge"):
                campos["rock ridge"] = linha.strip()
            elif ":" in linha:
                chave, _, valor = linha.partition(":")
                if chave.strip() in ("System id", "Volume id",
                                     "Logical block size is"):
                    campos[chave.strip()] = valor.strip()
        return campos

    a, b = ler(entrada), ler(saida)
    problemas = [f"{k}: input has {a.get(k, '(none)')!r}, "
                 f"output has {b.get(k, '(none)')!r}"
                 for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    if problemas:
        raise Erro("the package came out shaped differently from the "
                   "original:\n  " + "\n  ".join(problemas))
    print(f"  verified: same container as the original "
          f"({a.get('joliet', '?')}, {a.get('rock ridge', '?')})")

    # E os nomes longos têm de sobreviver pelos DOIS caminhos, porque não se
    # sabe por qual deles o atualizador lê.
    for rotulo, extra in (("Rock Ridge", ["-R"]), ("Joliet", ["-J"])):
        nomes = rodar("isoinfo", "-i", saida, "-f", *extra).splitlines()
        longos = [n for n in nomes if "rootfs.squashfs." in n]
        if not longos:
            raise Erro(f"the chunk names do not survive through {rotulo} in "
                       f"the generated package — this is exactly what left a "
                       f"device stuck on the update screen")
        print(f"  verified: {len(longos)} chunk names readable via {rotulo}")


def conferir_saida(upt: str, raiz_original: str, leitor: str,
                   trabalho: str, esperados: list[str]) -> None:
    """Desempacota o que acabou de ser gerado e compara com a entrada.

    Um pacote de firmware é a única coisa aqui que pode inutilizar o aparelho,
    então ele não sai daqui sem ser aberto de novo e conferido arquivo por
    arquivo. O que se espera é uma diferença só: o hiby_player.sh.
    """
    conf = os.path.join(trabalho, "conferencia")
    ler_iso(upt, conf, leitor)
    # Do pacote pronto, como o aparelho o receberá: o manifesto tem de fechar
    # com os pedaços que estão lá dentro.
    conferir_manifesto(os.path.join(conf, "ota_v0"))
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

    # Um arquivo novo não aparece percorrendo a árvore original, então a
    # comparação é feita nos dois sentidos.
    for base, _dirs, arqs in os.walk(raiz2):
        for a in arqs:
            rel = os.path.relpath(os.path.join(base, a), raiz2)
            if not os.path.lexists(os.path.join(raiz_original, rel)):
                diferentes.append(rel)

    inesperados = [d for d in diferentes
                   if d.split(" (")[0] not in esperados]
    if inesperados:
        raise Erro("the rebuilt image differs in files it should not:\n  "
                   + "\n  ".join(sorted(inesperados)[:20]))
    faltando = [e for e in esperados
                if not any(d.split(" (")[0] == e for d in diferentes)]
    if faltando:
        raise Erro("these were supposed to change and did not:\n  "
                   + "\n  ".join(faltando))
    print(f"  verified: {len(esperados)} file(s) differ, and they are the "
          f"ones asked for: " + ", ".join(esperados))

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
    ap.add_argument("--com-adb", action="store_true",
                    help="also install /etc/init.d/S90adb, which brings ADB "
                         "up at boot. Stock firmware never does, and without "
                         "ADB there is no way to install the collector.")
    ap.add_argument("--entendi-o-risco", action="store_true",
                    help="acknowledge that no package from this script has "
                         "been installed on a device yet")
    args = ap.parse_args()

    if not args.entendi_o_risco:
        print(AVISO, file=sys.stderr)
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
        # A lista do que TEM de mudar. No fim, o pacote é aberto de novo e
        # nada além disto pode ter se mexido.
        esperados = [os.path.join("usr", "bin", "hiby_player.sh")]
        print("  " + remendar_lancador(raiz))
        if args.com_adb:
            print("  " + instalar_adb_no_boot(raiz))
            esperados.append(os.path.join("etc", "init.d", "S90adb"))

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
        n = partir(novo, dir_ota, "rootfs.squashfs")
        print(f"  {n} chunks and their md5 list written")
        # E o manifesto, que é quem o atualizador realmente lê.
        manifesto = os.path.join(dir_ota, "ota_update.in")
        if not os.path.isfile(manifesto):
            raise Erro("there is no ota_v0/ota_update.in in this package; "
                       "without it the updater has nothing to verify against")
        print("  " + reescrever_manifesto(manifesto, os.path.getsize(novo),
                                          md5(novo)))
        os.remove(montado)

        print("building the package")
        # -J é obrigatório, e a falta dele foi o que travou um aparelho.
        #
        # Os pedaços têm nomes de 52 caracteres. No ISO 9660 puro eles viram
        # ROOTFS_S.000;1 e o md5 do nome — que é como o atualizador confere
        # cada pedaço — some. O nome longo sobrevive de duas formas: Rock
        # Ridge e Joliet. O pacote de fábrica traz as duas; eu tinha gerado só
        # com Rock Ridge, e o atualizador, que lê pelo Joliet, ficou
        # procurando arquivos que não existiam para ele. A tela "Upgrading…"
        # não é um travamento: é ele esperando por algo que nunca chega.
        rodar(gerador, "-quiet", "-R", "-J", "-V", "CDROM", "-o",
              args.saida, iso)
        print(f"  wrote {args.saida} ({os.path.getsize(args.saida):,} bytes)")

        print("checking the result")
        conferir_recipiente(args.entrada, args.saida)
        conferir_saida(args.saida, original, leitor, trabalho, esperados)

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
