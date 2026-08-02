/* r1send — monta e confirma um lote de scrobbles, dentro do próprio R1.
 *
 * A divisão de trabalho é de propósito: este programa faz tudo o que exige
 * exatidão (decidir o que conta como execução, assinar em MD5, codificar em
 * percent-encoding) e o curl faz só o que exige TLS. Nada de título de música
 * passa por variável de shell — títulos têm aspas, barras, tabulação, japonês,
 * e cada um desses já quebrou algum scrobbler por aí.
 *
 *   r1send preparar <fila> <enviados> <sk> <segredo> <apikey> <corpo> <ids>
 *       Escolhe até 50 execuções ainda não enviadas, escreve o corpo do POST
 *       já assinado em <corpo> e os rowid correspondentes em <ids>.
 *       stdout: "<quantas>"    saída 0 com lote, 3 quando não há nada a enviar.
 *
 *   r1send confirmar <resposta> <ids> <enviados>
 *       Lê a resposta do Last.fm e acrescenta a <enviados> os rowid aceitos.
 *       stdout: "<aceitos> <recusados>"
 *
 *   r1send listar <fila> <enviados>
 *       Só imprime o que seria enviado, em TSV. Existe para o teste poder
 *       comparar esta implementação com a do PC, linha a linha.
 *
 *   r1send agora <sk> <segredo> <apikey> <corpo> <artista> <titulo>
 *                [album] [duracao]
 *       Monta o corpo assinado de um track.updateNowPlaying — o "tocando
 *       agora" que aparece no perfil do Last.fm. Ao contrário do scrobble,
 *       isto tem de sair ENQUANTO a faixa toca, e não fica em fila: se não
 *       der para mandar, simplesmente não aconteceu.
 *
 * As regras vêm do Last.fm: a faixa precisa durar mais de 30 s e ter sido
 * ouvida por mais da metade, ou por 4 minutos, o que vier antes. Quanto tempo
 * foi ouvido sai do intervalo entre uma linha do histórico e a seguinte.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;

#define MAX_EXEC   4096
#define LOTE       50
#define TXT        512
#define MIN_FAIXA  30
#define CHEIA      240
/* O Last.fm recusa horas com mais de 14 dias; fica uma folga de um dia. */
#define VELHO      (13 * 86400L)
/* Antes disto o relógio do aparelho claramente não tinha sido acertado. */
#define PISO       1704067200L
/* Quanto se supõe que uma faixa dure quando o banco não diz o tamanho ou a
 * taxa de bits. Só entra na conta que espalha um lote no tempo. */
#define DUR_PADRAO 180L

/* ------------------------------------------------------------------ */
/* MD5 — domínio público, RFC 1321                                     */
/* ------------------------------------------------------------------ */

typedef struct { u32 a, b, c, d; u64 n; u8 buf[64]; } Md5;

static const u32 K[64] = {
0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,
0xfd469501,0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,
0xa679438e,0x49b40821,0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,
0x02441453,0xd8a1e681,0xe7d3fbc8,0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,
0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,0xfffa3942,0x8771f681,0x6d9d6122,
0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,0x289b7ec6,0xeaa127fa,
0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,0xf4292244,
0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,
0xeb86d391};
static const int S[64] = {
7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,
5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,
4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,
6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21};

static u32 rol(u32 x, int c) { return (x << c) | (x >> (32 - c)); }

static void md5_bloco(Md5 *m, const u8 *p)
{
    u32 M[16], A = m->a, B = m->b, C = m->c, D = m->d;
    int i;
    for (i = 0; i < 16; i++)
        M[i] = (u32)p[i*4] | ((u32)p[i*4+1] << 8) |
               ((u32)p[i*4+2] << 16) | ((u32)p[i*4+3] << 24);
    for (i = 0; i < 64; i++) {
        u32 F; int g;
        if (i < 16)      { F = (B & C) | (~B & D);        g = i; }
        else if (i < 32) { F = (D & B) | (~D & C);        g = (5*i + 1) & 15; }
        else if (i < 48) { F = B ^ C ^ D;                 g = (3*i + 5) & 15; }
        else             { F = C ^ (B | ~D);              g = (7*i) & 15; }
        F += A + K[i] + M[g];
        A = D; D = C; C = B;
        B += rol(F, S[i]);
    }
    m->a += A; m->b += B; m->c += C; m->d += D;
}

static void md5_init(Md5 *m)
{
    m->a = 0x67452301; m->b = 0xefcdab89;
    m->c = 0x98badcfe; m->d = 0x10325476;
    m->n = 0;
}

static void md5_add(Md5 *m, const void *dados, size_t n)
{
    const u8 *p = (const u8 *)dados;
    size_t usado = (size_t)(m->n & 63);
    m->n += n;
    if (usado) {
        size_t cabe = 64 - usado;
        if (cabe > n) cabe = n;
        memcpy(m->buf + usado, p, cabe);
        usado += cabe; p += cabe; n -= cabe;
        if (usado < 64) return;
        md5_bloco(m, m->buf);
    }
    while (n >= 64) { md5_bloco(m, p); p += 64; n -= 64; }
    if (n) memcpy(m->buf, p, n);
}

static void md5_fim(Md5 *m, char *hex)
{
    static const char H[] = "0123456789abcdef";
    u64 bits = m->n * 8;
    size_t usado = (size_t)(m->n & 63);
    u8 fim[72];
    size_t pad = (usado < 56) ? (56 - usado) : (120 - usado);
    u32 v[4];
    int i;
    memset(fim, 0, sizeof(fim));
    fim[0] = 0x80;
    for (i = 0; i < 8; i++) fim[pad + i] = (u8)(bits >> (8 * i));
    md5_add(m, fim, pad + 8);
    v[0] = m->a; v[1] = m->b; v[2] = m->c; v[3] = m->d;
    for (i = 0; i < 16; i++) {
        u8 b = (u8)(v[i / 4] >> (8 * (i & 3)));
        hex[i*2]   = H[b >> 4];
        hex[i*2+1] = H[b & 15];
    }
    hex[32] = 0;
}

/* ------------------------------------------------------------------ */
/* a fila                                                              */
/* ------------------------------------------------------------------ */

