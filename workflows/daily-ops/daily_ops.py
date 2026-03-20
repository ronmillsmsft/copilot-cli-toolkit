#!/usr/bin/env python3
"""
Daily Ops - Aggregation Scanner for Workflow Databases

This is the "morning briefing" tool for your AI-assisted workflow toolkit.
It reads from multiple workflow databases and consolidates everything into
a single status report that your AI assistant can surface at session start.

=== The Aggregation Scanner Pattern ===

Instead of checking each tool separately, Daily Ops acts as a single
read-only aggregator. It never writes data -- it only reads from databases
owned by other tools (action tracker, meeting prep, standup prep). This
separation keeps each tool independent while giving you one unified view.

=== Why This Matters ===

When your AI assistant runs this at session start, it gains immediate
context about your work: overdue items, upcoming meetings, stale tasks.
This shifts the assistant from reactive ("what should I do?") to
proactive ("you have 2 overdue items and a meeting in 3 hours").

=== Boot Sequence Integration ===

Add this to your copilot-instructions.md or agent startup config:

    At session start, run: python daily_ops.py scan
    Surface any warnings or due items in your greeting to the user.

This gives your assistant "eyes" across your entire workflow system
before you even ask a question.

=== How to Wire Into Other Assistants ===

Any AI assistant or automation tool can call this script and parse
the output. The format is human-readable but structured enough for
an LLM to extract key facts from each section.
"""

# ---------------------------------------------------------------------------
# Standard library only -- zero external dependencies.
# This makes the script portable and easy to share. Anyone with Python 3.9+
# can run it without installing anything.
# ---------------------------------------------------------------------------
import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Database Discovery
#
# Configure paths to your workflow databases.
# These are relative to this script's directory, pointing to sibling folders
# in the workflows/ directory. Adjust if your layout differs.
# ---------------------------------------------------------------------------
DB_PATHS = {
    "action_tracker": "../action-tracker/action_tracker.db",
    "meeting_prep": "../meeting-prep/meeting_prep.db",
    "standup_prep": "../standup-prep/standup_prep.db",
}

# How many days of no updates before an item is considered "stale"
STALE_THRESHOLD_DAYS = 14

# How many days ahead to look for upcoming meetings
MEETING_LOOKAHEAD_DAYS = 3

# Resolve all paths relative to this script's location, not the caller's cwd.
# This ensures the script works no matter where you run it from.
SCRIPT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Database Connection Helpers
# ---------------------------------------------------------------------------

def resolve_db_path(key: str) -> Path:
    """Turn a config key into an absolute path."""
    return (SCRIPT_DIR / DB_PATHS[key]).resolve()


def try_connect(key: str):
    """
    Attempt to open a read-only connection to one of the workflow databases.

    Returns a sqlite3.Connection on success, or None if the file is missing.

    Why graceful degradation matters:
    You might install these tools one at a time. Daily Ops should still work
    with whatever subset of databases exist, rather than crashing because
    one tool hasn't been set up yet.
    """
    path = resolve_db_path(key)
    if not path.exists():
        return None
    # Use row_factory so we can access columns by name, not just index.
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Output Helpers
# ---------------------------------------------------------------------------

def print_header(now: datetime):
    """Print the scan header with a box-drawing border."""
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
    title = f"  Daily Ops Scan - {timestamp}"
    # Pad the title to fill the box width
    width = 50
    padded = title.ljust(width)
    print()
    print("+" + "=" * width + "+")
    print("|" + padded + "|")
    print("+" + "=" * width + "+")
    print()


def print_section(title: str):
    """Print a section divider."""
    print(f"--- {title} ---")
    print()


def print_skip_notice(db_name: str, description: str):
    """
    Print a notice when a database is not found.
    This is the graceful degradation in action -- instead of crashing,
    we inform the user and move on to the next check.
    """
    print(f"  [info] {db_name} not found - skipping {description}")
    print()


# ---------------------------------------------------------------------------
# Scan Checks
#
# Each check function reads from a specific database and prints its
# findings. They all follow the same pattern:
#   1. Query the database
#   2. Format and print results
#   3. Return quietly if nothing found
# ---------------------------------------------------------------------------

def check_overdue_items(conn, today_str: str):
    """
    Check 1: Overdue Action Items
    Items with a due_date in the past that are still open.
    These are the highest-priority items to surface at session start.
    """
    cursor = conn.execute(
        """
        SELECT title, due_date, owner, priority
        FROM action_items
        WHERE status = 'open'
          AND due_date IS NOT NULL
          AND due_date < ?
        ORDER BY due_date ASC
        """,
        (today_str,),
    )
    rows = cursor.fetchall()

    if not rows:
        print("  No overdue action items.")
    else:
        print(f"  !! OVERDUE ITEMS ({len(rows)})")
        for row in rows:
            owner_part = f" [{row['owner']}]" if row["owner"] else ""
            print(f'    - "{row["title"]}" (due {row["due_date"]}){owner_part}')
    print()


