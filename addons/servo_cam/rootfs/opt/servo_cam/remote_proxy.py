#!/usr/bin/env python3
"""Reverse proxy for Servo Cam backend running on a remote host."""

import logging
import os
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from flask import Flask, Response, jsonify, request, stream_with_context

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("servo_cam.remote_proxy")

REMOTE_HOST = os.environ.get("REMOTE_HOST")
REMOTE_PORT = os.environ.get("REMOTE_PORT", "5000")
REMOTE_SCHEME = os.environ.get("REMOTE_SCHEME", "http")
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
REMOTE_TIMEOUT = float(os.environ.get("REMOTE_TIMEOUT", "10"))

if not REMOTE_HOST:
    LOGGER.error("REMOTE_HOST environment variable is required in remote mode.")
    raise SystemExit(1)

REMOTE_BASE = f"{REMOTE_SCHEME}://{REMOTE_HOST}:{REMOTE_PORT}"
LOGGER.info("Servo Cam remote proxy forwarding to %s", REMOTE_BASE)

app = Flask(__name__)


def _remote_url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return urljoin(REMOTE_BASE, path)


def _filter_headers(headers: dict) -> dict:
    """Remove hop-by-hop headers that should not be forwarded."""
    hop_headers = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
    return {k: v for k, v in headers.items() if k.lower() not in hop_headers}


def _forward_request(path: str, *, stream: bool = False) -> Response:
    url = _remote_url(path)
    headers = _filter_headers(dict(request.headers))

    data: Optional[bytes] = None
    json_payload = None

    if request.method in ("POST", "PUT", "PATCH"):
        if request.is_json:
            json_payload = request.get_json(silent=True)
        else:
            data = request.get_data()

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            headers=headers,
            data=data,
            json=json_payload,
            timeout=None if stream else REMOTE_TIMEOUT,
            stream=stream,
        )
    except requests.RequestException as exc:
        LOGGER.warning("Remote request failed: %s", exc)
        return jsonify({"status": "unavailable", "error": str(exc)}), 503

    filtered_headers = _filter_headers(resp.headers)

    if stream:
        def generate() -> Iterable[bytes]:
            try:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                resp.close()

        return Response(
            stream_with_context(generate()),
            status=resp.status_code,
            headers=filtered_headers,
            content_type=resp.headers.get("Content-Type"),
        )

    response = Response(
        resp.content,
        status=resp.status_code,
        headers=filtered_headers,
        content_type=resp.headers.get("Content-Type"),
    )
    resp.close()
    return response


@app.route("/healthz", methods=["GET"])
def healthz() -> Response:
    try:
        resp = requests.get(_remote_url("/healthz"), timeout=REMOTE_TIMEOUT)
        filtered_headers = _filter_headers(resp.headers)
        payload = resp.content
        status = resp.status_code
        resp.close()
        return Response(payload, status=status, headers=filtered_headers, content_type="application/json")
    except requests.RequestException as exc:
        LOGGER.warning("Remote health check failed: %s", exc)
        return jsonify({"status": "unavailable", "error": str(exc)}), 503


@app.route("/video_feed", methods=["GET"])
def video_feed() -> Response:
    return _forward_request("/video_feed", stream=True)


@app.route("/snapshot", methods=["GET"])
def snapshot() -> Response:
    return _forward_request("/snapshot")


@app.route("/status", methods=["GET"])
def status() -> Response:
    return _forward_request("/status")


@app.route("/config", methods=["GET", "POST"])
def config() -> Response:
    return _forward_request("/config")


@app.route("/monitoring/start", methods=["POST"])
@app.route("/monitoring/stop", methods=["POST"])
@app.route("/monitoring/toggle", methods=["POST"])
def monitoring_control() -> Response:
    return _forward_request(request.path)


@app.route("/servo/move", methods=["POST"])
@app.route("/servo/center", methods=["POST"])
def servo_control() -> Response:
    return _forward_request(request.path)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def catch_all(path: str) -> Response:
    """Forward any other request (UI assets, etc.) to the remote backend."""
    # video_feed handled separately
    full_path = f"/{path}" if not path.startswith("/") else path
    return _forward_request(full_path, stream=False)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True)