typedef struct {
    long rowid;
    long visto;         /* quando o coletor viu a linha aparecer */
    long inicio;        /* quando a faixa começou: visto menos a duração */
    /* Início declarado pela própria linha, em vez de deduzido.
     *
     * O caminho local não tem como saber: a linha do histórico só aparece
     * quando a faixa acaba, e o começo é inferido. O Tidal tem — o daemon vê
     * a faixa trocar, então sabe o segundo exato em que ela entrou. Quando
     * este campo vem preenchido ele manda, e o tempo ouvido deixa de ser uma
     * estimativa. Zero quer dizer "não sei", que é o caso de toda linha
     * gravada antes deste campo existir. */
    long inicio_dito;
    /* A linha veio da primeira colheita de uma execução do daemon: já estava
     * no banco quando ele acordou, e portanto tocou sem ninguém olhando. O
     * marcador a1 da fila é quem diz isso. */
    int  recuperada;
    long duracao;
    long ouviu;         /* -1 = não dá para saber */
    int  sessao;
    char artista[TXT];
    char titulo[TXT];
    char album[TXT];
    char album_artista[TXT];
} Exec;

typedef struct {
    Exec  v[MAX_EXEC];
    int   n;
    long  suspeito_ate;
} Fila;

static void desescapa(const char *s, char *out, size_t lim)
{
    size_t o = 0;
    while (*s && o + 1 < lim) {
        if (*s == '\\' && s[1]) {
            switch (s[1]) {
            case '\\': out[o++] = '\\'; s += 2; continue;
            case 't':  out[o++] = '\t'; s += 2; continue;
            case 'n':  out[o++] = '\n'; s += 2; continue;
            case 'r':  out[o++] = '\r'; s += 2; continue;
            case 'x':
                if (s[2] && s[3]) {
                    char h[3] = { s[2], s[3], 0 };
                    out[o++] = (char)strtol(h, 0, 16);
                    s += 4;
                    continue;
                }
                break;
            default: break;
            }
        }
        out[o++] = *s++;
    }
    out[o] = 0;
}

/* Parte a linha em campos separados por tabulação, sem alocar. */
static int campos(char *linha, char **out, int max)
{
    int n = 0;
    char *p = linha;
    out[n++] = p;
    while (*p && n < max) {
        if (*p == '\t') { *p = 0; out[n++] = p + 1; }
        p++;
    }
    return n;
}

static void apara(char *s)
{
    size_t n = strlen(s);
    while (n && (s[n-1] == '\n' || s[n-1] == '\r' || s[n-1] == ' ')) s[--n] = 0;
}

/* Lê a fila e reconstrói, do mesmo jeito que o lado do PC.
 *
 * O player do R1 grava a linha quando a faixa TERMINA — medido no aparelho,
 * numa faixa de 3min14 a gravação apareceu 194 s depois do play. Então:
 *
 *   - a hora de início é a da gravação menos a duração;
 *   - a existência da linha já prova que a faixa chegou ao fim;
 *   - mas o tempo ouvido ainda é limitado pelo espaço desde o evento
 *     anterior: uma faixa pulada gera a linha cedo demais para ter tocado
 *     inteira, e a conta pega isso;
 *   - b1 corta a sessão, porque um reinício não é uma pausa entre músicas;
 *   - c1 marca que o relógio estava errado dali para trás.
 */
/* Quando a faixa da posição i parou de tocar.
 *
 * Quase sempre a resposta é trivial e exata: parou quando a seguinte começou.
 * O caso que dá trabalho é a última de cada sessão, que não tem seguinte —
 * ela pode estar tocando agora, pode ter sido pausada, ou o aparelho pode ter
 * sido desligado no meio dela. Em ordem de confiança:
 *
 *   f1  o daemon viu o áudio parar nesta hora. É medido, não deduzido.
 *   i1  depois desta hora nada mais aconteceu. Serve de teto: a faixa não
 *       pode ter passado dali, porque o daemon teria notado.
 *   b1  a sessão seguinte abriu. Entre uma e outra houve um desligamento, e
 *       o mais honesto é fechar a faixa onde a sessão fechou.
 *
 * Sem nenhum dos três a faixa fica em aberto (devolve 0) e não é enviada
 * ainda. Isso é de propósito: a leitura seguinte da fila já vai ter o
 * marcador, e mandar cedo demais é o erro que estava sendo cometido.
 */
static long fim_da_faixa(const Fila *f, int i, const long *fecha, int nfecha,
                         const long *abertura, long agora_ref)
{
    const Exec *e = &f->v[i];
    long teto = 0;
    int k;

    if (i + 1 < f->n && f->v[i+1].sessao == e->sessao)
        return f->v[i+1].inicio_dito > 0 ? f->v[i+1].inicio_dito
                                         : f->v[i+1].visto;

    /* O menor marcador de fechamento posterior a esta faixa. */
    for (k = 0; k < nfecha; k++)
        if (fecha[k] > e->visto && (teto == 0 || fecha[k] < teto))
            teto = fecha[k];

    /* A abertura da sessão seguinte também fecha esta. */
    if (e->sessao + 1 < 64 && abertura[e->sessao + 1] > e->visto
        && (teto == 0 || abertura[e->sessao + 1] < teto))
        teto = abertura[e->sessao + 1];

    if (teto > 0)
        return teto;

    /* Última faixa da última sessão, sem marcador: só o relógio ajuda, e só
     * quando já passou tempo suficiente para a faixa ter cabido. Enquanto
     * não passou, ela continua em aberto. */
    if (agora_ref > 0 && e->duracao > 0
        && agora_ref - e->visto >= e->duracao)
        return e->visto + e->duracao;
    return 0;
}

