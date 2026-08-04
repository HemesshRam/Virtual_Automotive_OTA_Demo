import json
import os
import shutil
from pathlib import Path

from ecus.base.flash_memory import FlashMemoryEmulator


class SlotManager:
    SLOT_A = "A"
    SLOT_B = "B"
    INCOMPLETE_JOURNAL_STATES = {
        "INITIALIZED",
        "PREPARED",
        "ERASED",
        "PROGRAMMED",
    }

    def __init__(self, ecu_name: str):
        self.ecu_name = ecu_name
        self.ecu_root = Path("ecus", ecu_name)
        self.slots_root = self.ecu_root / "slots"
        self.state_file = self.ecu_root / "slot_state.json"

    @classmethod
    def _default_state(cls):
        return {
            "active_slot": cls.SLOT_A,
            "confirmed_slot": cls.SLOT_A,
            "previous_slot": cls.SLOT_A,
            "pending_slot": "",
            "pending_file": "",
            "pending_version": "",
            "boot_attempts": 0,
            "max_boot_attempts": 1,
            "rollback_reason": "",
            "last_transition": "INITIALIZED",
        }

    def active_slot(self) -> str:
        return self._load_state()["active_slot"]

    def inactive_slot(self) -> str:
        return self.SLOT_B if self.active_slot() == self.SLOT_A else self.SLOT_A

    def slot_path(self, slot: str) -> Path:
        return self.slots_root / slot

    def stage_firmware(self, download_path: Path, firmware_file: str) -> tuple[str, Path]:
        slot = self.inactive_slot()
        destination_dir = self.slot_path(slot)
        os.makedirs(destination_dir, exist_ok=True)
        destination = destination_dir / firmware_file

        if destination.exists():
            destination.unlink()

        shutil.move(str(download_path), str(destination))
        return slot, destination

    def mark_pending(self, slot: str, firmware_file: str, version: str):
        state = self._load_state()
        state["pending_slot"] = slot
        state["pending_file"] = firmware_file
        state["pending_version"] = version
        state["boot_attempts"] = 0
        state["rollback_reason"] = ""
        state["last_transition"] = "STAGED"
        self._save_state(state)
        self._update_control_block(
            slot,
            {
                "slot": slot,
                "firmware_file": firmware_file,
                "target_version": version,
                "bootable": True,
                "confirmed": False,
                "active": False,
                "rollback_reason": "",
            },
        )

    def activate_pending(self):
        state = self._load_state()
        pending_slot = state.get("pending_slot") or ""
        if not pending_slot:
            return None

        state["previous_slot"] = state["active_slot"]
        state["active_slot"] = pending_slot
        state["boot_attempts"] = int(state.get("boot_attempts", 0)) + 1
        state["last_transition"] = "BOOTED_PENDING"
        self._save_state(state)
        self._update_journal(
            pending_slot,
            "BOOTED_PENDING",
            {
                "boot_attempts": state["boot_attempts"],
            },
        )
        self._set_active_slot_control_blocks(pending_slot, confirmed=False)
        return pending_slot

    def commit_pending(self):
        state = self._load_state()
        state["confirmed_slot"] = state["active_slot"]
        state["pending_slot"] = ""
        state["pending_file"] = ""
        state["pending_version"] = ""
        state["boot_attempts"] = 0
        state["rollback_reason"] = ""
        state["last_transition"] = "CONFIRMED"
        self._save_state(state)
        self._update_journal(
            state["active_slot"],
            "CONFIRMED",
            {
                "confirmed_slot": state["confirmed_slot"],
            },
        )
        self._set_active_slot_control_blocks(state["active_slot"], confirmed=True)

    def rollback_pending(self, reason="POST_INSTALL_VALIDATION_FAILED"):
        state = self._load_state()
        rolled_back_slot = state.get("active_slot", self.SLOT_A)
        state["previous_slot"] = state["active_slot"]
        state["active_slot"] = state.get("confirmed_slot") or self.SLOT_A
        state["pending_slot"] = ""
        state["pending_file"] = ""
        state["pending_version"] = ""
        state["boot_attempts"] = 0
        state["rollback_reason"] = reason
        state["last_transition"] = "ROLLED_BACK"
        self._save_state(state)
        self._update_journal(
            rolled_back_slot,
            "ROLLED_BACK",
            {
                "rollback_reason": reason,
                "confirmed_slot": state["active_slot"],
            },
        )
        self._update_control_block(
            rolled_back_slot,
            {
                "bootable": False,
                "active": False,
                "confirmed": False,
                "rollback_reason": reason,
            },
        )
        self._set_active_slot_control_blocks(state["active_slot"], confirmed=True)

    def should_rollback_pending(self) -> bool:
        state = self._load_state()
        pending_slot = state.get("pending_slot") or ""
        if not pending_slot:
            return False
        return int(state.get("boot_attempts", 0)) >= int(state.get("max_boot_attempts", 1))

    def pending_journal_requires_recovery(self) -> bool:
        state = self._load_state()
        pending_slot = state.get("pending_slot") or ""
        if not pending_slot:
            return False

        journal = self._load_journal(pending_slot)
        if not journal:
            return False

        return journal.get("state") in self.INCOMPLETE_JOURNAL_STATES

    def _load_state(self):
        if not self.state_file.exists():
            state = self._default_state()
            self._save_state(state)
            return state

        with open(self.state_file, "r", encoding="utf-8") as fp:
            loaded = json.load(fp)
            state = self._default_state()
            state.update(loaded)
            return state

    def _save_state(self, state: dict):
        os.makedirs(self.state_file.parent, exist_ok=True)
        os.makedirs(self.slot_path(self.SLOT_A), exist_ok=True)
        os.makedirs(self.slot_path(self.SLOT_B), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=4)

    def _control_block_path(self, slot: str) -> Path:
        return self.slot_path(slot) / "activation_control.json"

    def _update_control_block(self, slot: str, updates: dict):
        slot_dir = self.slot_path(slot)
        layout_path = slot_dir / "flash_layout.json"
        if not layout_path.exists():
            return

        with open(layout_path, "r", encoding="utf-8") as fp:
            layout = json.load(fp)

        base_address = int(str(layout["base_address"]), 16)
        flash = FlashMemoryEmulator(
            slot_dir,
            base_address=base_address,
            partition_size=int(layout["partition_size"]),
            page_size=int(layout["page_size"]),
            sector_size=int(layout["sector_size"]),
        )
        flash.write_control_block(updates)

    def _set_active_slot_control_blocks(self, active_slot: str, confirmed: bool):
        for slot in (self.SLOT_A, self.SLOT_B):
            updates = {
                "active": slot == active_slot,
                "confirmed": confirmed if slot == active_slot else False,
            }
            if slot == active_slot:
                updates["bootable"] = True
            self._update_control_block(
                slot,
                updates,
            )

    def _update_journal(self, slot: str, state: str, updates: dict):
        slot_dir = self.slot_path(slot)
        layout_path = slot_dir / "flash_layout.json"
        if not layout_path.exists():
            return

        with open(layout_path, "r", encoding="utf-8") as fp:
            layout = json.load(fp)

        flash = FlashMemoryEmulator(
            slot_dir,
            base_address=int(str(layout["base_address"]), 16),
            partition_size=int(layout["partition_size"]),
            page_size=int(layout["page_size"]),
            sector_size=int(layout["sector_size"]),
        )
        flash.update_journal(state, updates)

    def _load_journal(self, slot: str) -> dict:
        slot_dir = self.slot_path(slot)
        journal_path = slot_dir / "flash_journal.json"
        if not journal_path.exists():
            return {}

        with open(journal_path, "r", encoding="utf-8") as fp:
            return json.load(fp)
