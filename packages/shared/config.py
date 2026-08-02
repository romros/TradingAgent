import os

from packages.portfolio.risk_policy import parse_risk_glidepath

ASSETS = os.getenv("PROBE_ASSETS", "MSFT,NVDA").split(",")
LEVERAGE = int(os.getenv("LEVERAGE", "5"))


def _parse_asset_leverage(raw: str) -> dict[str, int]:
    result = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        asset, value = item.split(":", 1)
        leverage = int(value)
        if leverage < 1:
            raise ValueError(f"leverage must be positive for {asset}")
        result[asset.strip().upper()] = leverage
    return result


# Caps provisionals de paper, derivats de pitjor MAE històrica amb buffer 25%.
# LEVERAGE continua sent el fallback per actius no especificats.
LEVERAGE_BY_ASSET = _parse_asset_leverage(
    os.getenv("LEVERAGE_BY_ASSET", "MSFT:10,NVDA:5,NDXUSD:5")
)
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.01"))
RISK_GLIDEPATH = parse_risk_glidepath(os.getenv(
    "RISK_GLIDEPATH", "400:0.015,1000:0.0125,2500:0.01,5000:0.0075,inf:0.005"
))
STOP_DISTANCE_BY_ASSET = {
    asset: float(value)
    for asset, value in (
        item.split(":", 1) for item in os.getenv(
            "STOP_DISTANCE_BY_ASSET", "MSFT:0.0476,NVDA:0.0700,NDXUSD:0.0522"
        ).split(",") if item.strip()
    )
}
CAPITAL_INITIAL = float(os.getenv("CAPITAL_INITIAL", "250.0"))
COL_PCT = float(os.getenv("COL_PCT", "0.20"))
COL_MAX = float(os.getenv("COL_MAX", "60.0"))
COL_MIN = float(os.getenv("COL_MIN", "15.0"))
FEE_RAW = os.getenv("FEE", "").strip()
FEE = float(FEE_RAW) if FEE_RAW else None
PAPER_COST_BPS = float(os.getenv("PAPER_COST_BPS", "8.0"))
PAPER_COST_CONSERVATIVE_BPS = float(os.getenv("PAPER_COST_CONSERVATIVE_BPS", "15.0"))
PAPER_COST_STRESS_BPS = float(os.getenv("PAPER_COST_STRESS_BPS", "30.0"))
BODY_THRESH = float(os.getenv("BODY_THRESH", "-0.02"))
BB_PERIOD = int(os.getenv("BB_PERIOD", "20"))
BB_STD = float(os.getenv("BB_STD", "2.0"))
DB_PATH = os.getenv("DB_PATH", "data/paper_probe.db")
DATA_LOOKBACK_DAYS = int(os.getenv("DATA_LOOKBACK_DAYS", "365"))
BS_BASE_URL = os.getenv("BS_BASE_URL", "http://localhost:8081")
PROBE_SNAPSHOTS_DIR = os.getenv("PROBE_SNAPSHOTS_DIR", "data/probe_snapshots")
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() in ("1", "true", "yes")
SCHEDULER_HOUR_UTC = int(os.getenv("SCHEDULER_HOUR_UTC", "21"))
