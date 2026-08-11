#!/usr/bin/env python3
"""Resume US500 v4 screen branches through supervised SQ generation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab.sq_bridge.eurusd_v4_sq_worker import tick as tick_v4, validate_scaffold
from lab.sq_bridge.us500_v4_hypotheses import US500_PROFILE_BLOCKS
from lab.sq_bridge.us500_v4_project_batch import compile_projects
from lab.sq_bridge.us500_v4_screen_trigger import verify_completed


def validate_us500_scaffold(path: Path, expected_hash: str,
                            expected_version: str) -> dict:
    return validate_scaffold(
        path, expected_hash, expected_version,
        tuple(sorted(US500_PROFILE_BLOCKS)))


def tick(**kwargs) -> dict:
    return tick_v4(
        **kwargs, screen_verify_fn=verify_completed,
        scaffold_validate_fn=validate_us500_scaffold,
        compile_fn=compile_projects)


def main() -> None:
    root = Path(__file__).parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-dir", type=Path, default=root / "data" /
                        "alquimia_v4/us500-d1-alquimia-v4/screen-bootstrap")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).with_name("us500_v4_sq_worker_config.json"))
    parser.add_argument("--output-dir", type=Path, default=root / "data" /
                        "alquimia_v4/us500-d1-alquimia-v4/sq-worker")
    args = parser.parse_args()
    print(json.dumps(tick(
        screen_dir=args.screen_dir, config_path=args.config,
        output_dir=args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
