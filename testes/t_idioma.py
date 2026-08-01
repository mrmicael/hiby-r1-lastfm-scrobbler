# -*- coding: utf-8 -*-
"""Nenhuma frase pode ficar sem tradução, e nenhuma chave pode faltar.

Este teste e o que torna o catalogo confiavel: ele varre o codigo-fonte
inteiro, junta toda chave que alguem pede a t(), e prova que todas existem em
todos os idiomas — com os mesmos campos {} nos dois. Sem isto, uma traducao
faltando so aparece na tela de quem esta usando o programa.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import ast, glob, os, re, string, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

from r1lastfm import idioma
from r1lastfm.textos import TEXTOS

falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


FONTES = (sorted(glob.glob(os.path.join(_RAIZ, "r1lastfm", "*.py")))
          + sorted(glob.glob(os.path.join(_RAIZ, "r1lastfm", "gui", "*.py")))
          + [os.path.join(_RAIZ, "r1lastfm.py")])


def campos(texto):
    """Os nomes entre chaves de uma string de formato."""
    return {n for _lit, n, _spec, _conv in string.Formatter().parse(texto) if n}


def chamadas_de_t(arv):
    """Todo nó Call que é uma chamada a t(...)."""
    for n in ast.walk(arv):
        if not isinstance(n, ast.Call):
            continue
        alvo = n.func
        nome = (alvo.id if isinstance(alvo, ast.Name)
                else alvo.attr if isinstance(alvo, ast.Attribute) else "")
        if nome == "t" and n.args:
            yield n


def constantes_de(no):
    """As strings de um literal, inclusive dentro de tuplas aninhadas."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return [no.value]
    if isinstance(no, (ast.Tuple, ast.List, ast.Set)):
        out = []
        for item in no.elts:
            out.extend(constantes_de(item))
        return out
    return []


def ligado_por_laco(arv, nome):
    """As strings que um `for` literal pode dar a esta variável.

    O padrão que aparece na janela é
        for chave, cb, estilo in (("btn.check", ...), ("btn.build", ...)):
            ttk.Button(..., text=t(chave))
    A variável é dinâmica no papel, mas o conjunto de valores está ali no
    código — dá para conferir, e é o que este teste faz em vez de desistir.
    """
    valores = []
    for n in ast.walk(arv):
        if not isinstance(n, ast.For):
            continue
        alvos = ([e for e in n.target.elts] if isinstance(n.target, ast.Tuple)
                 else [n.target])
        pos = next((i for i, a in enumerate(alvos)
                    if isinstance(a, ast.Name) and a.id == nome), None)
        if pos is None:
            continue
        for item in getattr(n.iter, "elts", []):
            if isinstance(item, (ast.Tuple, ast.List)) and len(item.elts) > pos:
                valores.extend(constantes_de(item.elts[pos]))
            elif len(alvos) == 1:
                valores.extend(constantes_de(item))
    return valores


print("=" * 74)
print("1. toda chave pedida no codigo existe no catalogo")
print("=" * 74)
pedidas = {}          # chave -> [arquivo:linha, ...]
dinamicas = []
for caminho in FONTES:
    arv = ast.parse(open(caminho, encoding="utf-8").read(), caminho)
    for n in chamadas_de_t(arv):
        prim = n.args[0]
        onde = f"{os.path.basename(caminho)}:{n.lineno}"
        if isinstance(prim, ast.Constant) and isinstance(prim.value, str):
            pedidas.setdefault(prim.value, []).append(onde)
        elif isinstance(prim, ast.Name):
            do_laco = ligado_por_laco(arv, prim.id)
            if do_laco:
                for k in do_laco:
                    pedidas.setdefault(k, []).append(onde + " (laço)")
            else:
                dinamicas.append((onde, prim.id))
        else:
            # t(f"novidade.{v}") e legitimo, mas so da para conferir a familia.
            dinamicas.append((onde, ast.dump(prim)[:60]))

print(f"   {len(pedidas)} chaves distintas pedidas em {len(FONTES)} arquivos")
sem_entrada = sorted(k for k in pedidas if k not in TEXTOS)
check("nenhuma chave pedida esta faltando no catalogo", not sem_entrada,
      "; ".join(f"{k} ({pedidas[k][0]})" for k in sem_entrada[:6]))

