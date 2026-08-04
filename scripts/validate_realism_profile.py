#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from common.automotive_realism import load_realism_profile, profile_summary
from transport.can.isotp_adapter import IsoTpAdapter
from transport.uds import codec


def fail(message: str):
    print(f"[FAIL] {message}")
    return False


def ok(message: str):
    print(f"[OK] {message}")
    return True


def main():
    profile = load_realism_profile()
    checks = []

    checks.append(ok("Automotive realism profile loaded"))

    uds_services = {
        "0x10": codec.SID_DIAGNOSTIC_SESSION_CONTROL,
        "0x11": codec.SID_ECU_RESET,
        "0x22": codec.SID_READ_DATA_BY_IDENTIFIER,
        "0x27": codec.SID_SECURITY_ACCESS,
        "0x31": codec.SID_ROUTINE_CONTROL,
        "0x34": codec.SID_REQUEST_DOWNLOAD,
        "0x36": codec.SID_TRANSFER_DATA,
        "0x37": codec.SID_REQUEST_TRANSFER_EXIT,
        "0x3E": codec.SID_TESTER_PRESENT,
    }
    configured_services = profile["uds"]["supported_services"]
    checks.append(
        ok("UDS service profile matches codec constants")
        if set(configured_services.keys()) == set(uds_services.keys())
        else fail("UDS service profile does not match codec constants")
    )

    nrcs = profile["uds"]["simulated_nrc_matrix"]
    checks.append(
        ok("UDS NRC matrix includes programming and security failures")
        if {"0x33", "0x35", "0x36", "0x72", "0x73", "0x78"}.issubset(nrcs.keys())
        else fail("UDS NRC matrix missing required programming/security failures")
    )

    isotp = profile["isotp"]["timing_and_flow_control"]
    checks.append(
        ok("ISO-TP timing profile matches adapter")
        if (
            isotp["single_frame_payload"] == IsoTpAdapter.SF_MAX_PAYLOAD
            and isotp["flow_control_timeout_seconds"] == IsoTpAdapter.FLOW_CONTROL_TIMEOUT
            and isotp["max_wait_frames"] == IsoTpAdapter.MAX_WAIT_FRAMES
        )
        else fail("ISO-TP timing profile does not match adapter")
    )

    checks.append(
        ok("Flash profile includes A/B and journal recovery")
        if profile["flash"]["ab_slots"] and "ROLLED_BACK" in profile["flash"]["journal_states"]
        else fail("Flash profile missing A/B or rollback journal state")
    )

    checks.append(
        ok("Ethernet profile includes DoIP UDP discovery and TCP diagnostics")
        if (
            profile["ethernet"]["vehicle_identification"] == "UDP/13400"
            and profile["ethernet"]["diagnostics"] == "TCP/13400"
        )
        else fail("Ethernet profile missing expected DoIP ports")
    )

    print()
    for line in profile_summary(profile):
        print(line)

    if not all(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
