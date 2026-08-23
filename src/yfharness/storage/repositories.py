"""All application SQL lives behind repository methods."""

from __future__ import annotations

import builtins
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from yfharness.core.models import AgentRun, AgentState, Message, RunStatus, Usage
from yfharness.storage.database import Database
from yfharness.storage.models import SessionRecord


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SessionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(
        self,
        *,
        title: str,
        provider: str,
        model: str,
        mode: str = "chat",
    ) -> SessionRecord:
        session_id = str(uuid4())
        now = _now()
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO sessions(id, title, provider, model, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, title, provider, model, mode, now, now),
            )
            await connection.commit()
        session = await self.get(session_id)
        assert session is not None
        return session

    async def get(self, session_id: str) -> SessionRecord | None:
        async with self.database.connect() as connection:
            row = await (
                await connection.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            ).fetchone()
        return SessionRecord.model_validate(dict(row)) if row else None

    async def list(
        self, *, query: str | None = None, include_archived: bool = False
    ) -> builtins.list[SessionRecord]:
        conditions = ["1 = 1"]
        params: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if query:
            conditions.append("title LIKE ? ESCAPE '\\'")
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        sql = f"SELECT * FROM sessions WHERE {' AND '.join(conditions)} ORDER BY updated_at DESC"
        async with self.database.connect() as connection:
            rows = await (await connection.execute(sql, params)).fetchall()
        return [SessionRecord.model_validate(dict(row)) for row in rows]

    async def rename(self, session_id: str, title: str) -> bool:
        if not title.strip():
            raise ValueError("session title must not be empty")
        return await self._update(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title.strip(), _now(), session_id),
        )

    async def archive(self, session_id: str, *, archived: bool = True) -> bool:
        return await self._update(
            "UPDATE sessions SET archived = ?, updated_at = ? WHERE id = ?",
            (int(archived), _now(), session_id),
        )

    async def delete(self, session_id: str) -> bool:
        return await self._update("DELETE FROM sessions WHERE id = ?", (session_id,))

    async def add_message(self, session_id: str, message: Message) -> None:
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO messages(
                    id, session_id, role, content_json, name, tool_call_id,
                    metadata_json, created_at, tool_calls_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    session_id,
                    message.role.value,
                    json.dumps([part.model_dump(mode="json") for part in message.content]),
                    message.name,
                    message.tool_call_id,
                    json.dumps(message.metadata),
                    message.created_at.isoformat(),
                    json.dumps([call.model_dump(mode="json") for call in message.tool_calls]),
                ),
            )
            await connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
            )
            await connection.commit()

    async def messages(self, session_id: str) -> builtins.list[Message]:
        async with self.database.connect() as connection:
            rows = await (
                await connection.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at, rowid",
                    (session_id,),
                )
            ).fetchall()
        return [
            Message.model_validate(
                {
                    "id": row["id"],
                    "role": row["role"],
                    "content": json.loads(row["content_json"]),
                    "name": row["name"],
                    "tool_call_id": row["tool_call_id"],
                    "tool_calls": json.loads(row["tool_calls_json"]),
                    "metadata": json.loads(row["metadata_json"]),
                    "created_at": row["created_at"],
                }
            )
            for row in rows
        ]

    async def export(self, session_id: str, *, format: str = "markdown") -> str:
        session = await self.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        messages = await self.messages(session_id)
        if format == "json":
            payload = {
                "session": session.model_dump(mode="json"),
                "messages": [message.model_dump(mode="json") for message in messages],
            }
            return json.dumps(_redact(payload), ensure_ascii=False, indent=2)
        if format != "markdown":
            raise ValueError("format must be markdown or json")
        lines = [f"# {session.title}", "", f"- Session: `{session.id}`", ""]
        for message in messages:
            lines.extend([f"## {message.role.value}", "", _redact_text(message.text_content), ""])
        return "\n".join(lines)

    async def _update(self, sql: str, params: tuple[object, ...]) -> bool:
        async with self.database.connect() as connection:
            cursor = await connection.execute(sql, params)
            await connection.commit()
            return cursor.rowcount > 0


class RunRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(self, session_id: str) -> AgentRun:
        run = AgentRun(session_id=session_id)
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO runs(
                    run_id, trace_id, session_id, state, status, started_at,
                    step_count, tool_call_count, usage_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.trace_id,
                    session_id,
                    run.state.value,
                    run.status.value,
                    run.started_at.isoformat(),
                    0,
                    0,
                    run.usage.model_dump_json(),
                ),
            )
            await connection.commit()
        return run

    async def finish(
        self,
        run: AgentRun,
        *,
        status: RunStatus,
        state: AgentState,
        usage: Usage,
        error: str | None = None,
    ) -> None:
        ended_at = datetime.now(UTC)
        async with self.database.connect() as connection:
            await connection.execute(
                """
                UPDATE runs SET status = ?, state = ?, ended_at = ?, step_count = ?,
                    tool_call_count = ?, usage_json = ?, error = ? WHERE run_id = ?
                """,
                (
                    status.value,
                    state.value,
                    ended_at.isoformat(),
                    run.step_count,
                    run.tool_call_count,
                    usage.model_dump_json(),
                    error,
                    run.run_id,
                ),
            )
            await connection.commit()

    async def mark_interrupted(self) -> int:
        async with self.database.connect() as connection:
            cursor = await connection.execute(
                """
                UPDATE runs SET status = ?, state = ?, ended_at = ?,
                    error = COALESCE(error, 'process interrupted') WHERE status = ?
                """,
                (
                    RunStatus.INTERRUPTED.value,
                    AgentState.FAILED.value,
                    _now(),
                    RunStatus.RUNNING.value,
                ),
            )
            await connection.commit()
            return cursor.rowcount

    async def get(self, run_id: str) -> AgentRun | None:
        async with self.database.connect() as connection:
            row = await (
                await connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            ).fetchone()
        if row is None:
            return None
        return AgentRun.model_validate(
            {
                "run_id": row["run_id"],
                "trace_id": row["trace_id"],
                "session_id": row["session_id"],
                "state": row["state"],
                "status": row["status"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "step_count": row["step_count"],
                "tool_call_count": row["tool_call_count"],
                "usage": json.loads(row["usage_json"]),
                "error": row["error"],
            }
        )


class FileChangeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def record(
        self,
        *,
        path: str,
        before: bytes | None,
        after: bytes | None,
        run_id: str | None,
        tool_call_id: str | None,
    ) -> str:
        record_id = str(uuid4())
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO file_change_records(
                    id, run_id, tool_call_id, path, before_hash, after_hash,
                    before_content, after_content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    run_id,
                    tool_call_id,
                    path,
                    _bytes_hash(before),
                    _bytes_hash(after),
                    before,
                    after,
                    _now(),
                ),
            )
            await connection.commit()
        return record_id


class TraceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def record_model_events(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
        request: dict[str, object],
        events: list[dict[str, object]],
        duration: float,
        retry_count: int = 0,
        error_type: str | None = None,
    ) -> str:
        record_id = str(uuid4())
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO model_requests(
                    id, run_id, provider, model, request_json, response_events_json,
                    started_at, duration, retry_count, error_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    run_id,
                    provider,
                    model,
                    json.dumps(_redact(request), ensure_ascii=False),
                    json.dumps(_redact(events), ensure_ascii=False),
                    _now(),
                    duration,
                    retry_count,
                    error_type,
                ),
            )
            await connection.commit()
        return record_id

    async def record_tool_call(
        self,
        *,
        run_id: str,
        call_id: str,
        name: str,
        arguments: dict[str, object],
        result: dict[str, object] | None,
        risk_level: str,
        status: str,
    ) -> None:
        now = _now()
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT OR REPLACE INTO tool_calls(
                    id, run_id, tool_name, arguments_json, result_json,
                    risk_level, started_at, ended_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{run_id}:{call_id}",
                    run_id,
                    name,
                    json.dumps(_redact(arguments), ensure_ascii=False),
                    json.dumps(_redact(result), ensure_ascii=False) if result is not None else None,
                    risk_level,
                    now,
                    now if result is not None else None,
                    status,
                ),
            )
            await connection.commit()

    async def record_approval(
        self,
        *,
        request_id: str,
        run_id: str,
        tool_call_id: str,
        request: dict[str, object],
        decision: str,
    ) -> None:
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO approvals(
                    id, run_id, tool_call_id, request_json, decision, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    run_id,
                    tool_call_id,
                    json.dumps(_redact(request), ensure_ascii=False),
                    decision,
                    _now(),
                ),
            )
            await connection.commit()

    async def record_usage(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
        usage: Usage,
        duration: float,
    ) -> None:
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO usage_records(
                    id, run_id, provider, model, input_tokens, output_tokens,
                    total_tokens, estimated, cost, duration, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    run_id,
                    provider,
                    model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.total_tokens,
                    int(usage.estimated),
                    usage.cost,
                    duration,
                    _now(),
                ),
            )
            await connection.commit()

    async def record_context(
        self,
        *,
        run_id: str,
        snapshot: dict[str, object],
        estimated_tokens: int,
    ) -> None:
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO context_snapshots(
                    id, run_id, snapshot_json, estimated_tokens, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    run_id,
                    json.dumps(_redact(snapshot), ensure_ascii=False),
                    estimated_tokens,
                    _now(),
                ),
            )
            await connection.commit()

    async def replay(self, run_id: str) -> dict[str, object]:
        async with self.database.connect() as connection:
            run = await (
                await connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            ).fetchone()
            requests = await (
                await connection.execute(
                    "SELECT * FROM model_requests WHERE run_id = ? ORDER BY started_at", (run_id,)
                )
            ).fetchall()
            tools = await (
                await connection.execute(
                    "SELECT * FROM tool_calls WHERE run_id = ? ORDER BY started_at", (run_id,)
                )
            ).fetchall()
            approvals = await (
                await connection.execute(
                    "SELECT * FROM approvals WHERE run_id = ? ORDER BY decided_at", (run_id,)
                )
            ).fetchall()
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        return {
            "mode": "read_only_replay",
            "run": dict(run),
            "model_requests": [
                _decoded_row(row, {"request_json", "response_events_json"}) for row in requests
            ],
            "tool_calls": [_decoded_row(row, {"arguments_json", "result_json"}) for row in tools],
            "approvals": [_decoded_row(row, {"request_json"}) for row in approvals],
        }


def _redact(value: object) -> object:
    sensitive = {"api_key", "authorization", "token", "secret", "password"}
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower() in sensitive else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(text: str) -> str:
    prefixes = ("sk-", "Bearer ")
    if any(prefix in text for prefix in prefixes):
        return "<redacted sensitive content>"
    return text


def _bytes_hash(value: bytes | None) -> str | None:
    return hashlib.sha256(value).hexdigest() if value is not None else None


def _decoded_row(row: sqlite3.Row, json_fields: set[str]) -> dict[str, object]:
    result: dict[str, object] = dict(row)
    for field in json_fields:
        value = result.get(field)
        if isinstance(value, str):
            result[field] = json.loads(value)
    return result
