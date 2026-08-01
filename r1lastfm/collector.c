/* r1collect — lê o histórico de reprodução do HiBy R1 e enfileira o que é novo.
 *
 * Roda no aparelho. Compilado estático para mipsel, sem nenhuma biblioteca
 * além da libc, e sem o SQLite: aqui há um leitor do formato de arquivo do
 * SQLite feito à mão, só de leitura.
 *
 * Por que não usar o SQLite de verdade:
 *
 *   - São 20 KB contra 1 MB. Num aparelho com 56 MB de RAM isso importa.
 *   - Este código não tem nenhum caminho que escreva. O banco do player não
 *     pode ser corrompido por um erro meu, porque o arquivo é aberto para
 *     leitura e nunca há journal, lock ou recuperação.
 *   - O formato é público e estável desde 2004.
 *
 * O que ele lê: /usr/data/usrlocal_media.db, tabela HISTORY_TABLE. Cada linha
 * é uma faixa que o player registrou, e o rowid cresce a cada reprodução —
 * inclusive quando a mesma faixa é repetida, porque o player apaga a linha
 * antiga e insere outra no fim. Então "rowid maior que o último visto" é
 * exatamente "o que tocou desde a última olhada".
 *
 * A duração não está guardada em lugar nenhum, mas size e bit_rate estão, e
 * bit_rate foi calculado pelo próprio player a partir da duração. Inverter a
 * conta devolve a duração com erro de fração de segundo (conferido: 257,2 s
 * calculados contra 257,5 s reais numa faixa de 4 min).
 *
 * Uso:
 *     r1collect <banco> <ultimo-rowid> <arquivo-de-saida>
 *
 * Saída no stdout: "<linhas-novas> <maior-rowid>".
 * Código de saída: 0 tudo bem, 1 erro de uso, 2 banco ilegível.
 *
 * O arquivo de saída é sempre recriado, e este programa não conhece nem a
 * fila nem o estado: quem junta as duas coisas é o daemon, e só depois de o
 * programa ter terminado bem. Se a cópia do banco vier rasgada — o player
 * pode estar gravando no mesmo instante — algumas linhas chegam a ser
 * escritas antes de a leitura falhar, e é justamente por isso que elas vão
 * para um arquivo descartável em vez de irem direto para a fila.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>   /* strcasecmp */
#include <dirent.h>    /* varrer /proc */
#include <unistd.h>    /* readlink */
#include <time.h>

typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef long long i64;

#define MAX_COLS 64
#define NAME_MAX_LEN 64

/* ------------------------------------------------------------------ */
/* o arquivo inteiro na memória: o banco tem ~500 KB e /tmp é RAM      */
/* ------------------------------------------------------------------ */

typedef struct {
    u8    *base;
    size_t len;
    u32    page_size;
    u32    usable;      /* page_size menos a reserva por página */
    u32    n_pages;
} Db;

static u32 be16(const u8 *p) { return ((u32)p[0] << 8) | p[1]; }
static u32 be32(const u8 *p) {
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
}

/* varint do SQLite: até 9 bytes, big-endian, 7 bits úteis por byte, exceto
 * o nono, que contribui com 8. */
static int varint(const u8 *p, const u8 *fim, u64 *out)
{
    u64 v = 0;
    int i;
    for (i = 0; i < 8; i++) {
        if (p + i >= fim) return 0;
        v = (v << 7) | (p[i] & 0x7f);
        if (!(p[i] & 0x80)) { *out = v; return i + 1; }
    }
    if (p + 8 >= fim) return 0;
    v = (v << 8) | p[8];
    *out = v;
    return 9;
}

static int db_open(Db *db, const char *path)
{
    FILE *f = fopen(path, "rb");
    long tam;
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    tam = ftell(f);
    if (tam < 512) { fclose(f); return 0; }
    rewind(f);
    db->base = (u8 *)malloc((size_t)tam);
    if (!db->base) { fclose(f); return 0; }
    if (fread(db->base, 1, (size_t)tam, f) != (size_t)tam) {
        free(db->base); fclose(f); return 0;
    }
    fclose(f);
    db->len = (size_t)tam;

    if (memcmp(db->base, "SQLite format 3", 16) != 0) { free(db->base); return 0; }
    db->page_size = be16(db->base + 16);
    if (db->page_size == 1) db->page_size = 65536;
    if (db->page_size < 512 || (db->page_size & (db->page_size - 1)))
        { free(db->base); return 0; }
    db->usable = db->page_size - db->base[20];
    if (db->usable < 480) { free(db->base); return 0; }
    db->n_pages = (u32)(db->len / db->page_size);
    return 1;
}

