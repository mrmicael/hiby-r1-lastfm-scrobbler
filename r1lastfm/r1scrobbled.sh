#!/bin/sh
# r1scrobbled — anota o que o R1 tocou e manda ao Last.fm quando dá.
#
# Roda no aparelho, iniciado pelo /usr/data/init.sh.
#
# Ele **nunca liga o WiFi**. O rádio é de longe o maior consumidor do
# aparelho, e ligá-lo por conta própria estragaria a autonomia por uma coisa
# que não tem pressa nenhuma. O que ele faz é olhar de doze em doze minutos:
# se o WiFi já estiver no ar — porque você ligou para o Tidal, ou deixou
# ligado —, aproveita a carona e manda o que estiver acumulado. Se não
# estiver, continua anotando e tenta de novo mais tarde.
#
# Sem WiFi nunca, a fila só cresce e o instalador manda pelo cabo. Os dois
# caminhos funcionam ao mesmo tempo e não brigam: o que já foi aceito fica
# anotado no próprio aparelho.
#
# Como ele custa quase nada
# -------------------------
# O laço parado não cria processo nenhum. Os testes
# `[ "$ARQ" -nt "$MARCA" ]` são internos ao shell — dois stat() e mais nada —
# e só quando um banco realmente muda é que alguma coisa é copiada ou
# executada.
#
# A espera também é interna: em vez de chamar `sleep`, que custaria um
# fork+exec por volta, o laço faz `read -t` num fifo que ninguém escreve.
# Medido: 0,25 ms por ciclo contra 8,5 ms com `sleep` — 34 vezes menos. Nem
# todo busybox aceita `read -t`, então na partida isso é conferido de verdade
# (cronometrando uma espera curta) e, se não funcionar, o `sleep` volta.
#
# De onde vêm os dados
# --------------------
# /usr/data/usrlocal_media.db, tabela HISTORY_TABLE. O player insere uma linha
# por reprodução e o rowid sempre cresce, inclusive ao repetir a mesma faixa
# (ele apaga a linha antiga e escreve outra no fim). Então "rowid maior que o
# último visto" é exatamente "o que tocou desde a última olhada".
#
# O banco é copiado para /tmp antes de ser lido. Assim o player nunca disputa
# o arquivo com a gente, e uma cópia pega no meio de uma gravação apenas falha
# a leitura e é refeita no ciclo seguinte — o r1collect abre só para leitura e
# não tem nenhum caminho de escrita.
#
# O segundo relógio
# -----------------
# A linha entra no banco quando a faixa COMEÇA — observado ao vivo: o player
# trocou de faixa e a linha apareceu no mesmo segundo, com o áudio ainda
# tocando por mais quarenta e cinco. Então a hora da linha É o começo dela.
#
# Quanto ela tocou, porém, não se deduz de carimbo nenhum: é MEDIDO. A cada
# volta, com o pcm aberto, o daemon soma o tempo desde a volta anterior, e ao
# fechar a faixa escreve o total no marcador t1.
#
# Deduzir do espaço entre uma linha e a seguinte parece equivalente e não é —
# esse espaço é tempo de relógio, não tempo de música. Ele quebra em três
# situações que acontecem todo dia, e as três viraram relato:
#
#   • pausa. Pelo espaço entre linhas a faixa "durou" a pausa inteira.
#   • o daemon subindo com música já tocando. A linha daquela faixa já está no
#     banco, e o espaço até ela é tempo em que o daemon nem existia — a faixa
#     subia como ouvida no instante em que começava, aparecendo no perfil como
#     scrobble e como "ouvindo agora" ao mesmo tempo.
#   • a última faixa de uma sequência, sem seguinte que a feche.
#
# Pausar não fecha faixa: o pcm fecha, mas o player mantém o ARQUIVO aberto, e
# é essa diferença que separa pausa de fim. Medido no aparelho, com a pausa
# apertada na mão: 50 s de pcm=1, 50 s de pcm=0 com o arquivo ainda aberto,
# 29 s de pcm=1 — e o rowid nunca mudou, porque retomar não escreve linha
# nenhuma no histórico.
#
#     pcm=1                  → tocando, conta o tempo
#     pcm=0 e arquivo aberto → pausado, não conta e não fecha
#     pcm=0 e nada aberto    → parou, fecha a faixa
#
# O marcador f1 continua saindo na hora em que o som para: ele é o teto que as
# versões antigas do PC usam para deduzir o fim, e serve de diagnóstico. Quem
# lê o t1 não precisa dele.
#
# O most_played.db do cartão também é vigiado, mas ele NÃO fecha faixa: uma
# mudança nele prova que algo estava acontecendo naquela hora, ou seja é
# limite inferior, nunca superior. Só o mtime, sem abrir o arquivo — ele tem
# linhas corrompidas pelo próprio player (uma com o nome de uma faixa e o
# caminho de outra) e não é confiável como fonte de metadados.
#
# Tocando agora
# --------------
# Opcional, desligado por padrão. Quando ligado, o daemon avisa o Last.fm da
# faixa em reprodução e ela aparece pulsando no seu perfil. Isso exige o WiFi
# ligado, e é o WiFi que custa bateria — a detecção em si são 10 ms por volta.
#
# A faixa atual poderia sair do banco, que ganha a linha no começo dela —
# mas a linha diz o que COMEÇOU, e entre isso e a próxima leitura pode ter
# havido troca. A fonte é direta: o arquivo que o player mantém aberto,
# visto em /proc/PID/fd.
#
# O Tidal
# -------
# Faixas transmitidas NÃO entram no HISTORY_TABLE — ele é o histórico da mídia
# local. Por isso o scrobbler nasceu cego ao Tidal, que num R1 com conta é
# quase tudo o que se ouve.
#
# O que existe é o id numérico da faixa, em UTF-16LE, no começo do
# /usr/data/user.ini. Conferido no aparelho: tocando três faixas seguidas, os
# ÚNICOS bytes que mudaram no arquivo foram os desse campo. Com o id, a API do
# Tidal devolve artista, título, álbum e duração — e o token para perguntar já
# está no aparelho, em /usr/data/tat, posto lá pelo próprio player.
#
# Aqui o começo da faixa é CONHECIDO, e não deduzido: o daemon vê a troca
# acontecer. A linha da fila leva a hora de início explícita, e o tempo ouvido
# deixa de ser estimativa.
#
# Duas armadilhas, as duas verificadas no aparelho:
#   - o id do Tidal não é apagado quando você volta a ouvir arquivos locais,
#     então "tocando Tidal" é `pcm aberto E nenhum arquivo de áudio aberto`;
#   - perguntar isso a cada volta custaria 14 ms em vez de 0,25, então só se
#     pergunta quando o user.ini muda ou quando há faixa em curso.
#
# Marcadores na fila
# ------------------
#   p1  uma reprodução, com os metadados
#   t1  <rowid> <n> <incerteza> fim — a faixa tocou <n> segundos, dos quais
#       até <incerteza> podem ter escapado da contagem. É a única linha daqui
#       que diz quanto se ouviu; todo o resto é hora de relógio. O campo "fim"
#       marca a faixa como encerrada; sem ele ela ainda está tocando. Duas t1
#       do mesmo rowid se SOMAM — um reinício no meio da música deixa metade
#       da medição numa e metade na outra
#   m1  o most_played foi tocado nesta hora. Prova que algo tocava, não
#       que algo parou — limite inferior, nunca superior
#   i1  nada mais aconteceu depois desta hora. NÃO fecha faixa: é
#       justamente enquanto uma faixa longa toca que nada acontece
#   f1  o áudio parou nesta hora, visto no pcm. Teto para quem não tem t1
#   b1  o daemon começou (houve desligamento ou reinício antes disto)
#   a1  as próximas n linhas já estavam no banco quando ele começou: tocaram
#       sem ninguém olhando, e o PC reconstrói as horas em vez de deduzi-las
#   c1  o relógio estava obviamente errado; o PC vai desconfiar das horas
#
# Para desligar tudo: apague /usr/data/scrobble e reinicie. Nada mais no
# aparelho é tocado.

DIR=/usr/data/scrobble
# O banco do player tem DOIS lugares possíveis, e quem escolhe é o dono do
# aparelho — na tela, pela opção `tf_music_db_enable`. Ligada, o player passa
# a gravar no cartão e o de dentro para de ser atualizado.
#
# Os dois caminhos estão escritos dentro do próprio /usr/bin/hiby_player:
#
#     /data/usrlocal_media.db                   com a opção desligada
#     /data/mnt/sd_0/.temp/usrlocal_media.db    com a opção ligada
#
# Isto aqui apontava fixo para o primeiro, e quem tinha a opção ligada via o
# programa dizer "rodando" e colher zero faixa para sempre — foi relatado
# exatamente assim. O DB é escolhido em achar_banco(), não aqui; este valor é
# só o ponto de partida, para as mensagens de erro terem o que dizer antes da
# primeira procura.
DB=/usr/data/usrlocal_media.db
DB_INTERNO=/usr/data/usrlocal_media.db
# Onde procurar o banco no cartão, relativo a cada raiz de $CARTOES.
DB_NO_CARTAO=.temp/usrlocal_media.db
# Qual banco o marcador de rowid está seguindo. Os dois bancos têm numeração
# própria, então trocar de um para o outro sem perceber faria o daemon reler o
# histórico inteiro ou pular tudo. Ver achar_banco().
BANCO_ATUAL=$DIR/banco
MAIS=/usr/data/mnt/sd_0/.temp/most_played.db
COLETOR=$DIR/r1collect
REMETENTE=$DIR/r1send
CURL=$DIR/curl
FILA=$DIR/fila.tsv
ESTADO=$DIR/estado
# Ponto de controle da faixa que está sendo medida agora. Existe só enquanto
# há faixa aberta; some quando ela fecha. Ver anotar_medida.
MEDINDO=$DIR/medindo
ENVIADOS=$DIR/enviados
SK=$DIR/sk
SEGREDO=$DIR/segredo
APIKEY=$DIR/apikey
MARCA=$DIR/.visto
MARCA2=$DIR/.visto2
MARCA3=$DIR/.visto3
# A trava fica em /tmp, e não junto do resto em /usr/data, de propósito.
#
# /usr/data sobrevive ao desligamento, e um arquivo de pid que sobrevive ao
# desligamento é veneno: no boot seguinte aquele número pertence a outro
# processo qualquer, o daemon conclui que já há outra instância e sai calado.
# Foi o que aconteceu num R1 de verdade — depois de reiniciar, o scrobbler
# inteiro ficava morto e sem deixar rastro. /tmp é tmpfs: some no boot, que é
# exatamente o comportamento certo para um arquivo de pid.
TRAVA=/tmp/.r1sc.rodando
COPIA=/tmp/.r1sc.db
PARCIAL=/tmp/.r1sc.tsv
CORPO=/tmp/.r1sc.post
IDS=/tmp/.r1sc.ids
RESP=/tmp/.r1sc.resp
CORPO_NP=/tmp/.r1sc.np
RESP_NP=/tmp/.r1sc.npresp
META=/tmp/.r1sc.meta
LOG=/tmp/.r1sc.log
TICK=/tmp/.r1sc.tick

API=https://ws.audioscrobbler.com/2.0/
API_HOST=ws.audioscrobbler.com
# O caminho sozinho, para o ajudante residente: ele recebe host e caminho
# separados, porque guarda uma conexão por host.
API_CAMINHO=/2.0/
# Dois lugares onde o pacote de certificados pode estar: no cartão (útil
# quando /usr/data está apertado) ou junto do próprio scrobbler.
CACERT_SD=/data/mnt/sd_0/.r1lastfm/cacert.pem
CACERT_LOCAL=$DIR/cacert.pem

# Onde o cartão de memória pode estar montado. O firmware não é coerente
# consigo mesmo — /usr/data/mnt/sd_0 e /data/mnt/sd_0 aparecem os dois no
# mesmo aparelho —, então os candidatos são testados na hora em vez de
# escolhidos por adivinhação.
CARTOES="/usr/data/mnt/sd_0 /data/mnt/sd_0 /mnt/sd_0"
# A pasta e os arquivos que ficam lá. O ponto disto é poder tirar o cartão,
# pôr no computador e ler — sem ADB, sem este programa, sem nada.
PASTA_SD=r1lastfm
sd=""
LOG_SD=""
CSV_SD=""
# Para o aviso de "sem remetente" sair uma vez, e não a cada volta do laço.
avisou_sem_remetente=0
# O registro no cartão é cortado quando passa disto, guardando a metade mais
# recente. Um log que cresce para sempre num cartão é um bug com atraso.
LOG_SD_MAX=262144

# Intervalos, em segundos. RAPIDO vale enquanto há atividade; depois de
# QUIETOS ciclos sem nada o laço passa para LENTO.
RAPIDO=15
LENTO=60
QUIETOS=8

# Quantos segundos esperar depois de o banco mudar antes de lê-lo.
#
# A linha entra no banco no mesmo instante em que a faixa começa, que é quando
# o player está alocando os buffers dela. Ler e criar processos nesse segundo
# somava a nossa carga à dele, e o aparelho reiniciava — trocar de faixa
# rápido derrubava o R1, e tirar o coletor resolvia.
ASSENTAR=5

# Por quanto tempo, no máximo, o envio pode ser adiado por trocas de faixa.
# Sem este teto, quem fica pulando adia para sempre e nada sobe.
TETO_ESPERA=150

# De quantos em quantos segundos ouvidos a medição é gravada em disco.
#
# É o tamanho do prejuízo num travamento: o que passou disto já está salvo.
# Trinta segundos custam duas reescritas de um arquivo de vinte bytes por
# minuto de música, e evitam perder a contagem de uma faixa inteira.
T1_PASSO=30

# Quanto tempo uma faixa pausada continua sendo a faixa em curso.
#
# Enquanto o player mantém o arquivo aberto, a pausa é pausa e a faixa espera.
# Isto é só o limite de bom senso para o caso de alguém pausar e largar o
# aparelho ligado: passada meia hora, o que já foi medido é escrito e a faixa
# sai da mão do daemon, em vez de ficar presa até a próxima música.
PAUSA_MAX=1800

# "Tocando agora": avisa o Last.fm da faixa em reprodução, o que faz aparecer
# aquele indicador pulsando no seu perfil. Desligado por padrão, porque só
# funciona com o WiFi ligado — e é o WiFi que custa bateria, não isto.
#
# Medido no R1: a detecção custa 10 ms, dos quais 5 são o fork. Tocando
# música dá 2,4 s de processador por hora (0,07% do tempo). O rádio associado
# consome ~50-150 mW contra os ~260 mW do aparelho tocando, ou seja tira uns
# 20-40% da autonomia. A conta é essa: o recurso é barato, o WiFi não é.
AGORA=0

# Acompanhar o Tidal. Ligado por padrão: sem isto o scrobbler é cego a tudo
# que você ouve por streaming, que num R1 com conta Tidal costuma ser a maior
# parte. Custa duas leituras de /proc por ciclo (as mesmas que o "tocando
# agora" já fazia) e uma consulta à API do Tidal por faixa nova — que só
# acontece quando há Tidal tocando, e nesse caso a rede já está de pé.
TIDAL=1

# Pode usar a rede ENQUANTO uma faixa do Tidal está tocando? Não, por padrão.
#
# Um único interruptor para as duas coisas que precisariam dela — buscar os
# dados da faixa e anunciar o "tocando agora" —, porque separá-las não faria
# sentido: são o mesmo risco.
#
# Não é medo abstrato. Num R1 de verdade o aparelho travou no instante exato em
# que o anúncio saiu, com o dono assistindo — e isso depois de a v21 já ter
# afastado o anúncio 20 segundos da troca de faixa e garantido que ele nunca
# dividisse ciclo com a consulta.
#
# O que eu sei, e o que não sei:
#
#   • medindo à parte, cinco requisições HTTPS seguidas no meio de uma faixa do
#     Tidal não incomodaram o player — pico de 896 KB, fragmentação intocada;
#   • e mesmo assim o anúncio derrubou;
#   • e o aparelho também já reiniciou uma vez com o daemon PARADO e nenhuma
#     requisição feita, o que quer dizer que existe pelo menos uma causa que
#     não é esta.
#
# Não tenho um modelo que explique as três coisas ao mesmo tempo. Ligar isto por
# padrão seria apostar a estabilidade do aparelho de quem instala num palpite
# meu. Quem quiser tentar é só pôr 1 aqui: toda a maquinaria da janela calma
# continua no lugar, e é ela que passa a valer.
#
# Com isto em 0, quase nada se perde. O cache é lido normalmente — ele não usa
# rede —, então uma faixa que você já ouviu vira linha da fila no instante em
# que acaba. Só a faixa NOVA espera o áudio parar para ser identificada. E o
# scrobble sobe inteiro nos dois casos, com a hora certa.
#
# Tocando do cartão, o "tocando agora" segue pelo AGORA e não passa por aqui:
# aquele caminho nunca deu problema e não é afetado.
# LIGADO. Ele veio desligado na v22 porque o aparelho travava, e eu ainda não
# sabia por quê. Agora sei: era o r1send reservando 8,7 MB de uma vez, o que
# levava o sistema ao matador de memória, que matava o player. Isso está
# consertado na raiz, e a lógica de anúncio daqui — janela calma, cache, nunca
# duas requisições no mesmo ciclo — é a mesma que passou nos testes.
REDE_NO_TIDAL=1

