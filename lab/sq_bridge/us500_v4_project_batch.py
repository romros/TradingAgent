#!/usr/bin/env python3
"""Compile every authorized US500 v4 branch into verified, inert SQ CFX files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab.sq_bridge.eurusd_v4_project_batch import compile_projects as compile_v4_projects
from lab.sq_bridge.us500_sq_generation_plan_v4 import compile_plan


def compile_projects(**kwargs) -> dict:
    return compile_v4_projects(
        **kwargs, market_key="US500", compile_plan_fn=compile_plan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", required=True, type=Path)
    parser.add_argument("--scaffold", required=True, type=Path)
    parser.add_argument("--registry", type=Path,
                        default=Path(__file__).with_name("ostium_markets.json"))
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = compile_projects(
        bootstrap_path=args.bootstrap, scaffold_path=args.scaffold,
        registry_path=args.registry, methodology_path=args.methodology,
        output_dir=args.output_dir)
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"]),
                      "sqcli_started": result["sqcli_started"]}, indent=2))


if __name__ == "__main__":
    main()
