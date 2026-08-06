"""Instalar, remover e consultar o coletor no aparelho, por ADB.

Tudo o que este módulo escreve no R1 fica em /usr/data/scrobble, e a única
coisa que ele toca fora dessa pasta é a linha que inicia o daemon dentro do
/usr/data/init.sh. Desinstalar é apagar a pasta e tirar a linha — nada mais
no aparelho é alterado em momento nenhum.
"""

from __future__ import annotations

import os
import posixpath
import time
from dataclasses import dataclass

from .adbtool import Adb
from .applog import Log
from .idioma import t
from .runner import InstallerError

DIR = "/usr/data/scrobble"
BIN = DIR + "/r1collect"
REMETENTE = DIR + "/r1send"
CURL = DIR + "/curl"
DAEMON = DIR + "/r1scrobbled"
FILA = DIR + "/fila.tsv"
ESTADO = DIR + "/estado"
# A medição da faixa em curso, salva de tempos em tempos para um travamento
# não levá-la junto. Existe só enquanto há faixa aberta. Ver o r1scrobbled.sh.
MEDINDO = DIR + "/medindo"
# Qual dos dois bancos do player o coletor está seguindo. Escrito por ele; aqui
# só é lido, para a tela poder dizer quando o banco está no cartão.
BANCO_ATUAL = DIR + "/banco"
ENVIADOS = DIR + "/enviados"
CONF = DIR + "/conf"
SK = DIR + "/sk"
SEGREDO = DIR + "/segredo"
APIKEY = DIR + "/apikey"
CACERT = DIR + "/cacert.pem"
# Um segundo lugar onde procurar, para quem já tiver um pacote de
# certificados no cartao vindo de outro uso. O daemon aceita os dois.
CACERT_SD = "/data/mnt/sd_0/.r1lastfm/cacert.pem"
VERSAO_ARQ = DIR + "/versao"
# A trava fica em /tmp, não em /usr/data: um arquivo de pid tem de sumir no
# boot. Ver o comentário longo no r1scrobbled.sh.
TRAVA = "/tmp/.r1sc.rodando"
TRAVA_ANTIGA = DIR + "/.rodando"
INIT = "/usr/data/init.sh"
# Onde procurar o cartão, na mesma ordem que o daemon usa. Os três caminhos
# são o mesmo cartão visto de lugares diferentes: /data é um link para
# /usr/data, e alguns firmwares montam também em /mnt.
CARTOES = ("/usr/data/mnt/sd_0", "/data/mnt/sd_0", "/mnt/sd_0")
PASTA_SD = "r1lastfm"
# Quem executa o init.sh — e o motivo de tudo isto existir.
#
# Nada no firmware DE FÁBRICA roda /usr/data/init.sh. Quem o roda é uma versão
# remendada do lançador do player, que outros mods do R1 instalam ao aplicar o
# patch de firmware. Sem esse patch, pôr uma linha no init.sh não inicia coisa
# alguma — o coletor fica instalado e nunca sobe.
#
# Isso passou meses despercebido porque o aparelho onde tudo foi desenvolvido
# já tinha outro mod instalado. Quem instalou num R1 de fábrica viu "Coletor
# instalado. Parado." e não tinha como adivinhar por quê.
LANCADOR = "/usr/bin/hiby_player.sh"

# Sobe a cada mudança que valha reinstalar no aparelho. A tela compara com o
# que está gravado lá e só oferece a atualização quando há diferença.
VERSAO = 19
# As versões que existem. O que cada uma trouxe está no catálogo de textos,
# sob "novidade.<n>", porque isso aparece na tela e tem de estar traduzido.
NOVIDADES = (19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1)


def novidade(versao: int) -> str:
    """O que a versão trouxe, no idioma de agora."""
    return t(f"novidade.{versao}")

# A linha que entra no init.sh. O marcador permite achar e remover depois sem
# tocar em mais nada do arquivo.
MARCA_INI = "# --- scrobbler do Last.fm (inicio) ---"
MARCA_FIM = "# --- scrobbler do Last.fm (fim) ---"
BLOCO = (
    MARCA_INI + "\n"
    "[ -x " + DAEMON + " ] && " + DAEMON + " &\n"
    + MARCA_FIM
)


