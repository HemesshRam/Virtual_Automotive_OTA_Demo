import hashlib
import hmac
import json
import os


MQTT_JOB_SIGNING_KEY = os.getenv(
    "MQTT_JOB_SIGNING_KEY",
    "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
)


def canonical_payload(payload: dict) -> bytes:
    unsigned = {
        key: value
        for key, value in payload.items()
        if key != "signature"
    }
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: dict) -> str:
    return hmac.new(
        bytes.fromhex(MQTT_JOB_SIGNING_KEY),
        canonical_payload(payload),
        hashlib.sha256,
    ).hexdigest()


def attach_signature(payload: dict) -> dict:
    signed = dict(payload)
    signed["signature"] = {
        "algorithm": "hmac-sha256",
        "value": sign_payload(signed),
    }
    return signed


def verify_signature(payload: dict) -> bool:
    signature = payload.get("signature", {})
    if signature.get("algorithm") != "hmac-sha256":
        return False
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature.get("value", ""))