static int carregar(const char *caminho, Fila *f)
{
    FILE *fh = fopen(caminho, "r");
    char linha[4096];
    int sessao = 0;
    int recuperar = 0;   /* quantas linhas ainda faltam do lote do a1 */
    int i, j;
    long agora_ref = (long)time(0);
    long fecha[256];
    int nfecha = 0;
    /* Quando cada sessão abriu, para a primeira faixa dela ter um limite. */
    long abertura[64];
    if (!fh) return 0;
    memset(abertura, 0, sizeof(abertura));
    f->n = 0;
    f->suspeito_ate = -1;

    while (fgets(linha, sizeof(linha), fh)) {
        char *c[16];
        int nc;
        apara(linha);
        if (!linha[0]) continue;
        nc = campos(linha, c, 16);
        if (nc < 2) continue;

        if (!strcmp(c[0], "b1")) {
            sessao++;
            if (sessao < 64) abertura[sessao] = atol(c[1]);
            recuperar = 0;
            continue;
        }
        if (!strcmp(c[0], "a1")) {
            /* As próximas n linhas já estavam no banco quando o daemon subiu. */
            recuperar = (nc > 2) ? atoi(c[2]) : 0;
            if (recuperar < 0) recuperar = 0;
            continue;
        }
        if (!strcmp(c[0], "c1")) { f->suspeito_ate = atol(c[1]); continue; }
        if (!strcmp(c[0], "f1") || !strcmp(c[0], "i1")
            || !strcmp(c[0], "m1")) {
            /* Horas em que se sabe que a faixa aberta já não estava tocando.
             * O f1 é o bom: o daemon viu o áudio parar. O i1 e o m1 são
             * tetos mais frouxos, mas melhores do que deixar a última faixa
             * de uma sessão sem fechamento nenhum. */
            if (nfecha < 256) fecha[nfecha++] = atol(c[1]);
            continue;
        }
        if (strcmp(c[0], "p1") || nc < 10) continue;
        if (f->n >= MAX_EXEC) break;
        {
            Exec *e = &f->v[f->n];
            memset(e, 0, sizeof(*e));
            e->rowid   = atol(c[1]);
            e->visto   = atol(c[2]);
            e->duracao = atol(c[7]);
            e->ouviu   = -1;
            e->sessao  = sessao;
            /* Campo 11, opcional. Linhas antigas têm um tab final e nada
             * depois, então c[10] existe mas vem vazio. */
            e->inicio_dito = (nc > 10 && c[10][0] >= '0' && c[10][0] <= '9')
                             ? atol(c[10]) : 0;
            if (recuperar > 0) { e->recuperada = 1; recuperar--; }
            desescapa(c[3], e->artista, TXT);
            desescapa(c[4], e->titulo, TXT);
            desescapa(c[5], e->album, TXT);
            desescapa(c[6], e->album_artista, TXT);
            /* uma linha repetida (queda de energia) não vira duas execuções */
            for (j = 0; j < f->n; j++)
                if (f->v[j].rowid == e->rowid) break;
            if (j == f->n) f->n++;
        }
    }
    fclose(fh);

    /* O lote que o daemon encontrou ao acordar precisa de horas inventadas —
     * mas inventadas com critério.
     *
     * Enquanto o daemon está de pé, cada passada acha uma faixa só e "agora"
     * é o fim dela: o espaço até a linha anterior é tempo real, e serve para
     * separar quem ouviu de quem pulou. Na primeira colheita de uma execução
     * isso não vale. O que estava no banco já estava lá antes; tocou sem
     * ninguém olhando, e todas as linhas chegam com o mesmo carimbo — o de
     * agora. O "espaço desde a anterior" dava zero, e o resultado era o que
     * dois usuários relataram: um disco inteiro registrado como 0s, e a
     * primeira faixa contada como ouvida por inteiro no instante em que
     * começou.
     *
     * Isso não era um erro de conta. O daemon realmente não estava lá — e no
     * firmware de fábrica ele nunca está, porque nada naquele sistema executa
     * o /usr/data/init.sh. Para essas pessoas a primeira colheita não é um
     * caso raro: é o caminho normal, toda vez que ligam o aparelho.
     *
     * O banco do player não guarda hora nenhuma (ctime e mtime vêm nulos,
     * begin_time zero, end_time -1); o rowid é a única coisa que diz a ordem.
     * Então o lote é esticado para trás a partir da hora da coleta, cada
     * faixa terminando onde a seguinte começa. É uma reconstrução, não uma
     * medida, e vale só para o lote marcado com a1: nas colheitas seguintes o
     * espaço entre as linhas é real e continua mandando, para que uma
     * sequência de pulos não vire uma sequência de scrobbles.
     */
    for (i = f->n - 1; i >= 0; i--) {
        Exec *e = &f->v[i];
        long d;
        if (!e->recuperada || e->inicio_dito > 0) continue;
        d = e->duracao > 0 ? e->duracao : DUR_PADRAO;
        /* Termina onde a seguinte do mesmo lote começou, ou na hora da coleta
         * se for a última dele. */
        if (i + 1 < f->n && f->v[i+1].recuperada
            && f->v[i+1].sessao == e->sessao
            && f->v[i+1].inicio_dito > 0
            && f->v[i+1].inicio_dito < e->visto)
            e->visto = f->v[i+1].inicio_dito;
        e->inicio_dito = e->visto - d;
    }

    /* A linha do histórico entra quando a faixa COMEÇA, não quando acaba.
     *
     * Este arquivo inteiro assumiu o contrário desde o primeiro dia, e a
     * conta saía deslocada em uma faixa. Foi observado ao vivo no aparelho:
     * às 08:49:41 o player trocou para outra faixa e a última linha do
     * histórico virou aquela faixa no mesmo instante, com o pcm ainda aberto
     * e a música tocando por mais quarenta e cinco segundos.
     *
     * Duas coisas seguem disso, e as duas foram relatadas por quem usou:
     *
     *   - a hora mandada ao Last.fm era `visto - duracao`, ou seja, uma faixa
     *     inteira ANTES de a faixa ter começado;
     *   - o espaço entre duas linhas é quanto a ANTERIOR tocou, não a atual.
     *     Creditá-lo à atual dava "esta faixa nem terminou e já aparece como
     *     ouvida por inteiro", enquanto a de verdade ouvida — a primeira da
     *     sessão, que não tinha anterior — ficava com zero.
     *
     * Com o modelo certo não há mais estimativa nenhuma no meio do caminho: a
     * hora da linha É o começo da faixa (a menos do atraso do laço, no
     * máximo uma volta), e o começo da seguinte é o fim desta. Uma faixa
     * pulada aparece sozinha: o espaço até a próxima é curto, e a regra da
     * metade a descarta.
     *
     * Só a ÚLTIMA faixa de cada sessão não tem "próxima" que a feche. Para
     * ela o daemon manda o marcador f1 com a hora em que o áudio parou; sem
     * ele sobra o i1 ("depois disto nada mais aconteceu"), e sem os dois ela
     * fica em aberto até a próxima leitura da fila.
     */
    for (i = 0; i < f->n; i++) {
        Exec *e = &f->v[i];
        long fim;

        /* O Tidal continua sendo o caso feliz: lá o daemon vê a troca de
         * faixa e diz o começo exato, então nada precisa ser deduzido. */
        if (e->inicio_dito > 0 && e->inicio_dito <= e->visto) {
            e->inicio = e->inicio_dito;
            fim = e->visto;
        } else {
            e->inicio = e->visto;
            fim = fim_da_faixa(f, i, fecha, nfecha, abertura, agora_ref);
        }

        if (fim <= e->inicio) {
            /* Ainda tocando, ou o fim é desconhecido: sem tempo ouvido. A
             * linha fica na fila e a leitura seguinte já a fecha. */
            e->ouviu = 0;
            continue;
        }
        e->ouviu = fim - e->inicio;
        if (e->duracao > 0 && e->ouviu > e->duracao)
            e->ouviu = e->duracao;
    }
    return 1;
}

