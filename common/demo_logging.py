import os


def quiet_enabled() -> bool:
    return os.getenv("OTA_DEMO_QUIET", "0").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def verbose_enabled() -> bool:
    return not quiet_enabled()


def demo_log(message: str) -> None:
    if verbose_enabled():
        print(message)
