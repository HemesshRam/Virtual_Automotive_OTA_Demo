import os
import socket
import time

from zones.base.zone_protocol import read_message, send_message
from zones.zone_registry import zone_for_logical_address


class ZoneTransportClient:
    """
    TCP client used by the central gateway to reach standalone zone services.
    """

    CONNECT_TIMEOUT_SECONDS = 2.0
    DEFAULT_RESPONSE_TIMEOUT_SECONDS = 180.0
    CONNECT_RETRY_SECONDS = 20.0

    def __init__(self):
        self.response_timeout_seconds = float(
            os.getenv(
                "OTA_ZONE_SERVICE_RESPONSE_TIMEOUT_SECONDS",
                str(self.DEFAULT_RESPONSE_TIMEOUT_SECONDS),
            )
        )

    def forward_uds(self, logical_address: int, payload: bytes) -> list[bytes]:
        zone_id, zone = zone_for_logical_address(logical_address)
        if zone_id is None or zone is None:
            raise KeyError(f"No zone owns logical address {hex(logical_address)}")

        host = zone.get("service_host", "127.0.0.1")
        port = int(os.getenv(f"OTA_ZONE_{zone_id.upper()}_PORT", zone["service_port"]))
        request = {
            "type": "forward_uds",
            "zone_id": zone_id,
            "target_logical_address": logical_address,
            "payload_hex": payload.hex(),
        }

        with self._connect(host, port) as sock:
            sock.settimeout(self.response_timeout_seconds)
            send_message(sock, request)
            response = read_message(sock)

        if response.get("status") != "OK":
            raise RuntimeError(
                f"Zone {zone_id} rejected request: {response.get('error', 'UNKNOWN')}"
            )

        return [
            bytes.fromhex(item)
            for item in response.get("responses", [])
        ]

    def inventory(self) -> list[dict]:
        inventories = []
        from zones.zone_registry import ZONE_REGISTRY

        for zone_id, zone in ZONE_REGISTRY.items():
            host = zone.get("service_host", "127.0.0.1")
            port = int(os.getenv(f"OTA_ZONE_{zone_id.upper()}_PORT", zone["service_port"]))
            with self._connect(host, port) as sock:
                sock.settimeout(self.response_timeout_seconds)
                send_message(sock, {"type": "inventory", "zone_id": zone_id})
                response = read_message(sock)
            if response.get("status") != "OK":
                raise RuntimeError(
                    f"Zone {zone_id} inventory failed: {response.get('error', 'UNKNOWN')}"
                )
            inventories.append(response["inventory"])
        return inventories

    def health(self) -> list[dict]:
        health = []
        from zones.zone_registry import ZONE_REGISTRY

        for zone_id, zone in ZONE_REGISTRY.items():
            host = zone.get("service_host", "127.0.0.1")
            port = int(os.getenv(f"OTA_ZONE_{zone_id.upper()}_PORT", zone["service_port"]))
            with self._connect(host, port) as sock:
                sock.settimeout(self.response_timeout_seconds)
                send_message(sock, {"type": "health", "zone_id": zone_id})
                response = read_message(sock)
            if response.get("status") != "OK":
                raise RuntimeError(
                    f"Zone {zone_id} health failed: {response.get('error', 'UNKNOWN')}"
                )
            health.append(response["health"])
        return health

    def _connect(self, host: str, port: int) -> socket.socket:
        deadline = time.time() + self.CONNECT_RETRY_SECONDS
        last_error = None
        while time.time() < deadline:
            try:
                return socket.create_connection(
                    (host, port),
                    timeout=self.CONNECT_TIMEOUT_SECONDS,
                )
            except OSError as exc:
                last_error = exc
                time.sleep(0.25)
        raise TimeoutError(
            f"Timed out connecting to zone service at {host}:{port}"
        ) from last_error
