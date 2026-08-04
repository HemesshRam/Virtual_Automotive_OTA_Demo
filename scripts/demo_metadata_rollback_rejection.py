import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tcu.trust.uptane_verifier import UptaneVerifier


def main():
    release_dir = Path("firmware/releases/2.0.0")

    with TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "trusted_metadata_state.json"

        print("Priming local trusted metadata state...")
        UptaneVerifier(release_dir, state_path=state_path).verify()

        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["roles"]["targets"]["version"] = 2
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        print()
        print("Simulating repository rollback:")
        print("  local trusted targets version : 2")
        print("  repository targets version    : 1")
        print()

        try:
            UptaneVerifier(release_dir, state_path=state_path).verify()
        except RuntimeError as exc:
            print(f"[OK] Rollback rejected: {exc}")
            return

        raise SystemExit("[FAIL] Metadata rollback was not rejected")


if __name__ == "__main__":
    main()
