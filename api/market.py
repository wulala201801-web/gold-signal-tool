import json
from http.server import BaseHTTPRequestHandler

from market_data import fetch_all


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            result = fetch_all()
            score_ok = result.get("scores", {}).get("combinedRisk") is not None
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
            status = 200
        except Exception as error:
            payload = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            status = 502
            score_ok = False
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Cache-Control",
            "public, s-maxage=300, stale-while-revalidate=600" if score_ok else "no-store",
        )
        self.end_headers()
        self.wfile.write(payload)
