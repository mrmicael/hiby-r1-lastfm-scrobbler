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
print("3b. o manifesto e reescrito E conferido")
print("=" * 74)
# O ota_update.in e o que o atualizador do aparelho realmente le: ele declara
# o md5 e o tamanho de cada imagem. Eu trocava o md5 no NOME do arquivo-marca
# e deixava o manifesto declarando o md5 do rootfs ORIGINAL. O atualizador
# remontava, comparava, nao fechava, e ficava esperando para sempre.
#
# Isso estava escrito no /etc/ota_bin/local_ota_update.sh do proprio firmware.
# Deduzir o formato pelos nomes dos arquivos em vez de ler o programa que os
# consome foi o que fez eu passar perto duas vezes sem acertar.
check("existe a reescrita do manifesto",
      "def reescrever_manifesto" in fonte)
check("ela troca img_md5 e img_size",
      'saida.append(f"img_md5={soma}")' in fonte
      and 'saida.append(f"img_size={tamanho}")' in fonte)
check("e so na entrada do rootfs, nao na do kernel",
      "dentro_do_rootfs" in fonte)
check("recusa se nao achar a entrada do rootfs",
      "could not find the rootfs entry" in fonte)
check("existe a conferencia do manifesto contra os pedacos",
      "def conferir_manifesto" in fonte)
check("ela confere kernel E rootfs",
      '"rootfs" not in declarado or "kernel" not in declarado' in fonte)
check("e roda sobre o pacote PRONTO, nao sobre o rascunho",
      "conferir_manifesto(os.path.join(conf" in fonte)

print()
print("=" * 74)
print("3c. a LISTA de md5 dos pedacos e escrita (era criada vazia)")
print("=" * 74)
# O ota_md5_<nome>.<md5 do inteiro> nao e uma marca: e um arquivo com o md5
# de CADA pedaco, uma linha por pedaco. O atualizador copia esse arquivo e le
# a linha i+1 para conferir o pedaco i. Eu o criava vazio, entao o `sed -n
# "1p"` devolvia nada e ele desistia no primeiro pedaco — tela de
# "Upgrading..." para sempre, duas vezes, no aparelho de duas pessoas.
check("a lista de md5 e gravada com uma linha por pedaco",
      'out.write("".join(s + "\\n" for s in somas))' in fonte)
check("e nao ha mais nenhum arquivo ota_md5 criado vazio",
      'f"ota_md5_rootfs.squashfs.{md5(novo)}"' not in fonte)
check("a conferencia le a lista e compara pedaco a pedaco",
      'linhas[i] != real' in fonte)
check("e recusa uma lista curta ou vazia",
      "len(linhas) < len(pedacos)" in fonte)
check("ela refaz o encadeamento de nomes como o atualizador faz",
      'f"{nome}.{i:04d}.{anterior}"' in fonte)
check("e confere o total contra o img_size, como o laco dele",
      'total < int(campos.get("img_size"' in fonte)

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