def check_stale_items(conn, cutoff_str: str):
    """
    Check 2: Stale Items
    Open or in-progress items that haven't been updated in 14+ days.
    These often indicate forgotten work or blocked tasks that need attention.
    """
    cursor = conn.execute(
        """
        SELECT title, updated_at
        FROM action_items
        WHERE status IN ('open', 'in_progress')
          AND updated_at < ?
        ORDER BY updated_at ASC
        """,
        (cutoff_str,),
    )
    rows = cursor.fetchall()

    if not rows:
        print("  No stale items.")
    else:
        print(f"  !! STALE ITEMS ({len(rows)})")
        for row in rows:
            # Calculate how many days since the last update
            try:
                last_update = datetime.fromisoformat(row["updated_at"])
                # Handle naive timestamps from SQLite's datetime('now')
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - last_update).days
                print(f'    - "{row["title"]}" ({days_ago} days untouched)')
            except (ValueError, TypeError):
                print(f'    - "{row["title"]}" (unknown last update)')
    print()


def check_due_routines(conn, now: datetime):
    """
    Check 3: Due Routines
    Playbook routines whose scheduled time has arrived based on their
    frequency and last run timestamp. This drives the "ops playbook"
    concept where recurring tasks are tracked and surfaced automatically.
    """
    cursor = conn.execute(
        """
        SELECT id, title, frequency, schedule_days, agent_id, last_run_at
        FROM playbook_routines
        WHERE enabled = 1
        ORDER BY frequency, title
        """
    )
    rows = cursor.fetchall()
    if not rows:
        return

    # Map frequency to the minimum interval between runs
    frequency_intervals = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "biweekly": timedelta(days=14),
        "monthly": timedelta(days=30),
    }

    today_day_name = now.strftime("%a")  # e.g., "Mon", "Tue"
    due_routines = []

    for row in rows:
        freq = row["frequency"]
        last_run = row["last_run_at"]
        schedule_days = row["schedule_days"]

        # If schedule_days is set, only show on matching days.
        # schedule_days is a comma-separated string like "Mon,Thu"
        if schedule_days:
            scheduled = [d.strip() for d in schedule_days.split(",")]
            if today_day_name not in scheduled:
                continue

        # Determine if enough time has passed since the last run
        is_due = False
        if last_run is None:
            # Never run before -- it's due
            is_due = True
        else:
            try:
                last_run_dt = datetime.fromisoformat(last_run)
                if last_run_dt.tzinfo is None:
                    last_run_dt = last_run_dt.replace(tzinfo=timezone.utc)
                interval = frequency_intervals.get(freq, timedelta(days=1))
                if (now - last_run_dt) >= interval:
                    is_due = True
            except (ValueError, TypeError):
                # If we can't parse the timestamp, treat it as due
                is_due = True

        if is_due:
            due_routines.append(row)

    if due_routines:
        print_section(f"OPS PLAYBOOK - DUE NOW ({len(due_routines)})")
        for r in due_routines:
            agent = r["agent_id"] or "manual"
            # Format: title, frequency, assigned agent
            print(f"    {r['title']:<30s} {r['frequency']:<12s} {agent}")
        print()


def check_action_stats(conn):
    """
    Check 6: Action Stats
    Summary counts of all action items by status.
    Gives a quick "health of the backlog" snapshot.
    """
    cursor = conn.execute(
        """
        SELECT status, COUNT(*) as cnt
        FROM action_items
        GROUP BY status
        ORDER BY status
        """
    )
    rows = cursor.fetchall()

    if not rows:
        return

    stats = {row["status"]: row["cnt"] for row in rows}
    open_count = stats.get("open", 0)
    in_progress = stats.get("in_progress", 0)
    done_count = stats.get("done", 0) + stats.get("closed", 0)

    print_section("SUMMARY")
    print(f"    Action Items: {open_count} open, {in_progress} in progress, {done_count} done")
    print()


def check_upcoming_meetings(conn, today):
    """
    Check 4 & 5: Upcoming Meetings + Active Topics
    Finds meetings scheduled within the next 3 days based on their
    day_of_week field, then counts unresolved discussion topics for each.

    Meetings in this system are recurring (weekly, biweekly), defined by
    day_of_week (0=Mon, 6=Sun) rather than specific dates. We check if
    any meeting's day falls within our lookahead window.
    """
    # First, get all meetings
    cursor = conn.execute(
        """
        SELECT id, name, day_of_week, time, cadence
        FROM meetings
        ORDER BY day_of_week, time
        """
    )
    meetings = cursor.fetchall()
    if not meetings:
        return

    # Get active topic counts per meeting in one query
    topic_cursor = conn.execute(
        """
        SELECT meeting_id, COUNT(*) as topic_count
        FROM meeting_topics
        WHERE status = 'active'
        GROUP BY meeting_id
        """
    )
    topic_counts = {row["meeting_id"]: row["topic_count"] for row in topic_cursor.fetchall()}

    # Find meetings happening in the next N days
    upcoming = []
    for day_offset in range(MEETING_LOOKAHEAD_DAYS):
        check_date = today + timedelta(days=day_offset)
        check_dow = check_date.weekday()  # 0=Mon, 6=Sun (matches schema)

        for mtg in meetings:
            if mtg["day_of_week"] == check_dow:
                topics = topic_counts.get(mtg["id"], 0)
                upcoming.append({
                    "date": check_date,
                    "name": mtg["name"],
                    "time": mtg["time"] or "TBD",
                    "topics": topics,
                })

    if upcoming:
        print_section(f"UPCOMING MEETINGS (next {MEETING_LOOKAHEAD_DAYS} days)")
        for m in upcoming:
            day_label = m["date"].strftime("%a %m/%d")
            topic_note = f" ({m['topics']} active topics)" if m["topics"] > 0 else ""
            print(f"    {day_label}  {m['time']:<6s} {m['name']}{topic_note}")
        print()
    else:
        print("  No meetings in the next 3 days.")
        print()


