from tcu.models.vehicle import Vehicle
from tcu.models.ecu import ECU
from tcu.campaign_manager import CampaignManager
from tcu.compatibility.validator import CompatibilityValidator


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
        transport="VCAN"
    )
)

vehicle.add_ecu(
    ECU(
        ecu_id=0x203,
        ecu_name="Cluster ECU",
        current_version="1.0.0",
        transport="VCAN"
    )
)

campaign = CampaignManager.load_campaign(
    "campaigns/campaign_v1.json"
)

validator = CompatibilityValidator()

validator.validate(vehicle, campaign)