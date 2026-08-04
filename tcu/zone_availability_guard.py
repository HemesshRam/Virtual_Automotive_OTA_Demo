import os

from zones.zone_registry import ZONE_REGISTRY
from zones.zone_transport_client import ZoneTransportClient


class ZoneAvailabilityGuard:
    """
    Applies live zone/ECU heartbeat availability to transports that do not route
    through the zone service directly.

    DoIP deep-zonal forwarding already enforces this inside the zone controller.
    VCAN mode sends directly on SocketCAN, so the TCU uses this guard to consult
    the same live zone inventory before discovery/flashing.
    """

    def __init__(self):
        self.client = ZoneTransportClient()

    @staticmethod
    def enabled() -> bool:
        if os.getenv("OTA_VCAN_ZONE_GUARD_ENABLED", "1").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        return os.getenv("OTA_USE_ZONAL_CONTROLLERS", "0").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def require_ecu_online(self, ecu_name: str) -> None:
        if not self.enabled():
            return

        availability = self.ecu_availability(ecu_name)
        state = availability.get("state", "UNKNOWN")
        if state in {"ONLINE", "STARTING", "UNMONITORED"}:
            return

        raise RuntimeError(
            f"Zone heartbeat gate rejected {ecu_name}: "
            f"state={state} reason={availability.get('reason', 'UNKNOWN')}"
        )

    def is_ecu_online(self, ecu_name: str) -> bool:
        if not self.enabled():
            return True

        try:
            self.require_ecu_online(ecu_name)
            return True
        except Exception:
            return False

    def ecu_availability(self, ecu_name: str) -> dict:
        inventories = self.client.inventory()

        for inventory in inventories:
            zone_health = inventory.get("health", {})
            for ecu in inventory.get("ecus", []):
                if ecu.get("ecu_name") != ecu_name:
                    continue

                availability = dict(ecu.get("availability", {}))
                availability["zone_id"] = inventory.get("zone_id")
                availability["zone_state"] = zone_health.get("state")
                availability["reason"] = zone_health.get("reason")
                return availability

        raise KeyError(f"{ecu_name} not found in live zone inventory")


def zone_service_available() -> bool:
    if not ZoneAvailabilityGuard.enabled():
        return False
    try:
        ZoneTransportClient().inventory()
        return True
    except Exception:
        return False


def topology_zone_id_for_ecu(ecu_name: str) -> str:
    for zone_id, zone in ZONE_REGISTRY.items():
        for ecu in zone.get("ecus", {}).values():
            if ecu.get("ecu_name") == ecu_name:
                return zone_id
    return ""
