from zones.base.zone_controller import ZoneController
from zones.zone_registry import ZONE_REGISTRY, zone_for_logical_address


class ZoneRouter:
    """
    Resolves ECU logical addresses to simulated zonal controllers.
    """

    def __init__(self):
        self.controllers = {
            zone_id: ZoneController(zone_id, config)
            for zone_id, config in ZONE_REGISTRY.items()
        }

    def forward_uds(self, logical_address: int, payload: bytes) -> list[bytes]:
        zone_id, _zone = zone_for_logical_address(logical_address)
        if zone_id is None:
            raise KeyError(f"No zone owns logical address {hex(logical_address)}")

        return self.controllers[zone_id].forward_uds(logical_address, payload)

    def inventory(self) -> list[dict]:
        return [
            controller.inventory()
            for controller in self.controllers.values()
        ]

    def shutdown(self):
        for controller in self.controllers.values():
            controller.shutdown()
