#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cert_dir="${OTA_TLS_CERT_DIR:-docker/tls}"
ca_key_file="${cert_dir}/demo-ca.key"
ca_cert_file="${cert_dir}/demo-ca.crt"
ca_conf_file="${cert_dir}/demo-ca.cnf"
cert_file="${cert_dir}/ota-server.crt"
key_file="${cert_dir}/ota-server.key"
csr_file="${cert_dir}/ota-server.csr"
ext_file="${cert_dir}/ota-server.ext"

mkdir -p "${cert_dir}"

openssl_log="$(mktemp)"
cat >"${ca_conf_file}" <<'EOF'
[req]
prompt = no
distinguished_name = req_distinguished_name
x509_extensions = v3_ca

[req_distinguished_name]
CN = Virtual OTA Demo CA

[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF

if ! openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "${ca_key_file}" \
    -out "${ca_cert_file}" \
    -sha256 \
    -days 3650 \
    -config "${ca_conf_file}" 2>"${openssl_log}"; then
    cat "${openssl_log}" >&2
    rm -f "${openssl_log}"
    exit 1
fi

cat >"${ext_file}" <<'EOF'
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1,DNS:localhost
EOF

if ! openssl req -new -newkey rsa:2048 -nodes \
    -keyout "${key_file}" \
    -out "${csr_file}" \
    -subj "/CN=127.0.0.1" 2>"${openssl_log}"; then
    cat "${openssl_log}" >&2
    rm -f "${openssl_log}"
    exit 1
fi

if ! openssl x509 -req \
    -in "${csr_file}" \
    -CA "${ca_cert_file}" \
    -CAkey "${ca_key_file}" \
    -CAcreateserial \
    -out "${cert_file}" \
    -days 365 \
    -sha256 \
    -extfile "${ext_file}" 2>"${openssl_log}"; then
    cat "${openssl_log}" >&2
    rm -f "${openssl_log}"
    exit 1
fi
rm -f "${openssl_log}"

rm -f "${csr_file}"
rm -f "${ca_conf_file}"
chmod 600 "${key_file}"
chmod 600 "${ca_key_file}"
chmod 644 "${cert_file}"
chmod 644 "${ca_cert_file}"

echo "Generated demo TLS certificate:"
echo "  OTA_TLS_CA_FILE=${ca_cert_file}"
echo "  OTA_TLS_CERT_FILE=${cert_file}"
echo "  OTA_TLS_KEY_FILE=${key_file}"
