import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.Webtester import analyze  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
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
        except Exception as error:
            self._send_json(500, {"error": str(error)})
            return

        self._send_json(200, result)

    def do_GET(self):
        self._send_json(405, {"error": "Method not allowed"})
