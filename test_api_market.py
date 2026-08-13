import io
import unittest
from unittest.mock import patch

from api.market import handler


class ApiHandlerTests(unittest.TestCase):
    def response_for(self, result):
        instance = object.__new__(handler)
        instance.wfile = io.BytesIO()
        instance.send_response = lambda status: setattr(instance, "status", status)
        instance.send_header = lambda key, value: setattr(instance, key.lower().replace("-", "_"), value)
        instance.end_headers = lambda: None
        with patch("api.market.fetch_all", return_value=result):
            instance.do_GET()
        return instance

    def test_incomplete_score_returns_503_and_is_not_cached(self):
        response = self.response_for({"scores": {"ok": False}})
        self.assertEqual(response.status, 503)
        self.assertEqual(response.cache_control, "no-store")

    def test_complete_score_returns_200_with_stale_error_fallback(self):
        response = self.response_for({"scores": {"combinedRisk": 46}})
        self.assertEqual(response.status, 200)
        self.assertIn("stale-if-error=86400", response.cache_control)


if __name__ == "__main__":
    unittest.main()
