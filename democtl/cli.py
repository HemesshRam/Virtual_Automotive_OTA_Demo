from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import prepare_ota_scenario as prepare_scenario


ACTIVE_SCENARIO_INFO = PROJECT_ROOT / "runtime" / "scenarios" / "active_prepared_scenario.json"
ACTIVE_ENV_FILE = PROJECT_ROOT / "runtime" / "scenarios" / "active_tcu_env.sh"
PROCESS_STATE_FILE = PROJECT_ROOT / "runtime" / "democtl" / "processes.json"
LOG_DIR = PROJECT_ROOT / "logs" / "democtl"
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.ecus.yml"
MOSQUITTO_CONFIG_FILE = PROJECT_ROOT / "docker" / "mosquitto" / "mosquitto-no-auth.conf"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Environment file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("export "):
            continue
        key, _, value = line[7:].partition("=")
        if not key or not _:
            continue
        env[key] = _shell_unquote(value)
    return env


def _shell_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_active_context() -> tuple[dict, dict[str, str]]:
    if not ACTIVE_SCENARIO_INFO.exists():
        raise RuntimeError(
            f"No prepared scenario found at {ACTIVE_SCENARIO_INFO}. "
            "Run `python -m democtl prepare ...` first."
        )
    info = _load_json(ACTIVE_SCENARIO_INFO)
    env_file = Path(info["env_file"])
    env = _parse_env_file(env_file)
    return info, env


def _base_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    if extra:
        env.update(extra)
    return env


def _run_foreground(command: list[str], env: dict[str, str] | None = None) -> int:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=_base_env(env),
        check=False,
    )
    return int(result.returncode)


def _auto_publish_mqtt_job(env: dict[str, str]) -> int:
    print()
    print("=" * 60)
    print("AUTO MQTT JOB PUBLISH")
    print("=" * 60)
    print("Preparing a fresh MQTT OTA job for this TCU run...")
    print("This replaces stale retained job notifications with a new job ID.")
    print("=" * 60)
    return _run_foreground(
        [sys.executable, "-m", "ota_server.campaign_scheduler"],
        {
            **env,
            "OTA_CAMPAIGN_PUBLISH_DELAY": "0",
        },
    )


def _start_background_process(name: str, command: list[str], env: dict[str, str]) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    log_handle = open(log_path, "ab")
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=_base_env(env),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_handle.close()
    return {
        "name": name,
        "pid": process.pid,
        "log": str(log_path),
        "command": command,
    }


def _save_process_state(runtime: str, records: list[dict], scenario_name: str) -> None:
    payload = {
        "runtime": runtime,
        "scenario_name": scenario_name,
        "processes": records,
    }
    _write_json(PROCESS_STATE_FILE, payload)


def _append_process_state(record: dict, runtime: str, scenario_name: str) -> None:
    state = _load_process_state() or {
        "runtime": runtime,
        "scenario_name": scenario_name,
        "processes": [],
    }
    processes = [
        existing
        for existing in state.get("processes", [])
        if existing.get("name") != record.get("name")
    ]
    processes.append(record)
    state["runtime"] = runtime
    state["scenario_name"] = scenario_name
    state["processes"] = processes
    _write_json(PROCESS_STATE_FILE, state)


def _load_process_state() -> dict | None:
    if not PROCESS_STATE_FILE.exists():
        return None
    return _load_json(PROCESS_STATE_FILE)


def _port_is_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _ensure_mqtt_broker(info: dict, env: dict[str, str]) -> int:
    host = env.get("MQTT_BROKER_HOST", "127.0.0.1")
    port = int(env.get("MQTT_BROKER_PORT", "1883"))

    if _port_is_listening(host, port):
        print(f"MQTT broker already listening on {host}:{port}.")
        return 0

    print(f"MQTT broker not listening on {host}:{port}. Starting local mosquitto...")

    broker_record = _start_background_process(
        "mqtt-broker",
        ["mosquitto", "-c", str(MOSQUITTO_CONFIG_FILE)],
        env,
    )
    _append_process_state(broker_record, info["runtime"], info["scenario_name"])

    for _ in range(20):
        if _port_is_listening(host, port):
            print(f"MQTT broker started on {host}:{port}.")
            print(f"MQTT broker log: {broker_record['log']}")
            return 0
        time.sleep(0.25)

    print(f"Failed to start MQTT broker on {host}:{port}.")
    print(f"MQTT broker log: {broker_record['log']}")
    return 1


def _signal_process_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def _stop_python_runtime() -> None:
    state = _load_process_state()
    if not state:
        return
    for record in state.get("processes", []):
        pid = int(record.get("pid", 0))
        if pid > 0:
            _signal_process_group(pid, signal.SIGTERM)
    PROCESS_STATE_FILE.unlink(missing_ok=True)


