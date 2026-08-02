PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    author TEXT,
    published_at TEXT,
    accessed_at TEXT NOT NULL,
    language TEXT,
    sq_version TEXT,
    source_level TEXT NOT NULL CHECK(source_level IN
      ('A_PRIMARY', 'B_PRACTITIONER', 'C_EXPLORATORY', 'D_REJECTED')),
    domain TEXT NOT NULL DEFAULT 'generic',
    rights_policy TEXT NOT NULL DEFAULT 'metadata_only',
    content_sha256 TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    locator TEXT NOT NULL,
    heading TEXT,
    body TEXT NOT NULL,
    body_sha256 TEXT NOT NULL,
    evidence_status TEXT NOT NULL DEFAULT 'captured' CHECK(evidence_status IN
      ('captured', 'corroborated', 'tested', 'verified', 'contradicted', 'obsolete')),
    UNIQUE(source_id, locator, body_sha256)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    heading,
    body,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, heading, body) VALUES (new.id, new.heading, new.body);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, heading, body)
  VALUES ('delete', old.id, old.heading, old.body);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, heading, body)
  VALUES ('delete', old.id, old.heading, old.body);
  INSERT INTO chunks_fts(rowid, heading, body) VALUES (new.id, new.heading, new.body);
END;

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims(id),
    chunk_id INTEGER NOT NULL REFERENCES chunks(id),
    relation TEXT NOT NULL CHECK(relation IN ('supports', 'contradicts', 'mentions')),
    notes TEXT,
    PRIMARY KEY (claim_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    claim_id TEXT REFERENCES claims(id),
    status TEXT NOT NULL,
    sq_version TEXT NOT NULL,
    project_sha256 TEXT,
    artifact_path TEXT,
    result_summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1))
);

CREATE INDEX IF NOT EXISTS chunks_source_idx ON chunks(source_id);
CREATE INDEX IF NOT EXISTS sources_domain_idx ON sources(domain);
