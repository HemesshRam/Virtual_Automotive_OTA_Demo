import json
import os
import threading
import time

from common.message_types import MessageType
from ecus.base.can_interface import CANInterface
from transport.can.isotp_adapter import IsoTpAdapter, IsoTpReassembler
from transport.uds.codec import (
    is_negative_response,
    is_response_pending,
    positive_response_sid,
)


class ZoneController:
    """
    OTA-relevant zonal controller simulation.

    A production zonal controller owns many local networks. This demo controller
    owns one CAN FD/VCAN channel and forwards raw UDS over ISO-TP to local ECUs.
    """

    DEFAULT_RESPONSE_TIMEOUT_SECONDS = 120.0

    def __init__(self, zone_id: str, config: dict):
        self.zone_id = zone_id
        self.config = config
        self.can_channel = config["can_channel"]
        self.ecus = config["ecus"]
        self.response_timeout_seconds = float(
            os.getenv(
                "OTA_ZONE_UDS_RESPONSE_TIMEOUT_SECONDS",
                str(self.DEFAULT_RESPONSE_TIMEOUT_SECONDS),
            )
        )
        self.started_at = time.monotonic()
        self.heartbeat_last_seen: dict[int, float] = {}
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_interface: CANInterface | None = None
        self.metrics = {
            "requests": 0,
            "forwarded": 0,
            "rejected": 0,
            "timeouts": 0,
            "heartbeat_frames": 0,
            "last_error": "",
            "last_service_id": "",
            "last_latency_ms": 0,
        }
        self.can_interface = CANInterface(self.can_channel)
        self._start_heartbeat_monitor()

    def health(self) -> dict:
        state = self._health_state()
        heartbeat = self._heartbeat_health()
        return {
            "zone_id": self.zone_id,
            "state": state,
            "can_channel": self.can_channel,
            "reason": self._health_reason(state),
            "heartbeat_monitor": heartbeat,
        }

    def inventory(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "display_name": self.config["display_name"],
            "can_channel": self.can_channel,
            "health": self.health(),
            "policy": {
                "programming_allowed": self._programming_allowed(),
                "allowed_services": [
                    f"0x{service_id:02X}"
                    for service_id in sorted(self._allowed_services())
                ],
            },
            "metrics": dict(self.metrics),
            "ecus": [
                {
                    "logical_address": hex(logical_address),
                    "ecu_name": info["ecu_name"],
                    "can_id": hex(info["can_id"]),
                    "availability": self._ecu_availability(logical_address),
                }
                for logical_address, info in self.ecus.items()
            ],
        }

    def forward_uds(self, logical_address: int, payload: bytes) -> list[bytes]:
        started_at = time.monotonic()
        self.metrics["requests"] += 1
        self.metrics["last_service_id"] = f"0x{payload[0]:02X}" if payload else ""

        if logical_address not in self.ecus:
            self._record_rejection("ECU_NOT_OWNED_BY_ZONE")
            raise KeyError(
                f"{hex(logical_address)} is not owned by zone {self.zone_id}"
            )

        self._enforce_health()
        self._enforce_target_online(logical_address)
        self._enforce_policy(payload)

        ecu = self.ecus[logical_address]
        print(
            f"[ZONE:{self.zone_id}] Forwarding UDS to "
            f"{ecu['ecu_name']} on {self.can_channel}"
        )

        IsoTpAdapter(self.can_interface.bus).send(ecu["can_id"], payload)

        deadline = time.time() + self.response_timeout_seconds
        request_sid = payload[0] if payload else None
        responses: list[bytes] = []
        reassembler = IsoTpReassembler()

        while time.time() < deadline:
            response = self.can_interface.receive(
                timeout=max(0.05, deadline - time.time())
            )
            if response is None:
                continue
            if response.arbitration_id != ecu["can_id"]:
                continue

            assembled = reassembler.feed(bytes(response.data))
            if assembled is not None:
                if not self._is_response_for_request(assembled, request_sid):
                    continue
                responses.append(assembled)
                if request_sid is not None and is_response_pending(assembled, request_sid):
                    continue
                self.metrics["forwarded"] += 1
                self.metrics["last_error"] = ""
                self.metrics["last_latency_ms"] = int(
                    (time.monotonic() - started_at) * 1000
                )
                return responses

        self.metrics["timeouts"] += 1
        self.metrics["last_error"] = "RESPONSE_TIMEOUT"
        raise TimeoutError(
            f"Timed out waiting for zone {self.zone_id} response from {ecu['ecu_name']}"
        )

    def shutdown(self):
        self._heartbeat_stop.set()
        if self._heartbeat_interface is not None:
            self._heartbeat_interface.shutdown()
        self.can_interface.shutdown()

    def _health_state(self) -> str:
        override = os.getenv(f"OTA_ZONE_{self.zone_id.upper()}_HEALTH")
        if override and override.upper() != "AUTO":
            return override.upper()

        configured = str(self.config.get("default_health", "ONLINE")).upper()
        if configured != "AUTO" and not self._heartbeat_monitor_enabled():
            return configured

        heartbeat = self._heartbeat_health()
        if heartbeat["state"] == "STARTING":
            return "STARTING"
        if heartbeat["offline_ecus"]:
            return "DEGRADED" if heartbeat["online_ecus"] else "OFFLINE"
        return "ONLINE"

    @staticmethod
    def _health_reason(state: str) -> str:
        reasons = {
            "ONLINE": "",
            "DEGRADED": "ZONE_DEGRADED_BUT_OPERATIONAL",
            "STARTING": "WAITING_FOR_ECU_HEARTBEAT",
            "OFFLINE": "ZONE_OFFLINE",
            "BUS_OFF": "ZONE_CAN_BUS_OFF",
            "SECURITY_LOCKED": "ZONE_SECURITY_LOCKED",
        }
        return reasons.get(state, f"UNKNOWN_ZONE_HEALTH_{state}")

    def _enforce_health(self) -> None:
        state = self._health_state()
        if state in {"ONLINE", "DEGRADED", "STARTING"}:
            return
        reason = self._health_reason(state)
        self._record_rejection(reason)
        raise RuntimeError(reason)

    def _enforce_target_online(self, logical_address: int) -> None:
        availability = self._ecu_availability(logical_address)
        if availability["state"] in {"ONLINE", "STARTING", "UNMONITORED"}:
            return

        ecu = self.ecus[logical_address]
        reason = f"ECU_HEARTBEAT_TIMEOUT:{ecu['ecu_name']}"
        self._record_rejection(reason)
        raise RuntimeError(reason)

    def _allowed_services(self) -> set[int]:
        configured = os.getenv(f"OTA_ZONE_{self.zone_id.upper()}_ALLOWED_SERVICES")
        if configured:
            return {
                int(item.strip(), 0)
                for item in configured.split(",")
                if item.strip()
            }
        return set(self.config.get("allowed_services", []))

    def _programming_allowed(self) -> bool:
        value = os.getenv(f"OTA_ZONE_{self.zone_id.upper()}_PROGRAMMING_ALLOWED")
        if value is None:
            return bool(self.config.get("programming_allowed", True))
        return value.lower() in {"1", "true", "yes", "on"}

    def _enforce_policy(self, payload: bytes) -> None:
        if not payload:
            self._record_rejection("EMPTY_UDS_PAYLOAD")
            raise RuntimeError("EMPTY_UDS_PAYLOAD")

        service_id = payload[0]
        allowed_services = self._allowed_services()
        if service_id not in allowed_services:
            reason = f"UDS_SERVICE_0x{service_id:02X}_BLOCKED_BY_ZONE_POLICY"
            self._record_rejection(reason)
            raise RuntimeError(reason)

        programming_services = {0x27, 0x31, 0x34, 0x36, 0x37}
        if service_id in programming_services and not self._programming_allowed():
            reason = "PROGRAMMING_BLOCKED_BY_ZONE_POLICY"
            self._record_rejection(reason)
            raise RuntimeError(reason)

    def _record_rejection(self, reason: str) -> None:
        self.metrics["rejected"] += 1
        self.metrics["last_error"] = reason
        print(
            json.dumps(
                {
                    "component": "zone_controller",
                    "zone_id": self.zone_id,
                    "event": "request_rejected",
                    "reason": reason,
                },
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _is_response_for_request(payload: bytes, request_sid: int | None) -> bool:
        if request_sid is None or not payload:
            return False

        if payload[0] == positive_response_sid(request_sid):
            return True

        return is_negative_response(payload) and len(payload) >= 3 and payload[1] == request_sid

    def _start_heartbeat_monitor(self) -> None:
        if not self._heartbeat_monitor_enabled():
            return

        self._heartbeat_interface = CANInterface(self.can_channel)
        self._heartbeat_thread = threading.Thread(
            target=self._monitor_heartbeats,
            daemon=True,
        )
        self._heartbeat_thread.start()

    @staticmethod
    def _heartbeat_monitor_enabled() -> bool:
        value = os.getenv("OTA_ZONE_HEARTBEAT_MONITOR_ENABLED", "1")
        return value.lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _heartbeat_timeout_seconds() -> float:
        return float(os.getenv("OTA_ZONE_HEARTBEAT_TIMEOUT_SECONDS", "3.0"))

    @staticmethod
    def _heartbeat_grace_seconds() -> float:
        return float(os.getenv("OTA_ZONE_HEARTBEAT_GRACE_SECONDS", "5.0"))

    def _monitor_heartbeats(self) -> None:
        assert self._heartbeat_interface is not None
        can_ids = {info["can_id"] for info in self.ecus.values()}

        while not self._heartbeat_stop.is_set():
            message = self._heartbeat_interface.receive(timeout=0.5)
            if message is None or message.arbitration_id not in can_ids:
                continue
            if not message.data:
                continue

            try:
                message_type = MessageType(message.data[0])
            except ValueError:
                continue

            if message_type != MessageType.HEARTBEAT:
                continue

            self.heartbeat_last_seen[message.arbitration_id] = time.monotonic()
            self.metrics["heartbeat_frames"] += 1

    def _heartbeat_health(self) -> dict:
        if not self._heartbeat_monitor_enabled():
            return {
                "enabled": False,
                "state": "UNMONITORED",
                "online_ecus": [],
                "offline_ecus": [],
                "timeout_seconds": self._heartbeat_timeout_seconds(),
            }

        online_ecus = []
        offline_ecus = []
        for logical_address, ecu in self.ecus.items():
            availability = self._ecu_availability(logical_address)
            if availability["state"] in {"ONLINE", "STARTING"}:
                online_ecus.append(ecu["ecu_name"])
            else:
                offline_ecus.append(ecu["ecu_name"])

        state = "ONLINE"
        if offline_ecus:
            state = "DEGRADED" if online_ecus else "OFFLINE"
        if not online_ecus and not offline_ecus:
            state = "ONLINE"
        if online_ecus and any(
            self._ecu_availability(logical_address)["state"] == "STARTING"
            for logical_address in self.ecus
        ):
            state = "STARTING"

        return {
            "enabled": True,
            "state": state,
            "online_ecus": online_ecus,
            "offline_ecus": offline_ecus,
            "timeout_seconds": self._heartbeat_timeout_seconds(),
            "grace_seconds": self._heartbeat_grace_seconds(),
        }

    def _ecu_availability(self, logical_address: int) -> dict:
        if not self._heartbeat_monitor_enabled():
            return {
                "state": "UNMONITORED",
                "last_seen_age_seconds": None,
            }

        ecu = self.ecus[logical_address]
        now = time.monotonic()
        last_seen = self.heartbeat_last_seen.get(ecu["can_id"])

        if last_seen is None:
            age_since_start = now - self.started_at
            if age_since_start < self._heartbeat_grace_seconds():
                return {
                    "state": "STARTING",
                    "last_seen_age_seconds": None,
                }
            return {
                "state": "OFFLINE",
                "last_seen_age_seconds": None,
            }

        age = now - last_seen
        if age <= self._heartbeat_timeout_seconds():
            return {
                "state": "ONLINE",
                "last_seen_age_seconds": round(age, 3),
            }

        return {
            "state": "OFFLINE",
            "last_seen_age_seconds": round(age, 3),
        }
