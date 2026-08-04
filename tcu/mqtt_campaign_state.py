import json
from datetime import datetime, timezone
from pathlib import Path


STATE_PATH = Path("tcu/state/mqtt_jobs.json")


class DuplicateMQTTJob(RuntimeError):
    pass


class MQTTJobState:

    def __init__(self, path: str | Path = STATE_PATH):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {"jobs": {}}
        with open(self.path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def save(self, state: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2)
            fp.write("\n")

    def ensure_not_completed(self, job_id: str):
        state = self.load()
        job = state.get("jobs", {}).get(job_id)
        if job and job.get("status") == "COMPLETED":
            raise DuplicateMQTTJob(f"MQTT job already completed: {job_id}")

    def record(self, job_id: str, campaign_id: str, status: str):
        state = self.load()
        jobs = state.setdefault("jobs", {})
        jobs[job_id] = {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save(state)