/* A lista do que já foi aceito, carregada uma vez e consultada por busca
 * binária.
 *
 * A versão anterior reabria o arquivo e o varria inteiro para CADA faixa da
 * fila. Com a fila e a lista crescendo juntas isso é O(n·m) com um fopen por
 * faixa — invisível nos primeiros dias e cada vez mais caro depois, num
 * aparelho cujo argumento inteiro é não custar nada. Como as duas coisas
 * cabem folgadas na memória (8 bytes por rowid), ler uma vez resolve.
 */
typedef struct {
    long *v;
    int n;
} Enviados;

static int cmp_long(const void *a, const void *b)
{
    long x = *(const long *)a, y = *(const long *)b;
    return (x > y) - (x < y);
}

static void enviados_liberar(Enviados *e)
{
    free(e->v);
    e->v = 0;
    e->n = 0;
}

/* Devolve 0 só quando faltou memória; arquivo ausente é uma lista vazia, que
 * é a resposta certa para uma instalação nova. */
static int enviados_ler(const char *caminho, Enviados *e)
{
    FILE *fh;
    long v;
    int cap = 256;
    e->v = 0;
    e->n = 0;
    fh = fopen(caminho, "r");
    if (!fh) return 1;
    e->v = (long *)malloc((size_t)cap * sizeof(long));
    if (!e->v) { fclose(fh); return 0; }
    while (fscanf(fh, "%ld", &v) == 1) {
        if (e->n == cap) {
            long *maior = (long *)realloc(e->v, (size_t)cap * 2 * sizeof(long));
            if (!maior) { fclose(fh); enviados_liberar(e); return 0; }
            e->v = maior;
            cap *= 2;
        }
        e->v[e->n++] = v;
    }
    fclose(fh);
    if (e->n > 1) qsort(e->v, (size_t)e->n, sizeof(long), cmp_long);
    return 1;
}

static int ja_enviado(const Enviados *e, long rowid)
{
    int lo = 0, hi = e->n - 1;
    while (lo <= hi) {
        int meio = lo + (hi - lo) / 2;
        if (e->v[meio] == rowid) return 1;
        if (e->v[meio] < rowid) lo = meio + 1;
        else hi = meio - 1;
    }
    return 0;
}

/* A faixa conta como execução? */
static int vale(const Exec *e, long agora, long suspeito_ate)
{
    long precisa;
    if (!e->artista[0] || !e->titulo[0]) return 0;
    if (e->visto <= 0 || e->inicio <= 0) return 0;
    if (e->visto <= suspeito_ate) return 0;
    if (e->inicio < PISO) return 0;
    if (e->inicio > agora + 300) return 0;
    if (agora - e->inicio > VELHO) return 0;
    if (e->duracao > 0 && e->duracao < MIN_FAIXA) return 0;
    if (e->duracao > 0 && e->ouviu >= 0) {
        precisa = e->duracao / 2;
        if (precisa > CHEIA) precisa = CHEIA;
        if (e->ouviu < precisa) return 0;
    }
    return 1;
}

/* ------------------------------------------------------------------ */
/* parâmetros, assinatura e corpo                                      */
/* ------------------------------------------------------------------ */

/* Lê um dos arquivinhos de credencial. Devolve 0 se veio vazio. */
static int ler_valor(const char *caminho, char *out, size_t lim)
{
    FILE *fh = fopen(caminho, "r");
    (void)lim;          /* o limite está no próprio formato do fscanf */
    out[0] = 0;
    if (!fh) return 0;
    if (fscanf(fh, "%127s", out) != 1) out[0] = 0;
    fclose(fh);
    return out[0] != 0;
}

typedef struct { char nome[32]; char valor[TXT]; } Par;

static int cmp_par(const void *a, const void *b)
{
    return strcmp(((const Par *)a)->nome, ((const Par *)b)->nome);
}

static void por(Par *v, int *n, const char *nome, const char *valor)
{
    if (*n >= 400 || !valor || !valor[0]) return;
    snprintf(v[*n].nome, sizeof(v[*n].nome), "%s", nome);
    snprintf(v[*n].valor, sizeof(v[*n].valor), "%s", valor);
    (*n)++;
}

static void por_num(Par *v, int *n, const char *nome, long valor)
{
    char b[32];
    snprintf(b, sizeof(b), "%ld", valor);
    por(v, n, nome, b);
}

/* Percent-encoding do application/x-www-form-urlencoded. Byte a byte, então
 * UTF-8 sai correto sem o programa precisar saber o que é UTF-8. */
static void escreve_enc(FILE *f, const char *s)
{
    static const char H[] = "0123456789ABCDEF";
    const u8 *p = (const u8 *)s;
    for (; *p; p++) {
        u8 c = *p;
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_' ||
            c == '.' || c == '~')
            fputc(c, f);
        else if (c == ' ')
            fputc('+', f);
        else {
            fputc('%', f);
            fputc(H[c >> 4], f);
            fputc(H[c & 15], f);
        }
    }
}

