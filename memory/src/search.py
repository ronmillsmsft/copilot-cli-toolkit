"""Full-text search and context retrieval across memory."""

from .db import db_session, rows_to_dicts


def search_messages(query, limit=20, db_path=None):
    """Full-text search across all stored messages using FTS5."""
    with db_session(db_path) as conn:
        rows = conn.execute(
            """SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp,
                      c.title as conversation_title,
                      highlight(messages_fts, 0, '>>>', '<<<') as highlighted
               FROM messages_fts fts
               JOIN messages m ON fts.rowid = m.id
               JOIN conversations c ON m.conversation_id = c.id
               WHERE messages_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
    return rows_to_dicts(rows)


def search_insights(query, limit=20, db_path=None):
    """Full-text search across insights using FTS5."""
    with db_session(db_path) as conn:
        # Try FTS5 first; fall back to LIKE if FTS table doesn't exist yet
        try:
            rows = conn.execute(
                """SELECT i.id, i.type, i.content, i.created_at, i.active,
                          i.updated_at, i.superseded_by,
                          highlight(insights_fts, 0, '>>>', '<<<') as highlighted
                   FROM insights_fts fts
                   JOIN insights i ON fts.rowid = i.id
                   WHERE insights_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        except Exception:
            # Fallback for pre-migration databases
            rows = conn.execute(
                "SELECT *, content as highlighted FROM insights WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
    return rows_to_dicts(rows)


def search_preferences(query, db_path=None):
    """Search preferences by key or value."""
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM preferences WHERE key LIKE ? OR value LIKE ? ORDER BY category, key",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    return rows_to_dicts(rows)


def search_all(query, limit=20, db_path=None):
    """Search across messages, preferences, and insights. Returns combined results."""
    return {
        "messages": search_messages(query, limit, db_path),
        "preferences": search_preferences(query, db_path),
        "insights": search_insights(query, limit, db_path),
    }


def get_context_summary(db_path=None):
    """Get a high-level summary of what's stored in memory."""
    with db_session(db_path) as conn:
        conv_count = conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]
        msg_count = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
        pref_count = conn.execute("SELECT COUNT(*) as cnt FROM preferences").fetchone()["cnt"]
        insight_count = conn.execute("SELECT COUNT(*) as cnt FROM insights WHERE active = 1").fetchone()["cnt"]
        archived_insight_count = conn.execute("SELECT COUNT(*) as cnt FROM insights WHERE active = 0").fetchone()["cnt"]
        pref_history_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM preference_history"
        ).fetchone()["cnt"] if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='preference_history'"
        ).fetchone() else 0

        recent_convs = conn.execute(
            "SELECT id, title, started_at, tags FROM conversations ORDER BY started_at DESC LIMIT 5"
        ).fetchall()

        top_categories = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM preferences GROUP BY category ORDER BY cnt DESC"
        ).fetchall()

    return {
        "total_conversations": conv_count,
        "total_messages": msg_count,
        "total_preferences": pref_count,
        "total_insights": insight_count,
        "archived_insights": archived_insight_count,
        "preference_changes": pref_history_count,
        "recent_conversations": rows_to_dicts(recent_convs),
        "preference_categories": rows_to_dicts(top_categories),
    }
