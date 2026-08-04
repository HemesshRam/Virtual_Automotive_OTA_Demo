import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent


ECUS = [
    "gateway",
    "bcm",
    "cluster",
]


def reset_version(ecu):

    version_file = PROJECT_ROOT / "ecus" / ecu / "version.json"

    data = {
        "version": "1.0.0"
    }

    with open(version_file, "w") as f:
        json.dump(data, f, indent=4)

    print(f"[OK] {ecu} version reset")


def clear_folder(folder):

    if not folder.exists():
        return

    for item in folder.iterdir():

        if item.is_file():
            item.unlink()

        elif item.is_dir():
            shutil.rmtree(item)


def reset_ecu_state(ecu):

    downloads = PROJECT_ROOT / "ecus" / ecu / "downloads"
    installed = PROJECT_ROOT / "ecus" / ecu / "installed"

    clear_folder(downloads)
    clear_folder(installed)

    print(f"[OK] {ecu} downloads cleared")
    print(f"[OK] {ecu} installed firmware cleared")


def main():

    print()
    print("=" * 60)
    print("AUTOMOTIVE OTA DEMO RESET")
    print("=" * 60)

    for ecu in ECUS:

        reset_version(ecu)
        reset_ecu_state(ecu)

    print()
    print("=" * 60)
    print("DEMO RESET COMPLETED")
    print("=" * 60)
    print()
    print("All ECUs restored to Version 1.0.0")
    print("Downloads removed")
    print("Installed firmware removed")
    print("Ready for next OTA campaign")


if __name__ == "__main__":
    main()
