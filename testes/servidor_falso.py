"""Um Last.fm e um Tidal de mentira, falando HTTPS de verdade.

Existe para uma coisa só: testar o `r1net` — o ajudante de rede residente —
pelo caminho inteiro, com TLS, HTTP e conexão guardada, sem depender da
internet nem de credenciais reais.

Sem ele, o cenário do daemon com o ajudante ia bater no servidor de verdade,
levar 401 por causa do token de mentira, e medir outra coisa. Foi assim que a
primeira execução do teste duplo apontou "o ajudante quebrou tudo" quando na
verdade o que estava errado era a bancada.

O certificado é gerado na hora, com os dois nomes dentro, e é ele que o
ajudante recebe como pacote de confiança. Ou seja: a validação do certificado
também está sendo exercitada, e não desligada.

Uso:
    python servidor_falso.py <porta> <arquivo-cert-para-o-cliente>

Escreve "PRONTO" na saída quando estiver aceitando conexões.
"""

import http.server
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading

HOSTS = ["ws.audioscrobbler.com", "api.tidal.com"]


def gerar_certificado(dir_saida):
    """Um certificado só nosso, com os dois nomes que o teste usa."""
    chave = os.path.join(dir_saida, "chave.pem")
    cert = os.path.join(dir_saida, "cert.pem")
    conf = os.path.join(dir_saida, "openssl.cnf")
    with open(conf, "w") as f:
        f.write(
            "[req]\ndistinguished_name=dn\nx509_extensions=v3\nprompt=no\n"
            "[dn]\nCN=ws.audioscrobbler.com\n"
            "[v3]\nsubjectAltName=" +
            ",".join(f"DNS:{h}" for h in HOSTS) + "\n"
            "basicConstraints=CA:TRUE\n"
        )
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", chave, "-out", cert, "-days", "2", "-config", conf],
        check=True, capture_output=True,
    )
    return chave, cert


class Falso(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"      # keep-alive, que e o que se quer testar

    def log_message(self, *_):
        pass

    def _responder(self, corpo):
        # Compacto, sem espaco depois dos dois-pontos — como as APIs de
        # verdade respondem.
        #
        # Isto nao e capricho: o daemon extrai o pais com
        # `tr ',' '\n' | grep countryCode | tr -d '"' | cut -d: -f2`, e um
        # espaco extra faz sair " BR}" em vez de "BR", que nao passa na
        # validacao de duas letras. Com o json.dumps padrao, o teste acusava o
        # ajudante de nao funcionar quando quem estava fora do padrao era o
        # servidor de mentira.
        dados = json.dumps(corpo, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if "/v1/sessions" in self.path:
            # Com campos DEPOIS do countryCode, como a resposta real. Sem
            # isso o pais sai como "BR}" — com a chave colada — e o teste
            # mediria uma coisa que nao acontece com a API de verdade.
            self._responder({"sessionId": "x", "userId": 1,
                             "countryCode": "BR", "channelId": 1})
        elif "/v1/tracks/" in self.path:
            self._responder({"title": "Faixa", "duration": 40,
                             "artist": {"name": "Artista"},
                             "album": {"title": "Album"}})
        else:
            self._responder({"ok": True})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        # A resposta do track.updateNowPlaying, no formato que o daemon espera.
        self._responder({"nowplaying": {
            "artist": {"corrected": "0", "#text": "Artista"},
            "track": {"corrected": "0", "#text": "Faixa"},
            "ignoredMessage": {"code": "0", "#text": ""},
        }})


def main():
    porta = int(sys.argv[1])
    destino_cert = sys.argv[2]

    tmp = tempfile.mkdtemp(prefix="r1servidor")
    chave, cert = gerar_certificado(tmp)
    # O cliente precisa confiar neste certificado: e o pacote que o r1net
    # recebe. Copiado para onde o teste pediu.
    with open(cert, "rb") as o, open(destino_cert, "wb") as d:
        d.write(o.read())

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, chave)

    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", porta), Falso)
    servidor.socket = ctx.wrap_socket(servidor.socket, server_side=True)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print("PRONTO", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