static u8 *page(Db *db, u32 n)   /* páginas contam a partir de 1 */
{
    if (n == 0 || n > db->n_pages) return 0;
    return db->base + (size_t)(n - 1) * db->page_size;
}

/* ------------------------------------------------------------------ */
/* um registro: cabeçalho de tipos seriais + os valores                */
/* ------------------------------------------------------------------ */

typedef struct {
    u8    *buf;        /* o payload já remontado, se houve overflow */
    int    owned;      /* precisa de free? */
    size_t len;
    int    n;
    u64    serial[MAX_COLS];
    size_t off[MAX_COLS];   /* deslocamento do valor dentro de buf */
    size_t size[MAX_COLS];
} Rec;

static size_t serial_size(u64 t)
{
    switch (t) {
    case 0: case 8: case 9: case 10: case 11: return 0;
    case 1: return 1;
    case 2: return 2;
    case 3: return 3;
    case 4: return 4;
    case 5: return 6;
    case 6: case 7: return 8;
    default: return (size_t)((t - 12) / 2);
    }
}

static int rec_parse(Rec *r)
{
    u64 hdr_len = 0;
    int used = varint(r->buf, r->buf + r->len, &hdr_len);
    size_t p, valor;
    if (!used || hdr_len > r->len) return 0;
    p = (size_t)used;
    valor = (size_t)hdr_len;
    r->n = 0;
    while (p < hdr_len && r->n < MAX_COLS) {
        u64 t = 0;
        int k = varint(r->buf + p, r->buf + hdr_len, &t);
        if (!k) return 0;
        p += (size_t)k;
        r->serial[r->n] = t;
        r->off[r->n] = valor;
        r->size[r->n] = serial_size(t);
        if (valor + r->size[r->n] > r->len) return 0;
        valor += r->size[r->n];
        r->n++;
    }
    return 1;
}

static void rec_free(Rec *r) { if (r->owned && r->buf) free(r->buf); r->buf = 0; }

static i64 rec_int(const Rec *r, int i)
{
    const u8 *v;
    u64 t;
    size_t k;
    i64 out = 0;
    if (i < 0 || i >= r->n) return 0;
    t = r->serial[i];
    if (t == 8) return 0;
    if (t == 9) return 1;
    if (t < 1 || t > 6) return 0;
    v = r->buf + r->off[i];
    k = r->size[i];
    if (v[0] & 0x80) out = -1;          /* sinal estendido */
    for (size_t j = 0; j < k; j++) out = (out << 8) | v[j];
    return out;
}

/* Devolve o texto e o tamanho já sem os NULs do fim: o player grava as
 * strings em C incluindo o terminador, então "Again" chega com 6 bytes. */
static const char *rec_text(const Rec *r, int i, size_t *len)
{
    size_t k;
    const char *s;
    *len = 0;
    if (i < 0 || i >= r->n) return "";
    if (r->serial[i] < 13 || (r->serial[i] & 1) == 0) return "";
    s = (const char *)r->buf + r->off[i];
    k = r->size[i];
    while (k > 0 && s[k - 1] == '\0') k--;
    *len = k;
    return s;
}

/* Monta o payload de uma célula, seguindo as páginas de overflow se houver.
 * A conta de quanto cabe na própria página é a da documentação do formato. */
static int cell_payload(Db *db, const u8 *p, const u8 *fim, u64 total, Rec *r)
{
    u32 X = db->usable - 35;
    u32 M, K, local;
    memset(r, 0, sizeof(*r));
    if (total <= X) {
        if (p + total > fim) return 0;
        r->buf = (u8 *)p;
        r->owned = 0;
        r->len = (size_t)total;
        return rec_parse(r);
    }
    M = ((db->usable - 12) * 32 / 255) - 23;
    K = M + (u32)((total - M) % (db->usable - 4));
    local = (K <= X) ? K : M;
    if (p + local + 4 > fim) return 0;

    r->buf = (u8 *)malloc((size_t)total);
    if (!r->buf) return 0;
    r->owned = 1;
    r->len = (size_t)total;
    memcpy(r->buf, p, local);
    {
        size_t feito = local;
        u32 prox = be32(p + local);
        int guarda = 0;
        while (feito < total && prox && guarda++ < 4096) {
            u8 *ov = page(db, prox);
            size_t cabe;
            if (!ov) { rec_free(r); return 0; }
            cabe = db->usable - 4;
            if (cabe > total - feito) cabe = total - feito;
            memcpy(r->buf + feito, ov + 4, cabe);
            feito += cabe;
            prox = be32(ov);
        }
        if (feito != total) { rec_free(r); return 0; }
    }
    return rec_parse(r);
}

