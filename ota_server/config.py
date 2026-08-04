import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TLS_CERT_FILE = PROJECT_ROOT / "docker" / "tls" / "ota-server.crt"
DEFAULT_TLS_KEY_FILE = PROJECT_ROOT / "docker" / "tls" / "ota-server.key"

HOST = os.getenv("OTA_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("OTA_SERVER_PORT", "8080"))
DEFAULT_HTTPS_ENABLED = (
    "1"
    if DEFAULT_TLS_CERT_FILE.exists() and DEFAULT_TLS_KEY_FILE.exists()
    else "0"
)
HTTPS_ENABLED = os.getenv("OTA_HTTPS_ENABLED", DEFAULT_HTTPS_ENABLED).lower() in {
    "1",
    "true",
    "yes",
}
TLS_CERT_FILE = os.getenv("OTA_TLS_CERT_FILE", str(DEFAULT_TLS_CERT_FILE))
TLS_KEY_FILE = os.getenv("OTA_TLS_KEY_FILE", str(DEFAULT_TLS_KEY_FILE))
PUBLIC_SCHEME = "https" if HTTPS_ENABLED else "http"

CAMPAIGN_FOLDER = PROJECT_ROOT / "campaigns"

FIRMWARE_FOLDER = PROJECT_ROOT / "firmware" / "releases" / "2.0.0"
