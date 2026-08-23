"""Forward-only, non-destructive SQLite migrations."""

from __future__ import annotations

SCHEMA_VERSION = 2

MIGRATIONS: dict[int, str] = {
    1: """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'chat',
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX idx_sessions_title ON sessions(title);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content_json TEXT NOT NULL,
    name TEXT,
    tool_call_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    step_count INTEGER NOT NULL DEFAULT 0,
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    usage_json TEXT NOT NULL DEFAULT '{}',
    error TEXT
);
CREATE INDEX idx_runs_session ON runs(session_id, started_at DESC);

CREATE TABLE model_requests (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_events_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    duration REAL,
    first_token_latency REAL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_type TEXT
);

CREATE TABLE tool_calls (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT,
    risk_level TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL
);

CREATE TABLE approvals (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    tool_call_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    decision TEXT,
    decided_at TEXT
);

CREATE TABLE usage_records (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated INTEGER NOT NULL DEFAULT 0,
    cost REAL,
    duration REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE context_snapshots (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL,
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE file_change_records (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(run_id) ON DELETE SET NULL,
    tool_call_id TEXT,
    path TEXT NOT NULL,
    before_hash TEXT,
    after_hash TEXT,
    before_content BLOB,
    after_content BLOB,
    created_at TEXT NOT NULL,
    undone_at TEXT
);

CREATE TABLE application_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
""",
    2: """
ALTER TABLE messages ADD COLUMN tool_calls_json TEXT NOT NULL DEFAULT '[]';
""",
}
