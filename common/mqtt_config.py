from dataclasses import dataclass
import os


MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
MQTT_CLIENT_ID_PREFIX = os.getenv("MQTT_CLIENT_ID_PREFIX", "virtual-ota")
DEFAULT_VEHICLE_ID = os.getenv("OTA_VEHICLE_ID", "demo-vin")
MQTT_CONNECT_RETRIES = int(os.getenv("MQTT_CONNECT_RETRIES", "3"))
MQTT_CONNECT_RETRY_DELAY = float(os.getenv("MQTT_CONNECT_RETRY_DELAY", "1.0"))
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_RETAIN_CAMPAIGN = os.getenv("MQTT_RETAIN_CAMPAIGN", "1").lower() in {
    "1",
    "true",
    "yes",
}
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
OTA_ADMIN_TOKEN = os.getenv("OTA_ADMIN_TOKEN")


@dataclass(frozen=True)
class MQTTTopics:
    campaign: str
    jobs_notify: str
    status: str
    jobs_status: str
    inventory: str
    events: str
    availability: str


def vehicle_topics(vehicle_id: str = DEFAULT_VEHICLE_ID) -> MQTTTopics:
    base = f"vehicle/{vehicle_id}/ota"
    return MQTTTopics(
        campaign=f"{base}/campaign",
        jobs_notify=f"{base}/jobs/notify",
        status=f"{base}/status",
        jobs_status=f"{base}/jobs/status",
        inventory=f"{base}/inventory",
        events=f"{base}/events",
        availability=f"{base}/availability",
    )
