#!/usr/bin/env python3
"""
Ops Playbook Action Tracker
============================
A CLI tool for managing recurring operational routines alongside an AI assistant.

Why SQLite?
-----------
SQLite is the right choice here because:
1. Zero setup: no database server to install or configure
2. Portable: the entire database is a single file you can copy or back up
3. Concurrent-safe for single-user CLI usage (no write contention)
4. Built into Python's standard library, so zero external dependencies

The "seed then customize" pattern:
----------------------------------
Rather than starting from a blank slate, the `seed` command populates a few
generic routines. Users can then modify, delete, or extend these to match
their actual workflows. This lowers the barrier to getting started and shows
the expected data shape by example.

The cli_prompt field:
---------------------
Each routine has a `cli_prompt` field containing a ready-to-paste prompt for
your AI assistant. This bridges the gap between "I have a recurring task" and
"my AI does it." You run `due`, see what needs attention, copy the prompt,
and paste it into Copilot CLI (or any LLM tool). The tracker handles schedule
tracking and history; the AI handles execution.
"""

import argparse
import json
import os
import sqlite3
import sys
import textwrap
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

# Store the database next to this script so it travels with the toolkit.
DB_PATH = Path(__file__).parent / "ops_playbook.db"

# Schema version lets us migrate gracefully if we change the schema later.
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Recurring ops routines.
-- Each row represents one thing you do on a schedule.
CREATE TABLE IF NOT EXISTS playbook_routines (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL,            -- daily, weekly, biweekly, monthly
    schedule_days TEXT,                  -- e.g. "Mon,Thu" for weekly routines
    times_per_day INTEGER DEFAULT 1,    -- how many times per day (daily only)
    agent_id TEXT,                       -- optional: which AI agent handles this
    cli_prompt TEXT,                     -- copy-paste prompt for Copilot CLI
    estimated_manual_minutes INTEGER DEFAULT 15,
    last_run_at TEXT,                    -- ISO timestamp of most recent run
    last_status TEXT,                    -- status of most recent run
    enabled INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- Execution history.
-- Every time you run a routine, a row is created here. Completing the run
-- fills in completed_at, duration, and status.
CREATE TABLE IF NOT EXISTS playbook_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    routine_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',       -- running, success, failed, skipped
    duration_seconds INTEGER,
    manual_minutes INTEGER,              -- estimated manual effort saved
    summary TEXT,
    FOREIGN KEY (routine_id) REFERENCES playbook_routines(id)
);

-- Simple metadata table for schema versioning.
CREATE TABLE IF NOT EXISTS _meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    """Open (and optionally initialize) the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent-read perf
    conn.executescript(SCHEMA_SQL)
    # Track schema version for future migrations.
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Uses datetime.now(timezone.utc) instead of the deprecated
    datetime.utcnow(), which was removed in Python 3.14.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(iso_str: str) -> datetime:
    """Parse an ISO timestamp string into a timezone-aware datetime."""
    # Handle both with and without trailing Z
    cleaned = iso_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        # Fallback for unusual formats
        return datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )


def today_utc() -> datetime:
    """Return today's date at midnight UTC as a timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def day_abbr_today() -> str:
    """Return today's three-letter day abbreviation (Mon, Tue, etc.)."""
    return datetime.now(timezone.utc).strftime("%a")


def format_duration(seconds: int | None) -> str:
    """Format a duration in seconds into a human-readable string."""
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining = seconds % 60
    if remaining == 0:
        return f"{minutes}m"
    return f"{minutes}m {remaining}s"


def format_timestamp(iso_str: str | None) -> str:
    """Format an ISO timestamp for display."""
    if not iso_str:
        return "never"
    try:
        dt = parse_utc(iso_str)
        today = today_utc()
        if dt >= today:
            return f"Today {dt.strftime('%H:%M')}"
        elif dt >= today - timedelta(days=1):
            return f"Yesterday {dt.strftime('%H:%M')}"
        elif dt >= today - timedelta(days=6):
            return dt.strftime("%a %H:%M")
        else:
            return dt.strftime("%b %d %H:%M")
    except (ValueError, TypeError):
        return iso_str[:16] if iso_str else "never"


