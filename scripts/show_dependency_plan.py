#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tcu.campaign_manager import CampaignManager
from tcu.dependency_manager import DependencyGraphBuilder, TopologicalUpdatePlanner
from tcu.models.ecu import ECU


def main():
    campaign_path = sys.argv[1] if len(sys.argv) > 1 else "campaigns/campaign_v1.json"
    campaign = CampaignManager.load_campaign(campaign_path)
    ecus = [
        ECU(
            ecu_id=0x200 + index,
            ecu_name=target.ecu_name,
            current_version="1.0.0",
            transport=campaign.transport,
        )
        for index, target in enumerate(campaign.targets, start=1)
    ]
    priority = {
        target.ecu_name: target.priority
        for target in campaign.targets
    }

    builder = DependencyGraphBuilder()
    errors = builder.validate_campaign_dependencies(ecus, campaign=campaign)
    if errors:
        print("Dependency graph validation failed.")
        for error in errors:
            print(f"[FAIL] {error}")
        raise SystemExit(1)

    graph = builder.build(ecus, campaign=campaign)

    print()
    print("=" * 60)
    print("CAMPAIGN DEPENDENCY PLAN")
    print("=" * 60)
    print(f"Campaign : {campaign.campaign_id}")
    print(f"Source   : {campaign_path}")
    print()
    print("Dependency overrides:")
    if campaign.dependency_overrides:
        for ecu_name, dependencies in campaign.dependency_overrides.items():
            depends_on = ", ".join(dependencies) if dependencies else "None"
            print(f"- {ecu_name} depends_on={depends_on}")
    else:
        print("- None, using vehicle topology defaults")

    graph.print_graph()
    update_order = TopologicalUpdatePlanner().plan(graph, priority=priority)
    TopologicalUpdatePlanner().print_update_order(update_order)


if __name__ == "__main__":
    main()
