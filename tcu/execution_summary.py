from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExecutionSummary:
    status: str
    transport: str
    cloud_control: str
    campaign_id: str = ""
    artifact_name: str = ""
    software_name: str = ""
    software_version: str = ""
    reason: str = ""
    discovered_ecus: list[str] = field(default_factory=list)
    eligible_ecus: list[str] = field(default_factory=list)
    update_order: list[str] = field(default_factory=list)
    platform_definition: str = ""
    runtime_mapping: str = ""
    scenario_name: str = ""
    per_ecu_results: list[dict[str, str]] = field(default_factory=list)


class ExecutionSummaryWriter:
    def __init__(self, path: str | None = None):
        configured = path or os.getenv("OTA_EXECUTION_SUMMARY_PATH", "").strip()
        self.path = Path(configured) if configured else None

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def write(self, summary: ExecutionSummary) -> None:
        if not self.path:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "status": summary.status,
            "transport": summary.transport,
            "cloud_control": summary.cloud_control,
            "campaign_id": summary.campaign_id,
            "artifact_name": summary.artifact_name,
            "software_name": summary.software_name,
            "software_version": summary.software_version,
            "reason": summary.reason,
            "discovered_ecus": summary.discovered_ecus,
            "eligible_ecus": summary.eligible_ecus,
            "update_order": summary.update_order,
            "platform_definition": summary.platform_definition,
            "runtime_mapping": summary.runtime_mapping,
            "scenario_name": summary.scenario_name,
            "per_ecu_results": summary.per_ecu_results,
        }
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
            fp.write("\n")
