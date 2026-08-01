"""Onde ficam as pastas de trabalho e o que é lembrado entre execuções.

O que é guardado neste computador:

* a **chave e o segredo de API** do Last.fm, que são seus e você mesmo
  registra (o programa explica como);
* a **chave de sessão**, que o Last.fm devolve depois de você aprovar o
  acesso no navegador. Ela não dá acesso à sua senha e pode ser revogada a
  qualquer momento em last.fm → Configurações → Aplicativos.

O que NÃO fica aqui: a fila do que você ouviu e a lista do que já foi
enviado. Essas duas ficam no próprio R1, de propósito — assim usar o programa
de outro computador não reenvia nada nem perde nada.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from .ambiente import Ambiente
from .runner import IS_WINDOWS, Runner

NOME = "R1LastFm"


def pasta_de_dados() -> str:
    """A pasta do usuário para este programa, seguindo o costume do sistema."""
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, NOME)
    if os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
        return os.path.expanduser(f"~/Library/Application Support/{NOME}")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "r1-lastfm")


@dataclass
class Config:
    base: str
    runner: Runner
    ambiente: Ambiente

    @property
    def arquivo(self) -> str:
        return os.path.join(self.base, "config.json")

    @property
    def cache(self) -> str:
        return os.path.join(self.base, "cache")

    @property
    def trabalho(self) -> str:
        return os.path.join(self.base, "trabalho")

    @property
    def registros(self) -> str:
        return os.path.join(self.base, "registros")

    def criar_pastas(self) -> None:
        for p in (self.base, self.cache, self.trabalho, self.registros):
            os.makedirs(p, exist_ok=True)

    # -- leitura e escrita ---------------------------------------------------

    def ler(self) -> dict:
        try:
            with open(self.arquivo, encoding="utf-8") as fh:
                dados = json.load(fh)
            return dados if isinstance(dados, dict) else {}
        except (OSError, ValueError):
            return {}

    def gravar(self, **valores) -> None:
        self.criar_pastas()
        dados = self.ler()
        dados.update(valores)
        tmp = self.arquivo + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dados, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.arquivo)
        except OSError:
            pass

    # -- as credenciais ------------------------------------------------------

    @property
    def api_key(self) -> str:
        return str(self.ler().get("api_key", "") or "")

    @property
    def api_secret(self) -> str:
        return str(self.ler().get("api_secret", "") or "")

    @property
    def chave_sessao(self) -> str:
        return str(self.ler().get("chave_sessao", "") or "")

    @property
    def usuario(self) -> str:
        return str(self.ler().get("usuario", "") or "")

    @property
    def idioma(self) -> str:
        """O idioma escolhido, ou "" se a pessoa nunca escolheu."""
        return str(self.ler().get("idioma", "") or "")

    @property
    def tem_api(self) -> bool:
        """Uma chave do Last.fm tem 32 caracteres hexadecimais; o segredo também."""
        k, s = self.api_key, self.api_secret
        return len(k) == 32 and len(s) == 32

    @property
    def conectado(self) -> bool:
        return bool(self.chave_sessao)

    def esquecer_conta(self) -> None:
        """Apaga só a sessão. A chave de API é sua e continua guardada."""
        self.gravar(chave_sessao="", usuario="")

    # -- caminhos dos binários gerados ---------------------------------------

    @property
    def dir_binarios(self) -> str:
        return os.path.join(self.trabalho, "binarios")

    def binario(self, nome: str) -> str:
        return os.path.join(self.dir_binarios, nome)

    @property
    def curl_local(self) -> str:
        return os.path.join(self.trabalho, "curl-mipsel", "curl")

    @property
    def cacert_local(self) -> str:
        return os.path.join(self.cache, "cacert.pem")


def montar(runner: Runner) -> Config:
    amb = Ambiente(runner=runner)
    cfg = Config(base=pasta_de_dados(), runner=runner, ambiente=amb)
    cfg.criar_pastas()
    return cfg
