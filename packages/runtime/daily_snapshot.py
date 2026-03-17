"""
T7d: Snapshot diari automàtic del probe.
Genera fitxer Markdown llegible a data/probe_snapshots/.
Reutilitza funcions canòniques; no duplica lògica.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR_DEFAULT = "data/probe_snapshots"


def _render_section(name: str, data: Any, error: Optional[str] = None) -> str:
    """Renderitza una secció del snapshot. Si error, retorna bloc error."""
    if error:
        return f"### {name}\n\n**error**: {error}\n\n"
    if data is None:
        return f"### {name}\n\n*(no data)*\n\n"
    if isinstance(data, dict):
        return f"### {name}\n\n```json\n{json.dumps(data, indent=2, default=str)}\n```\n\n"
    return f"### {name}\n\n{data}\n\n"


def render_snapshot_md(sections: dict[str, dict]) -> str:
    """
    Renderitza snapshot a Markdown.
    sections: {name: {status: ok|error, data: ..., message?: ...}}
    """
    lines = []
    now = datetime.now(timezone.utc)
    lines.append(f"# Probe Snapshot — {now.date().isoformat()}\n")
    lines.append(f"**Generated**: {now.isoformat()}\n")
    lines.append("---\n\n")

    for name, sec in sections.items():
        if sec.get("status") == "error":
            lines.append(_render_section(name, None, sec.get("message", "unknown")))
        else:
            lines.append(_render_section(name, sec.get("data")))

    return "".join(lines)


def _safe_get(
    fn,
    *args,
    default: Any = None,
    **kwargs,
) -> tuple[Any, Optional[str]]:
    """Executa fn, retorna (result, error_message)."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return default, str(e)[:200]


def build_daily_snapshot(
    db_path: str,
    output_dir: str = None,
    assets: list = None,
    base_url: str = None,
    days: int = 365,
    validation_result_override: dict = None,
    live_readiness_override: dict = None,
    data_quality_override: dict = None,
    trade_summary_override: dict = None,
    last_scan_override: dict = None,
    proxy_result_override: dict = None,
    bs_audit_override: dict = None,
) -> dict:
    """
    Genera snapshot diari. Reutilitza funcions canòniques.
    Overrides: per testing 0-network.
    Retorna {path, status: ok|warning|error, missing_sections: []}
    """
    from packages.portfolio.db import (
        init_db,
        get_trade_summary,
        get_last_scan_result,
    )
    from packages.portfolio.validation import run_validation, compute_live_readiness
    from packages.market.bs_probe import run_bs_audit, run_proxy_validation
    from packages.shared import config as shared_config

    output_dir = output_dir or getattr(shared_config, "PROBE_SNAPSHOTS_DIR", SNAPSHOTS_DIR_DEFAULT)
    assets = assets if assets is not None else list(getattr(shared_config, "ASSETS", ["MSFT", "NVDA", "QQQ"]))
    base_url = base_url or "http://localhost:8081"
    sections = {}
    missing = []

    # Trade summary + last scan
    if trade_summary_override is not None and last_scan_override is not None:
        trade_summary = trade_summary_override
        last_scan = last_scan_override
    else:
        try:
            conn = init_db(db_path)
            trade_summary = get_trade_summary(conn)
            last_scan = get_last_scan_result(conn)
            conn.close()
        except Exception as e:
            sections["trade_summary"] = {"status": "error", "message": str(e)[:200]}
            missing.append("trade_summary")
            trade_summary = {}
            last_scan = None

    if "trade_summary" not in sections:
        sections["trade_summary"] = {"status": "ok", "data": trade_summary}

    if last_scan is not None:
        sections["last_scan"] = {"status": "ok", "data": last_scan}
    else:
        sections["last_scan"] = {"status": "error", "message": "no scan"}
        missing.append("last_scan")

    # Validation
    if validation_result_override is not None:
        sections["validation"] = {"status": "ok", "data": validation_result_override}
    elif trade_summary and last_scan is not None:
        val, err = _safe_get(run_validation, trade_summary, last_scan)
        if err:
            sections["validation"] = {"status": "error", "message": err}
            missing.append("validation")
        else:
            sections["validation"] = {"status": "ok", "data": val}
    else:
        sections["validation"] = {"status": "error", "message": "no trade_summary/last_scan"}
        missing.append("validation")

    # Data quality (needs assets)
    if data_quality_override is not None:
        sections["data_quality"] = {"status": "ok", "data": data_quality_override}
    elif assets:
        from packages.market.data_quality import get_data_quality_result
        dq, err = _safe_get(lambda: get_data_quality_result(assets, days))
        if err:
            sections["data_quality"] = {"status": "error", "message": err}
            missing.append("data_quality")
        else:
            sections["data_quality"] = {"status": "ok", "data": dq}
    else:
        sections["data_quality"] = {"status": "error", "message": "no assets"}
        missing.append("data_quality")

    # Proxy validation
    if proxy_result_override is not None:
        sections["proxy_validation"] = {"status": "ok", "data": proxy_result_override}
    else:
        pr, err = _safe_get(lambda: run_proxy_validation(base_url=base_url, days=days))
        if err:
            sections["proxy_validation"] = {"status": "error", "message": err}
            missing.append("proxy_validation")
        else:
            sections["proxy_validation"] = {"status": "ok", "data": pr}

    # BS audit
    if bs_audit_override is not None:
        sections["bs_audit"] = {"status": "ok", "data": bs_audit_override}
    else:
        bs, err = _safe_get(lambda: run_bs_audit(assets=assets or ["MSFT"], base_url=base_url))
        if err:
            sections["bs_audit"] = {"status": "error", "message": err}
            missing.append("bs_audit")
        else:
            sections["bs_audit"] = {"status": "ok", "data": bs}

    # Live readiness
    if live_readiness_override is not None:
        sections["live_readiness"] = {"status": "ok", "data": live_readiness_override}
    else:
        val_res = sections.get("validation", {}).get("data")
        dq_res = sections.get("data_quality", {}).get("data")
        pr_res = sections.get("proxy_validation", {}).get("data")
        bs_res = sections.get("bs_audit", {}).get("data")
        if all(x for x in (val_res, dq_res, pr_res, bs_res)):
            lr = compute_live_readiness(val_res, pr_res, dq_res, bs_res)
            sections["live_readiness"] = {"status": "ok", "data": lr}
        else:
            sections["live_readiness"] = {"status": "error", "message": "missing inputs"}
            missing.append("live_readiness")

    # Render + write
    md = render_snapshot_md(sections)
    today = datetime.now(timezone.utc).date().isoformat()
    filename = f"{today}.md"
    out_path = Path(output_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    write_ok = True
    try:
        out_path.write_text(md, encoding="utf-8")
    except Exception as e:
        write_ok = False
        logger.warning("daily_snapshot write failed: %s", e)

    status = "ok" if write_ok and not missing else ("warning" if missing else "error")
    if not write_ok:
        status = "error"

    result = {
        "path": str(out_path),
        "status": status,
        "missing_sections": missing,
    }

    logger.info(
        "daily_snapshot_written path=%s status=%s missing=%s",
        result["path"], status, missing,
    )
    return result
