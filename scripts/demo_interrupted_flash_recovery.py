#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ecus.base.ecu_state import ECUState
from ecus.base.flash_memory import FlashMemoryEmulator
from ecus.base.reboot_manager import RebootManager
from ecus.base.slot_manager import SlotManager
from ecus.base.version_manager import VersionManager


def main():
    ecu_key = "recoverydemo"
    ecu_root = Path("ecus") / ecu_key
    if ecu_root.exists():
        shutil.rmtree(ecu_root)

    downloads = ecu_root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    (downloads / "fw.bin").write_bytes(b"interrupted-demo")

    slot_manager = SlotManager(ecu_key)
    version_manager = VersionManager(ecu_key)
    pending_slot, _ = slot_manager.stage_firmware(downloads / "fw.bin", "fw.bin")
    slot_manager.mark_pending(pending_slot, "fw.bin", "2.0.0")
    version_manager.set_pending_version("2.0.0", pending_slot=pending_slot)

    flash = FlashMemoryEmulator(
        slot_manager.slot_path(pending_slot),
        base_address=0x08000000,
        partition_size=4096,
    )
    flash.initialize()
    flash.update_journal("PROGRAMMED", {"note": "simulated interrupted flashing"})

    print("Before reboot")
    print(f"  pending_slot={pending_slot}")
    print(f"  journal_state={flash.load_journal().get('state')}")
    print(f"  current_version={version_manager.get_current_version()}")

    ecu_state = ECUState(ecu_key, current_version=version_manager.get_current_version())
    RebootManager(
        ecu_state,
        version_manager=version_manager,
        slot_manager=slot_manager,
    ).reboot()

    print("After reboot")
    print(f"  current_version={version_manager.get_current_version()}")
    print(f"  active_slot={slot_manager.active_slot()}")
    print(f"  rollback_reason={version_manager._load().get('rollback_reason')}")


if __name__ == "__main__":
    main()
