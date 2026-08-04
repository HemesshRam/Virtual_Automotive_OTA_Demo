import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tcu.campaign_manager import CampaignManager
from tcu.dynamic_update_planner import DynamicUpdatePlanner
from tcu.firmware_compatibility import FirmwareCompatibilityValidator
from tcu.compatibility.validator import CompatibilityValidator
from tcu.ecu_discovery import ECUDiscovery


def main() -> int:
    parser = argparse.ArgumentParser(description="Show dynamic OTA update plan")
    parser.add_argument(
        "--campaign",
        default="campaigns/campaign_v1.json",
        help="Campaign JSON path",
    )
    parser.add_argument(
        "--transport",
        default="DOIP",
        choices=["DOIP", "VCAN", "doip", "vcan"],
        help="Transport used for live discovery",
    )
    args = parser.parse_args()

    campaign = CampaignManager.load_campaign(args.campaign)
    campaign.transport = args.transport.upper()

    vehicle = ECUDiscovery().discover(transport=campaign.transport)

    if not CompatibilityValidator().validate(vehicle, campaign):
        print("Campaign compatibility rejected before planning")
        return 1

    eligible_updates = FirmwareCompatibilityValidator().validate(vehicle, campaign)
    planner = DynamicUpdatePlanner()
    plan = planner.plan(vehicle, campaign, eligible_updates)
    planner.print_report(plan, vehicle, campaign)

    return 0 if plan.executable else 1


if __name__ == "__main__":
    raise SystemExit(main())
