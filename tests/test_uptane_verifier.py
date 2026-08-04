import unittest
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tcu.trust.uptane_verifier import UptaneVerifier


class UptaneVerifierTest(unittest.TestCase):

    def test_release_metadata_chain_verifies(self):
        with TemporaryDirectory() as tmp:
            trusted_targets = UptaneVerifier(
                "firmware/releases/2.0.0",
                state_path=Path(tmp) / "trusted_state.json",
            ).verify()

            self.assertEqual(set(trusted_targets.keys()), {
                "gateway_v2.bin",
                "bcm_v2.bin",
                "cluster_v2.bin",
            })
            self.assertEqual(
                trusted_targets["gateway_v2.bin"].custom["ecu_name"],
                "Gateway ECU",
            )

    def test_release_metadata_rejects_missing_custom_fields(self):
        release_dir = Path("firmware/releases/2.0.0")
        with TemporaryDirectory() as tmp:
            verifier = UptaneVerifier(release_dir, state_path=Path(tmp) / "trusted_state.json")

            original_load_role = verifier._load_role

            def tampered_load_role(filename, require_signatures=True):
                role = deepcopy(original_load_role(filename, require_signatures))
                if filename == "targets.json":
                    role["signed"]["targets"]["gateway_v2.bin"]["custom"].pop(
                        "transport_support",
                        None,
                    )
                return role

            with patch.object(verifier, "_load_role", side_effect=tampered_load_role):
                with patch.object(verifier, "_verify_signatures", return_value=None):
                    with patch.object(verifier, "_check_meta_binding", return_value=None):
                        with self.assertRaisesRegex(RuntimeError, "missing trusted custom metadata"):
                            verifier.verify()

    def test_release_metadata_rejects_version_rollback(self):
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "trusted_state.json"
            verifier = UptaneVerifier("firmware/releases/2.0.0", state_path=state_path)
            verifier.verify()

            trusted_state = state_path.read_text(encoding="utf-8")
            self.assertIn('"targets"', trusted_state)
            state = json.loads(trusted_state)
            state["roles"]["targets"]["version"] = 2
            state_path.write_text(json.dumps(state), encoding="utf-8")

            original_load_role = verifier._load_role

            def rollback_load_role(filename, require_signatures=True):
                role = deepcopy(original_load_role(filename, require_signatures))
                if filename == "targets.json":
                    role["signed"]["version"] = 1
                return role

            with patch.object(verifier, "_load_role", side_effect=rollback_load_role):
                with patch.object(verifier, "_verify_signatures", return_value=None):
                    with patch.object(verifier, "_check_meta_binding", return_value=None):
                        with self.assertRaisesRegex(RuntimeError, "targets metadata rollback detected"):
                            verifier.verify()


if __name__ == "__main__":
    unittest.main()
