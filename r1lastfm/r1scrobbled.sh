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
# Saber QUANDO a faixa entrou não diz por quanto tempo ela foi ouvida, e o
# Last.fm só aceita como execução o que passou da metade (ou de 4 minutos).
# O intervalo entre duas linhas dá esse tempo para todas as faixas menos a
# última de cada sessão, que não tem uma linha seguinte para fechá-la.
#
# Por isso o most_played.db do cartão também é vigiado: ele é gravado num
# momento diferente do ciclo da faixa, e cada mudança dele vira um marcador
# com hora. Só o mtime, sem abrir o arquivo — ele tem linhas corrompidas pelo
# próprio player (uma com o nome de uma faixa e o caminho de outra) e não é
# confiável como fonte de metadados.
#
# Tocando agora
# --------------
# Opcional, desligado por padrão. Quando ligado, o daemon avisa o Last.fm da
# faixa em reprodução e ela aparece pulsando no seu perfil. Isso exige o WiFi
# ligado, e é o WiFi que custa bateria — a detecção em si são 10 ms por volta.
#
# A faixa atual não sai do banco (que só é escrito no fim dela), e sim do
# arquivo que o player mantém aberto, visto em /proc/PID/fd.
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
#   m1  o most_played foi tocado nesta hora
#   i1  nada mais aconteceu depois desta hora
#   b1  o daemon começou (houve desligamento ou reinício antes disto)
#   a1  as próximas n linhas já estavam no banco quando ele começou: tocaram
#       sem ninguém olhando, e o PC reconstrói as horas em vez de deduzi-las
#   c1  o relógio estava obviamente errado; o PC vai desconfiar das horas
#
# Para desligar tudo: apague /usr/data/scrobble e reinicie. Nada mais no
# aparelho é tocado.

DIR=/usr/data/scrobble
DB=/usr/data/usrlocal_media.db
MAIS=/usr/data/mnt/sd_0/.temp/most_played.db
COLETOR=$DIR/r1collect
REMETENTE=$DIR/r1send
CURL=$DIR/curl
FILA=$DIR/fila.tsv
ESTADO=$DIR/estado
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
ESPERA_IMEDIATO=15

# Antes disto (1 de janeiro de 2024) o relógio claramente não foi acertado.
# O Last.fm recusa horas com mais de 14 dias, então é melhor marcar do que
# mandar lixo.
PISO=1704067200

