import json
from http.server import BaseHTTPRequestHandler

from market_data import fetch_all


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(fetch_all(), ensure_ascii=False).encode("utf-8")
            status = 200
        except Exception as error:
            payload = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            status = 502
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, s-maxage=300, stale-while-revalidate=600")
        self.end_headers()
        self.wfile.write(payload)
