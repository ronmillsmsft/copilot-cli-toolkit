#!/usr/bin/env python3
"""
Meeting Prep Pipeline
=====================

A structured workflow for recurring meeting preparation.

PATTERN: Skeleton + AI Enrichment
---------------------------------
This script produces *deterministic structure* (meeting configs, tracked topics,
prep templates) as JSON output. An AI assistant (like Copilot CLI) then takes
that skeleton and enriches it with *live context* -- pulling from the data
sources listed in the config, summarizing recent activity, and filling in
the prep template with real information.

The split is intentional:
  - Structured data lives here (reliable, version-controlled, queryable)
  - Intelligence lives in the AI layer (flexible, context-aware, up-to-date)

WHY TOPIC TRACKING?
-------------------
Discussion topics often span multiple meetings. A topic raised on Monday
might not get resolved until the following week. By tracking topics in a
database (not a sticky note), we carry context across meetings automatically.
The AI layer can see what was deferred last time and prioritize accordingly.

WHY PREP HISTORY?
-----------------
Recording when prep was generated enables retrospectives: "We prepped for
this meeting 12 times in Q3 -- did the format actually help?" It also lets
the AI layer reference past preps to identify recurring themes.

DEPENDENCIES: None beyond Python stdlib. Uses SQLite via the built-in
sqlite3 module. Designed to be copy-paste shareable.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

# Store the database next to this script so it travels with the project.
DB_PATH = Path(__file__).parent / "meeting_prep.db"


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating tables if needed."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # safer for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row  # access columns by name
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist.

    The schema is intentionally simple. Meeting configs are rows, not files,
    so they are queryable alongside topics and history.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY,           -- slug: weekly-standup, project-review
            name TEXT NOT NULL,
            cadence TEXT NOT NULL,          -- weekly, biweekly, monthly
            day_of_week TEXT,              -- Monday, Tuesday, etc.
            time TEXT,                     -- 10:00 AM
            stakeholder TEXT,              -- primary stakeholder
            attendees TEXT,                -- JSON array of names
            purpose TEXT,
            data_sources TEXT,             -- JSON array: ["ADO queries", "email threads"]
            prep_template TEXT,            -- markdown template for prep
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS meeting_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            status TEXT DEFAULT 'active',   -- active, discussed, deferred, dropped
            added_at TEXT NOT NULL,
            discussed_at TEXT,
            notes TEXT,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        );

        CREATE TABLE IF NOT EXISTS prep_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT NOT NULL,
            prep_date TEXT NOT NULL,
            output_path TEXT,
            generated_at TEXT,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string.

    Uses datetime.now(timezone.utc) instead of the deprecated
    datetime.utcnow(), which is removed in Python 3.14.
    """
    return datetime.now(timezone.utc).isoformat()


