/* r1net — o ajudante de rede residente do scrobbler.
 *
 * POR QUE ELE EXISTE
 *
 * O R1 travava quando o scrobbler ia à rede com o Tidal tocando. Foram três
 * tentativas de conserto olhando para o lugar errado, até a medição no
 * aparelho dizer o seguinte:
 *
 *   • com o Tidal tocando sobram ~1,5 MB livres e o maior bloco contíguo de
 *     memória é de meio mega — e o kernel do R1 foi compilado SEM compactação,
 *     então isso não se recupera enquanto o áudio não parar;
 *   • parado, são 22 MB livres e blocos de 16 MB;
 *   • um curl no meio da faixa custa 896 KB de pico e, sozinho, não incomodou;
 *   • e mesmo assim o "tocando agora" derrubou o player no instante em que saiu.
 *
 * O que todas as tentativas tinham em comum não era o tamanho do curl: era
 * CRIAR ALGO no meio da reprodução. Um fork, um exec, mapear um binário de
 * 1,6 MB, abrir um socket, negociar TLS — tudo isso no pior momento possível.
 *
 * Este programa inverte a conta. Ele sobe no boot, quando há 22 MB livres e
 * blocos de 16 MB, e faz ali todas as alocações caras: lê e valida o pacote de
 * certificados, semeia o gerador aleatório, e monta os contextos de TLS com
 * seus buffers. Depois disso ele fica parado num fifo.
 *
 * Na hora de anunciar uma faixa, o daemon só escreve uma linha:
 *
 *     printf '...\n' > "$FIFO"      # printf e redirecionamento são internos
 *                                   # do shell: zero processos criados
 *
 * E a conexão TLS com o Last.fm fica ABERTA entre um pedido e outro. Então no
 * instante crítico não há fork, não há exec, não há mmap, não há socket novo e
 * não há handshake. Há um write num descritor que já existe.
 *
 * Isso não é prova de que resolve — a mesma medição que derrubou minhas
 * teorias anteriores mostrou o aparelho reiniciando uma vez com o daemon
 * PARADO e nenhuma requisição feita, o que quer dizer que existe pelo menos
 * uma causa que não é o scrobbler. Mas é o único desenho que ataca os dois
 * mecanismos candidatos ao mesmo tempo, e não sobra mais nada para tirar do
 * caminho.
 *
 * O PROTOCOLO
 *
 * Uma linha por pedido, campos separados por TAB:
 *
 *   id  metodo  host  ip  caminho  corpo  saida  cabecalhos
 *
 *   id          qualquer texto sem TAB; volta igual na resposta
 *   metodo      GET ou POST
 *   host        para o SNI e para a validação do certificado
 *   ip          endereço a discar, ou "-" para resolver pelo nome
 *   caminho     "/2.0/" e afins
 *   corpo       arquivo com o corpo do POST, ou "-"
 *   saida       arquivo onde gravar a resposta, ou "-" para descartar
 *   cabecalhos  arquivo com cabeçalhos extras (um por linha), ou "-"
 *
 * A resposta sai no fifo de respostas:
 *
 *   id  codigo  bytes        (codigo < 0 é falha nossa, não do servidor)
 *
 * NENHUM SEGREDO ATRAVESSA O FIFO. O corpo assinado do Last.fm e o cabeçalho
 * com o token do Tidal viajam como CAMINHO DE ARQUIVO, nunca como conteúdo —
 * o fifo fica em /tmp e o que passa por ele é legível por qualquer processo.
 * Pela mesma razão, nada do que este programa lê desses arquivos é registrado.
 */

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "mbedtls/ctr_drbg.h"
#include "mbedtls/debug.h"
#include "mbedtls/entropy.h"
#include "mbedtls/error.h"
#include "mbedtls/net_sockets.h"
#include "mbedtls/ssl.h"
#include "mbedtls/x509_crt.h"

/* O número do mbedTLS por extenso. Um "tls -27648" no registro não ajuda
 * ninguém a consertar nada. */
static const char *explicar(int rc)
{
    static char buf[128];
    mbedtls_strerror(rc, buf, sizeof(buf));
    if (!buf[0]) snprintf(buf, sizeof(buf), "erro %d", rc);
    return buf;
}

