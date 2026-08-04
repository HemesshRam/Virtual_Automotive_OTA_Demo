import os
import time
from pathlib import Path

from ecus.base.flash_memory import FlashMemoryEmulator
from ecus.base.version_manager import VersionManager
from ecus.base.ecu_state import ECUState
from ecus.base.reboot_manager import RebootManager
from ecus.base.slot_manager import SlotManager
from firmware.image_format import extract_firmware_payload


class FirmwareInstaller:

    @staticmethod
    def install(ecu_name, firmware_file, target_version="2.0.0"):

        repo_root = Path(__file__).resolve().parents[2]

        download_path = repo_root / "ecus" / ecu_name / "downloads" / firmware_file

        install_path = repo_root / "ecus" / ecu_name / "installed" / firmware_file

        version_manager = VersionManager(ecu_name)
        slot_manager = SlotManager(ecu_name)

        ecu_state = ECUState(
            ecu_name=ecu_name,
            current_version=version_manager.get_current_version(),
        )

        print()
        print("=" * 60)
        print("FIRMWARE INSTALLATION")
        print("=" * 60)
        ecu_state.firmware_status = "PROGRAMMING"

        #
        # Step 1
        #

        print("\nPreparing Flash Memory...")
        time.sleep(1)

        if install_path.exists():
            os.remove(install_path)

        print("Flash Erase Completed")

        #
        # Step 2
        #

        print()
        print("Programming Firmware...")

        if not download_path.exists():
            raise FileNotFoundError(
                f"Downloaded firmware not found: {download_path}"
            )

        image_bytes = download_path.read_bytes()
        image_metadata, payload = extract_firmware_payload(image_bytes)

        pending_slot = slot_manager.inactive_slot()
        slot_directory = slot_manager.slot_path(pending_slot)
        # Use larger page size for large payloads to avoid
        # hundreds-of-thousands of tiny file I/O operations.
        large_payload = image_metadata.payload_size > 1_000_000
        flash_page_size = 65536 if large_payload else FlashMemoryEmulator.PAGE_SIZE
        partition_size = max(
            FlashMemoryEmulator.SECTOR_SIZE,
            (
                (image_metadata.payload_size + FlashMemoryEmulator.SECTOR_SIZE - 1)
                // FlashMemoryEmulator.SECTOR_SIZE
            ) * FlashMemoryEmulator.SECTOR_SIZE,
        )

        flash = FlashMemoryEmulator(
            slot_directory=slot_directory,
            base_address=image_metadata.flash_address,
            partition_size=partition_size,
            page_size=flash_page_size,
        )
        flash.initialize()
        flash.update_journal(
            "PREPARED",
            {
                "firmware_file": firmware_file,
                "target_version": target_version,
            },
        )
        flash.erase_region(
            image_metadata.flash_address,
            image_metadata.payload_size,
        )

        sleep_interval = 0.001 if large_payload else 0.03
        last_milestone = -1

        for index in range(0, len(payload), flash.page_size):
            chunk = payload[index:index + flash.page_size]
            flash.program(image_metadata.flash_address + index, chunk)
            progress = min(100, ((index + len(chunk)) * 100) // len(payload))
            milestone = progress // 5
            if milestone > last_milestone:
                last_milestone = milestone
                print("█", end="", flush=True)
                time.sleep(sleep_interval)

        print(" 100%")

        pending_slot, slot_image_path = slot_manager.stage_firmware(
            download_path,
            firmware_file,
        )
        flash.write_control_block(
            {
                "ecu_name": ecu_name,
                "slot": pending_slot,
                "firmware_file": firmware_file,
                "target_version": target_version,
                "flash_address": f"0x{image_metadata.flash_address:08X}",
                "payload_size": image_metadata.payload_size,
                "payload_sha256": image_metadata.payload_sha256,
                "image_format": image_metadata.image_format,
                "build_number": image_metadata.build_number,
                "bootable": True,
                "confirmed": False,
                "active": False,
                "rollback_reason": "",
            }
        )
        slot_manager.mark_pending(
            pending_slot,
            firmware_file,
            target_version,
        )
        version_manager.set_pending_version(
            target_version,
            pending_slot=pending_slot,
        )
        ecu_state.pending_slot = pending_slot
        ecu_state.firmware_status = "VERIFYING"

        #
        # Step 3
        #

        print()
        print("Verifying Flash...")
        time.sleep(1)

        if not flash.verify(image_metadata.flash_address, payload):
            raise RuntimeError("Flash readback verification failed")
        if flash.sha256(image_metadata.flash_address, len(payload)) != image_metadata.payload_sha256:
            raise RuntimeError("Flash payload SHA256 verification failed")
        flash.record_payload_metadata(image_metadata.flash_address, payload)
        flash.update_journal(
            "VERIFIED",
            {
                "verify_address": f"0x{image_metadata.flash_address:08X}",
                "verify_size": image_metadata.payload_size,
                "payload_sha256": image_metadata.payload_sha256,
            },
        )

        print("Verification Successful")
        print(f"Flash Address   : 0x{image_metadata.flash_address:08X}")
        print(f"Payload Size    : {image_metadata.payload_size} bytes")
        print(f"Page Size       : {flash.page_size} bytes")
        print(f"Sector Size     : {flash.sector_size} bytes")

        #
        # Step 4
        #

        old_version = version_manager.get_current_version()
        ecu_state.current_version = old_version
        ecu_state.firmware_status = "PENDING_REBOOT"

        print(f"Current Version : {old_version}")
        print(f"Pending Version : {target_version}")
        print(f"Pending Slot    : {pending_slot}")

        ecu_state.last_install_result = "PENDING_COMMIT"
        flash.update_journal(
            "PENDING_ACTIVATION",
            {
                "pending_slot": pending_slot,
                "target_version": target_version,
            },
        )

        #
        # Step 5
        #

        reboot = RebootManager(
            ecu_state,
            version_manager=version_manager,
            slot_manager=slot_manager,
        )

        reboot.reboot()

        print("Firmware Installed To Inactive Slot")

        print()
        print(f"Staged Firmware    : {slot_image_path}")
        print(f"Legacy Install Path: {install_path}")

        print("=" * 60)

        return True
