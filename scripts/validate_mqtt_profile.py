import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.mqtt_config import (
    DEFAULT_VEHICLE_ID,
    MQTT_QOS,
    MQTT_RETAIN_CAMPAIGN,
    MQTT_USERNAME,
    OTA_ADMIN_TOKEN,
    vehicle_topics,
)
from common.mqtt_security import attach_signature, verify_signature


def main():
    topics = vehicle_topics(DEFAULT_VEHICLE_ID)

    print("[OK] MQTT profile loaded")
    print(f"Vehicle ID       : {DEFAULT_VEHICLE_ID}")
    print(f"Campaign topic   : {topics.campaign}")
    print(f"Jobs notify      : {topics.jobs_notify}")
    print(f"Status topic     : {topics.status}")
    print(f"Jobs status      : {topics.jobs_status}")
    print(f"Availability     : {topics.availability}")
    print(f"QoS              : {MQTT_QOS}")
    print(f"Retain campaign  : {MQTT_RETAIN_CAMPAIGN}")
    print(f"Broker auth      : {'enabled' if MQTT_USERNAME else 'disabled'}")
    print(f"Publish API auth : {'enabled' if OTA_ADMIN_TOKEN else 'disabled'}")

    if MQTT_QOS not in {0, 1, 2}:
        raise SystemExit("[FAIL] MQTT_QOS must be 0, 1, or 2")

    sample_job = attach_signature({
        "type": "ota_job",
        "job_id": "JOB_PROFILE_CHECK",
        "campaign_id": "OTA_PROFILE_CHECK",
        "vehicle_id": DEFAULT_VEHICLE_ID,
    })
    if not verify_signature(sample_job):
        raise SystemExit("[FAIL] MQTT job signature verification failed")
    print("[OK] MQTT job signature model verifies")

    print("[OK] MQTT production-style controls are configured")


if __name__ == "__main__":
    main()
