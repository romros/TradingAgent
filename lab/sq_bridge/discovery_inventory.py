#!/usr/bin/env python3
"""Inventaria un databank SQX congelat sense executar StrategyQuant."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


REQUIRED_MEMBERS = {"settings.xml", "strategy_Portfolio.xml", "version.txt"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(value: str | None, cast=float):
    if value is None:
        return None
    return cast(value)


def _tree(item: ET.Element) -> dict:
    """Representació estructural: conserva operadors, elimina valors ajustables."""
    children = []
    for block in item.findall("Block"):
        child = block.find("Item")
        if child is not None:
            children.append(_tree(child))
    children.extend(_tree(child) for child in item.findall("Item"))
    result = {"op": item.get("key", "")}
    if children:
        result["children"] = children
    return result


def _signal_structures(strategy: ET.Element) -> list[dict]:
    structures = []
    for rule in strategy.findall(".//Rule[@type='Signal']"):
        for signal in rule.findall("./signals/signal"):
            item = signal.find("Item")
            if item is not None:
                structures.append(_tree(item))
    return structures


def _blocks(strategy: ET.Element) -> tuple[list[str], list[dict]]:
    ops, indicators = [], []
    for item in strategy.findall(".//Rule[@type='Signal']//Item"):
        if item.get("generated") not in {"random", None}:
            continue
        op = item.get("key", "")
        if op:
            ops.append(op)
        category = item.get("categoryType", "")
        if category in {"indicator", "priceRange", "priceValue"}:
            periods = []
            for param in item.findall("Param"):
                if param.get("key") == "#Period#" and (param.text or "").strip():
                    periods.append(int(float(param.text)))
            indicators.append({"op": op, "category": category, "periods": periods})
    return sorted(set(ops)), indicators


def _entry_indicator_types(strategy: ET.Element, fallback: list[dict]) -> list[tuple[str, str]]:
    signals = {node.get("variable"): node for node in strategy.findall(".//Rule[@type='Signal']/signals/signal")}
    selected = []
    for name in ("Long entry", "Short entry"):
        rule = strategy.find(f".//Rule[@name='{name}']")
        variable = rule.find(".//Param[@key='#Variable#']") if rule is not None else None
        signal = signals.get((variable.text or "").strip()) if variable is not None else None
        if signal is not None:
            selected.extend(signal.findall(".//Item"))
    types = {(item.get("key", ""), item.get("categoryType", "")) for item in selected
             if item.get("categoryType") in {"indicator", "priceRange", "priceValue"}}
    if not types:
        types = {(row["op"], row["category"]) for row in fallback}
    return sorted(types)


def inspect_sqx(path: Path) -> dict:
    raw = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
        missing = sorted(REQUIRED_MEMBERS - members)
        if missing:
            raise ValueError(f"{path.name}: membres absents: {missing}")
        settings_raw = archive.read("settings.xml")
        strategy_raw = archive.read("strategy_Portfolio.xml")
        version = archive.read("version.txt").decode("utf-8", errors="replace").strip()
    settings = ET.fromstring(settings_raw)
    strategy = ET.fromstring(strategy_raw)
    fingerprint = settings.find(".//Fingerprint[@strategyName]")
    if fingerprint is None:
        raise ValueError(f"{path.name}: fingerprint absent")
    complexity_node = settings.find(".//Complexity")
    structures = _signal_structures(strategy)
    structure_json = json.dumps(structures, sort_keys=True, separators=(",", ":"))
    ops, indicators = _blocks(strategy)
    archetype = {
        "ops": ops,
        "indicator_types": sorted({(row["op"], row["category"]) for row in indicators}),
    }
    archetype_json = json.dumps(archetype, sort_keys=True, separators=(",", ":"))
    entry_indicator_types = _entry_indicator_types(strategy, indicators)
    entry_archetype_json = json.dumps(entry_indicator_types, separators=(",", ":"))
    trades = int(fingerprint.get("trades", "0"))
    profit = float(fingerprint.get("profit", "nan"))
    drawdown = float(fingerprint.get("drawdown", "nan"))
    return {
        "strategy": fingerprint.get("strategyName"),
        "file": path.name,
        "sqx_sha256": _sha256(raw),
        "size_bytes": len(raw),
        "sqx_version": version,
        "strategy_xml_sha256": _sha256(strategy_raw),
        "structural_family_sha256": _sha256(structure_json.encode()),
        "archetype_sha256": _sha256(archetype_json.encode()),
        "entry_indicator_archetype_sha256": _sha256(entry_archetype_json.encode()),
        "fingerprint_exact": fingerprint.get("exact"),
        "trades_hash": fingerprint.get("tradesHash"),
        "trades": trades,
        "profit": profit,
        "drawdown": drawdown,
        "profit_drawdown_ratio": round(profit / drawdown, 8) if drawdown > 0 else None,
        "fitness": float(fingerprint.get("fitness", "nan")),
        "complexity": int(complexity_node.text) if complexity_node is not None else None,
        "signal_ops": ops,
        "indicators": indicators,
        "entry_indicator_types": entry_indicator_types,
        "structural_signals": structures,
    }


def _dominates(left: dict, right: dict) -> bool:
    """Pareto descriptiu IS; no és un gate de promoció."""
    maximize = ("trades", "profit", "profit_drawdown_ratio", "fitness")
    minimize = ("drawdown", "complexity")
    no_worse = all(left[k] >= right[k] for k in maximize) and all(
        left[k] <= right[k] for k in minimize
    )
    strictly_better = any(left[k] > right[k] for k in maximize) or any(
        left[k] < right[k] for k in minimize
    )
    return no_worse and strictly_better


def inventory(source: Path, project_cfx: Path | None = None,
              project_manifest: Path | None = None) -> dict:
    paths = sorted(source.glob("*.sqx"))
    if not paths:
        raise ValueError(f"Cap SQX a {source}")
    candidates = [inspect_sqx(path) for path in paths]
    if len({row["strategy"] for row in candidates}) != len(candidates):
        raise ValueError("Noms d'estratègia duplicats")
    pareto = []
    for row in candidates:
        if not any(_dominates(other, row) for other in candidates if other is not row):
            pareto.append(row["strategy"])
    family_counts = Counter(row["structural_family_sha256"] for row in candidates)
    families = []
    for family_hash, count in sorted(family_counts.items(), key=lambda item: (-item[1], item[0])):
        members = sorted(row["strategy"] for row in candidates
                         if row["structural_family_sha256"] == family_hash)
        families.append({"structural_family_sha256": family_hash,
                         "count": count, "members": members})
    archetype_counts = Counter(row["archetype_sha256"] for row in candidates)
    archetypes = []
    for archetype_hash, count in sorted(archetype_counts.items(), key=lambda item: (-item[1], item[0])):
        members = sorted(row["strategy"] for row in candidates
                         if row["archetype_sha256"] == archetype_hash)
        archetypes.append({"archetype_sha256": archetype_hash,
                           "count": count, "members": members})
    entry_counts = Counter(row["entry_indicator_archetype_sha256"] for row in candidates)
    entry_archetypes = []
    for entry_hash, count in sorted(entry_counts.items(), key=lambda item: (-item[1], item[0])):
        members = sorted(row["strategy"] for row in candidates
                         if row["entry_indicator_archetype_sha256"] == entry_hash)
        exemplar = next(row for row in candidates
                        if row["entry_indicator_archetype_sha256"] == entry_hash)
        entry_archetypes.append({"entry_indicator_archetype_sha256": entry_hash,
                                 "indicator_types": exemplar["entry_indicator_types"],
                                 "count": count, "members": members})
    source_hash = hashlib.sha256("".join(
        f"{row['file']}:{row['sqx_sha256']}\n" for row in candidates
    ).encode()).hexdigest()
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "source_inventory_sha256": source_hash,
        "candidate_count": len(candidates),
        "project_cfx_sha256": _sha256(project_cfx.read_bytes()) if project_cfx else None,
        "project_manifest_sha256": _sha256(project_manifest.read_bytes()) if project_manifest else None,
        "pareto_is_descriptive_only": True,
        "pareto_candidates": sorted(pareto),
        "family_count": len(families),
        "families": families,
        "archetype_count": len(archetypes),
        "archetypes": archetypes,
        "entry_indicator_archetype_count": len(entry_archetypes),
        "entry_indicator_archetypes": entry_archetypes,
        "candidates": sorted(candidates, key=lambda row: row["strategy"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--project-cfx", type=Path)
    parser.add_argument("--project-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.source, args.project_cfx, args.project_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "candidate_count", "family_count", "archetype_count",
        "entry_indicator_archetype_count", "pareto_candidates",
        "source_inventory_sha256")}, indent=2))


if __name__ == "__main__":
    main()
