from tcu.models.vehicle import Vehicle
from tcu.models.ecu import ECU
from tcu.dependency_manager import DependencyGraphBuilder


vehicle = Vehicle()

vehicle.add_ecu(
    ECU(
        0x201,
        "Gateway ECU",
        "1.0.0",
        "VCAN"
    )
)

vehicle.add_ecu(
    ECU(
        0x202,
        "BCM ECU",
        "1.0.0",
        "VCAN",
        dependencies=["Gateway ECU"]
    )
)

vehicle.add_ecu(
    ECU(
        0x203,
        "Cluster ECU",
        "1.0.0",
        "VCAN",
        dependencies=["BCM ECU"]
    )
)

builder = DependencyGraphBuilder()

graph = builder.build(vehicle)

graph.print_graph()
