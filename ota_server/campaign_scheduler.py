import json
import os
import time

from ota_server.config import HOST, PORT, PUBLIC_SCHEME
from ota_server.mqtt_publisher import OTAMQTTPublisher
from ota_server.repository import OTARepository


def _public_base_url() -> str:
    configured = os.getenv("OTA_PUBLIC_BASE_URL")
    if configured:
        return configured.rstrip("/")

    host = "127.0.0.1" if HOST == "0.0.0.0" else HOST
    return f"{PUBLIC_SCHEME}://{host}:{PORT}"


def publish_current_campaign_once():
    with open(OTARepository.campaign(), "r", encoding="utf-8") as fp:
        campaign = json.load(fp)

    publisher = OTAMQTTPublisher()
    if not publisher.available:
        raise RuntimeError("paho-mqtt is not installed")

    return publisher.publish_campaign_available(campaign, _public_base_url())


def main():
    delay = float(os.getenv("OTA_CAMPAIGN_PUBLISH_DELAY", "3"))

    print()
    print("=" * 60)
    print("OTA CAMPAIGN SCHEDULER")
    print("=" * 60)
    print("Mode        : one-shot backend campaign publish")
    print(f"Delay       : {delay:.1f}s")
    print(f"Base URL    : {_public_base_url()}")
    print("Trigger     : automatic backend scheduler")
    print("=" * 60)

    if delay > 0:
        time.sleep(delay)

    payload = publish_current_campaign_once()

    print()
    print("Campaign notification published")
    print(f"Campaign ID : {payload['campaign_id']}")
    print(f"Job ID      : {payload['job_id']}")
    print(f"Topic       : {OTAMQTTPublisher().topics.jobs_notify}")
    print("=" * 60)


if __name__ == "__main__":
    main()
