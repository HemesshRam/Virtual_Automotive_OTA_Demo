from tcu.campaign_manager import CampaignManager
from tcu.validation.campaign_validator import CampaignValidator

campaign = CampaignManager.load_campaign(
    "campaigns/campaign_v1.json"
)

validator = CampaignValidator()

validator.validate(campaign)