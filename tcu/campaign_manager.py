import json

from tcu.models.campaign import Campaign
from tcu.models.campaign import CampaignTarget


class CampaignManager:

    @staticmethod
    def load_campaign(path: str):

        with open(path, "r", encoding="utf-8") as file:

            data = json.load(file)

        targets = []

        for item in data["targets"]:

            targets.append(

                CampaignTarget(

                    ecu_name=item["ecu_name"],

                    target_version=item["target_version"],

                    minimum_supported_version=item["minimum_supported_version"],

                    hardware_variant=item["hardware_variant"],

                    minimum_bootloader=item["minimum_bootloader"],

                    mandatory=item["mandatory"],

                    priority=item["priority"],

                    requires_reboot=item["requires_reboot"],

                    skip_if_unavailable=item.get("skip_if_unavailable", False),

                    skip_if_incompatible=item.get("skip_if_incompatible", False),

                )
            )

        return Campaign(

            campaign_id=data["campaign_id"],

            vehicle_model=data["vehicle_model"],

            release_version=data["release_version"],

            priority=data["priority"],

            transport=data["transport"],

            rollback_enabled=data["rollback_enabled"],

            created_by=data["created_by"],

            targets=targets,

            dependency_overrides={
                ecu_name: list(dependencies)
                for ecu_name, dependencies in data.get(
                    "dependency_overrides",
                    {},
                ).items()
            }
        )
