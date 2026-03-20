"""
Ops Dashboard - Streamlit-based operations center for the Copilot CLI Toolkit.

Connects to SQLite databases created by the Tier 3 workflow tools and provides
a unified view of playbook routines, meeting prep, agent performance, session
management, and system reliability.

To run the dashboard:
    streamlit run ops_dashboard.py

If port 8501 is already in use:
    streamlit run ops_dashboard.py --server.port 8502

To check what is using a port (PowerShell):
    Get-NetTCPConnection -LocalPort 8501 | Select-Object OwningProcess
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Path Configuration
# ---------------------------------------------------------------------------
# Resolve paths relative to this file so the dashboard works from any cwd.
BASE_DIR: Path = Path(__file__).parent.parent.parent  # toolkit root
DB_PATHS: dict[str, Path] = {
    "action_tracker": BASE_DIR / "workflows" / "action-tracker" / "ops_playbook.db",
    "meeting_prep": BASE_DIR / "workflows" / "meeting-prep" / "meeting_prep.db",
}
# Agent team DB lives alongside the dashboard
AGENT_DB: Path = Path(__file__).parent / "agent_team.db"
DEBUG_LOG: Path = BASE_DIR / "agent-debug.log"
INSTRUCTIONS_DIR: Path = BASE_DIR / "instructions"
DOCS_DIR: Path = BASE_DIR / "docs"

# ---------------------------------------------------------------------------
# Streamlit Page Config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ops Dashboard",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS - dark theme matching toolkit aesthetic
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    /* Main background */
    .stApp {
        background-color: #0f1117;
    }
    /* Card-like containers */
    div[data-testid="stExpander"] {
        background-color: #1a1d27;
        border: 1px solid #2d3348;
        border-radius: 8px;
    }
    /* Metric labels */
    div[data-testid="stMetricLabel"] {
        color: #94a3b8;
    }
    /* Muted helper text */
    .muted {
        color: #94a3b8;
        font-size: 0.85rem;
    }
    /* Status badges */
    .badge-active { color: #22c55e; font-weight: 600; }
    .badge-idle { color: #eab308; font-weight: 600; }
    .badge-retired { color: #94a3b8; font-weight: 600; }
    .badge-success { color: #22c55e; }
    .badge-failed { color: #ef4444; }
    .badge-running { color: #3b82f6; }
    .badge-skipped { color: #eab308; }
    /* Accent borders for sections */
    .accent-blue { border-left: 3px solid #3b82f6; padding-left: 12px; }
    .accent-purple { border-left: 3px solid #a855f7; padding-left: 12px; }
    .accent-cyan { border-left: 3px solid #06b6d4; padding-left: 12px; }
    .accent-green { border-left: 3px solid #22c55e; padding-left: 12px; }
    .accent-yellow { border-left: 3px solid #eab308; padding-left: 12px; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

def db_exists(name: str) -> bool:
    """Check whether a workflow database file exists on disk."""
    if name == "agent_team":
        return AGENT_DB.exists()
    return DB_PATHS.get(name, Path("__missing__")).exists()


def get_conn(name: str) -> sqlite3.Connection:
    """Return a sqlite3 connection for the named database.

    Raises FileNotFoundError when the database file is missing.
    """
    if name == "agent_team":
        path = AGENT_DB
    else:
        path = DB_PATHS[name]
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def query(name: str, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Run a read query and return results as a list of dicts."""
    with get_conn(name) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(name: str, sql: str, params: tuple = ()) -> None:
    """Run a write query (INSERT, UPDATE, DELETE)."""
    with get_conn(name) as conn:
        conn.execute(sql, params)
        conn.commit()


def setup_message(db_label: str) -> None:
    """Show a friendly message when a database is not yet created."""
    st.info(
        f"The **{db_label}** database has not been created yet. "
        "Run the workflow tools first to create databases:\n\n"
        "```bash\n"
        "python action_tracker.py seed   # creates ops_playbook.db\n"
        "python meeting_prep.py seed     # creates meeting_prep.db\n"
        "```"
    )


# ---------------------------------------------------------------------------
# Agent Team DB Bootstrap
# ---------------------------------------------------------------------------

