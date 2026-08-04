import os
from pathlib import Path

try:
    import urllib3
except ImportError:
    urllib3 = None

DEMO_CA_FILE = Path("docker/tls/demo-ca.crt")


def requests_verify_setting():
    configured = os.getenv("OTA_TLS_VERIFY")
    if configured is None and DEMO_CA_FILE.exists():
        return str(DEMO_CA_FILE)

    value = (configured or "1").strip()
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    return value


def suppress_unverified_https_warning_if_needed() -> None:
    if requests_verify_setting() is not False:
        return
    if urllib3 is None:
        return
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
