import os


DEMO_SECURITY_XOR_KEY = bytes.fromhex("A55A3CC3")


def derive_demo_security_key(seed: bytes) -> bytes:
    if not seed:
        return b""

    repeated_key = (
        DEMO_SECURITY_XOR_KEY
        * ((len(seed) + len(DEMO_SECURITY_XOR_KEY) - 1) // len(DEMO_SECURITY_XOR_KEY))
    )[: len(seed)]
    return bytes(a ^ b for a, b in zip(seed, repeated_key))


def derive_security_key(seed: bytes) -> bytes:
    mode = os.getenv("OTA_SECURITY_MODE", "demo_xor").strip().lower()

    if mode == "static":
        raw = os.getenv("OTA_SECURITY_STATIC_KEY_HEX", "").strip()
        if not raw:
            raise RuntimeError(
                "OTA_SECURITY_STATIC_KEY_HEX must be set when OTA_SECURITY_MODE=static"
            )
        key = bytes.fromhex(raw)
        if not key:
            raise RuntimeError("OTA_SECURITY_STATIC_KEY_HEX must not be empty")
        return (key * ((len(seed) + len(key) - 1) // len(key)))[: len(seed)]

    return derive_demo_security_key(seed)
