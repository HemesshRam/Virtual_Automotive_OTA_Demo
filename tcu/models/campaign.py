from dataclasses import dataclass, field
from typing import List


@dataclass
class CampaignTarget:

    ecu_name: str

    target_version: str

    minimum_supported_version: str

    hardware_variant: str

    minimum_bootloader: str

    mandatory: bool

    priority: int

    requires_reboot: bool

    skip_if_unavailable: bool = False

    skip_if_incompatible: bool = False


@dataclass
class Campaign:

    campaign_id: str

    vehicle_model: str

    release_version: str

    priority: str

    transport: str

    rollback_enabled: bool

    created_by: str

    targets: List[CampaignTarget]

    dependency_overrides: dict[str, list[str]] = field(default_factory=dict)