def ensure_agent_db() -> None:
    """Create agent_team.db tables if they do not exist, then seed defaults."""
    conn = sqlite3.connect(str(AGENT_DB))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                task_type TEXT,
                description TEXT,
                status TEXT DEFAULT 'completed',
                started_at TEXT,
                completed_at TEXT,
                duration_seconds INTEGER,
                estimated_manual_minutes INTEGER,
                output_summary TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );
            CREATE TABLE IF NOT EXISTS agent_metrics (
                agent_id TEXT NOT NULL,
                date TEXT NOT NULL,
                tasks_completed INTEGER DEFAULT 0,
                tasks_failed INTEGER DEFAULT 0,
                total_duration_seconds INTEGER DEFAULT 0,
                estimated_time_saved_minutes INTEGER DEFAULT 0,
                PRIMARY KEY (agent_id, date),
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );
        """)
        # Seed default agents if table is empty
        count = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc).isoformat()
            seed_agents = [
                ("daily-ops", "Daily Operations Scanner", "active",
                 "Scans email, calendar, and task boards each morning.", now, now),
                ("meeting-prep", "Meeting Preparation Agent", "active",
                 "Generates prep documents before scheduled meetings.", now, now),
                ("playbook-runner", "Ops Playbook Executor", "active",
                 "Runs playbook routines on schedule.", now, now),
            ]
            conn.executemany(
                "INSERT INTO agents (id, name, status, description, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                seed_agents,
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Frequency / Schedule Helpers
# ---------------------------------------------------------------------------

# Map day abbreviations to weekday numbers (Monday=0)
_DAY_MAP: dict[str, int] = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def is_routine_due(frequency: str, schedule_days: str | None,
                   last_run_time: str | None) -> bool:
    """Determine whether a playbook routine is currently due.

    Uses simple heuristics based on frequency and last run timestamp.
    """
    now = datetime.now(timezone.utc)
    if last_run_time is None:
        return True  # never run, always due

    try:
        last = datetime.fromisoformat(last_run_time)
        # Ensure timezone-aware comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True

    freq = (frequency or "").lower()
    if freq == "daily":
        return (now - last) > timedelta(hours=20)
    if freq == "weekly":
        return (now - last) > timedelta(days=6)
    if freq == "biweekly":
        return (now - last) > timedelta(days=13)
    if freq == "monthly":
        return (now - last) > timedelta(days=28)
    return False


def status_icon(status: str) -> str:
    """Return a colored circle emoji for a run status."""
    return {
        "success": "🟢",
        "failed": "🔴",
        "running": "🔵",
        "skipped": "🟡",
    }.get((status or "").lower(), "⚪")


# ===================================================================
# PAGE FUNCTIONS
# ===================================================================

def page_playbook() -> None:
    """Ops Playbook page. Shows routines, run history, and due-now alerts."""
    st.title("📋 Ops Playbook")

    if not db_exists("action_tracker"):
        setup_message("action_tracker (ops_playbook.db)")
        return

    # Fetch routines and their most recent run
    routines = query(
        "action_tracker",
        "SELECT * FROM playbook_routines ORDER BY title",
    )
    if not routines:
        st.warning("No playbook routines found. Run `python action_tracker.py seed` to create some.")
        return

    # Build a lookup of latest run per routine
    latest_runs: dict[str, dict] = {}
    try:
        runs = query(
            "action_tracker",
            "SELECT routine_id, MAX(started_at) AS started_at, status "
            "FROM playbook_runs GROUP BY routine_id",
        )
        for r in runs:
            latest_runs[r["routine_id"]] = r
    except Exception:
        pass  # playbook_runs table might not exist yet

    # --- Due Now section ---
    due_routines = [
        r for r in routines
        if is_routine_due(
            r["frequency"],
            r.get("schedule_days"),
            latest_runs.get(r["id"], {}).get("started_at"),
        )
    ]
    if due_routines:
        st.markdown("### 🔔 Due Now")
        cols = st.columns(min(len(due_routines), 3))
        for idx, routine in enumerate(due_routines):
            with cols[idx % 3]:
                st.markdown(f"**{routine['title']}**")
                st.caption(f"Frequency: {routine['frequency']}")
    st.divider()

    # --- Routine cards ---
    for routine in routines:
        rid = routine["id"]
        last = latest_runs.get(rid)
        last_status = last["status"] if last else "never"
        last_time = last["started_at"] if last else "N/A"

        with st.container():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"#### {routine['title']}")
                st.caption(
                    f"Frequency: {routine['frequency']}  |  "
                    f"Last run: {status_icon(last_status)} {last_status} ({last_time})"
                )
            with c2:
                # Copy-to-clipboard via st.code
                prompt_text = routine.get("description") or f"Run the '{routine['title']}' playbook routine."
                st.code(prompt_text, language=None)
            with c3:
                if st.button("Mark as Run", key=f"run_{rid}"):
                    now_str = datetime.now(timezone.utc).isoformat()
                    execute(
                        "action_tracker",
                        "INSERT INTO playbook_runs (routine_id, started_at, completed_at, status) "
                        "VALUES (?, ?, ?, 'success')",
                        (rid, now_str, now_str),
                    )
                    st.rerun()

            # Run history expander
            with st.expander(f"Run history for {routine['title']}"):
                try:
                    history = query(
                        "action_tracker",
                        "SELECT * FROM playbook_runs WHERE routine_id = ? ORDER BY started_at DESC LIMIT 20",
                        (rid,),
                    )
                    if history:
                        st.dataframe(history, hide_index=True)
                    else:
                        st.caption("No runs recorded yet.")
                except Exception:
                    st.caption("No run history table found.")
        st.divider()


def page_meeting_hub() -> None:
    """Meeting Hub page. Shows meetings, topics, and upcoming schedule."""
    st.title("📅 Meeting Hub")

    if not db_exists("meeting_prep"):
        setup_message("meeting_prep")
        return

    meetings = query("meeting_prep", "SELECT * FROM meetings ORDER BY name")
    if not meetings:
        st.warning("No meetings configured. Run `python meeting_prep.py seed` to add some.")
        return

    # --- Upcoming meetings (next 7 days) ---
    st.markdown("### 📆 Upcoming (Next 7 Days)")
    today = datetime.now(timezone.utc).date()
    upcoming: list[dict[str, Any]] = []
    for m in meetings:
        day_name = (m.get("day_of_week") or "").strip().lower()
        target_weekday = _DAY_MAP.get(day_name)
        if target_weekday is None:
            continue
        for offset in range(7):
            check_date = today + timedelta(days=offset)
            if check_date.weekday() == target_weekday:
                upcoming.append({
                    "Date": check_date.isoformat(),
                    "Day": check_date.strftime("%A"),
                    "Meeting": m["name"],
                    "Time": m.get("time", ""),
                    "Stakeholder": m.get("stakeholder", ""),
                })
    if upcoming:
        upcoming.sort(key=lambda x: x["Date"])
        st.dataframe(upcoming, hide_index=True, use_container_width=True)
    else:
        st.caption("No meetings scheduled in the next 7 days.")
    st.divider()

    # --- Per-meeting details ---
    for m in meetings:
        mid = m["id"]
        with st.expander(f"**{m['name']}** - {m.get('cadence', '')} on {m.get('day_of_week', '')} at {m.get('time', '')}"):
            st.markdown(f"**Purpose:** {m.get('purpose', 'N/A')}")
            st.markdown(f"**Stakeholder:** {m.get('stakeholder', 'N/A')}")

            # Active topics
            st.markdown("##### Active Topics")
            topics = query(
                "meeting_prep",
                "SELECT * FROM meeting_topics WHERE meeting_id = ? AND status = 'active' ORDER BY added_at DESC",
                (mid,),
            )
            if topics:
                for t in topics:
                    st.markdown(f"- {t['topic']}  *(added {t['added_at']})*")
            else:
                st.caption("No active topics.")

            # Add new topic form
            new_topic = st.text_input("Add a topic:", key=f"topic_{mid}")
            if st.button("Add", key=f"add_topic_{mid}") and new_topic.strip():
                now_str = datetime.now(timezone.utc).isoformat()
                execute(
                    "meeting_prep",
                    "INSERT INTO meeting_topics (meeting_id, topic, added_at) VALUES (?, ?, ?)",
                    (mid, new_topic.strip(), now_str),
                )
                st.rerun()

            # Prep history
            st.markdown("##### Prep History")
            try:
                preps = query(
                    "meeting_prep",
                    "SELECT * FROM prep_history WHERE meeting_id = ? ORDER BY prep_date DESC LIMIT 10",
                    (mid,),
                )
                if preps:
                    st.dataframe(preps, hide_index=True)
                else:
                    st.caption("No prep history yet.")
            except Exception:
                st.caption("No prep history table found.")


def page_agent_team() -> None:
    """Agent Team page. Shows agent roster, KPIs, task history, and time-saved chart."""
    st.title("🤖 Agent Team")

    # Ensure the database and seed data exist
    ensure_agent_db()

    agents = query("agent_team", "SELECT * FROM agents ORDER BY name")

    # --- KPI tiles ---
    total_tasks = 0
    total_saved = 0
    try:
        stats = query(
            "agent_team",
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(estimated_manual_minutes), 0) AS saved "
            "FROM agent_tasks WHERE status = 'completed'",
        )
        if stats:
            total_tasks = stats[0]["cnt"]
            total_saved = stats[0]["saved"]
    except Exception:
        pass

    k1, k2, k3 = st.columns(3)
    k1.metric("Agents", len(agents))
    k2.metric("Tasks Completed", total_tasks)
    k3.metric("Est. Time Saved", f"{total_saved} min")
    st.divider()

    # --- Agent roster ---
    st.markdown("### Agent Roster")
    for agent in agents:
        badge_class = f"badge-{agent['status']}"
        st.markdown(
            f"**{agent['name']}** "
            f"<span class='{badge_class}'>[{agent['status']}]</span> "
            f"<span class='muted'>{agent.get('description', '')}</span>",
            unsafe_allow_html=True,
        )
    st.divider()

    # --- Time saved chart (bar chart by agent) ---
    st.markdown("### Time Saved by Agent")
    try:
        chart_data = query(
            "agent_team",
            "SELECT a.name, COALESCE(SUM(t.estimated_manual_minutes), 0) AS minutes_saved "
            "FROM agents a LEFT JOIN agent_tasks t ON a.id = t.agent_id AND t.status = 'completed' "
            "GROUP BY a.id ORDER BY minutes_saved DESC",
        )
        if chart_data and any(d["minutes_saved"] > 0 for d in chart_data):
            import pandas as pd
            df = pd.DataFrame(chart_data)
            st.bar_chart(df, x="name", y="minutes_saved", color="#3b82f6")
        else:
            st.caption("No task data yet. Time-saved chart will appear once agents log tasks.")
    except Exception as exc:
        st.caption(f"Chart unavailable: {exc}")
    st.divider()

    # --- Task history per agent ---
    st.markdown("### Task History")
    selected_agent = st.selectbox(
        "Filter by agent:",
        options=["All"] + [a["name"] for a in agents],
        key="agent_filter",
    )
    try:
        if selected_agent == "All":
            tasks = query(
                "agent_team",
                "SELECT t.*, a.name AS agent_name FROM agent_tasks t "
                "JOIN agents a ON t.agent_id = a.id ORDER BY t.completed_at DESC LIMIT 50",
            )
        else:
            tasks = query(
                "agent_team",
                "SELECT t.*, a.name AS agent_name FROM agent_tasks t "
                "JOIN agents a ON t.agent_id = a.id WHERE a.name = ? "
                "ORDER BY t.completed_at DESC LIMIT 50",
                (selected_agent,),
            )
        if tasks:
            st.dataframe(tasks, hide_index=True, use_container_width=True)
        else:
            st.caption("No tasks recorded yet.")
    except Exception:
        st.caption("No task history available.")


def page_session_closeout() -> None:
    """Session Close-Out page. Provides copy-paste prompt templates."""
    st.title("🔒 Session Close-Out")

    st.markdown(
        "Use these templates to close out a Copilot CLI session. "
        "Copy the prompt and paste it into your active session. "
        "Each level captures progressively more context for future sessions."
    )
    st.divider()

    # --- Quick Close-Out ---
    with st.expander("⚡ Quick Close-Out (mid-day breaks)", expanded=True):
        st.markdown(
            "Use this when stepping away briefly. Captures a short summary "
            "and any new preferences so the next session picks up smoothly."
        )
        st.code(
            "Quick session close-out. Log this conversation to agent-memory "
            "with a brief summary. Save any new preferences or insights discovered.",
            language=None,
        )

    # --- Full Close-Out ---
    with st.expander("📝 Full Close-Out (end of day)", expanded=True):
        st.markdown(
            "Use this at the end of a work block. Captures detailed context, "
            "decisions, and updates to instruction files when workflows changed."
        )
        st.code(
            "Full session close-out. Log this conversation to agent-memory "
            "with a detailed summary. Save any new preferences discovered. "
            "Save any new insights (decisions, patterns, goals). "
            "Update any instruction files if workflows changed. "
            "Complete any open tasks.",
            language=None,
        )

    # --- Growth Close-Out ---
    with st.expander("🌱 Growth Close-Out (includes /reindex)", expanded=True):
        st.markdown(
            "Use this after sessions with significant new work. Includes everything "
            "from the full close-out, plus rebuilds the local session index so future "
            "sessions can search across all past work."
        )
        st.code(
            "Growth session close-out. Log this conversation to agent-memory "
            "with a detailed summary. Save any new preferences and insights. "
            "Update instruction files if workflows changed. Complete open tasks. "
            "Then run /reindex to rebuild the local session index so future "
            "sessions can search across all past work.",
            language=None,
        )

    st.divider()
    st.markdown(
        '<p class="muted">'
        "Each session close-out builds compound value. Quick close-outs keep "
        "continuity; full close-outs deepen understanding; growth close-outs "
        "make all past work searchable. The more consistently you close out, "
        "the smarter your next session starts."
        "</p>",
        unsafe_allow_html=True,
    )


def page_notebook() -> None:
    """Notebook page. Browse and edit instruction and documentation files."""
    st.title("📓 Notebook")

    def _collect_md_files(directory: Path, label: str) -> list[dict[str, Any]]:
        """Collect .md files from a directory with metadata."""
        results: list[dict[str, Any]] = []
        if not directory.exists():
            return results
        for fp in sorted(directory.glob("*.md")):
            stat = fp.stat()
            results.append({
                "path": fp,
                "name": fp.name,
                "group": label,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "size": stat.st_size,
            })
        return results

    instruction_files = _collect_md_files(INSTRUCTIONS_DIR, "Instruction Files")
    doc_files = _collect_md_files(DOCS_DIR, "Documentation")
    all_files = instruction_files + doc_files

    if not all_files:
        st.warning("No Markdown files found in instructions/ or docs/ directories.")
        return

    # Group and display
    for group_label in ("Instruction Files", "Documentation"):
        group = [f for f in all_files if f["group"] == group_label]
        if not group:
            continue
        st.markdown(f"### {group_label}")
        for entry in group:
            fp: Path = entry["path"]
            with st.expander(f"{entry['name']}  (modified {entry['modified']})"):
                try:
                    content = fp.read_text(encoding="utf-8")
                except Exception as exc:
                    st.error(f"Could not read file: {exc}")
                    continue

                # Editable text area
                edited = st.text_area(
                    f"Edit {entry['name']}",
                    value=content,
                    height=300,
                    key=f"edit_{fp}",
                )
                if st.button("Save", key=f"save_{fp}"):
                    try:
                        fp.write_text(edited, encoding="utf-8")
                        st.success(f"Saved {entry['name']}")
                    except Exception as exc:
                        st.error(f"Failed to save: {exc}")


def page_tools() -> None:
    """Tools & Configuration page. System info, MCP config, and DB stats."""
    st.title("🔧 Tools & Configuration")

    # --- MCP Configuration ---
    st.markdown("### MCP Servers")
    mcp_paths = [
        Path.home() / ".copilot" / "mcp-config.json",
        Path.home() / ".config" / "github-copilot" / "mcp-config.json",
    ]
    mcp_found = False
    for mcp_path in mcp_paths:
        if mcp_path.exists():
            mcp_found = True
            try:
                mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
                servers = mcp_data.get("mcpServers", mcp_data.get("servers", {}))
                if servers:
                    for name, config in servers.items():
                        c1, c2 = st.columns([1, 3])
                        c1.markdown(f"**{name}** 🟢")
                        cmd = config.get("command", "N/A")
                        args = " ".join(config.get("args", []))
                        c2.code(f"{cmd} {args}", language=None)
                else:
                    st.caption("Config file found but no servers defined.")
            except Exception as exc:
                st.warning(f"Could not parse {mcp_path}: {exc}")
    if not mcp_found:
        st.caption("No MCP configuration file found at common paths.")
    st.divider()

    # --- System Info ---
    st.markdown("### System Info")
    s1, s2, s3 = st.columns(3)
    s1.metric("Python", platform.python_version())
    s2.metric("Streamlit", st.__version__)
    s3.metric("OS", f"{platform.system()} {platform.release()}")
    st.divider()

    # --- Toolkit Structure ---
    st.markdown("### Toolkit Structure")
    if BASE_DIR.exists():
        structure_lines: list[str] = []
        for item in sorted(BASE_DIR.iterdir()):
            if item.name.startswith("."):
                continue
            prefix = "📁" if item.is_dir() else "📄"
            structure_lines.append(f"{prefix} {item.name}")
            # Show one level of children for directories
            if item.is_dir():
                try:
                    for child in sorted(item.iterdir()):
                        if child.name.startswith("."):
                            continue
                        c_prefix = "  📁" if child.is_dir() else "  📄"
                        structure_lines.append(f"{c_prefix} {child.name}")
                except PermissionError:
                    pass
        st.code("\n".join(structure_lines), language=None)
    st.divider()

    # --- Database Stats ---
    st.markdown("### Database Stats")
    all_dbs: dict[str, Path] = {**DB_PATHS, "agent_team": AGENT_DB}
    for db_name, db_path in all_dbs.items():
        if not db_path.exists():
            st.caption(f"**{db_name}**: not created yet")
            continue
        size_kb = db_path.stat().st_size / 1024
        try:
            with sqlite3.connect(str(db_path)) as conn:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
                table_info: list[str] = []
                for (tname,) in tables:
                    count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                    table_info.append(f"{tname}: {count} rows")
            st.markdown(f"**{db_name}** ({size_kb:.1f} KB)")
            st.caption("  |  ".join(table_info) if table_info else "No tables")
        except Exception as exc:
            st.markdown(f"**{db_name}** ({size_kb:.1f} KB)")
            st.caption(f"Error reading: {exc}")


def page_reliability() -> None:
    """Reliability page. Parses agent-debug.log and surfaces errors."""
    st.title("🔍 Reliability")

    if not DEBUG_LOG.exists():
        st.info(
            "No `agent-debug.log` found at the toolkit root.\n\n"
            "To enable debug logging, configure your workflow tools to write "
            "JSONL entries to:\n\n"
            f"```\n{DEBUG_LOG}\n```\n\n"
            "Each line should be a JSON object with keys: "
            "`timestamp`, `level`, `source`, `message`, `details`."
        )
        return

    # Parse JSONL log file
    entries: list[dict[str, Any]] = []
    try:
        with open(DEBUG_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        st.error(f"Could not read log file: {exc}")
        return

    if not entries:
        st.caption("Log file exists but contains no entries.")
        return

    # Count by level
    error_count = sum(1 for e in entries if (e.get("level") or "").lower() == "error")
    warn_count = sum(1 for e in entries if (e.get("level") or "").lower() == "warning")
    info_count = sum(1 for e in entries if (e.get("level") or "").lower() == "info")

    # --- KPI tiles ---
    k1, k2, k3 = st.columns(3)
    k1.metric("Errors", error_count)
    k2.metric("Warnings", warn_count)
    k3.metric("Info", info_count)
    st.divider()

    # --- Level filter ---
    level_filter = st.selectbox(
        "Filter by level:",
        options=["All", "error", "warning", "info"],
        key="log_level_filter",
    )
    if level_filter != "All":
        filtered = [e for e in entries if (e.get("level") or "").lower() == level_filter]
    else:
        filtered = entries

    # --- Recent entries table ---
    st.markdown("### Recent Entries")
    recent = filtered[-20:][::-1]  # last 20, newest first
    if recent:
        display_data = [
            {
                "Timestamp": e.get("timestamp", ""),
                "Level": (e.get("level") or "").upper(),
                "Source": e.get("source", ""),
                "Message": e.get("message", ""),
            }
            for e in recent
        ]
        st.dataframe(display_data, hide_index=True, use_container_width=True)
    else:
        st.caption("No entries match the selected filter.")
    st.divider()

    # --- Diagnose buttons for errors ---
    error_entries = [e for e in filtered if (e.get("level") or "").lower() == "error"]
    if error_entries:
        st.markdown("### Diagnose Errors")
        for idx, entry in enumerate(error_entries[-10:][::-1]):
            with st.expander(
                f"{entry.get('timestamp', 'N/A')} - {entry.get('source', 'unknown')}: "
                f"{entry.get('message', '')[:80]}"
            ):
                diag_prompt = (
                    f"Diagnose this error and suggest a fix:\n"
                    f"Source: {entry.get('source', 'unknown')}\n"
                    f"Error: {entry.get('message', '')}\n"
                    f"Details: {entry.get('details', '')}\n"
                    f"Timestamp: {entry.get('timestamp', '')}"
                )
                st.code(diag_prompt, language=None)


# ===================================================================
# NAVIGATION - Top-level app structure
# ===================================================================

pages = [
    st.Page(page_playbook, title="Playbook", icon="📋"),
    st.Page(page_meeting_hub, title="Meeting Hub", icon="📅"),
    st.Page(page_agent_team, title="Agent Team", icon="🤖"),
    st.Page(page_session_closeout, title="Close-Out", icon="🔒"),
    st.Page(page_notebook, title="Notebook", icon="📓"),
    st.Page(page_tools, title="Tools", icon="🔧"),
    st.Page(page_reliability, title="Reliability", icon="🔍"),
]

nav = st.navigation(pages, position="top")
nav.run()