# De quanto em quanto tempo olhar se dá para enviar. Doze minutos é o piso
# garantido: mesmo sem nada acontecer, a fila sai nesse ritmo.
ENVIO=720
# Quando uma tentativa falha, a seguinte demora o dobro, até este teto. Sem
# isso um aparelho sem rede ficaria acordando o curl para nada.
ENVIO_MAX=7200

# Mandar assim que a faixa termina, em vez de esperar os doze minutos.
#
# Dá para fazer porque o tempo ouvido de uma faixa fica determinado no
# instante em que a linha dela aparece: ele é o intervalo até o evento
# ANTERIOR, que já passou. Não falta nada para decidir.
#
# O custo é real e vale dizer em voz alta: um envio custa uns 0,1% de
# bateria, então um álbum de doze faixas custa ~1,2% em vez de ~0,1%. Só
# acontece com o WiFi já ligado — e ter o rádio ligado já custa 20-40% da
# autonomia, ao lado do qual isto é troco. Com o WiFi desligado nada muda:
# a fila espera, como sempre.
#
# O valor abaixo é o quanto do relógio de doze minutos se deixa correndo. O
# envio acontece na primeira verificação em que `desde_envio + intervalo`
# alcança o total, então mantê-lo em RAPIDO faz o envio cair na verificação
# seguinte à faixa ter sido anotada — uns 15 segundos, não os 12 minutos.
#
# Pôr um valor MAIOR que RAPIDO adiaria por mais um ciclo, o que juntaria mais
# faixas por envio. Não vale: quem pula cinco faixas seguidas já gera as cinco
# linhas numa leitura só do banco, e elas saem juntas de qualquer jeito.
IMEDIATO=1

# Antes disto (1 de janeiro de 2024) o relógio claramente não foi acertado.
# O Last.fm recusa horas com mais de 14 dias, então é melhor marcar do que
# mandar lixo.
PISO=1704067200

[ -r "$DIR/conf" ] && . "$DIR/conf"

# A espera do envio imediato sai do RAPIDO, e por isso vem depois do conf.
#
# O comentário do IMEDIATO sempre disse "mantê-lo em RAPIDO faz o envio cair
# na verificação seguinte", mas o número estava fixo em 15 — igual ao RAPIDO
# padrão, e por isso a diferença nunca apareceu. Quem baixasse o RAPIDO para
# ter o scrobble mais depressa continuava esperando os quinze segundos, sem
# nada em lugar nenhum explicando por quê.
ESPERA_IMEDIATO=45
# Quarenta e cinco segundos depois de a faixa fechar, e não quinze.
#
# Enviar executa o curl — 1,6 MB, mais do que a memória livre do aparelho — e
# fazê-lo logo depois de uma troca de faixa é despejar isso em cima do player
# no pior momento. A cada nova troca o relógio é reagendado (ver
# adiantar_envio), então uma sequência de pulos não dispara envio nenhum: ele
# sai quando a reprodução assentar, com tudo junto.
#
# O preço é o scrobble aparecer no perfil meio minuto mais tarde. É pouco
# perto de o aparelho reiniciar no meio da música.

# Uma instância só. Existir um processo com aquele pid não basta: o número
# pode ter sido reaproveitado por qualquer outro programa. Só conta se a linha
# de comando desse processo for a deste mesmo daemon.
if [ -f "$TRAVA" ]; then
    velho=$(cat "$TRAVA" 2>/dev/null)
    if [ -n "$velho" ] && [ -d "/proc/$velho" ]; then
        if grep -qa r1scrobbled "/proc/$velho/cmdline" 2>/dev/null; then
            exit 0
        fi
    fi
    rm -f "$TRAVA"
fi

mkdir -p "$DIR" 2>/dev/null
echo $$ > "$TRAVA"
[ -f "$FILA" ] || : > "$FILA"

# Primeira execução de todas: o histórico que já está no aparelho não tem
# hora nenhuma associada — essas faixas foram ouvidas sabe-se lá quando, e
# todas apareceriam com a hora de agora. Mandar isso ao Last.fm encheria o
# perfil de dezenas de execuções falsas no mesmo minuto.
#
# Então a primeira rodada serve de marco zero: o estado pula para o topo do
# histórico e só o que tocar daqui para frente é anotado.
primeira=0
if [ ! -f "$ESTADO" ]; then
    primeira=1
    echo 0 > "$ESTADO"
fi

# O cartão está aí e dá para escrever nele?
#
# É refeito de tempos em tempos, e não só na partida: o cartão pode ser posto
# depois de ligar o aparelho, e nesse caso o registro passa a existir a partir
# dali em vez de nunca. Custa um mkdir e um touch, uma vez a cada meia hora.
# Há um sistema de arquivos montado neste caminho?
#
# O ponto de montagem do cartão continua existindo quando não há cartão: é um
# diretório comum na memória interna, e ele passa no teste de escrita como
# qualquer outro. Sem esta pergunta o daemon anunciava "registro e planilha no
# cartao" com o slot vazio, gravava tudo na memória interna e, quando o cartão
# voltasse e montasse por cima, esses arquivos ficavam invisíveis — para quem
# usa, a planilha simplesmente sumia.
#
# Quando o /proc/mounts não puder ser lido, responde SIM: valia antes e vale
# de novo, porque recusar o cartão de quem tem um é pior do que aceitar o de
# quem não tem.
esta_montado() {
    [ -r /proc/mounts ] || return 0
    _real=$(cd "$1" 2>/dev/null && pwd -P) || return 1
    [ -n "$_real" ] || return 1
    while read -r _d _p _resto; do
        [ "$_p" = "$_real" ] && return 0
    done < /proc/mounts
    return 1
}

achar_cartao() {
    for c in $CARTOES; do
        [ -d "$c" ] || continue
        esta_montado "$c" || continue
        if mkdir -p "$c/$PASTA_SD" 2>/dev/null &&
           : > "$c/$PASTA_SD/.escrita" 2>/dev/null; then
            rm -f "$c/$PASTA_SD/.escrita"
            sd="$c/$PASTA_SD"
            LOG_SD="$sd/r1lastfm.log"
            CSV_SD="$sd/scrobbles.csv"
            return 0
        fi
    done
    sd=""; LOG_SD=""; CSV_SD=""
    return 1
}

