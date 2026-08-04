import shutil
import unittest
from pathlib import Path

from ecus.base.ecu_state import ECUState
from ecus.base.flash_memory import FlashMemoryEmulator
from ecus.base.reboot_manager import RebootManager
from ecus.base.slot_manager import SlotManager
from ecus.base.version_manager import VersionManager


class SlotSemanticsTest(unittest.TestCase):

    def setUp(self):
        self.ecu_root = Path("ecus/testslot")
        if self.ecu_root.exists():
            shutil.rmtree(self.ecu_root)
        (self.ecu_root / "downloads").mkdir(parents=True, exist_ok=True)
        (self.ecu_root / "downloads" / "fw.bin").write_bytes(b"demo")

    def tearDown(self):
        if self.ecu_root.exists():
            shutil.rmtree(self.ecu_root)

    def test_pending_boot_then_commit(self):
        slot_manager = SlotManager("testslot")
        version_manager = VersionManager("testslot")

        pending_slot, image_path = slot_manager.stage_firmware(
            self.ecu_root / "downloads" / "fw.bin",
            "fw.bin",
        )
        slot_manager.mark_pending(pending_slot, "fw.bin", "2.0.0")
        version_manager.set_pending_version("2.0.0", pending_slot=pending_slot)

        self.assertEqual(pending_slot, "B")
        self.assertTrue(image_path.exists())
        self.assertEqual(slot_manager._load_state()["pending_slot"], "B")

        version_manager.boot_pending_version()
        slot_manager.activate_pending()

        self.assertEqual(version_manager.get_current_version(), "2.0.0")
        self.assertTrue(version_manager.has_pending_commit())

        version_manager.confirm_version("2.0.0")
        slot_manager.commit_pending()

        self.assertEqual(version_manager.get_confirmed_version(), "2.0.0")
        self.assertFalse(version_manager.has_pending_commit())
        self.assertEqual(slot_manager.active_slot(), "B")
        self.assertEqual(version_manager._load()["last_boot_outcome"], "CONFIRMED")
        self.assertEqual(slot_manager._load_state()["last_transition"], "CONFIRMED")

    def test_pending_boot_then_rollback(self):
        slot_manager = SlotManager("testslot")
        version_manager = VersionManager("testslot")

        pending_slot, _ = slot_manager.stage_firmware(
            self.ecu_root / "downloads" / "fw.bin",
            "fw.bin",
        )
        slot_manager.mark_pending(pending_slot, "fw.bin", "2.0.0")
        version_manager.set_pending_version("2.0.0", pending_slot=pending_slot)
        version_manager.boot_pending_version()
        slot_manager.activate_pending()

        version_manager.rollback_pending_version()
        slot_manager.rollback_pending()

        self.assertEqual(version_manager.get_current_version(), "1.0.0")
        self.assertEqual(version_manager.get_confirmed_version(), "1.0.0")
        self.assertEqual(slot_manager.active_slot(), "A")
        self.assertEqual(version_manager._load()["last_boot_outcome"], "ROLLED_BACK")
        self.assertEqual(
            version_manager._load()["rollback_reason"],
            "POST_INSTALL_VALIDATION_FAILED",
        )
        self.assertEqual(slot_manager._load_state()["last_transition"], "ROLLED_BACK")
        self.assertEqual(
            slot_manager._load_state()["rollback_reason"],
            "POST_INSTALL_VALIDATION_FAILED",
        )

    def test_second_boot_before_confirm_triggers_rollback(self):
        slot_manager = SlotManager("testslot")
        version_manager = VersionManager("testslot")

        pending_slot, _ = slot_manager.stage_firmware(
            self.ecu_root / "downloads" / "fw.bin",
            "fw.bin",
        )
        slot_manager.mark_pending(pending_slot, "fw.bin", "2.0.0")
        version_manager.set_pending_version("2.0.0", pending_slot=pending_slot)

        ecu_state = ECUState("testslot", current_version="1.0.0")
        reboot = RebootManager(
            ecu_state,
            version_manager=version_manager,
            slot_manager=slot_manager,
        )

        reboot.reboot()
        self.assertEqual(version_manager.get_current_version(), "2.0.0")
        self.assertTrue(version_manager.has_pending_commit())

        reboot.reboot()

        self.assertEqual(version_manager.get_current_version(), "1.0.0")
        self.assertFalse(version_manager.has_pending_commit())
        self.assertEqual(slot_manager.active_slot(), "A")
        self.assertEqual(
            version_manager._load()["rollback_reason"],
            "BOOT_ATTEMPT_LIMIT_EXCEEDED",
        )
        self.assertEqual(
            slot_manager._load_state()["rollback_reason"],
            "BOOT_ATTEMPT_LIMIT_EXCEEDED",
        )

    def test_incomplete_flash_journal_triggers_recovery_rollback(self):
        slot_manager = SlotManager("testslot")
        version_manager = VersionManager("testslot")

        pending_slot, _ = slot_manager.stage_firmware(
            self.ecu_root / "downloads" / "fw.bin",
            "fw.bin",
        )
        slot_manager.mark_pending(pending_slot, "fw.bin", "2.0.0")
        version_manager.set_pending_version("2.0.0", pending_slot=pending_slot)

        flash = FlashMemoryEmulator(
            slot_manager.slot_path(pending_slot),
            base_address=0x08000000,
            partition_size=4096,
        )
        flash.initialize()
        flash.update_journal("PROGRAMMED")

        ecu_state = ECUState("testslot", current_version="1.0.0")
        reboot = RebootManager(
            ecu_state,
            version_manager=version_manager,
            slot_manager=slot_manager,
        )

        reboot.reboot()

        self.assertEqual(version_manager.get_current_version(), "1.0.0")
        self.assertFalse(version_manager.has_pending_commit())
        self.assertEqual(slot_manager.active_slot(), "A")
        self.assertEqual(
            version_manager._load()["rollback_reason"],
            "INCOMPLETE_FLASH_JOURNAL",
        )
        self.assertEqual(
            slot_manager._load_state()["rollback_reason"],
            "INCOMPLETE_FLASH_JOURNAL",
        )


if __name__ == "__main__":
    unittest.main()