def check_standup_prep(conn):
    """
    Read the most recent scan from standup-prep to show context about
    what was last analyzed. This gives continuity between sessions --
    you can see what the last standup scan found without re-running it.
    """
    cursor = conn.execute(
        """
        SELECT scanned_at, lookback_days, total_items,
               bring_up_count, state_changes_count
        FROM scan_history
        ORDER BY scanned_at DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()

    if row:
        print_section("STANDUP PREP")
        scanned = row["scanned_at"] or "unknown"
        total = row["total_items"] or 0
        flagged = row["bring_up_count"] or 0
        changes = row["state_changes_count"] or 0
        print(f"    Last scan: {scanned}")
        print(f"    {total} items reviewed, {flagged} flagged, {changes} state changes")
        print()
    # If no scan history exists, silently skip -- not worth a warning


# ---------------------------------------------------------------------------
# Main Commands
# ---------------------------------------------------------------------------

def cmd_scan():
    """
    Full scan across all workflow databases.

    This is the main entry point for the boot sequence integration.
    It runs every check in order, gracefully skipping any database
    that isn't available. The output is designed to be both human-readable
    and easy for an AI assistant to parse and summarize.
    """
    # Use timezone-aware UTC time throughout.
    # NOTE: We use datetime.now(timezone.utc) instead of the deprecated
    # datetime.utcnow(), which was removed in Python 3.14.
    now = datetime.now(timezone.utc)
    today = now.date()
    today_str = today.isoformat()
    stale_cutoff = (now - timedelta(days=STALE_THRESHOLD_DAYS)).isoformat()

    print_header(now)

    # --- Action Tracker checks ---
    at_conn = try_connect("action_tracker")
    if at_conn:
        print_section("ACTION ITEMS")
        check_overdue_items(at_conn, today_str)
        check_stale_items(at_conn, stale_cutoff)
        check_due_routines(at_conn, now)
        check_action_stats(at_conn)
        at_conn.close()
    else:
        print_skip_notice("action_tracker.db", "action item checks")

    # --- Meeting Prep checks ---
    mp_conn = try_connect("meeting_prep")
    if mp_conn:
        check_upcoming_meetings(mp_conn, today)
        mp_conn.close()
    else:
        print_skip_notice("meeting_prep.db", "meeting checks")

    # --- Standup Prep checks ---
    sp_conn = try_connect("standup_prep")
    if sp_conn:
        check_standup_prep(sp_conn)
        sp_conn.close()
    else:
        print_skip_notice("standup_prep.db", "standup prep checks")

    print("Scan complete.")


def cmd_status():
    """
    Quick health check showing which databases are reachable.

    Use this to verify your setup before running a full scan, or to
    debug why certain sections are being skipped.
    """
    print()
    print("Daily Ops - Database Status")
    print()

    all_found = True
    for key in DB_PATHS:
        path = resolve_db_path(key)
        if path.exists():
            # Show file size as a basic sanity check
            size_kb = path.stat().st_size / 1024
            print(f"  [ok]    {key:<20s} {path}  ({size_kb:.1f} KB)")
        else:
            print(f"  [miss]  {key:<20s} {path}")
            all_found = False

    print()
    if all_found:
        print("All databases found. Ready for scanning.")
    else:
        print("Some databases are missing. Those sections will be skipped during scan.")
    print()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    """
    Parse the command line and dispatch to the appropriate handler.

    Usage:
        python daily_ops.py scan      Full scan across all databases
        python daily_ops.py status    Quick health check
    """
    if len(sys.argv) < 2:
        print("Daily Ops - Aggregation Scanner")
        print()
        print("Usage:")
        print("  python daily_ops.py scan     Full scan across all databases")
        print("  python daily_ops.py status   Quick database health check")
        print()
        print("For boot sequence integration, add to your copilot-instructions.md:")
        print('  "At session start, run: python daily_ops.py scan"')
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "scan":
        cmd_scan()
    elif command == "status":
        cmd_status()
    else:
        print(f"Unknown command: {command}")
        print("Use 'scan' or 'status'. Run without arguments for help.")
        sys.exit(1)


if __name__ == "__main__":
    main()