static int cmd_preparar(int argc, char **argv)
{
    const char *f_fila, *f_env, *f_sk, *f_seg, *f_key, *f_corpo, *f_ids;
    Fila *fila;
    Enviados enviados = { 0, 0 };
    Par *pars;
    int np = 0, quantos = 0, i;
    long agora = (long)time(0);
    Md5 md;
    char sig[33];
    FILE *out;
    long ids[LOTE];

    if (argc != 9) {
        fprintf(stderr, "uso: %s preparar <fila> <enviados> <sk> <segredo> "
                        "<apikey> <corpo> <ids>\n", argv[0]);
        return 1;
    }
    f_fila = argv[2]; f_env = argv[3]; f_sk = argv[4];
    f_seg = argv[5]; f_key = argv[6]; f_corpo = argv[7]; f_ids = argv[8];

    fila = (Fila *)calloc(1, sizeof(Fila));
    pars = (Par *)calloc(400, sizeof(Par));
    if (!fila || !pars) { fprintf(stderr, "sem memoria\n"); return 2; }
    if (!carregar(f_fila, fila)) {
        /* Fila inexistente é o estado normal logo depois de instalar: o
         * coletor ainda não viu nada tocar. Isso é "nada a enviar", não
         * erro — dizer "nao consegui ler" aqui assusta à toa. */
        printf("0\n");
        enviados_liberar(&enviados); free(fila); free(pars);
        return 3;
    }

    if (!enviados_ler(f_env, &enviados)) { enviados_liberar(&enviados); free(fila); free(pars); return 2; }
    for (i = 0; i < fila->n && quantos < LOTE; i++) {
        Exec *e = &fila->v[i];
        char nome[32];
        if (!vale(e, agora, fila->suspeito_ate)) continue;
        if (ja_enviado(&enviados, e->rowid)) continue;
        snprintf(nome, sizeof(nome), "artist[%d]", quantos);
        por(pars, &np, nome, e->artista);
        snprintf(nome, sizeof(nome), "track[%d]", quantos);
        por(pars, &np, nome, e->titulo);
        snprintf(nome, sizeof(nome), "timestamp[%d]", quantos);
        por_num(pars, &np, nome, e->inicio);
        if (e->album[0]) {
            snprintf(nome, sizeof(nome), "album[%d]", quantos);
            por(pars, &np, nome, e->album);
        }
        if (e->album_artista[0] && strcmp(e->album_artista, e->artista)) {
            snprintf(nome, sizeof(nome), "albumArtist[%d]", quantos);
            por(pars, &np, nome, e->album_artista);
        }
        if (e->duracao >= MIN_FAIXA) {
            snprintf(nome, sizeof(nome), "duration[%d]", quantos);
            por_num(pars, &np, nome, e->duracao);
        }
        ids[quantos++] = e->rowid;
    }

    if (!quantos) {
        printf("0\n");
        enviados_liberar(&enviados); free(fila); free(pars);
        return 3;
    }

    {
        char sk[128], seg[128], key[128];
        int tem = ler_valor(f_sk, sk, sizeof(sk))
                & ler_valor(f_seg, seg, sizeof(seg))
                & ler_valor(f_key, key, sizeof(key));
        if (!tem) {
            fprintf(stderr, "r1send: falta a chave de sessao, o segredo ou a "
                            "chave de api\n");
            enviados_liberar(&enviados); free(fila); free(pars);
            return 2;
        }
        por(pars, &np, "api_key", key);
        por(pars, &np, "method", "track.scrobble");
        por(pars, &np, "sk", sk);

        /* A assinatura é o MD5 de nome+valor de todos os parâmetros em ordem
         * alfabética de nome, colados sem separador, mais o segredo. O
         * `format` fica de fora — e por isso ele nem entra na lista. */
        qsort(pars, (size_t)np, sizeof(Par), cmp_par);
        md5_init(&md);
        for (i = 0; i < np; i++) {
            md5_add(&md, pars[i].nome, strlen(pars[i].nome));
            md5_add(&md, pars[i].valor, strlen(pars[i].valor));
        }
        md5_add(&md, seg, strlen(seg));
        md5_fim(&md, sig);
    }

    out = fopen(f_corpo, "w");
    if (!out) {
        fprintf(stderr, "r1send: nao consegui escrever %s\n", f_corpo);
        enviados_liberar(&enviados); free(fila); free(pars);
        return 2;
    }
    for (i = 0; i < np; i++) {
        if (i) fputc('&', out);
        escreve_enc(out, pars[i].nome);
        fputc('=', out);
        escreve_enc(out, pars[i].valor);
    }
    fprintf(out, "&api_sig=%s&format=json", sig);
    if (fflush(out) || fclose(out)) {
        fprintf(stderr, "r1send: falha ao gravar %s\n", f_corpo);
        enviados_liberar(&enviados); free(fila); free(pars);
        return 2;
    }

    out = fopen(f_ids, "w");
    if (out) {
        for (i = 0; i < quantos; i++) fprintf(out, "%ld\n", ids[i]);
        fclose(out);
    }
    printf("%d\n", quantos);
    enviados_liberar(&enviados); free(fila); free(pars);
    return 0;
}

/* ------------------------------------------------------------------ */
/* a resposta                                                          */
/* ------------------------------------------------------------------ */

/* Não é um parser de JSON: procura as ocorrências de "ignoredMessage" na
 * ordem em que vieram — que é a ordem do pedido — e lê o "code" de cada uma.
 * Código "0" quer dizer aceita. Se a resposta trouxer "error", nada entrou.
 */
