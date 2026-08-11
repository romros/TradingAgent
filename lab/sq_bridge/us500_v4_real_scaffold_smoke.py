#!/usr/bin/env python3
"""Compile all US500 v4 search surfaces from the real SQ scaffold without running SQ."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab.sq_bridge.eurusd_v4_real_scaffold_smoke import smoke
from lab.sq_bridge.us500_v4_hypotheses import US500_PROFILE_BLOCKS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scaffold", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects/EURUSD/project.cfx"))
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name(
        "evidence") / "us500_d1_canonical_v4.csv")
    parser.add_argument("--registry", type=Path,
                        default=Path(__file__).with_name("ostium_markets.json"))
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("us500_v4_sq_worker_config.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = smoke(
        scaffold_path=args.scaffold, source_path=args.source,
        registry_path=args.registry, methodology_path=args.methodology,
        worker_config_path=args.worker_config, market_key="US500",
        profiles=US500_PROFILE_BLOCKS)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
