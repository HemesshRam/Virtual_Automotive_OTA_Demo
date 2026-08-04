"""
Vehicle ECU Registry.

Loaded from vehicle/topology.json so the gateway/TCU can share one topology
source instead of duplicating hardcoded ECU mappings.
"""

from vehicle.topology_loader import VehicleTopology


ECU_REGISTRY = VehicleTopology().ecu_registry()