static int cmd_confirmar(int argc, char **argv)
{
    FILE *fh;
    char *buf;
    long tam;
    long ids[LOTE];
    int nids = 0, i = 0, aceitos = 0, recusados = 0;
    const char *p;

    if (argc != 5) {
        fprintf(stderr, "uso: %s confirmar <resposta> <ids> <enviados>\n",
                argv[0]);
        return 1;
    }
    fh = fopen(argv[3], "r");
    if (fh) {
        long v;
        while (nids < LOTE && fscanf(fh, "%ld", &v) == 1) ids[nids++] = v;
        fclose(fh);
    }
    if (!nids) { fprintf(stderr, "r1send: lista de ids vazia\n"); return 2; }

    fh = fopen(argv[2], "rb");
    if (!fh) { fprintf(stderr, "r1send: sem resposta para ler\n"); return 2; }
    fseek(fh, 0, SEEK_END); tam = ftell(fh); rewind(fh);
    if (tam <= 0 || tam > 1000000) { fclose(fh);
        fprintf(stderr, "r1send: resposta de tamanho improvavel (%ld)\n", tam);
        return 2; }
    buf = (char *)malloc((size_t)tam + 1);
    if (!buf) { fclose(fh); return 2; }
    if (fread(buf, 1, (size_t)tam, fh) != (size_t)tam) {
        fclose(fh); free(buf); return 2;
    }
    fclose(fh);
    buf[tam] = 0;

    if (strstr(buf, "\"error\"")) {
        const char *e = strstr(buf, "\"error\"");
        fprintf(stderr, "r1send: o Last.fm recusou o lote: %.200s\n", e);
        free(buf);
        return 4;
    }

    fh = fopen(argv[4], "a");
    if (!fh) { free(buf); return 2; }
    p = buf;
    while ((p = strstr(p, "\"ignoredMessage\"")) != 0 && i < nids) {
        const char *c = strstr(p, "\"code\"");
        int aceita = 0;
        if (c) {
            c += 6;
            while (*c == ':' || *c == ' ' || *c == '"') c++;
            aceita = (*c == '0');
        }
        if (aceita) { fprintf(fh, "%ld\n", ids[i]); aceitos++; }
        else recusados++;
        i++;
        p += 16;
    }
    fclose(fh);
    free(buf);

    if (!i) {
        fprintf(stderr, "r1send: a resposta nao trouxe confirmacao nenhuma\n");
        return 4;
    }
    printf("%d %d\n", aceitos, recusados);
    return 0;
}

static int cmd_agora(int argc, char **argv)
{
    Par *pars;
    int np = 0, i;
    Md5 md;
    char sig[33];
    char sk[128], seg[128], key[128];
    FILE *out;

    if (argc < 8) {
        fprintf(stderr, "uso: %s agora <sk> <segredo> <apikey> <corpo> "
                        "<artista> <titulo> [album] [duracao]\n", argv[0]);
        return 1;
    }
    if (!ler_valor(argv[2], sk, sizeof(sk)) ||
        !ler_valor(argv[3], seg, sizeof(seg)) ||
        !ler_valor(argv[4], key, sizeof(key))) {
        fprintf(stderr, "r1send: falta a chave de sessao, o segredo ou a "
                        "chave de api\n");
        return 2;
    }
    if (!argv[6][0] || !argv[7][0]) {
        fprintf(stderr, "r1send: artista e titulo sao obrigatorios\n");
        return 1;
    }

    pars = (Par *)calloc(400, sizeof(Par));
    if (!pars) return 2;

    por(pars, &np, "artist", argv[6]);
    por(pars, &np, "track", argv[7]);
    if (argc > 8 && argv[8][0]) por(pars, &np, "album", argv[8]);
    if (argc > 9) {
        long dur = strtol(argv[9], 0, 10);
        /* Faixa curta demais nem deveria virar "tocando agora"; e o Last.fm
         * usa a duracao para saber quando apagar o aviso do perfil. */
        if (dur >= MIN_FAIXA) por_num(pars, &np, "duration", dur);
    }
    por(pars, &np, "api_key", key);
    por(pars, &np, "method", "track.updateNowPlaying");
    por(pars, &np, "sk", sk);

    qsort(pars, (size_t)np, sizeof(Par), cmp_par);
    md5_init(&md);
    for (i = 0; i < np; i++) {
        md5_add(&md, pars[i].nome, strlen(pars[i].nome));
        md5_add(&md, pars[i].valor, strlen(pars[i].valor));
    }
    md5_add(&md, seg, strlen(seg));
    md5_fim(&md, sig);

    out = fopen(argv[5], "w");
    if (!out) {
        fprintf(stderr, "r1send: nao consegui escrever %s\n", argv[5]);
        free(pars);
        return 2;
    }
    for (i = 0; i < np; i++) {
        if (i) fputc('&', out);
        escreve_enc(out, pars[i].nome);
        fputc('=', out);
        escreve_enc(out, pars[i].valor);
    }
    fprintf(out, "&api_sig=%s&format=json", sig);
    if (fflush(out) || fclose(out)) {
        fprintf(stderr, "r1send: falha ao gravar %s\n", argv[5]);
        free(pars);
        return 2;
    }
    printf("1\n");
    free(pars);
    return 0;
}

static int cmd_listar(int argc, char **argv)
{
    Fila *fila;
    Enviados enviados = { 0, 0 };
    long agora = (long)time(0);
    int i;
    if (argc != 4) {
        fprintf(stderr, "uso: %s listar <fila> <enviados>\n", argv[0]);
        return 1;
    }
    fila = (Fila *)calloc(1, sizeof(Fila));
    if (!fila) return 2;
    if (!carregar(argv[2], fila)) { free(fila); return 2; }
    if (!enviados_ler(argv[3], &enviados)) { free(fila); return 2; }
    for (i = 0; i < fila->n; i++) {
        Exec *e = &fila->v[i];
        if (!vale(e, agora, fila->suspeito_ate)) continue;
        if (ja_enviado(&enviados, e->rowid)) continue;
        /* A hora impressa é a de INÍCIO, que é a que vai para o Last.fm — o
         * teste diferencial compara esta saída com a do lado do PC. */
        printf("%ld\t%ld\t%s\t%s\t%s\t%ld\t%ld\n", e->rowid, e->inicio,
               e->artista, e->titulo, e->album, e->duracao, e->ouviu);
    }
    enviados_liberar(&enviados);
    free(fila);
    return 0;
}

/* ------------------------------------------------------------------ */
/* o relatório para o cartão                                           */
/* ------------------------------------------------------------------ */

