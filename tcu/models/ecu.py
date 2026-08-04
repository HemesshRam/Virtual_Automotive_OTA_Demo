from dataclasses import dataclass, field
from typing import List

from common.utils import normalize_transport
from common.utils import normalize_version
from common.utils import parse_version


@dataclass
class ECU:
    """
    Runtime representation of an ECU inside the Vehicle Digital Twin.
    """

    ecu_id: int
    ecu_name: str

    current_version: str

    transport: str

    can_channel: str = ""

    dependencies: List[str] = field(default_factory=list)

    # -------- Compatibility Information --------

    hardware_variant: str = "GENERIC"

    bootloader_version: str = "1.0.0"

    rollback_supported: bool = True

    # -------- OTA Runtime Information --------

    target_version: str = ""

    state: str = "READY"

    health: str = "HEALTHY"

    flash_size: int = 4096

    security_level: str = "LEVEL1"

    update_status: str = "NOT_STARTED"

    def is_ready(self):
        return self.state == "READY"

    def is_healthy(self):
        return self.health == "HEALTHY"

    def __str__(self):
        return (
            f"{self.ecu_name} "
            f"(0x{self.ecu_id:X}) "
            f"Version={self.current_version}"
        )

    @property
    def current_version_semver(self):
        return parse_version(self.current_version)

    @property
    def bootloader_version_semver(self):
        return parse_version(self.bootloader_version)

    @property
    def transport_normalized(self):
        return normalize_transport(self.transport)

    def set_current_version(self, version: str):
        self.current_version = normalize_version(version)

    def set_bootloader_version(self, version: str):
        self.bootloader_version = normalize_version(version)
