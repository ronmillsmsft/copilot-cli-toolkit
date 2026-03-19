"""Database initialization and schema setup for Agent Memory."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")


def get_schema_sql():
    """Return the full schema DDL."""
    return """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        summary TEXT,
        tags TEXT
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    );

    CREATE TABLE IF NOT EXISTS preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5 CHECK(confidence >= 0.0 AND confidence <= 1.0),
        source_conversation_id TEXT,
        learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_conversation_id) REFERENCES conversations(id),
        UNIQUE(category, key)
    );

    CREATE TABLE IF NOT EXISTS insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('decision', 'pattern', 'goal', 'context')),
        content TEXT NOT NULL,
        conversation_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        superseded_by INTEGER REFERENCES insights(id),
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    );

    -- Full-text search index across messages
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
        content,
        content_rowid='id',
        content='messages'
    );

    -- Full-text search index across insights
    CREATE VIRTUAL TABLE IF NOT EXISTS insights_fts USING fts5(
        content,
        content_rowid='id',
        content='insights'
    );

    -- Triggers to keep FTS index in sync
    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
    END;

    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    END;

    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
    END;

    -- Triggers to keep insights FTS index in sync
    CREATE TRIGGER IF NOT EXISTS insights_fts_ai AFTER INSERT ON insights BEGIN
        INSERT INTO insights_fts(rowid, content) VALUES (new.id, new.content);
    END;

    CREATE TRIGGER IF NOT EXISTS insights_fts_ad AFTER DELETE ON insights BEGIN
        INSERT INTO insights_fts(insights_fts, rowid, content) VALUES('delete', old.id, old.content);
    END;

    CREATE TRIGGER IF NOT EXISTS insights_fts_au AFTER UPDATE ON insights BEGIN
        INSERT INTO insights_fts(insights_fts, rowid, content) VALUES('delete', old.id, old.content);
        INSERT INTO insights_fts(rowid, content) VALUES (new.id, new.content);
    END;

    -- Preference history table
    CREATE TABLE IF NOT EXISTS preference_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        old_value TEXT NOT NULL,
        new_value TEXT NOT NULL,
        old_confidence REAL,
        new_confidence REAL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
    CREATE INDEX IF NOT EXISTS idx_preferences_category ON preferences(category);
    CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(type);
    CREATE INDEX IF NOT EXISTS idx_insights_active ON insights(active);
    CREATE INDEX IF NOT EXISTS idx_conversations_started ON conversations(started_at);
    CREATE INDEX IF NOT EXISTS idx_pref_history_cat_key ON preference_history(category, key);
    """


def initialize_db(db_path=None):
    """Create the database and all tables."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.executescript(get_schema_sql())
    conn.commit()
    conn.close()
    print(f"Database initialized at: {path}")
    return path


if __name__ == "__main__":
    initialize_db()
