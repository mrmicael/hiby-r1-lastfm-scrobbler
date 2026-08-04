<h1 align="center">Scrobbler do Last.fm para o HiBy R1</h1>

<p align="center">
  <b>Scrobbla tudo o que você toca — arquivos locais <i>e</i> Tidal —
  inclusive o que você ouviu sem rede nenhuma.</b><br>
  Sem root. Sem mexer no firmware. Nunca escreve no banco do player.
</p>

<p align="center">
  <img alt="Licenca: MIT" src="https://img.shields.io/badge/licen%C3%A7a-MIT-blue">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="Sem dependencias" src="https://img.shields.io/badge/depend%C3%AAncias-nenhuma-brightgreen">
  <img alt="Aparelho" src="https://img.shields.io/badge/aparelho-HiBy%20R1-lightgrey">
  <img alt="Idiomas" src="https://img.shields.io/badge/interface-EN%20%2B%20PT--BR-informational">
</p>

<p align="center">
  <a href="#o-que-ele-faz">Recursos</a> ·
  <a href="#passo-a-passo">Instalar</a> ·
  <a href="#o-que-ele-custa-de-bateria">Bateria</a> ·
  <a href="#como-funciona-por-dentro">Como funciona</a> ·
  <a href="#segurança-sem-enfeite">Segurança</a> ·
  <a href="README.md">English</a>
</p>

---

O R1 não tem scrobbling. Este programa põe um coletor minúsculo dentro do
aparelho, que anota o que você ouve — inclusive offline, no avião, no carro —
e manda tudo para o Last.fm depois. Se o WiFi do R1 já estiver ligado, ele
manda sozinho, sem PC nenhum no meio.

Funciona no **HiBy R1 comum** (Ingenic X1600, MIPS32 little-endian, firmware
de fábrica 1.6 com ADB).

```bash
python r1lastfm.py
```

<p align="center">
  <img src="docs/janela-pt.png" width="800"
       alt="A janela do programa: a explicação de como funciona e o cartão da chave de API do Last.fm">
</p>

Uma janela só, seis cartões, de cima para baixo. Nada escondido em menu, e
cada cartão diz o que vai fazer antes de fazer.

<p align="center">
  <img src="docs/janela-aparelho.png" width="800"
       alt="O cartão do aparelho: coletor instalado e rodando, 57 execuções anotadas, com os intervalos">
</p>

A interface está em **inglês e português**, inglês por padrão, e dá para trocar
a qualquer momento no canto inferior direito da janela.

---

## O que ele faz

|  | |
|---|---|
| **Tidal, não só arquivo local** | Faixas transmitidas nunca entram no banco local do player — por isso um scrobbler que só lê esse banco é cego a elas. Este lê o id da faixa que o player deixa no aparelho e pergunta artista, título, álbum e duração à própria API do Tidal, com o token que já está lá. |
| **Coleta offline** | Uma viagem inteira sem rede: o que tocou fica guardado no aparelho e sai quando aparecer conexão. Nada se perde, nada é chutado. |
| **Duas saídas, ao mesmo tempo** | Sozinho pelo WiFi do R1, e/ou pelo cabo a partir do PC. Nunca se duplicam, porque o que foi aceito fica anotado no aparelho. |
| **“Tocando agora” ao vivo** | A faixa em reprodução pulsa no seu perfil do Last.fm — para arquivo local e para Tidal. |
| **Tempo ouvido honesto** | Os segundos são **medidos** — áudio realmente saindo do aparelho —, e não deduzidos do espaço entre duas linhas do histórico. Pausar suspende a contagem em vez de encerrar a faixa; uma faixa que você pulou aos 0:19 é anotada como 19 segundos e não vai. E para contar, a faixa precisa ter tocado quase até o fim: 90% dela, mais rígido que a metade com que o Last.fm se contenta. |
| **Rápido** | O scrobble aparece uns poucos segundos depois de a faixa acabar, e não num relógio de doze minutos. |
| **Registro e planilha no cartão** | `<cartao>/r1lastfm/scrobbles.csv` e `r1lastfm.log`. Tire o cartão, abra o CSV numa planilha — sem ADB, sem este programa, sem nada. |
| **Barato** | 1 ms de processador por ciclo, **zero processos filhos** parado, 880 kB de RAM. Medido no aparelho. |
| **Seu** | Sua própria chave de API do Last.fm, guardada só no seu computador. Sem conta, sem servidor, sem telemetria, nada liga para casa. |

