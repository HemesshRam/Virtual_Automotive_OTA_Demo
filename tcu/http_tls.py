import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from common.demo_logging import verbose_enabled

try:
    import urllib3
except ImportError:
    urllib3 = None

DEMO_CA_FILE = Path("docker/tls/demo-ca.crt")
_FALLBACK_NOTICE_SHOWN: set[str] = set()


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


def is_local_demo_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.hostname in {"127.0.0.1", "localhost"}


def request_with_demo_tls_fallback(method: str, url: str, *, verify, **kwargs):
    try:
        return requests.request(method, url, verify=verify, **kwargs)
    except requests.exceptions.SSLError:
        if verify is False or not is_local_demo_url(url):
            raise
        if urllib3 is not None:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if url not in _FALLBACK_NOTICE_SHOWN and verbose_enabled():
            print(f"[TLS] Local demo certificate verification failed for {url}; retrying insecurely")
            _FALLBACK_NOTICE_SHOWN.add(url)
        return requests.request(method, url, verify=False, **kwargs)
