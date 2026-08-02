#!/usr/bin/env python3
"""Catàleg local determinista de l'Acadèmia (només biblioteca estàndard)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "catalog" / "schema.sql"
LEVELS = {"A_PRIMARY", "B_PRACTITIONER", "C_EXPLORATORY", "D_REJECTED"}
RIGHTS = {"metadata_only", "transformative_notes", "redistributable", "first_party"}
STATUSES = {"captured", "corroborated", "tested", "verified", "contradicted", "obsolete"}
KINDS = {"documentation", "paper", "web", "video", "audio", "experiment", "note"}
STOPWORDS = {"a", "al", "amb", "cada", "com", "de", "del", "els", "el", "en", "i", "la", "les", "o", "per", "que", "quan", "un", "una"}
SOURCE_KEYS = {
    "id", "kind", "title", "url", "author", "published_at", "accessed_at", "language",
    "sq_version", "source_level", "domain", "rights_policy", "content_sha256", "metadata", "chunks",
}


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        for package_file in sorted((ROOT / "packages").glob("*/package.json")):
            package = json.loads(package_file.read_text(encoding="utf-8"))
            db.execute(
                "INSERT OR REPLACE INTO packages(id,title,version,manifest_json) VALUES(?,?,?,?)",
                (package["id"], package["title"], package["version"], json.dumps(package, sort_keys=True)),
            )


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    required = {"id", "kind", "title", "accessed_at", "source_level", "domain", "rights_policy"}
    for field in sorted(required - data.keys()):
        errors.append(f"falta el camp obligatori: {field}")
    for field in sorted(data.keys() - SOURCE_KEYS):
        errors.append(f"camp desconegut: {field}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]+", str(data.get("id", ""))):
        errors.append("id no és estable o no compleix el patró")
    if data.get("kind") not in KINDS:
        errors.append(f"kind no admès: {data.get('kind')!r}")
    if data.get("source_level") not in LEVELS:
        errors.append(f"source_level no admès: {data.get('source_level')!r}")
    if data.get("rights_policy") not in RIGHTS:
        errors.append(f"rights_policy no admès: {data.get('rights_policy')!r}")
    if not isinstance(data.get("chunks", []), list):
        errors.append("chunks ha de ser una llista")
    for index, chunk in enumerate(data.get("chunks", [])):
        if not chunk.get("locator") or not chunk.get("body"):
            errors.append(f"chunks[{index}] necessita locator i body")
        if chunk.get("evidence_status", "captured") not in STATUSES:
            errors.append(f"chunks[{index}].evidence_status no admès")
    return errors


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: JSON invàlid: {exc}") from exc
    errors = validate(data)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    return data


def ingest(db_path: Path, files: list[Path]) -> None:
    init_db(db_path)
    with connect(db_path) as db:
        for path in files:
            data = load_manifest(path)
            metadata = data.get("metadata", {})
            db.execute(
                """INSERT OR REPLACE INTO sources
                (id,kind,title,url,author,published_at,accessed_at,language,sq_version,
                 source_level,domain,rights_policy,content_sha256,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                tuple(data.get(key) for key in (
                    "id", "kind", "title", "url", "author", "published_at", "accessed_at",
                    "language", "sq_version", "source_level", "domain", "rights_policy",
                    "content_sha256",
                )) + (json.dumps(metadata, sort_keys=True),),
            )
            db.execute("DELETE FROM chunks WHERE source_id=?", (data["id"],))
            for chunk in data.get("chunks", []):
                body = chunk["body"].strip()
                db.execute(
                    """INSERT INTO chunks(source_id,locator,heading,body,body_sha256,evidence_status)
                    VALUES(?,?,?,?,?,?)""",
                    (data["id"], chunk["locator"], chunk.get("heading"), body,
                     hashlib.sha256(body.encode()).hexdigest(), chunk.get("evidence_status", "captured")),
                )


def ingest_claims(db_path: Path, files: list[Path]) -> None:
    init_db(db_path)
    with connect(db_path) as db:
        for path in files:
            claims = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(claims, list):
                raise ValueError(f"{path}: s'esperava una llista de claims")
            for claim in claims:
                if claim.get("status") not in STATUSES or not 0 <= claim.get("confidence", -1) <= 1:
                    raise ValueError(f"{path}: claim invàlida: {claim.get('id')}")
                db.execute(
                    """INSERT OR REPLACE INTO claims
                    (id,statement,status,confidence,first_seen_at,updated_at) VALUES(?,?,?,?,?,?)""",
                    tuple(claim[key] for key in ("id", "statement", "status", "confidence", "first_seen_at", "updated_at")),
                )
                db.execute("DELETE FROM claim_evidence WHERE claim_id=?", (claim["id"],))
                for evidence in claim.get("evidence", []):
                    chunk = db.execute(
                        "SELECT id FROM chunks WHERE source_id=? AND locator=?",
                        (evidence["source_id"], evidence["locator"]),
                    ).fetchone()
                    if chunk is None:
                        raise ValueError(f"{path}: evidència inexistent {evidence['source_id']}#{evidence['locator']}")
                    db.execute(
                        "INSERT INTO claim_evidence(claim_id,chunk_id,relation,notes) VALUES(?,?,?,?)",
                        (claim["id"], chunk["id"], evidence["relation"], evidence.get("notes")),
                    )


