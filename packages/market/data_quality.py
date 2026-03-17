"""
Qualitat del data feed per asset. Reutilitzat per /data-quality i daily_snapshot.
"""
from packages.market.data_feed import YFinanceD1Feed, validate_candles


def get_data_quality_result(assets: list[str], days: int = 365) -> dict:
    """
    Retorna resultat data_quality per cada asset.
    Reutilitzat per /data-quality i daily_snapshot.
    """
    feed = YFinanceD1Feed()
    result = {"source": "yfinance", "assets": {}}
    for asset in assets:
        try:
            candles = feed.fetch(asset, days=days)
            validation = validate_candles(candles)
            result["assets"][asset] = {
                "status": validation["status"],
                "candles_count": len(candles),
                "warnings": validation["warnings"],
                "errors": validation["errors"],
            }
        except Exception as e:
            result["assets"][asset] = {
                "status": "error",
                "candles_count": 0,
                "warnings": [],
                "errors": [str(e)[:100]],
            }
    return result
