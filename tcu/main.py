import json
import os
from contextlib import suppress
from contextlib import redirect_stdout
from io import StringIO

from common.active_scenario import load_active_scenario, sync_process_environment_from_active
from common.demo_logging import quiet_enabled
from ecus.base.runtime_control import load_runtime_control
from tcu.ecu_discovery import ECUDiscovery
from tcu.validation.campaign_validator import CampaignValidator
from tcu.compatibility.validator import CompatibilityValidator
from tcu.firmware_compatibility import FirmwareCompatibilityValidator
from tcu.firmware_manager import FirmwareManager
from tcu.update_scheduler import UpdateScheduler
from tcu.post_install_validator import PostInstallValidator
from tcu.campaign_manager import CampaignManager
from tcu.cloud_client import OTACloudClient
from tcu.execution_summary import ExecutionSummary, ExecutionSummaryWriter
from tcu.mqtt_campaign_state import DuplicateMQTTJob
from tcu.status_reporter import reporter
from tcu.dynamic_update_planner import DynamicUpdatePlanner


RELEASE_DIRECTORY = "firmware/releases/2.0.0"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _auto_publish_mqtt_job(quiet: bool) -> None:
    if not _env_flag("OTA_AUTO_PUBLISH_MQTT_JOB", True):
        return

    from ota_server.campaign_scheduler import publish_current_campaign_once
    from ota_server.clear_mqtt_job_notification import clear_retained_job_notification

    print()
    print("=" * 60)
    print("AUTO MQTT JOB PUBLISH")
    print("=" * 60)
    print("Preparing a fresh MQTT OTA job for this TCU run...")

    with suppress(Exception):
        clear_retained_job_notification()

    payload = publish_current_campaign_once()

    if not quiet:
        print(f"Campaign notification published : {payload['campaign_id']}")
        print(f"MQTT Job ID                     : {payload['job_id']}")
    print("=" * 60)


def _run_step(label, operation, quiet=False, dump_on_false=True):
    if not quiet:
        return operation()

    print(f"{label:<32} ... ", end="", flush=True)
    captured = StringIO()
    try:
        with redirect_stdout(captured):
            result = operation()
    except Exception:
        print("FAILED")
        _dump_captured_output(captured)
        raise

    if result is False:
        print("FAILED")
        if dump_on_false:
            _dump_captured_output(captured)
    else:
        print("OK")

    return result


def _dump_captured_output(captured):
    output = captured.getvalue().strip()
    if output:
        print(output)


def _print_compact_discovery(vehicle):
    ecus = vehicle.get_all_ecus()
    ecu_text = ", ".join(
        f"{ecu.ecu_name}({ecu.current_version})"
        for ecu in ecus
    )
    print(f"Discovered ECUs                 : {len(ecus)}")
    print(f"Inventory                       : {ecu_text}")


def _print_compact_eligible(eligible_updates):
    names = ", ".join(
        entry["ecu"].ecu_name
        for entry in eligible_updates
    ) or "None"
    print(f"Eligible ECUs                   : {len(eligible_updates)}")
    print(f"Execution candidates            : {names}")


def _print_compact_plan(update_plan):
    order = " -> ".join(update_plan.update_order) or "None"
    print(f"Dynamic update order            : {order}")
    for ecu_name, classification in update_plan.classifications.items():
        if classification != "ELIGIBLE":
            print(f"Plan classification             : {ecu_name} = {classification}")
    if update_plan.blocking_errors:
        for error in update_plan.blocking_errors:
            print(f"Planning error                  : {error}")


def _selected_update_names(update_plan):
    return {
        ecu_name
        for ecu_name, classification in update_plan.classifications.items()
        if classification == "ELIGIBLE" and ecu_name in set(update_plan.update_order)
    }