print()
print("=" * 74)
print("2. as chaves montadas em tempo de execucao tambem existem")
print("=" * 74)
# Tres familias sao montadas com f-string a partir de um numero. Cada uma tem
# a sua lista de codigos no proprio modulo, e os dois lados sao conferidos
# aqui: nenhum codigo sem texto, nenhum texto sem codigo.
from r1lastfm import aparelho as AP
from r1lastfm import lastfm as LF

FAMILIAS = [
    ("novidade", [str(v) for v in AP.NOVIDADES]),
    ("lfm.code", [str(c) for c in LF.ERRORS] + ["unknown"]),
    ("lfm.ignore", list(LF.IGNORE_CODES) + ["other"]),
]
montadas = set()
for prefixo, codigos in FAMILIAS:
    faltando = [c for c in codigos if f"{prefixo}.{c}" not in TEXTOS]
    check(f"a familia {prefixo}.* esta completa ({len(codigos)} codigos)",
          not faltando, "; ".join(faltando))
    montadas |= {f"{prefixo}.{c}" for c in codigos}
    # E o contrario: um texto sem codigo correspondente nunca apareceria.
    orfas_fam = sorted(k for k in TEXTOS
                       if k.startswith(prefixo + ".")
                       and k not in {f"{prefixo}.{c}" for c in codigos})
    check(f"nenhum texto {prefixo}.* orfao", not orfas_fam,
          "; ".join(orfas_fam))

check("nao surgiu outra familia dinamica sem cobertura",
      len(dinamicas) <= len(FAMILIAS),
      "; ".join(f"{o} ({q})" for o, q in dinamicas))

print()
print("=" * 74)
print("3. todo idioma tem todas as chaves")
print("=" * 74)
for codigo in sorted(idioma.IDIOMAS):
    faltando = sorted(k for k, v in TEXTOS.items() if not v.get(codigo))
    check(f"{codigo} ({idioma.IDIOMAS[codigo]}) completo", not faltando,
          f"{len(faltando)} faltando: " + "; ".join(faltando[:5]))

print()
print("=" * 74)
print("4. os campos {} batem entre os idiomas")
print("=" * 74)
ruins = []
for chave, versoes in sorted(TEXTOS.items()):
    base = campos(versoes[idioma.PADRAO])
    for codigo, texto in versoes.items():
        if codigo == idioma.PADRAO:
            continue
        if campos(texto) != base:
            ruins.append(f"{chave} [{codigo}]: {sorted(campos(texto))} "
                         f"!= {sorted(base)}")
check("mesmos campos em todas as linguas", not ruins, "; ".join(ruins[:4]))

print()
print("=" * 74)
print("5. quem chama t() passa os campos que o texto pede")
print("=" * 74)
sem_campo = []
for caminho in FONTES:
    arv = ast.parse(open(caminho, encoding="utf-8").read(), caminho)
    for n in ast.walk(arv):
        if not isinstance(n, ast.Call):
            continue
        alvo = n.func
        nome = (alvo.id if isinstance(alvo, ast.Name)
                else alvo.attr if isinstance(alvo, ast.Attribute) else "")
        if nome != "t" or not n.args:
            continue
        prim = n.args[0]
        if not (isinstance(prim, ast.Constant) and isinstance(prim.value, str)):
            continue
        entrada = TEXTOS.get(prim.value)
        if not entrada:
            continue
        precisa = campos(entrada[idioma.PADRAO])
        passou = {kw.arg for kw in n.keywords if kw.arg}
        if precisa - passou:
            sem_campo.append(
                f"{os.path.basename(caminho)}:{n.lineno} {prim.value} "
                f"falta {sorted(precisa - passou)}")
check("nenhuma chamada esquece um campo", not sem_campo,
      "; ".join(sem_campo[:4]))

print()
print("=" * 74)
print("6. o catalogo nao acumula chaves mortas")
print("=" * 74)
# As familias dinamicas ja foram conferidas acima; o resto tem de aparecer
# literalmente no codigo, ou e texto que ninguem le mais.
usadas = set(pedidas) | montadas
orfas = sorted(k for k in TEXTOS if k not in usadas)
check("nenhuma chave sobrando", not orfas,
      f"{len(orfas)}: " + "; ".join(orfas[:8]))