### Em detalhe

* **Scrobbla o Tidal também.** Faixas transmitidas nunca entram no banco
  local do player, e é por isso que a maioria dos scrobblers de R1 simplesmente
  não as enxerga. Este lê o id da faixa que o player deixa no aparelho e
  pergunta os dados à própria API do Tidal, com o token que já está lá.
* **Anota offline.** Você pode passar a viagem inteira sem rede: o que tocou
  fica guardado no aparelho e vai embora quando houver conexão.
* **Manda sozinho pelo WiFi.** De doze em doze minutos o R1 olha se já existe
  rota para fora. Se existir, envia. Ele **nunca liga o rádio por conta
  própria** — quem decide isso é você.
* **Manda pelo cabo também.** Para quem nunca usa o WiFi do aparelho: plugue,
  clique em enviar, pronto. Os dois caminhos convivem sem duplicar nada.
* **“Tocando agora”, ao vivo.** A faixa em reprodução aparece pulsando no seu
  perfil, se você quiser.
* **Só conta o que você ouviu de verdade**, e conta medindo o áudio: 90% da
  faixa, ou quatro minutos, o que vier antes. O Last.fm se contenta com
  metade, e isso fazia uma faixa largada no meio subir como se tivesse sido
  ouvida — por isso a régua aqui é mais alta. Pausar no meio e voltar continua
  valendo como ter ouvido a música; pular na metade, não.
* **Envia uns poucos segundos depois** de a faixa acabar, e não num relógio de
  doze minutos.
* **Grava um registro e uma planilha no cartão**, em `<cartao>/r1lastfm/`:
  `r1lastfm.log` e `scrobbles.csv`. Tire o cartão, abra o CSV numa planilha —
  sem ADB, sem este programa, sem nada.

### A planilha do cartão

Linhas de verdade, saídas de um aparelho — faixas do Tidal, com as puladas
marcadas como tal e o título do álbum entre aspas porque tem vírgula:

```csv
started_at,started_at_epoch,artist,track,album,album_artist,seconds_heard,track_seconds,status,rowid
2026-08-01 16:36:05,1785612965,Odeal,Coming Home (feat. Jorja Smith),Coming Home (feat. Jorja Smith),,223,223,sent,1000000006
2026-08-01 16:40:11,1785613211,Wale,Overthink,Overthink,,187,207,sent,1000000007
2026-08-01 16:45:00,1785613500,Too $hort,So So So Good,"SIR TOO $HORT, VOL. 2 (DRINK & SMOKE)",,19,142,skipped,1000000008
2026-08-01 16:45:19,1785613519,Train,Mad Dog in the Fog,Mad Dog in the Fog,,227,227,sent,1000000009
2026-08-01 16:53:38,1785613980,Remi Wolf,Twiggy,Twiggy,,38,209,skipped,1000000011
```

O `status` é um de `sent`, `pending`, `playing`, `skipped`,
`track-too-short`, `too-old`, `future`, `bad-clock` ou `no-metadata` — dá para
ver não só o que foi, mas por que o resto não foi. O `playing` é a faixa que
ainda não terminou; não é recusa, e vira `pending` sozinho quando ela acaba.

## O que ele custa de bateria

Medido no aparelho, não estimado:

| | custo |
|---|---|
| coletor parado | 1 ms de processador por minuto — 0,0017% do tempo, **zero processos filhos** |
| coletor tocando | uma volta a cada 15 s, mesmo 1 ms por volta |
| memória | 880 kB de RSS |
| um envio pelo WiFi | ~0,1% de bateria |
| “tocando agora” | 10 ms por detecção; 2,4 s de processador por **hora** |

