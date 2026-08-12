import json
import time
import urllib.parse
import urllib.request


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "gold-signal-tool/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def yahoo(symbol):
    end = int(time.time())
    query = urllib.parse.urlencode({
        "period1": end - 7 * 86400,
        "period2": end,
        "interval": "1d",
        "events": "history",
    })
    encoded_symbol = urllib.parse.quote(symbol)
    data = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query}")
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes = [value for value in quote.get("close", []) if value is not None]
    if not closes:
        raise ValueError("no close data")
    timestamps = result.get("timestamp", [])
    return {
        "value": closes[-1],
        "previous": closes[-2] if len(closes) > 1 else None,
        "timestamp": timestamps[-1] if timestamps else int(time.time()),
        "currency": meta.get("currency"),
    }


def fred(series):
    # Limit the CSV window so serverless requests do not download the full
    # multi-decade series and time out before the page can calculate a signal.
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 120 * 86400))
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}"
    request = urllib.request.Request(url, headers={"User-Agent": "gold-signal-tool/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        rows = response.read().decode("utf-8").strip().splitlines()[1:]
    values = []
    for row in rows:
        if "," not in row:
            continue
        date, value = row.split(",", 1)
        if value not in (".", ""):
            values.append((date, value))
    if not values:
        raise ValueError("no FRED data")
    date, value = values[-1]
    previous = float(values[-2][1]) if len(values) > 1 else None
    return {
        "value": float(value),
        "previous": previous,
        "date": date,
        "timestamp": int(time.time()),
    }


def fetch_all():
    specs = {
        "gold": ("黄金期货", lambda: yahoo("GC=F"), "Yahoo Finance"),
        "dxy": ("美元指数", lambda: yahoo("DX-Y.NYB"), "Yahoo Finance"),
        "usdjpy": ("美元兑日圆", lambda: yahoo("JPY=X"), "Yahoo Finance"),
        "nasdaq": ("纳斯达克", lambda: yahoo("^IXIC"), "Yahoo Finance"),
        "vix": ("VIX", lambda: yahoo("^VIX"), "Yahoo Finance"),
        "real_yield": ("美国10年实际收益率", lambda: fred("DFII10"), "FRED"),
    }
    result = {"fetchedAt": int(time.time()), "data": {}, "errors": {}}
    for key, (label, fetch, source) in specs.items():
        try:
            value = fetch()
            value.update({"label": label, "source": source, "ok": True})
            result["data"][key] = value
        except Exception as error:
            result["errors"][key] = str(error)
            result["data"][key] = {"label": label, "source": source, "ok": False}
    return result
