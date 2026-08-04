import json
import os
from pathlib import Path

from common.utils import normalize_version


class VersionManager:

    def __init__(self, ecu_name):

        self.version_file = Path(
            "ecus",
            ecu_name,
            "version.json",
        )

    @staticmethod
    def _default_state():
        return {
            "current_version": "1.0.0",
            "confirmed_version": "1.0.0",
            "pending_version": "",
            "active_slot": "A",
            "confirmed_slot": "A",
            "pending_slot": "",
            "pending_commit": False,
            "boot_attempts": 0,
            "last_boot_outcome": "CONFIRMED",
            "rollback_reason": "",
        }

    def get_current_version(self):
        return self._load().get("current_version", "1.0.0")

    def get_confirmed_version(self):
        return self._load().get("confirmed_version", "1.0.0")

    def update_version(self, new_version):

        normalized = normalize_version(new_version)
        data = self._load()
        data["current_version"] = normalized
        data["confirmed_version"] = normalized
        data["pending_version"] = ""
        data["pending_slot"] = ""
        data["pending_commit"] = False
        data["boot_attempts"] = 0
        data["last_boot_outcome"] = "CONFIRMED"
        data["rollback_reason"] = ""

        os.makedirs(self.version_file.parent, exist_ok=True)

        with open(self.version_file, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
            )

        return True

    def set_pending_version(self, version, pending_slot: str = ""):

        normalized = normalize_version(version)
        data = self._load()
        data["pending_version"] = normalized
        if pending_slot:
            data["pending_slot"] = pending_slot
            data["pending_commit"] = True
        data["boot_attempts"] = 0
        data["last_boot_outcome"] = "PENDING_REBOOT"
        data["rollback_reason"] = ""
        self._save(data)
        return True

    def confirm_version(self, version):

        normalized = normalize_version(version)
        data = self._load()
        data["current_version"] = normalized
        data["confirmed_version"] = normalized
        data["pending_version"] = ""
        data["active_slot"] = data.get("pending_slot") or data.get("active_slot", "A")
        data["confirmed_slot"] = data["active_slot"]
        data["pending_slot"] = ""
        data["pending_commit"] = False
        data["boot_attempts"] = 0
        data["last_boot_outcome"] = "CONFIRMED"
        data["rollback_reason"] = ""
        self._save(data)
        return True

    def boot_pending_version(self):
        data = self._load()
        pending = data.get("pending_version", "")
        if not pending:
            return False

        data["current_version"] = pending
        data["active_slot"] = data.get("pending_slot") or data.get("active_slot", "A")
        data["pending_commit"] = True
        data["boot_attempts"] = int(data.get("boot_attempts", 0)) + 1
        data["last_boot_outcome"] = "PENDING_COMMIT"
        self._save(data)
        return True

    def rollback_pending_version(self, reason="POST_INSTALL_VALIDATION_FAILED"):
        data = self._load()
        data["current_version"] = data.get("confirmed_version", "1.0.0")
        data["pending_version"] = ""
        data["pending_slot"] = ""
        data["active_slot"] = data.get("confirmed_slot", "A")
        data["pending_commit"] = False
        data["boot_attempts"] = 0
        data["last_boot_outcome"] = "ROLLED_BACK"
        data["rollback_reason"] = reason
        self._save(data)
        return True

    def has_pending_commit(self):
        return bool(self._load().get("pending_commit", False))

    def _load(self):

        if not self.version_file.exists():
            return self._default_state()

        try:
            with open(self.version_file, "r", encoding="utf-8") as file:
                loaded = json.load(file)
                state = self._default_state()
                state.update(loaded)
                return state
        except (json.JSONDecodeError, OSError):
            return self._default_state()

    def _save(self, data):

        os.makedirs(self.version_file.parent, exist_ok=True)

        with open(self.version_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