/* ------------------------------------------------------------------ */
/* percurso da árvore de uma tabela                                    */
/* ------------------------------------------------------------------ */

typedef int (*RowFn)(void *ctx, i64 rowid, Rec *rec);

static int walk(Db *db, u32 pgno, RowFn fn, void *ctx, int fundo)
{
    u8 *pg = page(db, pgno);
    u32 hdr = (pgno == 1) ? 100 : 0;
    u32 tipo, n, i;
    if (!pg || fundo > 32) return 0;
    tipo = pg[hdr];
    n = be16(pg + hdr + 3);
    if (tipo != 0x0d && tipo != 0x05) return 0;

    for (i = 0; i < n; i++) {
        u32 co = be16(pg + hdr + (tipo == 0x05 ? 12 : 8) + i * 2);
        u8 *c;
        if (co < hdr || co >= db->usable) return 0;
        c = pg + co;
        if (tipo == 0x05) {
            u32 filho = be32(c);
            if (!walk(db, filho, fn, ctx, fundo + 1)) return 0;
        } else {
            u64 tam = 0, rid = 0;
            int a = varint(c, pg + db->usable, &tam);
            int b;
            Rec rec;
            if (!a) return 0;
            b = varint(c + a, pg + db->usable, &rid);
            if (!b) return 0;
            if (!cell_payload(db, c + a + b, pg + db->usable, tam, &rec))
                return 0;
            {
                int r = fn(ctx, (i64)rid, &rec);
                rec_free(&rec);
                if (!r) return 0;
            }
        }
    }
    if (tipo == 0x05) {
        u32 dir = be32(pg + hdr + 8);
        if (dir && !walk(db, dir, fn, ctx, fundo + 1)) return 0;
    }
    return 1;
}

/* ------------------------------------------------------------------ */
/* sqlite_master: achar a raiz da tabela e os nomes das colunas        */
/* ------------------------------------------------------------------ */

typedef struct {
    const char *alvo;
    u32   root;
    char  cols[MAX_COLS][NAME_MAX_LEN];
    int   n_cols;
} Busca;

/* Tira os nomes das colunas de um CREATE TABLE. Não é um parser de SQL: só
 * pega o primeiro identificador de cada item da lista do primeiro nível de
 * parênteses, que é o suficiente para o esquema do HiBy e falha de forma
 * visível se o formato mudar. */
static void cols_from_sql(const char *sql, size_t len, Busca *b)
{
    size_t i = 0;
    int prof = 0, inicio_item = 1;
    b->n_cols = 0;
    while (i < len && sql[i] != '(') i++;
    if (i >= len) return;
    i++; prof = 1;
    while (i < len && prof > 0 && b->n_cols < MAX_COLS) {
        char c = sql[i];
        if (c == '(') { prof++; i++; continue; }
        if (c == ')') { prof--; i++; continue; }
        if (prof == 1 && c == ',') { inicio_item = 1; i++; continue; }
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') { i++; continue; }
        if (prof == 1 && inicio_item) {
            size_t j = 0;
            char aspas = 0;
            if (c == '"' || c == '`' || c == '[') {
                aspas = (c == '[') ? ']' : c;
                i++;
            }
            while (i < len && j < NAME_MAX_LEN - 1) {
                char d = sql[i];
                if (aspas ? (d == aspas)
                          : (d == ' ' || d == ',' || d == '(' || d == ')' ||
                             d == '\t' || d == '\n' || d == '\r'))
                    break;
                b->cols[b->n_cols][j++] = d;
                i++;
            }
            b->cols[b->n_cols][j] = 0;
            /* CONSTRAINT/PRIMARY/UNIQUE etc. no fim da lista não são colunas */
            if (j && strcasecmp(b->cols[b->n_cols], "PRIMARY") &&
                     strcasecmp(b->cols[b->n_cols], "UNIQUE") &&
                     strcasecmp(b->cols[b->n_cols], "CHECK") &&
                     strcasecmp(b->cols[b->n_cols], "FOREIGN") &&
                     strcasecmp(b->cols[b->n_cols], "CONSTRAINT"))
                b->n_cols++;
            inicio_item = 0;
            continue;
        }
        i++;
    }
}

