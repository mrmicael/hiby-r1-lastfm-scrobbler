"""Which language the program speaks.

English is the default, because most people who find this project will not read
Portuguese. Portuguese is here because that is where it was written, and a
translation that loses the original is a translation that drifts.

How it works
------------
Every user-visible string lives in ``textos.py`` under a short key, with one
entry per language. Code calls ``t("card.api.title")`` instead of holding the
string. Two things follow from that:

* adding a language means adding a column to the catalogue, not hunting through
  a thousand lines of GUI code;
* ``testes/t_idioma.py`` can walk the source, collect every key that is asked
  for, and prove that all of them exist in **all** languages — a missing
  translation fails the suite instead of showing up on someone's screen.

The choice is remembered in ``config.json``. On the very first run, the
system's own language decides: a machine set to Portuguese starts in
Portuguese, everything else starts in English.
"""

from __future__ import annotations

import locale
import os
from typing import Optional

from .textos import TEXTOS

# Código -> nome do idioma *no próprio idioma*. Um menu que diz "Portuguese"
# para quem só lê português não ajuda ninguém a se achar.
IDIOMAS: dict[str, str] = {
    "en": "English",
    "pt": "Português (Brasil)",
}

PADRAO = "en"

_atual = PADRAO


def definir(codigo: Optional[str]) -> str:
    """Escolhe o idioma. Um código desconhecido cai no padrão, sem reclamar."""
    global _atual
    codigo = (codigo or "").strip().lower()
    if codigo[:2] in IDIOMAS:
        _atual = codigo[:2]
    else:
        _atual = PADRAO
    return _atual


def atual() -> str:
    return _atual


def do_sistema() -> str:
    """O idioma do computador, quando ele é um dos que existem aqui.

    Serve só para a primeira execução: depois disso vale o que a pessoa
    escolheu, mesmo que o sistema esteja em outra língua.
    """
    for fonte in (os.environ.get("R1LASTFM_LANG"),
                  os.environ.get("LANGUAGE"),
                  os.environ.get("LC_ALL"),
                  os.environ.get("LANG")):
        if fonte and fonte[:2].lower() in IDIOMAS:
            return fonte[:2].lower()
    try:
        # getlocale() devolve None em muitos Windows; getdefaultlocale está
        # obsoleto mas é o único que responde nesses casos.
        codigo = locale.getlocale()[0] or ""
        if not codigo:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                codigo = locale.getdefaultlocale()[0] or ""  # type: ignore[attr-defined]
    except (ValueError, TypeError):
        codigo = ""
    codigo = codigo.replace("-", "_")
    if codigo[:2].lower() in IDIOMAS:
        return codigo[:2].lower()
    # No Windows o nome vem por extenso: "Portuguese_Brazil".
    if codigo.lower().startswith("portuguese"):
        return "pt"
    return PADRAO


def t(chave: str, **campos) -> str:
    """O texto da chave, no idioma de agora.

    Um idioma incompleto cai no inglês em vez de sumir com a frase; uma chave
    que não existe aparece marcada, para ser vista e corrigida — nunca vira
    string vazia, que some na tela sem deixar rastro.
    """
    entrada = TEXTOS.get(chave)
    if entrada is None:
        return f"⟪{chave}⟫"
    texto = entrada.get(_atual) or entrada.get(PADRAO) or f"⟪{chave}⟫"
    if campos:
        try:
            return texto.format(**campos)
        except (KeyError, IndexError, ValueError):
            # Um campo faltando não pode derrubar a tela inteira.
            return texto
    return texto
