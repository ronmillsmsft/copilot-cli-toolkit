"""Preference and personality trait storage and retrieval."""

from datetime import datetime, timezone
from .db import db_session, rows_to_dicts, row_to_dict


def add_preference(category, key, value, confidence=0.5, conversation_id=None, db_path=None):
    """Add or update a user preference. Uses UPSERT on (category, key).
    Logs old value to preference_history when updating an existing preference."""
    now = datetime.now(timezone.utc).isoformat()
    with db_session(db_path) as conn:
        # Check for existing value to log history
        existing = conn.execute(
            "SELECT value, confidence FROM preferences WHERE category = ? AND key = ?",
            (category, key),
        ).fetchone()

        if existing and (existing["value"] != value or existing["confidence"] != confidence):
            conn.execute(
                """INSERT INTO preference_history
                   (category, key, old_value, new_value, old_confidence, new_confidence, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (category, key, existing["value"], value,
                 existing["confidence"], confidence, now),
            )

        conn.execute(
            """INSERT INTO preferences (category, key, value, confidence, source_conversation_id, learned_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(category, key) DO UPDATE SET
                   value = excluded.value,
                   confidence = MAX(excluded.confidence, preferences.confidence),
                   updated_at = excluded.updated_at""",
            (category, key, value, confidence, conversation_id, now, now),
        )


def get_preference(category, key, db_path=None):
    """Get a specific preference by category and key."""
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM preferences WHERE category = ? AND key = ?",
            (category, key),
        ).fetchone()
    return row_to_dict(row)


def get_preferences_by_category(category, db_path=None):
    """Get all preferences in a category."""
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM preferences WHERE category = ? ORDER BY key",
            (category,),
        ).fetchall()
    return rows_to_dicts(rows)


def list_all_preferences(db_path=None):
    """List every stored preference, grouped by category."""
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM preferences ORDER BY category, key"
        ).fetchall()
    return rows_to_dicts(rows)


def list_categories(db_path=None):
    """List all unique preference categories."""
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM preferences ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]


def update_confidence(category, key, new_confidence, db_path=None):
    """Update the confidence score of a preference."""
    now = datetime.now(timezone.utc).isoformat()
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE preferences SET confidence = ?, updated_at = ? WHERE category = ? AND key = ?",
            (new_confidence, now, category, key),
        )


def remove_preference(category, key, db_path=None):
    """Delete a preference."""
    with db_session(db_path) as conn:
        conn.execute(
            "DELETE FROM preferences WHERE category = ? AND key = ?",
            (category, key),
        )


def add_insight(type_, content, conversation_id=None, db_path=None):
    """Store an insight (decision, pattern, goal, or context)."""
    with db_session(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO insights (type, content, conversation_id) VALUES (?, ?, ?)",
            (type_, content, conversation_id),
        )
    return cursor.lastrowid


def get_insights(type_=None, limit=20, db_path=None):
    """Get insights, optionally filtered by type. Only returns active insights by default."""
    with db_session(db_path) as conn:
        if type_:
            rows = conn.execute(
                "SELECT * FROM insights WHERE type = ? AND active = 1 ORDER BY created_at DESC LIMIT ?",
                (type_, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM insights WHERE active = 1 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)


def get_all_insights(type_=None, limit=50, db_path=None):
    """Get ALL insights including archived ones."""
    with db_session(db_path) as conn:
        if type_:
            rows = conn.execute(
                "SELECT * FROM insights WHERE type = ? ORDER BY active DESC, created_at DESC LIMIT ?",
                (type_, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM insights ORDER BY active DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)


def archive_insight(insight_id, db_path=None):
    """Mark an insight as inactive (archived). Does not delete it."""
    now = datetime.now(timezone.utc).isoformat()
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE insights SET active = 0, updated_at = ? WHERE id = ?",
            (now, insight_id),
        )


def activate_insight(insight_id, db_path=None):
    """Re-activate an archived insight."""
    now = datetime.now(timezone.utc).isoformat()
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE insights SET active = 1, updated_at = ? WHERE id = ?",
            (now, insight_id),
        )


def update_insight(insight_id, content=None, type_=None, db_path=None):
    """Update an insight's content or type."""
    now = datetime.now(timezone.utc).isoformat()
    updates = ["updated_at = ?"]
    params = [now]
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if type_ is not None:
        updates.append("type = ?")
        params.append(type_)
    params.append(insight_id)
    with db_session(db_path) as conn:
        conn.execute(
            f"UPDATE insights SET {', '.join(updates)} WHERE id = ?", params
        )


def supersede_insight(old_id, new_content, type_=None, conversation_id=None, db_path=None):
    """Create a new insight that supersedes an old one. Archives the old insight."""
    now = datetime.now(timezone.utc).isoformat()
    with db_session(db_path) as conn:
        # Get old insight's type if not provided
        if type_ is None:
            old = conn.execute("SELECT type FROM insights WHERE id = ?", (old_id,)).fetchone()
            if old:
                type_ = old["type"]
            else:
                type_ = "context"

        # Create the new insight
        cursor = conn.execute(
            "INSERT INTO insights (type, content, conversation_id, updated_at) VALUES (?, ?, ?, ?)",
            (type_, new_content, conversation_id, now),
        )
        new_id = cursor.lastrowid

        # Archive and link the old one
        conn.execute(
            "UPDATE insights SET active = 0, superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_id, now, old_id),
        )
    return new_id


def get_preference_history(category=None, key=None, limit=20, db_path=None):
    """Get preference change history, optionally filtered by category/key."""
    with db_session(db_path) as conn:
        if category and key:
            rows = conn.execute(
                "SELECT * FROM preference_history WHERE category = ? AND key = ? ORDER BY changed_at DESC LIMIT ?",
                (category, key, limit),
            ).fetchall()
        elif category:
            rows = conn.execute(
                "SELECT * FROM preference_history WHERE category = ? ORDER BY changed_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM preference_history ORDER BY changed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)