@dataclass
class Situacao:
    instalado: bool = False
    rodando: bool = False
    no_init: bool = False
    linhas_fila: int = 0
    execucoes: int = 0
    enviadas: int = 0
    ultimo_rowid: int = 0
    espera_sem_fork: bool | None = None
    envio_pronto: bool = False
    tem_curl: bool = False
    tem_chave: bool = False
    tem_cacert: bool = False
    wifi_agora: bool = False
    versao: int = 0
    tocando_agora: bool = False
    # O firmware deste aparelho chega a executar o /usr/data/init.sh?
    # None = não deu para saber (lançador ausente ou ilegível).
    init_roda: bool | None = None
    ultimo_envio: str = ""
    # O que o daemon disse ao cair para o `sleep`, com as palavras dele.
    motivo_espera: str = ""
    detalhe: str = ""

    @property
    def desatualizado(self) -> bool:
        return self.instalado and self.versao < VERSAO

    # Quantas o r1send ainda mandaria. -1 = ele não estava lá para responder.
    enviaveis: int = -1
    # Caminho da planilha no cartão, vazio quando ela ainda não existe.
    csv_cartao: str = ""
    # A pasta do cartão onde dá para escrever, vazia quando não há cartão
    # gravável. É diferente da anterior: numa instalação nova existe
    # cartão e ainda não existe planilha, e confundir os dois fazia a tela
    # dizer "nenhum cartão gravável" para quem tinha o cartão ali.
    pasta_cartao: str = ""
    # Qual dos dois bancos do player o coletor está seguindo. O player pode
    # gravá-lo no cartão em vez de na memória interna (a opção
    # `tf_music_db_enable`, na tela do aparelho), e quem tinha isso ligado via
    # o programa dizer "rodando" e colher zero faixa, sem nada explicando por
    # quê. Vazio quando o coletor ainda não escolheu — instalação nova, ou uma
    # versão anterior a esta.
    banco: str = ""

    @property
    def banco_no_cartao(self) -> bool:
        return bool(self.banco) and "/mnt/" in self.banco

    @property
    def pendentes(self) -> int:
        """As que realmente ainda vão subir.

        Quando o r1send está instalado, quem responde é ele — as regras do
        envio são dele, e só ele sabe quais faixas serão recusadas de todo
        jeito. A subtração continua valendo como reserva para quando o
        aparelho ainda não tem o remetente.
        """
        if self.enviaveis >= 0:
            return self.enviaveis
        return max(0, self.execucoes - self.enviadas)

    @property
    def descartadas(self) -> int:
        """Registradas, mas que o Last.fm não aceitaria: pulos e afins."""
        if self.enviaveis < 0:
            return 0
        return max(0, self.execucoes - self.enviadas - self.enviaveis)


