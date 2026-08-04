"""
Checksum utilities for OTA firmware verification.

This module centralizes all SHA256 operations used by the
TCU and ECUs.
"""

import hashlib
from pathlib import Path


class SHA256Checksum:

    @staticmethod
    def calculate_bytes(data: bytes) -> str:
        """
        Calculate SHA256 from bytes.
        """
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def calculate_file(file_path: str | Path) -> str:
        """
        Calculate SHA256 of a file.
        """

        digest = hashlib.sha256()

        with open(file_path, "rb") as f:

            while True:

                chunk = f.read(4096)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    @staticmethod
    def verify(expected: str, actual: str) -> bool:
        """
        Compare two SHA256 hashes.
        """

        return expected.lower() == actual.lower()

    @staticmethod
    def file_size(file_path: str | Path) -> int:
        """
        Return firmware size in bytes.
        """

        return Path(file_path).stat().st_size