static int on_master(void *ctx, i64 rowid, Rec *rec)
{
    Busca *b = (Busca *)ctx;
    size_t ln = 0, ls = 0;
    const char *nome;
    (void)rowid;
    if (rec->n < 5) return 1;
    nome = rec_text(rec, 1, &ln);        /* name */
    if (ln != strlen(b->alvo) || memcmp(nome, b->alvo, ln) != 0) return 1;
    b->root = (u32)rec_int(rec, 3);      /* rootpage */
    {
        const char *sql = rec_text(rec, 4, &ls);
        cols_from_sql(sql, ls, b);
    }
    return 1;
}

static int col_index(const Busca *b, const char *nome)
{
    for (int i = 0; i < b->n_cols; i++)
        if (!strcasecmp(b->cols[i], nome)) return i;
    return -1;
}

/* ------------------------------------------------------------------ */
/* a coleta                                                            */
/* ------------------------------------------------------------------ */

typedef struct {
    const Busca *cols;
    int i_path, i_name, i_artist, i_album, i_albumartist;
    int i_size, i_bitrate, i_year, i_samplerate;
    i64  desde;
    i64  maior;
    long agora;
    FILE *saida;
    int  novas;
} Coleta;

/* TSV: escapa o que quebraria uma linha ou uma coluna. Títulos de música têm
 * de tudo, então nada é assumido. */
static void put_field(FILE *f, const char *s, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        switch (c) {
        case '\\': fputs("\\\\", f); break;
        case '\t': fputs("\\t", f);  break;
        case '\n': fputs("\\n", f);  break;
        case '\r': fputs("\\r", f);  break;
        default:
            if (c < 0x20) fprintf(f, "\\x%02x", c);
            else fputc(c, f);
        }
    }
}

static void put_col(FILE *f, const Rec *rec, int idx)
{
    size_t n = 0;
    const char *s = (idx >= 0) ? rec_text(rec, idx, &n) : "";
    put_field(f, s, n);
    fputc('\t', f);
}

static int on_row(void *ctx, i64 rowid, Rec *rec)
{
    Coleta *c = (Coleta *)ctx;
    i64 tam, taxa, dur = 0;
    if (rowid > c->maior) c->maior = rowid;
    if (rowid <= c->desde) return 1;

    tam  = (c->i_size    >= 0) ? rec_int(rec, c->i_size)    : 0;
    taxa = (c->i_bitrate >= 0) ? rec_int(rec, c->i_bitrate) : 0;
    if (tam > 0 && taxa > 0) dur = (tam * 8) / taxa;
    if (dur < 0 || dur > 86400) dur = 0;

    fprintf(c->saida, "p1\t%lld\t%ld\t", (long long)rowid, c->agora);
    put_col(c->saida, rec, c->i_artist);
    put_col(c->saida, rec, c->i_name);
    put_col(c->saida, rec, c->i_album);
    put_col(c->saida, rec, c->i_albumartist);
    fprintf(c->saida, "%lld\t%lld\t", (long long)dur,
            (long long)((c->i_year >= 0) ? rec_int(rec, c->i_year) : 0));
    put_col(c->saida, rec, c->i_path);
    fputc('\n', c->saida);
    c->novas++;
    return 1;
}

/* ------------------------------------------------------------------ */
/* buscar uma faixa pelo caminho, para o "tocando agora"               */
/* ------------------------------------------------------------------ */

/* Os caminhos não batem entre as duas pontas: o banco guarda
 * "a:\Músicas\Artista\Faixa.flac" e o sistema de arquivos vê
 * "/usr/data/mnt/sd_0/Músicas/Artista/Faixa.flac". Traduzir um no outro
 * exigiria saber onde o cartão está montado, o que muda.
 *
 * Comparar pelo FIM resolve sem precisar saber nada disso: separadores viram
 * um só, maiúsculas somem, e batem os últimos componentes. Pasta + arquivo
 * já é específico o bastante para não confundir duas faixas.
 */
