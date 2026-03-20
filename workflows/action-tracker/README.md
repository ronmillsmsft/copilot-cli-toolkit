# Ops Playbook Action Tracker

A lightweight CLI tool for managing recurring operational routines, designed to
work alongside your AI assistant (GitHub Copilot CLI, or any LLM-based tool).

## What Is the Ops Playbook Pattern?

Most productive workflows have a rhythm: daily inbox reviews, weekly status
reports, meeting prep sessions, system health checks. These are **recurring
routines** with predictable schedules.

The Ops Playbook pattern treats these routines as first-class objects:

- **Define** each routine with a name, frequency, and schedule
- **Track** when each routine was last run and whether it succeeded
- **Surface** what is due right now so nothing falls through the cracks
- **Measure** time savings by comparing manual effort to automated runs

Each routine includes a `cli_prompt` field, a copy-paste prompt you hand to
your AI assistant when it is time to run that routine.

## How It Integrates with Copilot CLI

The bridge between "I have a recurring task" and "my AI assistant does it" is
the `cli_prompt` field on each routine. The workflow looks like this:

1. Run `python action_tracker.py due` to see what needs attention
2. Pick a routine and copy its CLI prompt
3. Paste the prompt into Copilot CLI (or any AI assistant)
4. When the AI finishes, record the result with `complete`

```
$ python action_tracker.py due

  Due Routines
+-----------------+------------------+-----------+-------------------+
| ID              | Title            | Frequency | Last Run          |
+-----------------+------------------+-----------+-------------------+
| inbox-review    | Daily Inbox Triage | daily   | 2025-01-14 08:00  |
| weekly-status   | Weekly Status    | weekly    | 2025-01-07 09:00  |
+-----------------+------------------+-----------+-------------------+

  CLI Prompt for "inbox-review":
  Review and triage my inbox. Flag anything urgent, summarize key threads,
  and draft quick replies for routine messages.
```

You copy that prompt, paste it into Copilot CLI, and let the AI do the work.
Then record what happened:

```
$ python action_tracker.py run inbox-review
  Started run #42 for "Daily Inbox Triage"

$ python action_tracker.py complete 42 --status success --summary "Triaged 12 emails, flagged 2 urgent"
  Completed run #42 in 3 minutes (estimated manual: 15 min)
```

## How to Customize

### Add Your Own Routines

Use the interactive `add` command:

```
$ python action_tracker.py add
```

This walks you through setting up a new routine: title, description, frequency,
schedule days, and the CLI prompt your AI assistant should use.

You can also edit the SQLite database directly. The schema is intentionally
simple so you can modify it with any SQLite tool.

### Change Frequencies

Supported frequencies:
- **daily** - Runs every day (supports `times_per_day` for multiple runs)
- **weekly** - Runs on specific days (set `schedule_days` to "Mon,Wed,Fri" etc.)
- **biweekly** - Runs on schedule days, but only every two weeks
- **monthly** - Runs once per month

### Start with Seeds, Then Customize

Run `python action_tracker.py seed` to populate 3 example routines. These are
generic starting points. Edit or delete them, then add routines that match your
actual workflow.

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `playbook` | List all routines with current status |
| `due` | Show routines that are due now |
| `run <routine_id>` | Start a run, returns a run ID |
| `complete <run_id> [--status STATUS] [--summary "..."]` | Complete a run with results |
| `history [--routine ID] [--days N]` | Show execution history (default: 7 days) |
| `add` | Interactive routine creation |
| `seed` | Seed example routines into the database |

### Options

- `--status` - One of: `success`, `failed`, `skipped` (default: `success`)
- `--summary` - Free-text summary of what happened during the run
- `--routine` - Filter history to a specific routine ID
- `--days` - Number of days of history to show (default: 7)

## Example Output

### Playbook Overview

```
$ python action_tracker.py playbook

  Ops Playbook - All Routines
+--+-----------------+------------------------+-----------+--------------+----------+
|  | ID              | Title                  | Frequency | Last Run     | Status   |
+--+-----------------+------------------------+-----------+--------------+----------+
|# | inbox-review    | Daily Inbox Triage     | daily     | Today 08:00  | success  |
|  | weekly-status   | Weekly Status Report   | weekly    | Jan 07 09:00 | success  |
|  | meeting-prep    | Meeting Prep           | weekly    | Jan 09 14:00 | success  |
+--+-----------------+------------------------+-----------+--------------+----------+

  3 routines, 2 enabled, 1 due now
```

### Run History

```
$ python action_tracker.py history --days 3

  Run History (last 3 days)
+-----+------------------+---------------------+----------+----------+-----------+
| #   | Routine          | Started             | Duration | Status   | Summary   |
+-----+------------------+---------------------+----------+----------+-----------+
| 42  | inbox-review     | 2025-01-14 08:00:12 | 3m       | success  | Triaged   |
| 41  | meeting-prep     | 2025-01-13 14:00:05 | 7m       | success  | Prepped 3 |
| 40  | inbox-review     | 2025-01-13 08:01:30 | 2m       | success  | Quick day |
+-----+------------------+---------------------+----------+----------+-----------+
```

## Technical Notes

- **Zero dependencies.** Python stdlib + SQLite only. No pip install needed.
- **Portable.** The database is a single `.db` file you can move or back up.
- **Single-user safe.** SQLite handles concurrent reads well, and single-user
  CLI usage avoids write contention entirely.
- **Python 3.9+.** Uses `datetime.now(timezone.utc)` (not the deprecated
  `datetime.utcnow()`).

## File Structure

```
action-tracker/
  README.md             # This file
  action_tracker.py     # The CLI tool
  ops_playbook.db       # Created on first run (SQLite database)
```
