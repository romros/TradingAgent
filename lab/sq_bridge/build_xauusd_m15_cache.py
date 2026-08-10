#!/usr/bin/env python3
"""Build regenerable yearly XAUUSD M15 cache partitions from canonical M1 parquet."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def fingerprint(files: list[Path]) -> str:
    payload = "".join(f"{path}:{path.stat().st_size}:{path.stat().st_mtime_ns}\n" for path in files)
    return hashlib.sha256(payload.encode()).hexdigest()


def build(source_root: Path, cache_root: Path, year: int) -> dict:
    import duckdb
    files = sorted((source_root / "XAUUSD" / "tf=1m" / f"year={year}").glob("month=*/data.parquet"))
    if not files:
        raise FileNotFoundError(f"no XAUUSD M1 files for {year}")
    output = cache_root / f"year={year}" / "data.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET preserve_insertion_order=false")
    query = """
      CREATE TEMP TABLE aggregated AS
      SELECT CAST(floor(ts/900)*900 AS BIGINT) ts,
             arg_min(open,ts) open, max(high) high, min(low) low,
             arg_max("close",ts) AS "close", count(DISTINCT ts) minute_count
      FROM read_parquet(?, hive_partitioning=false)
      GROUP BY 1 ORDER BY 1
    """
    connection.execute(query, [[str(path) for path in files]])
    safe_output = str(output).replace("'", "''")
    connection.execute(f"COPY aggregated TO '{safe_output}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    bars = connection.execute("SELECT count(*) FROM read_parquet(?)", [str(output)]).fetchone()[0]
    connection.close()
    manifest = {"schema_version": 1, "symbol": "XAUUSD", "timeframe": "M15",
                "year": year, "source_files": [str(path) for path in files],
                "source_fingerprint": fingerprint(files), "output": str(output),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "bars": bars}
    output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    result = build(args.source_root, args.cache_root, args.year)
    print(json.dumps({key: result[key] for key in ("year", "bars", "output_sha256")}, indent=2))


if __name__ == "__main__":
    main()