#define MAX_LINHA   2048
#define MAX_CORPO   8192
#define MAX_CAB     1024
#define MAX_HOSTS   4
#define ESPERA_S    "20"

static FILE *registro;

static void diz(const char *fmt, ...)
{
    va_list ap;
    time_t agora;
    char quando[32];

    if (!registro) return;
    agora = time(0);
    strftime(quando, sizeof(quando), "%H:%M:%S", localtime(&agora));
    fprintf(registro, "[%s r1net] ", quando);
    va_start(ap, fmt);
    vfprintf(registro, fmt, ap);
    va_end(ap);
    fputc('\n', registro);
    fflush(registro);
}

static void depurar(void *ctx, int nivel, const char *arquivo, int linha,
                    const char *msg)
{
    (void)ctx; (void)nivel;
    if (!registro) return;
    fprintf(registro, "  [tls] %s:%d %s", arquivo, linha, msg);
    fflush(registro);
}

/* Um host com sua conexão. O contexto de TLS é montado UMA vez, na partida —
 * é ele que carrega os buffers de 16 KB e 4 KB. Entre uma conexão e outra
 * usa-se mbedtls_ssl_session_reset, que reaproveita esses buffers em vez de
 * devolvê-los e pedir de novo. */
typedef struct {
    char nome[128];
    int  ligado;
    mbedtls_net_context   net;
    mbedtls_ssl_context   ssl;
} Host;

static Host hosts[MAX_HOSTS];
static int  n_hosts;

/* Os códigos são os da própria norma do TLS (RFC 8446, secção 4.2.3), e são
 * os mesmos no 1.2 e no 1.3. Postos aqui em número, e não pelos nomes do
 * mbedTLS, porque os nomes mudaram de versão para versão e o valor não. */
static const uint16_t assinaturas[] = {
    0x0403,   /* ecdsa_secp256r1_sha256 */
    0x0503,   /* ecdsa_secp384r1_sha384 */
    0x0804,   /* rsa_pss_rsae_sha256    */
    0x0805,   /* rsa_pss_rsae_sha384    */
    0x0806,   /* rsa_pss_rsae_sha512    */
    0x0401,   /* rsa_pkcs1_sha256       */
    0x0501,   /* rsa_pkcs1_sha384       */
    0x0601,   /* rsa_pkcs1_sha512       */
    0x0000    /* fim da lista           */
};

static mbedtls_ssl_config    conf;
static mbedtls_entropy_context entropia;
static mbedtls_ctr_drbg_context drbg;
static mbedtls_x509_crt      cadeia;

static void desligar(Host *h)
{
    if (!h->ligado) return;
    mbedtls_ssl_close_notify(&h->ssl);
    mbedtls_net_free(&h->net);
    h->ligado = 0;
}

static Host *achar_host(const char *nome)
{
    int i;
    for (i = 0; i < n_hosts; i++)
        if (strcmp(hosts[i].nome, nome) == 0) return &hosts[i];
    if (n_hosts >= MAX_HOSTS) {
        /* Todos os lugares ocupados: o mais antigo sai. Na prática são dois
         * hosts (o Last.fm e o Tidal) e isto nunca acontece. */
        desligar(&hosts[0]);
        mbedtls_ssl_free(&hosts[0].ssl);
        memmove(&hosts[0], &hosts[1], sizeof(Host) * (MAX_HOSTS - 1));
        n_hosts--;
    }
    {
        Host *h = &hosts[n_hosts];
        memset(h, 0, sizeof(*h));
        snprintf(h->nome, sizeof(h->nome), "%s", nome);
        mbedtls_net_init(&h->net);
        mbedtls_ssl_init(&h->ssl);
        /* AQUI mora o custo que este programa existe para pagar adiantado:
         * o ssl_setup aloca os buffers de entrada e saída. Feito na partida,
         * com o aparelho vazio, e nunca mais. */
        if (mbedtls_ssl_setup(&h->ssl, &conf) != 0) return 0;
        n_hosts++;
        return h;
    }
}