def lexical_tokens(value: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode()
    return [token for token in re.findall(r"[a-z0-9]+", plain) if token not in STOPWORDS and len(token) > 1]


def fts_query(query: str) -> str:
    tokens = lexical_tokens(query)
    if not tokens:
        raise ValueError("consulta buida")
    return " OR ".join(f'"{token}"' for token in tokens)


def search(db_path: Path, query: str, limit: int, domain: str | None = None) -> list[dict]:
    sql = """SELECT s.id source_id,s.title,s.domain,c.locator,c.heading,c.body,
             snippet(chunks_fts,1,'[',']','…',18) snippet,bm25(chunks_fts) score
             FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
             JOIN sources s ON s.id=c.source_id WHERE chunks_fts MATCH ?"""
    params: list[object] = [fts_query(query)]
    if domain:
        sql += " AND s.domain=?"
        params.append(domain)
    sql += " ORDER BY score LIMIT ?"
    params.append(limit * 4)
    with connect(db_path) as db:
        raw = [dict(row) for row in db.execute(sql, params)]
    query_terms = lexical_tokens(query)
    minimum_matches = 1 if len(query_terms) <= 2 else 2
    accepted = []
    for hit in raw:
        haystack = set(lexical_tokens(f"{hit.get('heading') or ''} {hit['body']}"))
        matches = sum(any(word.startswith(term[:5]) or term.startswith(word[:5]) for word in haystack) for term in query_terms)
        coverage = matches / len(query_terms)
        hit.pop("body")
        hit["match_coverage"] = round(coverage, 3)
        if matches >= minimum_matches and coverage >= 0.25:
            accepted.append(hit)
    return accepted[:limit]


def benchmark(db_path: Path, dataset: Path, limit: int) -> dict:
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    reciprocal_ranks, recalls, latencies, no_answer_checks = [], [], [], []
    details = []
    for case in cases:
        started = time.perf_counter()
        hits = search(db_path, case["query"], limit, case.get("domain"))
        latencies.append((time.perf_counter() - started) * 1000)
        returned = list(dict.fromkeys(hit["source_id"] for hit in hits))
        relevant = set(case["relevant_source_ids"])
        if case.get("expected_empty"):
            no_answer_checks.append(not returned)
            details.append({"id": case["id"], "returned": returned, "expected_empty": True})
            continue
        rank = next((i for i, item in enumerate(returned, 1) if item in relevant), None)
        reciprocal_ranks.append(1 / rank if rank else 0)
        recalls.append(len(relevant.intersection(returned)) / len(relevant))
        details.append({"id": case["id"], "returned": returned, "first_relevant_rank": rank})
    answerable = len(recalls)
    result = {
        "engine": "sqlite-fts5-bm25", "cases": len(cases), "answerable_cases": answerable,
        f"recall_at_{limit}": sum(recalls) / answerable if answerable else None,
        f"mrr_at_{limit}": sum(reciprocal_ranks) / answerable if answerable else None,
        "latency_ms_mean": sum(latencies) / len(cases), "details": details,
    }
    if no_answer_checks:
        result["no_answer_accuracy"] = sum(no_answer_checks) / len(no_answer_checks)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "catalog" / "academia.db")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    load = commands.add_parser("ingest")
    load.add_argument("files", type=Path, nargs="+")
    claim_load = commands.add_parser("ingest-claims")
    claim_load.add_argument("files", type=Path, nargs="+")
    find = commands.add_parser("search")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    find.add_argument("--domain")
    bench = commands.add_parser("benchmark")
    bench.add_argument("dataset", type=Path)
    bench.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init_db(args.db)
            result = {"database": str(args.db), "status": "initialized"}
        elif args.command == "ingest":
            ingest(args.db, args.files)
            result = {"ingested": len(args.files)}
        elif args.command == "ingest-claims":
            ingest_claims(args.db, args.files)
            result = {"claim_files_ingested": len(args.files)}
        elif args.command == "search":
            result = search(args.db, args.query, args.limit, args.domain)
        else:
            result = benchmark(args.db, args.dataset, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, sqlite3.Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