# Escolhe qual dos dois bancos do player está valendo agora.
#
# A opção `tf_music_db_enable`, na tela do aparelho, move o banco para o
# cartão. Ligada, o de dentro para de ser atualizado — e o daemon, que olhava
# só para ele, colhia zero faixa para sempre enquanto dizia estar rodando.
#
# A escolha é pela hora de modificação, e não pela opção: ler a opção exigiria
# saber onde o player guarda o ajuste do usuário (o /usr/resource/config.json
# é só o valor de fábrica, e neste aparelho ele diz 1 com o banco de dentro
# sendo atualizado normalmente). A hora de modificação não depende de decifrar
# formato nenhum: o banco que o player está escrevendo é o que muda.
#
# Trocar de banco é o caso perigoso. Os dois têm numeração de linha própria, e
# seguir a numeração do antigo no novo faria o daemon reler o histórico
# inteiro ou pular tudo. Quando o caminho muda, o marcador é recomeçado do
# topo do banco novo — como numa primeira instalação — e o log diz que foi
# feito. Perde-se o que estava lá antes; inventar duplicata seria pior.
achar_banco() {
    _novo=""
    _quando=0

    # Primeiro, a resposta direta: qual banco o PLAYER tem aberto.
    #
    # Isto não é dedução — é o arquivo que está sendo usado, agora, por quem o
    # usa. Foi a resposta a uma objeção justa: "não seria melhor ler a opção
    # `tf_music_db_enable` e ter a certeza, em vez de comparar horas?".
    #
    # Ler a opção seria melhor se desse. Não dá: o único config.json do
    # sistema está no squashfs somente-leitura, é o valor de fábrica, e num R1
    # real ele diz 1 (cartão) com o player usando o banco interno. Não existe
    # cópia gravável dele em lugar nenhum da /usr/data. Ler aquilo daria a
    # resposta errada com toda a confiança do mundo.
    #
    # O descritor aberto responde a mesma pergunta sem intermediário. A
    # comparação por hora de modificação continua abaixo, para quando o player
    # não estiver rodando (o daemon sobe antes dele, no boot) ou para um
    # r1collect anterior a esta versão, que não conhece a terceira linha.
    _p=""; _l=""; _b=""
    { read -r _p; read -r _l; read -r _b; } <<FIM_BANCO
$("$COLETOR" estado 2>/dev/null)
FIM_BANCO
    if [ -n "$_b" ] && [ -f "$_b" ]; then
        _novo=$_b
    fi
    # O player não respondeu — no boot ele sobe depois do daemon. Se já havia
    # um banco anotado e ele continua existindo, fica com ele.
    #
    # Isto evita uma troca inventada: sem o player para dizer, a hora de
    # modificação pode apontar para o outro banco só porque nada foi tocado
    # ainda desde a última sessão, e trocar recomeça o marcador à toa. O que
    # valia ontem continua valendo até alguém provar o contrário.
    if [ -z "$_novo" ]; then
        _guardado=$(cat "$BANCO_ATUAL" 2>/dev/null)
        [ -n "$_guardado" ] && [ -f "$_guardado" ] && _novo=$_guardado
    fi

    # Nem o player, nem nada anotado: aí sim a hora de modificação decide.
    # É a reserva, e tem um ponto cego que o descritor aberto não tem — logo
    # depois de a opção mudar, e antes de a primeira faixa tocar, o banco
    # antigo ainda é o mais recente. Serve para a primeira instalação e para
    # um r1collect anterior a esta versão.
    if [ -z "$_novo" ]; then
        for _c in $DB_INTERNO; do
            [ -f "$_c" ] || continue
            _t=$(data_do_arquivo "$_c")
            if [ "$_t" -gt "$_quando" ] 2>/dev/null; then
                _quando=$_t; _novo=$_c
            fi
        done
        for _c in $CARTOES; do
            [ -f "$_c/$DB_NO_CARTAO" ] || continue
            _t=$(data_do_arquivo "$_c/$DB_NO_CARTAO")
            if [ "$_t" -gt "$_quando" ] 2>/dev/null; then
                _quando=$_t; _novo=$_c/$DB_NO_CARTAO
            fi
        done
    fi
    # Nenhum dos dois existe: mantém o que estava, para as mensagens de erro
    # continuarem apontando para algum lugar.
    [ -n "$_novo" ] || return 1

    _antes=$(cat "$BANCO_ATUAL" 2>/dev/null)
    if [ "$_novo" = "$_antes" ]; then
        DB=$_novo
        return 0
    fi

    # Quando recomeçar o marcador do topo.
    #
    #   já havia um caminho anotado e ele mudou  → recomeça: a numeração do
    #     banco novo não tem relação nenhuma com a do antigo.
    #   não havia caminho anotado (primeira vez desta versão) e o banco é o
    #     INTERNO → não recomeça: era exatamente esse que todas as versões
    #     anteriores seguiam, e o marcador continua valendo.
    #   não havia caminho anotado e o banco é o do CARTÃO → recomeça: o
    #     marcador que está lá conta linhas de outro arquivo. É o caso de quem
    #     tinha a opção ligada e atualizou o coletor — o relato que trouxe
    #     isto à tona.
    _recomecar=1
    [ -z "$_antes" ] && [ "$_novo" = "$DB_INTERNO" ] && _recomecar=0

    DB=$_novo
    echo "$DB" > "$BANCO_ATUAL" 2>/dev/null || :
    # A marca de mtime vale para o arquivo de antes; sem apagá-la, a volta
    # seguinte acharia que o banco novo não mudou e não colheria nada.
    rm -f "$MARCA"

    if [ "$_recomecar" = 0 ]; then
        registrar "banco do player: $DB"
        return 0
    fi

    # Recomeçar é pôr o marcador no topo do banco novo, aqui e agora — e não
    # apagar o marcador. Apagá-lo faria a colheita seguinte pedir "tudo desde
    # o zero" e despejar o histórico inteiro na fila de uma vez.
    _topo=""
    if cp -f "$DB" "$COPIA" 2>/dev/null; then
        if _s=$("$COLETOR" "$COPIA" 0 "$PARCIAL" 2>>"$LOG"); then
            _topo=${_s##* }
        fi
        rm -f "$COPIA" "$PARCIAL"
    fi
    if [ -n "$_topo" ]; then
        echo "$_topo" > "$ESTADO"
        registrar "banco do player agora e $DB (antes: ${_antes:-interno})." \
                  "A numeracao e outra, entao o marcador recomeca no rowid" \
                  "$_topo e so o que tocar daqui para frente e anotado"
    else
        registrar "banco do player agora e $DB, mas nao consegui le-lo para" \
                  "recomecar o marcador; tento de novo no proximo ciclo"
        rm -f "$BANCO_ATUAL"
    fi
    return 0
}

# A hora de modificação de um arquivo, em segundos. O busybox do R1 não tem
# `stat -c %Y`, mas o `date -r` dele aceita o arquivo.
data_do_arquivo() {
    date -r "$1" +%s 2>/dev/null || echo 0
}

# Corta o registro do cartão quando ele cresce demais, guardando a metade
# recente. Sem `tail -c`, que nem todo busybox tem: conta as linhas e fica com
# as últimas.
aparar_log_sd() {
    [ -n "$LOG_SD" ] && [ -f "$LOG_SD" ] || return 0
    tam=$(wc -c < "$LOG_SD" 2>/dev/null) || return 0
    [ "$tam" -gt "$LOG_SD_MAX" ] 2>/dev/null || return 0
    linhas=$(wc -l < "$LOG_SD" 2>/dev/null) || return 0
    if tail -n $((linhas / 2)) "$LOG_SD" > "$LOG_SD.novo" 2>/dev/null; then
        mv -f "$LOG_SD.novo" "$LOG_SD" 2>/dev/null
    else
        rm -f "$LOG_SD.novo"
    fi
}

# Uma linha de registro. Vai para /tmp sempre, e para o cartão quando houver
# um — com data, porque quem lê o arquivo no computador semanas depois não
# tem como saber a que dia aquilo se refere.
#
# A escrita no cartão nunca pode derrubar o daemon: se o cartão sumiu no meio,
# o redirecionamento falha, o `||` engole, e a próxima passada por
# achar_cartao descobre que não há mais cartão.
registrar() {
    echo "$*" >> "$LOG"
    [ -n "$LOG_SD" ] || return 0
    echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG_SD" 2>/dev/null || sd=""
}

# Reescreve o CSV do cartão a partir da fila. É o r1send quem faz, porque ele
# já sabe reconstruir a fila e decidir o que cada faixa virou.
atualizar_csv() {
    [ -n "$CSV_SD" ] || return 0
    [ -s "$FILA" ] || return 0
    # No máximo uma vez por minuto.
    #
    # Isto executa o r1send e reescreve a planilha inteira no cartão, e era
    # chamado a cada faixa. Numa sequência de pulos viravam vários processos e
    # várias reescritas em segundos, competindo com o player pela memória. A
    # planilha é para ler depois, no computador — atrasar um minuto não custa
    # nada a ninguém. Quem chama com "ja" (o desligamento) não espera.
    if [ "$1" != ja ]; then
        # Fora da janela calma, nem isto: reescrever a planilha é um r1send
        # mais a gravação inteira no cartão. Quem chama com "ja" é o
        # desligamento, e aí o áudio já acabou.
        [ "$tid_rede_ok" != 1 ] && return 0
        _ag_csv=$(date +%s)
        if [ -n "$csv_em" ] && [ $((_ag_csv - csv_em)) -lt 60 ] 2>/dev/null; then
            return 0
        fi
        csv_em=$_ag_csv
    fi
    if [ ! -x "$REMETENTE" ]; then
        # Sem o r1send não há planilha, e ficar calado sobre isso foi
        # exatamente o que gerou o relato "não tem scrobbles.csv no meu
        # cartão". A partir da v8 ele é instalado junto com o coletor; esta
        # mensagem é para quem ainda está com uma instalação antiga.
        if [ "$avisou_sem_remetente" != 1 ]; then
            avisou_sem_remetente=1
            registrar "sem $REMETENTE: a planilha nao pode ser escrita." \
                      "Reinstale pelo cartao 3 do programa no PC."
        fi
        return 0
    fi
    "$REMETENTE" relatorio "$FILA" "$ENVIADOS" "$CSV_SD" 2>>"$LOG" || :
}

# Fecha a faixa em curso: escreve quanto dela foi realmente ouvido.
#
# A linha t1 leva três coisas: de que faixa se fala (rowid), quantos segundos
# de áudio aberto foram contados, e quanto disso é incerto. A terceira importa:
# um número medido de olhada em olhada não pode ser cobrado como se fosse
# exato, e é o PC quem faz essa conta.
#
# A incerteza não é o RAPIDO nem o LENTO: é a soma dos intervalos em que o
# áudio começou ou parou sem ninguém ver a hora exata. Ver o acumulador, no
# laço, para o porquê de ela acompanhar as trocas e não o ritmo do laço.
fechar_faixa_atual() {
    [ -n "$atual_rowid" ] || return 0
    # O "fim" é o que separa "tocou 35 dos 133 segundos e acabou aí" de "está
    # no segundo 35 e continua tocando". Sem ele a planilha do cartão chamaria
    # de "skipped" a música que a pessoa está ouvindo naquele instante — uma
    # acusação falsa do programa contra ele mesmo.
    #
    # Sai mesmo valendo zero: não é a medida, é o aviso de que acabou. Faixa
    # pulada no primeiro segundo tem zero a dizer e precisa ser fechada.
    # "fimnat" = a faixa chegou ao fim sozinha; "fim" = foi interrompida.
    #
    # A diferença é observável e não precisa de chute: quem pula deixa o áudio
    # tocando até o instante do pulo, então o pcm ainda está aberto quando a
    # linha da faixa seguinte entra. Quando a faixa acaba por conta própria, o
    # áudio para ANTES — e é isso que `parado_desde` registra.
    #
    # Sem esta distinção, uma faixa tocada inteira era recusada por "faltou
    # tempo" toda vez que a duração estivesse superestimada: ela vem de
    # tamanho x 8 / taxa, e num arquivo com capa e tags o cálculo sobra. Foi o
    # relato de 3:21 de 3:27, com os seis segundos finais em silêncio.
    if [ -n "$parado_desde" ]; then
        _fim=fimnat
    else
        _fim=fim
    fi
    printf 't1\t%s\t%s\t%s\t%s\n' \
           "$atual_rowid" "$atual_ouvido" "$atual_granul" "$_fim" >> "$FILA"
    registrar "faixa $atual_rowid fechada: ${atual_ouvido}s ouvidos" \
              "(incerteza ${atual_granul}s)"
    rm -f "$MEDINDO"
    atual_rowid=""
    atual_ouvido=0
    atual_gravado=0
    atual_granul=0
    pcm_antes=1
}

# Guarda a medição em curso num arquivinho, para um travamento não levá-la.
#
# O fim nem sempre acontece. Este aparelho reinicia sozinho — travou duas
# vezes enquanto esta versão era escrita —, e num travamento nenhum trap roda:
# a contagem, que só existia na memória do daemon, morreria com ele. Foi o que
# aconteceu com a faixa 272 aqui, de 293 s: o aparelho reiniciou no meio dela
# e ela ainda assim subiu como ouvida por inteiro, porque sem medida a conta
# volta a deduzir do relógio.
#
# O ponto de controle vai para um arquivo próprio, e não como linhas na fila,
# porque a fila não é podada nunca: uma linha a cada trinta segundos de música
# a faria crescer dez vezes mais rápido, para sempre, e ela é lida inteira a
# cada envio. Aqui é um arquivo de vinte bytes reescrito no lugar.
#
# Na partida seguinte o que estiver aqui vira um t1 fechado — ver recuperar_
# medicao. Fechar normalmente apaga o arquivo, então nunca há os dois.
anotar_medida() {
    [ -n "$atual_rowid" ] || return 0
    printf '%s %s %s\n' "$atual_rowid" "$atual_ouvido" "$atual_granul" \
        > "$MEDINDO" 2>/dev/null || :
    atual_gravado=$atual_ouvido
}

# A medição que ficou órfã de um travamento entra na fila como faixa fechada.
recuperar_medicao() {
    [ -f "$MEDINDO" ] || return 0
    _r=""; _n=""; _g=""
    read -r _r _n _g < "$MEDINDO" 2>/dev/null || :
    rm -f "$MEDINDO"
    [ -n "$_r" ] && [ -n "$_n" ] || return 0
    [ "$_n" -gt 0 ] 2>/dev/null || return 0
    printf 't1\t%s\t%s\t%s\tfim\n' "$_r" "$_n" "${_g:-$RAPIDO}" >> "$FILA"
    registrar "medicao interrompida recuperada: faixa $_r com ${_n}s"
}

# Acabou de fechar uma faixa: não há razão para esperar o relógio dos doze
# minutos. Encurta para a espera curta, que existe só para juntar uma
# sequência de pulos num envio só em vez de um envio por faixa.
#
# Vale para os DOIS jeitos de uma faixa fechar. Só a troca de faixa chamava
# isto, e por isso a última música de cada sessão — justamente a que a pessoa
# está esperando ver aparecer — ficava até doze minutos parada na fila depois
# de o aparelho já estar em silêncio.
adiantar_envio() {
    [ "$IMEDIATO" = 1 ] || return 0
    [ "$proximo_envio" = "$ENVIO" ] || return 0
    falta=$((proximo_envio - ESPERA_IMEDIATO))
    [ "$falta" -lt 0 ] && falta=0
    # Antes isto só ANTECIPAVA o envio. Agora ele é reagendado: cada troca de
    # faixa empurra o relógio para frente de novo.
    #
    # O envio executa o curl, que são 1,6 MB — mais do que a memória livre
    # deste aparelho. Dispará-lo no meio de uma sequência de trocas rápidas
    # era pedir para travar. Reagendando, quem pula cinco faixas seguidas não
    # dispara curl nenhum: ele só sai quando a coisa acalmar, e aí manda todas
    # de uma vez, que é mais barato do que uma por faixa.
    # ...mas com teto. Reagendar sem limite fazia quem fica pulando faixa
    # nunca disparar envio nenhum: cada troca empurrava o relógio de novo e as
    # faixas ficavam paradas na fila, o que de fora parece "não contabilizou".
    # Passados TETO_ESPERA segundos desde o primeiro fecho pendente, vai.
    _ag_env=$(date +%s)
    [ -n "$pendente_desde" ] || pendente_desde=$_ag_env
    if [ $((_ag_env - pendente_desde)) -ge "$TETO_ESPERA" ]; then
        return 0
    fi
    if [ "$desde_envio" -ne "$falta" ]; then
        desde_envio=$falta
    fi
}

limpar() {
    # O que já foi medido da faixa em curso não pode morrer com o daemon.
    # Sem isto, desligar o aparelho no meio de uma música jogava fora a
    # contagem inteira dela — e desligar o aparelho no fim da última música é
    # o modo normal de terminar de ouvir.
    fechar_faixa_atual
    rm -f "$TRAVA" "$COPIA" "$PARCIAL" "$TICK" "$CORPO" "$IDS" "$RESP" \
          "$CORPO_NP" "$RESP_NP" "$META"
    exit 0
}
# INT e TERM são pedidos legítimos de parada. HUP não: ele chega toda vez que
# o shell que iniciou o daemon termina — o `adb shell` que o lançou, ou o
# supervisor no boot. Tratá-lo como pedido de parada fazia o daemon se matar
# segundos depois de subir, e foi exatamente o que aconteceu na primeira
# instalação de verdade.
trap limpar INT TERM
trap '' HUP

# A espera sem fork. O fifo é aberto para leitura E escrita, então a ponta de
# leitura nunca vê fim de arquivo e o `read -t` espera o tempo inteiro.
#
# O nome leva o pid: se por qualquer motivo houver duas instâncias subindo ao
# mesmo tempo, uma não apaga o fifo da outra entre o mkfifo e o exec.
TICK="$TICK.$$"
fifo_ok=0
motivo_espera="mkfifo nao funcionou"
_medido=-1
rm -f "$TICK"
# O `exec` sem comando aplica os redirecionamentos ao próprio shell, e para
# sempre — por isso o 2>/dev/null fica num subshell, senão o daemon perderia
# toda a saída de erro dali em diante.
if mkfifo "$TICK" 2>/dev/null && (exec 9<>"$TICK") 2>/dev/null; then
    exec 9<>"$TICK"
    # Conferir de verdade em vez de confiar: um busybox sem `read -t` faria
    # o laço girar sem parar, que é o pior desfecho possível para a bateria.
    motivo_espera="'read -t' existe mas nao esperou"
    _a=$(date +%s)
    read -t 2 _tick <&9 2>/dev/null
    _b=$(date +%s)
    _medido=$((_b - _a))
    if [ "$_medido" -ge 1 ]; then
        fifo_ok=1
    fi
fi

espera() {
    if [ "$fifo_ok" = 1 ]; then
        read -t "$1" _tick <&9 2>/dev/null || :
    else
        sleep "$1"
    fi
}

# Existe rota para fora? Lido direto do /proc com o `read` interno do shell,
# sem chamar grep nem awk: isto roda a cada doze minutos e não deve custar um
# processo. Uma linha com destino 00000000 é a rota default.
tem_rede() {
    [ -r /proc/net/route ] || return 1
    while read -r _iface destino _resto; do
        [ "$destino" = "00000000" ] && return 0
    done < /proc/net/route
    return 1
}

# A consulta ao Tidal (curl + TLS) e o maior pico de RAM do daemon inteiro —
# adiar para o ciclo seguinte (ver olhar_tidal) resolve a sobreposicao com a
# troca de faixa, mas nao ajuda se a memoria ja estiver curta por outro
# motivo. Lido do /proc com o `read` interno, sem awk nem grep: mesmo estilo
# do tem_rede, mesmo custo (quase zero).
MEM_MINIMA_KB=4000

tem_memoria() {
    [ -r /proc/meminfo ] || return 0
    while read -r _chave _valor _resto; do
        if [ "$_chave" = "MemAvailable:" ]; then
            [ "$_valor" -ge "$MEM_MINIMA_KB" ] 2>/dev/null || return 1
            return 0
        fi
    done < /proc/meminfo
    return 0
}

# Tudo pronto para mandar? Sem chave de sessão não há o que fazer, e o
# instalador é quem a coloca aqui.
pode_enviar() {
    [ -x "$REMETENTE" ] || return 1
    [ -x "$CURL" ] || return 1
    [ -s "$SK" ] || return 1
    [ -s "$SEGREDO" ] || return 1
    [ -s "$APIKEY" ] || return 1
    [ -s "$FILA" ] || return 1
    return 0
}

cacert() {
    if [ -s "$CACERT_SD" ]; then echo "$CACERT_SD"
    elif [ -s "$CACERT_LOCAL" ]; then echo "$CACERT_LOCAL"
    else echo ""
    fi
}

# O curl estático não resolve nomes neste aparelho.
#
# Ele é ligado com musl estático, e nessa combinação a thread que o curl usa
# para resolver DNS não sobe: toda requisição morre com "getaddrinfo() thread
# failed to start", mesmo com a rede funcionando e o busybox resolvendo nomes
# sem problema nenhum. Um curl compilado com --disable-threaded-resolver não
# tem isso, mas quem já tem o binário antigo não deveria precisar recompilar
# meia hora por causa disso.
#
# Então o nome é resolvido aqui, pelo busybox, e entregue pronto ao curl com
# --resolve. Funciona com os dois binários, e não custa nada: acontece no
# máximo uma vez a cada doze minutos.
resolver() {
    nslookup "$1" 2>/dev/null \
        | awk '/^Address/ { print $NF }' \
        | grep -v ':' \
        | tail -1
}

resolver_api() { resolver "$API_HOST"; }

# ---------------------------------------------------------------------------
# O ajudante de rede residente. Ver o comentário longo no r1net.c.
#
# Em resumo: com o Tidal tocando o aparelho fica com ~1,5 MB livres, e o curl
# pede ~900 KB de pico a cada chamada. O ajudante sobe no boot, quando há 22 MB
# livres, paga ali tudo o que é caro — ler e validar o pacote de certificados,
# semear o gerador aleatório, montar os contextos de TLS com seus buffers — e
# depois fica parado num fifo com a conexão aberta.
#
# Daqui em diante, mandar um pedido é escrever uma linha num descritor que já
# existe. `printf` e redirecionamento são internos do shell: não nasce processo
# nenhum, não se abre socket nenhum, não há handshake nenhum. Medido no R1:
# 688 KB residentes, e o residente NÃO cresce entre um pedido e outro.
#
# Os descritores 8 e 9 ficam abertos em leitura-e-escrita de propósito. Abrir
# um fifo só para escrita bloqueia até aparecer um leitor, e só para leitura
# bloqueia até aparecer um escritor; em leitura-e-escrita não bloqueia nunca, e
# o fifo nunca fica sem ponta — o que evita o `read` devolver EOF em roda-viva.
AJUDANTE=$DIR/r1net
FIFO_PED=/tmp/.r1sc.net
FIFO_RESP=/tmp/.r1sc.netr
# Estas nascem aqui, e não com as variáveis do laço lá embaixo: a
# subir_ajudante é chamada ANTES daquele bloco, e uma inicialização posterior
# zeraria o rede_pronta logo depois de o ajudante subir.
rede_pronta=0
http_seq=0
http_codigo=0
rede_falhas=0

subir_ajudante() {
    rede_pronta=0
    [ -x "$AJUDANTE" ] || return 1
    _aj_ca=$(cacert)
    [ -n "$_aj_ca" ] || return 1

    # Um ajudante de uma execução anterior não serve: os fifos dele são outros
    # arquivos, e ele estaria escrevendo num vazio.
    for _p in /proc/[0-9]*; do
        _c=$(tr '\0' ' ' < "$_p/cmdline" 2>/dev/null)
        case "$_c" in *r1net*) kill "${_p#/proc/}" 2>/dev/null ;; esac
    done
    rm -f "$FIFO_PED" "$FIFO_RESP"
    mkfifo "$FIFO_PED" "$FIFO_RESP" 2>/dev/null || return 1

    "$AJUDANTE" "$FIFO_PED" "$FIFO_RESP" "$_aj_ca" "$LOG" &
    _aj_pid=$!
    sleep 1
    kill -0 "$_aj_pid" 2>/dev/null || {
        registrar "r1net nao subiu; a rede segue pelo curl"
        return 1
    }
    exec 8<> "$FIFO_PED" || return 1
    exec 9<> "$FIFO_RESP" || return 1
    rede_pronta=1
    registrar "r1net de pe (pid $_aj_pid): a rede deixa de criar processos"
    return 0
}

# http_pedir <metodo> <host> <ip|-> <caminho> <corpo|-> <saida|-> <cabs|->
#
# Devolve 0 quando o servidor RESPONDEU — inclusive com 400 ou 500, igual ao
# curl, que também sai com zero nesses casos. Quem chama lê o corpo para saber
# o que o Last.fm achou; tratar um 400 como queda de rede faria o daemon perder
# as mensagens de erro dele e tentar de novo para sempre. O código fica em
# $http_codigo. Devolve 2 quando não há ajudante — o sinal para usar o curl.
http_pedir() {
    http_codigo=0
    [ "$rede_pronta" = 1 ] || return 2
    http_seq=$((http_seq + 1))
    _hid="q$http_seq"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$_hid" "$1" "$2" "$3" "$4" "$5" "$6" "$7" >&8 2>/dev/null || {
        rede_pronta=0
        return 2
    }
    # Uma resposta atrasada de um pedido que já expirou continuaria no fifo e
    # seria lida como se fosse desta. O id na resposta é o que separa as duas.
    _voltas=0
    while [ "$_voltas" -lt 4 ]; do
        _voltas=$((_voltas + 1))
        IFS='	' read -t 45 -r _rid _rcod _rby <&9 2>/dev/null || {
            # O ajudante emperrou. Sem isto TUDO para em silêncio: cada pedido
            # espera 45 s e falha, e nada mais sai. Duas vezes seguidas e ele é
            # dado por morto; a rede volta ao curl, que é pesado mas funciona.
            rede_falhas=$((rede_falhas + 1))
            registrar "r1net nao respondeu a tempo ($rede_falhas)"
            if [ "$rede_falhas" -ge 2 ]; then
                registrar "r1net dado por perdido; a rede volta pelo curl"
                rede_pronta=0
            fi
            return 1
        }
        rede_falhas=0
        [ "$_rid" = "$_hid" ] || continue
        http_codigo=$_rcod
        case "$_rcod" in
            [1-5][0-9][0-9]) return 0 ;;
            *) return 1 ;;
        esac
    done
    return 1
}