def _docker_services_for(topology: str) -> list[str]:
    if topology == "body-two":
        return ["zone-gateway", "gateway", "zone-body", "bcm", "cluster"]
    return ["zone-gateway", "gateway", "zone-body", "bcm", "zone-cluster", "cluster"]


def _offline_ecu_names(info: dict) -> set[str]:
    if "offline_ecus" in info:
        return {
            str(name).strip()
            for name in info.get("offline_ecus", [])
            if str(name).strip()
        }

    offline = info.get("offline")
    mapping = {
        "none": set(),
        "gateway": {"Gateway ECU"},
        "bcm": {"BCM ECU"},
        "cluster": {"Cluster ECU"},
        "gateway-bcm": {"Gateway ECU", "BCM ECU"},
        "gateway-cluster": {"Gateway ECU", "Cluster ECU"},
        "bcm-cluster": {"BCM ECU", "Cluster ECU"},
    }
    return mapping.get(str(offline or "none"), set())


def _python_commands_for(topology: str, offline_ecus: set[str] | None = None) -> list[tuple[str, list[str]]]:
    offline_ecus = offline_ecus or set()
    commands = [
        ("ota-server", ["bash", "scripts/run_ota_server_https.sh"]),
        ("zone-gateway", [sys.executable, "-m", "zones.run_zone_service", "gateway_zone"]),
        ("zone-body", [sys.executable, "-m", "zones.run_zone_service", "body_zone"]),
    ]
    if "Gateway ECU" not in offline_ecus:
        commands.append(("gateway-ecu", [sys.executable, "run_gateway.py"]))
    if "BCM ECU" not in offline_ecus:
        commands.append(("bcm-ecu", [sys.executable, "run_bcm.py"]))
    if "Cluster ECU" not in offline_ecus:
        commands.append(("cluster-ecu", [sys.executable, "run_cluster.py"]))
    if topology != "body-two":
        commands.append(
            ("zone-cluster", [sys.executable, "-m", "zones.run_zone_service", "cluster_zone"])
        )
    return commands


def command_prepare(args: argparse.Namespace) -> int:
    forwarded_args = [
        "--transport",
        args.transport,
        "--topology",
        args.topology,
        "--dependency",
        args.dependency,
        "--offline",
        args.offline,
        "--runtime",
        args.runtime,
        "--ecu-state",
        args.ecu_state,
        "--quiet",
        args.quiet,
    ]
    if args.offline_feature:
        forwarded_args.extend(["--offline-feature", args.offline_feature])
    if args.scenario_name:
        forwarded_args.extend(["--scenario-name", args.scenario_name])
    if args.campaign:
        forwarded_args.extend(["--campaign", args.campaign])
    if args.server_url:
        forwarded_args.extend(["--server-url", args.server_url])
    if args.status_url:
        forwarded_args.extend(["--status-url", args.status_url])
    if args.tls_verify:
        forwarded_args.extend(["--tls-verify", args.tls_verify])
    if args.build_mender:
        forwarded_args.append("--build-mender")
        if args.build_mender != "auto":
            forwarded_args.append(args.build_mender)
    if args.artifact_name:
        forwarded_args.extend(["--artifact-name", args.artifact_name])
    if args.device_type:
        forwarded_args.extend(["--device-type", args.device_type])
    if args.keep_payload_dir:
        forwarded_args.append("--keep-payload-dir")
    return int(prepare_scenario.main(forwarded_args) or 0)


def command_start_runtime(args: argparse.Namespace) -> int:
    info, env = _load_active_context()
    if args.restart:
        command_teardown(argparse.Namespace())

    if args.ensure_vcan:
        rc = _run_foreground(["sudo", "./scripts/setup_vcan_zones.sh"])
        if rc != 0:
            return rc

    runtime = info["runtime"]
    topology_mode = info.get("topology_mode", "default")
    topology = "body-two" if topology_mode == "body_two_ecus" else "default"
    scenario_name = info["scenario_name"]

    if runtime == "docker":
        services = _docker_services_for(topology)
        docker_env = env.copy()
        docker_env["LOCAL_UID"] = str(os.getuid())
        docker_env["LOCAL_GID"] = str(os.getgid())

        rc = _run_foreground(
            [
                "docker",
                "compose",
                "-f",
                str(DOCKER_COMPOSE_FILE),
                "--profile",
                "deep-zonal",
                "up",
                "--build",
                "-d",
                *services,
            ],
            docker_env,
        )
        if rc != 0:
            return rc

        server = _start_background_process(
            "ota-server",
            ["bash", "scripts/run_ota_server_https.sh"],
            env,
        )
        _save_process_state(runtime, [server], scenario_name)
        print(f"Docker runtime started for scenario `{scenario_name}`.")
        print(f"OTA server log: {server['log']}")
        return 0

    offline_ecus = _offline_ecu_names(info)
    process_records = []
    for name, command in _python_commands_for(topology, offline_ecus):
        process_records.append(_start_background_process(name, command, env))
    _save_process_state(runtime, process_records, scenario_name)
    print(f"Python runtime started for scenario `{scenario_name}`.")
    for record in process_records:
        print(f"{record['name']}: {record['log']}")
    if offline_ecus:
        print(f"Offline ECUs not started: {', '.join(sorted(offline_ecus))}")
    return 0


