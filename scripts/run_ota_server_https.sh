#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cert_file="${OTA_TLS_CERT_FILE:-docker/tls/ota-server.crt}"
key_file="${OTA_TLS_KEY_FILE:-docker/tls/ota-server.key}"
ca_cert_file="$(dirname "${cert_file}")/demo-ca.crt"

needs_regen=0
if [[ ! -f "${cert_file}" || ! -f "${key_file}" || ! -f "${ca_cert_file}" ]]; then
    needs_regen=1
elif ! openssl x509 -in "${ca_cert_file}" -noout -text | grep -q "Key Usage"; then
    needs_regen=1
fi

if [[ "${needs_regen}" -eq 1 ]]; then
    bash scripts/generate_demo_tls_cert.sh
fi

export OTA_HTTPS_ENABLED=1
export OTA_TLS_CERT_FILE="${cert_file}"
export OTA_TLS_KEY_FILE="${key_file}"
export OTA_PUBLIC_BASE_URL="${OTA_PUBLIC_BASE_URL:-https://127.0.0.1:8080}"

python -m ota_server.app
