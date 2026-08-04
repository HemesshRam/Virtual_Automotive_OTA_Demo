import json
from pathlib import Path


PROFILE_PATH = Path("docs/automotive_realism_profile.json")


def load_realism_profile(path: str | Path = PROFILE_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def profile_summary(profile: dict) -> list[str]:
    return [
        f"AUTOSAR simulated modules: {', '.join(profile['autosar']['simulated_modules'])}",
        f"UDS services modeled: {len(profile['uds']['supported_services'])}",
        f"UDS NRCs modeled: {len(profile['uds']['simulated_nrc_matrix'])}",
        f"ISO-TP addressing modes simulated: {', '.join(profile['isotp']['addressing_modes_simulated'])}",
        f"Uptane roles represented: {', '.join(profile['uptane']['simulated_roles'])}",
        f"Flash model: {profile['flash']['memory_type']}",
        f"Ethernet model: {profile['ethernet']['simulated_network']}",
    ]