def command_run_tcu(args: argparse.Namespace) -> int:
    info, env = _load_active_context()
    cloud_control = env.get("OTA_CLOUD_CONTROL", "").strip().lower()
    if cloud_control == "mqtt" and not args.skip_auto_publish:
        rc = _ensure_mqtt_broker(info, env)
        if rc != 0:
            return rc
        rc = _auto_publish_mqtt_job(env)
        if rc != 0:
            print("Fresh MQTT job publish failed. Continuing with the configured TCU flow.")
    return _run_foreground([sys.executable, "-m", "tcu.main"], env)


def command_build_mender(args: argparse.Namespace) -> int:
    info, _ = _load_active_context()
    topology_mode = info.get("topology_mode", "default")
    dependency_mode = info.get("dependency_mode", "topology_default")
    offline_ecus = _offline_ecu_names(info)
    offline_name_map = {
        frozenset(): "none",
        frozenset({"Gateway ECU"}): "gateway",
        frozenset({"BCM ECU"}): "bcm",
        frozenset({"Cluster ECU"}): "cluster",
        frozenset({"Gateway ECU", "BCM ECU"}): "gateway-bcm",
        frozenset({"Gateway ECU", "Cluster ECU"}): "gateway-cluster",
        frozenset({"BCM ECU", "Cluster ECU"}): "bcm-cluster",
    }
    reverse_topology = {
        "default": "default",
        "body_two_ecus": "body-two",
    }
    reverse_dependency = {
        "topology_default": "topology-default",
        "cluster_depends_gateway": "cluster-gateway",
        "bcm_before_gateway": "bcm-gateway-cluster",
        "partial_skip_cluster": "partial-skip",
    }
    reverse_ecu_state = {
        "keep_current": "keep-current",
        "fresh_baseline": "fresh",
        "gateway_bcm_updated_cluster_pending": "gateway-bcm-updated",
        "gateway_cluster_updated_bcm_pending": "gateway-cluster-updated",
        "bcm_cluster_updated_gateway_pending": "bcm-cluster-updated",
    }
    prepare_args = [
        "--transport",
        info["transport"],
        "--topology",
        reverse_topology.get(topology_mode, "default"),
        "--dependency",
        reverse_dependency.get(dependency_mode, "topology-default"),
        "--offline",
        offline_name_map.get(frozenset(offline_ecus), "none"),
        "--runtime",
        info["runtime"],
        "--ecu-state",
        reverse_ecu_state.get(info.get("ecu_state_preset", "fresh_baseline"), "fresh"),
        "--build-mender",
        args.output or "auto",
        "--device-type",
        args.device_type,
    ]
    if args.artifact_name:
        prepare_args.extend(["--artifact-name", args.artifact_name])
    if args.keep_payload_dir:
        prepare_args.append("--keep-payload-dir")
    return int(prepare_scenario.main(prepare_args) or 0)


def command_teardown(args: argparse.Namespace) -> int:
    _stop_python_runtime()
    rc = _run_foreground(["bash", "scripts/stop_demo.sh"])
    if rc != 0:
        rc = _run_foreground(["bash", "-lc", "bash scripts/stop_demo.sh || true"])
    return rc


