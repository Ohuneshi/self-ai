from __future__ import annotations

import json
import os
import threading
import uuid
from http import cookies
from pathlib import Path
from urllib.parse import unquote

import brain

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def user_id_from_environ(environ):
    jar = cookies.SimpleCookie()
    jar.load(environ.get("HTTP_COOKIE", ""))
    value = jar.get("self_ai_user")
    if value and value.value and len(value.value) <= 80:
        return value.value, False
    return uuid.uuid4().hex, True


def start_job(message: str, user_id: str) -> str:
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "status": "running", "stage_index": 0, "stage_name": "자동처리",
            "message": "입력에서 즉각적인 신호와 감정적 경향을 추출하고 있습니다.",
            "result": None, "error": None,
        }

    def progress(index, name, detail):
        with jobs_lock:
            if job_id in jobs:
                jobs[job_id].update(stage_index=index, stage_name=name, message=detail)

    def run():
        try:
            result = brain.process_interaction(message, progress=progress, user_id=user_id)
            with jobs_lock:
                jobs[job_id].update(status="done", result=result)
        except Exception as exc:
            with jobs_lock:
                jobs[job_id].update(status="error", error=f"{type(exc).__name__}: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return job_id


def json_response(start_response, status, body, set_cookie=None):
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(raw))),
    ]
    if set_cookie:
        headers.append(("Set-Cookie", set_cookie))
    start_response(status, headers)
    return [raw]


def text_response(start_response, status, text, content_type="text/plain; charset=utf-8"):
    raw = text.encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(raw))), ("Cache-Control", "no-store")])
    return [raw]


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = unquote(environ.get("PATH_INFO", "/"))
    user_id, new_cookie = user_id_from_environ(environ)
    cookie = None
    if new_cookie:
        jar = cookies.SimpleCookie()
        jar["self_ai_user"] = user_id
        jar["self_ai_user"]["max-age"] = 31536000
        jar["self_ai_user"]["httponly"] = True
        jar["self_ai_user"]["samesite"] = "Lax"
        cookie = jar.output(header="").strip()

    if method == "GET" and path == "/":
        raw = (WEB_DIR / "index.html").read_bytes()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(raw)))])
        return [raw]

    if method == "GET" and path.startswith("/static/"):
        rel = path[len("/static/"):]
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            return text_response(start_response, "404 Not Found", "Not Found")
        content_types = {".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8"}
        raw = target.read_bytes()
        start_response("200 OK", [("Content-Type", content_types.get(target.suffix, "application/octet-stream")), ("Content-Length", str(len(raw)))])
        return [raw]

    if method == "GET" and path == "/api/state":
        data = brain.load_state(user_id)
        body = brain.compact_state(data)
        body["internal_state"] = data["internal_state"]
        body["self_model"] = data["self_model"]
        body["goals"] = data["goals"]
        body["recent_episodes"] = data["episodic"][-12:]
        return json_response(start_response, "200 OK", body, cookie)

    if method == "POST" and path == "/api/chat":
        length = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ["wsgi.input"].read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return json_response(start_response, "400 Bad Request", {"error": "invalid JSON"}, cookie)
        message = str(payload.get("message", "")).strip()
        if not message:
            return json_response(start_response, "400 Bad Request", {"error": "message is required"}, cookie)
        return json_response(start_response, "200 OK", {"job_id": start_job(message, user_id)}, cookie)

    if method == "GET" and path.startswith("/api/status/"):
        job_id = path.rsplit("/", 1)[-1]
        with jobs_lock:
            data = jobs.get(job_id)
        if not data:
            return json_response(start_response, "404 Not Found", {"error": "job not found"})
        return json_response(start_response, "200 OK", data)

    return text_response(start_response, "404 Not Found", "Not Found")


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    brain.init_files()
    host = os.getenv("SELF_AI_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    with make_server(host, port, application) as server:
        print(f"Self AI running at http://{host}:{port}")
        server.serve_forever()