O que pesa de verdade é ter o WiFi ligado — o rádio consome 50-150 mW contra os
~260 mW do aparelho tocando, o que tira 20-40% da autonomia. Essa conta é do
WiFi, não deste programa: com o rádio desligado, o custo do coletor é
indistinguível de zero.

## Passo a passo

### 0. O que você precisa

| | |
|---|---|
| **Python 3.9+ com Tkinter** | só a biblioteca padrão; nada de `pip install` |
| **adb** (Android Platform Tools) | é como o programa fala com o R1 |

É só isso, para tudo menos um recurso opcional. Os dois programas que rodam no
R1 vêm já compilados, em [`r1lastfm/bin/`](r1lastfm/bin/) — você **não**
precisa de compilador.

**Só** se você quiser que o R1 mande sozinho pelo WiFi é que também precisa de
**WSL + Zig**, para compilar um `curl` estático para o aparelho. O programa
instala o Zig sozinho, conferindo o SHA256 publicado pelo ziglang.org. Sem
isso, todo o resto funciona: ele coleta offline e envia pelo cabo.

<details>
<summary><b>Instalando o Python (com Tkinter)</b></summary>

O Tkinter é a biblioteca gráfica em que a janela deste programa é feita. Ele
vem junto com o Python, mas em alguns sistemas é um pacote à parte — e é por
isso que ele aparece aqui em vez de ser dado como certo.

