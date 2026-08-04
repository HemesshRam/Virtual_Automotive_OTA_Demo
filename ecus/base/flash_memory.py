import hashlib
import json
import os
from pathlib import Path


class FlashMemoryEmulator:
    """
    File-backed flash partition emulator for one ECU slot.

    The slot file models NOR flash semantics closely enough for the demo:
    - erased bytes read as 0xFF
    - erase happens in sectors
    - programming happens in pages
    - bits may only transition from 1 -> 0 between erases
    """

    ERASED_BYTE = 0xFF
    PAGE_SIZE = 256
    SECTOR_SIZE = 4096

    def __init__(
        self,
        slot_directory: str | Path,
        base_address: int,
        partition_size: int,
        page_size: int = PAGE_SIZE,
        sector_size: int = SECTOR_SIZE,
    ):
        self.slot_directory = Path(slot_directory)
        self.base_address = base_address
        self.partition_size = partition_size
        self.page_size = page_size
        self.sector_size = sector_size
        self.flash_file = self.slot_directory / "flash_memory.bin"
        self.layout_file = self.slot_directory / "flash_layout.json"
        self.journal_file = self.slot_directory / "flash_journal.json"
        self.control_block_file = self.slot_directory / "activation_control.json"

    def initialize(self):
        os.makedirs(self.slot_directory, exist_ok=True)
        with open(self.flash_file, "wb") as fp:
            fp.write(bytes([self.ERASED_BYTE]) * self.partition_size)
        self._save_layout(
            {
                "base_address": f"0x{self.base_address:08X}",
                "partition_size": self.partition_size,
                "page_size": self.page_size,
                "sector_size": self.sector_size,
                "last_programmed_address": "",
                "last_programmed_size": 0,
                "last_chunk_sha256": "",
                "payload_sha256": "",
            }
        )
        self.update_journal("INITIALIZED")
        self.write_control_block(
            {
                "bootable": False,
                "confirmed": False,
                "active": False,
                "rollback_reason": "",
            }
        )

    def erase_region(self, address: int, size: int):
        start_offset = self._offset(address)
        end_offset = self._offset(address + size)

        erase_start = (start_offset // self.sector_size) * self.sector_size
        erase_end = ((end_offset + self.sector_size - 1) // self.sector_size) * self.sector_size
        erase_end = min(self.partition_size, erase_end)

        with open(self.flash_file, "r+b") as fp:
            fp.seek(erase_start)
            fp.write(bytes([self.ERASED_BYTE]) * (erase_end - erase_start))
        self.update_journal(
            "ERASED",
            {
                "erase_start": f"0x{address:08X}",
                "erase_size": size,
            },
        )

    def program(self, address: int, payload: bytes):
        start_offset = self._offset(address)
        end_offset = start_offset + len(payload)
        if end_offset > self.partition_size:
            raise ValueError("Flash write exceeds partition size")

        with open(self.flash_file, "r+b") as fp:
            for page_offset in range(0, len(payload), self.page_size):
                chunk = payload[page_offset:page_offset + self.page_size]
                offset = start_offset + page_offset
                fp.seek(offset)
                existing = fp.read(len(chunk))
                programmed = bytearray()

                for current, new_value in zip(existing, chunk):
                    if (current | new_value) != current:
                        raise ValueError(
                            "Flash programming attempted to set erased bits back to 1"
                        )
                    programmed.append(current & new_value)

                fp.seek(offset)
                fp.write(programmed)

        layout = self._load_layout()
        layout["last_programmed_address"] = f"0x{address:08X}"
        layout["last_programmed_size"] = len(payload)
        layout["last_chunk_sha256"] = hashlib.sha256(payload).hexdigest()
        self._save_layout(layout)
        self.update_journal(
            "PROGRAMMED",
            {
                "program_address": f"0x{address:08X}",
                "program_size": len(payload),
                "last_chunk_sha256": layout["last_chunk_sha256"],
            },
        )

    def read(self, address: int, size: int) -> bytes:
        offset = self._offset(address)
        if offset + size > self.partition_size:
            raise ValueError("Flash read exceeds partition size")
        with open(self.flash_file, "rb") as fp:
            fp.seek(offset)
            return fp.read(size)

    def verify(self, address: int, payload: bytes) -> bool:
        return self.read(address, len(payload)) == payload

    def sha256(self, address: int, size: int) -> str:
        return hashlib.sha256(self.read(address, size)).hexdigest()

    def update_journal(self, state: str, extra: dict | None = None):
        journal = {
            "state": state,
            "base_address": f"0x{self.base_address:08X}",
            "partition_size": self.partition_size,
        }
        if extra:
            journal.update(extra)
        with open(self.journal_file, "w", encoding="utf-8") as fp:
            json.dump(journal, fp, indent=4)

    def load_journal(self) -> dict:
        if not self.journal_file.exists():
            return {}
        with open(self.journal_file, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def write_control_block(self, fields: dict):
        control = self.read_control_block()
        control.update(fields)
        control.setdefault("base_address", f"0x{self.base_address:08X}")
        control.setdefault("partition_size", self.partition_size)
        with open(self.control_block_file, "w", encoding="utf-8") as fp:
            json.dump(control, fp, indent=4)

    def record_payload_metadata(self, address: int, payload: bytes):
        layout = self._load_layout()
        layout["payload_sha256"] = hashlib.sha256(payload).hexdigest()
        layout["payload_size"] = len(payload)
        layout["payload_address"] = f"0x{address:08X}"
        self._save_layout(layout)

    def read_control_block(self) -> dict:
        if not self.control_block_file.exists():
            return {}
        with open(self.control_block_file, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def _offset(self, address: int) -> int:
        offset = address - self.base_address
        if offset < 0:
            raise ValueError("Flash address precedes emulated base address")
        return offset

    def _load_layout(self) -> dict:
        if not self.layout_file.exists():
            return {}
        with open(self.layout_file, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def _save_layout(self, data: dict):
        with open(self.layout_file, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=4)