static void normaliza(const char *s, char *out, size_t lim)
{
    size_t o = 0;
    for (; *s && o + 1 < lim; s++) {
        char c = *s;
        if (c == '\\') c = '/';
        if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
        out[o++] = c;
    }
    out[o] = 0;
}

/* Os últimos `quantos` componentes de um caminho já normalizado. */
static const char *cauda(const char *norm, int quantos)
{
    const char *p = norm + strlen(norm);
    while (p > norm && quantos > 0) {
        p--;
        if (p > norm && *p == '/' && --quantos == 0) return p + 1;
    }
    return norm;
}

/* Um campo por linha, com os caracteres de controle trocados por espaço. */
static void escreve_linha(const char *s, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        fputc(c < 0x20 || c == 0x7f ? ' ' : c, stdout);
    }
    fputc('\n', stdout);
}

typedef struct {
    const Busca *cols;
    int i_path, i_name, i_artist, i_album, i_albumartist;
    int i_size, i_bitrate;
    char alvo[1024];       /* cauda normalizada do que se procura */
    int  achou;
} Acha;

static int on_media(void *ctx, i64 rowid, Rec *rec)
{
    Acha *a = (Acha *)ctx;
    size_t n = 0;
    const char *path;
    char norm[1024];
    (void)rowid;
    if (a->achou) return 1;
    path = rec_text(rec, a->i_path, &n);
    if (!n) return 1;
    {
        char bruto[1024];
        size_t k = n < sizeof(bruto) - 1 ? n : sizeof(bruto) - 1;
        memcpy(bruto, path, k);
        bruto[k] = 0;
        normaliza(bruto, norm, sizeof(norm));
    }
    {
        size_t la = strlen(a->alvo), ln = strlen(norm);
        if (la == 0 || la > ln) return 1;
        if (strcmp(norm + (ln - la), a->alvo) != 0) return 1;
    }
    {
        i64 tam  = (a->i_size    >= 0) ? rec_int(rec, a->i_size)    : 0;
        i64 taxa = (a->i_bitrate >= 0) ? rec_int(rec, a->i_bitrate) : 0;
        i64 dur = (tam > 0 && taxa > 0) ? (tam * 8) / taxa : 0;
        if (dur < 0 || dur > 86400) dur = 0;
        /* Uma linha por campo: o shell lê com `read -r` e nada é
         * interpretado, então título com aspas, acento ou japonês passa
         * intacto. Só os caracteres de controle viram espaço — um título com
         * quebra de linha desalinharia a leitura e faria o álbum virar
         * título. Nenhuma etiqueta legítima tem um. */
        size_t k;
        const char *v;
        v = rec_text(rec, a->i_artist, &k);  escreve_linha(v, k);
        v = rec_text(rec, a->i_name, &k);    escreve_linha(v, k);
        v = rec_text(rec, a->i_album, &k);   escreve_linha(v, k);
        printf("%lld\n", (long long)dur);
        a->achou = 1;
    }
    return 1;
}