/* Um campo de CSV, com as aspas do RFC 4180.
 *
 * Escapar aqui não é preciosismo: nomes de faixa trazem vírgula e aspas com
 * frequência ("Sgt. Pepper's", "Hello, Goodbye"), e uma planilha lida um
 * arquivo mal escapado deslocando colunas em silêncio — o pior desfecho
 * possível para um arquivo cujo propósito é ser processado por outra pessoa.
 */
static void csv_campo(FILE *f, const char *s)
{
    const char *p;
    int precisa = 0;
    for (p = s; *p; p++)
        if (*p == ',' || *p == '"' || *p == '\n' || *p == '\r') { precisa = 1; break; }
    if (!precisa) { fputs(s, f); return; }
    fputc('"', f);
    for (p = s; *p; p++) {
        if (*p == '"') fputc('"', f);
        /* CR e LF viram espaço: uma quebra de linha real dentro de um campo é
         * válida no RFC mas quebra metade das ferramentas que leem CSV. */
        fputc((*p == '\n' || *p == '\r') ? ' ' : *p, f);
    }
    fputc('"', f);
}

static void csv_iso(char *out, size_t lim, long epoca)
{
    time_t t = (time_t)epoca;
    struct tm *tm = localtime(&t);
    if (!tm || epoca <= 0) { snprintf(out, lim, ""); return; }
    strftime(out, lim, "%Y-%m-%d %H:%M:%S", tm);
}

/* O que aconteceu com esta faixa, em uma palavra que a pessoa entenda. */
static const char *situacao(const Exec *e, long agora, long suspeito_ate,
                            int enviado)
{
    long precisa;
    if (enviado) return "sent";
    if (!e->artista[0] || !e->titulo[0]) return "no-metadata";
    if (e->visto <= suspeito_ate) return "bad-clock";
    if (e->inicio < PISO) return "bad-clock";
    if (e->inicio > agora + 300) return "future";
    if (agora - e->inicio > VELHO) return "too-old";
    if (e->duracao > 0 && e->duracao < MIN_FAIXA) return "track-too-short";
    if (e->duracao > 0 && e->ouviu >= 0) {
        precisa = e->duracao / 2;
        if (precisa > CHEIA) precisa = CHEIA;
        if (e->ouviu < precisa) return "skipped";
    }
    return "pending";
}

/* Escreve a fila inteira como CSV, para quem quiser processar por fora.
 *
 * Vai para o cartão de memória, onde é lido plugando o cartão no computador —
 * sem ADB, sem este instalador, sem nada. É o arquivo que sobrevive a
 * desinstalar o scrobbler.
 *
 * Escreve num temporário e renomeia: se a bateria acabar no meio, o que fica
 * no cartão é a versão anterior inteira, e não meio arquivo.
 */
static int cmd_relatorio(int argc, char **argv)
{
    Fila *fila;
    Enviados enviados = { 0, 0 };
    long agora = (long)time(0);
    char tmp[512];
    FILE *f;
    int i;
    if (argc != 5) {
        fprintf(stderr, "uso: %s relatorio <fila> <enviados> <saida.csv>\n",
                argv[0]);
        return 1;
    }
    fila = (Fila *)calloc(1, sizeof(Fila));
    if (!fila) return 2;
    if (!carregar(argv[2], fila)) { free(fila); return 2; }

    if (!enviados_ler(argv[3], &enviados)) { free(fila); return 2; }

    snprintf(tmp, sizeof(tmp), "%s.tmp", argv[4]);
    f = fopen(tmp, "w");
    if (!f) { enviados_liberar(&enviados); free(fila); return 2; }

    fputs("started_at,started_at_epoch,artist,track,album,album_artist,"
          "seconds_heard,track_seconds,status,rowid\n", f);
    for (i = 0; i < fila->n; i++) {
        Exec *e = &fila->v[i];
        char quando[32];
        int enviado = ja_enviado(&enviados, e->rowid);
        csv_iso(quando, sizeof(quando), e->inicio);
        csv_campo(f, quando);                       fputc(',', f);
        fprintf(f, "%ld,", e->inicio);
        csv_campo(f, e->artista);                   fputc(',', f);
        csv_campo(f, e->titulo);                    fputc(',', f);
        csv_campo(f, e->album);                     fputc(',', f);
        csv_campo(f, e->album_artista);             fputc(',', f);
        fprintf(f, "%ld,%ld,", e->ouviu, e->duracao);
        csv_campo(f, situacao(e, agora, fila->suspeito_ate, enviado));
        fprintf(f, ",%ld\n", e->rowid);
    }
    enviados_liberar(&enviados);
    free(fila);
    /* fclose antes do rename, e o rename só depois de saber que o fclose deu
     * certo: num cartão cheio é o fclose que falha, e renomear mesmo assim
     * publicaria um CSV truncado por cima do bom. */
    if (fclose(f) != 0) { remove(tmp); return 2; }
    if (rename(tmp, argv[4]) != 0) { remove(tmp); return 2; }
    return 0;
}

/* ------------------------------------------------------------------ */
/* a resposta do Tidal                                                 */
/* ------------------------------------------------------------------ */

/* Copia uma string JSON, desfazendo os escapes que importam.
 *
 * Títulos vêm com \" e com \uXXXX o tempo todo — "Don't", aspas tipográficas,
 * japonês. Deixar o escape passar cru mandaria "Don’t" para o Last.fm.
 * Devolve o ponteiro logo depois da aspa de fechamento, ou NULL.
 */
