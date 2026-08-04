from vehicle.topology_loader import VehicleTopology


_TOPOLOGY = VehicleTopology()
OTA_ALLOWED_UDS_SERVICES = _TOPOLOGY.allowed_uds_services
ZONE_REGISTRY = _TOPOLOGY.build_zone_registry()


def zone_for_logical_address(logical_address: int):
    for zone_id, zone in ZONE_REGISTRY.items():
        if logical_address in zone["ecus"]:
            return zone_id, zone
    return None, None
