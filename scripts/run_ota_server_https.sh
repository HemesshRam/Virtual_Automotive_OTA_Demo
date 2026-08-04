#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

cert_file="${OTA_TLS_CERT_FILE:-docker/tls/ota-server.crt}"
key_file="${OTA_TLS_KEY_FILE:-docker/tls/ota-server.key}"

if [[ ! -f "${cert_file}" || ! -f "${key_file}" ]]; then
    bash scripts/generate_demo_tls_cert.sh
fi

export OTA_HTTPS_ENABLED=1
export OTA_TLS_CERT_FILE="${cert_file}"
export OTA_TLS_KEY_FILE="${key_file}"
export OTA_PUBLIC_BASE_URL="${OTA_PUBLIC_BASE_URL:-https://127.0.0.1:8080}"

python -m ota_server.app