/* Garante conexão viva com o host. Devolve 0 se está pronta. */
static int ligar(Host *h, const char *ip, char *erro, size_t tam_erro)
{
    int rc;
    const char *alvo = (ip && ip[0] && strcmp(ip, "-") != 0) ? ip : h->nome;

    if (h->ligado) return 0;

    mbedtls_net_init(&h->net);
    rc = mbedtls_net_connect(&h->net, alvo, "443", MBEDTLS_NET_PROTO_TCP);
    if (rc != 0) {
        snprintf(erro, tam_erro, "conexao %d", rc);
        return -1;
    }
    /* O nome vai para o SNI e para a validação do certificado mesmo quando o
     * endereço veio pronto — é o que o `--resolve` do curl faz, e é o que
     * evita uma resolução de nome no instante do pedido. */
    if (mbedtls_ssl_set_hostname(&h->ssl, h->nome) != 0) {
        snprintf(erro, tam_erro, "sni");
        mbedtls_net_free(&h->net);
        return -1;
    }
    mbedtls_ssl_session_reset(&h->ssl);
    mbedtls_ssl_set_bio(&h->ssl, &h->net,
                        mbedtls_net_send, mbedtls_net_recv, 0);
    while ((rc = mbedtls_ssl_handshake(&h->ssl)) != 0) {
        if (rc != MBEDTLS_ERR_SSL_WANT_READ && rc != MBEDTLS_ERR_SSL_WANT_WRITE) {
            uint32_t mot = mbedtls_ssl_get_verify_result(&h->ssl);
            if (mot != 0 && mot != 0xFFFFFFFFu)
                snprintf(erro, tam_erro, "certificado recusado (0x%lx)",
                         (unsigned long)mot);
            else
                snprintf(erro, tam_erro, "tls: %s", explicar(rc));
            mbedtls_net_free(&h->net);
            return -1;
        }
    }
    h->ligado = 1;
    return 0;
}

static int escrever_tudo(Host *h, const char *buf, size_t n)
{
    size_t feito = 0;
    while (feito < n) {
        int rc = mbedtls_ssl_write(&h->ssl, (const unsigned char *)buf + feito,
                                   n - feito);
        if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE)
            continue;
        if (rc <= 0) return -1;
        feito += (size_t)rc;
    }
    return 0;
}

/* Lê o arquivo inteiro. Devolve o tamanho, ou -1. Nada do conteúdo é
 * registrado: por aqui passam o corpo assinado do Last.fm e o token do
 * Tidal. */
static long ler_arquivo(const char *caminho, char *buf, size_t tam)
{
    FILE *f;
    size_t n;
    if (!caminho || !caminho[0] || strcmp(caminho, "-") == 0) return 0;
    f = fopen(caminho, "rb");
    if (!f) return -1;
    n = fread(buf, 1, tam - 1, f);
    fclose(f);
    buf[n] = 0;
    return (long)n;
}

/* Um pedido HTTP sobre a conexão que já está de pé. Devolve o código HTTP, ou
 * um negativo se nem chegou a haver resposta. */
