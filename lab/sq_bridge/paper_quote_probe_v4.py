#!/usr/bin/env python3
"""Fetch one BrokerageService quote and persist an inert Alquimia receipt."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.ostium_order_payload_v4 import revalidate_fresh_quote
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def fetch_latest_quote(*, base_url: str, symbol: str,
                       timeout_seconds: float = 5,
                       opener: Callable[..., Any] = urllib.request.urlopen) -> dict:
    """Perform exactly one unauthenticated GET; this module has no POST path."""
    root = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(root)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc \
            or parsed.username is not None or parsed.password is not None:
        raise ValueError("BrokerageService base URL invalid")
    query = urllib.parse.urlencode({"venue": "ostium", "symbol": symbol})
    request = urllib.request.Request(
        f"{root}/api/v1/broker/price/latest?{query}", method="GET",
        headers={"Accept": "application/json"})
    with opener(request, timeout=timeout_seconds) as response:
        if getattr(response, "status", 200) != 200:
            raise ValueError("BrokerageService quote HTTP no-200")
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError("BrokerageService quote no es un objecte")
    return value


def run_probe(*, template_path: Path, output_path: Path, base_url: str,
              observed_at: datetime | None = None,
              fetch_fn: Callable[..., dict] = fetch_latest_quote) -> dict:
    template = json.loads(template_path.resolve().read_text())
    if not isinstance(template, dict):
        raise ValueError("plantilla paper no es un objecte")
    body = template.get("request_body") or {}
    symbol = body.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("plantilla paper sense symbol")
    quote = fetch_fn(base_url=base_url, symbol=symbol)
    result = revalidate_fresh_quote(
        template=template, quote=quote,
        observed_at=observed_at or datetime.now(timezone.utc))
    receipt = {
        **result,
        "probe_type": "brokerage_service_read_only_quote",
        "http_method_used": "GET",
        "post_capability_present": False,
        "credentials_used": False,
        "request_sent": False,
        "signer_enabled": False,
        "live_authorized": False,
    }
    write_atomic(output_path.resolve(), receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    result = run_probe(
        template_path=args.template, output_path=args.output,
        base_url=args.base_url)
    print(json.dumps({key: result[key] for key in (
        "decision", "paper_request_ready", "request_sent")}, indent=2))


if __name__ == "__main__":
    main()
