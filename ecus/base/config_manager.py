import json
from pathlib import Path

from ecus.base.version_manager import VersionManager


class ConfigManager:
    """
    Loads and manages ECU configuration and version information.
    """

    def __init__(self, ecu_directory: str):
        self.ecu_directory = Path(ecu_directory)
        self.ecu_key = self.ecu_directory.name

        self.config_path = self.ecu_directory / "config.json"

        self.config = self._load_json(self.config_path)
        self.version_manager = VersionManager(self.ecu_key)

    @staticmethod
    def _load_json(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    @property
    def ecu_name(self):
        return self.config["ecu_name"]

    @property
    def ecu_id(self):
        return self.config["ecu_id"]

    @property
    def transport(self):
        return self.config["transport"]

    @property
    def dependencies(self):
        return self.config.get("dependencies", [])

    @property
    def dependency(self):
        return self.dependencies

    @property
    def current_version(self):
        return self.version_manager.get_current_version()

    def update_version(self, new_version: str):
        return self.version_manager.update_version(new_version)