def situacao(adb: Adb) -> Situacao:
    """Uma consulta só, para a tela não fazer dez chamadas de ADB."""
    script = (
        f"[ -x {BIN} ] && echo BIN=1 || echo BIN=0; "
        f"[ -x {DAEMON} ] && echo DAE=1 || echo DAE=0; "
        f"[ -x {CURL} ] && [ -x {REMETENTE} ] && echo CURL=1 || echo CURL=0; "
        f"[ -s {SK} ] && [ -s {SEGREDO} ] && [ -s {APIKEY} ] && echo SK=1 || echo SK=0; "
        f"{{ [ -s {CACERT_SD} ] || [ -s {CACERT} ]; }} && echo CA=1 || echo CA=0; "
        f"grep -qF '{MARCA_INI}' {INIT} 2>/dev/null && echo INIT=1 || echo INIT=0; "
        f"p=$(cat {TRAVA} 2>/dev/null); "
        f"if [ -n \"$p\" ] && [ -d /proc/$p ]; then echo RUN=1; else echo RUN=0; fi; "
        f"echo LINHAS=$(wc -l < {FILA} 2>/dev/null || echo 0); "
        f"echo TOQUES=$(grep -c '^p1' {FILA} 2>/dev/null); "
        f"echo ENVIADAS=$(wc -l < {ENVIADOS} 2>/dev/null || echo 0); "
        # Quantas AINDA PODEM ir. Não é execuções menos enviadas: dessa conta
        # saíam faixas que o Last.fm nunca aceitaria — pulos, faixas curtas
        # demais, horas velhas demais — e o cartão dizia "43 esperando" para
        # sempre, sem nunca diminuir, enquanto o envio respondia "não havia
        # nada pendente". Quem é capaz de responder isso é o próprio r1send,
        # que aplica as mesmas regras do envio.
        f"echo ENVIAVEIS=$([ -x {REMETENTE} ] && {REMETENTE} listar {FILA} "
        f"{ENVIADOS} 2>/dev/null | wc -l || echo -1); "
        # Onde a planilha foi parar — e, separadamente, se há cartão.
        #
        # Isto perguntava só pelo arquivo, e a tela concluía dele que não havia
        # cartão gravável. Numa instalação nova o arquivo ainda não existe, e
        # a pessoa recebia "nenhum cartão de memória gravável encontrado" com
        # o cartão ali, perfeitamente gravável. A pergunta e a conclusão eram
        # coisas diferentes.
        #
        # São duas perguntas, então: dá para escrever no cartão? e o arquivo
        # já está lá? A primeira é respondida do jeito que o daemon responde —
        # tentando criar a pasta e escrever nela.
        f"for c in {' '.join(CARTOES)}; do "
        f"  [ -d \"$c\" ] || continue; "
        # E há mesmo um cartão montado aí? O ponto de montagem continua
        # existindo com o slot vazio — é um diretório comum na memória
        # interna, e ele passa na prova de escrita como qualquer outro. Sem
        # esta pergunta a tela dizia "planilha no cartão" apontando para a
        # memória interna, e quando o cartão voltasse e montasse por cima, os
        # arquivos sumiam de vista. Se o /proc/mounts não der para ler, a
        # pergunta é pulada: recusar o cartão de quem tem é pior.
        f"  if [ -r /proc/mounts ]; then "
        f"    r=$(cd \"$c\" 2>/dev/null && pwd -P); "
        f"    grep -q \" $r \" /proc/mounts || continue; "
        f"  fi; "
        # A prova de escrita é um arquivo na RAIZ do cartão, criado e apagado
        # na mesma linha. Nada de `mkdir` da nossa pasta: esta consulta roda
        # antes de qualquer instalação, e uma consulta de estado não pode
        # deixar rastro no cartão de ninguém.
        f"  if : > \"$c/.r1lastfm.escrita\" 2>/dev/null; then "
        f"    rm -f \"$c/.r1lastfm.escrita\"; "
        f"    echo \"CARTAO=$c/{PASTA_SD}\"; "
        f"    [ -f \"$c/{PASTA_SD}/scrobbles.csv\" ] && "
        f"      echo \"CSV=$c/{PASTA_SD}/scrobbles.csv\"; "
        f"    break; "
        f"  fi; "
        f"done; "
        f"echo ROWID=$(cat {ESTADO} 2>/dev/null || echo 0); "
        f"echo BANCO=$(cat {BANCO_ATUAL} 2>/dev/null); "
        f"echo VERSAO=$(cat {VERSAO_ARQ} 2>/dev/null || echo 0); "
        f"grep -q '^AGORA=1' {CONF} 2>/dev/null && echo NP=1 || echo NP=0; "
        # O lançador cita o init.sh? Se não, ninguém nunca vai executá-lo.
        f"if [ -r {LANCADOR} ]; then "
        f"  grep -q '{INIT}' {LANCADOR} && echo SUP=1 || echo SUP=0; "
        f"else echo SUP=?; fi; "
        # rota default: destino 00000000 na segunda coluna do /proc/net/route
        f"awk '$2==\"00000000\"{{achou=1}} END{{print \"WIFI=\" (achou?1:0)}}' "
        f"/proc/net/route 2>/dev/null || echo WIFI=0; "
        f"echo ULTIMO=$(grep 'enviado ao Last.fm' /tmp/.r1sc.log 2>/dev/null "
        f"| tail -1); "
        f"grep -q 'sem fork' /tmp/.r1sc.log 2>/dev/null && echo FIFO=1 || "
        f"{{ grep -q 'usando sleep' /tmp/.r1sc.log 2>/dev/null && echo FIFO=0 || echo FIFO=?; }}; "
        # O motivo, com as palavras do proprio daemon. A tela dizia "este
        # busybox nao tem read -t" — e um dos dois motivos que o daemon
        # registra e justamente "'read -t' existe mas nao esperou". Eu
        # descartava a resposta e punha um palpite no lugar dela.
        f"echo ESPERA=$(grep 'usando sleep' /tmp/.r1sc.log 2>/dev/null "
        f"| tail -1)"
    )
    res = adb.shell(script, mutating=False)
    vals: dict[str, str] = {}
    for linha in res.stdout.splitlines():
        if "=" in linha:
            k, _, v = linha.strip().partition("=")
            vals[k] = v.strip()

    def num(chave: str) -> int:
        try:
            return int(vals.get(chave, "0") or 0)
        except ValueError:
            return 0

    fifo = vals.get("FIFO", "?")
    tem_curl = vals.get("CURL") == "1"
    tem_chave = vals.get("SK") == "1"
    tem_ca = vals.get("CA") == "1"
    return Situacao(
        instalado=vals.get("BIN") == "1" and vals.get("DAE") == "1",
        rodando=vals.get("RUN") == "1",
        no_init=vals.get("INIT") == "1",
        linhas_fila=num("LINHAS"),
        execucoes=num("TOQUES"),
        enviadas=num("ENVIADAS"),
        enviaveis=(num("ENVIAVEIS") if vals.get("ENVIAVEIS", "").lstrip("-")
                   .isdigit() and not vals.get("ENVIAVEIS", "").startswith("-")
                   else -1),
        ultimo_rowid=num("ROWID"),
        espera_sem_fork=(True if fifo == "1" else False if fifo == "0" else None),
        envio_pronto=tem_curl and tem_chave and tem_ca,
        tem_curl=tem_curl,
        tem_chave=tem_chave,
        tem_cacert=tem_ca,
        wifi_agora=vals.get("WIFI") == "1",
        versao=num("VERSAO"),
        tocando_agora=vals.get("NP") == "1",
        init_roda=(True if vals.get("SUP") == "1"
                   else False if vals.get("SUP") == "0" else None),
        csv_cartao=vals.get("CSV", "").strip(),
        pasta_cartao=vals.get("CARTAO", "").strip(),
        banco=vals.get("BANCO", "").strip(),
        ultimo_envio=vals.get("ULTIMO", "").strip(),
        motivo_espera=vals.get("ESPERA", "").strip(),
        detalhe=res.stdout.strip(),
    )