static int pedir(Host *h, const char *metodo, const char *caminho,
                 const char *corpo, size_t n_corpo, const char *cabecalhos,
                 const char *saida, long *bytes, char *erro, size_t tam_erro)
{
    char cab[MAX_CAB + 512];
    int n;
    int codigo = -1;
    long tam_conteudo = -1;
    int trocado = 0;
    char buf[2048];
    char *fim_cab;
    size_t usados = 0;
    FILE *fs = 0;
    long escritos = 0;
    char cabresp[4096];

    n = snprintf(cab, sizeof(cab),
                 "%s %s HTTP/1.1\r\n"
                 "Host: %s\r\n"
                 "User-Agent: hiby-r1-scrobbler/1.0\r\n"
                 "Connection: keep-alive\r\n"
                 "Accept-Encoding: identity\r\n",
                 metodo, caminho, h->nome);
    if (cabecalhos && cabecalhos[0])
        n += snprintf(cab + n, sizeof(cab) - n, "%s", cabecalhos);
    if (n_corpo > 0)
        n += snprintf(cab + n, sizeof(cab) - n,
                      "Content-Type: application/x-www-form-urlencoded\r\n"
                      "Content-Length: %lu\r\n", (unsigned long)n_corpo);
    n += snprintf(cab + n, sizeof(cab) - n, "\r\n");

    if (escrever_tudo(h, cab, (size_t)n) != 0) {
        snprintf(erro, tam_erro, "envio do cabecalho");
        return -1;
    }
    if (n_corpo > 0 && escrever_tudo(h, corpo, n_corpo) != 0) {
        snprintf(erro, tam_erro, "envio do corpo");
        return -1;
    }

    /* Cabeçalho da resposta, até a linha em branco. */
    cabresp[0] = 0;
    for (;;) {
        int rc = mbedtls_ssl_read(&h->ssl, (unsigned char *)buf, sizeof(buf));
        if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE)
            continue;
        if (rc <= 0) {
            snprintf(erro, tam_erro, "leitura %d", rc);
            return -1;
        }
        if (usados + (size_t)rc >= sizeof(cabresp)) {
            snprintf(erro, tam_erro, "cabecalho grande demais");
            return -1;
        }
        memcpy(cabresp + usados, buf, (size_t)rc);
        usados += (size_t)rc;
        cabresp[usados] = 0;
        fim_cab = strstr(cabresp, "\r\n\r\n");
        if (fim_cab) break;
    }

    if (sscanf(cabresp, "HTTP/1.%*d %d", &codigo) != 1) {
        snprintf(erro, tam_erro, "resposta ilegivel");
        return -1;
    }
    {
        const char *p = cabresp;
        while ((p = strchr(p, '\n')) != 0) {
            p++;
            if (strncasecmp(p, "Content-Length:", 15) == 0)
                tam_conteudo = strtol(p + 15, 0, 10);
            else if (strncasecmp(p, "Transfer-Encoding:", 18) == 0 &&
                     strstr(p, "chunked"))
                trocado = 1;
            else if (strncasecmp(p, "Connection:", 11) == 0 &&
                     strstr(p, "close"))
                h->ligado = -1;   /* o servidor avisou que vai fechar */
        }
    }

    if (saida && saida[0] && strcmp(saida, "-") != 0) {
        fs = fopen(saida, "wb");
        if (!fs) {
            snprintf(erro, tam_erro, "nao abri %s", saida);
            return -1;
        }
    }

    /* O que já veio junto com o cabeçalho. */
    {
        size_t off = (size_t)(fim_cab - cabresp) + 4;
        size_t sobra = usados - off;
        char *inicio = cabresp + off;

        if (trocado) {
            /* Pedaços: <tamanho em hexa>\r\n<dados>\r\n ... 0\r\n\r\n.
             * O Last.fm responde com Content-Length, mas a API do Tidal já
             * apareceu com pedaços — sem isto o corpo saía truncado e o
             * scrobble ia sem título. */
            char *p = inicio;
            size_t resta = sobra;
            for (;;) {
                char *nl;
                long tam_p;
                while (!(nl = memchr(p, '\n', resta))) {
                    int rc;
                    if (resta + 1 >= sizeof(cabresp)) {
                        snprintf(erro, tam_erro, "pedaco sem fim");
                        goto falhou;
                    }
                    memmove(cabresp, p, resta);
                    p = cabresp;
                    rc = mbedtls_ssl_read(&h->ssl,
                                          (unsigned char *)cabresp + resta,
                                          sizeof(cabresp) - resta - 1);
                    if (rc == MBEDTLS_ERR_SSL_WANT_READ ||
                        rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
                    if (rc <= 0) { snprintf(erro, tam_erro, "pedaco cortado");
                                   goto falhou; }
                    resta += (size_t)rc;
                }
                tam_p = strtol(p, 0, 16);
                resta -= (size_t)(nl + 1 - p);
                p = nl + 1;
                if (tam_p <= 0) break;
                while (tam_p > 0) {
                    size_t leva = resta < (size_t)tam_p ? resta : (size_t)tam_p;
                    if (leva) {
                        if (fs) fwrite(p, 1, leva, fs);
                        escritos += (long)leva;
                        p += leva; resta -= leva; tam_p -= (long)leva;
                    }
                    if (tam_p > 0) {
                        int rc = mbedtls_ssl_read(&h->ssl,
                                                  (unsigned char *)buf,
                                                  sizeof(buf));
                        if (rc == MBEDTLS_ERR_SSL_WANT_READ ||
                            rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
                        if (rc <= 0) { snprintf(erro, tam_erro, "corpo cortado");
                                       goto falhou; }
                        p = buf; resta = (size_t)rc;
                    }
                }
                /* o \r\n que fecha o pedaço */
                while (resta < 2) {
                    int rc = mbedtls_ssl_read(&h->ssl, (unsigned char *)buf,
                                              sizeof(buf));
                    if (rc == MBEDTLS_ERR_SSL_WANT_READ ||
                        rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
                    if (rc <= 0) { snprintf(erro, tam_erro, "fim de pedaco");
                                   goto falhou; }
                    p = buf; resta = (size_t)rc;
                }
                p += 2; resta -= 2;
            }
        } else {
            if (sobra) {
                if (fs) fwrite(inicio, 1, sobra, fs);
                escritos += (long)sobra;
            }
            while (tam_conteudo < 0 || escritos < tam_conteudo) {
                int rc = mbedtls_ssl_read(&h->ssl, (unsigned char *)buf,
                                          sizeof(buf));
                if (rc == MBEDTLS_ERR_SSL_WANT_READ ||
                    rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
                if (rc == 0 || rc == MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY) {
                    h->ligado = -1;
                    break;
                }
                if (rc < 0) {
                    if (tam_conteudo < 0) { h->ligado = -1; break; }
                    snprintf(erro, tam_erro, "corpo %d", rc);
                    goto falhou;
                }
                if (fs) fwrite(buf, 1, (size_t)rc, fs);
                escritos += rc;
            }
        }
    }

    if (fs) fclose(fs);
    *bytes = escritos;
    if (h->ligado == -1) { h->ligado = 1; desligar(h); }
    return codigo;

falhou:
    if (fs) fclose(fs);
    return -1;
}

static void responder(const char *fifo_resp, const char *id, int codigo,
                      long bytes)
{
    FILE *f = fopen(fifo_resp, "w");
    if (!f) return;
    fprintf(f, "%s\t%d\t%ld\n", id, codigo, bytes);
    fclose(f);
}

static char *campo(char **p)
{
    char *ini = *p;
    char *t;
    if (!ini) return 0;
    t = strchr(ini, '\t');
    if (t) { *t = 0; *p = t + 1; } else { *p = 0; }
    return ini;
}

int main(int argc, char **argv)
{
    const char *fifo_ped, *fifo_resp, *cacert, *arq_log;
    int fd;
    char linha[MAX_LINHA];
    static char corpo[MAX_CORPO];
    static char cabextra[MAX_CAB];
    FILE *entrada;

    if (argc < 4) {
        fprintf(stderr,
                "uso: r1net <fifo-pedidos> <fifo-respostas> <cacert.pem> "
                "[log]\n");
        return 2;
    }
    fifo_ped  = argv[1];
    fifo_resp = argv[2];
    cacert    = argv[3];
    arq_log   = (argc > 4) ? argv[4] : 0;

    /* Um pedido que ninguém está lendo não pode derrubar o ajudante. */
    signal(SIGPIPE, SIG_IGN);

    if (arq_log) registro = fopen(arq_log, "a");

    /* TUDO O QUE É CARO ACONTECE AQUI, na partida. É o ponto do programa. */
    mbedtls_ssl_config_init(&conf);
    mbedtls_entropy_init(&entropia);
    mbedtls_ctr_drbg_init(&drbg);
    mbedtls_x509_crt_init(&cadeia);

    if (mbedtls_ctr_drbg_seed(&drbg, mbedtls_entropy_func, &entropia,
                              (const unsigned char *)"r1net", 5) != 0) {
        diz("nao consegui semear o gerador aleatorio");
        return 1;
    }
    if (mbedtls_x509_crt_parse_file(&cadeia, cacert) < 0) {
        diz("nao consegui ler os certificados de %s", cacert);
        return 1;
    }
    if (mbedtls_ssl_config_defaults(&conf, MBEDTLS_SSL_IS_CLIENT,
                                    MBEDTLS_SSL_TRANSPORT_STREAM,
                                    MBEDTLS_SSL_PRESET_DEFAULT) != 0) {
        diz("nao montei a configuracao de TLS");
        return 1;
    }
    /* Verificação obrigatória. Um scrobbler que aceita qualquer certificado
     * entrega a chave de sessão do usuário para quem estiver no meio. */
    mbedtls_ssl_conf_authmode(&conf, MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_ca_chain(&conf, &cadeia, 0);

    /* A lista de algoritmos de assinatura, dita na mão.
     *
     * O mbedTLS monta uma lista padrão a partir do que está compilado, e numa
     * configuração enxuta como a nossa ela sai VAZIA. O sintoma é cruel: o
     * handshake morre com "internal error", e a única pista está no log de
     * depuração da biblioteca — "No signature algorithms defined" —, que em
     * uso normal ninguém liga. Dizer quais são tira a dedução do caminho. */
    mbedtls_ssl_conf_sig_algs(&conf, assinaturas);
    mbedtls_ssl_conf_rng(&conf, mbedtls_ctr_drbg_random, &drbg);

    /* Depuração do próprio mbedTLS, ligada por variável de ambiente. Fica
     * desligada em uso normal — mas quando um handshake falha, "internal
     * error" não diz nada e adivinhar sai caro. R1NET_DEBUG=3 mostra o
     * aperto de mão passo a passo. */
    {
        const char *d = getenv("R1NET_DEBUG");
        if (d && d[0]) {
            mbedtls_debug_set_threshold(atoi(d));
            mbedtls_ssl_conf_dbg(&conf, depurar, 0);
        }
    }

    diz("de pe; certificados de %s", cacert);

    /* O fifo fica aberto para leitura E para escrita ao mesmo tempo, de
     * propósito: com o descritor de escrita nas nossas mãos, o fifo nunca
     * chega a ter zero escritores, e o read() não fica devolvendo EOF em
     * roda-viva entre um pedido e outro. */
    fd = open(fifo_ped, O_RDWR);
    if (fd < 0) {
        diz("nao abri o fifo %s: %s", fifo_ped, strerror(errno));
        return 1;
    }
    entrada = fdopen(fd, "r");
    if (!entrada) { diz("fdopen falhou"); return 1; }

    while (fgets(linha, sizeof(linha), entrada)) {
        char *p = linha;
        char *id, *metodo, *host, *ip, *caminho, *arq_corpo, *saida, *arq_cab;
        Host *h;
        long n_corpo = 0, bytes = 0;
        int codigo;
        char erro[128];
        size_t fim = strlen(linha);

        while (fim && (linha[fim - 1] == '\n' || linha[fim - 1] == '\r'))
            linha[--fim] = 0;
        if (!fim) continue;

        id       = campo(&p);
        metodo   = campo(&p);
        host     = campo(&p);
        ip       = campo(&p);
        caminho  = campo(&p);
        arq_corpo= campo(&p);
        saida    = campo(&p);
        arq_cab  = campo(&p);

        if (!id || !metodo || !host || !caminho) {
            diz("pedido malformado");
            continue;
        }
        if (strcmp(id, "SAIR") == 0) break;

        erro[0] = 0;
        cabextra[0] = 0;
        corpo[0] = 0;

        n_corpo = ler_arquivo(arq_corpo, corpo, sizeof(corpo));
        if (n_corpo < 0) {
            diz("nao li o corpo");
            responder(fifo_resp, id, -1, 0);
            continue;
        }
        if (ler_arquivo(arq_cab, cabextra, sizeof(cabextra)) < 0)
            cabextra[0] = 0;

        h = achar_host(host);
        if (!h) {
            diz("sem lugar para o host %s", host);
            responder(fifo_resp, id, -1, 0);
            continue;
        }

        codigo = -1;
        /* Duas tentativas: a conexão guardada pode ter sido fechada pelo
         * servidor no tempo em que ficou parada, e descobrir isso é escrever
         * nela e falhar. A segunda vez já vai com conexão nova. */
        {
            int tentativa;
            for (tentativa = 0; tentativa < 2 && codigo < 0; tentativa++) {
                if (ligar(h, ip, erro, sizeof(erro)) != 0) {
                    desligar(h);
                    continue;
                }
                codigo = pedir(h, metodo, caminho, corpo, (size_t)n_corpo,
                               cabextra, saida, &bytes, erro, sizeof(erro));
                if (codigo < 0) desligar(h);
            }
        }

        if (codigo < 0)
            diz("%s %s%s falhou: %s", metodo, host, caminho,
                erro[0] ? erro : "sem detalhe");
        else
            diz("%s %s%s -> %d (%ld bytes)%s", metodo, host, caminho, codigo,
                bytes, h->ligado ? ", conexao guardada" : "");

        responder(fifo_resp, id, codigo, bytes);
    }

    diz("saindo");
    return 0;
}
