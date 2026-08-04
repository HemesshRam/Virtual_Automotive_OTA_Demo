import json
from pathlib import Path

from tcu.trust.uptane_verifier import UptaneVerifier


class FirmwareManifest:

    def __init__(self, path: str | Path | None = None):

        self.path = Path(path) if path is not None else Path(
            "firmware/releases/2.0.0/manifest.json"
        )

    def load(self, verify_trust: bool = False):

        if not self.path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as fp:
            manifest = json.load(fp)

        if "packages" not in manifest:
            raise ValueError("Manifest missing packages")

        if verify_trust:
            release_directory = self.path.parent
            trusted_targets = UptaneVerifier(release_directory).verify()
            manifest["_trusted_targets"] = {
                name: {
                    "file": value.file,
                    "length": value.length,
                    "sha256": value.sha256,
                    "custom": value.custom,
                }
                for name, value in trusted_targets.items()
            }

        return manifest
