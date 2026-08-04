import time

from ecus.base.ecu_state import ECUState
from ecus.base.version_manager import VersionManager
from ecus.base.slot_manager import SlotManager


class RebootManager:

    def __init__(self, ecu_state: ECUState, version_manager: VersionManager | None = None, slot_manager: SlotManager | None = None):

        self.ecu_state = ecu_state
        self.version_manager = version_manager
        self.slot_manager = slot_manager

    def reboot(self):

        print()
        print("Rebooting ECU...")
        print()

        print("Power OFF")
        time.sleep(0.8)

        print("Power ON")
        time.sleep(0.8)

        print("Bootloader Starting...")
        time.sleep(0.8)

        print("Initializing Hardware...")
        time.sleep(0.8)

        print("Loading Application...")
        time.sleep(0.8)

        print("Initializing CAN Interface...")
        time.sleep(0.8)

        if (
            self.version_manager is not None
            and self.slot_manager is not None
            and self.slot_manager.pending_journal_requires_recovery()
        ):
            self.version_manager.rollback_pending_version(
                reason="INCOMPLETE_FLASH_JOURNAL"
            )
            self.slot_manager.rollback_pending(
                reason="INCOMPLETE_FLASH_JOURNAL"
            )
            self.ecu_state.current_version = self.version_manager.get_current_version()
            self.ecu_state.firmware_status = "ROLLED_BACK"
            self.ecu_state.last_install_result = "ROLLBACK"
            self.ecu_state.reboot_count += 1

            print()
            print("ECU Online")
            print(f"Software Version : {self.ecu_state.current_version}")
            print(f"Reboot Count     : {self.ecu_state.reboot_count}")
            print("Rollback Reason  : INCOMPLETE_FLASH_JOURNAL")
            print()
            return

        if (
            self.version_manager is not None
            and self.slot_manager is not None
            and self.version_manager.has_pending_commit()
            and self.slot_manager.should_rollback_pending()
        ):
            self.version_manager.rollback_pending_version(
                reason="BOOT_ATTEMPT_LIMIT_EXCEEDED"
            )
            self.slot_manager.rollback_pending(
                reason="BOOT_ATTEMPT_LIMIT_EXCEEDED"
            )
            self.ecu_state.current_version = self.version_manager.get_current_version()
            self.ecu_state.firmware_status = "ROLLED_BACK"
            self.ecu_state.last_install_result = "ROLLBACK"
            self.ecu_state.reboot_count += 1

            print()
            print("ECU Online")
            print(f"Software Version : {self.ecu_state.current_version}")
            print(f"Reboot Count     : {self.ecu_state.reboot_count}")
            print("Rollback Reason  : BOOT_ATTEMPT_LIMIT_EXCEEDED")
            print()
            return

        if self.version_manager is not None and self.version_manager.has_pending_commit():
            self.version_manager.boot_pending_version()

        if self.slot_manager is not None:
            self.slot_manager.activate_pending()

        if self.version_manager is not None:
            self.ecu_state.current_version = self.version_manager.get_current_version()

        self.ecu_state.reboot_count += 1
        self.ecu_state.firmware_status = "PENDING_COMMIT"

        print()
        print("ECU Online")
        print(f"Software Version : {self.ecu_state.current_version}")
        print(f"Reboot Count     : {self.ecu_state.reboot_count}")
        print()
