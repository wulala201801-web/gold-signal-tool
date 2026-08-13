import threading
import time
import unittest
from unittest.mock import patch

import market_data


class FetchAllTests(unittest.TestCase):
    def test_fetches_market_inputs_in_parallel(self):
        barrier = threading.Barrier(6, timeout=1)

        def snapshot(value):
            barrier.wait()
            return {"value": value, "previous": value - 1, "timestamp": 1}

        def gold(symbol, days):
            barrier.wait()
            closes = list(range(1, 133))
            return {"value": closes[-1], "previous": closes[-2], "timestamp": 1}, closes

        def real_yield():
            barrier.wait()
            return {"value": 2.4, "previous": 2.5, "timestamp": 1}, "FRED"

        with patch.object(market_data, "yahoo_series", side_effect=gold), \
             patch.object(market_data, "yahoo", side_effect=lambda symbol: snapshot(100)), \
             patch.object(market_data, "real_yield", side_effect=real_yield):
            started = time.monotonic()
            result = market_data.fetch_all()

        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(len(result["data"]), 6)
        self.assertFalse(result["errors"])
        self.assertIn(result["scores"]["signal"], {"green", "yellow", "red"})


if __name__ == "__main__":
    unittest.main()
