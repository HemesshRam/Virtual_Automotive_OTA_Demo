import time

from tcu.ecu_discovery import ECUDiscovery
from tcu.status_reporter import reporter
from common.utils import version_eq
from ecus.base.slot_manager import SlotManager
from ecus.base.version_manager import VersionManager


class PostInstallValidator:
    """
    Post-Installation Validator

    Re-discovers all ECUs after OTA installation and
    validates that all target versions are running.
    """

    INITIAL_WAIT_SECONDS = 3
    VALIDATION_TIMEOUT_SECONDS = 20
    POLL_INTERVAL_SECONDS = 2

    def validate(self, campaign, transport="VCAN"):

        #
        # Wait for ECU reboots
        #

        print()
        print("Waiting for ECUs to restart...")
        time.sleep(self.INITIAL_WAIT_SECONDS)

        #
        # Post Installation Discovery
        #

        print()
        print("=" * 70)
        print("POST INSTALLATION VALIDATION")
        print("=" * 70)

        #
        # Build target version map from campaign
        #

        approved_targets = set(getattr(campaign, "approved_targets", []))
        skipped_targets = dict(getattr(campaign, "skipped_optional_targets", []))

        if approved_targets:
            validation_target_names = approved_targets
        else:
            validation_target_names = {
                target.ecu_name
                for target in campaign.targets
                if target.ecu_name not in skipped_targets
            }

        target_versions = {}

        for target in campaign.targets:

            if target.ecu_name not in validation_target_names:
                continue

            target_versions[target.ecu_name] = target.target_version

        campaign_id = getattr(campaign, "campaign_id", None)

        updated_vehicle = self._wait_for_expected_versions(
            target_versions,
            transport=transport,
        )

        #
        # Validate each ECU
        #

        print()

        all_updated = True

        results = []

        for ecu in updated_vehicle.get_all_ecus():

            expected = target_versions.get(ecu.ecu_name)

            if expected is None:
                skipped_reason = skipped_targets.get(ecu.ecu_name, "NOT_TARGETED")
                print(
                    f"{ecu.ecu_name:<15} "
                    f"Version : {ecu.current_version:<10} "
                    f"SKIPPED ({skipped_reason})"
                )
                continue

            actual = ecu.current_version

            passed = version_eq(actual, expected)

            status = "PASS" if passed else "FAIL"

            results.append(
                (ecu.ecu_name, actual, status)
            )

            print(
                f"{ecu.ecu_name:<15} "
                f"Version : {actual:<10} "
                f"{status}"
            )

            ecu_key = self._ecu_key(ecu.ecu_name)
            version_manager = VersionManager(ecu_key)
            slot_manager = SlotManager(ecu_key)

            if version_manager.has_pending_commit():
                if passed:
                    version_manager.confirm_version(actual)
                    slot_manager.commit_pending()
                    reporter.report(
                        ecu.ecu_name,
                        "SUCCESS",
                        100,
                        actual,
                        campaign_id=campaign_id,
                    )
                else:
                    version_manager.rollback_pending_version(
                        reason="POST_INSTALL_VALIDATION_FAILED"
                    )
                    slot_manager.rollback_pending(
                        reason="POST_INSTALL_VALIDATION_FAILED"
                    )
                    rolled_back_version = version_manager.get_current_version()
                    reporter.report(
                        ecu.ecu_name,
                        "ROLLBACK",
                        100,
                        rolled_back_version,
                        campaign_id=campaign_id,
                        error="POST_INSTALL_VALIDATION_FAILED",
                    )

            if not passed:
                all_updated = False

        #
        # Final Result
        #

        print()

        if all_updated:

            print("=" * 70)
            print("OTA UPDATE VERIFIED SUCCESSFULLY")
            print("ALL ECUs ARE NOW RUNNING SOFTWARE VERSION "
                  f"{campaign.release_version}")
            print("=" * 70)

        else:

            print("=" * 70)
            print("POST UPDATE VALIDATION FAILED")
            print("=" * 70)

        return all_updated

    def _wait_for_expected_versions(self, target_versions, transport):

        deadline = time.time() + self.VALIDATION_TIMEOUT_SECONDS
        latest_vehicle = None
        attempt = 1

        while True:
            latest_vehicle = ECUDiscovery().discover(transport=transport)

            if self._all_targets_running(latest_vehicle, target_versions):
                return latest_vehicle

            if time.time() >= deadline:
                return latest_vehicle

            print()
            print(
                f"Post-install validation retry {attempt}: "
                f"waiting for pending ECUs to boot..."
            )
            attempt += 1
            time.sleep(self.POLL_INTERVAL_SECONDS)

    @staticmethod
    def _all_targets_running(vehicle, target_versions):
        for ecu in vehicle.get_all_ecus():
            expected = target_versions.get(ecu.ecu_name)
            if expected is None:
                continue
            if not version_eq(ecu.current_version, expected):
                return False
        return True

    @staticmethod
    def _ecu_key(ecu_name: str) -> str:
        normalized = ecu_name.lower()
        if "gateway" in normalized:
            return "gateway"
        if "cluster" in normalized:
            return "cluster"
        if "bcm" in normalized:
            return "bcm"
        return normalized.split()[0]
