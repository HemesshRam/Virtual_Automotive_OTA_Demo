import json
import tempfile
import unittest
from pathlib import Path

from tcu.execution_summary import ExecutionSummary, ExecutionSummaryWriter


class ExecutionSummaryTest(unittest.TestCase):
    def test_writer_persists_summary_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "summary.json"
            writer = ExecutionSummaryWriter(str(path))
            writer.write(
                ExecutionSummary(
                    status="COMPLETED",
                    transport="DOIP",
                    cloud_control="http",
                    campaign_id="OTA_2026_001",
                    reason="FLASHING COMPLETE",
                    discovered_ecus=["Gateway ECU", "BCM ECU"],
                    eligible_ecus=["Gateway ECU"],
                    update_order=["Gateway ECU"],
                    platform_definition="vehicle/platform_definition.json",
                    runtime_mapping="vehicle/runtime_mapping.local.json",
                    scenario_name="mender_test",
                    per_ecu_results=[{"ecu": "Gateway ECU", "status": "PENDING"}],
                )
            )

            with open(path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)

            self.assertEqual(payload["status"], "COMPLETED")
            self.assertEqual(payload["campaign_id"], "OTA_2026_001")
            self.assertEqual(payload["per_ecu_results"][0]["ecu"], "Gateway ECU")


if __name__ == "__main__":
    unittest.main()
