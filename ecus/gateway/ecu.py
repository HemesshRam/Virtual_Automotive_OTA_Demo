from pathlib import Path

from ecus.base.ecu_base import ECUBase


def main():
    ecu = ECUBase(Path(__file__).parent)
    ecu.run()


if __name__ == "__main__":
    main()