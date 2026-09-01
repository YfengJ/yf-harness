"""All application SQL lives behind repository methods."""

from __future__ import annotations

import builtins
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from yfharness.core.compaction import CompactionSummary
from yfharness.core.models import AgentRun, AgentState, Message, RunStatus, Usage
from yfharness.storage.database import Database
from yfharness.storage.models import (
    FileChangeRecord,
    SessionRecord,
    UsageOverview,
    UsageTotals,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _workspace_value(workspace: Path | str | None) -> str | None:
    if workspace is None:
        return None
    return str(Path(workspace).expanduser().resolve())


def _normalize_goal(goal: str | None, status: str) -> tuple[str | None, str]:
    normalized = goal.strip() if goal is not None else ""
    if not normalized:
        return None, "inactive"
    if status not in {"active", "completed"}:
        raise ValueError("goal status must be active or completed")
    if len(normalized) > 4_000:
        raise ValueError("goal must not exceed 4000 characters")
    return normalized, status


def _session_record(row: sqlite3.Row) -> SessionRecord:
    payload = dict(row)
    raw_summary = payload.pop("context_summary_json", None)
    payload["context_summary"] = json.loads(raw_summary) if raw_summary else None
    return SessionRecord.model_validate(payload)


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
        workspace: Path | str | None = None,
        goal: str | None = None,
        goal_status: str = "inactive",
        context_summary: CompactionSummary | None = None,
        context_compacted_at: datetime | None = None,
    ) -> SessionRecord:
        normalized_goal, normalized_status = _normalize_goal(goal, goal_status)
        session_id = str(uuid4())
        now = _now()
        async with self.database.connect() as connection:
            await connection.execute(
                """
                INSERT INTO sessions(
                    id, title, provider, model, mode, workspace, goal, goal_status,
                    goal_updated_at, context_summary_json, context_compacted_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    provider,
                    model,
                    mode,
                    _workspace_value(workspace),
                    normalized_goal,
                    normalized_status,
                    now if normalized_goal is not None else None,
                    context_summary.model_dump_json() if context_summary is not None else None,
                    context_compacted_at.isoformat() if context_compacted_at is not None else None,
                    now,
                    now,
                ),
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
        return _session_record(row) if row else None

    async def list(
        self,
        *,
        query: str | None = None,
        include_archived: bool = False,
        workspace: Path | str | None = None,
    ) -> builtins.list[SessionRecord]:
        conditions = ["1 = 1"]
        params: list[object] = []
        if not include_archived:
            conditions.append("archived = 0")
        if query:
            conditions.append("title LIKE ? ESCAPE '\\'")
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        if workspace is not None:
            conditions.append("workspace = ?")
            params.append(_workspace_value(workspace))
        sql = f"SELECT * FROM sessions WHERE {' AND '.join(conditions)} ORDER BY updated_at DESC"
        async with self.database.connect() as connection:
            rows = await (await connection.execute(sql, params)).fetchall()
        return [_session_record(row) for row in rows]

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

    async def update_goal(
        self,
        session_id: str,
        goal: str | None,
        *,
        status: str = "active",
    ) -> bool:
        normalized_goal, normalized_status = _normalize_goal(goal, status)
        now = _now()
        return await self._update(
            """
            UPDATE sessions
            SET goal = ?, goal_status = ?, goal_updated_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                normalized_goal,
                normalized_status,
                now if normalized_goal is not None else None,
                now,
                session_id,
            ),
        )

    async def update_runtime(
        self,
        session_id: str,
        *,
        provider: str,
        model: str,
        mode: str,
    ) -> bool:
        if not provider.strip() or not model.strip() or not mode.strip():
            raise ValueError("provider, model, and mode must not be empty")
        return await self._update(
            """
            UPDATE sessions
            SET provider = ?, model = ?, mode = ?, updated_at = ?
            WHERE id = ?
            """,
            (provider, model, mode, _now(), session_id),
        )

    async def update_context_summary(
        self,
        session_id: str,
        summary: CompactionSummary | None,
    ) -> bool:
        now = _now()
        return await self._update(
            """
            UPDATE sessions
            SET context_summary_json = ?, context_compacted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                summary.model_dump_json() if summary is not None else None,
                now if summary is not None else None,
                now,
                session_id,
            ),
        )

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

    async def fork(self, session_id: str, *, title: str | None = None) -> SessionRecord:
        source = await self.get(session_id)
        if source is None:
            raise KeyError(f"session not found: {session_id}")
        forked = await self.create(
            title=title or f"{source.title} · 分支",
            provider=source.provider,
            model=source.model,
            mode=source.mode,
            workspace=source.workspace,
            goal=source.goal,
            goal_status=source.goal_status,
            context_summary=source.context_summary,
            context_compacted_at=source.context_compacted_at,
        )
        for message in await self.messages(session_id):
            await self.add_message(
                forked.id,
                message.model_copy(update={"id": str(uuid4())}, deep=True),
            )
        return forked

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

    async def get(self, record_id: str) -> FileChangeRecord | None:
        async with self.database.connect() as connection:
            row = await (
                await connection.execute(
                    "SELECT * FROM file_change_records WHERE id = ?",
                    (record_id,),
                )
            ).fetchone()
        return FileChangeRecord.model_validate(dict(row)) if row else None

    async def list_for_session(
        self,
        session_id: str,
        *,
        limit: int = 50,
    ) -> builtins.list[FileChangeRecord]:
        async with self.database.connect() as connection:
            rows = await (
                await connection.execute(
                    """
                    SELECT changes.* FROM file_change_records AS changes
                    JOIN runs ON runs.run_id = changes.run_id
                    WHERE runs.session_id = ?
                    ORDER BY changes.created_at DESC, changes.rowid DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
            ).fetchall()
        return [FileChangeRecord.model_validate(dict(row)) for row in rows]

    async def list_for_run(self, run_id: str) -> builtins.list[FileChangeRecord]:
        async with self.database.connect() as connection:
            rows = await (
                await connection.execute(
                    """
                    SELECT * FROM file_change_records
                    WHERE run_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    """,
                    (run_id,),
                )
            ).fetchall()
        return [FileChangeRecord.model_validate(dict(row)) for row in rows]

    async def mark_undone(self, record_id: str) -> bool:
        async with self.database.connect() as connection:
            cursor = await connection.execute(
                """
                UPDATE file_change_records SET undone_at = ?
                WHERE id = ? AND undone_at IS NULL
                """,
                (_now(), record_id),
            )
            await connection.commit()
            return cursor.rowcount > 0

    async def mark_undone_many(self, record_ids: builtins.list[str]) -> bool:
        if not record_ids:
            return False
        placeholders = ", ".join("?" for _ in record_ids)
        async with self.database.connect() as connection:
            cursor = await connection.execute(
                f"""
                UPDATE file_change_records SET undone_at = ?
                WHERE id IN ({placeholders}) AND undone_at IS NULL
                """,
                (_now(), *record_ids),
            )
            if cursor.rowcount != len(record_ids):
                await connection.rollback()
                return False
            await connection.commit()
            return True


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

    async def usage_overview(
        self,
        *,
        session_id: str,
        workspace: Path | str,
        day_start: datetime,
        month_start: datetime,
    ) -> UsageOverview:
        sql = """
        WITH scoped AS (
            SELECT u.*, r.session_id, s.workspace
            FROM usage_records AS u
            JOIN runs AS r ON r.run_id = u.run_id
            JOIN sessions AS s ON s.id = r.session_id
        ), totals AS (
            SELECT 'session' AS period, * FROM scoped WHERE session_id = ?
            UNION ALL
            SELECT 'today' AS period, * FROM scoped
                WHERE workspace = ? AND created_at >= ?
            UNION ALL
            SELECT 'month' AS period, * FROM scoped
                WHERE workspace = ? AND created_at >= ?
        )
        SELECT
            period,
            COUNT(*) AS run_count,
            COALESCE(SUM(input_tokens), 0) AS input_tokens,
            COALESCE(SUM(output_tokens), 0) AS output_tokens,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(CASE WHEN estimated = 1 THEN total_tokens ELSE 0 END), 0)
                AS estimated_tokens,
            COALESCE(SUM(CASE WHEN estimated = 1 THEN 1 ELSE 0 END), 0)
                AS estimated_runs,
            COALESCE(SUM(CASE WHEN cost IS NOT NULL THEN cost ELSE 0 END), 0.0)
                AS known_cost,
            COALESCE(SUM(CASE WHEN cost IS NULL THEN 1 ELSE 0 END), 0)
                AS unknown_cost_runs,
            COALESCE(SUM(duration), 0.0) AS duration
        FROM totals
        GROUP BY period
        """
        workspace_value = _workspace_value(workspace)
        async with self.database.connect() as connection:
            rows = await (
                await connection.execute(
                    sql,
                    (
                        session_id,
                        workspace_value,
                        day_start.astimezone(UTC).isoformat(),
                        workspace_value,
                        month_start.astimezone(UTC).isoformat(),
                    ),
                )
            ).fetchall()
        periods = {
            str(row["period"]): UsageTotals.model_validate(
                {key: value for key, value in dict(row).items() if key != "period"}
            )
            for row in rows
        }
        return UsageOverview(
            session=periods.get("session", UsageTotals()),
            today=periods.get("today", UsageTotals()),
            month=periods.get("month", UsageTotals()),
            generated_at=datetime.now(UTC),
        )

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
