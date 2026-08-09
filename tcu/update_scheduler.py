import os
import time

from tcu.transport_manager import TransportManager
from tcu.firmware_manager import FirmwareManager
from tcu.status_reporter import reporter
from tcu.dependency_policy import DependencyPolicyResolver


class UpdateScheduler:
    """
    Executes OTA updates according to the dependency order.
    """

    def __init__(self, release_directory: str, transport: str):

        self.transport = TransportManager(transport)
        self.firmware_manager = FirmwareManager(release_directory)
        self.policy_resolver = DependencyPolicyResolver()
        self.flash_retry_count = max(1, int(os.getenv("OTA_ECU_FLASH_RETRY_COUNT", "2")))
        self.inter_ecu_settle_seconds = max(
            0.0,
            float(os.getenv("OTA_INTER_ECU_SETTLE_SECONDS", "2.0")),
        )
        self.last_results = []
        self.last_campaign_result = "UNKNOWN"

    # -----------------------------------------------------

    def execute(self, eligible_updates, update_order, vehicle=None, dependency_map=None):

        print()
        print("=" * 60)
        print("OTA UPDATE EXECUTION")
        print("=" * 60)

        selected_target_names = [
            entry["ecu"].ecu_name
            for entry in eligible_updates
        ]

        if not self.firmware_manager.verify_repository(selected_target_names):

            raise RuntimeError(
                "Firmware repository verification failed."
            )

        self.firmware_manager.build_inventory(selected_target_names)
        campaign_id = self.firmware_manager.campaign_id()

        campaign_results = []
        failed_ecus = set()
        skipped_ecus = set()
        fatal_policy_abort = False
        eligible_names = {entry["ecu"].ecu_name for entry in eligible_updates}
        discovered_names = self._discovered_ecu_names(vehicle)
        completed_or_satisfied = discovered_names - eligible_names
        schedulable_names = set(update_order)
        dependency_lookup = dependency_map or {
            ecu_name: set(self.policy_resolver.for_ecu(ecu_name).dependencies)
            for ecu_name in schedulable_names
        }

        print()

        for ecu_name in update_order:

            dependencies = dependency_lookup.get(ecu_name, set())
            blocking_failed_dependencies = dependencies & failed_ecus
            blocking_skipped_dependencies = dependencies & skipped_ecus
            missing_dependencies = dependencies - schedulable_names - completed_or_satisfied

            if blocking_failed_dependencies or blocking_skipped_dependencies or missing_dependencies:
                policy = self.policy_resolver.for_ecu(ecu_name)
                reason = self._dependency_block_reason(
                    failed=blocking_failed_dependencies,
                    skipped=blocking_skipped_dependencies,
                    missing=missing_dependencies,
                )

                reporter.report(
                    ecu_name,
                    "SKIPPED",
                    0,
                    "unknown",
                    campaign_id=campaign_id,
                    error=reason,
                )

                print("----------------------------------------")
                print(f"Skipping ECU : {ecu_name}")
                print(f"Dependency policy reason : {reason}")
                self._print_dependency_sets(
                    failed=blocking_failed_dependencies,
                    skipped=blocking_skipped_dependencies,
                    missing=missing_dependencies,
                )
                print("----------------------------------------")
                print()

                if policy.dependency_failure_aborts_campaign:
                    campaign_results.append((ecu_name, "ABORTED"))
                    skipped_ecus.add(ecu_name)
                    print(
                        f"Campaign aborted by dependency policy for critical ECU: {ecu_name}"
                    )
                    self.last_results = list(campaign_results)
                    self.last_campaign_result = self._campaign_result(campaign_results)
                    self._print_summary(campaign_results)
                    self.transport.shutdown()
                    return False

                campaign_results.append((ecu_name, "SKIPPED"))
                skipped_ecus.add(ecu_name)
                continue

            entry = self._find_entry(eligible_updates, ecu_name)

            if entry is None:

                if ecu_name in completed_or_satisfied:
                    print("----------------------------------------")
                    print(f"Dependency Satisfied : {ecu_name}")
                    print("No update required for this ECU in the current campaign")
                    print("----------------------------------------")
                    print()

                    campaign_results.append((ecu_name, "SATISFIED"))
                    continue

                print("----------------------------------------")
                print(f"Skipping ECU : {ecu_name}")
                if ecu_name in eligible_names:
                    print("No schedulable package found")
                else:
                    print("Unsupported, incompatible, or already at target version")
                print("----------------------------------------")
                print()

                policy = self.policy_resolver.for_ecu(ecu_name)
                if policy.unavailable_aborts_campaign:
                    campaign_results.append((ecu_name, "ABORTED"))
                    skipped_ecus.add(ecu_name)
                    print(f"Campaign aborted by unavailable critical ECU: {ecu_name}")
                    self.last_results = list(campaign_results)
                    self.last_campaign_result = self._campaign_result(campaign_results)
                    self._print_summary(campaign_results)
                    self.transport.shutdown()
                    return False

                campaign_results.append((ecu_name, "SKIPPED"))
                skipped_ecus.add(ecu_name)
                continue

            ecu = entry["ecu"]
            package = dict(entry["package"])
            package["path"] = str(
                self.firmware_manager.release_directory / package["file"]
            )

            print("----------------------------------------")
            print(f"Updating ECU : {ecu.ecu_name}")
            print(f"Current Version : {ecu.current_version}")
            print(f"Target Version  : {package['target_version']}")
            print("----------------------------------------")

            reporter.report(
                ecu.ecu_name,
                "DOWNLOADING",
                0,
                ecu.current_version,
                campaign_id=campaign_id
            )

            success = False
            for attempt in range(1, self.flash_retry_count + 1):
                if attempt > 1:
                    print(
                        f"Retrying ECU transport step ({attempt}/{self.flash_retry_count}) : "
                        f"{ecu.ecu_name}"
                    )
                success = self.transport.send_firmware(
                    ecu,
                    package,
                )
                if success:
                    break
                if attempt < self.flash_retry_count:
                    time.sleep(1.0)

            if not success:

                reporter.report(
                    ecu.ecu_name,
                    "FAILED",
                    0,
                    ecu.current_version,
                    campaign_id=campaign_id,
                    error="TRANSPORT_FAILURE"
                )

                print(f"[FAILED] {ecu.ecu_name}")

                campaign_results.append(
                    (ecu.ecu_name, "FAILED")
                )
                failed_ecus.add(ecu.ecu_name)
                policy = self.policy_resolver.for_ecu(ecu.ecu_name)
                if policy.criticality == "critical":
                    fatal_policy_abort = True

                print()
                print("Dependent ECUs will be skipped.")
                print()
                continue

            reporter.report(
                ecu.ecu_name,
                "INSTALLING",
                70,
                ecu.current_version,
                campaign_id=campaign_id
            )

            reporter.report(
                ecu.ecu_name,
                "VERIFYING",
                95,
                ecu.current_version,
                campaign_id=campaign_id
            )

            ecu.update_status = "PENDING_COMMIT"
            ecu.state = "REBOOTING"
            ecu.target_version = package["target_version"]

            reporter.report(
                ecu.ecu_name,
                "PENDING_COMMIT",
                98,
                package["target_version"],
                campaign_id=campaign_id
            )

            campaign_results.append(
                (ecu.ecu_name, "FLASHED")
            )
            completed_or_satisfied.add(ecu.ecu_name)

            print(f"[FLASHED] {ecu.ecu_name} (awaiting post-install validation)")
            print()

            if self.inter_ecu_settle_seconds > 0:
                print(
                    f"Settling vehicle network before next ECU "
                    f"({self.inter_ecu_settle_seconds:.1f}s)"
                )
                print()
                time.sleep(self.inter_ecu_settle_seconds)

        self.last_results = list(campaign_results)
        self.last_campaign_result = self._campaign_result(campaign_results)
        self._print_summary(campaign_results)

        self.transport.shutdown()

        return not fatal_policy_abort and not failed_ecus

    # -----------------------------------------------------

    @staticmethod
    def _find_entry(eligible_updates, ecu_name):

        for entry in eligible_updates:

            if entry["ecu"].ecu_name == ecu_name:

                return entry

        return None

    @staticmethod
    def _discovered_ecu_names(vehicle):
        if vehicle is None or not hasattr(vehicle, "get_all_ecus"):
            return set()
        return {ecu.ecu_name for ecu in vehicle.get_all_ecus()}

    @staticmethod
    def _dependency_block_reason(failed: set[str], skipped: set[str], missing: set[str]) -> str:
        if failed:
            return "DEPENDENCY_FAILED"
        if skipped:
            return "DEPENDENCY_SKIPPED"
        if missing:
            return "DEPENDENCY_UNAVAILABLE"
        return "DEPENDENCY_BLOCKED"

    @staticmethod
    def _print_dependency_sets(failed: set[str], skipped: set[str], missing: set[str]):
        if failed:
            print(f"Failed dependencies      : {', '.join(sorted(failed))}")
        if skipped:
            print(f"Skipped dependencies     : {', '.join(sorted(skipped))}")
        if missing:
            print(f"Unavailable dependencies : {', '.join(sorted(missing))}")

    # -----------------------------------------------------

    @staticmethod
    def _print_summary(results):

        print()
        print("=" * 60)
        print("OTA CAMPAIGN SUMMARY")
        print("=" * 60)

        for ecu_name, status in results:

            print(f"{ecu_name:<20} {status}")

        print("=" * 60)

        print(f"Campaign Result : {UpdateScheduler._campaign_result(results)}")

        print("=" * 60)

    @staticmethod
    def _campaign_result(results):

        if len(results) == 0:
            return "NO APPLICABLE UPDATES"

        if any(status == "ABORTED" for _, status in results):
            return "ABORTED_BY_POLICY"

        if all(status == "SKIPPED" for _, status in results):
            return "NO APPLICABLE UPDATES"

        if all(status in ("PASS", "FLASHED", "SATISFIED") for _, status in results):
            return "FLASHING COMPLETE"

        if any(status == "FAILED" for _, status in results) and any(
            status in ("FLASHED", "SKIPPED") for _, status in results
        ):
            return "PARTIAL_SUCCESS"

        return "FAILED"
