import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.mqtt_security import attach_signature, verify_signature


def main():
    payload = {
        "type": "ota_job",
        "job_id": "JOB_DEMO_TAMPER",
        "campaign_id": "OTA_2026_001",
        "vehicle_id": "demo-vin",
        "operation": "software_update",
        "document": {
            "campaign_url": "http://127.0.0.1:8080/campaign/latest",
            "release_version": "2.0.0",
        },
    }

    signed = attach_signature(payload)
    print("[OK] MQTT job signed")

    if not verify_signature(signed):
        raise SystemExit("[FAIL] Signed MQTT job was rejected")

    tampered = dict(signed)
    tampered["campaign_id"] = "MALICIOUS_CAMPAIGN"

    if verify_signature(tampered):
        raise SystemExit("[FAIL] Tampered MQTT job was accepted")

    print("[OK] Tampered MQTT job rejected")


if __name__ == "__main__":
    main()
