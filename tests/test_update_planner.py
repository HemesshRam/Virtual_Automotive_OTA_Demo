from tcu.models.vehicle import Vehicle
from tcu.models.ecu import ECU
from tcu.dependency_manager import (
    DependencyGraphBuilder,
    TopologicalUpdatePlanner,
)

vehicle = Vehicle()

vehicle.add_ecu(
    ECU(
        ecu_id=0x201,
        ecu_name="Gateway ECU",
        current_version="1.0.0",
        transport="VCAN"
    )
)

vehicle.add_ecu(
    ECU(
        ecu_id=0x202,
        ecu_name="BCM ECU",
        current_version="1.0.0",
        transport="VCAN",
        dependencies=["Gateway ECU"]
    )
)

vehicle.add_ecu(
    ECU(
        ecu_id=0x203,
        ecu_name="Cluster ECU",
        current_version="1.0.0",
        transport="VCAN",
        dependencies=["BCM ECU"]
    )
)

graph_builder = DependencyGraphBuilder()

graph = graph_builder.build(vehicle)

planner = TopologicalUpdatePlanner()

update_order = planner.plan(graph)

planner.print_update_order(update_order)