**Windows** — pegue o instalador em
[python.org/downloads](https://www.python.org/downloads/). Duas caixas
importam:

* marque **Add python.exe to PATH** na primeira tela;
* deixe **tcl/tk and IDLE** marcado em *Optional Features* — esse é o Tkinter.

**macOS** — o instalador de
[python.org/downloads](https://www.python.org/downloads/) já traz um Tk que
funciona, e é o caminho fácil. Se preferir o Homebrew, o Tkinter é uma fórmula
separada:

```sh
brew install python python-tk
```

**Linux** — o Tkinter quase sempre é um pacote separado:

```sh
sudo apt install python3 python3-tk        # Debian, Ubuntu, Mint
sudo dnf install python3 python3-tkinter   # Fedora
sudo pacman -S python tk                   # Arch
sudo zypper install python3-tk             # openSUSE
```

**Confira que deu certo:**

```sh
python -c "import tkinter; print('Tkinter', tkinter.TkVersion)"
```

Um número de versão quer dizer que está tudo pronto. `ModuleNotFoundError: No
module named 'tkinter'` quer dizer que o Python está instalado mas o pacote do
Tk não — instale com a linha do seu sistema acima. O `python r1lastfm.py
--check` diz a mesma coisa com todas as letras, junto com tudo o mais de que
ele precisa.

> No Linux, pode não existir `python` e sim `python3`. Se for o seu caso, use
> `python3` nos dois comandos.

</details>

<details>
<summary><b>Instalando o adb</b></summary>

Baixe o Android Platform Tools do seu sistema:
<https://developer.android.com/tools/releases/platform-tools>

* **Windows** — extraia em `C:\platform-tools`. Esse é um dos lugares onde este
  programa procura, então não precisa de mais nada.
* **macOS** — `brew install android-platform-tools`.
* **Linux** — `sudo apt install adb` (ou o equivalente da sua distribuição).

Confira com `python r1lastfm.py --check`.
</details>

<details>
<summary><b>Instalando o WSL (Windows, opcional)</b></summary>

Só faz falta para o envio pelo WiFi e o “tocando agora”. Num PowerShell como
administrador:

```powershell
wsl --install -d Ubuntu
```

Reinicie e abra o Ubuntu uma vez, para ele terminar de se configurar. Não
precisa instalar o Zig — o programa faz isso quando você mandar compilar.
</details>

### 1. Registre a sua própria chave de API do Last.fm

Vá em <https://www.last.fm/api/account/create> (o programa tem um botão que
abre a página). Preencha um nome — algo como *meu scrobbler do R1* — e a
descrição. O resto pode ficar em branco. Envie, e copie os dois valores que
aparecem: **API key** e **Shared secret**.

Cole os dois no cartão 1 e clique em *Guardar*.

> **Por que a sua chave, e não uma que já viesse no programa?** Um segredo
> compartilhado publicado num repositório público não é segredo. Qualquer um
> poderia se passar pelo aplicativo, e o Last.fm o revogaria assim que
> percebesse — quebrando para todo mundo. Registrar leva um minuto e a chave é
> sua.

A chave fica só no seu computador, no `config.json`. Ela não é a sua senha, e o
programa nunca vê a sua senha em momento nenhum.

### 2. Autorize a sua conta

Clique em *Autorizar no navegador*, no cartão 2. Abre uma página do próprio
Last.fm, onde você aprova o acesso. Volte e clique em *Já autorizei — concluir*.

O que volta é uma **chave de sessão**, não a sua senha. Dá para revogá-la a
qualquer momento em *last.fm → Configurações → Aplicativos*.

### 3. Ligue o R1 e instale o coletor

No aparelho: **System → USB working mode → Device**. Depois plugue o cabo.

> ADB e USB-DAC dividem o mesmo controlador USB e são mutuamente exclusivos: com
> o modo em DAC, o `adbd` nem sobe, e a lista de aparelhos fica vazia
> igualzinho a um cabo ruim. Confira também se o cabo transmite dados — muitos
> só carregam.

No cartão 3, clique em **Instalar / atualizar**. É só isso — os programas que
vão para o aparelho já vêm compilados.

*(O botão **Compilar** ao lado é para quem prefere compilar os dois programas
do aparelho por conta própria. Se você fizer isso, o seu é usado no lugar do
que veio junto. Precisa do Zig, que o programa instala sozinho.)*

### 4. Reinicie o R1 — e leia isto se ele não voltar sozinho

O coletor é acrescentado ao `/usr/data/init.sh`. Reinicie uma vez e olhe o
cartão 3.

**No firmware de fábrica da HiBy ele vai dizer “⚠ este firmware não o inicia no
boot”, e isso não é erro seu.** Nada no firmware original executa o
`/usr/data/init.sh`. Isto foi conferido no pacote 1.6 de verdade, não deduzido:
o `/usr/bin/hiby_player.sh` de lá tem quatorze linhas e não contém a string
`/usr/data` em lugar nenhum, e nenhum outro script, arquivo de init ou binário
daquela imagem executa coisa alguma vinda de área gravável. O `/` é montado
`squashfs (ro)`, então também não dá para remendar com o aparelho ligado.

O `init.sh` é uma convenção que os firmwares **modificados** criaram — o mod de
podcast traz um `hiby_player.sh` remendado que o executa. Se você tem um
desses, o cartão 3 diz *“Inicia junto com o player”* e nada disto se aplica.

Se não tem, há dois caminhos, e todo o resto funciona igual nos dois:

* **Remende o seu próprio firmware — a solução definitiva.** O cartão 3 ganha
  um botão **Resolver o auto-start…** sempre que detecta um firmware que não
  vai iniciar o coletor. Ele pega o seu `r1.upt` de fábrica, acrescenta a
  linha que falta e grava um pacote novo, que você instala pelo menu de
  atualização do próprio player. Ele também **liga o ADB no boot**, coisa que
  o firmware de fábrica nunca faz — e sem isso este programa não enxerga um R1
  recém-saído da caixa até você achar o interruptor escondido de
  desenvolvedor.

  Pela linha de comando, se preferir:

  ```bash
  python3 ferramentas/remendar_firmware.py --entendi-o-risco --com-adb r1.upt r1-autostart.upt
  ```

  Um pacote gerado assim já foi instalado num R1 de verdade e deu boot: 1.6 de
  fábrica, coletor subindo sozinho, ADB no ar, cabo funcionando na hora.

  Ele muda dois arquivos e mais nada, e prova isso antes de gravar qualquer
  coisa: repete o laço de verificação do próprio atualizador do aparelho — lê
  o manifesto, percorre os pedaços pelos nomes encadeados de md5, confere cada
  um contra a lista, soma os tamanhos — e depois desempacota a própria saída e
  compara os 4.718 arquivos com a sua entrada: conteúdo, permissão e dono.
  Precisa de `squashfs-tools`, `genisoimage` e `p7zip-full` (no Windows, rode
  dentro do WSL). Ele nunca baixa nem distribui firmware da HiBy — o arquivo é
  você que fornece.

  **Gravar firmware não tem volta por software.** Ponha um `.upt` bom no
  cartão *antes* de gravar. Se alguma instalação travar em *Upgrading…*,
  desligue e ligue segurando **power + volume acima** — ele instala o firmware
  bom do cartão. Não grave com a bateria baixa nem a partir de um cartão com
  erros de leitura.

* Aperte **Iniciar agora** no cartão 3
  sempre que plugar o cabo. Daí ele segue rodando — offline, sem cabo — até
  você desligar o player. O equivalente à mão:

  ```
  adb shell "setsid /usr/data/scrobble/r1scrobbled </dev/null >/dev/null 2>&1 &"
  ```

O que você ouviu com ele parado **não** se perde: o que é lido é o histórico do
próprio player, então o coletor pega tudo assim que sobe. Ele só não tem como
saber as horas exatas, e por isso as reconstrói encostadas uma na outra,
terminando no momento em que acordou.

A partir daqui já funciona tudo pelo cabo. **Se você nunca quiser usar WiFi,
acabou**: ouça música, plugue quando quiser, clique em *Trazer a fila* e
*Enviar ao Last.fm*.

### 5. (Opcional) Envio automático pelo WiFi

No cartão 4, nesta ordem:

1. **Compilar o curl** — 20 a 30 minutos, uma vez por máquina. Ele baixa as
   fontes do curl e do Mbed-TLS dos sites oficiais dos dois projetos e compila
   para o MIPS do R1, no seu computador.
2. **Baixar certificados** — o pacote raiz que o projeto curl publica. Sem ele o
   aparelho não tem como conferir com quem está falando.
3. **Ativar envio pelo WiFi** — é o que leva a chave de sessão e os dois
   programas para o aparelho.
4. **Enviar agora (teste)** — prova que funciona sem esperar os doze minutos.

Marque *Mostrar “tocando agora” no meu perfil* se quiser o live scrobbling. Ele
é aplicado na hora, sem reinstalar nada.

### Conferir sem abrir a janela

```bash
python r1lastfm.py --check
```

E para ver tudo o que ele *faria*, sem tocar no aparelho:

```bash
python r1lastfm.py --dry-run
```

`--lang pt` / `--lang en` força um idioma só naquela execução, sem mudar a sua
preferência.

## Como funciona por dentro

O R1 mantém um SQLite em `/usr/data/usrlocal_media.db` com uma tabela
`HISTORY_TABLE`. Ela diz **o que** tocou e **em que ordem**, mas não guarda a
hora de nada — e é a hora que o Last.fm precisa.

Então o coletor (`collector.c`, um leitor de SQLite escrito à mão, ~770 linhas,
sem libsqlite) olha o banco de tempos em tempos e anota o **relógio do
aparelho** no momento em que cada linha nova aparece. Isso dá a hora em que a
faixa começou. A duração de cada faixa também não está no banco: é calculada de
`size * 8 / bit_rate`, o que bateu com o tempo real dentro de meio segundo nos
testes.

**Quanto você ouviu é medido, não deduzido.** O atalho óbvio — o espaço entre
duas linhas do histórico — é tempo de relógio, não de música, e quebra de três
jeitos que acontecem todo dia: você pausa e o espaço conta a pausa como
escuta; o coletor sobe com música já tocando e a faixa leva crédito por um
tempo em que ninguém estava olhando; a última faixa de uma sessão não tem
linha seguinte nenhuma. Em vez disso o coletor conta os segundos em que sai
som do aparelho, e anota o total.

Pausar não encerra a faixa, porque o aparelho diz a diferença: o dispositivo
de áudio fecha, mas o player mantém o **arquivo** aberto. Medido ao vivo, com
a pausa apertada na mão — 50 s tocando, 50 s pausado com o arquivo ainda
aberto, 29 s tocando de novo, e a linha do histórico nunca mudou, porque
retomar não escreve nada. Som parado e nenhum arquivo aberto quer dizer que a
reprodução acabou de verdade.

A medição carrega a própria incerteza junto: o estado do áudio é olhado de
tantos em tantos segundos, então cada vez que ele começa ou para, o instante
exato se perde dentro de um intervalo. Essa incerteza é somada e vai junto, e
a régua dos 90% é aplicada com ela — senão uma faixa ouvida até o fim seria
recusada por alguns segundos que ninguém teria como contar. Ela nunca derruba
a régua em mais de dez pontos.

Detalhes que só aparecem mexendo no aparelho de verdade, e que estão
documentados nos comentários do código:

* o player grava a linha do histórico **quando a faixa termina**, não quando
  começa — medido em 194 s numa faixa de 3min14;
* todo valor TEXT no banco carrega um byte NUL no fim (o player grava strings
  em C);
* o `most_played.db` do cartão está corrompido de fábrica (uma linha mistura o
  nome de uma faixa com o caminho de outra); só o mtime dele é usado, nunca o
  conteúdo;
* o banco é aberto **somente para leitura, e numa cópia** — o player nunca vê
  este programa.

O envio de dentro do aparelho é feito pelo `r1send.c`, que monta e assina o lote
(MD5 sobre os parâmetros ordenados + segredo, como a API do Last.fm exige) e
chama um `curl` estático. O daemon (`r1scrobbled.sh`) é ash de busybox e dorme
num `read -t` sobre um fifo, que custa 34× menos que chamar `sleep` — é por isso
que ele não cria processo nenhum enquanto espera.

## Onde ficam as coisas

**Neste computador**, em `%LOCALAPPDATA%\R1LastFm` (Windows),
`~/Library/Application Support/R1LastFm` (macOS) ou `~/.local/share/r1-lastfm`
(Linux):

* `config.json` — sua chave de API, a chave de sessão do Last.fm e o idioma;
* `registros/` — o log completo de cada sessão, com os comandos exatos, de forma
  que qualquer etapa possa ser refeita à mão;
* `trabalho/` — os binários compilados.

**No aparelho**, em `/usr/data/scrobble`: a fila, a lista do que já foi enviado,
e (se você ativar o envio pelo WiFi) a chave de sessão. Ficam lá de propósito —
assim usar o programa de outro computador não reenvia nem perde nada.

## Segurança, sem enfeite

* O programa **nunca vê a sua senha**. A autorização acontece numa página do
  próprio Last.fm; o que volta é uma chave de sessão, revogável quando você
  quiser em *last.fm → Configurações → Aplicativos*.
* Se você ativar o envio automático, essa chave é **gravada no aparelho**, em
  `/usr/data/scrobble/sk` com permissão 600. Ela não dá acesso à sua senha, mas
  **quem tiver ADB no aparelho consegue lê-la**. Se isso incomodar, use só o
  envio pelo cabo: funciona igual, e nada sai do PC.
* Sem o pacote de certificados no aparelho, o daemon **se recusa a enviar**, em
  vez de entregar a chave sem conferir com quem está falando.
* Nenhum binário é baixado pronto. O `curl` é compilado na sua máquina, a partir
  das fontes oficiais do curl e do Mbed-TLS, e o que sair ainda passa por uma
  checagem de ELF antes de ir para o aparelho.

## Desinstalar

O botão **Remover**, no cartão 3, tira tudo: os programas, o bloco do `init.sh`
e (se você mandar) a fila. Nada fora de `/usr/data/scrobble` e do
`/usr/data/init.sh` é tocado em momento nenhum.

## Não funcionou?

O log da sessão tem o comando exato de cada passo — é o primeiro lugar para
olhar, e ele está desenhado para poder ser refeito à mão linha por linha. Alguns
casos comuns:

* **“diz instalado mas não está rodando / nunca inicia sozinho”** — no firmware
  de fábrica ele não tem como. Ver o [passo 4](#4-reinicie-o-r1--e-leia-isto-se-ele-não-voltar-sozinho):
  nada na imagem original executa o `/usr/data/init.sh`. O cartão 3 avisa
  quando é o seu caso. Use **Iniciar agora**, ou um firmware remendado.
* **“não aparece nada no Last.fm depois de reiniciar”** — se o cartão 3 *diz*
  *Inicia junto com o player*, então o seu `init.sh` pode ter um `exit` antes do
  bloco do scrobbler; o programa insere o bloco **antes** do primeiro `exit`
  justamente por isso.
* **“ouvi um álbum inteiro e registrou 0 segundos”** / **“contou como ouvida
  inteira assim que começou”** — corrigido na versão 8. O player grava a linha
  do histórico quando a faixa **começa**, não quando acaba (observado ao vivo
  no aparelho: a linha mudou no mesmo segundo em que a faixa mudou, com o áudio
  ainda tocando por mais 45s). O código assumia o contrário, então o espaço
  entre duas linhas — que é quanto a *primeira* tocou — ia parar na *segunda*.
  Atualize o aparelho (cartão 3) para receber a correção.
* **“não tem scrobbles.csv no meu cartão”** — corrigido na versão 8. O programa
  que escreve a planilha só era instalado junto com o envio por WiFi; quem
  montou o coletor pelo cabo e parou por aí nunca teve planilha nenhuma. Agora
  ele vai junto com o coletor, e o cartão 3 mostra o caminho exato do arquivo.
* **“o envio automático não manda”** — o R1 não liga o WiFi sozinho. Ligue-o no
  aparelho e espere até doze minutos, ou use *Enviar agora (teste)*.
* **“scrobbles antigos não sobem”** — o Last.fm recusa timestamps de mais de 14
  dias. Nada a fazer.

## Rodando os testes

```bash
python testes/t_scrobble_all.py
```

Doze módulos: o leitor de SQLite em C contra o SQLite de verdade, o daemon
rodando sob busybox ash, a reconstrução da fila, a assinatura, o envio
automático, o “tocando agora”, as edições no `init.sh`, a API de aparelho contra
um adb falso, a conferência de ELF, a própria janela, e o catálogo de traduções.

Os testes que falam com a API real do Last.fm são pulados a menos que você passe
a sua chave:

```bash
LASTFM_API_KEY=... LASTFM_API_SECRET=... python testes/t_scrobble_all.py
```

## Traduzindo

Toda frase que o usuário vê mora em [`r1lastfm/textos.py`](r1lastfm/textos.py),
uma chave por mensagem, uma entrada por idioma. Para acrescentar um idioma,
ponha o código dele em `IDIOMAS`, em
[`r1lastfm/idioma.py`](r1lastfm/idioma.py), e uma entrada correspondente em
cada chave. Depois rode:

```bash
python testes/t_idioma.py
```

Ele varre o código-fonte inteiro, junta toda chave que alguém pede, e diz
exatamente quais faltaram — inclusive aquelas cujos `{campos}` não batem com o
original em inglês.

## Créditos

Escrito com [Claude Code](https://claude.com/claude-code) (Anthropic).

O formato de arquivo do SQLite, o comportamento do `HISTORY_TABLE` do R1 e os
números de bateria acima foram todos levantados no aparelho, medindo — não
estimando.

Licença MIT, em [LICENSE](LICENSE).
