#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

with_mender=0
skip_apt=0

usage() {
    cat <<'EOF'
Usage: bash bootstrap.sh [options]

Options:
  --with-mender    Also try to install the Mender client package
  --skip-apt       Skip apt package installation and only prepare the repo
  -h, --help       Show this help
EOF
}

while (($#)); do
    case "$1" in
        --with-mender)
            with_mender=1
            shift
            ;;
        --skip-apt)
            skip_apt=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[FAIL] Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

echo
echo "============================================================"
echo "VIRTUAL OTA BOOTSTRAP"
echo "============================================================"
echo "Project root : ${PROJECT_ROOT}"
echo "With Mender  : ${with_mender}"
echo "Skip apt     : ${skip_apt}"
echo "============================================================"

if (( skip_apt == 0 )); then
    sudo apt update

    packages=(
        python3
        python3-venv
        python3-pip
        python3-dev
        python-is-python3
        iproute2
        iputils-ping
        can-utils
        mosquitto
        openssl
        curl
    )

    sudo apt install -y "${packages[@]}"

    if command -v docker >/dev/null 2>&1; then
        echo "[OK] Docker command already present; skipping docker engine package install"
    else
        sudo apt install -y docker.io
    fi

    if docker compose version >/dev/null 2>&1; then
        echo "[OK] docker compose already present; skipping compose plugin install"
    else
        sudo apt install -y docker-compose-plugin
    fi

    if (( with_mender == 1 )); then
        if apt-cache policy mender-client4 >/dev/null 2>&1; then
            if sudo apt install -y mender-client4; then
                echo "[OK] Installed mender-client4"
            else
                echo "[WARN] mender-client4 install failed; configure the Mender APT repository and retry"
            fi
        else
            echo "[WARN] mender-client4 package not available in current APT sources"
            echo "[WARN] Add the Mender repository, then rerun: bash bootstrap.sh --with-mender"
        fi
    fi
fi

cd "${PROJECT_ROOT}"

if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

mkdir -p runtime logs tcu/state ota_server/state

if [[ ! -f docker/tls/ota-server.crt || ! -f docker/tls/ota-server.key ]]; then
    bash scripts/generate_demo_tls_cert.sh
fi

echo
echo "============================================================"
echo "BOOTSTRAP COMPLETE"
echo "============================================================"
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  bash scripts/preflight_ubuntu.sh --runtime both --tcu both --transport both"
echo "============================================================"