# Uma ida ao Last.fm com o lote: pelo ajudante quando ele está de pé, e pelo
# curl quando não está.
# ---------------------------------------------------------------------------
# A poda da fila.
#
# A fila só crescia, e isso não incomodava ninguém enquanto o r1send reservava
# 8,7 MB fixos: o tamanho dela não mudava nada. Quando ele passou a crescer sob
# demanda, o tamanho da fila VIROU o custo — 541 faixas custam 1,2 MB, e quem
# ouve cinquenta por dia chega ao teto de 4096 em uns dois meses. O travamento
# voltaria devagar, sozinho, sem ninguém ligar uma coisa à outra.
#
# Tirar o que o Last.fm já aceitou não perde nada: aquelas linhas não sobem de
# novo, e o que elas alimentavam é a planilha do cartão, que é histórico
# gravado lá e não depende da fila continuar inchando.
#
# Custo: em regime normal, ZERO processos. Tudo até a penúltima linha é teste
# interno do shell, e a passada do awk só acontece quando o relógio permite, a
# fila passou do tamanho, e o áudio está parado.
PODA_MIN=400
PODA_INTERVALO=21600     # seis horas

podar_fila() {
    [ -s "$ENVIADOS" ] || return 0
    [ -s "$FILA" ] || return 0
    [ $((agora - poda_em)) -ge "$PODA_INTERVALO" ] 2>/dev/null || return 0
    poda_em=$agora

    _pn=$(wc -l < "$FILA" 2>/dev/null)
    case "$_pn" in ''|*[!0-9]*) return 0 ;; esac
    [ "$_pn" -ge "$PODA_MIN" ] || return 0

    # A primeira passada lê os rowids aceitos; a segunda mantém tudo o que não
    # for p1/t1 daqueles rowids. O t1 sai junto com o p1 do mesmo rowid: ele
    # carrega o tempo medido daquela faixa e nada mais, e deixá-lo para trás
    # faria a fila crescer na própria poda.
    awk -F'\t' 'NR==FNR{m[$1]=1;next} ($1!="p1" && $1!="t1") || !($2 in m)' \
        "$ENVIADOS" "$FILA" > "$FILA.novo" 2>>"$LOG" || {
        rm -f "$FILA.novo"
        return 0
    }

    # Só troca se o resultado faz sentido: não vazio, e não maior que o
    # original. Uma fila perdida é escuta perdida, e isso não se recupera de
    # lugar nenhum — na dúvida, fica como estava.
    _pm=$(wc -l < "$FILA.novo" 2>/dev/null)
    case "$_pm" in ''|*[!0-9]*) rm -f "$FILA.novo"; return 0 ;; esac
    if [ "$_pm" -gt 0 ] && [ "$_pm" -le "$_pn" ]; then
        mv "$FILA.novo" "$FILA"
        registrar "fila podada: $_pn -> $_pm linhas (o que o Last.fm ja aceitou)"
    else
        rm -f "$FILA.novo"
    fi
}

chamar_curl() {
    http_pedir POST "$API_HOST" "${ip_api:--}" "$API_CAMINHO" \
               "$CORPO" "$RESP" -
    _rcl=$?
    [ "$_rcl" -ne 2 ] && return "$_rcl"
    if [ -n "$ip_api" ]; then
        "$CURL" -sS --max-time 45 --cacert "$1" \
            --resolve "$API_HOST:443:$ip_api" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -A "hiby-r1-scrobbler/1.0" \
            --data-binary "@$CORPO" -o "$RESP" "$API" 2>>"$LOG"
    else
        "$CURL" -sS --max-time 45 --cacert "$1" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -A "hiby-r1-scrobbler/1.0" \
            --data-binary "@$CORPO" -o "$RESP" "$API" 2>>"$LOG"
    fi
}

# Um lote. Devolve 0 se algo foi aceito, 1 se não deu, 3 se não havia nada.
mandar_lote() {
    rm -f "$CORPO" "$IDS" "$RESP"
    "$REMETENTE" preparar "$FILA" "$ENVIADOS" "$SK" "$SEGREDO" "$APIKEY" \
        "$CORPO" "$IDS" >/dev/null 2>>"$LOG"
    rc=$?
    [ "$rc" = 3 ] && return 3
    [ "$rc" = 0 ] || { registrar "preparar falhou (rc=$rc)"; return 1; }

    ca=$(cacert)
    if [ -z "$ca" ]; then
        # Sem pacote de certificados não dá para conferir quem está do outro
        # lado. Melhor não mandar a chave de sessão às cegas.
        registrar "sem cacert.pem: envio adiado (use o botao de baixar no PC)"
        return 1
    fi
    chamar_curl "$ca"
    rc=$?
    [ "$rc" = 0 ] || { registrar "curl falhou (rc=$rc)"; return 1; }

    "$REMETENTE" confirmar "$RESP" "$IDS" "$ENVIADOS" >>"$LOG" 2>&1
    rc=$?
    [ "$rc" = 0 ] || { registrar "o Last.fm nao confirmou (rc=$rc)"; return 1; }
    return 0
}

# -- "tocando agora" ---------------------------------------------------------
#
# O banco não serve para isto. Ele ganha a linha quando a faixa COMEÇA, o
# que à primeira vista serviria — mas a linha traz o que tocou, não o que
# está tocando, e entre o começo e a próxima leitura do banco pode ter
# havido troca. A fonte é outra, e direta — o
# player mantém o arquivo de áudio aberto, e /proc/PID/fd mostra qual
# (verificado no aparelho: muda ao pular de faixa).
#
# O r1collect faz a varredura inteira num exec só. Fazer isso em shell
# custaria pidof + ls + grep, quatro processos em vez de um.
anunciar() {
    # Sem cópia, pelo mesmo motivo da colheita: 624 KB para dentro da RAM na
    # troca de faixa é o que derrubava o aparelho. Falha de leitura aqui só
    # custa não achar os metadados desta faixa.
    [ -r "$DB" ] || return 1
    "$COLETOR" buscar "$DB" "$1" > "$META" 2>>"$LOG"
    rc=$?
    [ "$rc" = 0 ] || return 1

    # Um campo por linha; o r1collect já trocou controles por espaço, então
    # `read -r` lê exatamente o que ele escreveu.
    np_art=""; np_tit=""; np_alb=""; np_dur=""
    { read -r np_art; read -r np_tit; read -r np_alb; read -r np_dur; } < "$META"
    rm -f "$META"
    [ -n "$np_art" ] && [ -n "$np_tit" ] || return 1

    "$REMETENTE" agora "$SK" "$SEGREDO" "$APIKEY" "$CORPO_NP" \
        "$np_art" "$np_tit" "$np_alb" "$np_dur" >/dev/null 2>>"$LOG" || return 1

    ca=$(cacert)
    if [ -z "$ca" ]; then
        # Desistir calado aqui já custou caro: o "tocando agora" ficou
        # parecendo quebrado porque o cacert.pem tinha sumido, e nada dizia
        # isso. A queixa sai uma vez só, para não encher o registro a cada
        # volta do laço.
        if [ "$queixei_cacert" != 1 ]; then
            registrar "sem cacert.pem: nao da para conferir quem esta do outro lado, entao o 'tocando agora' fica parado. Use o botao 'Baixar certificados' no instalador."
            queixei_cacert=1
        fi
        return 1
    fi
    queixei_cacert=0
    http_pedir POST "$API_HOST" "${ip_api:--}" "$API_CAMINHO" \
               "$CORPO_NP" "$RESP_NP" -
    rc=$?
    if [ "$rc" = 2 ]; then
        if [ -n "$ip_api" ]; then
            "$CURL" -sS --max-time 20 --cacert "$ca" \
                --resolve "$API_HOST:443:$ip_api" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -A "hiby-r1-scrobbler/1.0" \
                --data-binary "@$CORPO_NP" -o "$RESP_NP" "$API" 2>>"$LOG"
        else
            "$CURL" -sS --max-time 20 --cacert "$ca" \
                -H "Content-Type: application/x-www-form-urlencoded" \
                -A "hiby-r1-scrobbler/1.0" \
                --data-binary "@$CORPO_NP" -o "$RESP_NP" "$API" 2>>"$LOG"
        fi
        rc=$?
    fi
    rm -f "$CORPO_NP" "$RESP_NP"
    # "Tocando agora" não vai para fila: se não deu, o momento passou. Não
    # vale gastar rádio tentando de novo uma faixa que já mudou.
    [ "$rc" = 0 ] || return 1
    # A duração é o que impede o MESMO anúncio de sair a cada volta do laço: o
    # olhar_tocando só reanuncia quando ela já passou. Com ela em zero, a
    # comparação é sempre verdadeira e a mesma faixa vai para o Last.fm de 15
    # em 15 segundos — foi o que aconteceu num aparelho de verdade, quando um
    # `return` posto cedo demais no caminho do ajudante pulou esta linha. Por
    # isso os dois caminhos terminam AQUI, num ponto só.
    np_dur_efetiva=$np_dur
    return 0
}

# -- o Tidal -----------------------------------------------------------------
#
# O Tidal não passa pelo banco: o HISTORY_TABLE é o histórico da mídia LOCAL, e
# uma faixa transmitida nunca entra nele. Por isso o scrobbler simplesmente não
# via o Tidal — nem para anotar, nem para o "tocando agora".
#
# O que existe é o id da faixa no /usr/data/user.ini (o r1collect lê) e, com
# ele, a API do Tidal devolve artista, título, álbum e duração. O token para
# perguntar já está no aparelho, em /usr/data/tat, posto lá pelo próprio
# player quando você entrou na sua conta — nada de credencial nova.
#
# A diferença para o caminho local é que aqui o começo da faixa é CONHECIDO: o
# daemon vê a troca acontecer. Então a linha da fila leva a hora de início
# explícita e o tempo ouvido deixa de ser estimativa.
TIDAL_INI=/usr/data/user.ini
TAT=/usr/data/tat
TIDAL_API=api.tidal.com
TIDAL_JSON=/tmp/.r1sc.tidal
SEQ=$DIR/tidal_seq
# Os rowid do Tidal moram acima de um bilhão para nunca esbarrarem nos do
# HISTORY_TABLE, que crescem de um em um e estão na casa das centenas.
TIDAL_BASE=1000000000

# O token, direto do arquivo do player. Nunca é registrado nem impresso.
tidal_token() {
    [ -s "$TAT" ] || return 1
    tr -c 'A-Za-z0-9._-' '\n' < "$TAT" 2>/dev/null \
        | awk 'length($0) > 100' | head -1
}

# O país da conta, que a API exige em toda consulta. Perguntado uma vez e
# guardado: ele não muda, e é uma requisição a menos por faixa.
tidal_pais() {
    [ -n "$tid_pais" ] && { echo "$tid_pais"; return 0; }
    t_ca=$(cacert); [ -n "$t_ca" ] || return 1
    t_tok=$(tidal_token) || return 1
    [ -n "$ip_tidal" ] || ip_tidal=$(resolver "$TIDAL_API")
    t_res=""
    [ -n "$ip_tidal" ] && t_res="--resolve $TIDAL_API:443:$ip_tidal"
    if escrever_cabecalho_tidal "$t_tok"; then
        rm -f "$TIDAL_JSON"
        http_pedir GET "$TIDAL_API" "${ip_tidal:--}" /v1/sessions \
                   - "$TIDAL_JSON" "$CAB_TIDAL"
        _rcp=$?
        rm -f "$CAB_TIDAL"
        if [ "$_rcp" = 0 ]; then
            # O `tr -cd` no fim não é enfeite: sem ele, o país sai grudado no
            # que vier junto — um `}` quando countryCode é o último campo do
            # json, ou um espaço quando o servidor formata com espaços. Ficar
            # dependendo da ordem dos campos de uma API de terceiros é frágil,
            # e um teste com servidor próprio mostrou isso na prática.
            tid_pais=$(tr ',' '\n' < "$TIDAL_JSON" | grep countryCode \
                       | tr -d '"' | cut -d: -f2 | tr -cd 'A-Za-z')
            rm -f "$TIDAL_JSON"
            case "$tid_pais" in
                [A-Za-z][A-Za-z]) echo "$tid_pais"; return 0 ;;
            esac
            tid_pais=""; return 1
        fi
        rm -f "$TIDAL_JSON"
        [ "$_rcp" = 1 ] && { tid_pais=""; return 1; }
        # rc 2 = sem ajudante; segue para o curl.
    fi
    [ -x "$CURL" ] || return 1
    tid_pais=$("$CURL" -sS --max-time 25 --cacert "$t_ca" $t_res \
        -H "Authorization: Bearer $t_tok" -H "Accept: application/json" \
        "https://$TIDAL_API/v1/sessions" 2>>"$LOG" \
        | tr ',' '\n' | grep countryCode | tr -d '"' | cut -d: -f2 \
        | tr -cd 'A-Za-z')
    case "$tid_pais" in [A-Za-z][A-Za-z]) ;; *) tid_pais=""; return 1 ;; esac
    echo "$tid_pais"
}

# O cabeçalho com o token do Tidal, num arquivo só nosso.
#
# Ele NÃO pode viajar pelo fifo: o fifo fica em /tmp e qualquer processo do
# aparelho pode lê-lo. Pelo caminho do arquivo, o ajudante lê o token
# diretamente e o que passa pelo fifo é só o nome do arquivo. O `umask` antes
# do redirecionamento é o que garante que ele nasça sem permissão para
# terceiros — criar e depois dar chmod deixaria uma fresta entre as duas
# coisas.
CAB_TIDAL=/tmp/.r1sc.cab
escrever_cabecalho_tidal() {
    [ -n "$1" ] || return 1
    _umask_antes=$(umask)
    umask 077
    rm -f "$CAB_TIDAL"
    {
        printf 'Authorization: Bearer %s\r\n' "$1"
        printf 'Accept: application/json\r\n'
    } > "$CAB_TIDAL" 2>/dev/null || { umask "$_umask_antes"; return 1; }
    umask "$_umask_antes"
    return 0
}

# Metadados de uma faixa. Preenche tid_art / tid_tit / tid_alb / tid_dur.
tidal_meta() {
    tid_art=""; tid_tit=""; tid_alb=""; tid_dur=0
    [ -x "$CURL" ] && [ -x "$REMETENTE" ] || return 1
    tem_rede || return 1
    t_ca=$(cacert); [ -n "$t_ca" ] || return 1
    t_tok=$(tidal_token) || return 1
    t_pais=$(tidal_pais) || return 1
    [ -n "$ip_tidal" ] || ip_tidal=$(resolver "$TIDAL_API")
    t_res=""
    [ -n "$ip_tidal" ] && t_res="--resolve $TIDAL_API:443:$ip_tidal"
    rm -f "$TIDAL_JSON"
    _feito=0
    if escrever_cabecalho_tidal "$t_tok"; then
        http_pedir GET "$TIDAL_API" "${ip_tidal:--}" \
                   "/v1/tracks/$1?countryCode=$t_pais" \
                   - "$TIDAL_JSON" "$CAB_TIDAL"
        _rcm=$?
        rm -f "$CAB_TIDAL"
        [ "$_rcm" = 0 ] && _feito=1
        [ "$_rcm" = 1 ] && return 1
    fi
    if [ "$_feito" = 0 ]; then
        [ -x "$CURL" ] || return 1
        "$CURL" -sS --max-time 25 --cacert "$t_ca" $t_res \
            -H "Authorization: Bearer $t_tok" -H "Accept: application/json" \
            "https://$TIDAL_API/v1/tracks/$1?countryCode=$t_pais" \
            -o "$TIDAL_JSON" 2>>"$LOG" || return 1
    fi
    # Um campo por linha, como o `r1collect buscar` já faz.
    { read -r tid_art; read -r tid_tit; read -r tid_alb; read -r tid_dur; } \
        <<FIM_META
$("$REMETENTE" tidalinfo "$TIDAL_JSON" 2>>"$LOG")
FIM_META
    rm -f "$TIDAL_JSON"
    [ -n "$tid_art" ] && [ -n "$tid_tit" ] || return 1
    case "$tid_dur" in ''|*[!0-9]*) tid_dur=0 ;; esac
    tidal_cache_gravar "$1"
    return 0
}