[ -r "$DIR/conf" ] && . "$DIR/conf"

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
achar_cartao() {
    for c in $CARTOES; do
        [ -d "$c" ] || continue
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

limpar() {
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

# Uma chamada ao curl, com o IP já resolvido quando dá.
chamar_curl() {
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
# O banco não serve para isto: ele só ganha a linha quando a faixa ACABA, e a
# essa altura não há mais nada tocando para anunciar. A fonte é outra — o
# player mantém o arquivo de áudio aberto, e /proc/PID/fd mostra qual
# (verificado no aparelho: muda ao pular de faixa).
#
# O r1collect faz a varredura inteira num exec só. Fazer isso em shell
# custaria pidof + ls + grep, quatro processos em vez de um.
anunciar() {
    cp -f "$DB" "$COPIA" 2>/dev/null || return 1
    "$COLETOR" buscar "$COPIA" "$1" > "$META" 2>>"$LOG"
    rc=$?
    rm -f "$COPIA"
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
    rm -f "$CORPO_NP" "$RESP_NP"
    # "Tocando agora" não vai para fila: se não deu, o momento passou. Não
    # vale gastar rádio tentando de novo uma faixa que já mudou.
    [ "$rc" = 0 ] || return 1
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
    tid_pais=$("$CURL" -sS --max-time 25 --cacert "$t_ca" $t_res \
        -H "Authorization: Bearer $t_tok" -H "Accept: application/json" \
        "https://$TIDAL_API/v1/sessions" 2>>"$LOG" \
        | tr ',' '\n' | grep countryCode | tr -d '"' | cut -d: -f2)
    [ -n "$tid_pais" ] || return 1
    echo "$tid_pais"
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
    "$CURL" -sS --max-time 25 --cacert "$t_ca" $t_res \
        -H "Authorization: Bearer $t_tok" -H "Accept: application/json" \
        "https://$TIDAL_API/v1/tracks/$1?countryCode=$t_pais" \
        -o "$TIDAL_JSON" 2>>"$LOG" || return 1
    # Um campo por linha, como o `r1collect buscar` já faz.
    { read -r tid_art; read -r tid_tit; read -r tid_alb; read -r tid_dur; } \
        <<FIM_META
$("$REMETENTE" tidalinfo "$TIDAL_JSON" 2>>"$LOG")
FIM_META
    rm -f "$TIDAL_JSON"
    [ -n "$tid_art" ] && [ -n "$tid_tit" ] || return 1
    case "$tid_dur" in ''|*[!0-9]*) tid_dur=0 ;; esac
    return 0
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

    # Parou de tocar (ou passou a tocar arquivo local): fecha a faixa aberta
    # com a hora de agora. O pcm fecha junto com o áudio, então "agora" está a
    # no máximo um ciclo do fim real.
    if [ "$t_toca" = 0 ]; then
        if [ -n "$tid_id" ]; then
            tidal_anotar "$t_agora" "$tid_desde"
            tid_id=""; tid_desde=0
        fi
        return 0
    fi

    # O id só muda quando entra outra faixa do Tidal; tocar arquivo local não
    # mexe nele. Um id vazio quer dizer que o campo ainda não existe (nunca
    # se usou o Tidal neste aparelho).
    [ -n "$t_novo" ] || return 0

    if [ "$t_novo" != "$tid_id" ]; then
        [ -n "$tid_id" ] && tidal_anotar "$t_agora" "$tid_desde"
        tid_id="$t_novo"
        tid_desde="$t_agora"
        if tidal_meta "$t_novo"; then
            [ "$AGORA" = 1 ] && anunciar_tidal
        else
            # Sem metadados a faixa não vira scrobble. Acontece quando a rede
            # cai no meio; a próxima troca tenta de novo.
            registrar "tidal: nao consegui os dados da faixa $t_novo"
            tid_id=""
        fi
        return 0
    fi

    # Mesma faixa há tempo suficiente para ela ter acabado: ou repetiu, ou o
    # player seguiu para outra que ainda não vimos. Fecha esta e recomeça a
    # contagem, que é o que faz o "repetir uma música" continuar scrobblando.
    if [ "$tid_dur" -gt 0 ] 2>/dev/null &&
       [ $((t_agora - tid_desde)) -ge "$tid_dur" ]; then
        t_fim=$((tid_desde + tid_dur))
        tidal_anotar "$t_fim" "$tid_desde"
        tid_desde=$t_fim
        [ "$AGORA" = 1 ] && anunciar_tidal
    fi
}

# O "tocando agora" da faixa do Tidal. Mesmo caminho do local, sem a parte
# que consulta o banco: os metadados já estão em mãos.
anunciar_tidal() {
    [ -x "$REMETENTE" ] && [ -x "$CURL" ] && [ -s "$SK" ] || return 1
    tem_rede || return 1
    t_ca=$(cacert); [ -n "$t_ca" ] || return 1
    "$REMETENTE" agora "$SK" "$SEGREDO" "$APIKEY" "$CORPO_NP" \
        "$tid_art" "$tid_tit" "$tid_alb" "$tid_dur" >/dev/null 2>>"$LOG" || return 1
    [ -n "$ip_api" ] || ip_api=$(resolver "$API_HOST")
    t_res=""
    [ -n "$ip_api" ] && t_res="--resolve $API_HOST:443:$ip_api"
    "$CURL" -sS --max-time 20 --cacert "$t_ca" $t_res \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -A "hiby-r1-scrobbler/1.0" \
        --data-binary "@$CORPO_NP" -o "$RESP_NP" \
        "$API" 2>>"$LOG"
    rc=$?
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
tentar_enviar() {
    pode_enviar || return 2
    tem_rede || return 2
    # Uma resolução por rodada, reaproveitada pelos lotes seguintes.
    ip_api=$(resolver_api)
    [ -n "$ip_api" ] || registrar "nao resolvi $API_HOST; deixando o curl tentar"
    voltas=0
    while [ "$voltas" -lt 20 ]; do
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

agora=$(date +%s)
printf 'b1\t%s\n' "$agora" >> "$FILA"
# Quantas colheitas esta execução já fez. A de número zero é a que encontra o
# que tocou enquanto o daemon estava fora do ar — ver o comentário no laço.
colheita=0
# Hora em que a faixa local hoje em curso entrou no histórico. Vazio quando
# não há nenhuma em aberto. Ver o comentário do f1, no laço.
aberta_em=""
if [ "$agora" -lt "$PISO" ]; then
    printf 'c1\t%s\n' "$agora" >> "$FILA"
    registrar "relogio em $agora, anterior ao piso $PISO: horas suspeitas"
fi
registrar "r1scrobbled iniciado em $(date), pid $$"
if [ -n "$sd" ]; then
    registrar "registro e planilha no cartao: $sd"
    # A planilha é reescrita já na partida. Sem isto ela só apareceria depois
    # da primeira faixa, e quem instalou e foi conferir o cartão na hora
    # encontraria a pasta vazia sem entender por quê.
    atualizar_csv
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
    fi

    if [ "$DB" -nt "$MARCA" ]; then
        mexeu=1
        # A marca é atualizada ANTES da cópia. Se o player gravar durante a
        # cópia, o banco fica mais novo que a marca e o ciclo seguinte pega —
        # o contrário perderia a gravação.
        touch "$MARCA" 2>/dev/null

        if cp -f "$DB" "$COPIA" 2>/dev/null; then
            desde=$(cat "$ESTADO" 2>/dev/null)
            [ -n "$desde" ] || desde=0
            if saida=$("$COLETOR" "$COPIA" "$desde" "$PARCIAL" 2>>"$LOG"); then
                novas=${saida%% *}
                maior=${saida##* }
                if [ "$novas" -gt 0 ] 2>/dev/null; then
                    # A PRIMEIRA colheita de uma execução é diferente de todas
                    # as outras, e essa diferença precisa chegar ao PC.
                    #
                    # Nas colheitas seguintes o daemon estava de olho: entre
                    # uma olhada e a outra passaram quinze segundos, então o
                    # espaço entre duas linhas é tempo real e dá para dizer se
                    # a faixa tocou inteira ou foi pulada.
                    #
                    # Na primeira não. O que está no banco já estava lá antes
                    # de o daemon existir; tocou enquanto ninguém olhava. Todas
                    # essas linhas chegam com a mesma hora — a de agora — e a
                    # conta do "espaço desde a anterior" dava zero. Era daí que
                    # vinha o "ouvi o disco inteiro e apareceu 0s": não era um
                    # erro de conta, era o daemon não ter estado lá.
                    #
                    # O marcador a1 diz ao r1send quantas linhas são dessas,
                    # para ele reconstruir as horas em vez de inventar zeros.
                    if [ "$colheita" = 0 ]; then
                        printf 'a1\t%s\t%s\n' "$(date +%s)" "$novas" >> "$FILA"
                    fi
                    colheita=$((colheita + 1))
                    # Fila e estado avançam juntos: se a energia acabar entre
                    # as duas linhas, o pior que acontece é repetir, e o PC
                    # descarta rowid repetido.
                    cat "$PARCIAL" >> "$FILA"
                    echo "$maior" > "$ESTADO"
                    registrar "$novas nova(s), rowid ate $maior"
                    # A última linha desta colheita é a faixa que ACABOU DE
                    # COMEÇAR. Ela fica em aberto até outra começar ou até o
                    # áudio parar; é isso que liga a sondagem do pcm.
                    aberta_em=$(date +%s)
                    atualizar_csv
                    # A anterior, essa sim, está fechada: a linha nova diz a
                    # hora em que ela parou. Se houver rede, não há razão para
                    # esperar o relógio dos doze minutos — só a espera curta
                    # que junta uma sequência de pulos num envio só.
                    if [ "$IMEDIATO" = 1 ] && [ "$proximo_envio" = "$ENVIO" ]; then
                        falta=$((proximo_envio - ESPERA_IMEDIATO))
                        [ "$falta" -lt 0 ] && falta=0
                        if [ "$desde_envio" -lt "$falta" ]; then
                            desde_envio=$falta
                        fi
                    fi
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
            rm -f "$COPIA" "$PARCIAL"
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
        fi
    fi

    # O "tocando agora" tem de sair enquanto a faixa toca, então ele não
    # espera o relógio de doze minutos — olha a cada volta. Custa 10 ms, e
    # só quando está ligado E o WiFi já está no ar.
    # Uma varredura de /proc por volta, compartilhada pelos dois
    # acompanhamentos. Antes eram duas, e a segunda respondia a mesma coisa.
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
    #   • fora disso, só quando o user.ini mudar.
    precisa_tidal=0
    if [ "$TIDAL" = 1 ]; then
        [ -n "$tid_id" ] && precisa_tidal=1
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
    # estiver assim é preciso olhar o pcm para saber a hora em que parou; sem
    # essa hora, a última faixa de cada sessão fica sem fechamento e nunca
    # sobe. Assim que o áudio para, o f1 é escrito e a sondagem se desliga
    # sozinha — o ciclo parado volta a não criar processo nenhum.
    [ -n "$aberta_em" ] && precisa_estado=1

    pcm_aberto=0
    local_tocando=""
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

    # A faixa local em aberto e a hora em que ela parou.
    #
    # A linha do histórico entra quando a faixa COMEÇA — observado ao vivo no
    # aparelho: o player trocou de faixa e a linha apareceu no mesmo segundo,
    # com o áudio ainda tocando por mais quarenta e cinco. Então cada linha
    # nova fecha a anterior, e a última de uma sequência só fecha quando o
    # áudio para. É essa hora que o f1 carrega.
    #
    # Sem ele a última faixa de cada sessão ficava sem fim conhecido, e o PC
    # não tinha como saber se ela tocou inteira ou se o aparelho foi desligado
    # no primeiro refrão.
    if [ -n "$aberta_em" ] && [ "$pcm_aberto" = 0 ]; then
        printf 'f1\t%s\n' "$(date +%s)" >> "$FILA"
        registrar "audio parou; faixa aberta desde $aberta_em fechada"
        aberta_em=""
        atualizar_csv
    fi

    olhar_tocando
    olhar_tidal

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
    if [ "$desde_envio" -ge "$proximo_envio" ]; then
        desde_envio=0
        tentar_enviar
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
