import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "gold-signal-tool/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_yahoo_chart(data):
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes = [value for value in quote.get("close", []) if value is not None]
    if not closes:
        raise ValueError("no close data")
    timestamps = result.get("timestamp", [])
    snapshot = {
        "value": closes[-1],
        "previous": closes[-2] if len(closes) > 1 else None,
        "timestamp": timestamps[-1] if timestamps else int(time.time()),
        "currency": meta.get("currency"),
    }
    return snapshot, closes


def yahoo_series(symbol, days=7):
    end = int(time.time())
    period_query = urllib.parse.urlencode({
        "period1": end - days * 86400,
        "period2": end,
        "interval": "1d",
        "events": "history",
    })
    range_query = urllib.parse.urlencode({
        "range": "6mo" if days >= 60 else "7d",
        "interval": "1d",
        "events": "history",
    })
    encoded_symbol = urllib.parse.quote(symbol)
    minimum = 60 if days >= 60 else 2
    errors = []
    for host, query in (
        ("query1.finance.yahoo.com", period_query),
        ("query2.finance.yahoo.com", range_query),
        ("query1.finance.yahoo.com", range_query),
    ):
        try:
            parsed = parse_yahoo_chart(get_json(
                f"https://{host}/v8/finance/chart/{encoded_symbol}?{query}"
            ))
            if len(parsed[1]) >= minimum:
                return parsed
            errors.append(f"{host}: only {len(parsed[1])} closes")
        except Exception as error:
            errors.append(f"{host}: {error}")
    raise ValueError("; ".join(errors))


def yahoo(symbol):
    return yahoo_series(symbol)[0]


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def macro_score(data):
    required = ("dxy", "real_yield", "usdjpy", "nasdaq", "vix")
    if any(not data.get(k, {}).get("ok") or data[k].get("previous") is None for k in required):
        raise ValueError("macro data incomplete")
    directional, reasons = 50, []
    change = lambda key: data[key]["value"] - data[key]["previous"]
    if change("dxy") < 0:
        directional += 10; reasons.append("美元走弱，宏观风险 -10")
    else:
        directional -= 10; reasons.append("美元走强，宏观风险 +10")
    if change("real_yield") < 0:
        directional += 15; reasons.append("实际收益率回落，宏观风险 -15")
    else:
        directional -= 10; reasons.append("实际收益率未回落，宏观风险 +10")
    if data["usdjpy"]["value"] < 160 and change("usdjpy") < 0:
        directional += 15; reasons.append("美元兑日圆回落，宏观风险 -15")
    elif data["usdjpy"]["value"] >= 160:
        directional -= 15; reasons.append("美元兑日圆突破 160，宏观风险 +15")
    deleverage = change("usdjpy") < 0 and change("nasdaq") < 0 and change("vix") > 0
    if deleverage:
        directional -= 20; reasons.append("日圆升值、纳指下跌且 VIX 上升，去杠杆风险 +20")
    risk = round(100 - clamp(directional))
    return max(risk, 80) if deleverage else risk, reasons, deleverage


def price_heat(closes):
    if len(closes) < 60:
        raise ValueError("fewer than 60 gold trading days")
    current, previous = closes[-1], closes[-2]
    percentile = 100 * sum(value <= current for value in closes) / len(closes)
    ma20_deviation = 100 * (current / (sum(closes[-20:]) / 20) - 1)
    return20 = 100 * (current / closes[-21] - 1)
    daily_return = 100 * (current / previous - 1)
    components = {
        "percentile": round(percentile, 1), "ma20Deviation": round(ma20_deviation, 2),
        "return20": round(return20, 2), "dailyReturn": round(daily_return, 2),
        "percentileScore": round(clamp(percentile), 1),
        "ma20DeviationScore": round(clamp(ma20_deviation / 8 * 100), 1),
        "return20Score": round(clamp(return20 / 15 * 100), 1),
        "dailyReturnScore": round(clamp(daily_return / 3 * 100), 1),
    }
    risk = round(components["percentileScore"]*.4 + components["ma20DeviationScore"]*.3 + components["return20Score"]*.2 + components["dailyReturnScore"]*.1)
    return risk, components