def command_run(args: argparse.Namespace) -> int:
    prepare_args = argparse.Namespace(
        transport=args.transport,
        topology=args.topology,
        dependency=args.dependency,
        offline=args.offline,
        runtime=args.runtime,
        ecu_state=args.ecu_state,
        offline_feature=args.offline_feature,
        scenario_name=args.scenario_name,
        campaign=args.campaign,
        server_url=args.server_url,
        status_url=args.status_url,
        tls_verify=args.tls_verify,
        quiet=args.quiet,
        build_mender=None,
        artifact_name=None,
        device_type="virtual-ota-tcu",
        keep_payload_dir=False,
    )

    rc = command_prepare(prepare_args)
    if rc != 0:
        return rc

    rc = command_start_runtime(
        argparse.Namespace(
            restart=args.restart_runtime,
            ensure_vcan=args.ensure_vcan,
        )
    )
    if rc != 0:
        return rc

    return command_run_tcu(
        argparse.Namespace(
            skip_auto_publish=args.skip_auto_publish,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="democtl",
        description="Operator CLI for the virtual automotive OTA demo",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare a scenario and optionally build a dynamic Mender artifact",
    )
    prepare_parser.add_argument("--transport", choices=["doip", "vcan"], required=True)
    prepare_parser.add_argument("--topology", choices=["default", "body-two"], required=True)
    prepare_parser.add_argument(
        "--dependency",
        choices=["topology-default", "cluster-gateway", "bcm-gateway-cluster", "partial-skip"],
        required=True,
    )
    prepare_parser.add_argument(
        "--offline",
        choices=["none", "gateway", "bcm", "cluster", "gateway-bcm", "gateway-cluster", "bcm-cluster"],
        default="none",
    )
    prepare_parser.add_argument(
        "--runtime",
        choices=["docker", "python"],
        required=True,
    )
    prepare_parser.add_argument(
        "--ecu-state",
        choices=["fresh", "keep-current", "gateway-bcm-updated", "gateway-cluster-updated", "bcm-cluster-updated"],
        default="fresh",
    )
    prepare_parser.add_argument("--offline-feature", choices=["heartbeat", "diagnostics", "programming"], default="heartbeat")
    prepare_parser.add_argument("--scenario-name")
    prepare_parser.add_argument("--campaign")
    prepare_parser.add_argument("--server-url")
    prepare_parser.add_argument("--status-url")
    prepare_parser.add_argument("--tls-verify")
    prepare_parser.add_argument("--quiet", choices=["0", "1"], default="1")
    prepare_parser.add_argument("--build-mender", nargs="?", const="auto")
    prepare_parser.add_argument("--artifact-name")
    prepare_parser.add_argument("--device-type", default="virtual-ota-tcu")
    prepare_parser.add_argument("--keep-payload-dir", action="store_true")
    prepare_parser.set_defaults(handler=command_prepare)

    start_parser = subparsers.add_parser(
        "start-runtime",
        help="Start the prepared ECU/zone runtime in the background",
    )
    start_parser.add_argument("--restart", action="store_true")
    start_parser.add_argument("--ensure-vcan", action="store_true")
    start_parser.set_defaults(handler=command_start_runtime)

    run_tcu_parser = subparsers.add_parser(
        "run-tcu",
        help="Run the non-Mender TCU against the prepared scenario",
    )
    run_tcu_parser.add_argument(
        "--skip-auto-publish",
        action="store_true",
        help="Do not auto-publish a fresh MQTT job before starting the TCU",
    )
    run_tcu_parser.set_defaults(handler=command_run_tcu)

    run_parser = subparsers.add_parser(
        "run",
        help="Zero-touch flow: prepare scenario, start runtime, then run the non-Mender TCU",
    )
    run_parser.add_argument("--transport", choices=["doip", "vcan"], required=True)
    run_parser.add_argument("--topology", choices=["default", "body-two"], required=True)
    run_parser.add_argument(
        "--dependency",
        choices=["topology-default", "cluster-gateway", "bcm-gateway-cluster", "partial-skip"],
        required=True,
    )
    run_parser.add_argument(
        "--offline",
        choices=["none", "gateway", "bcm", "cluster", "gateway-bcm", "gateway-cluster", "bcm-cluster"],
        default="none",
    )
    run_parser.add_argument("--runtime", choices=["docker", "python"], required=True)
    run_parser.add_argument(
        "--ecu-state",
        choices=["fresh", "keep-current", "gateway-bcm-updated", "gateway-cluster-updated", "bcm-cluster-updated"],
        default="fresh",
    )
    run_parser.add_argument("--offline-feature", choices=["heartbeat", "diagnostics", "programming"], default="heartbeat")
    run_parser.add_argument("--scenario-name")
    run_parser.add_argument("--campaign")
    run_parser.add_argument("--server-url")
    run_parser.add_argument("--status-url")
    run_parser.add_argument("--tls-verify")
    run_parser.add_argument("--quiet", choices=["0", "1"], default="1")
    run_parser.add_argument("--ensure-vcan", action="store_true")
    run_parser.add_argument("--restart-runtime", action="store_true")
    run_parser.add_argument(
        "--skip-auto-publish",
        action="store_true",
        help="Do not auto-publish a fresh MQTT job before starting the TCU",
    )
    run_parser.set_defaults(handler=command_run)

    mender_parser = subparsers.add_parser(
        "build-mender",
        help="Build a dynamic Mender artifact from the prepared scenario",
    )
    mender_parser.add_argument("--output")
    mender_parser.add_argument("--artifact-name")
    mender_parser.add_argument("--device-type", default="virtual-ota-tcu")
    mender_parser.add_argument("--keep-payload-dir", action="store_true")
    mender_parser.set_defaults(handler=command_build_mender)

    teardown_parser = subparsers.add_parser(
        "teardown",
        help="Stop docker/python runtime launched by the operator CLI",
    )
    teardown_parser.set_defaults(handler=command_teardown)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args) or 0)