# ---------------------------------------------------------------------------
# Box-drawing table renderer
# ---------------------------------------------------------------------------

def render_table(headers: list[str], rows: list[list[str]], title: str = "") -> str:
    """Render a table with box-drawing characters.

    This gives us nice CLI output without pulling in a third-party library
    like tabulate or rich. We calculate column widths from the data, then
    draw the box around it.
    """
    if not rows and not headers:
        return ""

    # Calculate column widths (max of header and all row values).
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
            else:
                col_widths.append(len(str(cell)))

    # Add padding.
    col_widths = [w + 2 for w in col_widths]

    def make_line(left: str, mid: str, right: str, fill: str = "\u2500") -> str:
        return left + mid.join(fill * w for w in col_widths) + right

    def make_row(cells: list[str]) -> str:
        parts = []
        for i, cell in enumerate(cells):
            width = col_widths[i] - 2  # subtract padding
            parts.append(f" {str(cell):<{width}} ")
        return "\u2502" + "\u2502".join(parts) + "\u2502"

    lines = []
    if title:
        lines.append(f"\n  {title}")
    lines.append(make_line("\u250c", "\u252c", "\u2510"))
    lines.append(make_row(headers))
    lines.append(make_line("\u251c", "\u253c", "\u2524"))

    if rows:
        for row in rows:
            # Pad row to match header count if needed.
            padded = list(row) + [""] * (len(headers) - len(row))
            lines.append(make_row(padded))
    else:
        # Show an empty-state message.
        total_width = sum(col_widths) + len(col_widths) - 1
        msg = "(none)"
        lines.append(f"\u2502{msg:^{total_width}}\u2502")

    lines.append(make_line("\u2514", "\u2534", "\u2518"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Due-date logic
# ---------------------------------------------------------------------------
# The frequency/schedule pattern for recurring tasks:
#
# Each routine has a `frequency` (daily, weekly, biweekly, monthly) and an
# optional `schedule_days` (comma-separated day abbreviations like "Mon,Thu").
#
# The "due" check compares the routine's schedule against its last_run_at
# timestamp to decide if it needs to run again. This keeps the logic simple
# and stateless: we never need a separate "next_run_at" field that could
# drift out of sync.

def is_due(routine: sqlite3.Row, conn: sqlite3.Connection) -> bool:
    """Determine whether a routine is due to run now.

    Due logic by frequency:
    - daily: due if not run enough times today (respects times_per_day)
    - weekly: due if today matches schedule_days and not run today
    - biweekly: due if today matches schedule_days and not run in 14 days
    - monthly: due if not run this calendar month
    """
    if not routine["enabled"]:
        return False

    frequency = routine["frequency"]
    last_run_str = routine["last_run_at"]
    schedule_days = routine["schedule_days"] or ""
    times_per_day = routine["times_per_day"] or 1
    today = today_utc()
    today_abbr = day_abbr_today()

    if frequency == "daily":
        # Count how many times this routine has run today.
        count = conn.execute(
            """SELECT COUNT(*) FROM playbook_runs
               WHERE routine_id = ? AND started_at >= ?""",
            (routine["id"], today.strftime("%Y-%m-%dT00:00:00Z")),
        ).fetchone()[0]
        return count < times_per_day

    elif frequency == "weekly":
        # Only due on scheduled days, and only if not already run today.
        if schedule_days and today_abbr not in schedule_days.split(","):
            return False
        if not last_run_str:
            return True
        last_run = parse_utc(last_run_str)
        return last_run < today

    elif frequency == "biweekly":
        # Same day-of-week check as weekly, but with a 14-day lookback.
        if schedule_days and today_abbr not in schedule_days.split(","):
            return False
        if not last_run_str:
            return True
        last_run = parse_utc(last_run_str)
        return last_run < today - timedelta(days=13)

    elif frequency == "monthly":
        # Due if no run exists in the current calendar month.
        if not last_run_str:
            return True
        last_run = parse_utc(last_run_str)
        return (last_run.year, last_run.month) < (today.year, today.month)

    # Unknown frequency: treat as not due.
    return False


# ---------------------------------------------------------------------------
# Status emoji
# ---------------------------------------------------------------------------

STATUS_EMOJI = {
    "success": "\u2705",   # green check
    "failed": "\u274c",    # red X
    "running": "\u23f3",   # hourglass
    "skipped": "\u23ed\ufe0f",   # skip
    None: "\u2b1c",        # white square (never run)
}


def status_icon(status: str | None) -> str:
    return STATUS_EMOJI.get(status, "\u2b1c")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_playbook(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """List all routines with their current status."""
    routines = conn.execute(
        "SELECT * FROM playbook_routines ORDER BY enabled DESC, frequency, title"
    ).fetchall()

    if not routines:
        print("\n  No routines found. Run `seed` to add example routines.")
        return

    headers = ["", "ID", "Title", "Frequency", "Last Run", "Status"]
    rows = []
    enabled_count = 0
    due_count = 0

    for r in routines:
        icon = status_icon(r["last_status"])
        if not r["enabled"]:
            icon = "\u23f8\ufe0f"  # paused
        else:
            enabled_count += 1
            if is_due(r, conn):
                due_count += 1

        rows.append([
            icon,
            r["id"],
            r["title"],
            r["frequency"],
            format_timestamp(r["last_run_at"]),
            r["last_status"] or "never run",
        ])

    print(render_table(headers, rows, "Ops Playbook - All Routines"))
    print(f"\n  {len(routines)} routines, {enabled_count} enabled, {due_count} due now\n")


def cmd_due(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """Show routines that are due to run now."""
    routines = conn.execute(
        "SELECT * FROM playbook_routines WHERE enabled = 1 ORDER BY frequency, title"
    ).fetchall()

    due_routines = [r for r in routines if is_due(r, conn)]

    if not due_routines:
        print("\n  \u2705 Nothing due right now. All caught up!\n")
        return

    headers = ["ID", "Title", "Frequency", "Last Run"]
    rows = []
    for r in due_routines:
        rows.append([
            r["id"],
            r["title"],
            r["frequency"],
            format_timestamp(r["last_run_at"]),
        ])

    print(render_table(headers, rows, "Due Routines"))

    # Show the CLI prompt for the first due routine as a convenience.
    first = due_routines[0]
    if first["cli_prompt"]:
        print(f"\n  CLI Prompt for \"{first['id']}\":")
        for line in textwrap.wrap(first["cli_prompt"], width=72):
            print(f"    {line}")
    print()


def cmd_run(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Start a new run for a routine. Returns the run ID."""
    routine_id = args.routine_id

    routine = conn.execute(
        "SELECT * FROM playbook_routines WHERE id = ?", (routine_id,)
    ).fetchone()

    if not routine:
        print(f"\n  Error: routine \"{routine_id}\" not found.")
        print("  Run `playbook` to see available routines.\n")
        sys.exit(1)

    started = now_utc()

    cursor = conn.execute(
        """INSERT INTO playbook_runs (routine_id, started_at, status, manual_minutes)
           VALUES (?, ?, 'running', ?)""",
        (routine_id, started, routine["estimated_manual_minutes"]),
    )
    run_id = cursor.lastrowid

    # Update the routine's last_run_at so due-checks reflect this run.
    conn.execute(
        "UPDATE playbook_routines SET last_run_at = ?, updated_at = ? WHERE id = ?",
        (started, started, routine_id),
    )
    conn.commit()

    print(f"\n  \u23f3 Started run #{run_id} for \"{routine['title']}\"")

    if routine["cli_prompt"]:
        print(f"\n  CLI Prompt (paste into Copilot CLI):")
        for line in textwrap.wrap(routine["cli_prompt"], width=72):
            print(f"    {line}")

    print(f"\n  When done: python action_tracker.py complete {run_id} --status success --summary \"...\"\n")


def cmd_complete(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Complete a run with status and optional summary."""
    run_id = args.run_id
    status = args.status or "success"
    summary = args.summary

    run = conn.execute(
        "SELECT * FROM playbook_runs WHERE id = ?", (run_id,)
    ).fetchone()

    if not run:
        print(f"\n  Error: run #{run_id} not found.\n")
        sys.exit(1)

    if run["status"] != "running":
        print(f"\n  Run #{run_id} is already marked as \"{run['status']}\".\n")
        return

    completed = now_utc()
    started_dt = parse_utc(run["started_at"])
    completed_dt = parse_utc(completed)
    duration = int((completed_dt - started_dt).total_seconds())

    conn.execute(
        """UPDATE playbook_runs
           SET completed_at = ?, status = ?, duration_seconds = ?, summary = ?
           WHERE id = ?""",
        (completed, status, duration, summary, run_id),
    )

    # Update routine's last status.
    conn.execute(
        "UPDATE playbook_routines SET last_status = ?, updated_at = ? WHERE id = ?",
        (status, completed, run["routine_id"]),
    )
    conn.commit()

    icon = status_icon(status)
    manual = run["manual_minutes"] or 0
    print(f"\n  {icon} Completed run #{run_id} in {format_duration(duration)}", end="")
    if manual:
        print(f" (estimated manual: {manual} min)", end="")
    print()

    if summary:
        print(f"  Summary: {summary}")
    print()


def cmd_history(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Show run history, optionally filtered by routine and date range."""
    days = args.days or 7
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT00:00:00Z"
    )

    query = """
        SELECT r.id, r.routine_id, r.started_at, r.duration_seconds,
               r.status, r.summary
        FROM playbook_runs r
        WHERE r.started_at >= ?
    """
    params: list = [cutoff]

    if args.routine:
        query += " AND r.routine_id = ?"
        params.append(args.routine)

    query += " ORDER BY r.started_at DESC"

    runs = conn.execute(query, params).fetchall()

    if not runs:
        label = f" for \"{args.routine}\"" if args.routine else ""
        print(f"\n  No runs found in the last {days} day(s){label}.\n")
        return

    headers = ["#", "Routine", "Started", "Duration", "Status", "Summary"]
    rows = []
    for r in runs:
        summary_display = (r["summary"] or "")[:30]
        rows.append([
            str(r["id"]),
            r["routine_id"],
            format_timestamp(r["started_at"]),
            format_duration(r["duration_seconds"]),
            f"{status_icon(r['status'])} {r['status']}",
            summary_display,
        ])

    title = f"Run History (last {days} day{'s' if days != 1 else ''})"
    if args.routine:
        title += f" - {args.routine}"
    print(render_table(headers, rows, title))
    print()


def cmd_add(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """Interactive routine creation.

    Walks the user through creating a new routine step by step.
    """
    print("\n  Add a New Routine")
    print("  " + "-" * 30)

    try:
        rid = input("  ID (short, lowercase, e.g. 'inbox-review'): ").strip()
        if not rid:
            print("  Cancelled: ID is required.\n")
            return

        # Check for duplicates.
        existing = conn.execute(
            "SELECT id FROM playbook_routines WHERE id = ?", (rid,)
        ).fetchone()
        if existing:
            print(f"  Error: routine \"{rid}\" already exists.\n")
            return

        title = input("  Title: ").strip() or rid
        description = input("  Description (optional): ").strip() or None

        print("  Frequency options: daily, weekly, biweekly, monthly")
        frequency = input("  Frequency: ").strip().lower()
        if frequency not in ("daily", "weekly", "biweekly", "monthly"):
            print(f"  Error: unknown frequency \"{frequency}\".\n")
            return

        schedule_days = None
        times_per_day = 1
        if frequency == "daily":
            tpd = input("  Times per day [1]: ").strip()
            times_per_day = int(tpd) if tpd else 1
        elif frequency in ("weekly", "biweekly"):
            schedule_days = input("  Schedule days (e.g. Mon,Wed,Fri): ").strip() or None

        cli_prompt = input("  CLI prompt (paste into Copilot CLI): ").strip() or None

        est = input("  Estimated manual minutes [15]: ").strip()
        estimated_minutes = int(est) if est else 15

        now = now_utc()
        conn.execute(
            """INSERT INTO playbook_routines
               (id, title, description, frequency, schedule_days, times_per_day,
                cli_prompt, estimated_manual_minutes, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (rid, title, description, frequency, schedule_days, times_per_day,
             cli_prompt, estimated_minutes, now, now),
        )
        conn.commit()

        print(f"\n  \u2705 Created routine \"{rid}\"")
        print(f"  Run it with: python action_tracker.py run {rid}\n")

    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled.\n")


def cmd_seed(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """Seed example routines into the database.

    The "seed then customize" pattern:
    These generic examples show the expected data shape and give users a
    working starting point. They can modify, delete, or extend these to
    match their real workflows. Seeding is idempotent: existing routines
    with the same ID are skipped, not overwritten.
    """
    seeds = [
        {
            "id": "inbox-review",
            "title": "Daily Inbox Triage",
            "description": "Review and triage inbox, flag urgent items, draft quick replies.",
            "frequency": "daily",
            "schedule_days": None,
            "times_per_day": 1,
            "cli_prompt": (
                "Review and triage my inbox. Flag anything urgent, "
                "summarize key threads, and draft quick replies for "
                "routine messages."
            ),
            "estimated_manual_minutes": 15,
        },
        {
            "id": "weekly-status",
            "title": "Weekly Status Report",
            "description": "Generate a weekly status report from recent work.",
            "frequency": "weekly",
            "schedule_days": "Mon",
            "times_per_day": 1,
            "cli_prompt": (
                "Generate my weekly status report. Summarize what I "
                "worked on, key decisions made, blockers encountered, "
                "and priorities for next week."
            ),
            "estimated_manual_minutes": 20,
        },
        {
            "id": "meeting-prep",
            "title": "Meeting Prep",
            "description": "Prepare for upcoming meetings with agenda review and action items.",
            "frequency": "weekly",
            "schedule_days": "Mon,Wed",
            "times_per_day": 1,
            "cli_prompt": (
                "Review my upcoming meetings for today. For each one, "
                "pull relevant context, prepare talking points, and "
                "list any open action items I should address."
            ),
            "estimated_manual_minutes": 10,
        },
    ]

    now = now_utc()
    added = 0
    skipped = 0

    for seed in seeds:
        existing = conn.execute(
            "SELECT id FROM playbook_routines WHERE id = ?", (seed["id"],)
        ).fetchone()

        if existing:
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO playbook_routines
               (id, title, description, frequency, schedule_days, times_per_day,
                cli_prompt, estimated_manual_minutes, enabled, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                seed["id"], seed["title"], seed["description"],
                seed["frequency"], seed["schedule_days"], seed["times_per_day"],
                seed["cli_prompt"], seed["estimated_manual_minutes"],
                now, now,
            ),
        )
        added += 1

    conn.commit()

    print(f"\n  Seeded {added} routine(s), skipped {skipped} (already exist).")
    if added > 0:
        print("  Run `python action_tracker.py playbook` to see them.")
    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Each subcommand maps to a cmd_* function above. This keeps the CLI
    surface clean and makes it easy to add new commands later.
    """
    parser = argparse.ArgumentParser(
        prog="action_tracker",
        description="Ops Playbook Action Tracker: manage recurring routines.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # playbook
    subparsers.add_parser("playbook", help="List all routines with status")

    # due
    subparsers.add_parser("due", help="Show routines due now")

    # run
    run_parser = subparsers.add_parser("run", help="Start a run for a routine")
    run_parser.add_argument("routine_id", help="ID of the routine to run")

    # complete
    complete_parser = subparsers.add_parser("complete", help="Complete a run")
    complete_parser.add_argument("run_id", type=int, help="Run ID to complete")
    complete_parser.add_argument(
        "--status",
        choices=["success", "failed", "skipped"],
        default="success",
        help="Run outcome (default: success)",
    )
    complete_parser.add_argument(
        "--summary", type=str, default=None, help="Free-text summary of the run"
    )

    # history
    history_parser = subparsers.add_parser("history", help="Show run history")
    history_parser.add_argument(
        "--routine", type=str, default=None, help="Filter to a specific routine ID"
    )
    history_parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back (default: 7)"
    )

    # add
    subparsers.add_parser("add", help="Interactive routine creation")

    # seed
    subparsers.add_parser("seed", help="Seed example routines")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Command dispatch table. Maps subcommand names to handler functions.
COMMANDS = {
    "playbook": cmd_playbook,
    "due": cmd_due,
    "run": cmd_run,
    "complete": cmd_complete,
    "history": cmd_history,
    "add": cmd_add,
    "seed": cmd_seed,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    conn = get_connection()
    try:
        handler = COMMANDS.get(args.command)
        if handler:
            handler(conn, args)
        else:
            parser.print_help()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
