import shutil
import unittest
from pathlib import Path

from ecus.base.flash_memory import FlashMemoryEmulator


class FlashMemoryEmulatorTest(unittest.TestCase):

    def setUp(self):
        self.slot_dir = Path("ecus/testflash/slots/B")
        if self.slot_dir.parent.parent.exists():
            shutil.rmtree(self.slot_dir.parent.parent)

    def tearDown(self):
        if self.slot_dir.parent.parent.exists():
            shutil.rmtree(self.slot_dir.parent.parent)

    def test_erase_program_and_verify(self):
        flash = FlashMemoryEmulator(
            self.slot_dir,
            base_address=0x08000000,
            partition_size=8192,
        )
        flash.initialize()

        payload = bytes(range(128))
        flash.erase_region(0x08000000, len(payload))
        flash.program(0x08000000, payload)

        self.assertTrue(flash.verify(0x08000000, payload))
        self.assertEqual(flash.read(0x08000000, len(payload)), payload)

    def test_program_without_erase_rejects_zero_to_one_flip(self):
        flash = FlashMemoryEmulator(
            self.slot_dir,
            base_address=0x08000000,
            partition_size=8192,
        )
        flash.initialize()
        flash.erase_region(0x08000000, 4)
        flash.program(0x08000000, b"\x00\x00\x00\x00")

        with self.assertRaises(ValueError):
            flash.program(0x08000000, b"\xFF\xFF\xFF\xFF")


if __name__ == "__main__":
    unittest.main()
