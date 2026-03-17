# Probe Snapshot — 2026-03-17
**Generated**: 2026-03-17T22:59:51.558042+00:00
---

### trade_summary

```json
{
  "open_count": 0,
  "settled_count": 0,
  "wins": 0,
  "losses": 0,
  "pnl_total": 0.0,
  "avg_pnl_per_trade": null,
  "last_trade": null
}
```

### last_scan

```json
{
  "run_utc": "2026-03-17T22:59:50.835597+00:00",
  "status": "ok",
  "assets": {
    "MSFT": {
      "status": "ok",
      "signal": false,
      "candles": 364,
      "reason": null
    },
    "NVDA": {
      "status": "ok",
      "signal": false,
      "candles": 364,
      "reason": null
    },
    "NDXUSD": {
      "status": "ok",
      "signal": false,
      "candles": 364,
      "reason": null
    }
  },
  "new_signals": [],
  "settled_count": 0,
  "pending_count": 0,
  "errors": []
}
```

### validation

```json
{
  "probe_ok": true,
  "paper_metrics": {
    "trades_total": 0,
    "wins": 0,
    "losses": 0,
    "winrate_pct": null,
    "winrate_confidence": "low",
    "pnl_total": 0.0,
    "avg_pnl_per_trade": null
  },
  "validation": {
    "status": "aligned",
    "delta_wr_pct": null,
    "delta_ev": null,
    "baseline": {
      "winrate_pct": 78.0,
      "avg_pnl_per_trade": 12.7
    },
    "paper": {
      "winrate_pct": null,
      "avg_pnl_per_trade": null
    }
  }
}
```

### data_quality

```json
{
  "source": "yfinance",
  "assets": {
    "MSFT": {
      "status": "ok",
      "candles_count": 364,
      "warnings": [],
      "errors": []
    },
    "NVDA": {
      "status": "ok",
      "candles_count": 364,
      "warnings": [],
      "errors": []
    },
    "NDXUSD": {
      "status": "ok",
      "candles_count": 364,
      "warnings": [],
      "errors": []
    }
  }
}
```

### proxy_validation

```json
{
  "status": "insufficient_data",
  "correlation": null,
  "avg_delta_pct": null,
  "samples": 0,
  "proxy": "QQQ",
  "target": "NDXUSD",
  "base_url": "http://localhost:8081",
  "reason": "BS: no NDXUSD/NASDAQUSD data"
}
```

### bs_audit

```json
{
  "source": "brokerage_service",
  "base_url": "http://localhost:8081",
  "assets": [
    {
      "asset": "MSFT",
      "available": false,
      "data_quality": "error",
      "comparison": "unknown",
      "candles_count": 0,
      "delta_pct": null,
      "warnings": [],
      "errors": [
        "BS no retorna candles D1"
      ]
    },
    {
      "asset": "NVDA",
      "available": false,
      "data_quality": "error",
      "comparison": "unknown",
      "candles_count": 0,
      "delta_pct": null,
      "warnings": [],
      "errors": [
        "BS no retorna candles D1"
      ]
    },
    {
      "asset": "NDXUSD",
      "available": false,
      "data_quality": "error",
      "comparison": "unknown",
      "candles_count": 0,
      "delta_pct": null,
      "warnings": [],
      "errors": [
        "BS no retorna candles D1"
      ]
    }
  ]
}
```

### live_readiness

```json
{
  "status": "LIVE_NOT_READY",
  "reasons": [
    "low_sample_size",
    "winrate_confidence_low",
    "proxy_not_ready",
    "bs_not_ready",
    "bs_data_quality_error"
  ],
  "metrics": {
    "trades": 0,
    "winrate": null,
    "ev": null
  }
}
```

