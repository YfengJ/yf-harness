"""Connection lifecycle, transactions, migrations, and crash recovery."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from yfharness.storage.migrations import MIGRATIONS, SCHEMA_VERSION


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as connection:
            await connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
            )
            row = await (
                await connection.execute("SELECT version FROM schema_version LIMIT 1")
            ).fetchone()
            if row is None:
                await connection.execute("INSERT INTO schema_version(version) VALUES (0)")
                current = 0
            else:
                current = int(row[0])
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema {current} is newer than supported {SCHEMA_VERSION}"
                )
            for version in range(current + 1, SCHEMA_VERSION + 1):
                await connection.executescript(MIGRATIONS[version])
                await connection.execute("UPDATE schema_version SET version = ?", (version,))
            await connection.commit()

    async def schema_version(self) -> int:
        async with self.connect() as connection:
            row = await (
                await connection.execute("SELECT version FROM schema_version LIMIT 1")
            ).fetchone()
        return int(row[0]) if row else 0

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        try:
            await connection.execute("PRAGMA foreign_keys = ON")
            await connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        except BaseException:
            await connection.rollback()
            raise
        finally:
            await connection.close()
