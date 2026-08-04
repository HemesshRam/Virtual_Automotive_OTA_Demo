import json
import os
from pathlib import Path

import requests
from common.progress_bar import ProgressBar
from tcu.http_tls import (
    requests_verify_setting,
    suppress_unverified_https_warning_if_needed,
)
from tcu.mqtt_campaign_state import DuplicateMQTTJob, MQTTJobState
from tcu.mqtt_client import TcuMQTTClient


class OTACloudClient:

    def __init__(self):

        self.base_url = os.getenv("OTA_SERVER_URL", "https://127.0.0.1:8080").rstrip("/")
        self.tls_verify = requests_verify_setting()
        suppress_unverified_https_warning_if_needed()
        self.campaign_url_override = os.getenv("OTA_CAMPAIGN_URL", "").strip()

        self.local_campaign = Path("campaigns/campaign_v1.json")

        self.local_firmware = Path("firmware/releases/2.0.0")
        self.mqtt = TcuMQTTClient()
        self.job_state = MQTTJobState()
        self.current_job = None

    # ---------------------------------------------------------

    def download_campaign(self):
        if self.campaign_url_override:
            return self.download_campaign_from_url(self.campaign_url_override)
        return self.download_campaign_from_url(
            f"{self.base_url}/campaign/latest"
        )

    # ---------------------------------------------------------

    def download_campaign_from_url(self, url):
        if url.startswith("file://"):
            return self.download_campaign_from_file(Path(url.removeprefix("file://")))
        path = Path(url)
        if path.exists():
            return self.download_campaign_from_file(path)

        print()
        print("=" * 60)
        print("CONNECTING TO OTA CLOUD")
        print("=" * 60)

        response = requests.get(
            url,
            timeout=5,
            verify=self.tls_verify,
        )

        response.raise_for_status()

        campaign = response.json()

        self.local_campaign.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(self.local_campaign, "w") as f:

            json.dump(
                campaign,
                f,
                indent=4
            )

        print("Campaign downloaded successfully")

        return campaign

    def download_campaign_from_file(self, path: Path):

        print()
        print("=" * 60)
        print("LOADING CAMPAIGN FROM LOCAL PAYLOAD")
        print("=" * 60)

        with open(path, "r", encoding="utf-8") as fp:
            campaign = json.load(fp)

        self.local_campaign.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(self.local_campaign, "w", encoding="utf-8") as f:
            json.dump(
                campaign,
                f,
                indent=4
            )

        print(f"Campaign loaded from {path}")

        return campaign

    # ---------------------------------------------------------

    def download_campaign_from_mqtt(self, timeout=60):

        print()
        print("=" * 60)
        print("WAITING FOR MQTT CAMPAIGN")
        print("=" * 60)

        if not self.mqtt.available:
            raise RuntimeError("paho-mqtt is not installed")

        payload = self.mqtt.wait_for_campaign(timeout=timeout)

        job_id = payload.get("job_id", payload.get("campaign_id", "UNKNOWN"))
        campaign_id = payload.get("campaign_id", "UNKNOWN")
        self.job_state.ensure_not_completed(job_id)
        self.job_state.record(job_id, campaign_id, "RECEIVED")
        self.current_job = payload

        print(f"Campaign notification received : {campaign_id}")
        print(f"MQTT Job ID                    : {job_id}")

        document = payload.get("document", {})
        download_url = document.get("campaign_url") or payload.get("download_url")

        if not download_url:
            raise RuntimeError("MQTT campaign payload missing download_url")

        self.job_state.record(job_id, campaign_id, "PROCESSING")
        return self.download_campaign_from_url(download_url)

    def mark_current_job(self, status: str):
        if not self.current_job:
            return
        self.job_state.record(
            self.current_job.get("job_id", self.current_job.get("campaign_id", "UNKNOWN")),
            self.current_job.get("campaign_id", "UNKNOWN"),
            status,
        )

    # ---------------------------------------------------------

    def download_firmware(self, campaign, target_names=None):

        print()
        print("=" * 60)
        print("DOWNLOADING FIRMWARE")
        print("=" * 60)

        self.local_firmware.mkdir(
            parents=True,
            exist_ok=True
        )

        selected_names = {
            name for name in (target_names or []) if str(name).strip()
        }
        targets = []
        for target in campaign["targets"]:
            ecu_name = str(target.get("ecu_name", "")).strip()
            if selected_names and ecu_name not in selected_names:
                continue
            targets.append(target)

        if not targets:
            print("No firmware artifacts need to be downloaded for this run")
            return

        for target in targets:

            filename = target["firmware_file"]

            print(f"Downloading {filename}")

            url = f"{self.base_url}/firmware/{filename}"
            response = requests.get(
                url,
                timeout=10,
                verify=self.tls_verify,
                stream=True,
            )

            response.raise_for_status()
            total_bytes = int(response.headers.get("content-length") or 0)
            downloaded = 0
            destination = self.local_firmware / filename
            temp_destination = destination.with_name(f"{filename}.downloading")

            if temp_destination.exists():
                temp_destination.unlink()

            try:
                with open(temp_destination, "wb") as f:

                    for chunk in response.iter_content(chunk_size=1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes:
                            ProgressBar.update(downloaded, total_bytes)
                        else:
                            print(f"\rDownloaded {downloaded} bytes", end="", flush=True)
            except Exception:
                if temp_destination.exists():
                    temp_destination.unlink()
                raise

            if not total_bytes:
                print()

            temp_destination.replace(destination)

            actual_size = destination.stat().st_size
            expected_text = f"/{total_bytes}" if total_bytes else ""
            print(f"OK - {actual_size}{expected_text} bytes received")

        print()
        print("All firmware downloaded successfully")