def instalar(adb: Adb, log: Log, coletor_local: str, daemon_local: str, *,
             rapido: int = 15, lento: int = 60, agora: bool = False,
             iniciar_no_boot: bool = True,
             remetente_local: str = "") -> None:
    """Põe o coletor no aparelho e (opcionalmente) no boot."""
    if not os.path.isfile(coletor_local):
        raise InstallerError(t("ap.err.collector.title"),
                            t("ap.err.collector.body"))
    if not os.path.isfile(daemon_local):
        raise InstallerError(t("ap.err.daemon"), daemon_local)

    log.step(t("ap.installing"))
    adb.mkdir(DIR)
    adb.push(coletor_local, BIN, mode="755")
    adb.push(daemon_local, DAEMON, mode="755")
    # O r1send vai junto, sempre.
    #
    # Ele era instalado só com o envio por WiFi, porque é ele quem assina o
    # lote. Só que é ele também quem escreve o scrobbles.csv do cartão — e
    # quem instalou apenas o coletor ficava sem planilha nenhuma, sem nada na
    # tela explicando por quê, enquanto o README prometia o arquivo. Foi
    # exatamente esse o relato: "não tem scrobbles.csv no meu cartão".
    #
    # São 118 KB e nenhuma credencial; o que depende do WiFi são o curl, os
    # certificados e a chave, que continuam onde estavam.
    if remetente_local and os.path.isfile(remetente_local):
        adb.push(remetente_local, REMETENTE, mode="755")

    # A configuração fica separada do script para que mexer nos tempos não
    # exija reenviar o daemon.
    # Em inglês de propósito: este arquivo mora no aparelho, ao lado de um
    # daemon em shell, e quem o abre está lendo o sistema, não a interface.
    conf = (f"# r1scrobbled intervals, in seconds\n"
            f"RAPIDO={int(rapido)}\n"
            f"LENTO={int(lento)}\n"
            f"# 1 = tell Last.fm what is playing now; needs Wi-Fi on\n"
            f"AGORA={1 if agora else 0}\n")
    adb.shell(f"printf '%s' {_aspas(conf)} > {CONF}")
    # A versão fica gravada para a tela saber quando vale reinstalar.
    adb.shell(f"printf '%s\\n' '{VERSAO}' > {VERSAO_ARQ}")

    # O daemon reclamaria de um /usr/data/init.sh inexistente; criar vazio é
    # inofensivo, porque o supervisor só o executa se ele existir.
    adb.shell(f"[ -f {INIT} ] || {{ printf '#!/bin/sh\\n' > {INIT}; "
              f"chmod 755 {INIT}; }}")

    if iniciar_no_boot:
        ligar_no_boot(adb, log)

    log.ok(t("ap.installed", onde=DIR))


