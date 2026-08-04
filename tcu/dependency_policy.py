from dataclasses import dataclass, field

from vehicle.topology_loader import VehicleTopology


@dataclass(frozen=True)
class ECUDependencyPolicy:
    ecu_name: str
    dependencies: list[str] = field(default_factory=list)
    criticality: str = "optional"
    on_unavailable: str = "skip"
    on_dependency_failed: str = "skip"

    @property
    def unavailable_aborts_campaign(self) -> bool:
        return self.criticality == "critical" or self.on_unavailable == "abort_campaign"

    @property
    def dependency_failure_aborts_campaign(self) -> bool:
        return (
            self.criticality == "critical"
            or self.on_dependency_failed == "abort_campaign"
        )


class DependencyPolicyResolver:
    def __init__(self):
        self.topology = VehicleTopology()

    def for_ecu(self, ecu_name: str) -> ECUDependencyPolicy:
        policy = self.topology.ecu_policy(ecu_name)
        return ECUDependencyPolicy(
            ecu_name=ecu_name,
            dependencies=list(policy.get("dependencies", [])),
            criticality=policy.get("criticality", "optional"),
            on_unavailable=policy.get("on_unavailable", "skip"),
            on_dependency_failed=policy.get("on_dependency_failed", "skip"),
        )
