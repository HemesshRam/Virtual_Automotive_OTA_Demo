from tcu.models.campaign import Campaign
from common.utils import normalize_transport


class CampaignValidator:

    SUPPORTED_TRANSPORTS = {"VCAN", "CAN", "DOIP", "ETHERNET"}

    def validate(self, campaign: Campaign) -> bool:

        print()
        print("=" * 55)
        print("CAMPAIGN VALIDATION")
        print("=" * 55)

        valid = True

        # Campaign ID
        if campaign.campaign_id:
            print("✓ Campaign ID")
        else:
            print("✗ Campaign ID Missing")
            valid = False

        # Vehicle Model
        if campaign.vehicle_model:
            print("✓ Vehicle Model")
        else:
            print("✗ Vehicle Model Missing")
            valid = False

        # Release Version
        if campaign.release_version:
            print("✓ Release Version")
        else:
            print("✗ Release Version Missing")
            valid = False

        # Targets
        if len(campaign.targets) == 0:
            print("✗ No Target ECUs")
            valid = False
        else:
            print(f"✓ Target ECUs : {len(campaign.targets)}")

        # Transport
        transport = normalize_transport(campaign.transport)

        if transport in self.SUPPORTED_TRANSPORTS:
            print(f"✓ Transport : {transport}")
        else:
            print(f"✗ Unsupported Transport : {campaign.transport}")
            valid = False

        ecu_names = set()
        priorities = set()

        for target in campaign.targets:

            if target.ecu_name in ecu_names:
                print(f"✗ Duplicate ECU : {target.ecu_name}")
                valid = False
            else:
                ecu_names.add(target.ecu_name)

            if target.priority in priorities:
                print(f"✗ Duplicate Priority : {target.priority}")
                valid = False
            else:
                priorities.add(target.priority)

            if not target.target_version:
                print(f"✗ Missing Target Version : {target.ecu_name}")
                valid = False

            if not target.minimum_supported_version:
                print(f"✗ Missing Minimum Supported Version : {target.ecu_name}")
                valid = False

            if not target.minimum_bootloader:
                print(f"✗ Missing Minimum Bootloader : {target.ecu_name}")
                valid = False

        print()

        if valid:
            print("CAMPAIGN VALIDATION PASSED")
        else:
            print("CAMPAIGN VALIDATION FAILED")

        print("=" * 55)

        return valid
