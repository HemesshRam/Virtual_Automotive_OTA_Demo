import os
from datetime import datetime, timezone

import requests
from common.mqtt_config import DEFAULT_VEHICLE_ID
from tcu.http_tls import (
    requests_verify_setting,
    suppress_unverified_https_warning_if_needed,
)
from tcu.mqtt_client import TcuMQTTClient


AWS_JOB_STATE_BY_STATUS = {
    "DOWNLOADING": "IN_PROGRESS",
    "INSTALLING": "IN_PROGRESS",
    "VERIFYING": "IN_PROGRESS",
    "PENDING_COMMIT": "IN_PROGRESS",
    "SUCCESS": "SUCCEEDED",
    "FAILED": "FAILED",
    "ROLLBACK": "FAILED",
    "SKIPPED": "REJECTED",
}


class StatusReporter:

    def __init__(self):
        base_url = os.getenv("OTA_SERVER_URL", "https://127.0.0.1:8080").rstrip("/")
        self.url = os.getenv("OTA_STATUS_URL", f"{base_url}/status")
        self.tls_verify = requests_verify_setting()
        suppress_unverified_https_warning_if_needed()
        self.mqtt = TcuMQTTClient()
        self.job_id = None
        self.vehicle_id = DEFAULT_VEHICLE_ID

    def set_job_context(self, job_id=None, vehicle_id=None):
        self.job_id = job_id
        if vehicle_id:
            self.vehicle_id = vehicle_id

    def report(
        self,
        ecu,
        status,
        progress,
        version,
        campaign_id=None,
        error=None
    ):

        try:

            payload = {
                "ecu": ecu,
                "status": status,
                "progress": progress,
                "version": version,
                "vehicle_id": self.vehicle_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_status": AWS_JOB_STATE_BY_STATUS.get(status, "IN_PROGRESS"),
            }

            if self.job_id is not None:
                payload["job_id"] = self.job_id

            if campaign_id is not None:
                payload["campaign_id"] = campaign_id

            if error is not None:
                payload["error"] = error

            requests.post(
                self.url,
                json=payload,
                timeout=2,
                verify=self.tls_verify,
            )

            self.mqtt.publish_status(payload)

        except requests.exceptions.RequestException as e:

            print(f"[StatusReporter] Failed to report: {e}")
            self.mqtt.publish_status(payload)


reporter = StatusReporter()