def _print_runtime_vehicle_context(summary_context):
    topology_path = os.getenv("OTA_VEHICLE_TOPOLOGY", "").strip()
    platform_definition = summary_context.get("platform_definition", "").strip()
    runtime_mapping = summary_context.get("runtime_mapping", "").strip()
    scenario_name = summary_context.get("scenario_name", "").strip()

    if not any([topology_path, platform_definition, runtime_mapping, scenario_name]):
        return

    print("Vehicle Context :")
    if scenario_name:
        print(f"  Scenario          : {scenario_name}")
    if topology_path:
        print(f"  Topology wrapper  : {topology_path}")
    if platform_definition:
        print(f"  Platform model    : {platform_definition}")
    if runtime_mapping:
        print(f"  Runtime mapping   : {runtime_mapping}")
    preset_description = os.getenv("OTA_SCENARIO_ECU_STATE_PRESET_DESCRIPTION", "").strip()
    preset_name = os.getenv("OTA_SCENARIO_ECU_STATE_PRESET", "").strip()
    if preset_description or preset_name:
        print(f"  ECU state preset  : {preset_description or preset_name}")
    runtime_mode = os.getenv("OTA_SCENARIO_RUNTIME", "").strip()
    if runtime_mode:
        print(f"  Runtime mode      : {runtime_mode}")