def combined_score(data, gold_closes):
    macro_risk, reasons, deleverage = macro_score(data)
    heat_risk, heat = price_heat(gold_closes)
    combined, guards = round(macro_risk*.4 + heat_risk*.6), []
    if heat_risk >= 60 and combined < 40:
        combined = 40; guards.append("价格追高风险达到 60，综合灯号最低为黄灯")
    if macro_risk >= 80 and combined < 71:
        combined = 71; guards.append("宏观风险达到 80，综合灯号强制为红灯")
    signal = "red" if combined >= 71 else "yellow" if combined >= 40 else "green"
    if signal == "green":
        conclusion = "综合风险较低：可按计划小额分批，不加杠杆"
        actions = ["按原计划持有，可小额分批", "分批买入，不一次重仓", "顺势观察，严格设置止损"]
    elif macro_risk < 40 and heat_risk >= 60:
        conclusion = "宏观偏有利，但金价处于阶段高位：持有，不追高"
        actions = ["继续持有，不因高位清空核心仓位", "等待回落后分批，不追高", "减少频繁交易，控制仓位"]
    elif signal == "yellow":
        conclusion = "综合风险中等：方向或价格位置未确认，持有或等待"
        actions = ["继续持有，不追涨", "等待回落或信号转绿再分批", "减少频繁交易，控制仓位"]
    else:
        conclusion = "综合风险较高：暂停追高，优先降低杠杆"
        actions = ["优先减仓或降低杠杆", "暂停买入与追高", "停止逆势交易，等待风险回落"]
    return {"macroRisk": macro_risk, "priceHeatRisk": heat_risk, "combinedRisk": combined, "signal": signal, "macroReasons": reasons, "priceHeat": heat, "guards": guards, "deleverage": deleverage, "conclusion": conclusion, "actions": actions}


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


def treasury_real_yield():
    month = time.strftime("%Y%m", time.gmtime())
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        f"?data=daily_treasury_real_yield_curve&field_tdr_date_value_month={month}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "gold-signal-tool/1.0"})
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read().decode("utf-8")
    rows = re.findall(
        r"<d:NEW_DATE[^>]*>([^<]+)</d:NEW_DATE>[\s\S]*?"
        r"<d:TC_10YEAR[^>]*>([^<]+)</d:TC_10YEAR>",
        body,
    )
    if not rows:
        raise ValueError("no Treasury real-yield data")
    date, value = rows[-1]
    previous = float(rows[-2][1]) if len(rows) > 1 else None
    return {
        "value": float(value),
        "previous": previous,
        "date": date[:10],
        "timestamp": int(time.time()),
    }


def real_yield():
    try:
        return fred("DFII10"), "FRED"
    except Exception:
        return treasury_real_yield(), "U.S. Treasury"


def fetch_all():
    specs = {
        "gold": ("黄金期货", lambda: yahoo_series("GC=F", 190), "Yahoo Finance"),
        "dxy": ("美元指数", lambda: yahoo("DX-Y.NYB"), "Yahoo Finance"),
        "usdjpy": ("美元兑日圆", lambda: yahoo("JPY=X"), "Yahoo Finance"),
        "nasdaq": ("纳斯达克", lambda: yahoo("^IXIC"), "Yahoo Finance"),
        "vix": ("VIX", lambda: yahoo("^VIX"), "Yahoo Finance"),
        "real_yield": ("美国10年实际收益率", real_yield, "FRED"),
    }
    result = {"fetchedAt": int(time.time()), "data": {}, "errors": {}}
    fetched = {}
    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        futures = {executor.submit(fetch): key for key, (_, fetch, _) in specs.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                fetched[key] = (future.result(), None)
            except Exception as error:
                fetched[key] = (None, error)

    gold_closes = None
    for key, (label, _, source) in specs.items():
        value, error = fetched[key]
        if error is not None:
            result["errors"][key] = str(error)
            result["data"][key] = {"label": label, "source": source, "ok": False}
            continue
        try:
            if key == "real_yield":
                value, source = value
            elif key == "gold":
                value, gold_closes = value
            value.update({"label": label, "source": source, "ok": True})
            result["data"][key] = value
        except Exception as error:
            result["errors"][key] = str(error)
            result["data"][key] = {"label": label, "source": source, "ok": False}
    try:
        result["scores"] = combined_score(result["data"], gold_closes or [])
    except Exception as error:
        result["errors"]["scores"] = str(error)
        result["scores"] = {"ok": False, "error": str(error)}
    return result
