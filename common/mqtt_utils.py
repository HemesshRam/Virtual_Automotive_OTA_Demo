import time

from common.demo_logging import demo_log
from common.mqtt_config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_CONNECT_RETRIES,
    MQTT_CONNECT_RETRY_DELAY,
    MQTT_KEEPALIVE,
    MQTT_PASSWORD,
    MQTT_USERNAME,
)


def configure_mqtt_client(client):
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    return client


def make_mqtt_client(mqtt_module, **kwargs):
    if hasattr(mqtt_module, "CallbackAPIVersion"):
        try:
            return mqtt_module.Client(
                mqtt_module.CallbackAPIVersion.VERSION2,
                **kwargs,
            )
        except TypeError:
            pass
    return mqtt_module.Client(**kwargs)


def connect_with_retry(client, role: str):
    last_error = None

    for attempt in range(1, MQTT_CONNECT_RETRIES + 1):
        try:
            demo_log(
                f"[MQTT:{role}] Connecting to "
                f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} "
                f"(attempt {attempt}/{MQTT_CONNECT_RETRIES})"
            )
            configure_mqtt_client(client)
            client.connect(
                MQTT_BROKER_HOST,
                MQTT_BROKER_PORT,
                MQTT_KEEPALIVE,
            )
            demo_log(f"[MQTT:{role}] Connected")
            return True
        except Exception as exc:
            last_error = exc
            demo_log(f"[MQTT:{role}] Connect failed: {exc}")
            if attempt < MQTT_CONNECT_RETRIES:
                time.sleep(MQTT_CONNECT_RETRY_DELAY)

    raise RuntimeError(
        f"Unable to connect to MQTT broker at "
        f"{MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}"
    ) from last_error
