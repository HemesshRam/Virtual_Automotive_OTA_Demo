import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_RELEASE_DIR = Path("firmware/releases/2.0.0")


def canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")


def sign_payload(key_hex: str, signed: dict) -> str:
    return hmac.new(
        bytes.fromhex(key_hex),
        canonical_json_bytes(signed),
        hashlib.sha256,
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(4096)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def iso_utc(days_from_now: int) -> str:
    value = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return value.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def _next_version(role: dict) -> int:
    return int(role["signed"].get("version", 0)) + 1


def _build_target_entry(package: dict, artifact_path: Path) -> dict:
    custom = {
        "ecu_name": package["ecu_name"],
        "hardware_variant": package["hardware_variant"],
        "target_version": package["target_version"],
        "minimum_bootloader": package["minimum_bootloader"],
        "transport_support": package.get("transport_support") or [package["transport"]],
    }

    if "flash_address" in package:
        custom["flash_address"] = package["flash_address"]
    if "part_number" in package:
        custom["part_number"] = package["part_number"]
    if "image_format" in package:
        custom["image_format"] = package["image_format"]
    if "payload_sha256" in package:
        custom["payload_sha256"] = package["payload_sha256"]

    return {
        "length": artifact_path.stat().st_size,
        "hashes": {
            "sha256": sha256_file(artifact_path),
        },
        "custom": custom,
    }


def refresh_demo_trust_metadata(release_dir: Path = DEFAULT_RELEASE_DIR) -> dict:
    metadata_dir = release_dir / "metadata"
    root_path = metadata_dir / "root.json"
    targets_path = metadata_dir / "targets.json"
    snapshot_path = metadata_dir / "snapshot.json"
    timestamp_path = metadata_dir / "timestamp.json"
    manifest_path = release_dir / "manifest.json"

    root = load_json(root_path)
    targets = load_json(targets_path)
    snapshot = load_json(snapshot_path)
    timestamp = load_json(timestamp_path)
    manifest = load_json(manifest_path)

    key_hex = root["signed"]["keys"]["demo-root"]["key"]

    refreshed_targets = {}
    for package in manifest["packages"]:
        artifact_path = release_dir / package["file"]
        if not artifact_path.exists():
            raise FileNotFoundError(f"Firmware artifact missing for trust metadata refresh: {artifact_path}")
        refreshed_targets[package["file"]] = _build_target_entry(package, artifact_path)

    targets["signed"]["version"] = _next_version(targets)
    targets["signed"]["expires"] = iso_utc(59)
    targets["signed"]["targets"] = refreshed_targets
    targets["signatures"][0]["sig"] = sign_payload(key_hex, targets["signed"])
    targets_bytes = canonical_json_bytes(targets)

    snapshot["signed"]["version"] = _next_version(snapshot)
    snapshot["signed"]["expires"] = iso_utc(60)
    snapshot["signed"]["meta"]["targets.json"] = {
        "version": targets["signed"]["version"],
        "length": len(targets_bytes),
        "hashes": {
            "sha256": hashlib.sha256(targets_bytes).hexdigest(),
        },
    }
    snapshot["signatures"][0]["sig"] = sign_payload(key_hex, snapshot["signed"])
    snapshot_bytes = canonical_json_bytes(snapshot)

    timestamp["signed"]["version"] = _next_version(timestamp)
    timestamp["signed"]["expires"] = iso_utc(61)
    timestamp["signed"]["meta"]["snapshot.json"] = {
        "version": snapshot["signed"]["version"],
        "length": len(snapshot_bytes),
        "hashes": {
            "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        },
    }
    timestamp["signatures"][0]["sig"] = sign_payload(key_hex, timestamp["signed"])

    write_json(targets_path, targets)
    write_json(snapshot_path, snapshot)
    write_json(timestamp_path, timestamp)

    return {
        "targets_version": targets["signed"]["version"],
        "snapshot_version": snapshot["signed"]["version"],
        "timestamp_version": timestamp["signed"]["version"],
        "target_count": len(refreshed_targets),
        "targets_expires": targets["signed"]["expires"],
        "snapshot_expires": snapshot["signed"]["expires"],
        "timestamp_expires": timestamp["signed"]["expires"],
    }


def main() -> int:
    result = refresh_demo_trust_metadata()
    print("Refreshed demo trust metadata")
    print(f"targets.version   = {result['targets_version']}")
    print(f"snapshot.version  = {result['snapshot_version']}")
    print(f"timestamp.version = {result['timestamp_version']}")
    print(f"trusted targets   = {result['target_count']}")
    print(f"targets.expires   = {result['targets_expires']}")
    print(f"snapshot.expires  = {result['snapshot_expires']}")
    print(f"timestamp.expires = {result['timestamp_expires']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
