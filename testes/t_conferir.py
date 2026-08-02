# -*- coding: utf-8 -*-
"""A conferencia do binario compilado, contra ELFs de verdade.

Existe por causa de um bug bobo e caro: eu comparava o campo de endianness
com "little", quando ele vale "little-endian". Resultado: TODO binario correto
era recusado, com a mensagem "little-endian-endian; o R1 e little-endian".
Nenhum teste pegou porque a conferir() nunca era chamada — a suite testava a
compilacao por fora, olhando o ELF na mao.

Agora ela e chamada com binarios reais: o mipsel bom, um x86 (arquitetura
errada), um big-endian forjado, um dinamico e um arquivo que nem e ELF.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import os, shutil, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, _RAIZ)
from r1lastfm.applog import Log
from r1lastfm.runner import InstallerError, Runner
from r1lastfm.compilar import FLAGS_ESPERADAS, conferir, e_flags

SCRATCH = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SCRATCH, "lastfm")
TMP = os.path.join(SCRATCH, "conferir")
os.makedirs(TMP, exist_ok=True)
log = Log(os.path.join(SCRATCH, "t_conferir.log"))
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


def aceita(caminho, rotulo="teste"):
    """(passou, mensagem)."""
    try:
        conferir(caminho, log, rotulo)
        return True, ""
    except InstallerError as exc:
        return False, (exc.message + " | " + exc.detail).replace("\n", " ")


print("=" * 74)
print("1. o binario mipsel de verdade PASSA")
print("=" * 74)
# Os que a suite ja compilou para o R1.
for nome in ("r1collect.mipsel", "r1send.mipsel"):
    p = os.path.join(WORK, nome)
    if not os.path.isfile(p):
        print(f"   (pulei {nome}: nao foi compilado nesta maquina)")
        continue
    ok, msg = aceita(p, nome)
    check(f"{nome} aceito", ok, msg[:120])
    check(f"{nome} tem os e_flags do R1", e_flags(p) == FLAGS_ESPERADAS,
          hex(e_flags(p) or 0))

# E o que a propria interface gerou, se estiver la.
from r1lastfm.config import pasta_de_dados
_DADOS = pasta_de_dados()
gerado = os.path.join(_DADOS, "trabalho", "scrobble", "r1collect")
if os.path.isfile(gerado):
    ok, msg = aceita(gerado, "r1collect da interface")
    check("o binario que a interface gerou e aceito", ok, msg[:140])

print()
print("=" * 74)
print("2. o curl estatico compilado aqui tambem passa")
print("=" * 74)
curl = os.path.join(_DADOS, "trabalho", "curl-mipsel", "curl")
if not os.path.isfile(curl):
    curl = os.path.join(_DADOS, "trabalho", "build-curl", "curl")
if os.path.isfile(curl):
    ok, msg = aceita(curl, "curl")
    check("curl mipsel aceito", ok, msg[:140])
else:
    print("   (curl nao compilado nesta maquina; pulando)")

print()
print("=" * 74)
print("3. binarios ERRADOS tem de ser recusados, com o motivo certo")
print("=" * 74)
base = os.path.join(WORK, "r1collect.mipsel")
if not os.path.isfile(base):
    base = os.path.join(WORK, "r1collect")   # o do proprio PC, x86

# 3a. um ELF x86-64 (o Python deste computador serve de cobaia)
x86 = os.path.join(TMP, "x86")
shutil.copy(sys.executable, x86) if os.name != "nt" else None
if os.path.isfile(os.path.join(WORK, "r1collect")):
    # o r1collect compilado para o PC dentro do WSL: ELF x86-64
    ok, msg = aceita(os.path.join(WORK, "r1collect"), "x86")
    check("ELF x86-64 recusado", not ok, msg[:100])
    check("e o motivo fala de arquitetura", "MIPS" in msg or "arquitetura" in msg,
          msg[:100])

# 3b. big-endian forjado: troca o byte EI_DATA de um ELF bom
if os.path.isfile(base):
    with open(base, "rb") as fh:
        dados = bytearray(fh.read())
    dados[5] = 2                       # EI_DATA = big-endian
    be = os.path.join(TMP, "bigendian")
    with open(be, "wb") as fh:
        fh.write(bytes(dados))
    ok, msg = aceita(be, "big-endian")
    check("big-endian recusado", not ok, msg[:100])
    check("o motivo diz big-endian, sem repetir a palavra",
          "big-endian" in msg and "little-endian-endian" not in msg, msg[:110])

    # 3c. 64 bits forjado
    dados2 = bytearray(open(base, "rb").read())
    dados2[4] = 2                      # EI_CLASS = 64 bits
    b64 = os.path.join(TMP, "64bits")
    with open(b64, "wb") as fh:
        fh.write(bytes(dados2))
    ok, msg = aceita(b64, "64 bits")
    check("64 bits recusado", not ok, msg[:100])

# 3d. nem e ELF
naoelf = os.path.join(TMP, "naoelf")
with open(naoelf, "wb") as fh:
    fh.write(b"#!/bin/sh\necho eu nao sou um ELF\n")
ok, msg = aceita(naoelf, "script")
check("arquivo que nao e ELF recusado", not ok, msg[:100])

# 3e. um mipsel DINAMICO de verdade: mesma arquitetura, so que sem -static.
# Um /bin/echo do WSL nao serviria — ele e x86, e seria recusado pela
# arquitetura antes de a checagem de estatico entrar em cena.
r = Runner(log=Log("nul"), wsl_distro="Ubuntu")
zig = None
try:
    from r1lastfm import zigsetup
    achado = zigsetup.find_installed(r)
    zig = achado[0] if achado else None
except Exception:
    pass
din = os.path.join(TMP, "dinamico")
if zig:
    fonte = os.path.join(TMP, "oi.c")
    with open(fonte, "w", encoding="utf-8") as fh:
        fh.write("int main(void){return 0;}\n")
    r.posix_path_extra = zig
    # O `-dynamic` e necessario: para alvos musl o zig linka estatico por
    # padrao, entao sem ele o binario sairia estatico e o teste nao provaria
    # nada. Com ele sai um ELF que pede /lib/ld-musl-mipsel.so.1.
    r.posix(f"zig cc -target mipsel-linux-musleabihf -dynamic -o "
            f"{r.to_posix_path(din)} {r.to_posix_path(fonte)} 2>&1",
            mutating=False, quiet=True)
    r.posix_path_extra = ""
if os.path.isfile(din):
    ok, msg = aceita(din, "dinamico")
    check("mipsel dinamico recusado", not ok, msg[:100])
    # O motivo tem de dizer o que ha de errado, e em qualquer idioma. Antes
    # este teste procurava so as palavras em portugues; passou meses sem
    # rodar (faltava o Zig) e, quando rodou, acusou uma mensagem em ingles
    # perfeitamente correta. Agora ele exerce os dois idiomas — o que de
    # quebra prova que a mensagem esta traduzida.
    from r1lastfm import idioma as _id
    guardado = _id.atual()
    palavras = {"pt": ("estátic", "dinâmic", "bibliotec"),
                "en": ("static", "dynamic", "librar", "interpreter")}
    for lang, esperadas in palavras.items():
        _id.definir(lang)
        _ok, m = aceita(din, "dinamico")
        check(f"o motivo explica o problema em {lang}",
              any(p in m.lower() for p in esperadas), m[:120])
    _id.definir(guardado)
else:
    print("   (nao consegui gerar um mipsel dinamico; pulando)")

print()
print("=" * 74)
print("4. mensagem de sucesso legivel")
print("=" * 74)
linhas = []
log2 = Log(os.path.join(SCRATCH, "t_conferir2.log"))
log2.add_sink(lambda nivel, m: linhas.append(m))
if os.path.isfile(os.path.join(WORK, "r1collect.mipsel")):
    conferir(os.path.join(WORK, "r1collect.mipsel"), log2, "Coletor")
    texto = " ".join(linhas)
    check("diz o nome, o tamanho e a arquitetura",
          "Coletor" in texto and "MIPS" in texto and "estático" in texto,
          texto[-90:])
    check("nao repete 'endian'", texto.count("endian") <= 1, texto[-90:])
    check("os campos ficam separados por virgula, nao por ponto",
          "bytes, 32 bits" in texto, texto[-90:])

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