def instalar_envio(adb: Adb, log: Log, *, remetente_local: str,
                   curl_local: str, cacert_local: str = "",
                   session_key: str, api_key: str, api_secret: str) -> None:
    """Deixa o aparelho capaz de mandar sozinho, quando houver WiFi no ar.

    A chave de sessão fica em /usr/data/scrobble/sk com modo 600. Ela não dá
    acesso à sua senha e pode ser revogada em last.fm → Configurações →
    Aplicativos, mas fica legível para quem tiver ADB no aparelho — é o mesmo
    que vale para qualquer scrobbler instalado num aparelho.
    """
    if not os.path.isfile(remetente_local):
        raise InstallerError(t("ap.err.sender.title"), t("ap.err.sender.body"))
    if not os.path.isfile(curl_local):
        raise InstallerError(t("ap.err.curl.title"), t("ap.err.curl.body"))
    if not session_key:
        raise InstallerError(t("ap.err.nokey.title"), t("ap.err.nokey.body"))

    log.step(t("ap.teaching"))
    adb.mkdir(DIR)
    adb.push(remetente_local, REMETENTE, mode="755")

    # O curl é experimentado NO APARELHO antes de tomar o lugar do que já
    # estava lá.
    #
    # Uma receita de compilação que parecia mais correta gerava um curl que
    # morria com sinal 11 em toda requisição, e quem ligou o envio por WiFi
    # recebeu isso depois de meia hora compilando:
    #     Segmentation fault
    #     CURL_FALHOU rc=139
    # sem nada na mensagem que apontasse para o binário recém-feito. Pior: ele
    # substituiu um curl que funcionava.
    #
    # Então ele entra por um nome temporário, é executado, e só vira o curl
    # oficial se responder. Um binário que não roda não derruba o que rodava.
    provisorio = CURL + ".novo"
    adb.push(curl_local, provisorio, mode="755")
    prova = adb.shell(
        f"{provisorio} --version >/dev/null 2>&1; v=$?; "
        f"{provisorio} -sS --max-time 5 -o /dev/null http://127.0.0.1:1/ "
        f">/dev/null 2>&1; r=$?; echo \"V=$v R=$r\"",
        mutating=False)
    saida = prova.stdout
    # 139 = 128+11, morto por SIGSEGV. O 7 (não conseguiu conectar) é o que se
    # espera de um curl são apontado para uma porta fechada.
    if "V=139" in saida or "R=139" in saida or "V=0" not in saida:
        adb.shell(f"rm -f {provisorio}")
        raise InstallerError(t("ap.err.curl.quebrado.title"),
                             t("ap.err.curl.quebrado.body", saida=saida.strip()))
    adb.shell(f"mv -f {provisorio} {CURL} && chmod 755 {CURL}")
    log.ok(t("ap.curl.ok"))

    if cacert_local and os.path.isfile(cacert_local):
        adb.push(cacert_local, CACERT, mode="644")

    # Sem cacert não dá para conferir quem está do outro lado da conexão, e o
    # daemon prefere adiar o envio a mandar a chave às cegas.
    tem_ca = adb.shell(
        f"{{ [ -s {CACERT_SD} ] || [ -s {CACERT} ]; }} && echo SIM || echo NAO",
        mutating=False)
    if "SIM" not in tem_ca.stdout:
        # Antes isto era só um aviso, e o resultado foi um recurso que parecia
        # instalado e nunca funcionava: sem certificados o daemon não manda
        # nada, e não havia como o usuário descobrir por quê. Melhor recusar
        # a instalação do que entregar algo mudo.
        raise InstallerError(t("ap.err.nocacert.title"),
                            t("ap.err.nocacert.body"))

    for caminho, valor in ((SK, session_key), (SEGREDO, api_secret),
                           (APIKEY, api_key)):
        adb.shell(f"printf '%s\\n' {_aspas(valor)} > {caminho}")
    adb.shell(f"chmod 600 {SK} {SEGREDO}")
    adb.shell(f"chmod 644 {APIKEY}")
    log.ok(t("ap.sending_on"))


def definir_agora(adb: Adb, log: Log, ligado: bool) -> None:
    """Liga ou desliga o "tocando agora" sem reinstalar nada.

    Existe porque a versão anterior só gravava essa escolha durante a
    instalação: marcar a caixa depois de instalar não fazia efeito nenhum, e
    o usuário ficava esperando por um recurso que nunca tinha sido ligado.
    """
    valor = 1 if ligado else 0
    adb.shell(
        f"[ -f {CONF} ] || printf '' > {CONF}; "
        f"cp {CONF} {CONF}.bak && "
        f"grep -v '^AGORA=' {CONF}.bak > {CONF}; "
        f"printf 'AGORA={valor}\\n' >> {CONF}; "
        f"rm -f {CONF}.bak")
    log.ok(t("ap.now.on") if ligado else t("ap.now.off"))
    # O daemon lê a configuração só na partida, então precisa recomeçar.
    parar_agora(adb, log)
    iniciar_agora(adb, log)


def instalar_cacert(adb: Adb, log: Log, local: str) -> None:
    """Põe o pacote de certificados no aparelho.

    Sem ele o curl não tem como conferir que o servidor do outro lado é mesmo
    o Last.fm, e o daemon prefere adiar o envio a mandar a chave de sessão às
    cegas. O arquivo é o que o projeto curl publica em curl.se/ca.
    """
    if not os.path.isfile(local):
        raise InstallerError(t("ap.err.cacert.here"), local)
    tam = os.path.getsize(local)
    if tam < 50_000:
        raise InstallerError(t("ap.err.cacert.small.title"),
                            t("ap.err.cacert.small.body", tam=tam))
    adb.mkdir(DIR)
    adb.push(local, CACERT, mode="644")
    log.ok(t("ap.cacert.ok", tam=f"{tam:,}"))


def desligar_envio(adb: Adb, log: Log) -> None:
    """Tira só a capacidade de enviar. A coleta continua, e a fila também."""
    adb.shell(f"rm -f {SK} {SEGREDO}")
    log.ok(t("ap.sending_off"))


