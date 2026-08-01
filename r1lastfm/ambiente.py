"""O que precisa existir nesta máquina, e como achar.

O scrobbler precisa de bem pouco: o adb para falar com o R1 e, só para quem
quiser o envio pelo WiFi, o Zig para compilar os dois programinhas do
aparelho. No Windows o Zig roda dentro do WSL, porque é lá que a compilação
cruzada funciona sem sustos.

Cada verificação devolve um estado e, quando falha, uma instrução do que fazer
— nunca só "erro".
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from .applog import Log
from .idioma import t
from .runner import IS_WINDOWS, InstallerError, Runner, which

# Onde o Android Platform Tools costuma cair quando se baixa o zip e extrai.
LUGARES_DO_ADB = (
    r"C:\platform-tools\adb.exe",
    r"C:\Android\platform-tools\adb.exe",
    os.path.expanduser(r"~\platform-tools\adb.exe"),
    os.path.expanduser(r"~\Downloads\platform-tools\adb.exe"),
    os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    "/usr/bin/adb",
    "/usr/local/bin/adb",
    "/opt/homebrew/bin/adb",
)

URL_PLATFORM_TOOLS = "https://developer.android.com/tools/releases/platform-tools"

# Distribuicoes do WSL que existem para outra coisa e nao servem de ambiente
# de compilacao. Oferecer a do Docker so levaria a um erro confuso mais tarde.
DISTROS_INUTEIS = ("docker-desktop", "docker-desktop-data",
                   "podman-machine-default")

# Sem isto o wsl.exe pisca um console preto a cada sondagem.
_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Verificacao:
    rotulo: str
    estado: str        # "ok" | "aviso" | "falta"
    detalhe: str = ""
    dica: str = ""
    obrigatorio: bool = True


@dataclass
class Ambiente:
    runner: Runner
    adb: Optional[str] = None
    zig_dir: Optional[str] = None
    zig_versao: str = ""
    wsl_ok: bool = False
    distros: list = field(default_factory=list)
    verificacoes: list = field(default_factory=list)

    # -- adb -----------------------------------------------------------------

    def achar_adb(self) -> Optional[str]:
        caminho = which("adb")
        if not caminho:
            for tentativa in LUGARES_DO_ADB:
                if os.path.isfile(tentativa):
                    caminho = tentativa
                    break
        self.adb = caminho
        return caminho

    # -- zig -----------------------------------------------------------------

    def achar_zig(self) -> Optional[str]:
        """O Zig que este programa instalou, se houver."""
        from . import zigsetup
        achado = zigsetup.find_installed(self.runner)
        if achado:
            self.zig_dir, self.zig_versao = achado[0], achado[1]
            self.runner.posix_path_extra = self.zig_dir
            return self.zig_dir
        # Um Zig do próprio sistema também serve.
        from .compilar import zig_disponivel, zig_versao
        if zig_disponivel(self.runner):
            self.zig_dir = ""
            self.zig_versao = zig_versao(self.runner)
            return ""
        self.zig_dir = None
        return None

    # -- wsl -----------------------------------------------------------------

    def listar_distros(self) -> list[str]:
        """As distribuições do WSL que podem hospedar um compilador."""
        if not IS_WINDOWS or not shutil.which("wsl.exe"):
            return []
        try:
            proc = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True,
                                  timeout=25, creationflags=_SEM_JANELA)
        except (OSError, subprocess.TimeoutExpired):
            return []
        # O wsl.exe imprime a própria saída de gerência em UTF-16LE.
        bruto = proc.stdout
        texto = (bruto.decode("utf-16-le", errors="replace")
                 if b"\x00" in bruto[:40]
                 else bruto.decode("utf-8", errors="replace"))
        nomes = []
        for linha in texto.splitlines():
            nome = linha.strip().strip("﻿").replace("\x00", "").strip()
            if nome and nome.lower() not in DISTROS_INUTEIS:
                nomes.append(nome)
        return nomes

    def checar_wsl(self) -> bool:
        """Acha uma distribuição que responda e a escolhe para o Runner.

        Sem isto, ``runner.wsl_distro`` fica em None e a primeira tentativa de
        rodar qualquer coisa no lado POSIX morre com um TypeError dentro do
        subprocess — um erro que não diz nada a quem está só usando o programa.
        """
        if not IS_WINDOWS:
            self.wsl_ok = True
            return True
        self.distros = self.listar_distros()
        for nome in self.distros:
            res = self.runner.run(["wsl.exe", "-d", nome, "--", "sh", "-c",
                                   "echo VIVO"],
                                  mutating=False, quiet=True, timeout=60)
            if res.ok and "VIVO" in res.stdout:
                self.runner.wsl_distro = nome
                self.wsl_ok = True
                return True
        self.wsl_ok = False
        return False

    # -- tudo junto ----------------------------------------------------------

    def verificar(self) -> list:
        """Uma passada por tudo. O envio pelo cabo só precisa do adb."""
        v: list = []

        import sys
        try:
            import tkinter  # noqa: F401
            v.append(Verificacao(t("env.python"), "ok",
                                 f"{sys.version.split()[0]}"))
        except ImportError:
            v.append(Verificacao(t("env.python"), "falta",
                                 t("env.python.missing"), t("env.python.hint")))

        adb = self.achar_adb()
        if adb:
            res = self.runner.run([adb, "version"], mutating=False, quiet=True,
                                  timeout=30)
            primeira = (res.stdout.splitlines() or [""])[0]
            v.append(Verificacao(t("env.adb"), "ok", f"{adb} — {primeira}"))
        else:
            v.append(Verificacao(
                t("env.adb"), "falta", t("env.adb.missing"),
                t("env.adb.hint", url=URL_PLATFORM_TOOLS)))

        if IS_WINDOWS:
            if self.checar_wsl():
                v.append(Verificacao(
                    t("env.wsl"), "ok",
                    t("env.wsl.ok", nome=self.runner.wsl_distro),
                    obrigatorio=False))
            else:
                v.append(Verificacao(
                    t("env.wsl"), "aviso", t("env.wsl.missing"),
                    t("env.wsl.hint"), obrigatorio=False))

        zig = self.achar_zig()
        if zig is not None:
            v.append(Verificacao(t("env.zig"), "ok",
                                 self.zig_versao or t("env.zig.present"),
                                 obrigatorio=False))
        else:
            v.append(Verificacao(
                t("env.zig"), "aviso", t("env.zig.missing"),
                t("env.zig.hint"), obrigatorio=False))

        self.verificacoes = v
        return v

    @property
    def pronto_para_o_basico(self) -> bool:
        """Dá para coletar e enviar pelo cabo?"""
        return bool(self.adb)

    def exigir_adb(self) -> str:
        if not self.adb and not self.achar_adb():
            raise InstallerError(
                t("err.adb.title2"),
                t("err.adb.body", url=URL_PLATFORM_TOOLS))
        return self.adb  # type: ignore[return-value]