def _parse_json_field(value: str | None) -> list:
    """Safely parse a JSON array field, returning an empty list on failure."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _get_meeting_or_exit(conn: sqlite3.Connection, meeting_id: str) -> sqlite3.Row:
    """Fetch a meeting by ID, or exit with a helpful error."""
    row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if row is None:
        print(f"Error: No meeting found with id '{meeting_id}'.")
        print("Run 'python meeting_prep.py list' to see configured meetings.")
        sys.exit(1)
    return row


# ---------------------------------------------------------------------------
# Day-of-week mapping for the 'upcoming' command
# ---------------------------------------------------------------------------

# Python's weekday(): Monday=0 ... Sunday=6
_DAY_NAME_TO_INT = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def _next_occurrence(day_name: str, cadence: str, from_date: datetime) -> list[datetime]:
    """Return upcoming occurrences of a meeting within a window.

    For 'weekly' meetings, returns every matching weekday.
    For 'biweekly', returns the next matching weekday (simplified --
    a real system would track the actual biweekly anchor date).
    For 'monthly', returns the next matching weekday in the month.
    """
    target_weekday = _DAY_NAME_TO_INT.get(day_name)
    if target_weekday is None:
        return []

    # Handle meetings that occur on multiple days (e.g., "Monday/Thursday")
    day_parts = [d.strip() for d in day_name.split("/")]
    target_weekdays = []
    for part in day_parts:
        wd = _DAY_NAME_TO_INT.get(part)
        if wd is not None:
            target_weekdays.append(wd)

    if not target_weekdays:
        return []

    occurrences = []
    for wd in target_weekdays:
        # Calculate days until next occurrence of this weekday
        days_ahead = (wd - from_date.weekday()) % 7
        if days_ahead == 0:
            occurrences.append(from_date)
        next_date = from_date + timedelta(days=days_ahead if days_ahead > 0 else 0)
        if next_date not in occurrences:
            occurrences.append(next_date)

    return sorted(occurrences)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """List all configured meetings."""
    rows = conn.execute(
        "SELECT id, name, cadence, day_of_week, time, purpose FROM meetings ORDER BY name"
    ).fetchall()

    if not rows:
        print("No meetings configured. Run 'python meeting_prep.py seed' to add examples.")
        return

    print(f"{'ID':<20} {'Name':<25} {'Cadence':<10} {'Day':<15} {'Time':<10}")
    print("-" * 80)
    for r in rows:
        print(f"{r['id']:<20} {r['name']:<25} {r['cadence']:<10} {r['day_of_week'] or '':<15} {r['time'] or '':<10}")
        if r["purpose"]:
            print(f"  {'Purpose:':<18} {r['purpose']}")


def cmd_prep(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Generate a prep skeleton as JSON.

    JSON OUTPUT PATTERN
    -------------------
    The output is a self-contained JSON object with everything an AI assistant
    needs to produce a meeting prep document:

      - meeting metadata (name, stakeholder, attendees)
      - active discussion topics (carried from previous meetings)
      - data source hints (where to pull live context from)
      - a markdown template (the desired output structure)

    The AI layer reads this JSON and fills in the template using the data
    sources as guidance. The human reviews and edits the result.
    """
    meeting = _get_meeting_or_exit(conn, args.meeting_id)

    # Fetch active topics for this meeting
    topics = conn.execute(
        "SELECT topic, added_at FROM meeting_topics WHERE meeting_id = ? AND status = 'active' ORDER BY added_at",
        (args.meeting_id,),
    ).fetchall()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build the skeleton that an AI assistant will enrich
    skeleton = {
        "meeting": meeting["name"],
        "date": today,
        "stakeholder": meeting["stakeholder"] or "",
        "attendees": _parse_json_field(meeting["attendees"]),
        "purpose": meeting["purpose"] or "",
        "active_topics": [
            {"topic": t["topic"], "added": t["added_at"][:10]} for t in topics
        ],
        "data_sources": _parse_json_field(meeting["data_sources"]),
        "template": meeting["prep_template"] or "",
    }

    print(json.dumps(skeleton, indent=2))

    # Record this prep generation in history so we can track usage patterns
    conn.execute(
        "INSERT INTO prep_history (meeting_id, prep_date, generated_at) VALUES (?, ?, ?)",
        (args.meeting_id, today, _now_iso()),
    )
    conn.commit()


