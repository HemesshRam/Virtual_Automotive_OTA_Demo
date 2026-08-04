import socket
import threading

from zones.base.zone_controller import ZoneController
from zones.base.zone_protocol import read_message, send_message


class ZoneService:
    """
    Standalone zonal controller service.

    This makes a zone visible as an independent runtime component while still
    forwarding UDS over the existing CAN FD/ISO-TP ECU path.
    """

    def __init__(self, zone_id: str, config: dict):
        self.zone_id = zone_id
        self.config = config
        self.host = config.get("service_bind_host", "127.0.0.1")
        self.port = int(config["service_port"])
        self.controller = ZoneController(zone_id, config)

    def start(self):
        print()
        print("=" * 60)
        print(f"ZONE CONTROLLER SERVICE: {self.zone_id}")
        print("=" * 60)
        print(f"Display Name : {self.config['display_name']}")
        print(f"CAN Channel  : {self.config['can_channel']}")
        print(f"Listen       : {self.host}:{self.port}")
        print(f"Health       : {self.controller.health()['state']}")
        print("=" * 60)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(8)

            while True:
                client, address = server.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client, address),
                    daemon=True,
                ).start()

    def _handle_client(self, client: socket.socket, address):
        with client:
            try:
                request = read_message(client)
                response = self._dispatch(request)
            except Exception as exc:
                response = {
                    "status": "ERROR",
                    "zone_id": self.zone_id,
                    "error": str(exc),
                }
            send_message(client, response)

    def _dispatch(self, request: dict) -> dict:
        request_type = request.get("type")
        if request_type == "inventory":
            return {
                "status": "OK",
                "zone_id": self.zone_id,
                "inventory": self.controller.inventory(),
            }

        if request_type == "health":
            return {
                "status": "OK",
                "zone_id": self.zone_id,
                "health": self.controller.health(),
            }

        if request_type == "forward_uds":
            logical_address = int(request["target_logical_address"])
            payload = bytes.fromhex(request["payload_hex"])
            responses = self.controller.forward_uds(logical_address, payload)
            return {
                "status": "OK",
                "zone_id": self.zone_id,
                "responses": [item.hex() for item in responses],
            }

        return {
            "status": "ERROR",
            "zone_id": self.zone_id,
            "error": f"unsupported request type {request_type}",
        }