# Os metadados desta faixa já estão em casa? Preenche tid_art/tid_tit/tid_alb/
# tid_dur e devolve 0 se sim. É leitura de arquivo: nenhum processo, nenhuma
# rede — pode ser feito a qualquer momento, inclusive na troca de faixa.
tidal_cache_ler() {
    [ -s "$CACHE_TIDAL" ] || return 1
    while IFS='	' read -r _cid _cart _ctit _calb _cdur; do
        [ "$_cid" = "$1" ] || continue
        tid_art=$_cart; tid_tit=$_ctit; tid_alb=$_calb; tid_dur=$_cdur
        case "$tid_dur" in ''|*[!0-9]*) tid_dur=0 ;; esac
        [ -n "$tid_art" ] && [ -n "$tid_tit" ] || return 1
        return 0
    done < "$CACHE_TIDAL"
    return 1
}

tidal_cache_gravar() {
    [ -n "$tid_art" ] && [ -n "$tid_tit" ] || return 0
    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$1" "$tid_art" "$tid_tit" "$tid_alb" "$tid_dur" >> "$CACHE_TIDAL"
    # Não deixa crescer para sempre. As mais novas ficam: quem ouviu trezentas
    # faixas diferentes desde a última poda não vai voltar às primeiras tão
    # cedo, e o pior que acontece é uma consulta a mais.
    _n=$(wc -l < "$CACHE_TIDAL" 2>/dev/null)
    case "$_n" in ''|*[!0-9]*) return 0 ;; esac
    if [ "$_n" -gt $((CACHE_MAX * 2)) ]; then
        _fim=$(tail -n "$CACHE_MAX" "$CACHE_TIDAL" 2>/dev/null)
        [ -n "$_fim" ] && printf '%s\n' "$_fim" > "$CACHE_TIDAL"
    fi
}

# Faixas do Tidal que terminaram e ainda não viraram linha da fila: id,
# começo e fim, uma por linha.
#
# Este arquivo existe por causa de uma medição no aparelho. Com o Tidal
# tocando sobram ~1,5 MB livres e o maior bloco contíguo de memória é de meio
# mega; e este kernel foi compilado SEM compactação — não existe
# `/proc/sys/vm/compact_memory` nem os contadores de compactação em
# /proc/vmstat —, então essa fragmentação não se desfaz enquanto o áudio não
# para. Com o som parado são 22 MB livres e blocos de 16 MB.
#
# No meio disso o daemon rodava o curl, que tem 1,6 MB — vinte vezes o
# r1collect. O player não morria de falta de memória total (há uns 10 MB
# recuperáveis de cache): morria de não conseguir o pedaço que precisava. E
# quando ele morre, o supervisor do firmware o reinicia, e depois de cinco
# mortes seguidas reinicia o aparelho — que é o "travamento" que você via.
#
# Tocando do cartão isso não acontecia porque ali o player ocupa bem menos:
# no Tidal ele tem 20 MB residentes, 32 threads e 14 sockets abertos.
#
# Então a regra passou a ser: enquanto o Tidal toca, o daemon só escreve
# texto. Nenhum processo, nenhuma alocação, nenhuma rede. Tudo o que precisa
# da rede espera o silêncio.
PEND_TIDAL=$DIR/tidal_pend

# Quanto esperar, depois de a faixa trocar, antes de encostar na rede.
#
# Medido no aparelho: um curl no MEIO da faixa custa 896 KB de pico residente,
# derruba a memória livre em uns 116 KB e não mexe na fragmentação — o maior
# bloco contíguo continua na ordem 7 antes, durante e depois. Cinco handshakes
# seguidos com o Tidal tocando não incomodaram o player.
#
# O que a v14–v19 faziam de diferente não era o tamanho: era a HORA. Elas
# disparavam no instante da troca, que é quando o player está pedindo memória
# para a faixa nova.
#
# Eram vinte segundos enquanto o anúncio significava criar um curl de 1,6 MB,
# abrir socket e negociar TLS bem ali. Com o ajudante residente isso deixou de
# existir: o que nasce na janela é um r1send de 120 KB, que monta o corpo e
# não fala com a rede. A rajada de alocação do player numa troca de faixa se
# resolve em bem menos que seis segundos, e o que sobra para esperar é isso.
#
# O ganho é direto para quem usa: o "tocando agora" aparece no perfil em uns
# quinze segundos em vez de quase um minuto.
CALMA=6

# Metadados de faixas do Tidal já consultadas: id, artista, título, álbum e
# duração, um por linha.
#
# Uma faixa só precisa ser perguntada uma vez na vida. Sem isto, ouvir o mesmo
# álbum duas vezes custa o dobro de consultas, e uma faixa repetida custa uma
# consulta por repetição — tudo isso com o áudio tocando, que é o que se quer
# evitar. Com o cache, quase toda faixa que você ouve de novo não custa rede
# nenhuma: nem para anunciar, nem para entrar na fila.
CACHE_TIDAL=$DIR/tidal_cache
CACHE_MAX=300

# Uma faixa do Tidal terminou. É só um `printf` num arquivo — o redirecionamento
# e o printf são internos do shell, então isto custa zero processos.
#   $1 = id   $2 = quando começou   $3 = quando terminou
tidal_pendurar() {
    [ -n "$1" ] || return 0
    [ "$2" -gt 0 ] 2>/dev/null || return 0
    _dur=$(($3 - $2))
    # Menos que isto não passa da regra dos 90% nem na faixa mais curta que o
    # Last.fm aceita (30s pedem 27s ouvidos). Descartar aqui poupa uma consulta
    # à rede por faixa pulada, que é justamente o que acontece aos montes
    # quando você percorre uma lista.
    [ "$_dur" -ge 25 ] 2>/dev/null || return 0
    printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$PEND_TIDAL"
}

# Tira a primeira linha do arquivo de pendentes.
tidal_desempilhar() {
    _resto=$(tail -n +2 "$PEND_TIDAL" 2>/dev/null)
    if [ -n "$_resto" ]; then
        printf '%s\n' "$_resto" > "$PEND_TIDAL"
    else
        rm -f "$PEND_TIDAL"
    fi
}

# Uma faixa pendente vira linha da fila. Só é chamada com o áudio PARADO, que
# é o único momento em que há memória de sobra para o curl.
#
# Uma por volta, de propósito: se você ouviu vinte faixas seguidas, elas saem
# em vinte voltas do laço, e nunca há dois processos grandes ao mesmo tempo.
tidal_resolver() {
    [ -s "$PEND_TIDAL" ] || return 0

    IFS='	' read -r _pid _pini _pfim < "$PEND_TIDAL" || return 0
    case "$_pid" in ''|*[!0-9]*) tidal_desempilhar; return 0 ;; esac

    # Guardar e devolver o estado da faixa EM CURSO.
    #
    # O tidal_meta e o tidal_cache_ler escrevem em tid_art/tid_tit/tid_alb/
    # tid_dur, e o tidal_anotar lê o tid_id — as mesmas variáveis que descrevem
    # o que está tocando agora. Resolver uma faixa velha por cima delas troca os
    # dados da faixa em curso pelos da antiga, e o pior efeito não é o nome
    # errado: é o tid_dur de OUTRA faixa entrar na conta da repetição, que
    # então dispara em cadeia e escreve a mesma faixa várias vezes na fila.
    # Foi assim que scrobbles falsos foram parar na conta de alguém.
    _sv_id=$tid_id; _sv_art=$tid_art; _sv_tit=$tid_tit
    _sv_alb=$tid_alb; _sv_dur=$tid_dur; _sv_sab=$tid_sabido
    _devolver() {
        tid_id=$_sv_id; tid_art=$_sv_art; tid_tit=$_sv_tit
        tid_alb=$_sv_alb; tid_dur=$_sv_dur; tid_sabido=$_sv_sab
    }

    # O cache primeiro: uma faixa já perguntada alguma vez não custa rede, e
    # aí não há motivo para esperar nada. Sai na hora.
    if tidal_cache_ler "$_pid"; then
        tid_id="$_pid"
        tidal_escrever "$_pini" "$_pfim"
        tidal_desempilhar
        _devolver
        return 0
    fi

    tem_memoria || { _devolver; return 0; }
    tem_rede    || { _devolver; return 0; }
    [ "$t_agora" -lt "$tid_tentar" ] 2>/dev/null && { _devolver; return 0; }
    tid_rede_ok=0

    if tidal_meta "$_pid"; then
        tid_falhas=0
        tid_id="$_pid"
        tidal_escrever "$_pini" "$_pfim"
        tidal_desempilhar
        _devolver
        return 0
    fi

    # Rede fora do ar, token trocado, faixa que saiu do catálogo: tenta de novo
    # daqui a um minuto. A faixa não se perde — ela fica no arquivo, que está
    # em /usr/data e sobrevive até a um desligamento.
    tid_falhas=$((tid_falhas + 1))
    tid_pais=""
    tid_tentar=$((t_agora + 60))
    if [ "$tid_falhas" -ge 5 ]; then
        # Cinco tentativas e nada: esta faixa não vai resolver, e segurá-la
        # trancaria todas as outras atrás dela.
        registrar "tidal: desisti dos dados da faixa $_pid; segue a fila"
        tid_falhas=0
        tidal_desempilhar
    fi
    _devolver
}

# Escreve na fila a faixa do Tidal, já com os metadados em mãos.
#   $1 = quando começou   $2 = quando terminou
#
# Se o mesmo id ficou tocando por várias vezes a duração dele, você o deixou
# no repetir: sai uma linha por repetição. O caminho antigo tentava perceber
# isso durante a reprodução, o que exigia saber a duração — e saber a duração
# exigia a consulta que agora não acontece mais ali dentro. Feito aqui, com o
# tempo total já conhecido, sai mais simples e mais certo.
tidal_escrever() {
    _ini=$1; _fim=$2
    _vezes=1
    if [ "$tid_dur" -gt 0 ] 2>/dev/null &&
       [ $((_fim - _ini)) -ge $((tid_dur * 2)) ]; then
        _vezes=$(( (_fim - _ini) / tid_dur ))
        [ "$_vezes" -gt 20 ] && _vezes=20
    fi
    _i=0
    while [ "$_i" -lt "$_vezes" ]; do
        if [ "$_vezes" = 1 ]; then
            _a=$_ini; _b=$_fim
        else
            _a=$((_ini + _i * tid_dur))
            _b=$((_a + tid_dur))
        fi
        tidal_anotar "$_b" "$_a"
        _i=$((_i + 1))
    done
}

# Escreve na fila a faixa do Tidal que acabou de terminar.
#   $1 = quando terminou   $2 = quando começou
tidal_anotar() {
    [ -n "$tid_art" ] && [ -n "$tid_tit" ] || return 0
    t_seq=$(cat "$SEQ" 2>/dev/null)
    case "$t_seq" in ''|*[!0-9]*) t_seq=0 ;; esac
    t_seq=$((t_seq + 1))
    echo "$t_seq" > "$SEQ"
    # Mesmo formato do p1 do coletor, com o 11º campo — a hora de início —
    # que o caminho local deixa vazio por não saber.
    printf 'p1\t%s\t%s\t%s\t%s\t%s\t\t%s\t0\ttidal:%s\t%s\n' \
        "$((TIDAL_BASE + t_seq))" "$1" "$tid_art" "$tid_tit" "$tid_alb" \
        "$tid_dur" "$tid_id" "$2" >> "$FILA"
    t_ouviu=$(($1 - $2))
    [ "$tid_dur" -gt 0 ] 2>/dev/null && [ "$t_ouviu" -gt "$tid_dur" ] &&
        t_ouviu=$tid_dur
    registrar "tidal: $tid_art — $tid_tit (${t_ouviu}s de ${tid_dur}s)"
    atualizar_csv
    if [ "$IMEDIATO" = 1 ] && [ "$proximo_envio" = "$ENVIO" ]; then
        t_falta=$((proximo_envio - ESPERA_IMEDIATO))
        [ "$t_falta" -lt 0 ] && t_falta=0
        [ "$desde_envio" -lt "$t_falta" ] && desde_envio=$t_falta
    fi
}

# Uma volta do acompanhamento do Tidal.
olhar_tidal() {
    # O portão fica aqui e não lá dentro: tanto o `r1collect tidal` quanto o
    # `date` são fork+exec, e chamá-los toda volta era o que fazia o ciclo
    # parado custar 14 ms em vez de 0,25.
    [ "$precisa_tidal" = 1 ] || return 0
    [ -x "$COLETOR" ] || return 0

    t_novo=$("$COLETOR" tidal 2>/dev/null)
    t_agora=$(date +%s)

    # Tocando pelo Tidal quer dizer: o áudio está saindo E não há arquivo
    # local aberto. Streaming é socket, não arquivo — e o id do Tidal no
    # user.ini não é apagado quando você volta aos arquivos locais, então sem
    # esta distinção uma faixa que ninguém ouviu entraria na fila.
    if [ "$pcm_aberto" = 1 ] && [ -z "$local_tocando" ]; then
        t_toca=1
    else
        t_toca=0
    fi

    # A partir daqui, quem decide se o resto do daemon pode usar a rede nesta
    # volta é este bloco. Ele começa a volta valendo 1 (ver o laço principal) e
    # só é zerado nos momentos que a medição apontou como ruins: o instante da
    # troca, os primeiros CALMA segundos da faixa, e as voltas em que a própria
    # olhar_tidal já gastou uma ida à rede.
    tid_rede_ok=0

    # Parou de tocar (ou passou a tocar arquivo local): fecha a faixa aberta
    # com a hora de agora. O pcm fecha junto com o áudio, então "agora" está a
    # no máximo um ciclo do fim real.
    if [ "$t_toca" = 0 ]; then
        if [ -n "$tid_id" ]; then
            tidal_fechar "$t_agora"
            tid_id=""; tid_desde=0
        fi
        # Silêncio: sobra memória de verdade (22 MB contra 1,5 MB). É aqui que
        # o que ficou pendente por falta de metadados se resolve, uma por volta.
        tid_rede_ok=1
        tidal_resolver
        return 0
    fi

    # O id só muda quando entra outra faixa do Tidal; tocar arquivo local não
    # mexe nele. Um id vazio quer dizer que o campo ainda não existe (nunca
    # se usou o Tidal neste aparelho).
    [ -n "$t_novo" ] || return 0

    if [ "$t_novo" != "$tid_id" ]; then
        # Trocou de faixa. Aqui não nasce processo nenhum: fechar a anterior é
        # escrita de texto, e a decisão entre "já sei os dados" e "não sei" sai
        # de uma variável. Este é o instante em que o player está pedindo
        # memória para a faixa nova — o único momento que a medição apontou
        # como perigoso, e o único em que este código não faz absolutamente
        # nada além de escrever.
        [ -n "$tid_id" ] && tidal_fechar "$t_agora"
        tid_id="$t_novo"
        tid_desde="$t_agora"
        tid_sabido=0
        tid_anunciado=0
        tid_tent_anuncio=0
        tid_reanuncio=0
        tid_perdida=0
        # Pede que a PRÓXIMA volta aconteça em CALMA segundos, e não nos 15
        # de sempre.
        #
        # Sem isto a janela calma não vale nada: ela é de 6 segundos, mas o
        # laço só acorda de 15 em 15, então o anúncio cai sempre no tique
        # seguinte e os 6 viram 15. Medido no aparelho: 37 segundos da troca
        # até o aviso, dos quais só 4 são trabalho — o resto é espera.
        #
        # Não é polling a mais: é UMA volta adiantada por troca de faixa. Em
        # regime parado nada muda.
        tid_apressar=1
        return 0
    fi

    # Daqui para baixo, a faixa em curso. Primeiro o que é de graça.

    # O cache é leitura de arquivo: não usa rede, não cria processo, e por isso
    # acontece sempre — inclusive nos primeiros segundos da faixa e com
    # REDE_NO_TIDAL desligado. É ele que faz uma faixa já conhecida entrar na
    # fila no instante em que acaba, em vez de esperar o silêncio.
    if [ "$tid_sabido" != 1 ] && tidal_cache_ler "$tid_id"; then
        tid_sabido=1
    fi

    # Mesma faixa há tempo suficiente para ela ter acabado: ou você a pôs no
    # repetir, ou o player seguiu para outra que ainda não vimos. Fecha esta e
    # recomeça a contagem — é o que faz repetir uma música continuar
    # scrobblando. Precisa da duração, que só se tem sabendo a faixa.
    if [ "$tid_sabido" = 1 ] && [ "$tid_dur" -gt 0 ] 2>/dev/null &&
       [ $((t_agora - tid_desde)) -ge "$tid_dur" ]; then
        t_fim=$((tid_desde + tid_dur))
        tidal_anotar "$t_fim" "$tid_desde"
        tid_desde=$t_fim
        tid_anunciado=0
    fi

    # Daqui para baixo é rede, e com o Tidal tocando ela depende de permissão.
    # Sem ela, tid_rede_ok fica em 0 e o daemon inteiro — consulta, anúncio,
    # envio e planilha — espera o áudio parar. É o padrão.
    [ "$REDE_NO_TIDAL" = 1 ] || return 0

    # E mesmo com permissão, nada nos primeiros CALMA segundos da faixa.
    [ $((t_agora - tid_desde)) -ge "$CALMA" ] || return 0

    # A faixa que o cache não conhecia. Quando vai à rede, para por aqui: o
    # anúncio fica para a volta seguinte, para nunca haver dois curl no mesmo
    # ciclo.
    if [ "$tid_sabido" != 1 ]; then
        # O catálogo já disse que não conhece esta faixa. Perguntar de novo dá
        # a mesma resposta — ver o 404 mais abaixo.
        [ "$tid_perdida" = 1 ] && return 0
        [ "$t_agora" -lt "$tid_tentar" ] 2>/dev/null && return 0
        tem_memoria || return 0
        if tidal_meta "$tid_id"; then
            tid_sabido=1
            tid_falhas=0
            # Com o ajudante de pé, a consulta que acabou de acontecer não
            # criou processo nem abriu conexão — foi uma escrita num descritor
            # que já existia. Então o anúncio pode sair NESTA MESMA volta, e o
            # "tocando agora" deixa de esperar mais um ciclo do laço.
            #
            # Sem o ajudante isso seriam dois curl seguidos, que é exatamente
            # o que derrubava o aparelho: aí a separação continua valendo.
            [ "$rede_pronta" = 1 ] || return 0
        elif [ "$http_codigo" = 404 ]; then
            # O catálogo do Tidal não conhece este id.
            #
            # Visto num R1 de verdade: quatro faixas seguidas devolvendo
            # `{"status":404,"subStatus":2001,"userMessage":"Track [...] not
            # found"}`, e o mesmo 404 em /v1/videos, /v1/albums e
            # /v1/episodes. Não é rede, não é token, não é o país — o id
            # simplesmente não existe lá.
            #
            # Insistir não muda a resposta, e sem esta saída o daemon repetia
            # duas requisições por minuto, para sempre, por uma faixa que
            # nunca teria nome. Fica registrado uma vez e segue a vida.
            registrar "tidal: o catalogo nao conhece a faixa $tid_id (404); sem dados para anunciar"
            tid_perdida=1
            return 0
        else
            tid_pais=""
            tid_tentar=$((t_agora + 60))
            return 0
        fi
    fi

    # O "tocando agora": uma ida à rede, longe da troca, uma só por faixa.
    # O "tocando agora": uma ida à rede, longe da troca, uma só por faixa — mas
    # a marca só é posta quando ele DEU CERTO.
    #
    # Marcar antes era o que fazia o recurso ser "às vezes sim, às vezes não":
    # qualquer tropeço passageiro deixava aquela faixa sem anúncio para sempre,
    # sem nova tentativa e sem nada no registro dizendo por quê.
    if [ "$AGORA" = 1 ] && [ "$tid_anunciado" != 1 ]; then
        [ "$t_agora" -lt "$tid_reanuncio" ] 2>/dev/null && return 0
        tem_memoria || return 0
        if anunciar_tidal; then
            tid_anunciado=1
        else
            tid_tent_anuncio=$((tid_tent_anuncio + 1))
            if [ "$tid_tent_anuncio" -ge 3 ]; then
                # Três tentativas espaçadas bastam: passado esse tempo a faixa
                # já andou demais para o aviso fazer sentido.
                tid_anunciado=1
                registrar "tidal: desisti do 'tocando agora' desta faixa"
            else
                tid_reanuncio=$((t_agora + 20))
            fi
        fi
        return 0
    fi

    # Nada a fazer nesta volta: a faixa já está sabida e já foi anunciada, e a
    # janela calma passou. É seguro o resto do daemon usar a rede agora.
    tid_rede_ok=1
}

