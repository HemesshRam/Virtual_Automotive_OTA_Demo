import time

from ecus.base.can_interface import CANInterface
from common.can_protocol import CANProtocol
from common.message_types import MessageType
from common.constants import BROADCAST_ID, CAN_INTERFACES, CAN_INTERFACE
from common.ecu_registry import ECU_REGISTRY
from vehicle.topology_loader import VehicleTopology

from tcu.models.vehicle import Vehicle
from tcu.models.ecu import ECU
from common.utils import normalize_transport, normalize_version
from tcu.zone_availability_guard import ZoneAvailabilityGuard, zone_service_available
from zones.zone_transport_client import ZoneTransportClient
from transport.uds.codec import build_read_data_by_identifier, parse_software_version


class ECUDiscovery:
    """
    ECU Discovery Service

    Discovers every ECU connected over VCAN and
    builds the Vehicle Digital Twin.
    """

    def __init__(self):
        self.can_interfaces = None

    def discover(self, timeout=3, transport="VCAN"):
        normalized_transport = normalize_transport(transport)

        if normalized_transport == "DOIP":
            return self._discover_doip(timeout=timeout, transport=normalized_transport)

        return self._discover_can(timeout=timeout, transport=normalized_transport)

    def _discover_can(self, timeout=3, transport="VCAN"):

        vehicle = Vehicle()
        zone_guard = ZoneAvailabilityGuard()
        use_zone_guard = zone_guard.enabled() and zone_service_available()
        if use_zone_guard:
            return self._discover_can_via_zones(transport=transport)

        self.can_interfaces = [
            CANInterface(channel)
            for channel in self._channels()
        ]

        print("\n========== ECU DISCOVERY ==========\n")

        request = CANProtocol.create_message(
            arbitration_id=BROADCAST_ID,
            message_type=MessageType.DISCOVERY_REQUEST,
        )

        print("Sending Discovery Request...\n")

        for can_interface in self.can_interfaces:
            print(f"Sending on {can_interface.channel}")
            can_interface.send(request)

        discovered = set()
        start = time.time()

        try:
            while time.time() - start < timeout:

                message = None
                source_channel = None

                for can_interface in self.can_interfaces:
                    message = can_interface.receive(timeout=0.05)
                    if message is not None:
                        source_channel = can_interface.channel
                        break

                if message is None:
                    continue

                try:
                    decoded = CANProtocol.parse_message(message)
                except ValueError:
                    # Ignore non-legacy CAN traffic that does not match the
                    # simple discovery message format.
                    continue

                if decoded["message_type"] != MessageType.DISCOVERY_RESPONSE:
                    continue

                ecu_id = decoded["sender_id"]

                if ecu_id in discovered:
                    continue

                discovered.add(ecu_id)

                version = normalize_version(
                    f"{decoded['version_major']}."
                    f"{decoded['version_minor']}.0"
                )
                ecu_name = self._ecu_name(ecu_id)

                if use_zone_guard and not zone_guard.is_ecu_online(ecu_name):
                    print(
                        f"Skipped ECU : {ecu_name} "
                        f"({hex(ecu_id)}) reason=ZONE_HEARTBEAT_OFFLINE"
                    )
                    continue

                ecu = ECU(
                    ecu_id=ecu_id,
                    ecu_name=ecu_name,
                    current_version=version,
                    transport=transport,
                    can_channel=source_channel or "",
                    dependencies=self._dependencies(ecu_id),
                    state="READY",
                    health="HEALTHY",
                )

                #
                # Convenience alias
                #

                ecu.version = version

                vehicle.add_ecu(ecu)

                print(
                    f"Discovered ECU : "
                    f"{ecu.ecu_name} "
                    f"({hex(ecu_id)}) "
                    f"Version {version} "
                    f"on {source_channel}"
                )
        finally:
            for can_interface in self.can_interfaces:
                can_interface.shutdown()
            self.can_interfaces = None

        print()

        print("Discovery Completed")
        print(f"Total ECUs Found : {len(vehicle.get_all_ecus())}")

        return vehicle

    def _discover_can_via_zones(self, transport="VCAN"):
        vehicle = Vehicle()
        client = ZoneTransportClient()
        topology = VehicleTopology()

        print("\n========== ECU DISCOVERY ==========\n")
        print("Querying zone controller inventory...\n")

        inventories = client.inventory()
        discovered = set()

        for inventory in inventories:
            zone_id = inventory.get("zone_id", "unknown")
            can_channel = inventory.get("can_channel", "")

            for ecu_entry in inventory.get("ecus", []):
                ecu_name = ecu_entry.get("ecu_name", "UNKNOWN")
                logical_address = int(ecu_entry["logical_address"], 16)
                availability = ecu_entry.get("availability", {})
                state = availability.get("state", "UNKNOWN")

                if state not in {"ONLINE", "STARTING", "UNMONITORED"}:
                    print(
                        f"Skipped ECU : {ecu_name} "
                        f"reason=ZONE_CONTROLLER_{state}"
                    )
                    continue

                try:
                    responses = client.forward_uds(
                        logical_address,
                        build_read_data_by_identifier(),
                    )
                    version = parse_software_version(responses[-1])
                except Exception as exc:
                    print(
                        f"Skipped ECU : {ecu_name} "
                        f"reason={exc}"
                    )
                    continue

                ecu_id = self._can_id_for_name(ecu_name)
                if ecu_id in discovered:
                    continue

                discovered.add(ecu_id)

                ecu = ECU(
                    ecu_id=ecu_id,
                    ecu_name=ecu_name,
                    current_version=normalize_version(version),
                    transport=transport,
                    can_channel=can_channel,
                    dependencies=topology.dependency_for_can_id(ecu_id),
                    state="READY",
                    health="HEALTHY",
                )
                ecu.version = ecu.current_version
                vehicle.add_ecu(ecu)

                print(
                    f"Discovered ECU : "
                    f"{ecu.ecu_name} "
                    f"({hex(ecu_id)}) "
                    f"Version {ecu.current_version} "
                    f"via zone {zone_id} on {can_channel}"
                )

        print()
        print("Discovery Completed")
        print(f"Total ECUs Found : {len(vehicle.get_all_ecus())}")

        return vehicle

    def _discover_doip(self, timeout=3, transport="DOIP"):

        from transport.doip.library_client import LibraryDoIPClient

        vehicle = Vehicle()

        print("\n========== ECU DISCOVERY ==========\n")
        print("Sending DoIP Vehicle Identification Request...\n")

        client = LibraryDoIPClient()
        client.connect()
        client.discover_vehicle()
        client.activate()

        discovered = set()
        deadline = time.time() + timeout

        try:
            for ecu_name, info in ECU_REGISTRY.items():
                if time.time() >= deadline:
                    break

                logical_address = info["logical_address"]

                try:
                    version = client.read_version_by_address(
                        logical_address,
                        timeout=max(0.5, deadline - time.time()),
                    )
                except Exception as exc:
                    print(
                        f"Skipped ECU : {ecu_name} "
                        f"({hex(logical_address)}) "
                        f"reason={exc}"
                    )
                    continue

                ecu_id = self._can_id_for_name(ecu_name)

                if ecu_id in discovered:
                    continue

                discovered.add(ecu_id)

                ecu = ECU(
                    ecu_id=ecu_id,
                    ecu_name=ecu_name,
                    current_version=normalize_version(version),
                    transport=transport,
                    can_channel="doip",
                    dependencies=self._dependencies(ecu_id),
                    state="READY",
                    health="HEALTHY",
                )
                ecu.version = ecu.current_version
                vehicle.add_ecu(ecu)

                print(
                    f"Discovered ECU : "
                    f"{ecu.ecu_name} "
                    f"({hex(ecu_id)}) "
                    f"Version {ecu.current_version} "
                    f"via DoIP {hex(logical_address)}"
                )
        finally:
            client.shutdown()

        print()
        print("Discovery Completed")
        print(f"Total ECUs Found : {len(vehicle.get_all_ecus())}")

        return vehicle

    # ---------------------------------------------------------

    @staticmethod
    def _channels():

        return CAN_INTERFACES or [CAN_INTERFACE]

    # ---------------------------------------------------------

    @staticmethod
    def _ecu_name(ecu_id):

        names = {
            0x201: "Gateway ECU",
            0x202: "BCM ECU",
            0x203: "Cluster ECU",
        }

        return names.get(ecu_id, f"ECU_{hex(ecu_id)}")

    @staticmethod
    def _can_id_for_name(ecu_name):

        mapping = {
            "Gateway ECU": 0x201,
            "BCM ECU": 0x202,
            "Cluster ECU": 0x203,
        }

        return mapping.get(ecu_name, 0x200)

    # ---------------------------------------------------------

    @staticmethod
    def _dependencies(ecu_id):
        return VehicleTopology().dependency_for_can_id(ecu_id)
