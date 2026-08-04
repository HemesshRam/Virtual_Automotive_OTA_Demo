from tcu.models.vehicle import Vehicle
from tcu.models.ecu import ECU


vehicle = Vehicle()

gateway = ECU(
    ecu_id=0x201,
    ecu_name="Gateway ECU",
    current_version="1.0.0",
    transport="VCAN"
)

bcm = ECU(
    ecu_id=0x202,
    ecu_name="BCM ECU",
    current_version="1.0.0",
    transport="VCAN",
    dependencies=["Gateway ECU"]
)

cluster = ECU(
    ecu_id=0x203,
    ecu_name="Cluster ECU",
    current_version="1.0.0",
    transport="VCAN",
    dependencies=["BCM ECU"]
)

vehicle.add_ecu(gateway)
vehicle.add_ecu(bcm)
vehicle.add_ecu(cluster)

vehicle.print_inventory()