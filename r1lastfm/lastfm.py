"""Cliente do Last.fm — só a parte que roda no PC.

O R1 nunca fala com o Last.fm. Ele só anota o que tocou; quem autentica e
envia é este módulo. Isso é de propósito: a autenticação envolve um segredo
compartilhado que não deveria morar num aparelho que passa de mão em mão, e o
envio em lote é o que permite deixar o WiFi do R1 desligado o tempo todo.

Fluxo de autenticação (o "desktop application" da documentação do Last.fm):

    auth.getToken            -> token de uso único
    abre o navegador em      https://www.last.fm/api/auth/?api_key=…&token=…
    o usuário aprova lá
    auth.getSession          -> chave de sessão, que não expira

A chave de sessão é o único segredo que fica guardado, e ela não dá acesso à
senha. Existe também o auth.getMobileSession, que troca usuário+senha direto
por uma sessão; está implementado aqui porque é útil quando não há navegador,
mas ele *vê a sua senha* e por isso não é o caminho padrão.

Assinatura: concatena os parâmetros ordenados por nome como chave+valor, sem
separadores, acrescenta o segredo compartilhado e tira o MD5 do resultado em
UTF-8. O parâmetro `format` fica de fora da assinatura.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .applog import Log
from .idioma import t
from .runner import InstallerError

API_ROOT = "https://ws.audioscrobbler.com/2.0/"
AUTH_PAGE = "https://www.last.fm/api/auth/"
USER_AGENT = "hiby-r1-scrobbler/1.0"

# Um lote de track.scrobble aceita no máximo 50 faixas.
BATCH = 50

# O que conta como uma execução.
#
# O Last.fm pede metade da faixa, ou 4 minutos, o que vier antes. Aqui a régua
# é mais alta de propósito: com metade, uma faixa largada no meio sobe para o
# perfil como se tivesse sido ouvida, e foi essa a reclamação — "pulei e
# contabilizou como se tivesse escutado toda".
#
# Não são 100% porque trocar de faixa um ou dois segundos antes do fim é o uso
# normal do aparelho; em 100% quase nada subiria. 90% é "ouviu até o fim" na
# prática.
#
# Este número tem de ser o MESMO do MIN_PCT no r1send.c: são duas
# implementações da mesma regra, e o teste diferencial compara as duas.
MIN_TRACK_SECONDS = 30
FULL_PLAY_SECONDS = 240
MIN_PLAY_PERCENT = 90
# Tetos da margem que a incerteza da medição concede. Iguais ao MARGEM_MAX e
# ao MARGEM_PCT do r1send.c, pelo mesmo motivo dos outros números daqui: são
# duas implementações da mesma regra, e o teste diferencial compara as duas.
MEASURE_SLACK_MAX = 30
MEASURE_SLACK_PCT = 10


class LastfmError(InstallerError):
    """Erro devolvido pela API, já traduzido."""

    def __init__(self, code: int, message: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"Last.fm: {message}", detail)


# Os códigos de erro que a API devolve. O texto de cada um mora no catálogo,
# sob "lfm.code.<n>": ele aparece na tela, e "Invalid session key - Please
# re-authenticate" no meio de uma janela traduzida não ajuda ninguém.
ERRORS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 16, 17, 26, 29)


def erro_da_api(codigo: int) -> str:
    """O que esse código quer dizer, no idioma de agora."""
    return t(f"lfm.code.{codigo}") if codigo in ERRORS else ""

# Erros que valem a pena tentar de novo sozinho.
TRANSIENT = {8, 11, 16, 29}


@dataclass
class Play:
    """Uma execução, do jeito que o Last.fm quer receber."""

    artist: str
    track: str
    timestamp: int
    album: str = ""
    album_artist: str = ""
    duration: int = 0
    # Só para o nosso lado: quanto tempo o aparelho realmente ficou nela.
    # -1 quer dizer "não dá para saber", que é diferente de 0 ("não ouviu
    # nada"). Confundir os dois faria toda faixa pulada passar como válida.
    listened: int = -1
    source: str = ""
    # A linha do historico de onde ela veio. E o que permite dizer ao
    # aparelho "esta aqui eu nao quero" sem depender de artista e titulo,
    # que se repetem.
    rowid: int = 0
    # A régua com que `listened` foi medido, em segundos; 0 quando o número
    # não veio de medição nenhuma. Ver a margem em scrobblable().
    regua: int = 0
    # A faixa chegou ao fim sozinha (o audio parou antes de a seguinte entrar),
    # em vez de ter sido pulada. Vale mais do que a razao medido/duracao, que
    # erra com silencio no fim do arquivo ou com duracao estimada a mais.
    ate_o_fim: bool = False

    def scrobblable(self) -> tuple[bool, str]:
        """As regras do Last.fm, ditas em voz alta.

        Devolve (pode, motivo). O motivo é para a tela mostrar por que uma
        faixa foi deixada de fora, em vez de ela simplesmente sumir.
        """
        if not self.artist or not self.track:
            return False, t("play.no_artist")
        if self.timestamp <= 0:
            return False, t("play.no_time")
        if self.duration and self.duration < MIN_TRACK_SECONDS:
            return False, t("play.too_short", segundos=self.duration,
                            minimo=MIN_TRACK_SECONDS)
        # Tocou ate o fim sozinha: conta, e a razao medido/duracao nao
        # opina. Ela erra justamente aqui — a duracao vem de tamanho x 8 /
        # taxa e sobra num arquivo com capa e tags, e silencio no fim encurta
        # o medido. Ainda assim e preciso ter ouvido a maior parte: uma faixa
        # aberta e abandonada tambem termina com o audio parado.
        # Tocou ate o fim sozinha: 80% em vez dos 90%.
        #
        # O sinal de "acabou sozinha" e bom mas nao e infalivel: entre uma
        # faixa e a proxima ha um instante de silencio, e num pulo o daemon
        # pode peg -lo justamente na volta em que olha. Dez pontos cobrem a
        # duracao superestimada e o silencio no fim; nao cobrem um pulo. Com
        # metade — como estava — uma faixa pulada passada a metade subia.
        if (self.ate_o_fim and self.duration
                and self.listened * 5 >= self.duration * 4):
            return True, ""
        if self.duration and self.listened >= 0:
            # Arredondando para CIMA, como o r1send.c faz com o `+ 99`. Com a
            # divisão inteira de antes, uma faixa de 125 s precisava de 62 s e
            # 62 passava — 49,6% da faixa contava como ouvida.
            preciso = min(-(-self.duration * MIN_PLAY_PERCENT // 100),
                          FULL_PLAY_SECONDS)
            # A margem é a incerteza da própria medição, não folga.
            #
            # O daemon olha o pcm de tantos em tantos segundos; cada vez que o
            # áudio para ou volta, a hora disso se perde dentro de um
            # intervalo, e o pedaço tocado ali não entrou na soma. Cobrar os
            # 90% de um número que veio sabidamente curto reprovaria faixa
            # ouvida até o fim — era o que fazia quem pausa perder a música.
            #
            # O teto proporcional garante que, por pior que a medição tenha
            # sido, nada conta com menos de 80% da faixa tocado.
            margem = min(max(0, self.regua), MEASURE_SLACK_MAX,
                         self.duration * MEASURE_SLACK_PCT // 100)
            if self.listened + margem < preciso:
                return False, t("play.too_little", ouviu=self.listened,
                                total=self.duration,
                                precisa=f"{preciso:.0f}")
        return True, ""

    def fields(self, i: int) -> dict:
        """Os parâmetros indexados de um item dentro do lote."""
        out = {
            f"artist[{i}]": self.artist,
            f"track[{i}]": self.track,
            f"timestamp[{i}]": str(self.timestamp),
        }
        if self.album:
            out[f"album[{i}]"] = self.album
        if self.album_artist and self.album_artist != self.artist:
            out[f"albumArtist[{i}]"] = self.album_artist
        if self.duration >= MIN_TRACK_SECONDS:
            out[f"duration[{i}]"] = str(self.duration)
        return out


@dataclass
class ScrobbleResult:
    accepted: int = 0
    ignored: list[tuple[Play, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.accepted + len(self.ignored)


# Motivos de recusa que o próprio Last.fm devolve por faixa. O texto está no
# catálogo, sob "lfm.ignore.<n>".
IGNORE_CODES = ("1", "2", "3", "4", "5")


def motivo_da_recusa(codigo: str) -> str:
    return t(f"lfm.ignore.{codigo}") if codigo in IGNORE_CODES else ""


def _json_ou_nada(corpo: bytes):
    """O corpo como objeto, ou None se não for JSON legível."""
    try:
        return json.loads(corpo.decode("utf-8", "replace"))
    except ValueError:
        return None


def signature(params: dict, secret: str) -> str:
    """api_sig: pares ordenados, colados sem separador, mais o segredo."""
    corpo = "".join(f"{k}{params[k]}" for k in sorted(params)
                    if k not in ("format", "callback"))
    return hashlib.md5((corpo + secret).encode("utf-8")).hexdigest()


class Client:
    def __init__(self, api_key: str, secret: str, log: Log | None = None,
                 session_key: str = "", timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.secret = secret
        self.session_key = session_key
        self.log = log
        self.timeout = timeout
        self.username = ""

    # -- transporte ---------------------------------------------------------

    def _say(self, level: str, msg: str) -> None:
        if self.log:
            getattr(self.log, level, self.log.info)(msg)

    def call(self, method: str, params: dict | None = None, *,
             sign: bool = False, post: bool = False,
             tries: int = 3) -> dict:
        p = dict(params or {})
        p["method"] = method
        p["api_key"] = self.api_key
        if sign:
            if self.session_key and "sk" not in p and "token" not in p:
                p["sk"] = self.session_key
            p["api_sig"] = signature(p, self.secret)
        p["format"] = "json"
        dados = urllib.parse.urlencode(p, encoding="utf-8").encode("ascii")

        ultimo: LastfmError | None = None
        for tentativa in range(1, tries + 1):
            try:
                return self._once(method, dados, post)
            except LastfmError as exc:
                ultimo = exc
                if exc.code not in TRANSIENT or tentativa == tries:
                    raise
                espera = 2 ** tentativa
                self._say("warn", t("lfm.retry", metodo=method,
                                    mensagem=exc.message, segundos=espera,
                                    tentativa=tentativa, total=tries))
                time.sleep(espera)
            except urllib.error.URLError as exc:
                if tentativa == tries:
                    raise InstallerError(
                        t("lfm.err.net.title"),
                        t("lfm.err.net.body", metodo=method,
                          motivo=exc.reason)) from exc
                time.sleep(2 ** tentativa)
        assert ultimo is not None
        raise ultimo

    def _once(self, method: str, dados: bytes, post: bool) -> dict:
        if post:
            req = urllib.request.Request(
                API_ROOT, data=dados,
                headers={"User-Agent": USER_AGENT,
                         "Content-Type": "application/x-www-form-urlencoded"})
        else:
            req = urllib.request.Request(
                API_ROOT + "?" + dados.decode("ascii"),
                headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                corpo = resp.read()
        except urllib.error.HTTPError as exc:
            # O código e o corpo são copiados aqui porque o nome `exc` some no
            # fim deste bloco, e o tratamento continua depois dele.
            status, corpo, causa = exc.code, exc.read(), exc
            # A API devolve o erro no corpo mesmo com status 4xx; se der para
            # ler, a mensagem dela é melhor do que "HTTP 403".
            obj = _json_ou_nada(corpo)
            if obj is not None:
                self._raise(obj, method)
            # Chegar aqui é um 4xx que não trouxe erro nenhum no corpo. Não
            # dá para reerguer o HTTPError: ele vazaria como traceback.
            raise InstallerError(
                t("lfm.err.http", status=status, metodo=method),
                corpo[:400].decode("utf-8", "replace")
                or t("lfm.err.empty")) from causa
        obj = _json_ou_nada(corpo)
        if obj is None:
            raise InstallerError(
                t("lfm.err.notjson", metodo=method),
                corpo[:400].decode("utf-8", "replace"))
        self._raise(obj, method)
        return obj

    def _raise(self, obj: dict, method: str) -> None:
        if not isinstance(obj, dict) or "error" not in obj:
            return
        code = int(obj.get("error", 0))
        texto = (erro_da_api(code) or obj.get("message")
                 or t("lfm.code.unknown"))
        raise LastfmError(code, texto,
                          t("lfm.detail", metodo=method, codigo=code,
                            mensagem=obj.get("message", "")))

    # -- autenticação -------------------------------------------------------

    def request_token(self) -> str:
        return str(self.call("auth.getToken", sign=True)["token"])

    def auth_url(self, token: str) -> str:
        return (AUTH_PAGE + "?" +
                urllib.parse.urlencode({"api_key": self.api_key,
                                        "token": token}))

    def finish_auth(self, token: str) -> str:
        """Troca um token já aprovado por uma chave de sessão."""
        obj = self.call("auth.getSession", {"token": token}, sign=True)
        ses = obj.get("session") or {}
        self.session_key = str(ses.get("key", ""))
        self.username = str(ses.get("name", ""))
        if not self.session_key:
            raise InstallerError(t("lfm.err.nosk"), json.dumps(obj)[:400])
        return self.session_key

    def mobile_session(self, user: str, password: str) -> str:
        """Caminho alternativo, sem navegador.

        Este é o único ponto do programa que toca na sua senha do Last.fm. Ela
        vai direto para a API por POST e não é guardada em lugar nenhum, mas
        ainda assim o caminho do navegador é preferível justamente por não
        precisar dela.
        """
        obj = self.call("auth.getMobileSession",
                        {"username": user, "password": password},
                        sign=True, post=True)
        ses = obj.get("session") or {}
        self.session_key = str(ses.get("key", ""))
        self.username = str(ses.get("name", ""))
        if not self.session_key:
            raise InstallerError(t("lfm.err.nosk"), json.dumps(obj)[:400])
        return self.session_key

    def check_session(self) -> str:
        """Confirma que a chave guardada ainda vale, e devolve o usuário."""
        obj = self.call("user.getInfo", sign=True)
        self.username = str((obj.get("user") or {}).get("name", ""))
        return self.username

    # -- envio --------------------------------------------------------------

    def scrobble(self, plays: Sequence[Play]) -> ScrobbleResult:
        """Envia um lote de até 50. Devolve o que foi aceito e o que não."""
        if not plays:
            return ScrobbleResult()
        if len(plays) > BATCH:
            raise ValueError(f"lote de {len(plays)}; o máximo é {BATCH}")
        params: dict[str, str] = {}
        for i, play in enumerate(plays):
            params.update(play.fields(i))
        obj = self.call("track.scrobble", params, sign=True, post=True)
        return self._read_result(obj, plays)

    def _read_result(self, obj: dict, plays: Sequence[Play]) -> ScrobbleResult:
        bloco = obj.get("scrobbles") or {}
        # A API devolve um objeto quando é uma faixa só e uma lista quando são
        # várias — é a pegadinha clássica desta API.
        itens = bloco.get("scrobble") or []
        if isinstance(itens, dict):
            itens = [itens]
        res = ScrobbleResult()
        for play, item in zip(plays, itens):
            ig = (item or {}).get("ignoredMessage") or {}
            codigo = str(ig.get("code", "0"))
            if codigo == "0":
                res.accepted += 1
            else:
                motivo = (motivo_da_recusa(codigo) or ig.get("#text")
                          or t("lfm.ignore.other", codigo=codigo))
                res.ignored.append((play, motivo))
        # Se a resposta veio mais curta do que o lote, o que sobrou não foi
        # confirmado. Melhor contar como não enviado do que inventar sucesso.
        faltando = len(plays) - len(itens)
        for play in plays[len(itens):]:
            res.ignored.append((play, t("lfm.unconfirmed")))
        if faltando:
            self._say("warn", t("lfm.partial", confirmadas=len(itens),
                                total=len(plays)))
        return res

    def now_playing(self, play: Play) -> None:
        params = {"artist": play.artist, "track": play.track}
        if play.album:
            params["album"] = play.album
        if play.duration >= MIN_TRACK_SECONDS:
            params["duration"] = str(play.duration)
        self.call("track.updateNowPlaying", params, sign=True, post=True)


def send_all(client: Client, plays: Iterable[Play], *,
             progress=None) -> tuple[ScrobbleResult, list[Play]]:
    """Envia tudo em lotes, e diz exatamente onde parou se algo falhar.

    Devolve (resultado, ainda_na_fila). O segundo item é o que não chegou a
    ser confirmado — é ele que deve continuar guardado, para o envio poder ser
    repetido sem duplicar o que já entrou.
    """
    lista = list(plays)
    total = ScrobbleResult()
    enviados = 0
    for inicio in range(0, len(lista), BATCH):
        lote = lista[inicio:inicio + BATCH]
        try:
            r = client.scrobble(lote)
        except InstallerError:
            # O que já foi confirmado sai da fila; o resto fica.
            return total, lista[enviados:]
        total.accepted += r.accepted
        total.ignored.extend(r.ignored)
        enviados += len(lote)
        if progress:
            progress(enviados, len(lista))
    return total, []
