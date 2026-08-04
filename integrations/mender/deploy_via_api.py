#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib import error, parse, request


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _authorization_header(token: str) -> str:
    value = token.strip()
    if value.lower().startswith("bearer "):
        return value
    return f"Bearer {value}"


def _read_response_body(exc: error.HTTPError) -> str:
    try:
        payload = exc.read().decode("utf-8", errors="replace")
    except Exception:
        payload = ""
    return payload


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----virtual-ota-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for key, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )

    return b"".join(chunks), boundary


def upload_artifact(base_url: str, token: str, artifact_path: Path, description: str = "") -> dict:
    body, boundary = _multipart_body(
        {
            "description": description,
            "size": str(artifact_path.stat().st_size),
        },
        "artifact",
        artifact_path,
    )
    url = f"{base_url.rstrip('/')}/api/management/v1/deployments/artifacts"
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": _authorization_header(token),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req) as resp:
            payload = resp.read().decode("utf-8", errors="replace").strip()
            return {
                "status": resp.status,
                "location": resp.headers.get("Location", ""),
                "body": payload,
            }
    except error.HTTPError as exc:
        payload = _read_response_body(exc)
        if exc.code == 409:
            return {
                "status": exc.code,
                "location": exc.headers.get("Location", ""),
                "body": payload,
            }
        raise RuntimeError(
            f"Artifact upload failed with HTTP {exc.code}: {payload or exc.reason}"
        ) from exc


def create_group_deployment(
    base_url: str,
    token: str,
    artifact_name: str,
    group_name: str,
    deployment_name: str,
    *,
    retries: int = 1,
) -> dict:
    encoded_group = parse.quote(group_name, safe="")
    url = f"{base_url.rstrip('/')}/api/management/v1/deployments/deployments/group/{encoded_group}"
    payload = json.dumps(
        {
            "name": deployment_name,
            "artifact_name": artifact_name,
            "retries": retries,
        }
    ).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": _authorization_header(token),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req) as resp:
            return {
                "status": resp.status,
                "location": resp.headers.get("Location", ""),
                "body": resp.read().decode("utf-8", errors="replace").strip(),
            }
    except error.HTTPError as exc:
        payload_text = _read_response_body(exc)
        raise RuntimeError(
            f"Deployment creation failed with HTTP {exc.code}: {payload_text or exc.reason}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload a Mender artifact and create a deployment via the Mender Management API")
    parser.add_argument("--artifact-file", required=True, help="Path to the .mender artifact")
    parser.add_argument("--artifact-name", required=True, help="Artifact name to deploy")
    parser.add_argument("--deployment-name", required=True, help="Human-readable deployment name")
    parser.add_argument("--group-name", default=os.getenv("MENDER_DEVICE_GROUP", ""), help="Static group name or single-device group name")
    parser.add_argument("--base-url", default=os.getenv("MENDER_BASE_URL", "https://hosted.mender.io"))
    parser.add_argument("--token", default=os.getenv("MENDER_API_TOKEN", ""))
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--description", default="Virtual OTA dynamic deployment artifact")
    args = parser.parse_args(argv)

    artifact_path = Path(args.artifact_file).expanduser().resolve()
    if not artifact_path.exists():
        raise SystemExit(f"Artifact file not found: {artifact_path}")
    if not args.token.strip():
        raise SystemExit("MENDER_API_TOKEN is required")
    if not args.group_name.strip():
        raise SystemExit("MENDER_DEVICE_GROUP is required")

    if not args.skip_upload:
        upload_result = upload_artifact(args.base_url, args.token, artifact_path, args.description)
        print(f"Artifact upload status : {upload_result['status']}")
        if upload_result["location"]:
            print(f"Artifact location      : {upload_result['location']}")
        if upload_result["status"] == 409:
            print("Artifact already exists on the Mender server; reusing it.")

    deployment_result = create_group_deployment(
        args.base_url,
        args.token,
        args.artifact_name,
        args.group_name,
        args.deployment_name,
        retries=args.retries,
    )
    print(f"Deployment create HTTP : {deployment_result['status']}")
    if deployment_result["location"]:
        print(f"Deployment location    : {deployment_result['location']}")
    if deployment_result["body"]:
        print(f"Deployment response    : {deployment_result['body']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
