#!/usr/bin/env python3
"""Select a v10 validation representative by topology, never by performance."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

from lab.sq_bridge.xau_d1_trend_pullback_v10 import PARAMETERS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adjacent(left: dict, right: dict, grid: dict) -> bool:
    differences = []
    for name in PARAMETERS:
        if left[name] == right[name]:
            continue
        if name == "side":
            return False
        differences.append(abs(grid[name].index(left[name]) - grid[name].index(right[name])))
    return differences == [1]


def components(rows: list[dict], grid: dict) -> list[list[int]]:
    graph = {i: [] for i in range(len(rows))}
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if adjacent(rows[i]["parameters"], rows[j]["parameters"], grid):
                graph[i].append(j); graph[j].append(i)
    pending, result = set(graph), []
    while pending:
        seed = min(pending); pending.remove(seed); queue = [seed]; component = []
        while queue:
            node = queue.pop(); component.append(node)
            for neighbour in graph[node]:
                if neighbour in pending:
                    pending.remove(neighbour); queue.append(neighbour)
        result.append(sorted(component))
    return result


def medoid(component: list[int], rows: list[dict], grid: dict) -> int:
    neighbours = {i: [j for j in component if i != j and adjacent(rows[i]["parameters"], rows[j]["parameters"], grid)] for i in component}
    scores = []
    for start in component:
        distance = {start: 0}; queue = deque([start])
        while queue:
            node = queue.popleft()
            for other in neighbours[node]:
                if other not in distance:
                    distance[other] = distance[node] + 1; queue.append(other)
        scores.append((sum(distance.values()), rows[start]["candidate_id"], start))
    return min(scores)[2]


def select(train_path: Path, family_path: Path) -> dict:
    train, family = json.loads(train_path.read_text()), json.loads(family_path.read_text())
    rows = train["stable_candidates"]
    if not rows:
        raise ValueError("NO_STABLE_CANDIDATES")
    groups = components(rows, family["pre_registered_grid"])
    largest = min(groups, key=lambda group: (-len(group), sorted(rows[i]["candidate_id"] for i in group)))
    chosen = rows[medoid(largest, rows, family["pre_registered_grid"])]
    return {
        "schema_version": 1, "family_id": family["family_id"],
        "selection_rule": family["representative_selection"],
        "train_artifact": str(train_path), "train_artifact_sha256": sha256(train_path),
        "stable_candidates": len(rows), "component_sizes": sorted((len(group) for group in groups), reverse=True),
        "selected_candidate_ids": [chosen["candidate_id"]],
        "selected": [{"candidate_id": chosen["candidate_id"], "parameters": chosen["parameters"],
                      "train_metrics": chosen["metrics"]}],
        "validation_accessed": False, "holdout_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = select(args.train, args.family)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
