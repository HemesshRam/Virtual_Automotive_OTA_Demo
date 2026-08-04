import json

from common.mqtt_config import DEFAULT_VEHICLE_ID, MQTT_CLIENT_ID_PREFIX, MQTT_QOS, vehicle_topics
from common.mqtt_utils import connect_with_retry, make_mqtt_client

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


def clear_retained_job_notification(vehicle_id: str = DEFAULT_VEHICLE_ID) -> bool:
    if mqtt is None:
        raise RuntimeError("paho-mqtt is not installed")

    topics = vehicle_topics(vehicle_id)
    client = make_mqtt_client(
        mqtt,
        client_id=f"{MQTT_CLIENT_ID_PREFIX}-retained-clear-{vehicle_id}",
    )
    connect_with_retry(client, "SERVER")
    client.loop_start()
    try:
        result = client.publish(topics.jobs_notify, payload="", qos=MQTT_QOS, retain=True)
        result.wait_for_publish()
    finally:
        client.loop_stop()
        client.disconnect()

    print(json.dumps({"result": "OK", "cleared_topic": topics.jobs_notify}))
    return True


if __name__ == "__main__":
    clear_retained_job_notification()
