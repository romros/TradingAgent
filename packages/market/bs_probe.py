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

ASSETS_TO_AUDIT = ["MSFT", "NVDA", "NDXUSD"]

# Símbols alternatius a provar (BS pot usar format diferent)
SYMBOL_VARIANTS = {
    "MSFT": ["MSFT", "MSFTUSD"],
    "NVDA": ["NVDA", "NVDAUSD"],
    "NDXUSD": ["NDXUSD", "NASDAQUSD", "QQQ", "QQQUSD"],
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


# ─── T8b: Proxy validation QQQ vs NASDAQUSD/NDXUSD ───────────────────────────

PROXY_MIN_SAMPLES = 30
PROXY_CORR_ALIGNED = 0.95
PROXY_CORR_WARNING = 0.90
PROXY_DELTA_ALIGNED_PCT = 1.0
PROXY_DELTA_WARNING_PCT = 3.0

# Símbols BS per índex Nasdaq-100 (Ostium: NDXUSD; alguns brokers: NASDAQUSD)
BS_NDX_SYMBOLS = ["NDXUSD", "NASDAQUSD"]


def _candles_to_by_date(candles: list) -> dict:
    """Converteix llista candles a dict date_str -> {close, ...}."""
    out = {}
    for c in candles:
        d = c.get("date")
        if isinstance(d, date):
            d = d.isoformat()
        if d and c.get("close") is not None:
            out[d] = c
    return out


def _align_returns_by_date(qqq_candles: list, bs_candles: list) -> tuple[list, list]:
    """
    Alinea candles per data (intersecció) i retorna parells (ret_qqq, ret_bs).
    ret_t = (close_t / close_t-1) - 1
    """
    qqq_by = _candles_to_by_date(qqq_candles)
    bs_by = _candles_to_by_date(bs_candles)
    common_dates = sorted(set(qqq_by.keys()) & set(bs_by.keys()))
    if len(common_dates) < 2:
        return [], []
    ret_qqq = []
    ret_bs = []
    for i in range(1, len(common_dates)):
        d_prev, d_curr = common_dates[i - 1], common_dates[i]
        c_prev_q = qqq_by[d_prev]["close"]
        c_curr_q = qqq_by[d_curr]["close"]
        c_prev_b = bs_by[d_prev]["close"]
        c_curr_b = bs_by[d_curr]["close"]
        if c_prev_q and c_curr_q and c_prev_b and c_curr_b and c_prev_q > 0 and c_prev_b > 0:
            ret_qqq.append((c_curr_q / c_prev_q) - 1.0)
            ret_bs.append((c_curr_b / c_prev_b) - 1.0)
    return ret_qqq, ret_bs


def _compute_proxy_metrics(ret_qqq: list, ret_bs: list) -> dict:
    """Calcula correlació Pearson i avg_delta_pct (mitjana |ret_qqq - ret_bs| * 100)."""
    if len(ret_qqq) < 2 or len(ret_qqq) != len(ret_bs):
        return {"correlation": None, "avg_delta_pct": None, "samples": len(ret_qqq)}
    try:
        import math
        n = len(ret_qqq)
        mean_q = sum(ret_qqq) / n
        mean_b = sum(ret_bs) / n
        var_q = sum((x - mean_q) ** 2 for x in ret_qqq) / n
        var_b = sum((x - mean_b) ** 2 for x in ret_bs) / n
        cov = sum((ret_qqq[i] - mean_q) * (ret_bs[i] - mean_b) for i in range(n)) / n
        if var_q > 0 and var_b > 0:
            corr = cov / math.sqrt(var_q * var_b)
        else:
            corr = None
        deltas = [abs(ret_qqq[i] - ret_bs[i]) * 100 for i in range(n)]
        avg_delta = sum(deltas) / n
        return {
            "correlation": round(corr, 4) if corr is not None else None,
            "avg_delta_pct": round(avg_delta, 4),
            "samples": n,
        }
    except (ZeroDivisionError, ValueError, IndexError):
        return {"correlation": None, "avg_delta_pct": None, "samples": len(ret_qqq)}


def _classify_proxy(metrics: dict) -> str:
    """
    Classificació: aligned | warning | diverged | insufficient_data.
    aligned: corr >= 0.95 AND delta < 1%
    warning: corr >= 0.90 AND delta < 3%
    insufficient_data: samples < 30
    """
    samples = metrics.get("samples", 0)
    if samples < PROXY_MIN_SAMPLES:
        return "insufficient_data"
    corr = metrics.get("correlation")
    delta = metrics.get("avg_delta_pct")
    if corr is None or delta is None:
        return "diverged"
    if corr >= PROXY_CORR_ALIGNED and delta < PROXY_DELTA_ALIGNED_PCT:
        return "aligned"
    if corr >= PROXY_CORR_WARNING and delta < PROXY_DELTA_WARNING_PCT:
        return "warning"
    return "diverged"


def run_proxy_validation(
    base_url: str = None,
    days: int = None,
    qqq_candles_override: list = None,
    bs_candles_override: list = None,
) -> dict:
    """
    T8b: Valida QQQ com a proxy de NASDAQUSD/NDXUSD.
    Fetch QQQ (yfinance) i NDX (BS 1m→D1), alinea returns, correlació, classificació.
    No throws; retorna status amb explicació.
    Overrides: per testing 0-network, passar qqq_candles_override/bs_candles_override.
    """
    base_url = base_url or BS_BASE_URL
    days = days or DATA_LOOKBACK_DAYS
    result = {
        "status": "insufficient_data",
        "correlation": None,
        "avg_delta_pct": None,
        "samples": 0,
        "proxy": "QQQ",
        "target": "NDXUSD",
        "base_url": base_url,
    }
    try:
        if qqq_candles_override is not None:
            qqq_candles = qqq_candles_override
        else:
            qqq_candles = _fetch_yf_d1("QQQ", days=days)
        if not qqq_candles:
            result["reason"] = "QQQ: no data from yfinance"
            logger.info("proxy_validation insufficient_data reason=qqq_empty")
            return result
        if bs_candles_override is not None:
            bs_candles_d1 = bs_candles_override
            result["target"] = "override"
        else:
            bs_candles_d1 = []
            for sym in BS_NDX_SYMBOLS:
                raw = _fetch_bs_ohlcv(base_url, sym, limit=5000)
                if raw and raw.get("candles"):
                    bs_candles_d1 = _aggregate_1m_to_d1(raw["candles"])
                    result["target"] = sym
                    break
        if not bs_candles_d1:
            result["reason"] = "BS: no NDXUSD/NASDAQUSD data"
            logger.info("proxy_validation insufficient_data reason=bs_empty")
            return result
        ret_qqq, ret_bs = _align_returns_by_date(qqq_candles, bs_candles_d1)
        metrics = _compute_proxy_metrics(ret_qqq, ret_bs)
        result["correlation"] = metrics["correlation"]
        result["avg_delta_pct"] = metrics["avg_delta_pct"]
        result["samples"] = metrics["samples"]
        result["status"] = _classify_proxy(metrics)
        logger.info(
            "proxy_validation correlation=%s delta=%s samples=%s status=%s",
            result["correlation"], result["avg_delta_pct"], result["samples"], result["status"],
        )
        return result
    except Exception as e:
        result["status"] = "error"
        result["reason"] = str(e)[:100]
        logger.warning("proxy_validation error: %s", e)
        return result
