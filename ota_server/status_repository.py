from threading import Lock
from copy import deepcopy
from datetime import datetime, timezone


class StatusRepository:

    def __init__(self):
        self.lock = Lock()
        self.data = {}

    def update(self, ecu, status):

        with self.lock:
            record = deepcopy(status)
            record["ecu"] = ecu
            record["timestamp"] = datetime.now(timezone.utc).isoformat()

            current = self.data.get(ecu, {"latest": None, "history": []})
            current["latest"] = record
            current["history"].append(record)
            self.data[ecu] = current

    def get_all(self):

        with self.lock:
            return deepcopy(self.data)


repository = StatusRepository()