def cmd_topic_add(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Add a discussion topic to a meeting.

    Topics persist across meetings until explicitly marked as discussed.
    This prevents items from falling through the cracks between recurring
    meetings -- a common problem when prep is done ad-hoc.
    """
    _get_meeting_or_exit(conn, args.meeting_id)

    now = _now_iso()
    conn.execute(
        "INSERT INTO meeting_topics (meeting_id, topic, status, added_at) VALUES (?, ?, 'active', ?)",
        (args.meeting_id, args.topic_text, now),
    )
    conn.commit()
    print(f"Topic added to '{args.meeting_id}': {args.topic_text}")


def cmd_topic_list(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """List active topics for a meeting."""
    _get_meeting_or_exit(conn, args.meeting_id)

    rows = conn.execute(
        "SELECT id, topic, status, added_at FROM meeting_topics WHERE meeting_id = ? AND status = 'active' ORDER BY added_at",
        (args.meeting_id,),
    ).fetchall()

    if not rows:
        print(f"No active topics for '{args.meeting_id}'.")
        return

    print(f"Active topics for '{args.meeting_id}':")
    print(f"  {'ID':<6} {'Added':<12} {'Topic'}")
    print("  " + "-" * 60)
    for r in rows:
        added_short = r["added_at"][:10] if r["added_at"] else ""
        print(f"  {r['id']:<6} {added_short:<12} {r['topic']}")


def cmd_topic_done(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Mark a topic as discussed.

    We record when it was discussed rather than deleting it, so the
    history remains available for retrospectives and pattern analysis.
    """
    now = _now_iso()
    result = conn.execute(
        "UPDATE meeting_topics SET status = 'discussed', discussed_at = ? WHERE id = ? AND status = 'active'",
        (now, args.topic_id),
    )
    conn.commit()

    if result.rowcount == 0:
        # Check if the topic exists at all
        row = conn.execute("SELECT status FROM meeting_topics WHERE id = ?", (args.topic_id,)).fetchone()
        if row is None:
            print(f"Error: No topic found with id {args.topic_id}.")
        else:
            print(f"Topic {args.topic_id} is already '{row['status']}'.")
    else:
        print(f"Topic {args.topic_id} marked as discussed.")


def cmd_upcoming(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Show meetings occurring in the next N days."""
    days = args.days
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today + timedelta(days=days)

    rows = conn.execute(
        "SELECT id, name, cadence, day_of_week, time FROM meetings WHERE day_of_week IS NOT NULL ORDER BY name"
    ).fetchall()

    if not rows:
        print("No meetings configured. Run 'python meeting_prep.py seed' to add examples.")
        return

    upcoming = []
    for r in rows:
        day_parts = [d.strip() for d in (r["day_of_week"] or "").split("/")]
        for day_name in day_parts:
            target_wd = _DAY_NAME_TO_INT.get(day_name)
            if target_wd is None:
                continue
            # Find all occurrences of this weekday in the window
            days_ahead = (target_wd - today.weekday()) % 7
            occurrence = today + timedelta(days=days_ahead)
            while occurrence <= end_date:
                upcoming.append({
                    "date": occurrence.strftime("%Y-%m-%d (%A)"),
                    "sort_key": occurrence,
                    "name": r["name"],
                    "id": r["id"],
                    "time": r["time"] or "",
                })
                # For biweekly, skip every other week; for monthly, skip to next month
                if r["cadence"] == "weekly":
                    occurrence += timedelta(weeks=1)
                elif r["cadence"] == "biweekly":
                    occurrence += timedelta(weeks=2)
                else:
                    break  # monthly or unknown: just show the next one

    if not upcoming:
        print(f"No meetings scheduled in the next {days} day(s).")
        return

    upcoming.sort(key=lambda x: x["sort_key"])

    print(f"Meetings in the next {days} day(s):")
    print(f"  {'Date':<22} {'Time':<10} {'Meeting':<25} {'ID'}")
    print("  " + "-" * 70)
    for u in upcoming:
        print(f"  {u['date']:<22} {u['time']:<10} {u['name']:<25} {u['id']}")


def cmd_history(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    """Show prep generation history for a meeting.

    This history enables retrospectives: How often do we prep? Are we
    actually using the process? Did we skip a week?
    """
    _get_meeting_or_exit(conn, args.meeting_id)

    rows = conn.execute(
        "SELECT id, prep_date, generated_at FROM prep_history WHERE meeting_id = ? ORDER BY generated_at DESC LIMIT 20",
        (args.meeting_id,),
    ).fetchall()

    if not rows:
        print(f"No prep history for '{args.meeting_id}'.")
        return

    print(f"Prep history for '{args.meeting_id}' (most recent first):")
    print(f"  {'ID':<6} {'Prep Date':<12} {'Generated At'}")
    print("  " + "-" * 50)
    for r in rows:
        gen_at = r["generated_at"][:19] if r["generated_at"] else ""
        print(f"  {r['id']:<6} {r['prep_date']:<12} {gen_at}")


def cmd_seed(conn: sqlite3.Connection, _args: argparse.Namespace) -> None:
    """Seed the database with example meeting configurations.

    These examples are generic and meant for teaching. Replace them with
    your real meetings. The key fields to customize:

      - data_sources: Where does context for this meeting come from?
      - prep_template: What does the ideal prep document look like?
      - attendees: Who is in the room?
    """
    now = _now_iso()

    seed_meetings = [
        {
            "id": "team-standup",
            "name": "Team Standup",
            "cadence": "weekly",
            "day_of_week": "Monday/Thursday",
            "time": "9:30 AM",
            "stakeholder": "Team Lead",
            "attendees": json.dumps(["Alice", "Bob", "Carol", "Dave"]),
            "purpose": "Quick sync on blockers and priorities",
            "data_sources": json.dumps(["Jira sprint board", "Slack #team-updates"]),
            "prep_template": "## Blockers\n\n## Progress Since Last Standup\n\n## Priorities for Today\n\n## Action Items",
            "notes": "Keep it under 15 minutes. Focus on blockers first.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "project-review",
            "name": "Project Review",
            "cadence": "biweekly",
            "day_of_week": "Wednesday",
            "time": "2:00 PM",
            "stakeholder": "Program Manager",
            "attendees": json.dumps(["PM", "Tech Lead", "QA Lead", "Designer"]),
            "purpose": "Review project milestones and risks",
            "data_sources": json.dumps(["ADO work items", "risk register", "milestone tracker"]),
            "prep_template": "## Milestone Status\n\n## Risks and Mitigations\n\n## Decisions Needed\n\n## Timeline Updates\n\n## Action Items",
            "notes": "Bring updated burndown chart. Flag any scope changes early.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "1on1-manager",
            "name": "1:1 with Manager",
            "cadence": "weekly",
            "day_of_week": "Friday",
            "time": "3:00 PM",
            "stakeholder": "Manager",
            "attendees": json.dumps(["You", "Manager"]),
            "purpose": "Career growth, blockers, feedback",
            "data_sources": json.dumps(["personal notes", "goal tracker", "recent feedback"]),
            "prep_template": "## Wins This Week\n\n## Blockers or Concerns\n\n## Career Growth Topics\n\n## Feedback (Give and Receive)\n\n## Action Items",
            "notes": "This is your meeting. Come with an agenda.",
            "created_at": now,
            "updated_at": now,
        },
    ]

    inserted = 0
    skipped = 0
    for m in seed_meetings:
        existing = conn.execute("SELECT id FROM meetings WHERE id = ?", (m["id"],)).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO meetings (id, name, cadence, day_of_week, time, stakeholder,
               attendees, purpose, data_sources, prep_template, notes, created_at, updated_at)
               VALUES (:id, :name, :cadence, :day_of_week, :time, :stakeholder,
               :attendees, :purpose, :data_sources, :prep_template, :notes, :created_at, :updated_at)""",
            m,
        )
        inserted += 1

    conn.commit()
    print(f"Seeded {inserted} meeting(s). Skipped {skipped} (already exist).")
    if inserted > 0:
        print("Run 'python meeting_prep.py list' to see them.")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Meeting Prep Pipeline - structured meeting configs + topic tracking + prep generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python meeting_prep.py seed                         Seed example meetings\n"
            "  python meeting_prep.py list                         List all meetings\n"
            "  python meeting_prep.py prep team-standup             Generate prep skeleton\n"
            "  python meeting_prep.py topic add team-standup 'Bug triage process'\n"
            "  python meeting_prep.py topic list team-standup       Show active topics\n"
            "  python meeting_prep.py topic done 3                  Mark topic #3 discussed\n"
            "  python meeting_prep.py upcoming --days 14            Meetings in next 14 days\n"
            "  python meeting_prep.py history project-review        Show prep history\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    subparsers.add_parser("list", help="List configured meetings")

    # prep
    prep_parser = subparsers.add_parser("prep", help="Generate prep skeleton (JSON output)")
    prep_parser.add_argument("meeting_id", help="Meeting ID (slug)")

    # topic (with sub-subcommands)
    topic_parser = subparsers.add_parser("topic", help="Manage discussion topics")
    topic_sub = topic_parser.add_subparsers(dest="topic_command", help="Topic subcommands")

    topic_add = topic_sub.add_parser("add", help="Add a discussion topic")
    topic_add.add_argument("meeting_id", help="Meeting ID (slug)")
    topic_add.add_argument("topic_text", help="Topic description")

    topic_list = topic_sub.add_parser("list", help="List active topics")
    topic_list.add_argument("meeting_id", help="Meeting ID (slug)")

    topic_done = topic_sub.add_parser("done", help="Mark a topic as discussed")
    topic_done.add_argument("topic_id", type=int, help="Topic ID number")

    # upcoming
    upcoming_parser = subparsers.add_parser("upcoming", help="Show meetings in next N days")
    upcoming_parser.add_argument("--days", type=int, default=7, help="Number of days to look ahead (default: 7)")

    # history
    history_parser = subparsers.add_parser("history", help="Show prep generation history")
    history_parser.add_argument("meeting_id", help="Meeting ID (slug)")

    # seed
    subparsers.add_parser("seed", help="Seed example meeting configurations")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    conn = get_connection()

    try:
        if args.command == "list":
            cmd_list(conn, args)
        elif args.command == "prep":
            cmd_prep(conn, args)
        elif args.command == "topic":
            if not hasattr(args, "topic_command") or not args.topic_command:
                print("Usage: python meeting_prep.py topic {add|list|done} ...")
                sys.exit(1)
            if args.topic_command == "add":
                cmd_topic_add(conn, args)
            elif args.topic_command == "list":
                cmd_topic_list(conn, args)
            elif args.topic_command == "done":
                cmd_topic_done(conn, args)
        elif args.command == "upcoming":
            cmd_upcoming(conn, args)
        elif args.command == "history":
            cmd_history(conn, args)
        elif args.command == "seed":
            cmd_seed(conn, args)
        else:
            parser.print_help()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
