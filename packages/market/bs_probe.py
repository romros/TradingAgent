"""
Auditoria de BrokerageService per suport equities D1 (T8a pre-live).
Consulta BS, valida dades, compara amb yfinance.
"""
import json
import logging
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, date, timezone, timedelta
from typing import Optional

from packages.shared.config import BS_BASE_URL, DATA_LOOKBACK_DAYS
from packages.market.data_feed import YFinanceD1Feed, validate_candles

logger = logging.getLogger(__name__)

ASSETS_TO_AUDIT = ["MSFT", "NVDA", "QQQ"]

# Símbols alternatius a provar (BS pot usar format diferent)
SYMBOL_VARIANTS = {
    "MSFT": ["MSFT", "MSFTUSD"],
    "NVDA": ["NVDA", "NVDAUSD"],
    "QQQ": ["QQQ", "QQQUSD"],
}

# Marges per classificació comparació BS vs yfinance
DELTA_ALIGNED_PCT = 0.5
DELTA_WARNING_PCT = 2.0


def _fetch_bs_ohlcv(base_url: str, symbol: str, limit: int = 5000) -> Optional[dict]:
    """
    GET /data/ohlcv/{symbol}?tf=1m&limit=...
    BS retorna {candles: [[ts,o,h,l,c,v], ...], ...}
    """
    url = f"{base_url.rstrip('/')}/data/ohlcv/{symbol}?tf=1m&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TradingAgent-BS-Audit/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data
    except urllib.error.HTTPError as e:
        logger.warning("bs_fetch HTTP %s %s", e.code, url)
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("bs_fetch error %s: %s", url, e)
        return None


def _aggregate_1m_to_d1(candles_array: list) -> list:
    """
    Agrega candles 1m [[ts,o,h,l,c,v], ...] a D1.
    Retorna [{date, open, high, low, close}, ...] ordenat cronològicament.
    """
    if not candles_array:
        return []
    by_date = defaultdict(list)
    for row in candles_array:
        if len(row) < 5:
            continue
        ts, o, h, l, c = row[0], row[1], row[2], row[3], row[4]
        try:
            if ts > 1e12:  # milliseconds
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            d = dt.date()
            by_date[d].append({"date": d, "open": float(o), "high": float(h), "low": float(l), "close": float(c)})
        except (ValueError, TypeError, IndexError):
            continue
    result = []
    for d in sorted(by_date.keys()):
        bars = by_date[d]
        if not bars:
            continue
        result.append({
            "date": d.isoformat(),
            "open": bars[0]["open"],
            "high": max(b["high"] for b in bars),
            "low": min(b["low"] for b in bars),
            "close": bars[-1]["close"],
        })
    return result


def _fetch_yf_d1(asset: str, days: int = 365) -> list:
    """Candles D1 des de yfinance."""
    feed = YFinanceD1Feed()
    return feed.fetch(asset, days=days)


def _compare_closes(bs_candles: list, yf_candles: list) -> dict:
    """
    Compara close dels candles overlapping per data.
    Retorna {delta_pct: float, comparison: aligned|warning|diverged, overlapping: int}
    """
    yf_by_date = {c["date"]: c for c in yf_candles}
    deltas = []
    for c in bs_candles:
        d = c.get("date")
        if isinstance(d, date):
            d = d.isoformat()
        yf_c = yf_by_date.get(d)
        if yf_c and yf_c.get("close") and yf_c["close"] > 0:
            bs_close = c.get("close")
            if bs_close is not None:
                delta_pct = abs(bs_close - yf_c["close"]) / yf_c["close"] * 100
                deltas.append(delta_pct)
    if not deltas:
        return {"delta_pct": None, "comparison": "no_overlap", "overlapping": 0}
    avg_delta = sum(deltas) / len(deltas)
    if avg_delta < DELTA_ALIGNED_PCT:
        comp = "aligned"
    elif avg_delta < DELTA_WARNING_PCT:
        comp = "warning"
    else:
        comp = "diverged"
    return {"delta_pct": round(avg_delta, 4), "comparison": comp, "overlapping": len(deltas)}


def audit_asset(asset: str, base_url: str) -> dict:
    """
    Audita un asset: disponibilitat BS, qualitat dades, comparació vs yfinance.
    """
    result = {
        "asset": asset,
        "available": False,
        "data_quality": "error",
        "comparison": "unknown",
        "candles_count": 0,
        "delta_pct": None,
        "warnings": [],
        "errors": [],
    }
    symbols_to_try = SYMBOL_VARIANTS.get(asset, [asset])
    bs_candles_d1 = []
    bs_raw = None
    for sym in symbols_to_try:
        bs_raw = _fetch_bs_ohlcv(base_url, sym, limit=5000)
        if bs_raw and bs_raw.get("candles"):
            bs_candles_d1 = _aggregate_1m_to_d1(bs_raw["candles"])
            if len(bs_candles_d1) >= 200:
                result["available"] = True
                break
            elif len(bs_candles_d1) > 0:
                result["available"] = True
                result["warnings"].append(f"candles_count={len(bs_candles_d1)} < 200")
                break
        if bs_raw is not None and not bs_raw.get("candles"):
            result["errors"].append(f"BS retorna empty per {sym}")
    if not bs_candles_d1:
        result["errors"].append("BS no retorna candles D1")
        logger.info("bs_audit asset=%s available=false", asset)
        return result
    result["candles_count"] = len(bs_candles_d1)
    validation = validate_candles(bs_candles_d1)
    result["data_quality"] = validation["status"]
    result["warnings"].extend(validation["warnings"])
    result["errors"].extend(validation["errors"])
    yf_candles = _fetch_yf_d1(asset, days=DATA_LOOKBACK_DAYS)
    if yf_candles:
        comp = _compare_closes(bs_candles_d1, yf_candles)
        result["comparison"] = comp["comparison"]
        result["delta_pct"] = comp["delta_pct"]
    logger.info(
        "bs_audit asset=%s available=%s quality=%s delta=%s status=%s",
        asset, result["available"], result["data_quality"],
        result["delta_pct"], result["comparison"],
    )
    return result


def run_bs_audit(assets: list = None, base_url: str = None) -> dict:
    """
    Executa auditoria completa de BrokerageService.
    Retorna {source: "brokerage_service", assets: [{asset, available, ...}, ...]}
    """
    assets = assets or ASSETS_TO_AUDIT
    base_url = base_url or BS_BASE_URL
    results = []
    for asset in assets:
        try:
            r = audit_asset(asset, base_url)
            results.append(r)
        except Exception as e:
            results.append({
                "asset": asset,
                "available": False,
                "data_quality": "error",
                "comparison": "error",
                "candles_count": 0,
                "delta_pct": None,
                "warnings": [],
                "errors": [str(e)[:100]],
            })
            logger.warning("bs_audit asset=%s exception: %s", asset, e)
    return {"source": "brokerage_service", "base_url": base_url, "assets": results}
