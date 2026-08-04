import tempfile
import unittest
from pathlib import Path

from integrations.mender.package_artifact import build_artifact_command


class MenderArtifactPackagingTest(unittest.TestCase):
    def test_build_artifact_command_includes_update_module_type_and_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            payload_dir = Path(temp_dir)
            (payload_dir / "deployment.json").write_text("{}", encoding="utf-8")
            (payload_dir / "campaign.json").write_text("{}", encoding="utf-8")

            command = build_artifact_command(
                "virtual-ota-default-doip",
                payload_dir / "artifact.mender",
                "virtual-ota-tcu",
                payload_dir,
                software_name="virtual-ota",
                software_version="2.0.0",
            )

            self.assertIn("module-image", command)
            self.assertIn("tcu-ota-module", command)
            self.assertIn(str(payload_dir / "deployment.json"), command)
            self.assertIn(str(payload_dir / "campaign.json"), command)


if __name__ == "__main__":
    unittest.main()
