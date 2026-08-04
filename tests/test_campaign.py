from tcu.campaign_manager import CampaignManager


campaign = CampaignManager.load_campaign(
    "campaigns/campaign_v1.json"
)

print()

print("=" * 45)
print("CAMPAIGN INFORMATION")
print("=" * 45)

print()

print("Campaign ID :", campaign.campaign_id)

print("Vehicle     :", campaign.vehicle_model)

print("Release     :", campaign.release_version)

print("Transport   :", campaign.transport)

print("Rollback    :", campaign.rollback_enabled)

print()

print("=" * 45)
print("TARGET ECUS")
print("=" * 45)

for target in campaign.targets:

    print()

    print("ECU :", target.ecu_name)

    print("Target Version :", target.target_version)

    print("Priority :", target.priority)

    print("Mandatory :", target.mandatory)

    print("Reboot :", target.requires_reboot)