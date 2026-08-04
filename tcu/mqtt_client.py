import json
import time

from common.demo_logging import demo_log
from common.mqtt_config import (
    DEFAULT_VEHICLE_ID,
    MQTT_CLIENT_ID_PREFIX,
    MQTT_QOS,
    vehicle_topics,
)
from common.mqtt_security import verify_signature
from common.mqtt_utils import connect_with_retry, make_mqtt_client

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


class TcuMQTTClient:

    def __init__(self, vehicle_id: str = DEFAULT_VEHICLE_ID):
        self.vehicle_id = vehicle_id
        self.topics = vehicle_topics(vehicle_id)

    @property
    def available(self):
        return mqtt is not None

    def wait_for_campaign(self, timeout=60):
        if not self.available:
            raise RuntimeError("paho-mqtt is not installed")

        message_holder = {"payload": None}

        def on_connect(client, _userdata, _flags, reason_code, _properties=None):
            if getattr(reason_code, "is_failure", False):
                print(f"[MQTT:TCU] Subscribe connect failed: {reason_code}")
                return
            demo_log(f"[MQTT:TCU] Subscribing to {self.topics.jobs_notify}")
            client.subscribe(self.topics.jobs_notify, qos=MQTT_QOS)

        def on_message(_client, _userdata, msg):
            try:
                if not msg.payload:
                    return
                payload = json.loads(msg.payload.decode("utf-8"))
                if payload.get("type") != "ota_job":
                    return
                demo_log(f"[MQTT:TCU] Campaign received on {msg.topic}")
                if payload.get("type") == "ota_job" and not verify_signature(payload):
                    print("[MQTT:TCU] Rejected MQTT job: invalid signature")
                    message_holder["payload"] = None
                    return
                message_holder["payload"] = payload
            except json.JSONDecodeError:
                message_holder["payload"] = None

        client = make_mqtt_client(
            mqtt,
            client_id=f"{MQTT_CLIENT_ID_PREFIX}-tcu-{self.vehicle_id}",
            clean_session=False,
        )
        client.on_connect = on_connect
        client.on_message = on_message
        client.will_set(
            self.topics.availability,
            json.dumps({"vehicle_id": self.vehicle_id, "state": "offline"}),
            qos=MQTT_QOS,
            retain=True,
        )

        connect_with_retry(client, "TCU")
        client.loop_start()
        client.publish(
            self.topics.availability,
            json.dumps({"vehicle_id": self.vehicle_id, "state": "online"}),
            qos=MQTT_QOS,
            retain=True,
        )

        deadline = time.time() + timeout

        try:
            while time.time() < deadline:
                if message_holder["payload"] is not None:
                    return message_holder["payload"]
                time.sleep(0.1)
        finally:
            client.loop_stop()
            client.disconnect()

        raise TimeoutError("Timed out waiting for MQTT campaign notification")

    def publish_status(self, payload):
        if not self.available:
            return False

        client = make_mqtt_client(
            mqtt,
            client_id=f"{MQTT_CLIENT_ID_PREFIX}-status-{self.vehicle_id}"
        )
        client.will_set(
            self.topics.availability,
            json.dumps({"vehicle_id": self.vehicle_id, "state": "offline"}),
            qos=MQTT_QOS,
            retain=True,
        )
        connect_with_retry(client, "STATUS")
        client.loop_start()

        try:
            demo_log(f"[MQTT:STATUS] Publishing to {self.topics.jobs_status}")
            result = client.publish(
                self.topics.jobs_status,
                json.dumps(payload),
                qos=MQTT_QOS,
                retain=False,
            )
            result.wait_for_publish()
        finally:
            client.loop_stop()
            client.disconnect()
        return True
