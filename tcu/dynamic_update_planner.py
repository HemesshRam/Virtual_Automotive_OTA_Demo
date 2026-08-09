from dataclasses import dataclass, field
import json
from pathlib import Path

from common.utils import version_eq
from tcu.dependency_manager import TopologicalUpdatePlanner
from tcu.dependency_policy import DependencyPolicyResolver
from tcu.models.dependency_graph import DependencyGraph


DEFAULT_POLICY_PATH = Path("vehicle/update_planning_policy.json")


@dataclass
class DynamicUpdatePlan:
    update_order: list[str]
    dependency_map: dict[str, set[str]]
    dependency_sources: dict[str, str]
    classifications: dict[str, str]
    blocking_errors: list[str] = field(default_factory=list)

    @property
    def executable(self) -> bool:
        return not self.blocking_errors


class DynamicUpdatePlanner:
    """
    Builds the final executable OTA plan from campaign intent and live vehicle state.
    """

    def __init__(self, policy_path: str | Path = DEFAULT_POLICY_PATH):
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.policy_resolver = DependencyPolicyResolver()

    def plan(self, vehicle, campaign, eligible_updates) -> DynamicUpdatePlan:
        discovered_by_name = {
            ecu.ecu_name: ecu
            for ecu in vehicle.get_all_ecus()
        }
        eligible_by_name = {
            entry["ecu"].ecu_name: entry
            for entry in eligible_updates
        }
        target_by_name = {
            target.ecu_name: target
            for target in campaign.targets
        }
        skipped_targets = {
            ecu_name: reason
            for ecu_name, reason in getattr(campaign, "skipped_optional_targets", [])
        }

        classifications = {}
        blocking_errors = []

        for ecu_name, target in target_by_name.items():
            ecu = discovered_by_name.get(ecu_name)
            policy = self.policy_resolver.for_ecu(ecu_name)

            if ecu_name in eligible_by_name:
                classifications[ecu_name] = "ELIGIBLE"
                continue

            if ecu_name in skipped_targets:
                classifications[ecu_name] = f"SKIPPED_OPTIONAL:{skipped_targets[ecu_name]}"
                continue

            if ecu is None:
                if (
                    target.mandatory
                    and not getattr(target, "skip_if_unavailable", False)
                    and policy.unavailable_aborts_campaign
                ):
                    classifications[ecu_name] = "ABORT_REQUIRED:ECU_NOT_FOUND"
                    blocking_errors.append(f"{ecu_name} is mandatory but not discovered")
                else:
                    classifications[ecu_name] = "SKIPPED_OPTIONAL:ECU_NOT_FOUND"
                continue

            if self._version_matches(ecu.current_version, target.target_version):
                classifications[ecu_name] = "ALREADY_SATISFIED"
            elif (
                target.mandatory
                and not getattr(target, "skip_if_incompatible", False)
            ) or (
                policy.unavailable_aborts_campaign
                and not getattr(target, "skip_if_incompatible", False)
            ):
                classifications[ecu_name] = "ABORT_REQUIRED:NOT_ELIGIBLE"
                blocking_errors.append(
                    f"{ecu_name} is required but not eligible for update"
                )
            else:
                classifications[ecu_name] = "SKIPPED_OPTIONAL:NOT_ELIGIBLE"

        dependency_map, dependency_sources, dependency_errors = (
            self._resolve_dependencies(target_by_name, campaign)
        )
        blocking_errors.extend(dependency_errors)

        executable_names = {
            ecu_name
            for ecu_name, classification in classifications.items()
            if classification == "ELIGIBLE"
        }
        satisfied_names = {
            ecu_name
            for ecu_name, classification in classifications.items()
            if classification == "ALREADY_SATISFIED"
        }
        changed = True
        while changed:
            changed = False
            skipped_names = {
                ecu_name
                for ecu_name, classification in classifications.items()
                if classification.startswith("SKIPPED")
                or classification.startswith("BLOCKED_BY_DEPENDENCY")
                or classification.startswith("ABORT_REQUIRED")
            }

            for ecu_name in sorted(executable_names):
                policy = self.policy_resolver.for_ecu(ecu_name)
                dependencies = dependency_map.get(ecu_name, set())
                missing = dependencies - executable_names - satisfied_names
                missing_blocking = missing - skipped_names
                skipped_blocking = missing & skipped_names

                if missing_blocking or skipped_blocking:
                    reason = "DEPENDENCY_UNAVAILABLE"
                    if skipped_blocking:
                        reason = "DEPENDENCY_SKIPPED"
                    classifications[ecu_name] = f"BLOCKED_BY_DEPENDENCY:{reason}"
                    executable_names.remove(ecu_name)
                    changed = True
                    if policy.dependency_failure_aborts_campaign:
                        blocking_errors.append(
                            f"{ecu_name} has blocking dependencies: "
                            f"{', '.join(sorted(missing))}"
                        )
                    break

        graph = DependencyGraph()
        for ecu_name in executable_names:
            graph.add_node(ecu_name)
        for ecu_name in executable_names:
            for dependency in dependency_map.get(ecu_name, set()):
                if dependency in executable_names:
                    graph.add_dependency(dependency, ecu_name)

        target_priority = {
            target.ecu_name: target.priority
            for target in campaign.targets
        }

        update_order = []
        if graph.nodes:
            update_order = TopologicalUpdatePlanner().plan(
                graph,
                priority=target_priority,
            )

        return DynamicUpdatePlan(
            update_order=update_order,
            dependency_map=dependency_map,
            dependency_sources=dependency_sources,
            classifications=classifications,
            blocking_errors=blocking_errors,
        )

    def print_report(self, plan: DynamicUpdatePlan, vehicle, campaign) -> None:
        if not self.policy.get("print_planning_report", True):
            return

        discovered_by_name = {
            ecu.ecu_name: ecu
            for ecu in vehicle.get_all_ecus()
        }

        print()
        print("=" * 60)
        print("DYNAMIC OTA UPDATE PLAN")
        print("=" * 60)
        print(f"Campaign : {campaign.campaign_id}")
        print(f"Transport : {campaign.transport}")
        print(f"Planner   : {self.policy.get('planning_mode', 'dynamic')}")

        print()
        print("Live Inventory:")
        for target in campaign.targets:
            ecu = discovered_by_name.get(target.ecu_name)
            current = ecu.current_version if ecu else "unknown"
            state = getattr(ecu, "health", "OFFLINE") if ecu else "OFFLINE"
            print(
                f"- {target.ecu_name:<12} "
                f"state={state:<8} current={current:<8} "
                f"target={target.target_version:<8} "
                f"mandatory={target.mandatory}"
            )

        print()
        print("Dependency Resolution:")
        for target in campaign.targets:
            dependencies = sorted(plan.dependency_map.get(target.ecu_name, set()))
            depends_on = ", ".join(dependencies) if dependencies else "None"
            source = plan.dependency_sources.get(target.ecu_name, "none")
            print(f"- {target.ecu_name:<12} depends_on={depends_on} source={source}")

        print()
        print("Eligibility Classification:")
        for target in campaign.targets:
            classification = plan.classifications.get(target.ecu_name, "UNKNOWN")
            reason = self._classification_reason(classification)
            print(f"- {target.ecu_name:<12} {classification}")
            if reason:
                print(f"  reason={reason}")

        print()
        print("Topological Execution Plan:")
        if plan.update_order:
            for index, ecu_name in enumerate(plan.update_order, start=1):
                print(f"{index}. {ecu_name}")
        else:
            print("- No executable updates")

        if plan.blocking_errors:
            print()
            print("Blocking Errors:")
            for error in plan.blocking_errors:
                print(f"✗ {error}")

        print("=" * 60)

    def _resolve_dependencies(self, target_by_name, campaign):
        dependency_overrides = getattr(campaign, "dependency_overrides", {}) or {}
        dependency_map = {}
        dependency_sources = {}
        errors = []
        known_names = set(self.policy_resolver.topology.ecu_registry())
        known_names.update(target_by_name)

        for ecu_name in target_by_name:
            if ecu_name in dependency_overrides:
                dependencies = set(dependency_overrides[ecu_name])
                source = "campaign_overrides"
            else:
                policy = self.policy_resolver.for_ecu(ecu_name)
                dependencies = set(policy.dependencies)
                source = "vehicle_topology" if dependencies else "none"

            for dependency in dependencies:
                if dependency not in known_names:
                    errors.append(f"{ecu_name} depends on unknown ECU: {dependency}")

            dependency_map[ecu_name] = dependencies
            dependency_sources[ecu_name] = source

        if not errors:
            try:
                self._validate_cycle(dependency_map)
            except RuntimeError as exc:
                errors.append(str(exc))

        return dependency_map, dependency_sources, errors

    @staticmethod
    def _validate_cycle(dependency_map: dict[str, set[str]]) -> None:
        graph = DependencyGraph()
        for ecu_name in dependency_map:
            graph.add_node(ecu_name)
        for ecu_name, dependencies in dependency_map.items():
            for dependency in dependencies:
                if dependency in dependency_map:
                    graph.add_dependency(dependency, ecu_name)
        TopologicalUpdatePlanner().plan(graph)

    @staticmethod
    def _version_matches(current_version: str, target_version: str) -> bool:
        if not current_version or not target_version:
            return False
        try:
            return version_eq(current_version, target_version)
        except (AttributeError, TypeError, ValueError):
            return current_version == target_version

    @staticmethod
    def _classification_reason(classification: str) -> str:
        if classification == "ELIGIBLE":
            return "update will be executed because target version is newer and compatible"
        if classification == "ALREADY_SATISFIED":
            return "skip because current ECU version already matches the campaign target version"
        if classification.startswith("SKIPPED_OPTIONAL:"):
            return "optional ECU target is not executable and will be skipped by policy"
        if classification.startswith("BLOCKED_BY_DEPENDENCY:"):
            return "ECU cannot execute because one or more dependencies are not satisfied"
        if classification.startswith("ABORT_REQUIRED:"):
            return "required ECU target is not executable and campaign must not proceed"
        return ""

    def _load_policy(self) -> dict:
        if not self.policy_path.exists():
            return {"planning_mode": "dynamic", "print_planning_report": True}
        with open(self.policy_path, "r", encoding="utf-8") as fp:
            return json.load(fp)
