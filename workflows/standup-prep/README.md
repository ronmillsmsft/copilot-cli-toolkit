# Standup Prep

**Surface what matters from your work tracking system -- fast, offline, and portable.**

Standup Prep pulls your work items into a local SQLite cache and runs analysis
patterns against them. No API calls at scan time, no cloud dependency for analysis.
You bring the data, it finds the signal.

## What It Does

Most standups devolve into status recitation. Standup Prep flips the script by
surfacing the items that actually need attention:

| Pattern | What It Catches |
|---------|----------------|
| **Bring Up Items** | P1s still open + P2 bugs created recently |
| **Stale Items** | Active items with no state change in 5+ days |
| **State Changes** | Items that moved states within your lookback window |
| **Portfolio Pulse** | Counts grouped by tag or area path |

The philosophy: if an item is high-priority and open, or if something has gone
dark for a week, you should know about it *before* standup -- not during.

## Connecting to Your Work Tracking System

Standup Prep is **system-agnostic**. It works with a local SQLite database that
you populate from whatever tracker you use. The import command accepts a JSON
file with a simple schema, so you just need a small adapter script for your
system.

### Supported Systems (via JSON export)

- **Azure DevOps (ADO):** Use the REST API or `az boards` CLI to export work items as JSON.
- **Jira:** Use the Jira REST API (`/rest/api/2/search`) and map fields to the schema below.
- **GitHub Issues:** Use `gh issue list --json` and reshape the output.
- **Linear, Shortcut, etc.:** Any system with a JSON export or API works.

### JSON Import Format

Each work item should be a JSON object in an array:

```json
[
  {
    "id": "101",
    "title": "API latency spike in production",
    "state": "Active",
    "priority": 1,
    "assigned_to": "ron",
    "tags": "backend;reliability",
    "created_date": "2026-03-10T09:00:00Z",
    "changed_date": "2026-03-15T14:30:00Z",
    "area_path": "Backend",
    "work_item_type": "Bug"
  }
]
```

### Field Mapping

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Unique identifier from your system |
| `title` | Yes | Item title or summary |
| `state` | Yes | New, Active, In Progress, Done, Closed |
| `priority` | No | 1=Critical, 2=High, 3=Medium (default), 4=Low |
| `assigned_to` | No | Owner or assignee |
| `tags` | No | Semicolon-delimited tags |
| `created_date` | No | ISO 8601 datetime |
| `changed_date` | No | Last state change datetime |
| `area_path` | No | Team or area grouping |
| `work_item_type` | No | Bug, Task, Story, PBI |

## CLI Commands

```bash
# Seed the database with example items (great for trying it out)
python standup_prep.py seed

# Run analysis against cached items (default lookback: 4 days)
python standup_prep.py scan

# Run analysis with a custom lookback window
python standup_prep.py scan --lookback 7

# Import work items from a JSON file
python standup_prep.py import items.json

# Show past scan results
python standup_prep.py history

# Show portfolio pulse (item counts by tag and area)
python standup_prep.py pulse
```

## Example Output

```
+==================================================+
|  Standup Prep -- 2026-03-20                       |
+==================================================+

RED BRING UP (3)
  #101  [P1] API latency spike in prod        Active    (5 days stale)
  #205  [P2] Login timeout on mobile           New       (new bug)
  #112  [P1] Payment gateway errors            Active    (3 days stale)

!! STALE ITEMS (4)
  #098  Database migration script              Active    (12 days unchanged)
  #134  Search indexer rewrite                 Active    (8 days unchanged)
  #156  Cache invalidation logic               In Progress (6 days unchanged)
  #178  Onboarding flow redesign               Active    (15 days unchanged)

STATE CHANGES (last 4 days)
  #201  Auth refactor                          Active -> In Progress
  #210  Dashboard performance fix              New -> Active
  #215  Error handling cleanup                 In Progress -> Done

PORTFOLIO PULSE
  Backend:    12 items (3 New, 5 Active, 4 Done)
  Frontend:    8 items (1 New, 4 Active, 3 Done)
  Platform:    5 items (0 New, 3 Active, 2 Done)
```

## How It Works

1. **Cache locally:** Import work items from your tracker into a local SQLite DB.
2. **Analyze locally:** Run pattern detection against the cache. No network needed.
3. **Review the signal:** See what needs attention before your standup.
4. **Repeat:** Re-import periodically to refresh the cache.

This "cache-then-analyze" pattern means scans are instant, work offline, and
you control exactly what data leaves your machine.

## Requirements

- Python 3.9+
- No external packages (stdlib + SQLite only)
