#!/usr/bin/env python3
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from market_data import fetch_all

ROOT = Path(__file__).parent

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/market":
            try:
                payload = json.dumps(fetch_all(), ensure_ascii=False).encode()
                status = 200
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
                status = 502
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        target = ROOT / ("index.html" if self.path in ("/", "") else self.path.lstrip("/"))
        if target.is_file() and ROOT in target.resolve().parents:
            self.send_response(200)
            content_type, _ = mimetypes.guess_type(target.name)
            if target.name == "manifest.webmanifest":
                content_type = "application/manifest+json"
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.end_headers()
            self.wfile.write(target.read_bytes())
        else:
            self.send_error(404)

if __name__ == "__main__":
    print("Gold Signal Tool: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
