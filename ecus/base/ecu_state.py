from dataclasses import dataclass


@dataclass
class ECUState:

    ecu_name: str

    current_version: str = "1.0.0"

    firmware_status: str = "ACTIVE"

    reboot_count: int = 0

    last_install_result: str = "NONE"