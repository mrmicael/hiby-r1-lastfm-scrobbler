#!/bin/bash
# Compila o r1net — o ajudante de rede residente — para o R1.
#
# Ele é o único programa do projeto que precisa de uma biblioteca de fora, e é
# por isso que tem um script só dele em vez de entrar no botão "Build" junto
# com os outros dois: baixar e compilar o mbedTLS leva alguns minutos e pede
# rede, o que não cabe num botão que a pessoa clica esperando resposta.
#
# O binário pronto está em bin/r1net, como os outros. Isto aqui é para quem
# quiser refazer.
#
# Precisa de: git, e o Zig em algum lugar do PATH.
#   https://ziglang.org/download/
set -e

ALVO=${ALVO:-mipsel-linux-musleabihf}
VERSAO_MBEDTLS=v3.6.2
AQUI=$(cd "$(dirname "$0")" && pwd)
W=${W:-$HOME/.cache/r1lastfm/mbedtls-build}
M=$W/mbedtls

command -v zig >/dev/null || {
    echo "zig não está no PATH. Baixe em https://ziglang.org/download/" >&2
    exit 1
}

mkdir -p "$W"
if [ ! -d "$M/library" ]; then
    echo "baixando o mbedTLS $VERSAO_MBEDTLS..."
    git clone --depth 1 --branch "$VERSAO_MBEDTLS" \
        https://github.com/Mbed-TLS/mbedtls.git "$M"
fi

# A configuração do mbedTLS: cliente TLS 1.2 e mais nada.
#
# Sem TLS 1.3 de propósito. No mbedTLS 3.x ele roda sobre o PSA, e o PSA numa
# configuração enxuta sobe sem algoritmo nenhum — todo handshake morre com
# "internal error" e a única pista fica no log de depuração da biblioteca. O
# ws.audioscrobbler.com e o api.tidal.com falam 1.2, então o custo é nenhum, e
# o que se ganha é menos código num aparelho com 56 MB de RAM.
#
# Este arquivo é reescrito a cada compilação, de propósito: uma configuração
# fantasma de uma tentativa anterior custou horas de diagnóstico.
cat > "$W/config.h" <<'FIM'
#ifndef R1_MBEDTLS_CONFIG_H
#define R1_MBEDTLS_CONFIG_H

#define MBEDTLS_HAVE_TIME
#define MBEDTLS_HAVE_TIME_DATE
#define MBEDTLS_PLATFORM_C
#define MBEDTLS_FS_IO

#define MBEDTLS_ENTROPY_C
#define MBEDTLS_CTR_DRBG_C
#define MBEDTLS_AES_C
#define MBEDTLS_CIPHER_C
#define MBEDTLS_MD_C

#define MBEDTLS_SHA224_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_SHA384_C
#define MBEDTLS_SHA512_C
#define MBEDTLS_SHA1_C

#define MBEDTLS_BIGNUM_C
#define MBEDTLS_RSA_C
#define MBEDTLS_PKCS1_V15
#define MBEDTLS_PKCS1_V21
#define MBEDTLS_OID_C
#define MBEDTLS_PK_C
#define MBEDTLS_PK_PARSE_C
#define MBEDTLS_ASN1_PARSE_C
#define MBEDTLS_ASN1_WRITE_C
#define MBEDTLS_ECP_C
#define MBEDTLS_ECDSA_C
#define MBEDTLS_ECDH_C
#define MBEDTLS_ECDSA_DETERMINISTIC
#define MBEDTLS_HMAC_DRBG_C
#define MBEDTLS_ECP_DP_SECP256R1_ENABLED
#define MBEDTLS_ECP_DP_SECP384R1_ENABLED

#define MBEDTLS_BASE64_C
#define MBEDTLS_PEM_PARSE_C
#define MBEDTLS_X509_USE_C
#define MBEDTLS_X509_CRT_PARSE_C

#define MBEDTLS_GCM_C

#define MBEDTLS_SSL_TLS_C
#define MBEDTLS_SSL_CLI_C
#define MBEDTLS_SSL_PROTO_TLS1_2
#define MBEDTLS_SSL_SERVER_NAME_INDICATION
#define MBEDTLS_SSL_KEEP_PEER_CERTIFICATE
#define MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
#define MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED

#define MBEDTLS_NET_C

/* O buffer de SAÍDA pode ser pequeno: nossos pedidos são curtos. O de ENTRADA
 * fica no máximo do TLS, porque um servidor pode mandar um registro inteiro e
 * cortar aqui quebraria a conexão. */
#define MBEDTLS_SSL_OUT_CONTENT_LEN 4096
#define MBEDTLS_SSL_IN_CONTENT_LEN  16384

#define MBEDTLS_ERROR_C
/* Fica compilado, mas só liga com R1NET_DEBUG no ambiente. Quando um
 * handshake falha, "internal error" não diz nada e adivinhar sai caro. */
#define MBEDTLS_DEBUG_C

#endif
FIM

OBJ=$W/obj-$ALVO
mkdir -p "$OBJ"
echo "compilando o mbedTLS para $ALVO ($(ls $M/library/*.c | wc -l) arquivos)..."
for f in "$M"/library/*.c; do
    o="$OBJ/$(basename "${f%.c}").o"
    [ -f "$o" ] && [ "$o" -nt "$f" ] && [ "$o" -nt "$W/config.h" ] && continue
    zig cc -target "$ALVO" -Os -c -o "$o" "$f" \
        -I"$M/include" -I"$M/library" -I"$W" \
        -DMBEDTLS_CONFIG_FILE='"config.h"' -Wno-everything
done
zig ar rcs "$W/libmbedtls-$ALVO.a" "$OBJ"/*.o

echo "compilando o r1net..."
zig cc -target "$ALVO" -Os -static -Wall -Wextra \
    -o "$W/r1net" "$AQUI/r1net.c" \
    -I"$M/include" -I"$M/library" -I"$W" \
    -DMBEDTLS_CONFIG_FILE='"config.h"' \
    "$W/libmbedtls-$ALVO.a"

echo
echo "pronto: $W/r1net"
stat -c '  %s bytes' "$W/r1net"
command -v readelf >/dev/null && \
    readelf -h "$W/r1net" | grep -E 'Class|Data|Machine' | sed 's/^/  /'
command -v sha256sum >/dev/null && sha256sum "$W/r1net" | sed 's/^/  /'
echo
echo "para instalar no lugar do que vem pronto:"
echo "  cp $W/r1net $AQUI/bin/r1net"
