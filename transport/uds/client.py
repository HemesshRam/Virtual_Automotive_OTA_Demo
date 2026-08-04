from transport.uds.flash_manager import FlashManager


class UDSClient:

    def __init__(self, transport):
        self.transport = transport
        self.flash = FlashManager(transport)

    def flash_firmware(self, firmware):

        self.flash.enter_programming()

        if not self.flash.erase_memory(len(firmware)):
            raise RuntimeError("Erase routine failed")

        if not self.flash.request_download(len(firmware)):
            raise RuntimeError("Request download rejected")

        if not self.flash.transfer_data(firmware):
            raise RuntimeError("Transfer data failed")

        if not self.flash.transfer_exit():
            raise RuntimeError("Request transfer exit failed")

        if not self.flash.ecu_reset():
            raise RuntimeError("ECU reset failed")

        if hasattr(self.transport, "wait_for_boot"):
            if not self.transport.wait_for_boot():
                raise RuntimeError("Post-reset boot confirmation failed")

        current_package = getattr(self.transport, "current_package", None)

        if hasattr(self.transport, "read_software_version") and current_package:
            actual_version = self.transport.read_software_version(timeout=5.0)
            target_version = current_package["target_version"]
            if actual_version != target_version:
                raise RuntimeError(
                    "Post-reset version readback mismatch: "
                    f"expected {target_version}, got {actual_version}"
                )

        return True
