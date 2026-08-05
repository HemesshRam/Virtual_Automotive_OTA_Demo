#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

runtime="both"
tcu_mode="both"
transport="both"
require_free_ports=0
auto_vcan=0

usage() {
    cat <<'EOF'
Usage: bash scripts/preflight_ubuntu.sh [options]

Options:
  --runtime <python|docker|both>       Runtime mode to validate (default: both)
  --tcu <mender|non-mender|both>       TCU mode to validate (default: both)
  --transport <vcan|doip|both>         Transport to validate (default: both)
  --auto-vcan                          Automatically run setup_vcan_zones.sh when VCAN is requested
  --require-free-ports                 Fail if demo ports are already listening
  -h, --help                           Show this help
EOF
}

while (($#)); do
    case "$1" in
        --runtime)
            runtime="${2:?missing value for --runtime}"
            shift 2
            ;;
        --tcu)
            tcu_mode="${2:?missing value for --tcu}"
            shift 2
            ;;
        --transport)
            transport="${2:?missing value for --transport}"
            shift 2
            ;;
        --auto-vcan)
            auto_vcan=1
            shift
            ;;
        --require-free-ports)
            require_free_ports=1
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

case "$runtime" in
    python|docker|both) ;;
    *)
        echo "[FAIL] --runtime must be python, docker, or both" >&2
        exit 2
        ;;
esac

case "$tcu_mode" in
    mender|non-mender|both) ;;
    *)
        echo "[FAIL] --tcu must be mender, non-mender, or both" >&2
        exit 2
        ;;
esac

case "$transport" in
    vcan|doip|both) ;;
    *)
        echo "[FAIL] --transport must be vcan, doip, or both" >&2
        exit 2
        ;;
esac

fails=0
warns=0

pass() { echo "[OK] $*"; }
warn() { echo "[WARN] $*"; warns=$((warns + 1)); }
fail() { echo "[FAIL] $*"; fails=$((fails + 1)); }

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

version_ge() {
    local current="$1"
    local minimum="$2"
    local current_major="${current%%.*}"
    local current_minor="${current#*.}"
    current_minor="${current_minor%%.*}"
    local min_major="${minimum%%.*}"
    local min_minor="${minimum#*.}"
    min_minor="${min_minor%%.*}"

    if (( current_major > min_major )); then
        return 0
    fi
    if (( current_major < min_major )); then
        return 1
    fi
    (( current_minor >= min_minor ))
}

check_binary() {
    local binary="$1"
    local package_hint="${2:-$1}"
    if have_cmd "$binary"; then
        pass "Command available: $binary"
    else
        fail "Missing command: $binary (install package: $package_hint)"
    fi
}

check_port() {
    local port="$1"
    local label="$2"
    if ! have_cmd ss; then
        warn "ss not available, skipping port check for ${label} (${port})"
        return
    fi

    local output
    output="$(ss -ltn "( sport = :${port} )" 2>/dev/null | tail -n +2 || true)"
    if [[ -n "$output" ]]; then
        if (( require_free_ports == 1 )); then
            fail "Port ${port} already in use for ${label}"
        else
            warn "Port ${port} already in use for ${label}"
        fi
    else
        pass "Port ${port} is available for ${label}"
    fi
}

interface_is_up() {
    local iface="$1"
    ip link show "$iface" >/dev/null 2>&1
}

echo
echo "============================================================"
echo "UBUNTU PREFLIGHT"
echo "============================================================"
echo "Project root : ${PROJECT_ROOT}"
echo "Runtime      : ${runtime}"
echo "TCU mode     : ${tcu_mode}"
echo "Transport    : ${transport}"
echo "Auto VCAN    : ${auto_vcan}"
echo "============================================================"

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ "${ID:-}" == "ubuntu" ]]; then
        if version_ge "${VERSION_ID:-0.0}" "22.04"; then
            pass "Ubuntu version supported: ${VERSION_ID}"
        else
            fail "Ubuntu ${VERSION_ID:-unknown} is below the supported baseline of 22.04"
        fi
    else
        warn "Detected distro '${ID:-unknown}', not Ubuntu"
    fi
else
    warn "/etc/os-release not found, skipping distro check"
fi

check_binary python3 python3
if have_cmd python3; then
    py_version="$(python3 - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
    if version_ge "$py_version" "3.10"; then
        pass "Python version supported: ${py_version}"
    else
        fail "Python ${py_version} is below the supported baseline of 3.10"
    fi
fi

if have_cmd python; then
    pass "python command is available"
else
    warn "python command not found; prefer python3 in customer commands"
fi

check_binary pip3 python3-pip
check_binary ip iproute2
check_binary openssl openssl
check_binary curl curl

if [[ "$runtime" == "docker" || "$runtime" == "both" ]]; then
    check_binary docker docker.io
    if have_cmd docker; then
        if docker info >/dev/null 2>&1; then
            pass "Docker daemon is reachable"
        else
            fail "Docker daemon is not reachable"
        fi
    fi

    if docker compose version >/dev/null 2>&1; then
        pass "docker compose is available"
    else
        fail "docker compose is not available (install docker-compose-plugin)"
    fi
fi

check_binary mosquitto mosquitto

if [[ "$transport" == "vcan" || "$transport" == "both" ]]; then
    if have_cmd modprobe; then
        if modprobe -n vcan >/dev/null 2>&1; then
            pass "vcan kernel module is available"
        else
            fail "vcan kernel module is not available on this host"
        fi
    else
        fail "modprobe command not available"
    fi

    if (( auto_vcan == 1 )); then
        if sudo ./scripts/setup_vcan_zones.sh >/dev/null; then
            pass "VCAN interfaces ensured via scripts/setup_vcan_zones.sh"
        else
            fail "Unable to auto-create VCAN interfaces via scripts/setup_vcan_zones.sh"
        fi
    fi

    for iface in vcan_gate vcan_bcm vcan_clus; do
        if interface_is_up "$iface"; then
            pass "VCAN interface is up: $iface"
        else
            warn "VCAN interface not up: $iface"
        fi
    done
fi

if [[ "$tcu_mode" == "mender" || "$tcu_mode" == "both" ]]; then
    if have_cmd systemctl; then
        pass "systemd is available"
    else
        fail "systemctl not available; Mender demo mode requires systemd"
    fi

    if have_cmd mender-update && have_cmd mender-auth; then
        pass "Mender client commands are available"
    else
        warn "Mender client commands not found; Mender demo mode requires mender-client4"
    fi
fi

tls_cert="${PROJECT_ROOT}/docker/tls/ota-server.crt"
tls_key="${PROJECT_ROOT}/docker/tls/ota-server.key"
if [[ -f "$tls_cert" && -f "$tls_key" ]]; then
    pass "TLS certificate files are present"
else
    warn "TLS certificate files are missing; run bash scripts/generate_demo_tls_cert.sh"
fi

check_port 1883 "MQTT broker"
check_port 8080 "OTA HTTPS server"
if [[ "$transport" == "doip" || "$transport" == "both" ]]; then
    check_port 13400 "DoIP gateway"
fi

echo
echo "============================================================"
if (( fails > 0 )); then
    echo "PREFLIGHT RESULT : FAILED (${fails} failures, ${warns} warnings)"
    echo "============================================================"
    exit 1
fi

if (( warns > 0 )); then
    echo "PREFLIGHT RESULT : PASS WITH WARNINGS (${warns})"
else
    echo "PREFLIGHT RESULT : PASS"
fi
echo "============================================================"
