import json
import os
import time
from datetime import datetime, timedelta, timezone

from common.demo_logging import demo_log
from common.mqtt_security import attach_signature
from common.mqtt_config import (
    DEFAULT_VEHICLE_ID,
    MQTT_CLIENT_ID_PREFIX,
    MQTT_QOS,
    MQTT_RETAIN_CAMPAIGN,
    vehicle_topics,
)
from common.mqtt_utils import connect_with_retry, make_mqtt_client
from ota_server.job_repository import job_repository

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class OTAMQTTPublisher:

    def __init__(self, vehicle_id: str = DEFAULT_VEHICLE_ID):
        self.vehicle_id = vehicle_id
        self.topics = vehicle_topics(vehicle_id)

    @property
    def available(self):
        return mqtt is not None

    def publish_campaign_available(self, campaign, base_url):
        if not self.available:
            raise RuntimeError("paho-mqtt is not installed")

        client = make_mqtt_client(
            mqtt,
            client_id=f"{MQTT_CLIENT_ID_PREFIX}-server-{int(time.time())}"
        )

        connect_with_retry(client, "SERVER")
        client.loop_start()

        try:
            now = datetime.now(timezone.utc)
            job_id = os.getenv("OTA_JOB_ID")
            if not job_id:
                issued_at = now.strftime("%Y%m%dT%H%M%SZ")
                job_id = f"JOB_{campaign['campaign_id']}_{self.vehicle_id}_{issued_at}"
            payload = {
                "type": "ota_job",
                "job_id": job_id,
                "campaign_id": campaign["campaign_id"],
                "vehicle_id": self.vehicle_id,
                "operation": "software_update",
                "priority": campaign.get("priority", "NORMAL"),
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=24)).isoformat(),
                "release_version": campaign["release_version"],
                "vehicle_model": campaign["vehicle_model"],
                "download_url": f"{base_url}/campaign/latest",
                "document": {
                    "campaign_url": f"{base_url}/campaign/latest",
                    "release_version": campaign["release_version"],
                    "metadata_url": f"{base_url}/campaign/latest",
                },
                "issued_at": int(time.time()),
            }
            payload = attach_signature(payload)
            job_repository.create_job(payload)

            demo_log(f"[MQTT:SERVER] Publishing to {self.topics.jobs_notify}")
            result = client.publish(
                self.topics.jobs_notify,
                json.dumps(payload),
                qos=MQTT_QOS,
                retain=MQTT_RETAIN_CAMPAIGN,
            )
            result.wait_for_publish()
        finally:
            client.loop_stop()
            client.disconnect()

        return payload