static const char *json_str(const char *p, char *out, size_t lim)
{
    size_t o = 0;
    if (*p != '"') return 0;
    p++;
    while (*p && *p != '"') {
        if (*p == '\\' && p[1]) {
            p++;
            switch (*p) {
            case 'n': case 't': case 'r': case 'b': case 'f':
                /* Controles viram espaço: nenhum deles faz sentido num
                 * título, e um \n cru quebraria a linha da fila. */
                if (o + 1 < lim) out[o++] = ' ';
                p++;
                continue;
            case 'u': {
                unsigned cp = 0;
                int i;
                for (i = 1; i <= 4 && p[i]; i++) {
                    char c = p[i];
                    cp <<= 4;
                    if (c >= '0' && c <= '9') cp |= (unsigned)(c - '0');
                    else if (c >= 'a' && c <= 'f') cp |= (unsigned)(c - 'a' + 10);
                    else if (c >= 'A' && c <= 'F') cp |= (unsigned)(c - 'A' + 10);
                    else { cp = 0; break; }
                }
                if (i < 5) { p++; continue; }
                p += 5;
                /* Pares substitutos: o Tidal manda emoji em títulos. Sem
                 * juntá-los sai lixo em vez de caractere. */
                if (cp >= 0xD800 && cp <= 0xDBFF && p[0] == '\\' && p[1] == 'u') {
                    unsigned baixo = 0;
                    for (i = 2; i <= 5 && p[i]; i++) {
                        char c = p[i];
                        baixo <<= 4;
                        if (c >= '0' && c <= '9') baixo |= (unsigned)(c - '0');
                        else if (c >= 'a' && c <= 'f') baixo |= (unsigned)(c - 'a' + 10);
                        else if (c >= 'A' && c <= 'F') baixo |= (unsigned)(c - 'A' + 10);
                        else { baixo = 0; break; }
                    }
                    if (baixo >= 0xDC00 && baixo <= 0xDFFF) {
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (baixo - 0xDC00);
                        p += 6;
                    }
                }
                /* UTF-8 na saída, que é o que o Last.fm espera. */
                if (cp < 0x80) {
                    if (o + 1 < lim) out[o++] = (char)cp;
                } else if (cp < 0x800) {
                    if (o + 2 < lim) {
                        out[o++] = (char)(0xC0 | (cp >> 6));
                        out[o++] = (char)(0x80 | (cp & 0x3F));
                    }
                } else if (cp < 0x10000) {
                    if (o + 3 < lim) {
                        out[o++] = (char)(0xE0 | (cp >> 12));
                        out[o++] = (char)(0x80 | ((cp >> 6) & 0x3F));
                        out[o++] = (char)(0x80 | (cp & 0x3F));
                    }
                } else {
                    if (o + 4 < lim) {
                        out[o++] = (char)(0xF0 | (cp >> 18));
                        out[o++] = (char)(0x80 | ((cp >> 12) & 0x3F));
                        out[o++] = (char)(0x80 | ((cp >> 6) & 0x3F));
                        out[o++] = (char)(0x80 | (cp & 0x3F));
                    }
                }
                continue;
            }
            default:
                /* \" \\ \/ e qualquer outro: o próprio caractere. */
                if (o + 1 < lim) out[o++] = *p;
                p++;
                continue;
            }
        }
        if (o + 1 < lim) out[o++] = *p;
        p++;
    }
    out[o] = 0;
    return *p == '"' ? p + 1 : 0;
}

/* Acha "chave": e devolve o que vem depois, pulando espaços. */
static const char *json_campo(const char *json, const char *chave)
{
    char alvo[64];
    const char *p;
    snprintf(alvo, sizeof(alvo), "\"%s\"", chave);
    p = strstr(json, alvo);
    if (!p) return 0;
    p += strlen(alvo);
    while (*p == ' ' || *p == '\t') p++;
    if (*p != ':') return 0;
    p++;
    while (*p == ' ' || *p == '\t') p++;
    return p;
}

/* Extrai de uma resposta do /v1/tracks/<id> o que o Last.fm precisa.
 *
 * Um campo por linha, na ordem artista / título / álbum / duração — o mesmo
 * formato que `r1collect buscar` já usa, para o daemon ler os dois do mesmo
 * jeito. Sem parser de JSON genérico: a resposta é conhecida, e o que
 * importa é não engasgar com escapes nos títulos.
 */
static int cmd_tidalinfo(int argc, char **argv)
{
    FILE *fh;
    char *json;
    long tam;
    const char *p;
    char artista[TXT] = "", titulo[TXT] = "", album[TXT] = "";
    long duracao = 0;

    if (argc != 3) {
        fprintf(stderr, "uso: %s tidalinfo <resposta.json>\n", argv[0]);
        return 1;
    }
    fh = fopen(argv[2], "rb");
    if (!fh) return 2;
    fseek(fh, 0, SEEK_END);
    tam = ftell(fh);
    fseek(fh, 0, SEEK_SET);
    if (tam <= 0 || tam > (1 << 20)) { fclose(fh); return 2; }
    json = (char *)malloc((size_t)tam + 1);
    if (!json) { fclose(fh); return 2; }
    tam = (long)fread(json, 1, (size_t)tam, fh);
    fclose(fh);
    json[tam] = 0;

    /* Um erro da API vem como {"status":401,...} e não tem título nenhum. */
    if (json_campo(json, "status") && !json_campo(json, "title")) {
        free(json);
        return 3;
    }

    p = json_campo(json, "title");
    if (p) json_str(p, titulo, sizeof(titulo));

    /* "artist" vem como objeto; o nome está dentro dele. Procurar "name"
     * a partir dali evita pegar o "name" de outra parte do JSON. */
    p = json_campo(json, "artist");
    if (p && *p == '{') {
        const char *nome = json_campo(p, "name");
        if (nome) json_str(nome, artista, sizeof(artista));
    }
    p = json_campo(json, "album");
    if (p && *p == '{') {
        const char *t = json_campo(p, "title");
        if (t) json_str(t, album, sizeof(album));
    }
    p = json_campo(json, "duration");
    if (p) duracao = atol(p);

    free(json);
    if (!artista[0] || !titulo[0]) return 3;
    printf("%s\n%s\n%s\n%ld\n", artista, titulo, album, duracao);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr,
                "uso: %s preparar|confirmar|listar|agora|relatorio|"
                "tidalinfo ...\n", argv[0]);
        return 1;
    }
    if (!strcmp(argv[1], "tidalinfo")) return cmd_tidalinfo(argc, argv);
    if (!strcmp(argv[1], "preparar"))  return cmd_preparar(argc, argv);
    if (!strcmp(argv[1], "confirmar")) return cmd_confirmar(argc, argv);
    if (!strcmp(argv[1], "listar"))    return cmd_listar(argc, argv);
    if (!strcmp(argv[1], "agora"))     return cmd_agora(argc, argv);
    if (!strcmp(argv[1], "relatorio")) return cmd_relatorio(argc, argv);
    fprintf(stderr, "%s: subcomando desconhecido: %s\n", argv[0], argv[1]);
    return 1;
}
