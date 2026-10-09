import json
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.Webtester import analyze  # noqa: E402

MAX_REQUEST_BYTES = 4096
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_RATE_LIMIT_CLIENTS = 10_000
_rate_limit_lock = threading.Lock()
_requests_by_client = {}


def check_rate_limit(client_id, now=None):
    current_time = time.monotonic() if now is None else now
    cutoff = current_time - RATE_LIMIT_WINDOW_SECONDS

    with _rate_limit_lock:
        requests = _requests_by_client.get(client_id)
        if requests is None:
            if len(_requests_by_client) >= MAX_RATE_LIMIT_CLIENTS:
                _requests_by_client.pop(next(iter(_requests_by_client)))
            requests = deque()
            _requests_by_client[client_id] = requests

        while requests and requests[0] <= cutoff:
            requests.popleft()

        if len(requests) >= RATE_LIMIT_REQUESTS:
            retry_after = max(1, int(requests[0] + RATE_LIMIT_WINDOW_SECONDS - current_time) + 1)
            return retry_after

        requests.append(current_time)
        return None


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload, extra_headers=None):
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(response)

    def do_POST(self):
        client_id = (
            self.headers.get("x-vercel-forwarded-for")
            or self.headers.get("x-forwarded-for")
            or self.client_address[0]
        )
        retry_after = check_rate_limit(client_id)
        if retry_after is not None:
            self._send_json(
                429,
                {"error": "Rate limit exceeded. Try again shortly."},
                {"Retry-After": str(retry_after)},
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length"})
            return

        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request body is too large"})
            return

        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        url = payload.get("url", "").strip() if isinstance(payload, dict) else ""
        if not url:
            self._send_json(400, {"error": "A website URL is required"})
            return

        try:
            result = analyze(url)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        except Exception:
            self._send_json(502, {"error": "Unable to analyze the requested URL"})
            return

        self._send_json(200, result)

    def do_GET(self):
        self._send_json(405, {"error": "Method not allowed"})