def enviar_agora(adb: Adb, log: Log) -> str:
    """Força uma rodada de envio no aparelho, sem esperar os 12 minutos.

    Serve para conferir na hora que está tudo certo, em vez de instalar e
    torcer.
    """
    res = adb.shell(
        f"cd {DIR} 2>/dev/null || exit 1; "
        f"if [ ! -x {REMETENTE} ] || [ ! -x {CURL} ]; then "
        f"echo 'SEM_PROGRAMAS'; exit 1; fi; "
        f"if [ ! -s {SK} ]; then echo 'SEM_CHAVE'; exit 1; fi; "
        f"ca={CACERT_SD}; [ -s \"$ca\" ] || ca={CACERT}; "
        f"if [ ! -s \"$ca\" ]; then echo 'SEM_CACERT'; exit 1; fi; "
        f"{REMETENTE} preparar {FILA} {ENVIADOS} {SK} {SEGREDO} {APIKEY} "
        f"/tmp/.r1sc.post /tmp/.r1sc.ids; rc=$?; "
        f"if [ $rc = 3 ]; then echo 'NADA_A_ENVIAR'; exit 0; fi; "
        f"if [ $rc != 0 ]; then echo \"PREPARAR_FALHOU rc=$rc\"; exit 1; fi; "
        # O curl estático não resolve nomes neste aparelho (a thread do
        # resolvedor não sobe com musl estático), então o busybox resolve e
        # entrega o IP pronto. Ver o comentário longo em r1scrobbled.sh.
        f"ip=$(nslookup ws.audioscrobbler.com 2>/dev/null "
        f"| awk '/^Address/ {{ print $NF }}' | grep -v ':' | tail -1); "
        f"if [ -n \"$ip\" ]; then "
        f"  R=\"--resolve ws.audioscrobbler.com:443:$ip\"; else R=\"\"; fi; "
        f"{CURL} -sS --max-time 45 --cacert \"$ca\" $R "
        f"-H 'Content-Type: application/x-www-form-urlencoded' "
        f"-A 'hiby-r1-scrobbler/1.0' "
        f"--data-binary @/tmp/.r1sc.post -o /tmp/.r1sc.resp "
        f"https://ws.audioscrobbler.com/2.0/ ; rc=$?; "
        f"if [ $rc != 0 ]; then echo \"CURL_FALHOU rc=$rc\"; exit 1; fi; "
        f"{REMETENTE} confirmar /tmp/.r1sc.resp /tmp/.r1sc.ids {ENVIADOS} "
        f"&& echo OK || echo CONFIRMAR_FALHOU; "
        f"head -c 300 /tmp/.r1sc.resp; echo; "
        f"rm -f /tmp/.r1sc.post /tmp/.r1sc.ids /tmp/.r1sc.resp",
        mutating=True)
    saida = (res.output or "").strip()
    log.info(t("ap.reply", saida=saida[:300]))
    if "SEM_PROGRAMAS" in saida:
        raise InstallerError(t("ap.err.noprogs.title"), t("ap.err.noprogs.body"))
    if "SEM_CHAVE" in saida:
        raise InstallerError(t("ap.err.nosk.title"), t("ap.err.nosk.body"))
    if "SEM_CACERT" in saida:
        raise InstallerError(t("ap.err.nocacert.title"),
                            t("ap.err.nocacert2.body"))
    if "CURL_FALHOU" in saida:
        raise InstallerError(t("ap.err.curlfail.title"),
                            t("ap.err.curlfail.body", saida=saida))
    if "NADA_A_ENVIAR" in saida:
        return t("ap.nothing_pending")
    if "OK" not in saida:
        raise InstallerError(t("ap.err.unconfirmed"), saida)
    return saida


def comando_ligar(init: str = INIT) -> str:
    """O comando que insere o bloco no init.sh, ANTES do primeiro `exit`.

    Fica separado para o teste poder executar exatamente este texto contra um
    init.sh de mentira. Uma cópia do comando no teste seria pior que teste
    nenhum: ela envelhece sozinha e passa a aprovar o que o produto não faz.

    O `exit` importa porque o init.sh dos ajustes portados termina com
    `exit 0`. Um bloco colado depois disso fica no arquivo, aparece no grep, e
    nunca executa — o daemon simplesmente não subia no boot.
    """
    return (
        f"printf '%s\\n' {_aspas(BLOCO)} > {init}.novo; "
        f"[ -f {init} ] || printf '#!/bin/sh\\n' > {init}; "
        # A linha do primeiro `exit` de nível zero. Um `exit` indentado está
        # dentro de um if ou de uma função e não termina o script.
        f"n=$(grep -n '^[[:space:]]*exit' {init} | head -1 | cut -d: -f1); "
        f"if [ -n \"$n\" ]; then "
        f"  head -n $((n - 1)) {init} > {init}.tmp; "
        f"  cat {init}.novo >> {init}.tmp; "
        f"  tail -n +$n {init} >> {init}.tmp; "
        f"  echo ANTES_DO_EXIT=$n; "
        f"else "
        f"  cp {init} {init}.tmp; cat {init}.novo >> {init}.tmp; "
        f"  echo NO_FIM; "
        f"fi; "
        f"mv {init}.tmp {init} && chmod 755 {init}; "
        f"rm -f {init}.novo"
    )


