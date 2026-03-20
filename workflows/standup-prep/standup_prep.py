"""
Standup Prep -- Surface what matters from your work tracking system.

This script follows the "cache locally, analyze locally" pattern:
  1. You export work items from your tracker (ADO, Jira, GitHub Issues, etc.)
  2. Import them into a local SQLite database
  3. Run analysis patterns against the cache

Why this pattern?
  - Scans are instant (no API calls at analysis time)
  - Works offline (airplane mode? no problem)
  - System-agnostic (any tracker that exports JSON works)
  - You control what data stays on your machine

Zero external dependencies -- Python stdlib + SQLite only.
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

# Store the database alongside this script so it travels with the toolkit.
DB_PATH = Path(__file__).parent / "standup_prep.db"

# States we consider "open" -- items in these states are still actionable.
OPEN_STATES = {"New", "Active", "In Progress"}

# How many days without a state change before we flag an item as stale.
# Five days catches items that survived a full work week with no movement.
STALE_THRESHOLD_DAYS = 5


def get_connection() -> sqlite3.Connection:
    """Return a connection to the local SQLite cache."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Create tables if they don't exist yet.

    The schema is intentionally flat -- one table for work items, one for scan
    history. This keeps the import/export path simple and makes it easy to
    adapt for different tracking systems.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS work_items (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            priority INTEGER DEFAULT 3,
            assigned_to TEXT,
            tags TEXT,
            created_date TEXT,
            changed_date TEXT,
            area_path TEXT,
            work_item_type TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            lookback_days INTEGER,
            total_items INTEGER,
            bring_up_count INTEGER,
            stale_count INTEGER,
            state_changes_count INTEGER
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    """
    Return the current UTC time as a timezone-aware datetime.

    We use datetime.now(timezone.utc) instead of datetime.utcnow() because
    utcnow() returns a naive datetime (no timezone info) and has been
    deprecated since Python 3.12 / removed in 3.14.
    """
    return datetime.now(timezone.utc)


def parse_date(date_str: str | None) -> datetime | None:
    """
    Parse an ISO 8601 date string into a timezone-aware datetime.

    Handles both 'Z' suffix and '+00:00' offset notation. Returns None
    if the input is None or unparseable -- we don't want a bad date in
    one item to crash the entire scan.
    """
    if not date_str:
        return None
    try:
        # Normalize the "Z" shorthand to an explicit UTC offset
        cleaned = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        return None


def days_since(date_str: str | None) -> int | None:
    """Return the number of days between a date string and now, or None."""
    dt = parse_date(date_str)
    if dt is None:
        return None
    delta = now_utc() - dt
    return delta.days


def priority_label(priority: int) -> str:
    """Map a numeric priority to a human-readable label."""
    labels = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
    return labels.get(priority, f"P{priority}")


# ---------------------------------------------------------------------------
# Analysis engine
# ---------------------------------------------------------------------------
# Each analysis function takes a list of work item rows and returns a filtered
# list. This keeps the logic testable and composable -- you can combine or
# replace patterns without touching the output formatting.
# ---------------------------------------------------------------------------

def find_bring_up_items(items: list[sqlite3.Row], lookback_days: int) -> list[dict]:
    """
    Find items worth bringing up in standup.

    The logic:
      - Any P1 (critical) item that is still open. These always deserve airtime.
      - Any P2 bug that was created within the lookback window. New high-priority
        bugs are the kind of thing the team should hear about early.

    Why these two rules? P1s are table-stakes. P2 bugs that are new represent
    emerging risk -- catching them early prevents them from becoming P1s.
    """
    results = []
    cutoff = now_utc() - timedelta(days=lookback_days)

    for item in items:
        state = item["state"]
        priority = item["priority"] or 3
        work_type = item["work_item_type"] or ""
        created = parse_date(item["created_date"])
        changed = parse_date(item["changed_date"])

        is_open = state in OPEN_STATES

        # Rule 1: P1 items that are still open
        if priority == 1 and is_open:
            stale_days = days_since(item["changed_date"])
            note = f"{stale_days} days stale" if stale_days and stale_days >= STALE_THRESHOLD_DAYS else "open"
            results.append({**dict(item), "_note": note})
            continue

        # Rule 2: P2 bugs created recently
        if priority == 2 and work_type.lower() == "bug" and created and created >= cutoff:
            results.append({**dict(item), "_note": "new bug"})

    return results


def find_stale_items(items: list[sqlite3.Row]) -> list[dict]:
    """
    Find items that have gone dark.

    Staleness detection matters because items that stop moving are often items
    where someone is blocked, confused, or has silently deprioritized the work.
    Surfacing these prevents the "oh, I forgot about that" moment two sprints
    later.

    An item is stale if:
      - It is in an open state (New, Active, In Progress)
      - Its last state change was more than STALE_THRESHOLD_DAYS ago
    """
    results = []
    for item in items:
        if item["state"] not in OPEN_STATES:
            continue
        stale_days = days_since(item["changed_date"])
        if stale_days is not None and stale_days >= STALE_THRESHOLD_DAYS:
            results.append({**dict(item), "_stale_days": stale_days})

    # Sort by staleness descending -- the oldest stale items are the scariest.
    results.sort(key=lambda x: x.get("_stale_days", 0), reverse=True)
    return results


def find_state_changes(items: list[sqlite3.Row], lookback_days: int) -> list[dict]:
    """
    Find items whose state changed within the lookback window.

    The lookback window concept: we only care about changes since the last
    standup (or whatever cadence you choose). A 4-day lookback covers
    "since last standup" for daily standups, even across a weekend.

    Note: We detect state changes by comparing changed_date to the lookback
    cutoff. For richer change tracking (e.g., "Active -> In Progress"), your
    import script can store the previous state in a convention field. The
    current schema tracks the latest state only.
    """
    results = []
    cutoff = now_utc() - timedelta(days=lookback_days)

    for item in items:
        changed = parse_date(item["changed_date"])
        if changed and changed >= cutoff:
            results.append(dict(item))

    # Most recent changes first
    results.sort(key=lambda x: x.get("changed_date", ""), reverse=True)
    return results


def compute_portfolio_pulse(items: list[sqlite3.Row]) -> dict[str, dict[str, int]]:
    """
    Group items by area_path (or tag) and count by state.

    Portfolio pulse gives you the "how much is on our plate" view. It answers
    questions like "how many active items does Backend have?" without opening
    your tracker.
    """
    groups: dict[str, dict[str, int]] = {}

    for item in items:
        # Use area_path as the primary grouping. Fall back to "Unassigned"
        # so nothing gets silently dropped.
        group = item["area_path"] or "Unassigned"
        if group not in groups:
            groups[group] = {"total": 0, "New": 0, "Active": 0, "In Progress": 0, "Done": 0, "Closed": 0}
        groups[group]["total"] += 1
        state = item["state"]
        if state in groups[group]:
            groups[group][state] += 1

    return groups


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_header(today_str: str) -> str:
    """Build the top banner for scan output."""
    title = f"  Standup Prep -- {today_str}"
    width = 50
    lines = [
        "+" + "=" * width + "+",
        "|" + title.ljust(width) + "|",
        "+" + "=" * width + "+",
    ]
    return "\n".join(lines)


def format_bring_up(items: list[dict]) -> str:
    """Format the bring-up section."""
    if not items:
        return "\nBRING UP: None -- looking clean.\n"
    lines = [f"\n!! BRING UP ({len(items)})"]
    for item in items:
        pid = priority_label(item.get("priority", 3))
        note = item.get("_note", "")
        note_str = f"  ({note})" if note else ""
        lines.append(f"  #{item['id']:<5} [{pid}] {item['title']:<35} {item['state']:<14}{note_str}")
    return "\n".join(lines) + "\n"


def format_stale(items: list[dict]) -> str:
    """Format the stale items section."""
    if not items:
        return "\nSTALE ITEMS: None -- everything is moving.\n"
    lines = [f"\n>> STALE ITEMS ({len(items)})"]
    for item in items:
        stale_days = item.get("_stale_days", "?")
        lines.append(f"  #{item['id']:<5} {item['title']:<40} {item['state']:<14} ({stale_days} days unchanged)")
    return "\n".join(lines) + "\n"


def format_state_changes(items: list[dict], lookback_days: int) -> str:
    """Format the state changes section."""
    if not items:
        return f"\nSTATE CHANGES (last {lookback_days} days): None.\n"
    lines = [f"\nSTATE CHANGES (last {lookback_days} days, {len(items)} items)"]
    for item in items:
        lines.append(f"  #{item['id']:<5} {item['title']:<40} {item['state']}")
    return "\n".join(lines) + "\n"


def format_pulse(groups: dict[str, dict[str, int]]) -> str:
    """Format the portfolio pulse section."""
    if not groups:
        return "\nPORTFOLIO PULSE: No items.\n"
    lines = ["\nPORTFOLIO PULSE"]
    # Sort groups by total item count descending
    for group, counts in sorted(groups.items(), key=lambda g: g[1]["total"], reverse=True):
        parts = []
        for state in ["New", "Active", "In Progress", "Done", "Closed"]:
            if counts.get(state, 0) > 0:
                parts.append(f"{counts[state]} {state}")
        summary = ", ".join(parts)
        lines.append(f"  {group + ':':<16} {counts['total']:>3} items  ({summary})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scan(args) -> None:
    """
    Run the full analysis pipeline against cached work items.

    This is the main command. It loads all items from the local SQLite cache,
    runs each analysis pattern, prints the results, and logs the scan to
    history so you can see trends over time.
    """
    conn = get_connection()
    ensure_schema(conn)

    lookback = args.lookback
    items = conn.execute("SELECT * FROM work_items").fetchall()

    if not items:
        print("No work items in the cache. Run 'seed' to create sample data or 'import' to load your own.")
        return

    # Run each analysis pattern
    bring_up = find_bring_up_items(items, lookback)
    stale = find_stale_items(items)
    changes = find_state_changes(items, lookback)
    pulse = compute_portfolio_pulse(items)

    # Format and print
    today_str = now_utc().strftime("%Y-%m-%d")
    print(format_header(today_str))
    print(format_bring_up(bring_up))
    print(format_stale(stale))
    print(format_state_changes(changes, lookback))
    print(format_pulse(pulse))

    # Log this scan to history for trend tracking
    conn.execute(
        """INSERT INTO scan_history (scanned_at, lookback_days, total_items,
           bring_up_count, stale_count, state_changes_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (now_utc().isoformat(), lookback, len(items),
         len(bring_up), len(stale), len(changes))
    )
    conn.commit()
    conn.close()


def cmd_import(args) -> None:
    """
    Import work items from a JSON file into the local cache.

    The JSON file should contain an array of objects. Each object maps to a row
    in the work_items table. Unknown fields are silently ignored, so you can
    export extra metadata from your tracker without breaking the import.

    Adapting for different systems:
      - ADO: Map System.Title -> title, System.State -> state, etc.
      - Jira: Map fields.summary -> title, fields.status.name -> state, etc.
      - GitHub Issues: Map title -> title, state -> state, labels -> tags, etc.
    The easiest approach is a small jq or Python script that reshapes your
    system's JSON into the format this tool expects, then pipe it to import.
    """
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("Expected a JSON array of work item objects.")
        sys.exit(1)

    conn = get_connection()
    ensure_schema(conn)

    # Valid columns in work_items table
    valid_fields = {
        "id", "title", "state", "priority", "assigned_to", "tags",
        "created_date", "changed_date", "area_path", "work_item_type"
    }

    inserted = 0
    updated = 0
    for record in data:
        if "id" not in record or "title" not in record or "state" not in record:
            print(f"  Skipping record (missing id, title, or state): {record}")
            continue

        # Filter to known fields only
        filtered = {k: v for k, v in record.items() if k in valid_fields}

        # Use INSERT OR REPLACE so re-imports update existing items
        columns = ", ".join(filtered.keys())
        placeholders = ", ".join(["?"] * len(filtered))
        values = list(filtered.values())

        # Check if this is an update or insert
        existing = conn.execute("SELECT 1 FROM work_items WHERE id = ?", (filtered["id"],)).fetchone()
        conn.execute(f"INSERT OR REPLACE INTO work_items ({columns}) VALUES ({placeholders})", values)

        if existing:
            updated += 1
        else:
            inserted += 1

    conn.commit()
    conn.close()
    print(f"Import complete: {inserted} new, {updated} updated, {inserted + updated} total.")


def cmd_seed(_args) -> None:
    """
    Seed the database with realistic example work items.

    These items are designed to produce interesting scan output on first run:
      - A mix of priorities (P1 through P4)
      - A mix of states (New, Active, In Progress, Done, Closed)
      - Several stale items (changed_date far in the past)
      - Recent P2 bugs (to trigger bring-up detection)
      - Multiple area paths and tags (for portfolio pulse)
    """
    conn = get_connection()
    ensure_schema(conn)

    now = now_utc()

    # Helper to create ISO date strings relative to "now"
    def days_ago(n: int) -> str:
        return (now - timedelta(days=n)).isoformat()

    seed_items = [
        # P1 items -- should appear in bring-up
        ("101", "API latency spike in production", "Active", 1, "ron", "backend;reliability",
         days_ago(10), days_ago(5), "Backend", "Bug"),
        ("102", "Payment gateway timeout errors", "Active", 1, "sara", "backend;payments",
         days_ago(7), days_ago(3), "Backend", "Bug"),
        ("103", "Data pipeline job failing nightly", "New", 1, "ron", "platform;data",
         days_ago(2), days_ago(1), "Platform", "Bug"),

        # P2 bugs created recently -- should appear in bring-up
        ("205", "Login timeout on mobile Safari", "New", 2, "alex", "frontend;auth",
         days_ago(2), days_ago(2), "Frontend", "Bug"),
        ("206", "Dashboard chart rendering glitch", "New", 2, "chen", "frontend;viz",
         days_ago(1), days_ago(1), "Frontend", "Bug"),

        # Stale items -- active but no movement for a while
        ("098", "Database migration script for v3", "Active", 3, "ron", "backend;infra",
         days_ago(30), days_ago(15), "Backend", "Task"),
        ("134", "Search indexer rewrite", "Active", 3, "sara", "backend;search",
         days_ago(25), days_ago(12), "Backend", "Story"),
        ("156", "Cache invalidation logic overhaul", "In Progress", 3, "alex", "platform;perf",
         days_ago(20), days_ago(8), "Platform", "Task"),
        ("178", "Onboarding flow redesign", "Active", 2, "chen", "frontend;ux",
         days_ago(22), days_ago(18), "Frontend", "Story"),
        ("089", "Legacy API deprecation plan", "Active", 4, "ron", "backend;tech-debt",
         days_ago(40), days_ago(25), "Backend", "Task"),

        # Items with recent state changes -- should appear in state changes
        ("201", "Auth refactor to OAuth2", "In Progress", 2, "alex", "backend;auth",
         days_ago(14), days_ago(2), "Backend", "Story"),
        ("210", "Dashboard performance optimization", "Active", 3, "chen", "frontend;perf",
         days_ago(10), days_ago(1), "Frontend", "Task"),
        ("215", "Error handling cleanup in API layer", "Done", 3, "ron", "backend;quality",
         days_ago(12), days_ago(1), "Backend", "Task"),
        ("220", "CI pipeline caching improvements", "Done", 4, "sara", "platform;devex",
         days_ago(8), days_ago(3), "Platform", "Task"),

        # Completed/closed items -- background for pulse
        ("050", "User profile page redesign", "Done", 3, "chen", "frontend;ux",
         days_ago(45), days_ago(30), "Frontend", "Story"),
        ("055", "Rate limiting middleware", "Closed", 2, "ron", "backend;security",
         days_ago(35), days_ago(28), "Backend", "Task"),
        ("060", "Monitoring dashboard setup", "Done", 3, "sara", "platform;observability",
         days_ago(50), days_ago(35), "Platform", "Task"),
        ("070", "Mobile responsive header fix", "Closed", 4, "alex", "frontend;mobile",
         days_ago(20), days_ago(15), "Frontend", "Bug"),
    ]

    for item in seed_items:
        conn.execute(
            """INSERT OR REPLACE INTO work_items
               (id, title, state, priority, assigned_to, tags,
                created_date, changed_date, area_path, work_item_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            item
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(seed_items)} work items. Run 'scan' to see the analysis.")


def cmd_history(_args) -> None:
    """Show past scan results for trend tracking."""
    conn = get_connection()
    ensure_schema(conn)

    rows = conn.execute(
        "SELECT * FROM scan_history ORDER BY scanned_at DESC LIMIT 20"
    ).fetchall()

    if not rows:
        print("No scan history yet. Run 'scan' to create the first entry.")
        conn.close()
        return

    print(f"\n{'Scanned At':<28} {'Lookback':>8} {'Total':>6} {'Bring Up':>9} {'Stale':>6} {'Changes':>8}")
    print("-" * 72)
    for row in rows:
        scanned = row["scanned_at"][:19]  # Trim to seconds
        print(f"{scanned:<28} {row['lookback_days']:>5} days {row['total_items']:>6} "
              f"{row['bring_up_count']:>9} {row['stale_count']:>6} {row['state_changes_count']:>8}")

    conn.close()


def cmd_pulse(_args) -> None:
    """
    Show portfolio pulse as a standalone command.

    Useful when you just want the "how much is on our plate" view without
    running the full scan.
    """
    conn = get_connection()
    ensure_schema(conn)

    items = conn.execute("SELECT * FROM work_items").fetchall()
    conn.close()

    if not items:
        print("No work items in the cache. Run 'seed' or 'import' first.")
        return

    pulse = compute_portfolio_pulse(items)
    print(format_pulse(pulse))

    # Also show a tag-based breakdown for cross-cutting concerns
    tag_counts: dict[str, int] = {}
    for item in items:
        tags_str = item["tags"] or ""
        for tag in tags_str.split(";"):
            tag = tag.strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if tag_counts:
        print("TAG DISTRIBUTION")
        for tag, count in sorted(tag_counts.items(), key=lambda t: t[1], reverse=True):
            print(f"  {tag + ':':<20} {count} items")
        print()


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser with subcommands.

    Each subcommand maps to a cmd_* function above. Adding a new command is
    as simple as writing the function and adding a subparser here.
    """
    parser = argparse.ArgumentParser(
        description="Standup Prep -- surface what matters from your work tracking cache."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Analyze cached items and show results")
    scan_parser.add_argument(
        "--lookback", type=int, default=4,
        help="Number of days to look back for state changes and new items (default: 4)"
    )
    scan_parser.set_defaults(func=cmd_scan)

    # import
    import_parser = subparsers.add_parser("import", help="Import work items from a JSON file")
    import_parser.add_argument("file", help="Path to the JSON file to import")
    import_parser.set_defaults(func=cmd_import)

    # seed
    seed_parser = subparsers.add_parser("seed", help="Seed example work items for demo")
    seed_parser.set_defaults(func=cmd_seed)

    # history
    history_parser = subparsers.add_parser("history", help="Show past scan results")
    history_parser.set_defaults(func=cmd_history)

    # pulse
    pulse_parser = subparsers.add_parser("pulse", help="Show portfolio pulse (counts by tag/area)")
    pulse_parser.set_defaults(func=cmd_pulse)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
