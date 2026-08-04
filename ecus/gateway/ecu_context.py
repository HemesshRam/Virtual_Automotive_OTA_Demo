from ecus.gateway.firmware_receiver import FirmwareReceiver
from ecus.base.version_manager import VersionManager


class ECUContext:

    def __init__(
        self,
        ecu_key,
        ecu_name,
        logical_address,
        profile,
    ):

        self.ecu_key = ecu_key
        self.ecu_name = ecu_name
        self.logical_address = logical_address

        self.profile = profile

        self.version_manager = VersionManager(ecu_key)

        self.receiver = FirmwareReceiver(
            profile["download_directory"]
        )

        self.target_version = profile["target_version"]
        self.expected_download_size = 0
        self.download_received_size = 0
        self.install_pending = False
        self.install_started = False
        self.download_verified = False
        self.security_unlocked = False
        self.pending_seed = b""
        self.seed_counter = 0
        self.erase_completed = False
        self.activation_marked = False
        self.current_session = 0x00
        self.session_started_at = 0.0
        self.security_failures = 0
        self.security_locked_until = 0.0
        self.expected_transfer_sequence = 1
