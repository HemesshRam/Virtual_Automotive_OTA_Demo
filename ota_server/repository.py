import os
from pathlib import Path

from common.active_scenario import active_campaign_path
from ota_server.config import CAMPAIGN_FOLDER
from ota_server.config import FIRMWARE_FOLDER

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_CAMPAIGN_POINTER = PROJECT_ROOT / "runtime" / "scenarios" / "active_campaign_path.txt"


class OTARepository:

    @staticmethod
    def campaign():
        configured = os.getenv("OTA_CAMPAIGN_FILE", "").strip()
        if configured:
            return Path(configured)
        canonical = active_campaign_path()
        if canonical:
            return Path(canonical)
        if SERVER_CAMPAIGN_POINTER.exists():
            pointer_path = SERVER_CAMPAIGN_POINTER.read_text(encoding="utf-8").strip()
            if pointer_path:
                return Path(pointer_path)
        return CAMPAIGN_FOLDER / "campaign_v1.json"

    @staticmethod
    def firmware(filename):

        return FIRMWARE_FOLDER / filename
