# Ops Dashboard

A Streamlit-based operations dashboard that connects to your Copilot CLI Toolkit
workflow databases. It provides a unified view of playbook routines, meeting prep,
agent performance, session management, and system reliability.

## Quick Start

```bash
pip install streamlit
streamlit run ops_dashboard.py
```

The dashboard opens at `http://localhost:8501` by default.

## Handling Port Conflicts

If port 8501 is already in use (another Streamlit app, for example), the app will
fail to start. You have two options:

1. **Specify a different port:**
   ```bash
   streamlit run ops_dashboard.py --server.port 8502
   ```

2. **Find what is using the port** (PowerShell):
   ```powershell
   Get-NetTCPConnection -LocalPort 8501 | Select-Object OwningProcess
   ```

The dashboard itself does not auto-detect port conflicts. Streamlit surfaces a
clear error message when the port is taken, and you simply relaunch on a new port.

## Pages

The dashboard ships with seven pages, accessible from the top navigation bar.

### 1. Playbook (Home)

The default landing page. Reads `playbook_routines` and `playbook_runs` from the
action tracker database (`ops_playbook.db`). Shows:

- A "Due Now" section highlighting routines that need attention based on frequency.
- Each routine as a card with title, frequency, and last run status.
- A copyable CLI prompt for each routine so you can paste it into Copilot CLI.
- A "Mark as Run" button to record a successful execution.
- Run history inside an expander per routine.

### 2. Meeting Hub

Reads `meetings`, `meeting_topics`, and `prep_history` from the meeting prep
database (`meeting_prep.db`). Shows:

- Configured meetings with schedule details (day, time, cadence).
- Active topics per meeting, with a form to add new ones.
- An upcoming meetings view for the next 7 days.
- Preparation history per meeting.

### 3. Agent Team

Uses a local `agent_team.db` (co-located with the dashboard). Tracks AI agents
and the tasks they complete. Shows:

- Agent roster with status badges (active, idle, retired).
- KPI tiles for total tasks completed and estimated time saved.
- Task history per agent in a filterable table.
- A bar chart of estimated manual minutes saved, broken down by agent.

The database seeds itself with three example agents on first run.

### 4. Session Close-Out

Provides three copy-paste prompt templates for ending a Copilot CLI session:

- **Quick Close-Out** for mid-day breaks (brief memory log).
- **Full Close-Out** for end of day (detailed log, preferences, insights).
- **Growth Close-Out** for sessions that should also rebuild the local index.

Each template is displayed in a code block for easy copying.

### 5. Notebook

Scans the `instructions/` and `docs/` directories for Markdown files. Shows:

- Each file in an expander with its content.
- An editable text area and Save button to update files in place.
- Last modified timestamps.
- Files grouped into "Instruction Files" and "Documentation" sections.

### 6. Tools & Configuration

System information and configuration overview:

- MCP server configuration from common config paths.
- Python version, Streamlit version, OS details.
- Toolkit directory structure.
- Database file sizes and row counts for each workflow database.

### 7. Reliability

Reads from `agent-debug.log` (JSONL format) at the toolkit root. Shows:

- KPI tiles for error, warning, and info counts.
- A recent errors table (last 20 entries).
- Level-based filtering.
- A "Diagnose" button per error that generates a copyable prompt for Copilot CLI.

If the log file does not exist, the page displays setup instructions.

## Customizing Pages

To add a new page, define a function and add it to the `pages` list in
`ops_dashboard.py`:

```python
def page_my_custom():
    """My custom dashboard page."""
    st.title("My Page")
    st.write("Content goes here.")

# Then add to the pages list:
pages = [
    # ... existing pages ...
    st.Page(page_my_custom, title="My Page", icon="🆕"),
]
```

To remove a page, delete or comment out its entry in the `pages` list.

## Database Locations

All paths are resolved relative to the dashboard file location:

| Database | Relative Path |
|----------|--------------|
| Action Tracker | `../../workflows/action-tracker/ops_playbook.db` |
| Meeting Prep | `../../workflows/meeting-prep/meeting_prep.db` |
| Agent Team | `./agent_team.db` (same directory as dashboard) |
| Debug Log | `../../agent-debug.log` |

## Requirements

- Python 3.10+
- Streamlit (`pip install streamlit`)
- No other dependencies (uses only the Python standard library and Streamlit)
