# Meeting Prep Pipeline

A structured workflow for recurring meeting preparation that pairs **deterministic data** (configs, topics, history) with **AI enrichment** (live context, summaries, action items).

## What Is This?

The Meeting Prep Pipeline is a pattern built on three ideas:

1. **Meeting Configs** - Define your recurring meetings once (cadence, stakeholders, data sources, prep templates). These rarely change.
2. **Topic Tracking** - Carry discussion topics across meetings. Topics persist until resolved, so nothing falls through the cracks.
3. **Prep Generation** - On demand, produce a structured JSON skeleton containing everything an AI assistant needs to generate a rich, context-aware prep document.

The key insight: your meetings are *predictable structures* with *variable content*. The script handles the structure; AI handles the content.

## How It Integrates with Copilot CLI

The pipeline follows a "skeleton + AI enrichment" pattern:

```
meeting_prep.py prep weekly-standup
  --> Outputs structured JSON (topics, attendees, data sources, template)
    --> Copilot CLI reads the JSON and enriches it with live data
      --> Final prep doc with real context from your actual tools
```

In practice, you might run:

```bash
# Generate the skeleton
python meeting_prep.py prep project-review > prep.json

# Ask Copilot CLI to enrich it
# (Copilot reads the JSON, pulls from the listed data sources,
#  and fills in the template with real information)
```

Copilot CLI can use the `data_sources` field to know *where* to look (ADO queries, email threads, Slack channels) and the `prep_template` to know *what format* to produce.

## How to Customize

### Add Your Own Meetings

Edit the `seed` data in `meeting_prep.py`, or use the CLI directly:

```bash
# The seed command loads example meetings to get you started
python meeting_prep.py seed

# Then customize by editing the SQLite database directly,
# or modify the seed_meetings() function with your own configs
```

Each meeting config supports:

| Field | Purpose |
|-------|---------|
| `id` | URL-friendly slug (e.g., `weekly-standup`) |
| `name` | Display name |
| `cadence` | `weekly`, `biweekly`, or `monthly` |
| `day_of_week` | `Monday` through `Friday` |
| `time` | Display time (e.g., `10:00 AM`) |
| `stakeholder` | Primary stakeholder or meeting owner |
| `attendees` | JSON array of attendee names |
| `purpose` | One-line description of the meeting's goal |
| `data_sources` | JSON array of where to pull context from |
| `prep_template` | Markdown template for the prep output |
| `notes` | Freeform notes about the meeting |

### Change Data Sources

The `data_sources` field is a JSON array of strings. These are labels that tell Copilot CLI where to look for context. Examples:

```json
["ADO sprint board", "email threads", "Slack #project-channel"]
["GitHub PRs", "deployment logs", "Jira backlog"]
["shared OneNote", "Teams chat history"]
```

### Customize Prep Templates

The `prep_template` field is a Markdown string that defines the output structure:

```markdown
## Status Update
## Blockers
## Decisions Needed
## Action Items
```

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `python meeting_prep.py list` | List all configured meetings |
| `python meeting_prep.py prep <meeting_id>` | Generate a prep skeleton (JSON) |
| `python meeting_prep.py topic add <meeting_id> "text"` | Add a discussion topic |
| `python meeting_prep.py topic list <meeting_id>` | List active topics for a meeting |
| `python meeting_prep.py topic done <topic_id>` | Mark a topic as discussed |
| `python meeting_prep.py upcoming` | Show meetings in the next 7 days |
| `python meeting_prep.py upcoming --days 14` | Show meetings in the next N days |
| `python meeting_prep.py history <meeting_id>` | Show prep generation history |
| `python meeting_prep.py seed` | Load example meeting configurations |

## Example Workflow

```bash
# 1. First time setup - seed example meetings
python meeting_prep.py seed

# 2. See what meetings are configured
python meeting_prep.py list

# 3. Check what's coming up this week
python meeting_prep.py upcoming --days 7

# 4. Add topics as they come up during the week
python meeting_prep.py topic add team-standup "API migration timeline"
python meeting_prep.py topic add team-standup "New hire onboarding checklist"
python meeting_prep.py topic add project-review "Q3 milestone risk assessment"

# 5. Before a meeting, review active topics
python meeting_prep.py topic list team-standup

# 6. Generate the prep skeleton for Copilot CLI to enrich
python meeting_prep.py prep team-standup

# 7. After the meeting, mark discussed topics as done
python meeting_prep.py topic done 1
python meeting_prep.py topic done 2

# 8. Review past prep history
python meeting_prep.py history team-standup
```

## Database

The script uses a local SQLite database (`meeting_prep.db`) stored alongside the script. The database is created automatically on first run. No external dependencies required.

## Requirements

- Python 3.9+ (uses `datetime.now(timezone.utc)`)
- No external packages needed (stdlib + SQLite only)
