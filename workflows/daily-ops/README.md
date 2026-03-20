# Daily Ops - Aggregation Scanner

Daily Ops is the "morning briefing" layer for your workflow toolkit. It scans across all your other workflow databases (action tracker, meeting prep, standup prep) and consolidates everything into a single status report. Think of it as the read-only dashboard that ties the Tier 3 tools together.

## How It Fits Together

```
daily-ops (this tool)
  |
  +-- reads from --> action-tracker/action_tracker.db
  |                    - Overdue action items
  |                    - Stale items (untouched 14+ days)
  |                    - Playbook routines due now
  |                    - Action item stats
  |
  +-- reads from --> meeting-prep/meeting_prep.db
  |                    - Meetings in the next 3 days
  |                    - Active discussion topics per meeting
  |
  +-- reads from --> standup-prep/standup_prep.db
                       - Most recent scan results
```

Daily Ops never writes to any database. It is purely a reader and aggregator. Each tool owns its own data; Daily Ops just surfaces what matters right now.

## Boot Sequence Integration

The real power of Daily Ops is running it automatically at every Copilot CLI session start. This gives your AI assistant immediate context about what needs attention.

**How to wire it in:**

Add this to your `copilot-instructions.md` or agent startup config:

```
At session start, run: python daily_ops.py scan
Surface any warnings or due items in your greeting to the user.
```

This turns your assistant from reactive ("what should I work on?") to proactive ("Hey, you have 2 overdue items and a meeting in 3 hours").

## CLI Commands

### Full Scan

```bash
python daily_ops.py scan
```

Runs all checks across every reachable database and prints a consolidated report. If a database file is missing, that section is skipped with an info note.

### Health Check

```bash
python daily_ops.py status
```

Quick check showing which databases are found and reachable. Useful for verifying your setup.

## Example Output

```
+==================================================+
|  Daily Ops Scan - 2026-03-20 08:15 UTC           |
+==================================================+

--- ACTION ITEMS ---

  No overdue action items.

  STALE ITEMS (2)
    - "Update API docs" (18 days untouched)
    - "Review PR #42" (15 days untouched)

--- OPS PLAYBOOK - DUE NOW (1) ---

    Weekly Status Report     weekly     status-agent

--- UPCOMING MEETINGS (next 3 days) ---

    Mon 03/22  09:30  Team Standup (2 active topics)
    Wed 03/24  14:00  Project Review (4 active topics)

--- STANDUP PREP ---

    Last scan: 2026-03-19 17:00 UTC (12 items, 3 flagged)

--- SUMMARY ---

    Action Items: 5 open, 3 in progress, 12 done
```

## Graceful Degradation

Not all workflow tools need to be installed at once. If a database file is missing, Daily Ops skips that section cleanly:

```
  [info] action_tracker.db not found - skipping action item checks
```

This lets you adopt tools incrementally. Start with just the action tracker, add meeting prep later, and Daily Ops adapts automatically.

## Requirements

- Python 3.9+ (stdlib only, zero external dependencies)
- SQLite databases created by the sibling workflow tools

## File Layout

```
copilot-cli-toolkit/workflows/
  daily-ops/
    daily_ops.py      <-- this scanner
    README.md         <-- you are here
  action-tracker/
    action_tracker.db
  meeting-prep/
    meeting_prep.db
  standup-prep/
    standup_prep.db
```
