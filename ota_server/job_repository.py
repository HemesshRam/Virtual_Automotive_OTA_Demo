import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


JOB_STATE_PATH = Path("ota_server/state/jobs.json")


class JobRepository:

    def __init__(self, path: str | Path = JOB_STATE_PATH):
        self.path = Path(path)
        self.lock = Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"jobs": {}}
        with open(self.path, "r", encoding="utf-8") as fp:
            return json.load(fp)

    def _save(self, state: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2)
            fp.write("\n")

    def create_job(self, payload: dict):
        with self.lock:
            state = self._load()
            jobs = state.setdefault("jobs", {})
            job_id = payload["job_id"]
            now = datetime.now(timezone.utc).isoformat()
            current = jobs.get(job_id, {})
            history = current.get("history", [])
            record = {
                "job_id": job_id,
                "vehicle_id": payload["vehicle_id"],
                "campaign_id": payload["campaign_id"],
                "status": "QUEUED",
                "created_at": payload.get("created_at", now),
                "updated_at": now,
                "document": payload.get("document", {}),
                "history": history + [
                    {
                        "status": "QUEUED",
                        "timestamp": now,
                        "source": "backend_scheduler",
                    }
                ],
            }
            jobs[job_id] = record
            self._save(state)
            return deepcopy(record)

    def update_status(self, job_id: str, status: str, payload: dict):
        with self.lock:
            state = self._load()
            jobs = state.setdefault("jobs", {})
            now = datetime.now(timezone.utc).isoformat()
            current = jobs.get(job_id, {
                "job_id": job_id,
                "status": "UNKNOWN",
                "history": [],
            })
            current["status"] = status
            current["updated_at"] = now
            if "vehicle_id" in payload:
                current["vehicle_id"] = payload["vehicle_id"]
            if "campaign_id" in payload:
                current["campaign_id"] = payload["campaign_id"]
            current.setdefault("history", []).append({
                "status": status,
                "timestamp": now,
                "source": "tcu",
                "payload": payload,
            })
            jobs[job_id] = current
            self._save(state)
            return deepcopy(current)

    def get_all(self):
        with self.lock:
            return deepcopy(self._load().get("jobs", {}))

    def get(self, job_id: str):
        with self.lock:
            return deepcopy(self._load().get("jobs", {}).get(job_id))


job_repository = JobRepository()