static int cmd_buscar(const char *arq_banco, const char *caminho)
{
    Db db;
    Busca b;
    Acha a;
    char norm[1024];

    if (!db_open(&db, arq_banco)) {
        fprintf(stderr, "r1collect: nao consegui ler %s\n", arq_banco);
        return 2;
    }
    memset(&b, 0, sizeof(b));
    /* MEDIA_TABLE tem a biblioteca inteira, preenchida na varredura — ela
     * conhece a faixa antes de ela tocar, ao contrário do HISTORY_TABLE. */
    b.alvo = "MEDIA_TABLE";
    if (!walk(&db, 1, on_master, &b, 0) || !b.root || !b.n_cols) {
        fprintf(stderr, "r1collect: MEDIA_TABLE nao encontrada\n");
        free(db.base);
        return 2;
    }
    memset(&a, 0, sizeof(a));
    a.cols = &b;
    a.i_path        = col_index(&b, "path");
    a.i_name        = col_index(&b, "name");
    a.i_artist      = col_index(&b, "artist");
    a.i_album       = col_index(&b, "album");
    a.i_albumartist = col_index(&b, "album_artist");
    a.i_size        = col_index(&b, "size");
    a.i_bitrate     = col_index(&b, "bit_rate");
    if (a.i_path < 0 || a.i_name < 0 || a.i_artist < 0) {
        fprintf(stderr, "r1collect: esquema inesperado em MEDIA_TABLE\n");
        free(db.base);
        return 2;
    }
    normaliza(caminho, norm, sizeof(norm));
    snprintf(a.alvo, sizeof(a.alvo), "%s", cauda(norm, 2));

    if (!walk(&db, b.root, on_media, &a, 0)) {
        fprintf(stderr, "r1collect: arvore ilegivel\n");
        free(db.base);
        return 2;
    }
    free(db.base);
    if (!a.achou) {
        fprintf(stderr, "r1collect: nao achei %s na biblioteca\n", a.alvo);
        return 3;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* que arquivo o player está tocando agora                             */
/* ------------------------------------------------------------------ */

static int e_audio(const char *s)
{
    static const char *ext[] = {".flac", ".mp3", ".wav", ".m4a", ".ape",
                                ".ogg", ".dsf", ".dff", ".wv", ".aac",
                                ".opus", ".alac", ".aiff", ".aif", 0};
    size_t n = strlen(s);
    for (int i = 0; ext[i]; i++) {
        size_t k = strlen(ext[i]);
        if (n > k && !strcasecmp(s + (n - k), ext[i])) return 1;
    }
    return 0;
}

/* O arquivo de áudio que este processo tem aberto, se houver. */
static int audio_de(const char *pid, char *out, size_t lim)
{
    char dir[64];
    DIR *d;
    struct dirent *e;
    int achou = 0;
    snprintf(dir, sizeof(dir), "/proc/%s/fd", pid);
    d = opendir(dir);
    if (!d) return 0;
    while (!achou && (e = readdir(d)) != 0) {
        char link[80], alvo[1024];
        ssize_t n;
        if (e->d_name[0] == '.') continue;
        snprintf(link, sizeof(link), "%s/%s", dir, e->d_name);
        n = readlink(link, alvo, sizeof(alvo) - 1);
        if (n <= 0) continue;
        alvo[n] = 0;
        if (e_audio(alvo)) {
            snprintf(out, lim, "%s", alvo);
            achou = 1;
        }
    }
    closedir(d);
    return achou;
}

/* Este processo é o player?  O nome em /proc/N/comm é o da *thread*
 * ("system_main_thr" no R1), então quem responde é a linha de comando. */
static int e_player(const char *pid)
{
    char caminho[64], buf[512];
    FILE *fh;
    size_t n;
    snprintf(caminho, sizeof(caminho), "/proc/%s/cmdline", pid);
    fh = fopen(caminho, "rb");
    if (!fh) return 0;
    n = fread(buf, 1, sizeof(buf) - 1, fh);
    fclose(fh);
    buf[n] = 0;
    /* cmdline separa os argumentos por NUL; argv[0] basta. */
    return strstr(buf, "hiby_player") != 0;
}

/* Imprime o caminho do que está tocando. Sem tocar no banco: isto roda a
 * cada ciclo do laço, e abrir 500 kB de SQLite para nada seria desperdício.
 * Saída 0 com o caminho, 3 quando não há nada tocando. */
static int cmd_tocando(void)
{
    DIR *d = opendir("/proc");
    struct dirent *e;
    char achado[1024] = "";
    char reserva[1024] = "";
    if (!d) return 2;
    while ((e = readdir(d)) != 0) {
        if (e->d_name[0] < '0' || e->d_name[0] > '9') continue;
        if (e_player(e->d_name)) {
            if (audio_de(e->d_name, achado, sizeof(achado))) break;
        } else if (!reserva[0]) {
            /* Se o player mudar de nome numa versão futura, qualquer
             * processo com um arquivo de áudio aberto ainda serve. */
            audio_de(e->d_name, reserva, sizeof(reserva));
        }
    }
    closedir(d);
    if (!achado[0] && reserva[0]) snprintf(achado, sizeof(achado), "%s", reserva);
    if (!achado[0]) return 3;
    printf("%s\n", achado);
    return 0;
}

/* ------------------------------------------------------------------ */
/* o Tidal                                                             */
/* ------------------------------------------------------------------ */

/* O Tidal não passa pelo banco.
 *
 * O HISTORY_TABLE é o histórico de mídia *local*: uma faixa transmitida pelo
 * Tidal nunca entra ali, e o arquivo de áudio que o "tocando agora" procura
 * em /proc/PID/fd também não existe — é um socket. Por isso o scrobbler
 * simplesmente não via o Tidal.
 *
 * O que o player deixa é o id numérico da faixa, em UTF-16LE, no começo do
 * /usr/data/user.ini. Verificado no aparelho: tocando três faixas seguidas,
 * os ÚNICOS bytes que mudaram no arquivo foram os desse campo, e o caminho da
 * última faixa local ao lado dele ficou intacto.
 *
 * Com o id, a API do Tidal devolve artista, título, álbum e duração — e o
 * token para perguntar está no próprio aparelho, em /usr/data/tat.
 */
#define TIDAL_INI   "/usr/data/user.ini"
#define TIDAL_OFF   40      /* onde o campo mora neste firmware */
#define TIDAL_MAX   12      /* ids têm 9 dígitos; 12 é folga */

/* Lê `n` caracteres UTF-16LE a partir de `off`, aceitando só dígitos.
 * Devolve o tamanho, ou 0 se não parecer um id. */
static size_t le_id_u16(const unsigned char *b, size_t tam, size_t off,
                        char *out, size_t lim)
{
    size_t o = 0, i;
    for (i = off; i + 1 < tam && o + 1 < lim && o < TIDAL_MAX; i += 2) {
        unsigned cp = (unsigned)b[i] | ((unsigned)b[i + 1] << 8);
        if (cp == 0) break;                  /* fim da string */
        if (cp < '0' || cp > '9') return 0;   /* não é um id */
        out[o++] = (char)cp;
    }
    out[o] = 0;
    /* Um id do Tidal tem uns 9 dígitos. Menos de 5 é ruído. */
    return o >= 5 ? o : 0;
}

/* Imprime o id da faixa do Tidal, ou nada.
 *
 * O deslocamento fixo é o caminho rápido; se ele não render um id — outra
 * versão de firmware, outro layout —, o começo do arquivo é varrido à
 * procura da primeira sequência que pareça um. Ficar preso a um número
 * mágico seria trocar "não funciona" por "funciona só neste aparelho".
 */
static int cmd_tidal(void)
{
    FILE *fh = fopen(TIDAL_INI, "rb");
    unsigned char buf[512];
    char id[TIDAL_MAX + 1];
    size_t n, i;
    if (!fh) return 3;
    n = fread(buf, 1, sizeof(buf), fh);
    fclose(fh);
    if (n < TIDAL_OFF + 12) return 3;

    if (le_id_u16(buf, n, TIDAL_OFF, id, sizeof(id))) {
        printf("%s\n", id);
        return 0;
    }
    for (i = 0; i + 12 < n; i += 2) {
        if (le_id_u16(buf, n, i, id, sizeof(id))) {
            printf("%s\n", id);
            return 0;
        }
    }
    return 3;
}

/* O estado da reprodução, numa varredura só de /proc.
 *
 * Duas perguntas que o daemon precisa fazer a cada volta, e que juntas custam
 * o mesmo que uma:
 *
 *   pcm=1     o player abre /dev/snd/pcmC0D0p enquanto toca e o fecha quando
 *             para — conferido no aparelho, com e sem música
 *   local=…   o arquivo de áudio aberto, quando é mídia local
 *
 * Separar os dois é o que impede um erro concreto: o id do Tidal no user.ini
 * NÃO é apagado quando você volta a ouvir arquivos locais. Sem saber que o
 * que toca agora é local, o daemon veria aquele id parado e registraria uma
 * faixa do Tidal que ninguém ouviu. Tidal tocando é "pcm aberto E nenhum
 * arquivo de áudio aberto" — porque streaming é socket, não arquivo.
 */
static int cmd_estado(void)
{
    DIR *d = opendir("/proc");
    struct dirent *e;
    int pcm = 0;
    char local[1024] = "";
    /* A mesma reserva do `tocando`: se o player mudar de nome numa versão
     * futura do firmware, qualquer processo com um arquivo de áudio aberto
     * ainda serve. Sem isto o "tocando agora" pararia de funcionar numa
     * atualização de firmware sem nenhum aviso. */
    char reserva[1024] = "";
    if (!d) return 2;
    while ((e = readdir(d)) != 0) {
        char dir[64];
        DIR *fd;
        struct dirent *f;
        int player;
        if (e->d_name[0] < '0' || e->d_name[0] > '9') continue;
        player = e_player(e->d_name);
        if (!player && (reserva[0] || local[0])) continue;
        snprintf(dir, sizeof(dir), "/proc/%s/fd", e->d_name);
        fd = opendir(dir);
        if (!fd) continue;
        while ((f = readdir(fd)) != 0) {
            char link[80], alvo[1024];
            ssize_t k;
            if (f->d_name[0] == '.') continue;
            snprintf(link, sizeof(link), "%s/%s", dir, f->d_name);
            k = readlink(link, alvo, sizeof(alvo) - 1);
            if (k <= 0) continue;
            alvo[k] = 0;
            if (player && strstr(alvo, "/dev/snd/pcm")) pcm = 1;
            else if (e_audio(alvo)) {
                if (player) {
                    if (!local[0]) snprintf(local, sizeof(local), "%s", alvo);
                } else if (!reserva[0]) {
                    snprintf(reserva, sizeof(reserva), "%s", alvo);
                }
            }
        }
        closedir(fd);
        if (pcm && local[0]) break;
    }
    closedir(d);
    if (!local[0] && reserva[0]) snprintf(local, sizeof(local), "%s", reserva);
    printf("pcm=%d\n", pcm);
    escreve_linha(local, strlen(local));
    return 0;
}

int main(int argc, char **argv)
{
    Db db;
    Busca b;
    Coleta c;
    const char *banco, *saida;
    i64 desde = 0;

    /* r1collect tocando */
    if (argc == 2 && !strcmp(argv[1], "tocando"))
        return cmd_tocando();

    /* r1collect tidal — o id da faixa do Tidal em reprodução */
    if (argc == 2 && !strcmp(argv[1], "tidal"))
        return cmd_tidal();

    /* r1collect estado — pcm aberto? e qual arquivo local, se houver */
    if (argc == 2 && !strcmp(argv[1], "estado"))
        return cmd_estado();

    /* r1collect buscar <banco> <caminho-do-arquivo-tocando> */
    if (argc == 4 && !strcmp(argv[1], "buscar"))
        return cmd_buscar(argv[2], argv[3]);

    if (argc != 4) {
        fprintf(stderr, "uso: %s <banco> <ultimo-rowid> <saida>\n"
                        "     %s buscar <banco> <caminho>\n",
                argv[0], argv[0]);
        return 1;
    }
    banco = argv[1];
    desde = (i64)strtoll(argv[2], 0, 10);
    if (desde < 0) desde = 0;
    saida = argv[3];

    if (!db_open(&db, banco)) {
        fprintf(stderr, "r1collect: nao consegui ler %s\n", banco);
        return 2;
    }

    memset(&b, 0, sizeof(b));
    b.alvo = "HISTORY_TABLE";
    if (!walk(&db, 1, on_master, &b, 0) || !b.root || !b.n_cols) {
        fprintf(stderr, "r1collect: HISTORY_TABLE nao encontrada\n");
        free(db.base);
        return 2;
    }

    memset(&c, 0, sizeof(c));
    c.cols = &b;
    c.i_path        = col_index(&b, "path");
    c.i_name        = col_index(&b, "name");
    c.i_artist      = col_index(&b, "artist");
    c.i_album       = col_index(&b, "album");
    c.i_albumartist = col_index(&b, "album_artist");
    c.i_size        = col_index(&b, "size");
    c.i_bitrate     = col_index(&b, "bit_rate");
    c.i_samplerate  = col_index(&b, "sample_rate");
    c.i_year        = col_index(&b, "year");
    if (c.i_name < 0 || c.i_artist < 0) {
        fprintf(stderr, "r1collect: esquema inesperado (sem name/artist)\n");
        free(db.base);
        return 2;
    }
    c.desde = desde;
    c.maior = desde;
    c.agora = (long)time(0);

    c.saida = fopen(saida, "w");
    if (!c.saida) {
        fprintf(stderr, "r1collect: nao consegui abrir %s\n", saida);
        free(db.base);
        return 2;
    }
    if (!walk(&db, b.root, on_row, &c, 0)) {
        fprintf(stderr, "r1collect: arvore ilegivel\n");
        fclose(c.saida);
        free(db.base);
        return 2;
    }
    if (fflush(c.saida) != 0 || fclose(c.saida) != 0) {
        fprintf(stderr, "r1collect: falha ao gravar %s\n", saida);
        free(db.base);
        return 2;
    }

    printf("%d %lld\n", c.novas, (long long)c.maior);
    free(db.base);
    return 0;
}