def comando_desligar(init: str = INIT) -> str:
    """O comando que tira o bloco do init.sh, sem tocar em mais nada."""
    return (f"[ -f {init} ] || exit 0; "
            f"cp {init} {init}.bak && "
            f"sed -e '/{_esc_sed(MARCA_INI)}/,/{_esc_sed(MARCA_FIM)}/d' "
            f"{init}.bak > {init} && rm -f {init}.bak")


def ligar_no_boot(adb: Adb, log: Log) -> None:
    """Põe o bloco no init.sh, sem duplicar e sem mexer no resto.

    O bloco vai ANTES do primeiro `exit` do arquivo, não no fim dele. O
    init.sh dos ajustes portados termina com `exit 0`, e um bloco colado
    depois disso nunca executa — o daemon simplesmente não subia no boot, sem
    erro nenhum para denunciar. Só quando não há `exit` é que o fim do
    arquivo serve.
    """
    ja = adb.shell(f"grep -qF '{MARCA_INI}' {INIT} 2>/dev/null && echo SIM || echo NAO",
                   mutating=False)
    if "SIM" in ja.stdout:
        log.info(t("ap.boot.already"))
        return

    res = adb.shell(comando_ligar(INIT))
    onde = (res.output or "").strip()

    conferido = adb.shell(
        f"sh -n {INIT} && echo SINTAXE_OK || echo SINTAXE_RUIM; "
        f"grep -c 'r1scrobbled' {INIT}", mutating=False)
    if "SINTAXE_OK" not in conferido.stdout:
        raise InstallerError(
            t("ap.err.init.title"),
            t("ap.err.init.body", caminho=INIT, saida=conferido.output[:400]))
    if "ANTES_DO_EXIT" in onde:
        log.ok(t("ap.boot.on_line", linha=onde.split("=")[-1]))
    else:
        log.ok(t("ap.boot.on"))


def desligar_do_boot(adb: Adb, log: Log) -> None:
    """Tira só o nosso bloco do init.sh; o resto do arquivo fica intacto."""
    # sed com endereços: apaga do marcador de início ao de fim, inclusive.
    adb.shell(comando_desligar(INIT))
    log.ok(t("ap.boot.off"))


def iniciar_agora(adb: Adb, log: Log) -> None:
    """Sobe o daemon e CONFERE que ele ficou de pé.

    Dizer "iniciado" sem olhar já escondeu um problema real: o daemon
    trapeava SIGHUP, e o `adb shell` manda HUP ao sair, então ele morria
    segundos depois de subir enquanto a tela dizia que estava tudo bem.
    """
    adb.shell(
        f"[ -x {DAEMON} ] || exit 1; "
        # setsid tira o daemon do grupo de processos do adb shell; o nohup é
        # cinto e suspensório, para o caso de um busybox sem setsid.
        f"if command -v setsid >/dev/null 2>&1; then "
        f"  setsid {DAEMON} </dev/null >/dev/null 2>&1 & "
        f"else "
        f"  nohup {DAEMON} </dev/null >/dev/null 2>&1 & "
        f"fi; "
        f"sleep 1")
    # Um instante para o daemon escrever a trava, e outro para um HUP tardio
    # ter chance de matá-lo — é justamente esse caso que interessa detectar.
    time.sleep(2.5)
    res = adb.shell(
        f"p=$(cat {TRAVA} 2>/dev/null); "
        f"if [ -n \"$p\" ] && [ -d /proc/$p ]; then echo VIVO; "
        f"else echo MORTO; fi", mutating=False)
    if "VIVO" not in res.stdout:
        detalhe = adb.shell(f"cat /tmp/.r1sc.log 2>/dev/null | tail -20",
                            mutating=False)
        raise InstallerError(
            t("ap.err.died.title"),
            t("ap.err.died.body",
              registro=detalhe.stdout.strip() or t("ap.log.empty"),
              daemon=DAEMON))
    log.ok(t("ap.started"))


def parar_agora(adb: Adb, log: Log) -> None:
    adb.shell(f"p=$(cat {TRAVA} 2>/dev/null); "
              f"[ -n \"$p\" ] && kill -TERM $p 2>/dev/null; "
              f"rm -f {TRAVA} {TRAVA_ANTIGA}")
    log.ok(t("ap.stopped"))