# Fecha a faixa do Tidal que estava tocando.
#
# Se os dados dela já estão em mãos — o caso comum, porque a janela calma os
# buscou logo no começo —, a linha da fila sai agora, sem rede. Se não estão
# (faixa pulada antes dos vinte segundos, ou rede fora do ar), ela vai para o
# arquivo de pendentes e espera o silêncio.
tidal_fechar() {
    if [ "$tid_sabido" = 1 ]; then
        tidal_anotar "$1" "$tid_desde"
    else
        tidal_pendurar "$tid_id" "$tid_desde" "$1"
    fi
    tid_sabido=0
    tid_anunciado=0
}

# O "tocando agora" da faixa do Tidal. Mesmo caminho do local, sem a parte que
# consulta o banco: os metadados já estão em mãos quando isto é chamado.
#
# Quem garante a segurança não é esta função: é quem a chama. Ela só roda
# passados os CALMA segundos desde a troca, nunca no mesmo ciclo de uma
# consulta de metadados, e no máximo uma vez por faixa.
anunciar_tidal() {
    [ -x "$REMETENTE" ] && [ -s "$SK" ] || return 1
    tem_rede || return 1
    t_ca=$(cacert); [ -n "$t_ca" ] || return 1
    # O r1send monta e assina o corpo. Continua sendo um processo, mas tem
    # 120 KB e não fala com a rede — é o curl, com 1,6 MB e um handshake, que
    # o ajudante tira daqui.
    "$REMETENTE" agora "$SK" "$SEGREDO" "$APIKEY" "$CORPO_NP" \
        "$tid_art" "$tid_tit" "$tid_alb" "$tid_dur" >/dev/null 2>>"$LOG" || return 1
    [ -n "$ip_api" ] || ip_api=$(resolver "$API_HOST")

    http_pedir POST "$API_HOST" "${ip_api:--}" "$API_CAMINHO" \
               "$CORPO_NP" "$RESP_NP" -
    rc=$?
    if [ "$rc" = 2 ]; then
        [ -x "$CURL" ] || { rm -f "$CORPO_NP" "$RESP_NP"; return 1; }
        t_res=""
        [ -n "$ip_api" ] && t_res="--resolve $API_HOST:443:$ip_api"
        "$CURL" -sS --max-time 20 --cacert "$t_ca" $t_res \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -A "hiby-r1-scrobbler/1.0" \
            --data-binary "@$CORPO_NP" -o "$RESP_NP" \
            "$API" 2>>"$LOG"
        rc=$?
    fi
    rm -f "$CORPO_NP" "$RESP_NP"
    [ "$rc" = 0 ] && registrar "tocando agora (tidal): $tid_art — $tid_tit"
    return $rc
}

# Uma olhada no que está tocando, e o anúncio se for faixa nova.
olhar_tocando() {
    [ "$AGORA" = 1 ] || return 0
    [ -x "$REMETENTE" ] && [ -x "$CURL" ] && [ -s "$SK" ] || return 0
    tem_rede || return 0

    atual=$local_tocando
    [ -n "$atual" ] || return 0

    # Repetiu a mesma faixa? O Last.fm apaga o aviso sozinho quando a duração
    # acaba, então depois desse tempo vale anunciar de novo — é o que faz o
    # "repetir uma música" continuar aparecendo.
    agora_seg=$(date +%s)
    if [ "$atual" = "$np_ultimo" ]; then
        [ -n "$np_quando" ] || return 0
        [ -n "$np_dur_efetiva" ] || return 0
        [ $((agora_seg - np_quando)) -ge "$np_dur_efetiva" ] || return 0
    fi

    [ -n "$ip_api" ] || ip_api=$(resolver_api)
    if anunciar "$atual"; then
        np_ultimo=$atual
        np_quando=$agora_seg
        registrar "tocando agora: $np_art — $np_tit"
    fi
}

# Manda o que houver, em lotes de 50, até acabar ou dar erro.
# Códigos: 0 mandou, 1 falhou de verdade, 2 sem rede, 3 nada a enviar.
#
# Separar "sem rede" de "falhou" importa. O recuo exponencial existe para não
# martelar um serviço que está com problema, mas ficar sem WiFi não é problema
# nenhum — é o estado normal de quem está numa viagem de carro. Se as duas
# coisas contassem igual, três horas sem rede levariam o intervalo ao teto de
# duas horas, e ao chegar em casa e ligar o WiFi você esperaria todo esse
# tempo pelos scrobbles. Conferir se há rota custa dois stat(): pode ser feito
# sempre, sem recuo.
# $1 = quantos lotes no máximo. Cada lote é um curl.
tentar_enviar() {
    pode_enviar || return 2
    tem_rede || return 2
    # Uma resolução por rodada, reaproveitada pelos lotes seguintes.
    ip_api=$(resolver_api)
    [ -n "$ip_api" ] || registrar "nao resolvi $API_HOST; deixando o curl tentar"
    _teto=${1:-20}
    voltas=0
    while [ "$voltas" -lt "$_teto" ]; do
        mandar_lote
        rc=$?
        [ "$rc" = 3 ] && { [ "$voltas" = 0 ] && return 3; return 0; }
        [ "$rc" = 0 ] || return 1
        voltas=$((voltas + 1))
    done
    return 0
}

# O cartão é procurado antes do primeiro registro, para o cabeçalho da sessão
# já cair nele.
achar_cartao && aparar_log_sd

# O ajudante sobe AGORA, na partida do daemon — que é a partida do aparelho.
# É o momento em que há 22 MB livres, e é por isso que todo o custo dele é pago
# aqui. Se não subir, nada quebra: a rede volta a ser o curl de sempre.
subir_ajudante || rede_pronta=0

agora=$(date +%s)
printf 'b1\t%s\n' "$agora" >> "$FILA"
# Sobrou medição de uma execução que não teve como se despedir? Ela vira faixa
# fechada agora, antes de qualquer outra coisa mexer na fila.
recuperar_medicao
# Quantas colheitas esta execução já fez. A de número zero é a que encontra o
# que tocou enquanto o daemon estava fora do ar — ver o comentário no laço.
colheita=0
# Hora em que a faixa local hoje em curso entrou no histórico. Vazio quando
# não há nenhuma em aberto. Ver o comentário do f1, no laço.
aberta_em=""
# A faixa em curso e quantos segundos de áudio ela já teve. Isto é MEDIDO: a
# cada volta, se o pcm estiver aberto, o tempo decorrido entra na conta. É o
# que separa "ouviu" de "estava na tela": pausar não conta, pular não conta,
# desligar no meio não conta. Ver fechar_faixa_atual e o t1.
atual_rowid=""
atual_ouvido=0
# Quanto do `atual_ouvido` já foi salvo em disco. Ver anotar_medida.
atual_gravado=0
# A incerteza acumulada da medição, em segundos: uma vez o intervalo do laço
# para cada vez que o áudio começou ou parou dentro dele. Ver o acumulador.
atual_granul=0
# O pcm na volta anterior, para reconhecer as trocas.
pcm_antes=1
ultimo_olhar=$agora
# Desde quando o som está parado com a faixa ainda aberta. Vazio = tocando.
parado_desde=""
# Quando a planilha do cartão foi reescrita pela última vez. Ver atualizar_csv.
csv_em=""
# Quando a fila foi podada pela última vez. Nasce em zero de propósito: assim
# a primeira parada depois de ligar já enxuga o que ficou para trás, em vez de
# esperar seis horas de aparelho ligado.
poda_em=0
# Desde quando há faixa fechada esperando envio. Ver o teto em adiantar_envio.
pendente_desde=""
# Quando foi a colheita anterior. É a janela que se reparte quando várias
# faixas caem numa passada só.
ultima_colheita=""
# 1 quando esta volta é um momento seguro para usar a rede. Ver olhar_tidal.
tid_rede_ok=1
# Os metadados da faixa do Tidal em curso já estão em mãos?
tid_sabido=0
# E ela já foi anunciada como "tocando agora"? Uma vez por faixa.
tid_anunciado=0
# Consultas seguidas que falharam para a faixa da frente da fila de pendentes.
tid_falhas=0
tid_tentar=0
# Tentativas do "tocando agora" da faixa em curso, e quando repetir.
tid_tent_anuncio=0
tid_reanuncio=0
# 1 quando a faixa acabou de trocar e a próxima volta deve vir mais cedo.
tid_apressar=0
# 1 quando o catálogo do Tidal respondeu 404 para a faixa em curso.
tid_perdida=0
if [ "$agora" -lt "$PISO" ]; then
    printf 'c1\t%s\n' "$agora" >> "$FILA"
    registrar "relogio em $agora, anterior ao piso $PISO: horas suspeitas"
fi
registrar "r1scrobbled iniciado em $(date), pid $$"
# Qual dos dois bancos do player está valendo. Vem antes do marco zero e do
# lote atrasado, porque os dois leem o banco — e pode mudar `primeira`.
if achar_banco; then
    # Dito a cada partida, e não só quando muda. Quando o banco está no lugar
    # errado o sintoma é "diz que está rodando e não colhe nada", e a primeira
    # coisa que alguém vai olhar é este registro.
    registrar "banco do player em uso: $DB"
else
    registrar "nenhum banco do player encontrado; procurei em $DB_INTERNO e" \
              "em <cartao>/$DB_NO_CARTAO"
fi
if [ -n "$sd" ]; then
    registrar "registro e planilha no cartao: $sd"
    # A planilha é reescrita já na partida. Sem isto ela só apareceria depois
    # da primeira faixa, e quem instalou e foi conferir o cartão na hora
    # encontraria a pasta vazia sem entender por quê. Por isso "ja": esta não
    # espera o minuto de folga.
    atualizar_csv ja
else
    registrar "sem cartao gravavel; o registro fica so em $LOG (some no boot)"
fi

if [ "$primeira" = 1 ]; then
    if cp -f "$DB" "$COPIA" 2>/dev/null; then
        if saida=$("$COLETOR" "$COPIA" 0 "$PARCIAL" 2>>"$LOG"); then
            # Só o maior rowid interessa; as linhas em si são descartadas.
            echo "${saida##* }" > "$ESTADO"
            registrar "primeira execucao: historico antigo ignorado, marco em"\
                      "rowid ${saida##* } (${saida%% *} faixas ja existiam)"
        fi
        rm -f "$COPIA" "$PARCIAL"
    fi
fi
# O lote atrasado é o que já estava no banco AGORA, na partida — e não a
# primeira colheita que vier a acontecer.
#
# Eu marcava como lote a primeira colheita de cada execução, qualquer que
# fosse a hora dela. Só que numa partida sem nada atrasado a primeira colheita
# é a próxima faixa que a pessoa tocar, dali a minutos — e ela levava o
# tratamento de lote: crédito integral no instante em que começou. Que é
# exatamente a reclamação que o lote veio resolver, reintroduzida por ele.
#
# Aqui a pergunta certa é feita uma vez só, antes de o laço começar: o banco
# tem linhas além do que já foi anotado? Se tem, elas tocaram sem ninguém
# olhando e são lote de verdade. Se não tem, não há lote nenhum, e tudo que
# vier depois é ao vivo.
atrasadas=0
if cp -f "$DB" "$COPIA" 2>/dev/null; then
    desde=$(cat "$ESTADO" 2>/dev/null)
    [ -n "$desde" ] || desde=0
    if saida=$("$COLETOR" "$COPIA" "$desde" "$PARCIAL" 2>>"$LOG"); then
        atrasadas=${saida%% *}
        if [ "$atrasadas" -gt 0 ] 2>/dev/null; then
            maior_ini=${saida##* }
            # A ÚLTIMA dessas linhas pode ser a faixa que está tocando agora.
            #
            # Isso custou um relato: o daemon subia com música tocando, via a
            # linha daquela faixa no banco, chamava aquilo de "tocou sem
            # ninguém olhando", dava crédito integral e a mandava ao Last.fm
            # na hora. A pessoa via a mesma faixa como "scrobbling now" e como
            # scrobble ao mesmo tempo — porque ela estava mesmo tocando.
            #
            # Uma faixa que está tocando NESTE momento não é passado. Ela fica
            # de fora do lote e vira a faixa em curso, contada do zero como
            # qualquer outra: perde-se o pedaço que já tinha tocado, e é
            # melhor perder isso do que inventar uma escuta inteira.
            #
            # A pergunta não é "sai som?" e sim "há ARQUIVO LOCAL aberto?".
            # Som saindo pode ser o Tidal, e aí as linhas locais são passado
            # de verdade — descartar a última seria perder um scrobble bom.
            # Arquivo local aberto é a faixa desta última linha, tocando.
            tocando_agora_ini=0
            _pcm_ini=""; _loc_ini=""
            { read -r _pcm_ini; read -r _loc_ini; } <<FIM_INI
$("$COLETOR" estado 2>/dev/null)
FIM_INI
            case "$_pcm_ini" in
            pcm=*) [ -n "$_loc_ini" ] && tocando_agora_ini=1 ;;
            *)
                # r1collect antigo, sem `estado`: `tocando` responde o mesmo.
                [ -n "$("$COLETOR" tocando 2>/dev/null)" ] && \
                    tocando_agora_ini=1
                ;;
            esac

            if [ "$tocando_agora_ini" = 1 ]; then
                atrasadas=$((atrasadas - 1))
                if [ "$atrasadas" -gt 0 ]; then
                    printf 'a1\t%s\t%s\n' "$(date +%s)" "$atrasadas" >> "$FILA"
                    head -n "$atrasadas" "$PARCIAL" >> "$FILA"
                fi
                tail -n 1 "$PARCIAL" >> "$FILA"
                atual_rowid=$maior_ini
                atual_ouvido=0
                atual_gravado=0
                # $RAPIDO e não $intervalo: o laço ainda não começou, e é com
                # o RAPIDO que ele vai começar.
                atual_granul=$RAPIDO
                # Ela está tocando: é essa a condição para chegar aqui.
                pcm_antes=1
                ultimo_olhar=$(date +%s)
                if [ "$atrasadas" -gt 0 ]; then
                    registrar "$atrasadas atrasada(s), e a ultima linha e a" \
                              "faixa tocando agora: contada do zero"
                else
                    registrar "nada atrasado; a unica linha nova e a faixa" \
                              "tocando agora, contada do zero"
                fi
            else
                printf 'a1\t%s\t%s\n' "$(date +%s)" "$atrasadas" >> "$FILA"
                cat "$PARCIAL" >> "$FILA"
                registrar "$atrasadas faixa(s) tocaram com o daemon fora do ar;" \
                          "horas reconstruidas"
            fi
            echo "$maior_ini" > "$ESTADO"
            aberta_em=$(date +%s)
            atualizar_csv
        fi
    fi
    rm -f "$COPIA" "$PARCIAL"
