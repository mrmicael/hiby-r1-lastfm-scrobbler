# -*- coding: utf-8 -*-
"""O remendador de firmware: desativado, e com o defeito travado no lugar.

Este arquivo existe por causa do pior erro do projeto. O remendador gerou um
pacote que NAO INSTALA: um aparelho ficou preso na tela "Upgrading..."
indefinidamente e so foi recuperado pondo um firmware bom no cartao e ligando
com power + volume acima.

A causa: a ISO de fabrica tem Joliet, e eu gerava so com Rock Ridge. Os nomes
dos pedacos tem 52 caracteres; no ISO 9660 puro viram ROOTFS_S.000;1 e o md5
que o atualizador confere some junto. Sem Joliet ele procurava arquivos que,
para ele, nao existiam.

O que doi nao e o bug — e que eu tinha conferencia de sobra e nenhuma delas
olhava para o recipiente. Cadeia de md5, conteudo do squashfs, permissao, dono
e sintaxe do lancador: tudo certo, tudo dentro do pacote. Conferir o recheio e
nao a embalagem da confianca sem dar garantia.

Entao aqui ficam tres coisas: que ele continua desativado, que a chamada do
gerador de ISO carrega o -J, e que a conferencia do recipiente acontece antes
de qualquer pacote existir.
"""
import os as _os, sys as _sys
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _RAIZ)
import ast, subprocess, sys

for f in (sys.stdout, sys.stderr):
    try: f.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

FERRAMENTA = _os.path.join(_RAIZ, "ferramentas", "remendar_firmware.py")
falhas = []


def check(rot, ok, extra=""):
    print(f"   {'OK ' if ok else 'FALHA'} {rot}{('  ' + extra) if extra else ''}")
    if not ok:
        falhas.append(rot)


fonte = open(FERRAMENTA, encoding="utf-8").read()
arv = ast.parse(fonte)

print("=" * 74)
print("1. nao roda sem que a pessoa reconheca o risco")
print("=" * 74)
# A primeira versao gerou um pacote que travou um aparelho. O defeito foi
# achado e corrigido, mas nenhum pacote deste script foi instalado ainda —
# entao ele nao roda sozinho, e o aviso tem de contar a historia inteira e
# dizer como recuperar, ANTES de qualquer coisa acontecer.
r = subprocess.run([sys.executable, FERRAMENTA, "entrada.upt", "saida.upt"],
                   capture_output=True, text=True)
check("recusa rodar sem o reconhecimento", r.returncode != 0, f"rc={r.returncode}")
saida = (r.stdout or "") + (r.stderr or "")
check("avisa que nenhum pacote foi instalado ainda",
      "has been installed" in saida)
check("conta o que aconteceu da primeira vez",
      "did NOT install" in saida or "does not install" in saida)
check("manda por um firmware bom no cartao ANTES", "BEFORE you flash" in saida)
check("e diz como recuperar um aparelho preso", "volume-up" in saida)

print()
print("=" * 74)
print("2. a ISO e gerada com Joliet — foi a falta dele que travou o aparelho")
print("=" * 74)
# A chamada do genisoimage, lida do proprio codigo. Se alguem tirar o -J um
# dia, isto acusa antes de virar um aparelho na tela de atualizacao.
chamadas = []
for n in ast.walk(arv):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "rodar"):
        args = [a.value for a in n.args if isinstance(a, ast.Constant)]
        if any(isinstance(a, str) and a.startswith("-o") for a in args) or \
           any(isinstance(a, str) and a == "-V" for a in args):
            chamadas.append(args)
check("achei a chamada do gerador de ISO", bool(chamadas), str(chamadas[:1]))
if chamadas:
    ch = chamadas[0]
    check("ela passa -J (Joliet)", "-J" in ch, str(ch))
    check("e continua passando -R (Rock Ridge)", "-R" in ch, str(ch))

print()
print("=" * 74)
print("3. o recipiente e conferido, e antes do resto")
print("=" * 74)
check("existe uma conferencia de recipiente",
      "def conferir_recipiente" in fonte)
check("ela compara Joliet entre entrada e saida",
      "joliet" in fonte.lower() and "conferir_recipiente" in fonte)
check("ela e chamada com a ENTRADA e a SAIDA",
      "conferir_recipiente(args.entrada, args.saida)" in fonte)
i_rec = fonte.find("conferir_recipiente(args.entrada")
i_con = fonte.find("conferir_saida(args.saida")
check("e vem antes da conferencia do conteudo",
      0 < i_rec < i_con, f"recipiente em {i_rec}, conteudo em {i_con}")
check("sem o isoinfo ela nao e pulada, e sim recusada",
      "cannot be skipped" in fonte)

print()
print("=" * 74)
print("4. os nomes longos sao conferidos pelos DOIS caminhos")
print("=" * 74)
# Nao se sabe por qual dos dois o atualizador le; entao os dois tem de
# funcionar.
check("confere os nomes via Rock Ridge e via Joliet",
      '("Rock Ridge", ["-R"])' in fonte and '("Joliet", ["-J"])' in fonte)

print()
print("=" * 74)
print("FALHAS:", falhas if falhas else "nenhuma")
sys.exit(1 if falhas else 0)
