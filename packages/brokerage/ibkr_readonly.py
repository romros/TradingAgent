"""Fail-closed read-only subset of the IBKR Client Portal Web API.

This module deliberately exposes no generic request method and no order endpoint.
It is intended only to qualify and inspect an instrument in an authenticated
local Client Portal Gateway session.
"""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class IbkrContractCandidate:
    conid: int
    symbol: str
    description: str
    sections: tuple[dict, ...]


class IbkrReadonlyClient:
    _ALLOWED_PATHS = frozenset({
        "/v1/api/iserver/auth/status",
        "/v1/api/iserver/secdef/search",
        "/v1/api/iserver/secdef/info",
    })

    def __init__(self, base_url: str = "https://localhost:5000",
                 timeout: float = 10.0, verify_tls: bool = False,
                 transport: Callable | None = None):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("IBKR gateway must be local HTTPS")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_tls = verify_tls
        self._transport = transport or self._get

    def _get(self, path: str, params: dict | None = None):
        if path not in self._ALLOWED_PATHS:
            raise ValueError("endpoint is not read-only allowlisted")
        query = urllib.parse.urlencode(params or {})
        url = self.base_url + path + ("?" + query if query else "")
        context = None if self.verify_tls else ssl._create_unverified_context()
        req = urllib.request.Request(url, method="GET", headers={"User-Agent":"TradingAgent-IBKR-Readonly/1"})
        with urllib.request.urlopen(req, timeout=self.timeout, context=context) as response:
            return json.loads(response.read().decode())

    def auth_status(self) -> dict:
        value = self._transport("/v1/api/iserver/auth/status", None)
        return {"authenticated": bool(value.get("authenticated")),
                "connected": bool(value.get("connected")),
                "competing": bool(value.get("competing"))}

    def search(self, symbol: str, name: bool = False) -> tuple[IbkrContractCandidate, ...]:
        if not symbol or len(symbol) > 32:
            raise ValueError("invalid symbol")
        rows = self._transport("/v1/api/iserver/secdef/search", {"symbol":symbol,"name":str(name).lower()})
        return tuple(IbkrContractCandidate(int(row["conid"]), row.get("symbol", ""),
                     row.get("companyName") or row.get("companyHeader", ""),
                     tuple(row.get("sections") or ())) for row in rows)

    def contract_info(self, conid: int, sec_type: str = "STK") -> list[dict]:
        if conid <= 0 or sec_type not in {"STK", "ETF"}:
            raise ValueError("invalid contract query")
        value = self._transport("/v1/api/iserver/secdef/info", {"conid":conid,"sectype":sec_type})
        return value if isinstance(value, list) else [value]

