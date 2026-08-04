import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_TOPOLOGY_PATH = Path("vehicle/topology.json")


def parse_int(value: int | str) -> int:
    if isinstance(value, int):
        return value
    return int(value, 0)


class VehicleTopology:
    def __init__(self, path: str | Path | None = None):
        configured_path = os.getenv("OTA_VEHICLE_TOPOLOGY")
        self.path = self._resolve_path(path or configured_path or DEFAULT_TOPOLOGY_PATH)
        self.data = self._load()

    @staticmethod
    def _project_root() -> Path | None:
        env_root = os.getenv("OTA_PROJECT_ROOT", "").strip()
        if not env_root:
            return None
        return Path(env_root).expanduser().resolve()

    def _resolve_path(self, configured_path: str | Path) -> Path:
        path = Path(configured_path)
        if path.is_absolute():
            return path

        project_root = self._project_root()
        if project_root is not None:
            candidate = (project_root / path).resolve()
            if candidate.exists():
                return candidate

        return path.resolve()

    def _load(self) -> dict[str, Any]:
        data = self._load_json(self.path)
        if self._is_composed_topology(data):
            return self._compose_topology(data)
        return data

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    @staticmethod
    def _is_composed_topology(data: dict[str, Any]) -> bool:
        return (
            data.get("topology_layout") == "composed"
            and bool(data.get("platform_definition"))
            and bool(data.get("runtime_mapping"))
        )

    def _resolve_relative(self, relative_path: str) -> Path:
        return (self.path.parent / relative_path).resolve()

    def _compose_topology(self, layout: dict[str, Any]) -> dict[str, Any]:
        platform_path = self._resolve_relative(layout["platform_definition"])
        runtime_path = self._resolve_relative(layout["runtime_mapping"])
        platform = self._load_json(platform_path)
        runtime = self._load_json(runtime_path)

        composed = deepcopy(platform)
        composed["schema_version"] = layout.get("schema_version", platform.get("schema_version", "2.0"))
        composed["topology_layout"] = "resolved"
        composed["platform_definition"] = str(platform_path)
        composed["runtime_mapping"] = str(runtime_path)
        composed["deployment_runtime"] = deepcopy(runtime)

        gateway_runtime = runtime.get("transport_backbone", {})
        central_gateway = composed.setdefault("central_gateway", {})
        if gateway_runtime.get("gateway_host"):
            central_gateway["host"] = gateway_runtime["gateway_host"]
        if gateway_runtime.get("gateway_doip_port"):
            central_gateway["doip_port"] = int(gateway_runtime["gateway_doip_port"])
        if gateway_runtime.get("type"):
            central_gateway["backbone_type"] = gateway_runtime["type"]

        runtime_zones = {
            zone["zone_id"]: zone
            for zone in runtime.get("zones", [])
        }

        for zone in composed.get("zones", []):
            runtime_zone = runtime_zones.get(zone["zone_id"], {})
            network = zone.setdefault("network", {})
            runtime_network = runtime_zone.get("network", {})
            if runtime_network:
                network.update(runtime_network)
            if runtime_zone.get("service_host"):
                zone["service_host"] = runtime_zone["service_host"]
            if runtime_zone.get("service_bind_host"):
                zone["service_bind_host"] = runtime_zone["service_bind_host"]
            if runtime_zone.get("service_port") is not None:
                zone["service_port"] = int(runtime_zone["service_port"])

        return composed

    @property
    def allowed_uds_services(self) -> list[int]:
        return [
            parse_int(service_id)
            for service_id in self.data.get("ota_allowed_uds_services", [])
        ]

    @property
    def zones(self) -> list[dict[str, Any]]:
        return list(self.data.get("zones", []))

    @property
    def platform_metadata(self) -> dict[str, Any]:
        return {
            "vehicle": deepcopy(self.data.get("vehicle", {})),
            "tester": deepcopy(self.data.get("tester", {})),
            "central_gateway": deepcopy(self.data.get("central_gateway", {})),
        }

    def build_zone_registry(self) -> dict[str, dict[str, Any]]:
        allowed_services = self.allowed_uds_services
        registry: dict[str, dict[str, Any]] = {}

        for zone in self.zones:
            policy = zone.get("policy", {})
            configured_services = policy.get("allowed_services", "ota_default")
            if configured_services == "ota_default":
                zone_allowed_services = allowed_services
            else:
                zone_allowed_services = [
                    parse_int(service_id)
                    for service_id in configured_services
                ]

            ecus = {}
            for ecu in zone.get("ecus", []):
                logical_address = parse_int(ecu["logical_address"])
                ecus[logical_address] = {
                    "ecu_name": ecu["ecu_name"],
                    "short_name": ecu.get("short_name", ecu["ecu_name"]),
                    "can_id": parse_int(ecu["can_id"]),
                    "criticality": ecu.get("criticality", "optional"),
                    "dependencies": list(ecu.get("dependencies", [])),
                    "on_unavailable": ecu.get("on_unavailable", "skip"),
                    "on_dependency_failed": ecu.get("on_dependency_failed", "skip"),
                }

            registry[zone["zone_id"]] = {
                "zone_id": zone["zone_id"],
                "display_name": zone["display_name"],
                "can_channel": zone["network"]["channel"],
                "network": dict(zone.get("network", {})),
                "service_host": zone.get("service_host", "127.0.0.1"),
                "service_bind_host": zone.get("service_bind_host", "127.0.0.1"),
                "service_port": int(zone["service_port"]),
                "default_health": policy.get("default_health", "ONLINE"),
                "programming_allowed": bool(policy.get("programming_allowed", True)),
                "allowed_services": zone_allowed_services,
                "ecus": ecus,
            }

        return registry

    def ecu_registry(self) -> dict[str, dict[str, Any]]:
        registry = {}
        for zone in self.build_zone_registry().values():
            for logical_address, ecu in zone["ecus"].items():
                registry[ecu["ecu_name"]] = {
                    "logical_address": logical_address,
                    "can_id": ecu["can_id"],
                    "zone_id": zone["zone_id"],
                    "can_channel": zone["can_channel"],
                    "dependencies": ecu["dependencies"],
                    "criticality": ecu["criticality"],
                    "on_unavailable": ecu["on_unavailable"],
                    "on_dependency_failed": ecu["on_dependency_failed"],
                }
        return registry

    def ecu_policy(self, ecu_name: str) -> dict[str, Any]:
        return self.ecu_registry().get(
            ecu_name,
            {
                "dependencies": [],
                "criticality": "optional",
                "on_unavailable": "skip",
                "on_dependency_failed": "skip",
            },
        )

    def dependency_for_can_id(self, can_id: int) -> list[str]:
        for entry in self.ecu_registry().values():
            if entry["can_id"] == can_id:
                return list(entry.get("dependencies", []))
        return []

    def validate(self) -> list[str]:
        errors: list[str] = []
        zone_ids: set[str] = set()
        service_ports: set[int] = set()
        can_channels: set[str] = set()
        ecu_names: set[str] = set()
        logical_addresses: set[int] = set()
        can_ids: set[int] = set()
        dependencies: dict[str, list[str]] = {}

        for zone in self.zones:
            zone_id = zone.get("zone_id", "")
            if not zone_id:
                errors.append("zone missing zone_id")
            elif zone_id in zone_ids:
                errors.append(f"duplicate zone_id: {zone_id}")
            zone_ids.add(zone_id)

            port = int(zone.get("service_port", 0))
            if port <= 0:
                errors.append(f"{zone_id} has invalid service_port")
            elif port in service_ports:
                errors.append(f"duplicate service_port: {port}")
            service_ports.add(port)

            channel = zone.get("network", {}).get("channel", "")
            if not channel:
                errors.append(f"{zone_id} missing CAN channel")
            elif channel in can_channels:
                errors.append(f"duplicate CAN channel: {channel}")
            can_channels.add(channel)

            for ecu in zone.get("ecus", []):
                ecu_name = ecu.get("ecu_name", "")
                if not ecu_name:
                    errors.append(f"{zone_id} has ECU without ecu_name")
                    continue
                if ecu_name in ecu_names:
                    errors.append(f"duplicate ECU name: {ecu_name}")
                ecu_names.add(ecu_name)

                logical_address = parse_int(ecu["logical_address"])
                if logical_address in logical_addresses:
                    errors.append(f"duplicate logical address: {hex(logical_address)}")
                logical_addresses.add(logical_address)

                can_id = parse_int(ecu["can_id"])
                if can_id in can_ids:
                    errors.append(f"duplicate CAN ID: {hex(can_id)}")
                can_ids.add(can_id)

                dependencies[ecu_name] = list(ecu.get("dependencies", []))

        for ecu_name, deps in dependencies.items():
            for dependency in deps:
                if dependency not in ecu_names:
                    errors.append(
                        f"{ecu_name} depends on unknown ECU: {dependency}"
                    )

        errors.extend(self._dependency_cycle_errors(dependencies))
        return errors

    @staticmethod
    def _dependency_cycle_errors(dependencies: dict[str, list[str]]) -> list[str]:
        visiting: set[str] = set()
        visited: set[str] = set()
        errors: list[str] = []

        def visit(node: str, path: list[str]) -> None:
            if node in visiting:
                cycle = " -> ".join(path + [node])
                errors.append(f"dependency cycle detected: {cycle}")
                return
            if node in visited:
                return

            visiting.add(node)
            for dependency in dependencies.get(node, []):
                visit(dependency, path + [node])
            visiting.remove(node)
            visited.add(node)

        for ecu_name in dependencies:
            visit(ecu_name, [])

        return errors
