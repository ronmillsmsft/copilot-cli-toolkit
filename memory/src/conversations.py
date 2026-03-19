"""Conversation storage and retrieval."""

import uuid
from datetime import datetime, timezone
from .db import db_session, rows_to_dicts, row_to_dict


def start_conversation(title=None, tags=None, db_path=None):
    """Start a new conversation. Returns the conversation ID."""
    conv_id = str(uuid.uuid4())
    with db_session(db_path) as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, started_at, tags) VALUES (?, ?, ?, ?)",
            (conv_id, title, datetime.now(timezone.utc).isoformat(), tags),
        )
    return conv_id


def add_message(conversation_id, role, content, db_path=None):
    """Add a message to a conversation. Role must be 'user' or 'assistant'."""
    with db_session(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
    return cursor.lastrowid


def end_conversation(conversation_id, summary=None, db_path=None):
    """Mark a conversation as ended, optionally with a summary."""
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET ended_at = ?, summary = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), summary, conversation_id),
        )


def get_conversation(conversation_id, db_path=None):
    """Get a conversation with all its messages."""
    with db_session(db_path) as conn:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if conv is None:
            return None
        messages = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,),
        ).fetchall()
    result = row_to_dict(conv)
    result["messages"] = rows_to_dicts(messages)
    return result


def list_conversations(limit=20, offset=0, tag=None, db_path=None):
    """List conversations, newest first. Optionally filter by tag."""
    with db_session(db_path) as conn:
        if tag:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE tags LIKE ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (f"%{tag}%", limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversations ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return rows_to_dicts(rows)


def update_conversation(conversation_id, title=None, summary=None, tags=None, db_path=None):
    """Update conversation metadata."""
    updates = []
    params = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)
    if tags is not None:
        updates.append("tags = ?")
        params.append(tags)
    if not updates:
        return
    params.append(conversation_id)
    with db_session(db_path) as conn:
        conn.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?", params
        )


def get_recent_messages(limit=50, role=None, db_path=None):
    """Get the most recent messages across all conversations."""
    with db_session(db_path) as conn:
        if role:
            rows = conn.execute(
                "SELECT m.*, c.title as conversation_title FROM messages m "
                "JOIN conversations c ON m.conversation_id = c.id "
                "WHERE m.role = ? ORDER BY m.timestamp DESC LIMIT ?",
                (role, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT m.*, c.title as conversation_title FROM messages m "
                "JOIN conversations c ON m.conversation_id = c.id "
                "ORDER BY m.timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return rows_to_dicts(rows)


def count_conversations(db_path=None):
    """Return total conversation count."""
    with db_session(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()
    return row["cnt"]
