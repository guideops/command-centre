from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "command-centre.db"
_local = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = _open()
    return _local.conn


def _open() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    return conn


def new_conn() -> sqlite3.Connection:
    """Open a fresh connection (for background threads)."""
    conn = _open()
    return conn


def _migrate_add_column(conn: sqlite3.Connection, table: str, col: str, col_type: str) -> None:
    existing = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")


def init_db() -> None:
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                source TEXT DEFAULT 'ide',
                cwd TEXT,
                git_branch TEXT,
                model TEXT,
                started_at TEXT,
                ended_at TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_create_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                effective_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0,
                duration_ms INTEGER,
                error_count INTEGER DEFAULT 0,
                rate_limit_hit INTEGER DEFAULT 0,
                stop_reason TEXT,
                title TEXT,
                synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                date TEXT,
                model TEXT,
                source TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_create_tokens INTEGER DEFAULT 0,
                PRIMARY KEY (date, model, source)
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
                session_id TEXT,
                tool_use_id TEXT,
                tool_name TEXT,
                ts TEXT,
                duration_ms INTEGER,
                error INTEGER DEFAULT 0,
                PRIMARY KEY (session_id, tool_use_id)
            );
            CREATE INDEX IF NOT EXISTS idx_tool_calls_name_ts ON tool_calls (tool_name, ts);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls (session_id);

            CREATE TABLE IF NOT EXISTS otel_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                session_id TEXT,
                prompt_id TEXT,
                timestamp TEXT,
                model TEXT,
                tool_name TEXT,
                tool_success INTEGER,
                tool_duration_ms REAL,
                tool_error TEXT,
                cost_usd REAL,
                api_duration_ms REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER,
                cache_create_tokens INTEGER,
                speed TEXT,
                error_message TEXT,
                status_code INTEGER,
                attempt_count INTEGER,
                skill_name TEXT,
                skill_source TEXT,
                prompt_length INTEGER,
                decision TEXT,
                decision_source TEXT,
                request_id TEXT,
                tool_result_size_bytes INTEGER,
                mcp_server_scope TEXT,
                plugin_name TEXT,
                plugin_version TEXT,
                marketplace_name TEXT,
                install_trigger TEXT,
                mcp_server_name TEXT,
                mcp_tool_name TEXT,
                received_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_otel_event_name ON otel_events (event_name, received_at);
            CREATE INDEX IF NOT EXISTS idx_otel_session ON otel_events (session_id);

            CREATE TABLE IF NOT EXISTS otel_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT,
                metric_type TEXT,
                value REAL,
                session_id TEXT,
                model TEXT,
                timestamp TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_otel_metrics_name ON otel_metrics (metric_name, timestamp);

            CREATE TABLE IF NOT EXISTS ops_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 50,
                assigned_skill TEXT,
                model TEXT,
                execution_mode TEXT DEFAULT 'stream',
                scheduled_for TEXT,
                requires_approval INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'low',
                dry_run INTEGER DEFAULT 0,
                quadrant TEXT DEFAULT 'do',
                approved_at TEXT,
                session_id TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_ms INTEGER,
                cost_usd REAL,
                output_summary TEXT,
                error_message TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ops_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cron_expression TEXT,
                task_title TEXT,
                task_description TEXT,
                assigned_skill TEXT,
                enabled INTEGER DEFAULT 1,
                next_run_at TEXT,
                last_run_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ops_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                session_id TEXT,
                prompt TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                answered_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_dedup
                ON ops_decisions (session_id, prompt)
                WHERE session_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS ops_inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                session_id TEXT,
                direction TEXT DEFAULT 'agent_to_user',
                body TEXT,
                read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                detail TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_activities_type ON activities (event_type, created_at);

            CREATE TABLE IF NOT EXISTS live_session_state (
                session_id TEXT PRIMARY KEY,
                state TEXT,
                current_tool TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS mcp_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT,
                tools INTEGER,
                total_tokens INTEGER,
                error TEXT,
                measured_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mcp_schemas (
                server TEXT,
                tool TEXT,
                schema_json TEXT,
                tokens INTEGER,
                collected_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (server, tool)
            );

            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                environment TEXT,
                description TEXT,
                path TEXT,
                autonomy_level TEXT DEFAULT 'review',
                user_invocable INTEGER DEFAULT 0,
                script_count INTEGER DEFAULT 0,
                last_modified TEXT
            );

            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                event_key TEXT,
                sent_at TEXT DEFAULT (datetime('now')),
                chat_id TEXT,
                telegram_message_id INTEGER,
                snoozed_until TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_notif_dedup
                ON notification_log (event_type, event_key, chat_id);
        """)

    # Idempotent migrations for columns added after initial schema
    with conn:
        _migrate_add_column(conn, "sessions", "version", "TEXT")
        _migrate_add_column(conn, "otel_events", "hook_name", "TEXT")
        _migrate_add_column(conn, "ops_tasks", "pid", "INTEGER")
