import os
import threading
import time

from common.can_protocol import CANProtocol
from common.message_types import MessageType
from ecus.base.runtime_control import load_runtime_control


class ECUHeartbeatPublisher:
    """
    Periodic ECU availability signal on the local CAN FD segment.

    Real vehicles usually expose availability through network-management,
    diagnostics, or gateway health aggregation. This demo models that signal as
    a CAN FD heartbeat so zonal controllers can detect missing ECUs dynamically.
    """

    def __init__(
        self,
        can_interface,
        ecu_id: int,
        ecu_key: str,
        ecu_name: str,
        interval_seconds: float | None = None,
    ):
        self.can_interface = can_interface
        self.ecu_id = ecu_id
        self.ecu_key = ecu_key.upper().replace("-", "_")
        self.ecu_name = ecu_name
        self.interval_seconds = interval_seconds or float(
            os.getenv("OTA_ECU_HEARTBEAT_INTERVAL_SECONDS", "1.0")
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self._enabled():
            print(f"{self.ecu_name} heartbeat disabled by configuration")
            return

        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(
            f"{self.ecu_name} heartbeat enabled "
            f"({self.interval_seconds:.1f}s interval)"
        )

    def stop(self) -> None:
        self._stop.set()

    def _enabled(self) -> bool:
        specific = os.getenv(f"OTA_ECU_{self.ecu_key}_HEARTBEAT_ENABLED")
        value = specific if specific is not None else os.getenv(
            "OTA_ECU_HEARTBEAT_ENABLED",
            "1",
        )
        return value.lower() in {"1", "true", "yes", "on"}

    def _run(self) -> None:
        sequence = 0
        while not self._stop.is_set():
            if not load_runtime_control(self.ecu_key.lower())["heartbeat_enabled"]:
                self._stop.wait(self.interval_seconds)
                continue

            payload = bytes([sequence & 0xFF])
            message = CANProtocol.create_message(
                arbitration_id=self.ecu_id,
                message_type=MessageType.HEARTBEAT,
                payload=payload,
            )
            try:
                self.can_interface.send(message)
            except Exception as exc:
                print(f"{self.ecu_name} heartbeat send failed: {exc}")
            sequence = (sequence + 1) % 256
            self._stop.wait(self.interval_seconds)
