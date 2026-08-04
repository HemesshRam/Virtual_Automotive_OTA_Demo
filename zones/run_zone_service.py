import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zones.base.zone_service import ZoneService
from zones.zone_registry import ZONE_REGISTRY


def main():
    parser = argparse.ArgumentParser(description="Run a simulated zonal controller")
    parser.add_argument("zone_id", choices=sorted(ZONE_REGISTRY))
    args = parser.parse_args()

    ZoneService(args.zone_id, ZONE_REGISTRY[args.zone_id]).start()


if __name__ == "__main__":
    main()