def desinstalar(adb: Adb, log: Log, *, apagar_fila: bool = False) -> None:
    """Remove o coletor. A fila só sai se for pedido explicitamente.

    O padrão é preservar a fila: ela é a única coisa aqui que representa algo
    que você fez e não dá para refazer.
    """
    parar_agora(adb, log)
    desligar_do_boot(adb, log)
    if apagar_fila:
        adb.shell(f"rm -rf {DIR}")
        log.warn(t("ap.removed.all"))
    else:
        # A fila fica; o resto sai. O `medindo` é a medição de uma faixa que
        # estava tocando na hora, e sem o daemon ninguém a fecharia — deixá-lo
        # faria a próxima instalação recuperar uma escuta de meses atrás. As
        # marcas .visto* são só mtimes de controle e não valem nada sozinhas.
        adb.shell(f"rm -f {BIN} {DAEMON} {CONF} {REMETENTE} {CURL} {TRAVA_ANTIGA} "
                  f"{SK} {SEGREDO} {APIKEY} {MEDINDO} "
                  f"{DIR}/.visto {DIR}/.visto2 {DIR}/.visto3")
        log.ok(t("ap.removed.kept", fila=FILA))


def puxar_fila(adb: Adb, log: Log, destino_local: str) -> str:
    """Traz a fila para o PC. Não apaga nada do aparelho."""
    os.makedirs(os.path.dirname(destino_local) or ".", exist_ok=True)
    existe = adb.shell(f"[ -f {FILA} ] && echo SIM || echo NAO",
                       mutating=False)
    if "SIM" not in existe.stdout:
        raise InstallerError(t("ap.err.noqueue.title"),
                            t("ap.err.noqueue.body", fila=FILA))
    res = adb.raw(["pull", FILA, destino_local], mutating=False, check=False)
    if not res.ok or not os.path.isfile(destino_local):
        raise InstallerError(t("ap.err.pull"), res.output[:600])
    log.ok(t("ap.queue.pulled", bytes=os.path.getsize(destino_local)))
    return destino_local


def ler_enviados(adb: Adb) -> set[int]:
    """Os rowid que já foram aceitos pelo Last.fm, guardados no aparelho.

    Ficam no aparelho, e não no PC, porque é a fila que eles acompanham: se o
    instalador for usado de outro computador, o que já foi enviado continua
    sabido.
    """
    res = adb.shell(f"cat {ENVIADOS} 2>/dev/null", mutating=False)
    out: set[int] = set()
    for tok in res.stdout.split():
        try:
            out.add(int(tok))
        except ValueError:
            pass
    return out


def marcar_enviados(adb: Adb, log: Log, ids: set[int]) -> None:
    if not ids:
        return
    texto = "\n".join(str(i) for i in sorted(ids)) + "\n"
    adb.shell(f"printf '%s' {_aspas(texto)} >> {ENVIADOS}")
    log.ok(t("ap.marked", n=len(ids)))


def limpar_fila(adb: Adb, log: Log, enviados: set[int]) -> None:
    """Enxuga a fila, tirando o que já foi aceito.

    Só é chamado quando você pede. A fila é pequena (umas 200 bytes por
    faixa), então deixá-la crescer não incomoda ninguém — mas quem quiser
    limpar, pode.
    """
    if not enviados:
        return
    lista = ",".join(str(i) for i in sorted(enviados))
    # Reescreve mantendo os marcadores e as faixas que ainda não foram.
    #
    # O t1 sai junto com o p1 do mesmo rowid. Ele traz o tempo medido daquela
    # faixa e nada mais; sem a faixa não quer dizer coisa alguma, e deixá-lo
    # para trás faria a fila continuar crescendo justamente na limpeza. Os
    # dois têm o rowid no mesmo campo, então é a mesma pergunta.
    script = (
        f"cd {DIR} || exit 1; "
        f"cp fila.tsv fila.tsv.bak || exit 1; "
        f"awk -F'\\t' -v ids='{lista}' 'BEGIN{{n=split(ids,a,\",\"); "
        f"for(i=1;i<=n;i++) m[a[i]]=1}} "
        f"($1!=\"p1\" && $1!=\"t1\") || !($2 in m)' fila.tsv.bak "
        f"> fila.tsv.novo && "
        f"mv fila.tsv.novo fila.tsv && rm -f fila.tsv.bak"
    )
    adb.shell(script)
    log.ok(t("ap.trimmed"))


def _aspas(texto: str) -> str:
    """Passa um texto para o shell do aparelho sem que ele o interprete."""
    return "'" + texto.replace("'", "'\\''") + "'"


def _esc_sed(texto: str) -> str:
    for c in "\\/.*[]^$":
        texto = texto.replace(c, "\\" + c)
    return texto