fi

# Subiu com música tocando e sem nada atrasado? Adota a faixa mesmo assim.
#
# É o caso de toda partida que não é a do boot: uma atualização, ou — neste
# aparelho, que trava sozinho — um reinício no meio de uma música. O banco não
# ganhou linha nova (retomar não escreve nada), então o bloco do lote acima
# não viu nada para fazer, e o resto da faixa ficava sem ninguém medindo.
#
# Visto aqui: a faixa 282 tocou 39 s, ficou 14 minutos pausada, voltou e tocou
# mais 82 — e foi registrada com os 34 s que o daemon anterior tinha medido,
# porque o novo não sabia que ela existia.
#
# Adotar custa nada e soma: o t1 desta execução se junta ao que já estava na
# fila. O pedaço tocado entre o travamento e a partida é o único que se perde,
# e perder isso é melhor do que inventar.
if [ -z "$atual_rowid" ]; then
    _pcm_ret=""; _loc_ret=""
    { read -r _pcm_ret; read -r _loc_ret; } <<FIM_RET
$("$COLETOR" estado 2>/dev/null)
FIM_RET
    case "$_pcm_ret" in
    pcm=*) ;;
    *) _loc_ret=$("$COLETOR" tocando 2>/dev/null) ;;
    esac
    _ult=$(cat "$ESTADO" 2>/dev/null)
    if [ -n "$_loc_ret" ] && [ -n "$_ult" ] && [ "$_ult" -gt 0 ] 2>/dev/null
    then
        atual_rowid=$_ult
        atual_ouvido=0
        atual_gravado=0
        atual_granul=$RAPIDO
        pcm_antes=1
        ultimo_olhar=$(date +%s)
        aberta_em=$ultimo_olhar
        parado_desde=""
        registrar "faixa $atual_rowid ja estava tocando na partida;" \
                  "medindo o resto dela"
    fi
fi

# Daqui em diante nenhuma colheita é lote: o daemon está de olho, e o espaço
# entre uma linha e a outra é tempo de verdade.
colheita=1

if [ "$fifo_ok" = 1 ]; then
    registrar "espera sem fork (read -t no fifo; esperou ${_medido}s de 2)"
else
    registrar "usando sleep: $motivo_espera (mediu ${_medido}s de 2)"
fi

# As marcas começam mais velhas que os bancos de propósito, para que uma
# reprodução ocorrida com o daemon fora do ar ainda seja recolhida no primeiro
# ciclo.
for m in "$MARCA" "$MARCA2" "$MARCA3"; do
    [ -f "$m" ] || touch -t 200001010000 "$m" 2>/dev/null || : > "$m"
done

# O acompanhamento do Tidal só acorda quando o /usr/data/user.ini muda — e ele
# muda na TROCA de faixa. Um daemon que sobe no meio de uma faixa fica cego até
# você pular, porque o arquivo já mudou antes de ele existir.
#
# Não é caso raro de quem instala: acontece toda vez que o aparelho liga com o
# Tidal retomando de onde parou. Visto ao vivo — o daemon foi reiniciado com
# uma faixa tocando e não anunciou nada até a seguinte.
#
# Envelhecer esta marca faz a primeira volta olhar o Tidal e adotar o que já
# está no ar. O que se perde é só o tempo antes de o daemon existir, que
# ninguém tinha como medir mesmo.
[ "$TIDAL" = 1 ] && touch -t 200001010000 "$MARCA3" 2>/dev/null

intervalo=$RAPIDO
quietos=0
ativo=0
ultimo=$agora
desde_envio=0
proximo_envio=$ENVIO
np_ultimo=""
np_quando=0
# O acompanhamento do Tidal: qual faixa, desde quando, e os dados dela.
tid_id=""
tid_desde=0
tid_art=""; tid_tit=""; tid_alb=""; tid_dur=0
tid_pais=""
ip_tidal=""
# Preenchidos uma vez por volta pelo `r1collect estado`.
pcm_aberto=0
local_tocando=""
precisa_tidal=0
precisa_estado=0
np_dur_efetiva=0
queixei_cacert=0
ip_api=""
# Começa em 1 para o marco zero não disparar um envio na partida.
tinha_rede=1
# Quanto falta para reconferir o cartão. Meia hora: tempo de sobra para quem
# pôs o cartão depois de ligar o aparelho, e raro o bastante para não pesar.
recheca_sd=1800

while :; do
    mexeu=0

    # O cartão pode ter sido posto ou tirado desde a última olhada.
    recheca_sd=$((recheca_sd - intervalo))
    if [ "$recheca_sd" -le 0 ]; then
        recheca_sd=1800
        tinha_sd=$sd
        achar_cartao || :
        if [ -n "$sd" ] && [ "$sd" != "$tinha_sd" ]; then
            aparar_log_sd
            registrar "cartao encontrado: $sd"
            atualizar_csv
        fi
        # O banco pode ter mudado de lugar junto: a opção que o move para o
        # cartão é mexida na tela do aparelho, com o daemon rodando, e o
        # banco novo só passa a existir quando o player o reconstrói.
        achar_banco || :
    fi

    # Quando vale a pena perguntar ao r1collect o que está tocando.
    #
    # Esta consulta é a única coisa do laço que cria processo, e chamá-la toda
    # volta custa 18 ms contra os 0,25 ms de um ciclo parado — setenta vezes
    # mais, o dia inteiro, para quase sempre ouvir "nada mudou". O mesmo teste
    # de mtime que já protege o banco resolve: o id do Tidal mora no
    # user.ini, e se o arquivo não foi tocado não há faixa nova para ver.
    #
    #   • com "tocando agora" ligado, é preciso olhar sempre — é o preço
    #     declarado desse recurso;
    #   • com uma faixa do Tidal em curso, é preciso olhar para saber quando
    #     ela termina;
    #   • com uma faixa local aberta, é preciso olhar para medir o tempo dela;
    #   • fora disso, só quando o user.ini mudar.
    #
    # Ela vem ANTES da colheita, e isso não é arrumação. A colheita fecha a
    # faixa anterior, e fechar exige o tempo dela até este instante; com a
    # sondagem depois, o fecho usava a leitura da volta PASSADA e perdia um
    # intervalo inteiro de escuta — até 60 s, sempre no fim da faixa, que é
    # justamente onde a regra dos 90% decide.
    precisa_tidal=0
    if [ "$TIDAL" = 1 ]; then
        [ -n "$tid_id" ] && precisa_tidal=1
        # Há faixa esperando os metadados: isso é trabalho a fazer, e quem o
        # faz é a olhar_tidal. Sem esta linha o daemon adormece com o arquivo
        # cheio e as faixas nunca chegam à fila.
        [ -s "$PEND_TIDAL" ] && precisa_tidal=1
        if [ -f "$TIDAL_INI" ] && [ "$TIDAL_INI" -nt "$MARCA3" ]; then
            touch "$MARCA3" 2>/dev/null
            precisa_tidal=1
        fi
    fi
    precisa_estado=0
    [ "$AGORA" = 1 ] && precisa_estado=1
    [ "$precisa_tidal" = 1 ] && precisa_estado=1
    # Há uma faixa local em aberto — a última que entrou no histórico, que só
    # deixa de tocar quando outra começa ou quando o áudio para. Enquanto
    # estiver assim é preciso olhar o pcm: para medir quanto dela tocou e para
    # saber a hora em que parou. Quando ela fecha, a sondagem se desliga
    # sozinha — o ciclo parado volta a não criar processo nenhum.
    [ -n "$aberta_em" ] && precisa_estado=1

    pcm_aberto=0
    local_tocando=""
    # Vale 1 até que a olhar_tidal diga o contrário. Quando não há Tidal em
    # jogo — arquivo local, ou nada tocando — ela nem roda, e o daemon segue
    # como sempre foi.
    tid_rede_ok=1
    if [ "$precisa_estado" = 1 ]; then
        _pcm=""
        { read -r _pcm; read -r local_tocando; } <<FIM_ESTADO