def _validate_active_scenario_consistency():
    active = load_active_scenario()
    if not active:
        return True

    def _normalize_scenario_path(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        candidate = text.replace("\\", "/")
        try:
            absolute_candidate = os.path.abspath(text).replace("\\", "/")
        except OSError:
            absolute_candidate = candidate

        project_root = os.getenv("OTA_PROJECT_ROOT", "").strip()
        known_roots = []
        if project_root:
            known_roots.append(project_root.replace("\\", "/").rstrip("/"))
        known_roots.append("/app")

        for root in known_roots:
            if not root:
                continue
            prefix = f"{root}/"
            if candidate == root:
                return ""
            if candidate.startswith(prefix):
                return candidate[len(prefix):]
            if absolute_candidate == root:
                return ""
            if absolute_candidate.startswith(prefix):
                return absolute_candidate[len(prefix):]

        def _repo_relative_suffix(path_text: str) -> str:
            parts = [part for part in path_text.split("/") if part]
            anchors = {
                "runtime",
                "vehicle",
                "campaigns",
                "docker",
                "scenarios",
                "firmware",
                "logs",
            }
            for index, part in enumerate(parts):
                if part in anchors:
                    return "/".join(parts[index:])
            return path_text

        if "/" in candidate:
            return _repo_relative_suffix(candidate)
        return _repo_relative_suffix(absolute_candidate)

    expected = {
        "OTA_SCENARIO_NAME": active.get("scenario_name", ""),
        "OTA_CAMPAIGN_FILE": active.get("campaign_file", ""),
        "OTA_VEHICLE_TOPOLOGY": active.get("topology_file", ""),
        "OTA_PLATFORM_DEFINITION": active.get("platform_definition", ""),
        "OTA_RUNTIME_MAPPING": active.get("runtime_mapping", ""),
        "OTA_SCENARIO_RUNTIME": active.get("runtime", ""),
        "OTA_SCENARIO_DEPENDENCY_MODE": active.get("dependency_mode", ""),
        "OTA_SCENARIO_TOPOLOGY_MODE": active.get("topology_mode", ""),
    }
    mismatches = []
    for key, expected_value in expected.items():
        expected_text = str(expected_value or "").strip()
        actual_text = os.getenv(key, "").strip()
        if (
            expected_text
            and actual_text
            and _normalize_scenario_path(actual_text)
            != _normalize_scenario_path(expected_text)
        ):
            mismatches.append((key, expected_text, actual_text))

    if not mismatches:
        return True

    print()
    print("=" * 60)
    print("ACTIVE SCENARIO MISMATCH")
    print("=" * 60)
    print("The current process environment does not match the canonical active scenario.")
    print("Run from the refreshed active scenario, or rebuild the scenario before retrying.")
    print()
    for key, expected_value, actual_value in mismatches:
        print(f"- {key}")
        print(f"  canonical : {expected_value}")
        print(f"  current   : {actual_value}")
    print()
    print("Recommended fix:")
    print("1. source runtime/scenarios/active_tcu_env.sh")
    print("2. retry the OTA run")
    print("=" * 60)
    return False


def _validate_expected_ecu_versions(vehicle):
    raw = os.getenv("OTA_SCENARIO_ECU_STATE_EXPECTED_VERSIONS", "").strip()
    if not raw:
        return True

    try:
        expected_versions = json.loads(raw)
    except json.JSONDecodeError:
        print("Warning: invalid OTA_SCENARIO_ECU_STATE_EXPECTED_VERSIONS payload")
        return True

    if not expected_versions:
        return True

    discovered_versions = {
        ecu.ecu_name: ecu.current_version
        for ecu in vehicle.get_all_ecus()
    }
    mismatches = []
    configured_offline = {
        value.strip()
        for value in os.getenv("OTA_SCENARIO_OFFLINE_ECUS", "").split(",")
        if value.strip()
    }

    for ecu_name, expected_version in expected_versions.items():
        actual_version = discovered_versions.get(ecu_name)
        if actual_version is None and _offline_mismatch_allowed(ecu_name, configured_offline):
            continue
        if actual_version is None:
            mismatches.append(
                f"{ecu_name}: expected {expected_version}, discovered MISSING"
            )
        elif actual_version != expected_version:
            mismatches.append(
                f"{ecu_name}: expected {expected_version}, discovered {actual_version}"
            )

    if not mismatches:
        return True

    print()
    print("=" * 60)
    print("RUNTIME ECU STATE MISMATCH")
    print("=" * 60)
    print("Selected ECU state preset does not match the currently running ECU stack.")
    print("This usually means the ECU/zone runtime was already running before the")
    print("new scenario preset was applied.")
    print()
    for mismatch in mismatches:
        print(f"- {mismatch}")
    print()
    print("Action:")
    print("1. Stop the running ECU/zone stack")
    print("2. Restart the runtime using the commands printed by the launcher")
    print("3. Run the scenario again")
    print("=" * 60)
    return False


def _offline_mismatch_allowed(ecu_name: str, configured_offline: set[str]) -> bool:
    if ecu_name in configured_offline:
        return True

    ecu_key = ecu_name.strip().lower().replace(" ecu", "")
    if not ecu_key:
        return False

    control = load_runtime_control(ecu_key)
    return (
        not control.get("heartbeat_enabled", True)
        or not control.get("diagnostics_enabled", True)
    )


def main():
    sync_process_environment_from_active(overwrite=False)
    quiet = quiet_enabled()
    summary_writer = ExecutionSummaryWriter()
    summary_context = {
        "transport": "",
        "cloud_control": "",
        "campaign_id": "",
        "artifact_name": os.getenv("OTA_MENDER_ARTIFACT_NAME", ""),
        "software_name": os.getenv("OTA_MENDER_SOFTWARE_NAME", ""),
        "software_version": os.getenv("OTA_MENDER_SOFTWARE_VERSION", ""),
        "discovered_ecus": [],
        "eligible_ecus": [],
        "update_order": [],
        "platform_definition": os.getenv("OTA_PLATFORM_DEFINITION", ""),
        "runtime_mapping": os.getenv("OTA_RUNTIME_MAPPING", ""),
        "scenario_name": os.getenv("OTA_SCENARIO_NAME", ""),
    }

    def finalize(status: str, reason: str = "", per_ecu_results=None):
        summary_writer.write(
            ExecutionSummary(
                status=status,
                transport=summary_context["transport"],
                cloud_control=summary_context["cloud_control"],
                campaign_id=summary_context["campaign_id"],
                artifact_name=summary_context["artifact_name"],
                software_name=summary_context["software_name"],
                software_version=summary_context["software_version"],
                reason=reason,
                discovered_ecus=summary_context["discovered_ecus"],
                eligible_ecus=summary_context["eligible_ecus"],
                update_order=summary_context["update_order"],
                platform_definition=summary_context["platform_definition"],
                runtime_mapping=summary_context["runtime_mapping"],
                scenario_name=summary_context["scenario_name"],
                per_ecu_results=per_ecu_results or [],
            )
        )
        return 0 if status == "COMPLETED" else 1

    print()
    print("=" * 70)
    print("AUTOMOTIVE OTA UPDATE MANAGER")
    print("=" * 70)

    if not _validate_active_scenario_consistency():
        return finalize("FAILED", "ACTIVE_SCENARIO_MISMATCH")

    # ----------------------------------------------------------
    # Transport Selection
    # ----------------------------------------------------------

    configured_transport = os.getenv("OTA_TRANSPORT", "").strip().lower()
    if not quiet or not configured_transport:
        print("\n")
        print("=" * 60)
        print("Select Communication Transport")
        print("=" * 60)
        print("1. VCAN")
        print("2. DoIP")
        print()
    if configured_transport:
        choice = {"vcan": "1", "can": "1", "doip": "2"}.get(configured_transport, "")
        if quiet:
            print(f"Transport : {configured_transport.upper()}")
        else:
            print(f"Enter choice : {choice}  (from OTA_TRANSPORT={configured_transport})")
    else:
        choice = input("Enter choice : ").strip()

    if choice == "1":
        transport = "VCAN"

    elif choice == "2":
        transport = "DOIP"

    else:
        print("Invalid selection")
        return finalize("FAILED", "INVALID_TRANSPORT_SELECTION")
    summary_context["transport"] = transport

    configured_cloud = os.getenv("OTA_CLOUD_CONTROL", "").strip().lower()
    if not quiet or not configured_cloud:
        print("\n")
        print("=" * 60)
        print("Select Cloud Control Plane")
        print("=" * 60)
        print("1. HTTP Poll")
        print("2. MQTT Notify")
        print()
    if configured_cloud:
        cloud_choice = {
            "http": "1",
            "https": "1",
            "http_poll": "1",
            "https_poll": "1",
            "poll": "1",
            "mqtt": "2",
            "mqtt_notify": "2",
            "notify": "2",
        }.get(configured_cloud, "")
        if quiet:
            if cloud_choice == "2":
                print("Cloud Link : MQTT notify/status + HTTPS campaign/artifact download")
            else:
                print("Cloud Link : HTTPS poll + HTTPS campaign/artifact download")
        else:
            print(f"Enter choice : {cloud_choice}  (from OTA_CLOUD_CONTROL={configured_cloud})")
    else:
        cloud_choice = input("Enter choice : ").strip()
    summary_context["cloud_control"] = "mqtt" if cloud_choice == "2" else "http"

    if quiet:
        _print_runtime_vehicle_context(summary_context)

    # ----------------------------------------------------------
    # STEP 1 : Download campaign and firmware from OTA Cloud
    # ----------------------------------------------------------

    cloud = OTACloudClient()

    if cloud_choice == "2":
        try:
            _auto_publish_mqtt_job(quiet)
            campaign_data = cloud.download_campaign_from_mqtt()
        except DuplicateMQTTJob as exc:
            print(f"MQTT duplicate job skipped: {exc}")
            print("OTA Campaign Aborted")
            return finalize("FAILED", "DUPLICATE_MQTT_JOB")
        except Exception as exc:
            print(f"MQTT unavailable, falling back to HTTP poll: {exc}")
            campaign_data = cloud.download_campaign()
    else:
        campaign_data = cloud.download_campaign()

    if cloud.current_job:
        reporter.set_job_context(
            job_id=cloud.current_job.get("job_id"),
            vehicle_id=cloud.current_job.get("vehicle_id"),
        )

    #
    # Load campaign from downloaded file
    #

    campaign = CampaignManager.load_campaign(
        str(cloud.local_campaign)
    )
    summary_context["campaign_id"] = getattr(campaign, "campaign_id", "")

    #
    # Bind the user-selected execution transport to this run.
    # The downloaded campaign is the intent; the selected transport
    # is the actual execution path in this demo.
    #

    campaign.transport = transport

    #
    # Campaign Validation
    #

    if not _run_step(
        "Campaign validation",
        lambda: CampaignValidator().validate(campaign),
        quiet,
    ):
        print("\nCampaign validation failed.")
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "CAMPAIGN_VALIDATION_FAILED")

    #
    # ECU Discovery
    #

    discovery = ECUDiscovery()

    vehicle = _run_step(
        "ECU discovery",
        lambda: discovery.discover(transport=transport),
        quiet,
    )
    summary_context["discovered_ecus"] = [ecu.ecu_name for ecu in vehicle.get_all_ecus()]
    if quiet:
        _print_compact_discovery(vehicle)

    if not _validate_expected_ecu_versions(vehicle):
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "RUNTIME_ECU_STATE_MISMATCH")

    #
    # Compatibility Validation
    #

    if not _run_step(
        "Campaign compatibility",
        lambda: CompatibilityValidator().validate(vehicle, campaign),
        quiet,
    ):
        print("\nCompatibility validation failed.")
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "CAMPAIGN_COMPATIBILITY_FAILED")

    #
    # Firmware Compatibility
    #

    eligible_updates = _run_step(
        "Firmware compatibility",
        lambda: FirmwareCompatibilityValidator().validate(
            vehicle,
            campaign,
            require_downloaded_files=False,
        ),
        quiet,
    )
    summary_context["eligible_ecus"] = [entry["ecu"].ecu_name for entry in eligible_updates]
    if quiet:
        _print_compact_eligible(eligible_updates)

    if len(eligible_updates) == 0:
        print("\nNo compatible ECUs found.")
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "NO_COMPATIBLE_ECUS")

    #
    # Dynamic Dependency / Topological Planning
    #

    dynamic_planner = DynamicUpdatePlanner()
    update_plan = dynamic_planner.plan(vehicle, campaign, eligible_updates)
    if quiet:
        _print_compact_plan(update_plan)
    else:
        dynamic_planner.print_report(update_plan, vehicle, campaign)

    if not update_plan.executable:
        print()
        print("Dynamic update planning failed.")
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "DYNAMIC_PLANNING_FAILED")

    update_order = update_plan.update_order
    summary_context["update_order"] = list(update_order)
    selected_update_names = _selected_update_names(update_plan)

    if not selected_update_names:
        print("\nNo ECUs require firmware download or flashing.")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "NO_EXECUTABLE_UPDATES")

    #
    # Download only the firmware selected by live planning
    #

    cloud.download_firmware(campaign_data, target_names=selected_update_names)

    #
    # Validate downloaded repository subset
    #

    firmware_manager = FirmwareManager(RELEASE_DIRECTORY)

    _run_step(
        "Repository verification",
        lambda: firmware_manager.verify_repository(selected_update_names),
        quiet,
    )

    _run_step(
        "Firmware inventory",
        lambda: firmware_manager.build_inventory(selected_update_names),
        quiet,
    )

    #
    # Verify the downloaded artifacts for the selected ECU set
    #

    selected_eligible_updates = _run_step(
        "Downloaded artifact verification",
        lambda: FirmwareCompatibilityValidator().validate(
            vehicle,
            campaign,
            require_downloaded_files=True,
            target_names=selected_update_names,
        ),
        quiet,
    )

    if len(selected_eligible_updates) != len(selected_update_names):
        print("\nDownloaded firmware verification failed.")
        print("OTA Campaign Aborted")
        cloud.mark_current_job("FAILED")
        return finalize("FAILED", "DOWNLOADED_ARTIFACT_VERIFICATION_FAILED")

    #
    # Execute OTA
    #

    scheduler = UpdateScheduler(RELEASE_DIRECTORY, transport)

    success = scheduler.execute(
        selected_eligible_updates,
        update_order,
        vehicle=vehicle,
        dependency_map=update_plan.dependency_map,
    )

    if not success:
        print()
        print("OTA Campaign Failed")
        cloud.mark_current_job("FAILED")
        return finalize(
            "FAILED",
            scheduler.last_campaign_result or "OTA_EXECUTION_FAILED",
            [
                {"ecu": ecu_name, "status": status}
                for ecu_name, status in scheduler.last_results
            ],
        )

    #
    # Post Installation Validation
    #

    validator = PostInstallValidator()

    if validator.validate(campaign, transport=transport):
        cloud.mark_current_job("COMPLETED")
        return finalize(
            "COMPLETED",
            scheduler.last_campaign_result or "FLASHING_COMPLETE",
            [
                {"ecu": ecu_name, "status": status}
                for ecu_name, status in scheduler.last_results
            ],
        )
    else:
        cloud.mark_current_job("FAILED")
        return finalize(
            "FAILED",
            "POST_INSTALL_VALIDATION_FAILED",
            [
                {"ecu": ecu_name, "status": status}
                for ecu_name, status in scheduler.last_results
            ],
        )


if __name__ == "__main__":
    raise SystemExit(main())
