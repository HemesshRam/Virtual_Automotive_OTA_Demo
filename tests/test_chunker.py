import argparse

from transport.can.firmware_chunker import FirmwareChunker
from common.message_types import MessageType


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect legacy raw CAN firmware chunks in a readable format."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="print every chunk instead of only the preview",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="number of chunks to preview when --all is not set",
    )
    args = parser.parse_args(argv)

    chunker = FirmwareChunker(
        "firmware/releases/2.0.0/gateway_v2.bin"
    )

    print()

    print("Firmware Size :", chunker.firmware_size())
    print("Total Chunks  :", chunker.total_chunks())

    print()

    for index, chunk in enumerate(chunker.chunks(), start=1):
        if not args.all and index > args.limit:
            remaining = chunker.total_chunks() - args.limit
            print(f"... {remaining} more chunks hidden; rerun with --all for full dump")
            break

        message_type = MessageType(chunk[0]).name
        sequence = chunk[1]
        payload = chunk[2:]

        print(
            f"Chunk {index:04d} | "
            f"type={message_type} | "
            f"seq={sequence:03d} | "
            f"payload={payload.hex(' ').upper()}"
        )


if __name__ == "__main__":
    main()
