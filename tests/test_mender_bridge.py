import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.mender.build_payload_dir import build_payload_dir, load_profiles
from integrations.mender.run_tcu_from_mender import run_from_payload
from tcu.cloud_client import OTACloudClient


class MenderBridgeTest(unittest.TestCase):
    def test_cloud_client_can_load_campaign_from_local_file_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            campaign_path = Path(temp_dir) / "campaign.json"
            campaign_path.write_text(
                json.dumps({"campaign_id": "TEST", "targets": []}),
                encoding="utf-8",
            )
            previous = os.environ.get("OTA_CAMPAIGN_URL")
            os.environ["OTA_CAMPAIGN_URL"] = f"file://{campaign_path}"
            self.addCleanup(
                lambda: os.environ.pop("OTA_CAMPAIGN_URL", None)
                if previous is None else os.environ.__setitem__("OTA_CAMPAIGN_URL", previous)
            )

            campaign = OTACloudClient().download_campaign()
            self.assertEqual(campaign["campaign_id"], "TEST")

    @patch("integrations.mender.run_tcu_from_mender.tcu_main", return_value=0)
    def test_run_from_payload_sets_http_control_and_local_campaign(self, _tcu_main):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_dir = Path(temp_dir)
            (payload_dir / "campaign.json").write_text(
                json.dumps({"campaign_id": "LOCAL", "targets": []}),
                encoding="utf-8",
            )
            (payload_dir / "deployment.json").write_text(
                json.dumps(
                    {
                        "scenario": "scenarios/dynamic_demo_template.json",
                        "scenario_name": "mender_test",
                        "transport": "doip",
                        "topology_mode": "default",
                        "dependency_mode": "topology_default",
                        "cloud_control": "http",
                        "quiet": 1,
                        "campaign_file": "campaign.json",
                        "tls_verify": "docker/tls/demo-ca.crt",
                    }
                ),
                encoding="utf-8",
            )

            result = run_from_payload(payload_dir)

            self.assertEqual(result, 0)
            self.assertEqual(os.environ["OTA_CLOUD_CONTROL"], "http")
            self.assertTrue(os.environ["OTA_CAMPAIGN_URL"].startswith("file://"))
            self.assertTrue(
                os.environ["OTA_EXECUTION_SUMMARY_PATH"].endswith("mender_execution_summary.json")
            )

    @patch("integrations.mender.run_tcu_from_mender.tcu_main", return_value=0)
    def test_run_from_payload_can_merge_active_dynamic_scenario(self, _tcu_main):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_dir = Path(temp_dir)
            active_dir = payload_dir / "runtime" / "mender"
            active_dir.mkdir(parents=True, exist_ok=True)

            (payload_dir / "campaign.json").write_text(
                json.dumps({"campaign_id": "LOCAL", "targets": []}),
                encoding="utf-8",
            )
            (payload_dir / "deployment.json").write_text(
                json.dumps(
                    {
                        "scenario": "scenarios/dynamic_demo_template.json",
                        "scenario_name": "mender_generic",
                        "transport": "doip",
                        "topology_mode": "default",
                        "dependency_mode": "topology_default",
                        "cloud_control": "http",
                        "quiet": 1,
                        "campaign_file": "campaign.json",
                        "tls_verify": "docker/tls/demo-ca.crt",
                        "use_active_scenario": True,
                        "active_scenario_file": str(active_dir / "active_scenario.json"),
                    }
                ),
                encoding="utf-8",
            )
            (active_dir / "active_scenario.json").write_text(
                json.dumps(
                    {
                        "transport": "vcan",
                        "topology_mode": "body_two_ecus",
                        "dependency_mode": "cluster_depends_gateway",
                        "offline_ecus": ["Cluster ECU"],
                    }
                ),
                encoding="utf-8",
            )

            result = run_from_payload(payload_dir)

            self.assertEqual(result, 0)
            self.assertEqual(os.environ["OTA_TRANSPORT"], "vcan")
            self.assertEqual(os.environ["OTA_SCENARIO_TOPOLOGY_MODE"], "body_two_ecus")
            self.assertEqual(os.environ["OTA_SCENARIO_DEPENDENCY_MODE"], "cluster_depends_gateway")
            self.assertEqual(os.environ["OTA_SCENARIO_OFFLINE_ECUS"], "Cluster ECU")

    def test_build_payload_dir_creates_expected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "payload"
            campaign = Path(temp_dir) / "campaign.json"
            campaign.write_text(
                json.dumps({"campaign_id": "LOCAL", "targets": []}),
                encoding="utf-8",
            )

            build_payload_dir(output_dir, campaign, transport="vcan")

            self.assertTrue((output_dir / "deployment.json").exists())
            self.assertTrue((output_dir / "campaign.json").exists())

    def test_deployment_profiles_include_default_doip(self):
        profiles = load_profiles()
        self.assertIn("default_doip", profiles)
        self.assertEqual(profiles["default_doip"]["transport"], "doip")
        self.assertIn("dynamic_generic", profiles)
        self.assertTrue(profiles["dynamic_generic"]["use_active_scenario"])

    def test_build_payload_dir_supports_profile_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "payload"
            campaign = Path(temp_dir) / "campaign.json"
            campaign.write_text(
                json.dumps({"campaign_id": "LOCAL", "targets": []}),
                encoding="utf-8",
            )

            profiles = load_profiles()
            profile = profiles["gateway_offline"]
            build_payload_dir(
                output_dir,
                campaign,
                transport=profile["transport"],
                topology_mode=profile["topology_mode"],
                dependency_mode=profile["dependency_mode"],
                offline_ecus=profile["offline_ecus"],
            )

            with open(output_dir / "deployment.json", "r", encoding="utf-8") as fp:
                deployment = json.load(fp)

            self.assertEqual(deployment["transport"], "doip")
            self.assertEqual(deployment["offline_ecus"], ["Gateway ECU"])


if __name__ == "__main__":
    unittest.main()
