from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: Any) -> "SemVer":
        if isinstance(value, SemVer):
            return value

        if value is None:
            raise ValueError("Version value cannot be None")

        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Version value cannot be empty")

        match = re.match(
            r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$",
            normalized,
        )

        if not match:
            raise ValueError(f"Invalid version value: {value!r}")

        major = int(match.group(1))
        minor = int(match.group(2) or 0)
        patch = int(match.group(3) or 0)

        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_version(value: Any) -> SemVer:
    return SemVer.parse(value)


def version_lt(left: Any, right: Any) -> bool:
    return parse_version(left) < parse_version(right)


def version_lte(left: Any, right: Any) -> bool:
    return parse_version(left) <= parse_version(right)


def version_eq(left: Any, right: Any) -> bool:
    return parse_version(left) == parse_version(right)


def version_gte(left: Any, right: Any) -> bool:
    return parse_version(left) >= parse_version(right)


def normalize_version(value: Any) -> str:
    return str(parse_version(value))


def normalize_transport(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().upper()
    aliases = {
        "CAN": "CAN",
        "VCAN": "VCAN",
        "DOIP": "DOIP",
        "ETHERNET": "ETHERNET",
    }
    return aliases.get(text, text)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return value
    return [value]
