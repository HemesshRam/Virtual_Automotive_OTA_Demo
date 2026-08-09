from tcu.models.vehicle import Vehicle
from tcu.models.campaign import Campaign
from common.utils import normalize_transport
from common.utils import version_lt
from tcu.dependency_policy import DependencyPolicyResolver


class CompatibilityValidator:

    def __init__(self):
        self.policy_resolver = DependencyPolicyResolver()

    def validate(self, vehicle: Vehicle, campaign: Campaign):

        print()
        print("=" * 55)
        print("CAMPAIGN COMPATIBILITY VALIDATION")
        print("=" * 55)

        overall_result = True
        skipped_optional = []
        approved_targets = []

        for target in campaign.targets:

            print()
            print("-" * 55)
            print(target.ecu_name)

            ecu = None

            for e in vehicle.get_all_ecus():
                if e.ecu_name == target.ecu_name:
                    ecu = e
                    break

            target_failed = False

            if ecu is None:
                print("✗ ECU Not Found")
                target_failed = True
                if self._target_can_be_skipped(target, reason="ECU_NOT_FOUND"):
                    skipped_optional.append((target.ecu_name, "ECU_NOT_FOUND"))
                    print("→ Target will be skipped by availability policy")
                    continue
                overall_result = False
                continue

            print("✓ ECU Found")

            if ecu.hardware_variant != target.hardware_variant:
                print("✗ Hardware Variant Mismatch")
                target_failed = True
            else:
                print("✓ Hardware Variant Compatible")

            if version_lt(ecu.current_version, target.minimum_supported_version):
                print("✗ Current Version Too Old")
                target_failed = True
            else:
                print("✓ Current Version Compatible")

            if version_lt(ecu.bootloader_version, target.minimum_bootloader):
                print("✗ Bootloader Version Too Old")
                target_failed = True
            else:
                print("✓ Bootloader Compatible")

            if normalize_transport(ecu.transport) != normalize_transport(campaign.transport):
                print("✗ Transport Not Supported")
                target_failed = True
            else:
                print("✓ Transport Supported")

            if not ecu.rollback_supported:
                print("✗ Rollback Unsupported")
                target_failed = True
            else:
                print("✓ Rollback Supported")

            if target_failed:
                if not self._target_can_be_skipped(target, reason="INCOMPATIBLE"):
                    overall_result = False
                else:
                    skipped_optional.append((target.ecu_name, "INCOMPATIBLE"))
                    print("→ Target will be skipped by availability policy")
            else:
                approved_targets.append(target.ecu_name)

        campaign.approved_targets = approved_targets
        campaign.skipped_optional_targets = skipped_optional

        print()
        print("=" * 55)

        if skipped_optional:
            print("OPTIONAL TARGETS SKIPPED")
            for ecu_name, reason in skipped_optional:
                print(f"- {ecu_name} : {reason}")
            print("=" * 55)

        if overall_result:
            print("CAMPAIGN ACCEPTED")
        else:
            print("CAMPAIGN REJECTED")

        print("=" * 55)

        return overall_result

    def _target_can_be_skipped(self, target, reason: str) -> bool:
        if reason == "ECU_NOT_FOUND" and getattr(target, "skip_if_unavailable", False):
            return True

        if reason == "INCOMPATIBLE" and getattr(target, "skip_if_incompatible", False):
            return True

        if not target.mandatory:
            return True

        policy = self.policy_resolver.for_ecu(target.ecu_name)
        return not policy.unavailable_aborts_campaign
