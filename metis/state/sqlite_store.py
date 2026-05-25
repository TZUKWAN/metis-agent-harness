"""SQLite-backed state store for sessions, messages, tool calls, and planning."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from metis.planning.models import Goal, Plan, Step


class SQLiteStateStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    step_id TEXT,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    acceptance_json TEXT NOT NULL DEFAULT '[]',
                    constraints_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    order_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    action TEXT NOT NULL,
                    required_inputs_json TEXT NOT NULL DEFAULT '[]',
                    expected_output TEXT NOT NULL,
                    allowed_tools_json TEXT NOT NULL DEFAULT '[]',
                    verification_method TEXT NOT NULL,
                    done_condition TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    artifact_refs_json TEXT NOT NULL DEFAULT '[]',
                    required_gates_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    strength TEXT NOT NULL DEFAULT 'medium',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS loops (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    interval_seconds REAL NOT NULL,
                    max_iterations INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    last_run_at TEXT,
                    iterations INTEGER NOT NULL DEFAULT 0,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    loop_id TEXT NOT NULL,
                    expression TEXT NOT NULL,
                    next_run_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS run_checkpoints (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    task_contract_hash TEXT NOT NULL DEFAULT '',
                    prompt_stack_hash TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            self._ensure_column(conn, "steps", "required_gates_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "evidence", "strength", "TEXT NOT NULL DEFAULT 'medium'")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_session(self, session_id: str | None = None, metadata: dict[str, Any] | None = None) -> str:
        session_id = session_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, metadata_json) VALUES (?, ?)",
                (session_id, json.dumps(metadata or {}, ensure_ascii=False)),
            )
        return session_id

    def append_message(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages (session_id, role, content, metadata_json) VALUES (?, ?, ?, ?)",
                (session_id, role, content, json.dumps(metadata or {}, ensure_ascii=False)),
            )
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (session_id,))
            return int(cur.lastrowid)

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, metadata_json FROM messages WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [
            {"role": row["role"], "content": row["content"], "metadata": json.loads(row["metadata_json"])}
            for row in rows
        ]

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, status, metadata_json, created_at, updated_at FROM sessions ORDER BY updated_at DESC, created_at DESC, id"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "status": row["status"],
                "metadata": json.loads(row["metadata_json"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        args: dict[str, Any],
        *,
        result: str = "",
        status: str = "ok",
        error: str | None = None,
        step_id: str | None = None,
        call_id: str | None = None,
    ) -> str:
        call_id = call_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_calls (id, session_id, step_id, tool_name, args_json, result, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (call_id, session_id, step_id, tool_name, json.dumps(args, ensure_ascii=False), result, status, error),
            )
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (session_id,))
        return call_id

    def list_tool_calls(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_calls WHERE session_id=? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
        return [dict(row) | {"args": json.loads(row["args_json"])} for row in rows]

    def create_goal(
        self,
        session_id: str,
        objective: str,
        *,
        acceptance_criteria: list[str] | None = None,
        constraints: list[str] | None = None,
        goal_id: str | None = None,
    ) -> str:
        goal_id = goal_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO goals (id, session_id, objective, acceptance_json, constraints_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    goal_id,
                    session_id,
                    objective,
                    json.dumps(acceptance_criteria or [], ensure_ascii=False),
                    json.dumps(constraints or [], ensure_ascii=False),
                ),
            )
        return goal_id

    def get_goal(self, goal_id: str) -> Goal | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        if row is None:
            return None
        return Goal(
            id=row["id"],
            session_id=row["session_id"],
            objective=row["objective"],
            status=row["status"],
            acceptance_criteria=json.loads(row["acceptance_json"]),
            constraints=json.loads(row["constraints_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_goal_status(self, goal_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE goals SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, goal_id),
            )

    def create_plan(self, goal_id: str, *, version: int = 1, plan_id: str | None = None) -> str:
        plan_id = plan_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO plans (id, goal_id, version) VALUES (?, ?, ?)",
                (plan_id, goal_id, version),
            )
        return plan_id

    def get_plan(self, plan_id: str) -> Plan | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        if row is None:
            return None
        return Plan(id=row["id"], goal_id=row["goal_id"], version=row["version"], status=row["status"], created_at=row["created_at"])

    def create_step(
        self,
        plan_id: str,
        *,
        order_index: int,
        title: str,
        action: str,
        expected_output: str,
        verification_method: str,
        done_condition: str,
        required_inputs: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        required_gates: list[str] | None = None,
        step_id: str | None = None,
    ) -> str:
        step_id = step_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO steps (
                    id, plan_id, order_index, title, action, required_inputs_json, expected_output,
                    allowed_tools_json, verification_method, done_condition, required_gates_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    plan_id,
                    order_index,
                    title,
                    action,
                    json.dumps(required_inputs or [], ensure_ascii=False),
                    expected_output,
                    json.dumps(allowed_tools or [], ensure_ascii=False),
                    verification_method,
                    done_condition,
                    json.dumps(required_gates or [], ensure_ascii=False),
                ),
            )
        return step_id

    def get_step(self, step_id: str) -> Step | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM steps WHERE id=?", (step_id,)).fetchone()
        return self._row_to_step(row) if row else None

    def list_steps(self, plan_id: str) -> list[Step]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM steps WHERE plan_id=? ORDER BY order_index",
                (plan_id,),
            ).fetchall()
        return [self._row_to_step(row) for row in rows]

    def update_step_status(self, step_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE steps SET status=? WHERE id=?", (status, step_id))

    def create_loop(
        self,
        session_id: str,
        prompt: str,
        *,
        interval_seconds: float,
        max_iterations: int,
        loop_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        loop_id = loop_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO loops (id, session_id, prompt, interval_seconds, max_iterations, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    loop_id,
                    session_id,
                    prompt,
                    interval_seconds,
                    max_iterations,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        return loop_id

    def get_loop(self, loop_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM loops WHERE id=?", (loop_id,)).fetchone()
        return self._row_to_loop(row) if row else None

    def list_loops(self, session_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM loops"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id=?"
            params.append(session_id)
        query += " ORDER BY created_at, id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_loop(row) for row in rows]

    def update_loop_status(self, loop_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE loops SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, loop_id),
            )

    def record_loop_tick(self, loop_id: str, *, failed: bool = False) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE loops
                SET iterations=iterations+1,
                    consecutive_failures=?,
                    last_run_at=datetime('now'),
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (0 if not failed else self._next_loop_failure_count(conn, loop_id), loop_id),
            )

    def create_schedule(
        self,
        *,
        loop_id: str,
        expression: str,
        next_run_at: str,
        schedule_id: str | None = None,
    ) -> str:
        schedule_id = schedule_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO schedules (id, loop_id, expression, next_run_at)
                VALUES (?, ?, ?, ?)
                """,
                (schedule_id, loop_id, expression, next_run_at),
            )
        return schedule_id

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        return dict(row) if row else None

    def list_schedules(self, loop_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM schedules"
        params: list[Any] = []
        if loop_id is not None:
            query += " WHERE loop_id=?"
            params.append(loop_id)
        query += " ORDER BY created_at, id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_schedule_next_run(self, schedule_id: str, next_run_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE schedules SET next_run_at=?, updated_at=datetime('now') WHERE id=?",
                (next_run_at, schedule_id),
            )

    def record_checkpoint(
        self,
        session_id: str,
        *,
        phase: str,
        status: str,
        task_contract_hash: str = "",
        prompt_stack_hash: str = "",
        metadata: dict[str, Any] | None = None,
        checkpoint_id: str | None = None,
    ) -> str:
        checkpoint_id = checkpoint_id or uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_checkpoints (
                    id, session_id, phase, status, task_contract_hash, prompt_stack_hash, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    session_id,
                    phase,
                    status,
                    task_contract_hash,
                    prompt_stack_hash,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.execute("UPDATE sessions SET updated_at=datetime('now') WHERE id=?", (session_id,))
        return checkpoint_id

    def list_checkpoints(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_checkpoints WHERE session_id=? ORDER BY rowid",
                (session_id,),
            ).fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    def latest_checkpoint(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM run_checkpoints WHERE session_id=? ORDER BY rowid DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> Step:
        return Step(
            id=row["id"],
            plan_id=row["plan_id"],
            order_index=row["order_index"],
            title=row["title"],
            action=row["action"],
            required_inputs=json.loads(row["required_inputs_json"]),
            expected_output=row["expected_output"],
            allowed_tools=json.loads(row["allowed_tools_json"]),
            verification_method=row["verification_method"],
            done_condition=row["done_condition"],
            status=row["status"],
            evidence_refs=json.loads(row["evidence_refs_json"]),
            artifact_refs=json.loads(row["artifact_refs_json"]),
            required_gates=json.loads(row["required_gates_json"]),
        )

    @staticmethod
    def _next_loop_failure_count(conn: sqlite3.Connection, loop_id: str) -> int:
        row = conn.execute("SELECT consecutive_failures FROM loops WHERE id=?", (loop_id,)).fetchone()
        return int(row["consecutive_failures"]) + 1 if row else 1

    @staticmethod
    def _row_to_loop(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    @staticmethod
    def _row_to_checkpoint(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data