print()
print("=" * 74)
print("7. o mecanismo em si")
print("=" * 74)
antes = idioma.atual()
try:
    check("o padrao e o ingles", idioma.PADRAO == "en")
    idioma.definir("pt")
    check("definir('pt') muda mesmo", idioma.atual() == "pt")
    check("e o texto sai em portugues",
          idioma.t("dlg.cancel") == "Cancelar", idioma.t("dlg.cancel"))
    idioma.definir("en")
    check("definir('en') volta", idioma.t("dlg.cancel") == "Cancel")
    idioma.definir("pt-BR")
    check("aceita 'pt-BR' como pt", idioma.atual() == "pt")
    idioma.definir("klingon")
    check("idioma desconhecido cai no padrao", idioma.atual() == idioma.PADRAO)
    idioma.definir(None)
    check("None tambem cai no padrao", idioma.atual() == idioma.PADRAO)
    marcada = idioma.t("chave.que.nao.existe")
    check("chave inexistente aparece marcada, nao vazia",
          marcada.startswith("⟪") and "chave.que.nao.existe" in marcada, marcada)
    check("campo faltando nao levanta excecao",
          isinstance(idioma.t("dev.counts"), str))
    check("campo sobrando nao atrapalha",
          "Cancel" in idioma.t("dlg.cancel", inexistente=1))
    check("do_sistema() devolve um idioma conhecido",
          idioma.do_sistema() in idioma.IDIOMAS, idioma.do_sistema())
finally:
    idioma.definir(antes)

print()
print("=" * 74)
print("8. nao sobrou frase solta em nenhum modulo")
print("=" * 74)
# Uma string com acento e espaco, fora de docstring e fora do catalogo, quase
# sempre e texto que escapou da traducao. A varredura cobre o pacote inteiro:
# um erro de rede aparece na tela tanto quanto um rotulo de botao.
ACENTOS = "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
# Acento sozinho nao basta. "REGISTRO AO VIVO" ficou meses no rodape da
# janela, em portugues, com a interface inteira em ingles — e passou por este
# teste porque nao tem um unico acento. Um punhado de palavras que sao
# portuguesas e nao inglesas fecha o buraco.
PALAVRAS = (" ao ", " do ", " da ", " de ", " os ", " as ", " um ", " uma ",
            " para ", " com ", " sem ", " que ", " nao ", " voce ",
            "registro", "aparelho", "arquivo", "faixa", "envio", "fila",
            "cartao", "chave", "aviso", "erro ")


# Pedacos de shell que vao para o aparelho nao sao interface: eles carregam
# comentarios e marcadores em portugues de proposito, e traduzi-los mudaria o
# comportamento do daemon em vez de mudar o que alguem le.
CODIGO = ("&&", "||", "2>", "$(", "/dev/", "echo ", "printf ", "grep ",
          "awk ", "[ -", "; ", "	")


def parece_codigo(v):
    return v.lstrip().startswith("#") or any(c in v for c in CODIGO)


def parece_portugues(v):
    if parece_codigo(v):
        return False
    baixo = " " + v.lower() + " "
    return (any(c in ACENTOS for c in v)
            or any(p in baixo for p in PALAVRAS))
soltas = []
for caminho in FONTES:
    if os.path.basename(caminho) in ("textos.py", "idioma.py"):
        continue
    fonte = open(caminho, encoding="utf-8").read()
    arv = ast.parse(fonte, caminho)
    docs = set()
    for n in ast.walk(arv):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            d = ast.get_docstring(n, clean=False)
            if d:
                docs.add(d)
    for n in ast.walk(arv):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        v = n.value
        if v in docs or len(v) < 15 or " " not in v:
            continue
        if v.startswith(("http", "/", "#!", "  ")) or "\t" in v:
            continue
        if not parece_portugues(v):
            continue
        soltas.append(f"{os.path.basename(caminho)}:{n.lineno} {v[:45]!r}")
check("nenhuma frase em portugues fora do catalogo", not soltas,
      "; ".join(soltas[:4]))

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
