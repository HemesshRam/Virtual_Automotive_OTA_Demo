import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TRUSTED_STATE_PATH = Path("tcu/trust/trusted_metadata_state.json")


def _canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(4096)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class TrustedTarget:
    file: str
    length: int
    sha256: str
    custom: dict


class UptaneVerifier:
    """
    Minimal Uptane-style trust gate for the demo release flow.

    This uses HMAC-SHA256 signatures from pinned root metadata so the repo
    gets a real metadata chain today without adding heavy PKI dependencies.
    """

    def __init__(self, release_directory: str | Path, state_path: str | Path = TRUSTED_STATE_PATH):
        self.release_directory = Path(release_directory)
        self.metadata_directory = self.release_directory / "metadata"
        self.state_path = Path(state_path)

    def verify(self) -> dict[str, TrustedTarget]:
        print()
        print("=" * 60)
        print("UPTANE-STYLE TRUST VERIFICATION")
        print("=" * 60)

        trusted_state = self._load_trusted_state()

        root = self._load_role("root.json", require_signatures=True)
        self._validate_root(root["signed"])
        self._check_expiry(root["signed"], "root")
        trusted_keys = root["signed"]["keys"]
        trusted_roles = root["signed"]["roles"]
        self._verify_signatures(root, "root", trusted_keys, trusted_roles["root"])
        self._check_rollback(root["signed"], "root", trusted_state)
        print("✓ Root trust anchor loaded")

        timestamp = self._load_and_verify_role("timestamp.json", "timestamp", trusted_keys, trusted_roles)
        snapshot = self._load_and_verify_role("snapshot.json", "snapshot", trusted_keys, trusted_roles)
        targets = self._load_and_verify_role("targets.json", "targets", trusted_keys, trusted_roles)

        for role_name, role in {
            "timestamp": timestamp,
            "snapshot": snapshot,
            "targets": targets,
        }.items():
            self._check_rollback(role["signed"], role_name, trusted_state)

        self._check_meta_binding(timestamp["signed"]["meta"], "snapshot.json", snapshot)
        print("✓ Timestamp -> Snapshot binding verified")

        self._check_meta_binding(snapshot["signed"]["meta"], "targets.json", targets)
        print("✓ Snapshot -> Targets binding verified")

        trusted_targets = self._verify_artifacts(targets["signed"]["targets"])
        print(f"✓ Trusted targets verified : {len(trusted_targets)}")
        self._store_trusted_state(root, timestamp, snapshot, targets, trusted_state)
        print("✓ Local trusted metadata state updated")
        print("=" * 60)

        return trusted_targets

    def _load_role(self, filename: str, require_signatures: bool = True):
        path = self.metadata_directory / filename
        if not path.exists():
            raise FileNotFoundError(f"Trust metadata missing: {path}")

        role = _load_json(path)
        if "signed" not in role:
            raise ValueError(f"Trust metadata missing signed section: {path}")
        if require_signatures and "signatures" not in role:
            raise ValueError(f"Trust metadata missing signatures: {path}")
        return role

    def _load_and_verify_role(self, filename: str, role_name: str, trusted_keys: dict, trusted_roles: dict):
        role = self._load_role(filename)
        self._validate_role(role["signed"], role_name)
        self._check_expiry(role["signed"], role_name)
        self._verify_signatures(role, role_name, trusted_keys, trusted_roles[role_name])
        print(f"✓ {role_name.capitalize()} metadata verified")
        return role

    @staticmethod
    def _validate_root(signed: dict):
        required_roles = {"root", "timestamp", "snapshot", "targets"}
        roles = signed.get("roles", {})
        keys = signed.get("keys", {})

        missing_roles = required_roles - set(roles.keys())
        if missing_roles:
            missing = ", ".join(sorted(missing_roles))
            raise RuntimeError(f"root metadata missing required roles: {missing}")

        for role_name in required_roles:
            role_rule = roles[role_name]
            threshold = int(role_rule.get("threshold", 0))
            keyids = role_rule.get("keyids", [])
            if threshold < 1:
                raise RuntimeError(f"{role_name} metadata threshold must be >= 1")
            if len(keyids) < threshold:
                raise RuntimeError(f"{role_name} metadata key threshold cannot be met")
            for keyid in keyids:
                if keyid not in keys:
                    raise RuntimeError(f"{role_name} metadata references unknown key {keyid}")

    @staticmethod
    def _validate_role(signed: dict, role_name: str):
        if signed.get("role") != role_name:
            raise RuntimeError(f"{role_name} metadata role name mismatch")
        if int(signed.get("version", 0)) < 1:
            raise RuntimeError(f"{role_name} metadata version must be >= 1")

    def _check_expiry(self, signed: dict, role_name: str):
        expires_at = _parse_timestamp(signed["expires"])
        if expires_at <= datetime.now(timezone.utc):
            raise RuntimeError(f"{role_name} metadata expired at {signed['expires']}")

    def _load_trusted_state(self) -> dict:
        if not self.state_path.exists():
            return {"roles": {}}
        return _load_json(self.state_path)

    @staticmethod
    def _check_rollback(signed: dict, role_name: str, trusted_state: dict):
        current_version = int(signed.get("version", 0))
        trusted_version = int(
            trusted_state.get("roles", {}).get(role_name, {}).get("version", 0)
        )
        if current_version < trusted_version:
            raise RuntimeError(
                f"{role_name} metadata rollback detected: "
                f"{current_version} < trusted {trusted_version}"
            )

    def _store_trusted_state(self, root: dict, timestamp: dict, snapshot: dict, targets: dict, trusted_state: dict):
        roles = trusted_state.setdefault("roles", {})
        for role_name, role in {
            "root": root,
            "timestamp": timestamp,
            "snapshot": snapshot,
            "targets": targets,
        }.items():
            signed = role["signed"]
            previous = roles.get(role_name, {})
            roles[role_name] = {
                "version": max(
                    int(previous.get("version", 0)),
                    int(signed["version"]),
                ),
                "expires": signed["expires"],
                "sha256": _sha256_bytes(_canonical_json_bytes(role)),
            }

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as fp:
            json.dump(trusted_state, fp, indent=2)
            fp.write("\n")

    def _verify_signatures(self, role: dict, role_name: str, trusted_keys: dict, role_rule: dict):
        signatures = role.get("signatures", [])
        if len(signatures) < role_rule["threshold"]:
            raise RuntimeError(
                f"{role_name} metadata has insufficient signatures: "
                f"{len(signatures)} < {role_rule['threshold']}"
            )

        signed_bytes = _canonical_json_bytes(role["signed"])
        valid_keyids = set()

        for signature in signatures:
            keyid = signature["keyid"]
            if keyid not in role_rule["keyids"]:
                continue

            key_entry = trusted_keys.get(keyid)
            if key_entry is None:
                continue
            if key_entry.get("algorithm") != "hmac-sha256":
                continue

            expected = hmac.new(
                bytes.fromhex(key_entry["key"]),
                signed_bytes,
                hashlib.sha256,
            ).hexdigest()

            if hmac.compare_digest(expected, signature["sig"]):
                valid_keyids.add(keyid)

        if len(valid_keyids) < role_rule["threshold"]:
            raise RuntimeError(f"{role_name} metadata signature verification failed")

    def _check_meta_binding(self, meta: dict, filename: str, role: dict):
        if filename not in meta:
            raise RuntimeError(f"Metadata binding missing {filename}")

        expected = meta[filename]
        payload = _canonical_json_bytes(role)

        if expected["version"] != role["signed"]["version"]:
            raise RuntimeError(f"{filename} version mismatch")
        if expected["length"] != len(payload):
            raise RuntimeError(f"{filename} length mismatch")
        if expected["hashes"]["sha256"] != _sha256_bytes(payload):
            raise RuntimeError(f"{filename} hash mismatch")

    def _verify_artifacts(self, targets: dict) -> dict[str, TrustedTarget]:
        trusted = {}

        for filename, entry in targets.items():
            artifact_path = self.release_directory / filename
            if not artifact_path.exists():
                raise FileNotFoundError(f"Trusted artifact missing: {artifact_path}")

            length = artifact_path.stat().st_size
            sha256 = _sha256_file(artifact_path)

            if entry["length"] != length:
                raise RuntimeError(f"{filename} trusted length mismatch")
            if entry["hashes"]["sha256"] != sha256:
                raise RuntimeError(f"{filename} trusted hash mismatch")
            self._validate_target_metadata(filename, entry)

            trusted[filename] = TrustedTarget(
                file=filename,
                length=length,
                sha256=sha256,
                custom=entry.get("custom", {}),
            )

        return trusted

    @staticmethod
    def _validate_target_metadata(filename: str, entry: dict):
        custom = entry.get("custom", {})
        required_custom = {
            "ecu_name",
            "hardware_variant",
            "target_version",
            "minimum_bootloader",
            "transport_support",
        }
        missing = required_custom - set(custom.keys())
        if missing:
            formatted = ", ".join(sorted(missing))
            raise RuntimeError(f"{filename} missing trusted custom metadata: {formatted}")

        transport_support = custom.get("transport_support")
        if not isinstance(transport_support, list) or not transport_support:
            raise RuntimeError(f"{filename} transport_support must be a non-empty list")