$("$COLETOR" estado 2>/dev/null)
FIM_ESTADO
        case "$_pcm" in
        pcm=1) pcm_aberto=1 ;;
        pcm=0) ;;
        *)
            # Um r1collect anterior a este daemon não conhece `estado`. Sem
            # esta reserva o "tocando agora" pararia calado depois de uma
            # atualização em que só o daemon foi trocado — e "parou de
            # funcionar sem dizer nada" é o pior modo de falhar que existe.
            local_tocando=$("$COLETOR" tocando 2>/dev/null)
            [ -n "$local_tocando" ] && pcm_aberto=1
            ;;
        esac
    fi

    # O tempo ouvido é MEDIDO, e não deduzido dos carimbos.
    #
    # Deduzir do espaço entre uma linha e a seguinte parece equivalente e não
    # é. Ele quebra em três situações que acontecem todo dia:
    #
    #   • pausa. Você para no meio, atende alguém, volta e ouve o resto. Pelo
    #     espaço entre linhas a faixa "durou" tudo isso; pelo relógio de
    #     parede ela tocou muito menos. Um dos dois está errado, e é sempre o
    #     mesmo.
    #   • o daemon subindo com música já tocando. A linha daquela faixa já
    #     está no banco, e ele não tem como saber quanto dela já passou — foi
    #     o que mandou ao Last.fm faixas que estavam começando naquele
    #     instante, aparecendo como scrobble e como "ouvindo agora" ao mesmo
    #     tempo.
    #   • a última faixa de uma sequência, que não tem seguinte para fechá-la
    #     e acabava sendo fechada por chute.
    #
    # Aqui o número é o que ele viu: a cada volta, com o pcm aberto, soma o
    # tempo desde a volta anterior. Uma pausa simplesmente não é contada,
    # porque o pcm fecha.
    #
    # Junto com o total vai a incerteza dele, na mesma linha t1: o PC precisa
    # saber com que precisão o número foi medido para não cobrar dele mais do
    # que ele tem. Como ela é somada está logo abaixo.
    if [ -n "$atual_rowid" ]; then
        _ag=$(date +%s)
        _d=$((_ag - ultimo_olhar))
        # Um salto absurdo (relógio acertado, suspensão) não vira nada.
        [ "$_d" -gt 0 ] && [ "$_d" -le $((LENTO * 2)) ] || _d=0

        # A incerteza da medição, somada honestamente.
        #
        # O pcm é olhado de tantos em tantos segundos, então a hora em que ele
        # mudou de estado só se sabe com a precisão de um intervalo. Cada
        # troca — o áudio parou, o áudio voltou — esconde até um intervalo
        # inteiro de música que não entrou na conta.
        #
        # Visto ao vivo: a sonda de um em um segundo cronometrou 6 s de pausa
        # numa faixa; o daemon, olhando de 15 em 15, contou 15. Os 9 segundos
        # de diferença são música que tocou e não foi somada.
        #
        # Por isso a incerteza acompanha as TROCAS, e não o intervalo do laço.
        # Uma faixa ouvida direto tem duas (começou, acabou) e quase nenhuma
        # incerteza; uma faixa pausada três vezes tem oito, e é justo que o PC
        # cobre dela com a mesma folga com que ela foi medida. Um pulo não
        # ganha nada com isso: pular também dá uma troca só.
        if [ "$pcm_aberto" != "$pcm_antes" ]; then
            atual_granul=$((atual_granul + _d))
        fi
        pcm_antes=$pcm_aberto

        if [ "$pcm_aberto" = 1 ]; then
            if [ "$_d" -gt 0 ]; then
                atual_ouvido=$((atual_ouvido + _d))
            fi
            # Passou o suficiente desde o último ponto de controle: grava,
            # para um travamento não levar a contagem junto.
            if [ $((atual_ouvido - atual_gravado)) -ge "$T1_PASSO" ]; then
                anotar_medida
            fi
        fi
        ultimo_olhar=$_ag
    fi

    if [ "$DB" -nt "$MARCA" ]; then
        mexeu=1

        # Deixa o player respirar antes de ler o banco dele.
        #
        # A linha nova aparece no mesmo instante em que a faixa começa, que é
        # exatamente quando o player está pedindo os buffers dela. Ler o banco
        # e criar processos nesse segundo é somar a nossa carga à dele, e o
        # aparelho reiniciava. Esperar uma volta custa alguns segundos numa
        # medição que já é feita com régua de segundos, e tira a nossa parte
        # de cima do pior momento.
        #
        # A marca NÃO é tocada aqui: sem isso o ciclo seguinte não veria mais
        # a mudança e a faixa se perderia.
        _m_db=$(data_do_arquivo "$DB")
        _ag_db=$(date +%s)
        if [ "$_m_db" -gt 0 ] 2>/dev/null &&
           [ $((_ag_db - _m_db)) -lt "$ASSENTAR" ]; then
            colher=0
        else
            colher=1
        fi
    else
        colher=0
    fi

    if [ "$colher" = 1 ]; then
        # A marca é atualizada ANTES da cópia. Se o player gravar durante a
        # cópia, o banco fica mais novo que a marca e o ciclo seguinte pega —
        # o contrário perderia a gravação.
        touch "$MARCA" 2>/dev/null

        # O banco é lido NO LUGAR, sem cópia.
        #
        # Aqui havia um `cp` do banco inteiro para /tmp, que é RAM. São 624 KB
        # alocados de uma vez, no exato instante em que o player está pedindo
        # os buffers da faixa nova, num aparelho que vive com 1,7 MB livres.
        # Trocar de faixa rápido travava o aparelho, e parar de scrobblar
        # resolvia — foi assim que isto foi encontrado.
        #
        # A cópia existia para se proteger de ler o banco enquanto o player
        # escreve. A proteção continua, por outro caminho: uma leitura rasgada
        # faz o r1collect falhar, e o `else` logo abaixo já põe a marca para
        # trás e tenta de novo no ciclo seguinte. Era esse o plano B desde o
        # começo; agora ele é o plano A.
        if [ -r "$DB" ]; then
            desde=$(cat "$ESTADO" 2>/dev/null)
            [ -n "$desde" ] || desde=0
            if saida=$("$COLETOR" "$DB" "$desde" "$PARCIAL" 2>>"$LOG"); then
                novas=${saida%% *}
                maior=${saida##* }
                if [ "$novas" -gt 0 ] 2>/dev/null; then
                    # Nenhum a1 aqui. O que tocou com o daemon fora do ar já
                    # foi recolhido e marcado na partida, antes deste laço
                    # começar; daqui para a frente ele está de olho, e o
                    # espaço entre duas linhas é tempo de verdade.
                    # Fila e estado avançam juntos: se a energia acabar entre
                    # as duas linhas, o pior que acontece é repetir, e o PC
                    # descarta rowid repetido.
                    # A faixa que estava aberta acabou: a linha nova é a
                    # prova de que outra começou. Fecha com o que foi medido.
                    fechar_faixa_atual

                    # Mais de uma linha nova na MESMA colheita.
                    #
                    # Acontece porque o laço cai para 60 s com o aparelho
                    # ocioso: começar um álbum pode pôr duas faixas no banco
                    # antes da primeira olhada. Todas recebem o mesmo carimbo
                    # — o desta colheita —, então o espaço entre elas dá zero
                    # e todas menos a última saíam com "não ouviu nada".
                    #
                    # Foi exatamente o relato: "a primeira faixa de qualquer
                    # álbum nunca sobe, sobe a seguinte; e ela aparece no
                    # scrobbling now". A primeira aparecia no tocando agora
                    # (que não depende disto) e morria na hora de subir.
                    #
                    # As anteriores à última não foram vistas começar, que é a
                    # mesma situação do lote atrasado — e o a1 já manda o PC
                    # reconstruir as horas para trás pela duração de cada uma.
                    # Só a última é a que está tocando agora, e essa é medida.
                    if [ "$novas" -gt 1 ]; then
                        # Várias faixas numa colheita só: reparte a JANELA
                        # REAL entre elas, em vez de dar a duração de cada uma.
                        #
                        # Aqui eu marcava com a1, que é o tratamento do que
                        # tocou com o daemon fora do ar — e o a1 reconstrói
                        # supondo que cada faixa tocou inteira. Pulando
                        # depressa, três linhas caem na mesma passada e as
                        # três subiam como ouvidas por completo. Foi relatado
                        # com print: cinco faixas a um minuto uma da outra,
                        # todas contabilizadas.
                        #
                        # O que se sabe é quanto tempo passou desde a última
                        # olhada. Se três linhas entraram em 45 segundos,
                        # nenhuma tocou mais que quinze — e a regra dos 90%
                        # descarta as três, que é o certo.
                        # A hora é pega AQUI: o _ag_col só é calculado mais
                        # abaixo, e usá-lo antes deixava a conta com uma
                        # variável vazia — o que mata o daemon na primeira
                        # colheita, sem dizer nada.
                        _ag_jan=$(date +%s)
                        _jan=$((_ag_jan - ${ultima_colheita:-$_ag_jan}))
                        [ "$_jan" -lt 0 ] 2>/dev/null && _jan=0
                        _cada=$((_jan / novas))
                        _i=0
                        while IFS= read -r _l; do
                            _i=$((_i + 1))
                            [ "$_i" -ge "$novas" ] && break
                            printf 't1\t%s\t%s\t%s\tfim\n' \
                                "$(echo "$_l" | cut -f2)" "$_cada" \
                                "$intervalo" >> "$FILA"
                        done < "$PARCIAL"
                        registrar "$novas linhas numa colheita so;" \
                                  "${_jan}s repartidos, ${_cada}s para cada" \
                                  "uma das $((novas - 1)) primeiras"
                    fi
                    ultima_colheita=$(date +%s)
                    cat "$PARCIAL" >> "$FILA"
                    echo "$maior" > "$ESTADO"
                    # A última linha desta colheita é a faixa que ACABOU DE
                    # COMEÇAR, e a contagem dela começa QUANDO ELA COMEÇOU —
                    # não quando o daemon percebeu.
                    #
                    # A diferença entre as duas coisas é um intervalo do laço,
                    # até quinze segundos, e ela some do começo de toda faixa.
                    # O próprio banco diz a hora certa: a mtime dele é o
                    # instante em que o player gravou a linha. Já é lida a
                    # cada volta para saber se o banco mudou; usá-la aqui não
                    # custa nada e tira o erro na fonte, em vez de descontá-lo
                    # depois na margem.
                    #
                    # Só é aceita se fizer sentido: no passado, e não mais
                    # velha que duas voltas lentas. Um relógio recém-acertado
                    # ou um cartão com data errada cai na reserva de sempre.
                    _ag_col=$(date +%s)
                    aberta_em=$(data_do_arquivo "$DB")
                    if [ "$aberta_em" -gt 0 ] 2>/dev/null &&
                       [ "$aberta_em" -le "$_ag_col" ] &&
                       [ $((_ag_col - aberta_em)) -le $((LENTO * 2)) ]; then
                        # A mtime tem precisão de segundo, e a linha pode ter
                        # sido gravada um instante antes do arquivo fechar.
                        atual_granul=2
                        registrar "$novas nova(s), rowid ate $maior;" \
                                  "inicio pela mtime do banco," \
                                  "$((_ag_col - aberta_em))s atras"
                    else
                        aberta_em=$_ag_col
                        # Sem hora confiável, volta a valer o que valia: o
                        # começo está em algum ponto do último intervalo.
                        atual_granul=$intervalo
                        registrar "$novas nova(s), rowid ate $maior;" \
                                  "mtime do banco nao serve, inicio pelo" \
                                  "relogio (ate ${intervalo}s de atraso)"
                    fi
                    atual_rowid=$maior
                    atual_ouvido=0
                    atual_gravado=0
                    # Uma linha nova é uma faixa começando: está tocando.
                    pcm_antes=1
                    ultimo_olhar=$aberta_em
                    parado_desde=""
                    atualizar_csv
                    # A anterior, essa sim, está fechada: a linha nova diz a
                    # hora em que ela parou. Se houver rede, não há razão para
                    # esperar o relógio dos doze minutos — só a espera curta
                    # que junta uma sequência de pulos num envio só.
                    adiantar_envio
                elif [ -n "$maior" ]; then
                    echo "$maior" > "$ESTADO"
                fi
            else
                # Leitura falhou (cópia rasgada, provavelmente). A marca é
                # posta para trás para o ciclo seguinte tentar de novo; o
                # rowid guardado não avançou, então nada se perdeu.
                registrar "leitura falhou; tentando de novo no proximo ciclo"
                touch -t 200001010000 "$MARCA" 2>/dev/null
            fi
            # Só o parcial: o banco não é mais copiado, e apagá-lo seria
            # apagar o histórico do player.
            rm -f "$PARCIAL"
        fi
    fi

    if [ -f "$MAIS" ] && [ "$MAIS" -nt "$MARCA2" ]; then
        mexeu=1
        touch "$MARCA2" 2>/dev/null
        printf 'm1\t%s\n' "$(date +%s)" >> "$FILA"
    fi

    # Uma faixa do Tidal em curso conta como atividade. Sem isto o laço cai
    # para 60 s e a troca de faixa é notada até um minuto depois — foi o que
    # produziu um registro de "274s de 227s" no aparelho: a faixa tinha
    # acabado havia 47 segundos e ninguém tinha olhado ainda. A hora de
    # início da faixa seguinte herdava o mesmo atraso.
    [ -n "$tid_id" ] && mexeu=1

    # Uma faixa local tocando também conta como atividade, pelo mesmo motivo e
    # mais um. O motivo antigo: sem isso o laço cai para 60 s e a troca de
    # faixa demora até um minuto para ser notada. O motivo novo: cada vez que
    # o áudio começa ou para entre duas olhadas, o pedaço tocado ali some da
    # conta — a 60 s some até um minuto, e some no fim da faixa, que é onde se
    # decide se ouviu os 90%. A 15 s o erro cabe no bolso.
    #
    # Isto não acorda o laço à toa: só vale enquanto há som saindo. Pausado ou
    # parado, ele volta a dormir.
    [ -n "$aberta_em" ] && [ "$pcm_aberto" = 1 ] && mexeu=1

    if [ "$mexeu" = 1 ]; then
        ultimo=$(date +%s)
        intervalo=$RAPIDO
        quietos=0
        ativo=1
    else
        quietos=$((quietos + 1))
        if [ "$quietos" -ge "$QUIETOS" ]; then
            if [ "$ativo" = 1 ]; then
                # Fecha a sessão com a hora do ÚLTIMO evento, não a de agora:
                # o que se sabe é que depois dessa hora nada mais aconteceu.
                # Quanto a última faixa tocou de fato, ninguém no aparelho
                # registra — quem decide o que fazer com isso é o PC.
                printf 'i1\t%s\n' "$ultimo" >> "$FILA"
                ativo=0
            fi
            intervalo=$LENTO
            # Nada acontecendo há um bom tempo: é a hora certa de podar a
            # fila. Aqui não há áudio para atrapalhar, e a função sai por
            # conta própria quando não é o caso — em regime normal ela não
            # cria processo nenhum.
            podar_fila
        fi
    fi

    # Com faixas do Tidal esperando os metadados, o laço fica no ritmo rápido.
    #
    # O tidal_resolver tira UMA por volta, de propósito — é o que garante que
    # nunca haja dois processos grandes ao mesmo tempo. Mas a 60 s por volta,
    # uma sessão de vinte faixas levaria um quarto de hora para terminar de
    # aparecer no Last.fm; a 15 s leva cinco minutos.
    #
    # Isto não é ficar acordado à toa: enquanto há pendente, há trabalho de
    # verdade a fazer a cada volta. E quando o arquivo esvazia, o laço volta a
    # desacelerar sozinho.
    [ -s "$PEND_TIDAL" ] && intervalo=$RAPIDO

    # Pausar não é parar, e o aparelho diz a diferença.
    #
    # Fechar a faixa no primeiro segundo de silêncio foi o que produziu o
    # relato de "faixas que eu ouvi não aparecem": pausar para atender alguém
    # fecha o pcm igualzinho a desligar o aparelho, e a faixa ia embora com
    # meia escuta — abaixo do mínimo, ou seja, descartada. Quem pausa no meio
    # de uma música e volta ouviu a música.
    #
    # Medido no aparelho, com uma faixa tocando e a pausa apertada de verdade:
    #
    #     ...  50s  pcm=1  rowid=261  arq=.../After Dark.flac   tocando
    #     ...  50s  pcm=0  rowid=261  arq=.../After Dark.flac   PAUSADO
    #     ...  29s  pcm=1  rowid=261  arq=.../After Dark.flac   voltou
    #
    # O pcm fecha, o ARQUIVO não. E o rowid não mudou: retomar não escreve
    # linha nenhuma no histórico, então não há nada além disto que avise que a
    # faixa continua. Parado de verdade — fim da lista, aparelho ocioso — o
    # arquivo também fecha, e aí `arq` vem vazio.
    #
    # Daí a regra, que é observação e não temporizador:
    #
    #     pcm=1                  → tocando, conta o tempo
    #     pcm=0 e arquivo aberto → pausado, não conta e não fecha
    #     pcm=0 e nada aberto    → parou, fecha a faixa
    #
    # O teto de pausa existe só para a faixa não ficar presa para sempre se
    # alguém pausar e largar o aparelho ligado: passado ele, o que foi medido
    # vai embora e a faixa segue para o Last.fm se tiver dado o mínimo.
    # O `precisa_estado` no teste não é zelo: sem ele isto decide no escuro.
    #
    # A sondagem acontece no TOPO do laço e só quando há faixa aberta. Na
    # volta em que a colheita abre uma faixa, portanto, ninguém olhou o pcm
    # ainda — as variáveis valem o zero com que começam a volta. Ler isso como
    # "não há som e nenhum arquivo aberto" fechava a faixa no mesmo instante
    # em que ela abria, com zero segundo ouvido. Nada é decidido sobre um
    # estado que não foi medido; a volta seguinte já mede.
    if [ -n "$aberta_em" ] && [ "$precisa_estado" = 1 ]; then
        _ag=$(date +%s)
        if [ "$pcm_aberto" = 1 ]; then
            if [ -n "$parado_desde" ]; then
                registrar "audio voltou apos $((_ag - parado_desde))s de pausa;" \
                          "faixa $atual_rowid continua, $atual_ouvido s ate aqui"
                parado_desde=""
            fi
        else
            if [ -z "$parado_desde" ]; then
                parado_desde=$_ag
                # O f1 continua saindo na hora exata em que o som parou: ele é
                # o teto que as versões antigas do PC usam para deduzir o fim,
                # e serve de diagnóstico. Quem lê o t1 nem olha para ele.
                printf 'f1\t%s\n' "$_ag" >> "$FILA"
            fi
            if [ -z "$local_tocando" ]; then
                fechar_faixa_atual
                registrar "audio parou e o arquivo fechou; faixa encerrada"
                aberta_em=""
                parado_desde=""
                atualizar_csv
                adiantar_envio
            elif [ $((_ag - parado_desde)) -ge "$PAUSA_MAX" ]; then
                fechar_faixa_atual
                registrar "pausa passou de ${PAUSA_MAX}s; faixa encerrada com" \
                          "o que foi medido"
                aberta_em=""
                parado_desde=""
                atualizar_csv
                adiantar_envio
            fi
        fi
    fi

    olhar_tocando
    olhar_tidal

    # A faixa do Tidal acabou de trocar: a próxima volta vem em CALMA
    # segundos, e não nos 15 de sempre.
    #
    # É o que faz a janela calma significar alguma coisa. Ela é de 6 segundos,
    # mas o laço acorda de 15 em 15 — sem isto o anúncio esperaria o tique
    # seguinte de qualquer jeito, e os 6 virariam 15. Uma volta adiantada por
    # troca de faixa, e nada mais: em regime parado nada muda.
    #
    # E fica AQUI, depois da olhar_tidal, porque é ela quem levanta a bandeira.
    # Na primeira tentativa esta verificação estava lá em cima, antes da
    # chamada — então a pressa só era vista na volta SEGUINTE, quinze segundos
    # depois, que é exatamente o que ela existe para evitar. Medido no
    # aparelho: 26 segundos, duas vezes, sem variação nenhuma.
    if [ "$tid_apressar" = 1 ]; then
        tid_apressar=0
        intervalo=$CALMA
    fi

    # O WiFi acabou de aparecer? Então não espera o relógio: manda agora.
    #
    # É o caso de quem ouviu música a viagem inteira sem rede e chegou em
    # casa. Conferir isso é o mesmo teste de rota de sempre, que não custa
    # processo nenhum.
    if tem_rede; then
        if [ "$tinha_rede" = 0 ]; then
            registrar "wifi apareceu; enviando o que estava guardado"
            desde_envio=$proximo_envio
            proximo_envio=$ENVIO
        fi
        tinha_rede=1
    else
        tinha_rede=0
    fi

    # O relógio do envio. Ele conta segundos de verdade, não voltas, porque o
    # intervalo do laço muda conforme você está ouvindo ou não.
    desde_envio=$((desde_envio + intervalo))
    # O envio espera a janela calma, pela mesma razão do anúncio: ele roda o
    # r1send e o curl, e o instante da troca de faixa é o único que a medição
    # apontou como ruim. O relógio continua correndo, então ele sai na primeira
    # volta em que for seguro — nada se acumula sem sair.
    #
    # Tocando do cartão isto não vale: lá a olhar_tidal nem roda, tid_rede_ok
    # fica em 1 e o envio segue como sempre foi.
    if [ "$tid_rede_ok" != 1 ]; then
        desde_envio=$proximo_envio
    elif [ "$desde_envio" -ge "$proximo_envio" ]; then
        desde_envio=0
        # O relógio do teto recomeça: o que estava pendente foi tratado.
        pendente_desde=""
        # Com o Tidal tocando, dois lotes por rodada em vez de vinte. Uma fila
        # grande sairia como vinte requisições seguidas — cada uma é modesta
        # sozinha (896 KB de pico, medido), mas emendadas viram atividade
        # sustentada bem no meio da reprodução. O resto sai na rodada seguinte,
        # que o adiantar_envio já puxa para perto.
        if [ -n "$tid_id" ]; then
            tentar_enviar 2
        else
            tentar_enviar
        fi
        rc=$?
        if [ "$rc" = 0 ]; then
            registrar "enviado ao Last.fm"
            proximo_envio=$ENVIO
            # A planilha do cartão tem uma coluna de situação; depois de um
            # envio bem-sucedido ela está desatualizada até ser reescrita.
            atualizar_csv
        elif [ "$rc" = 3 ] || [ "$rc" = 2 ]; then
            # Nada a enviar, ou nenhuma rede à vista. Nenhum dos dois é falha:
            # o relógio fica no normal, e no instante em que o WiFi voltar a
            # fila sai — sem herdar recuo nenhum de horas sem rede.
            proximo_envio=$ENVIO
        else
            # Falha de verdade: o serviço recusou, ou o curl não completou.
            # Aí sim vale esperar o dobro, até o teto, para não martelar.
            proximo_envio=$((proximo_envio * 2))
            [ "$proximo_envio" -gt "$ENVIO_MAX" ] && proximo_envio=$ENVIO_MAX
            registrar "proxima tentativa em ${proximo_envio}s"
        fi
        rm -f "$CORPO" "$IDS" "$RESP"
    fi

    espera "$intervalo"
done
