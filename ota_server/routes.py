from flask import Blueprint
from flask import jsonify
from flask import request
from flask import send_file
from flask import abort
import json

from common.mqtt_config import OTA_ADMIN_TOKEN
from ota_server.repository import OTARepository
from ota_server.status_repository import repository
from ota_server.job_repository import job_repository
from ota_server.mqtt_publisher import OTAMQTTPublisher

ota = Blueprint("ota", __name__)


@ota.get("/campaign/latest")
def campaign():

    with open(OTARepository.campaign()) as f:

        return jsonify(json.load(f))


@ota.get("/firmware/<filename>")
def firmware(filename):

    path = OTARepository.firmware(filename)

    print(f"Serving firmware : {path}")

    return send_file(
        str(path.resolve()),
        as_attachment=True
    )


@ota.route("/status", methods=["POST"])
def update_status():

    payload = request.json

    if not isinstance(payload, dict) or "ecu" not in payload:
        abort(400, description="Invalid status payload")

    repository.update(
        payload["ecu"],
        payload
    )

    job_id = payload.get("job_id")
    job_status = payload.get("job_status")
    if job_id and job_status:
        job_repository.update_status(job_id, job_status, payload)

    return {
        "result": "OK"
    }


@ota.route("/status", methods=["GET"])
def get_status():

    return repository.get_all()


@ota.route("/jobs", methods=["GET"])
def get_jobs():

    return job_repository.get_all()


@ota.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):

    job = job_repository.get(job_id)
    if job is None:
        abort(404, description="Job not found")

    return job


@ota.route("/jobs/<job_id>/status", methods=["POST"])
def update_job_status(job_id):

    payload = request.json
    if not isinstance(payload, dict) or "job_status" not in payload:
        abort(400, description="Invalid job status payload")

    return job_repository.update_status(
        job_id,
        payload["job_status"],
        payload,
    )


@ota.route("/campaign/publish", methods=["POST"])
def publish_campaign():
    if OTA_ADMIN_TOKEN:
        bearer = request.headers.get("Authorization", "")
        header_token = request.headers.get("X-OTA-Admin-Token", "")
        if bearer.startswith("Bearer "):
            header_token = bearer.removeprefix("Bearer ").strip()
        if header_token != OTA_ADMIN_TOKEN:
            abort(401, description="Invalid OTA admin token")

    with open(OTARepository.campaign(), "r", encoding="utf-8") as f:
        campaign = json.load(f)

    publisher = OTAMQTTPublisher()

    if not publisher.available:
        abort(503, description="paho-mqtt is not installed")

    base_url = request.host_url.rstrip("/")
    payload = publisher.publish_campaign_available(campaign, base_url)

    return {
        "result": "OK",
        "topic": publisher.topics.jobs_notify,
        "payload": payload,
    }
