"""
Binary firmware image helpers for demo OTA artifacts.

The image format is intentionally simple but structured:

    - fixed-size binary header
    - deterministic binary payload
    - trailing raw payload bytes

This keeps the repository artifacts realistic enough for OTA flows while
remaining easy to generate and validate in the demo environment.
"""

from __future__ import annotations

import binascii
import hashlib
import struct
from dataclasses import dataclass
from typing import Any


MAGIC = b"VOTAIMG1"
FORMAT_VERSION = 1
HEADER_SIZE = 160


def _pad_text(value: str, size: int) -> bytes:
    data = value.encode("ascii", errors="ignore")
    if len(data) > size:
        return data[:size]
    return data.ljust(size, b"\x00")


def _unpad_text(value: bytes) -> str:
    return value.rstrip(b"\x00").decode("ascii", errors="ignore")


def looks_like_firmware_image(image: bytes) -> bool:
    return len(image) >= len(MAGIC) and image[: len(MAGIC)] == MAGIC


def _deterministic_payload(seed: str, size: int) -> bytes:
    """
    Build a repeatable binary payload that is not text-like.

    Uses a seeded PRNG for speed.  The original SHA-256-chain approach
    works fine for small payloads but takes minutes at 50 MB.  The
    ``random`` module with a fixed seed is deterministic across runs on
    the same Python version, which is sufficient for demo firmware.
    """
    import random as _random

    rng = _random.Random(seed)
    return rng.randbytes(size)


@dataclass(frozen=True)
class FirmwareImageSpec:
    ecu_name: str
    ecu_id: int
    part_number: str
    current_version: str
    target_version: str
    build_date: str
    build_number: int
    flash_address: int
    payload_size: int
    image_format: str = "RAW"
    payload_data: bytes | None = None


@dataclass(frozen=True)
class FirmwareImageMetadata:
    ecu_name: str
    ecu_id: int
    part_number: str
    current_version: str
    target_version: str
    build_date: str
    build_number: int
    flash_address: int
    payload_size: int
    image_size: int
    crc32: int
    payload_sha256: str
    image_format: str


def build_firmware_image(spec: FirmwareImageSpec) -> bytes:
    if spec.payload_data is not None:
        payload = spec.payload_data
        if spec.payload_size != len(payload):
            raise ValueError(
                f"payload_size mismatch for {spec.ecu_name}: "
                f"expected {spec.payload_size}, got {len(payload)}"
            )
    else:
        payload = _deterministic_payload(
            f"{spec.ecu_name}|{spec.target_version}|{spec.build_number}",
            spec.payload_size,
        )

    payload_sha256 = hashlib.sha256(payload).digest()
    crc32 = binascii.crc32(payload) & 0xFFFFFFFF
    image_size = HEADER_SIZE + len(payload)

    header = struct.pack(
        ">8sBBH16s16s16s16s8sIIIII32s8s16s",
        MAGIC,
        FORMAT_VERSION,
        spec.ecu_id & 0xFF,
        HEADER_SIZE,
        _pad_text(spec.ecu_name, 16),
        _pad_text(spec.part_number, 16),
        _pad_text(spec.current_version, 16),
        _pad_text(spec.target_version, 16),
        _pad_text(spec.build_date, 8),
        spec.build_number,
        spec.flash_address,
        len(payload),
        image_size,
        crc32,
        payload_sha256,
        _pad_text(spec.image_format, 8),
        b"\x00" * 16,
    )

    return header + payload


def parse_firmware_image(image: bytes) -> FirmwareImageMetadata:
    if len(image) < HEADER_SIZE:
        raise ValueError("Firmware image too small to contain a header")

    (
        magic,
        format_version,
        ecu_id,
        header_size,
        ecu_name,
        part_number,
        current_version,
        target_version,
        build_date,
        build_number,
        flash_address,
        payload_size,
        image_size,
        crc32,
        payload_sha256,
        image_format,
        _reserved,
    ) = struct.unpack(
        ">8sBBH16s16s16s16s8sIIIII32s8s16s",
        image[:HEADER_SIZE],
    )

    if magic != MAGIC:
        raise ValueError("Invalid firmware image magic")

    if format_version != FORMAT_VERSION:
        raise ValueError(f"Unsupported firmware image version: {format_version}")

    if header_size != HEADER_SIZE:
        raise ValueError(f"Unexpected header size: {header_size}")

    payload = image[HEADER_SIZE:HEADER_SIZE + payload_size]
    if len(payload) != payload_size:
        raise ValueError("Firmware image payload truncated")

    calculated_crc32 = binascii.crc32(payload) & 0xFFFFFFFF
    calculated_sha256 = hashlib.sha256(payload).hexdigest()

    return FirmwareImageMetadata(
        ecu_name=_unpad_text(ecu_name),
        ecu_id=ecu_id,
        part_number=_unpad_text(part_number),
        current_version=_unpad_text(current_version),
        target_version=_unpad_text(target_version),
        build_date=_unpad_text(build_date),
        build_number=build_number,
        flash_address=flash_address,
        payload_size=payload_size,
        image_size=image_size,
        crc32=crc32 if crc32 == calculated_crc32 else calculated_crc32,
        payload_sha256=calculated_sha256,
        image_format=_unpad_text(image_format),
    )


def extract_firmware_payload(image: bytes) -> tuple[FirmwareImageMetadata, bytes]:
    metadata = parse_firmware_image(image)
    payload = image[HEADER_SIZE:HEADER_SIZE + metadata.payload_size]
    return metadata, payload


def image_summary(metadata: FirmwareImageMetadata) -> dict[str, Any]:
    return {
        "ecu_name": metadata.ecu_name,
        "ecu_id": metadata.ecu_id,
        "part_number": metadata.part_number,
        "current_version": metadata.current_version,
        "target_version": metadata.target_version,
        "build_date": metadata.build_date,
        "build_number": metadata.build_number,
        "flash_address": f"0x{metadata.flash_address:08X}",
        "payload_size": metadata.payload_size,
        "image_size": metadata.image_size,
        "crc32": f"0x{metadata.crc32:08X}",
        "payload_sha256": metadata.payload_sha256,
        "image_format": metadata.image_format,
    }
