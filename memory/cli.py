#!/usr/bin/env python3
"""Agent Memory CLI — interact with your memory database from the terminal."""

import argparse
import json
import sys
import os

# Add parent dir to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.conversations import (
    start_conversation, add_message, end_conversation,
    get_conversation, list_conversations, count_conversations,
)
from src.preferences import (
    add_preference, list_all_preferences, get_preferences_by_category,
    add_insight, get_insights, get_all_insights, list_categories,
    archive_insight, activate_insight, update_insight, supersede_insight,
    get_preference_history,
)
from src.search import search_all, search_messages, get_context_summary
from setup_db import initialize_db


def fmt_json(data):
    """Pretty-print data as JSON."""
    print(json.dumps(data, indent=2, default=str))


# ── Commands ──────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize the database."""
    initialize_db()


def cmd_log(args):
    """Log a quick interaction (single user message + assistant response)."""
    conv_id = start_conversation(title=args.title, tags=args.tags)
    add_message(conv_id, "user", args.user)
    if args.assistant:
        add_message(conv_id, "assistant", args.assistant)
    if args.summary:
        end_conversation(conv_id, summary=args.summary)
    else:
        end_conversation(conv_id)
    print(f"Logged conversation: {conv_id}")


def cmd_start(args):
    """Start a new conversation (for multi-message logging)."""
    conv_id = start_conversation(title=args.title, tags=args.tags)
    print(conv_id)


def cmd_msg(args):
    """Add a message to an existing conversation."""
    msg_id = add_message(args.conversation_id, args.role, args.content)
    print(f"Added message {msg_id}")


def cmd_end(args):
    """End a conversation."""
    end_conversation(args.conversation_id, summary=args.summary)
    print("Conversation ended.")


def cmd_show(args):
    """Show a conversation with all messages."""
    conv = get_conversation(args.conversation_id)
    if conv is None:
        print("Conversation not found.")
        return
    print(f"\n{'='*60}")
    print(f"  {conv['title'] or 'Untitled'}")
    print(f"  Started: {conv['started_at']}")
    if conv['tags']:
        print(f"  Tags: {conv['tags']}")
    if conv['summary']:
        print(f"  Summary: {conv['summary']}")
    print(f"{'='*60}")
    for msg in conv["messages"]:
        role_label = "YOU" if msg["role"] == "user" else "AI "
        print(f"\n  [{role_label}] {msg['timestamp']}")
        print(f"  {msg['content']}")
    print()


def cmd_list(args):
    """List recent conversations."""
    convs = list_conversations(limit=args.limit, tag=args.tag)
    if not convs:
        print("No conversations found.")
        return
    total = count_conversations()
    print(f"\nShowing {len(convs)} of {total} conversations:\n")
    for c in convs:
        title = c["title"] or "Untitled"
        tags = f" [{c['tags']}]" if c["tags"] else ""
        print(f"  {c['started_at'][:10]}  {title}{tags}")
        print(f"           ID: {c['id']}")
        if c["summary"]:
            print(f"           Summary: {c['summary'][:80]}")
        print()


def cmd_pref(args):
    """Manage preferences."""
    if args.action == "add":
        add_preference(args.category, args.key, args.value, confidence=args.confidence or 0.5)
        print(f"Preference set: [{args.category}] {args.key} = {args.value}")
    elif args.action == "list":
        if args.category:
            prefs = get_preferences_by_category(args.category)
        else:
            prefs = list_all_preferences()
        if not prefs:
            print("No preferences found.")
            return
        current_cat = None
        for p in prefs:
            if p["category"] != current_cat:
                current_cat = p["category"]
                print(f"\n  [{current_cat}]")
            conf = f" (confidence: {p['confidence']:.1f})" if p["confidence"] != 0.5 else ""
            print(f"    {p['key']}: {p['value']}{conf}")
        print()
    elif args.action == "categories":
        cats = list_categories()
        if not cats:
            print("No categories found.")
            return
        print("\nPreference categories:")
        for c in cats:
            print(f"  - {c}")
        print()
    elif args.action == "history":
        history = get_preference_history(
            category=args.category, key=args.key, limit=args.limit or 20
        )
        if not history:
            print("No preference changes found.")
            return
        print("\nPreference change history:")
        for h in history:
            print(f"  [{h['category']}] {h['key']}")
            print(f"    {h['old_value']} → {h['new_value']}")
            conf_change = ""
            if h['old_confidence'] is not None and h['new_confidence'] is not None:
                conf_change = f"  (confidence: {h['old_confidence']:.1f} → {h['new_confidence']:.1f})"
            print(f"    Changed: {h['changed_at']}{conf_change}")
        print()


def cmd_insight(args):
    """Manage insights."""
    if args.action == "add":
        add_insight(args.type, args.content)
        print(f"Insight added: [{args.type}] {args.content[:60]}")
    elif args.action == "list":
        insights = get_insights(type_=args.type, limit=args.limit)
        if not insights:
            print("No active insights found.")
            return
        for i in insights:
            print(f"  [{i['type']}] {i['content']}")
            print(f"          ID: {i['id']}  {i['created_at']}")
        print()
    elif args.action == "all":
        insights = get_all_insights(type_=args.type, limit=args.limit)
        if not insights:
            print("No insights found.")
            return
        for i in insights:
            status = "" if i.get("active", 1) else " [ARCHIVED]"
            superseded = f" → #{i['superseded_by']}" if i.get("superseded_by") else ""
            print(f"  [{i['type']}]{status}{superseded} {i['content']}")
            print(f"          ID: {i['id']}  {i['created_at']}")
        print()
    elif args.action == "archive":
        if not args.id:
            print("Error: --id required for archive")
            return
        archive_insight(args.id)
        print(f"Insight #{args.id} archived.")
    elif args.action == "activate":
        if not args.id:
            print("Error: --id required for activate")
            return
        activate_insight(args.id)
        print(f"Insight #{args.id} re-activated.")
    elif args.action == "update":
        if not args.id:
            print("Error: --id required for update")
            return
        update_insight(args.id, content=args.content, type_=args.type)
        print(f"Insight #{args.id} updated.")
    elif args.action == "supersede":
        if not args.id or not args.content:
            print("Error: --id and --content required for supersede")
            return
        new_id = supersede_insight(args.id, args.content, type_=args.type)
        print(f"Insight #{args.id} superseded by new insight #{new_id}.")


def cmd_search(args):
    """Search across all memory."""
    if args.messages_only:
        results = search_messages(args.query, limit=args.limit)
        if not results:
            print("No matching messages found.")
            return
        for r in results:
            role = "YOU" if r["role"] == "user" else "AI "
            print(f"  [{role}] {r['conversation_title'] or 'Untitled'} ({r['timestamp'][:10]})")
            print(f"        {r['highlighted']}")
            print()
    else:
        results = search_all(args.query, limit=args.limit)
        found = False
        if results["messages"]:
            found = True
            print(f"\n  Messages ({len(results['messages'])} matches):")
            for r in results["messages"]:
                print(f"    [{r['role']}] {r['highlighted']}")
        if results["preferences"]:
            found = True
            print(f"\n  Preferences ({len(results['preferences'])} matches):")
            for r in results["preferences"]:
                print(f"    [{r['category']}] {r['key']}: {r['value']}")
        if results["insights"]:
            found = True
            print(f"\n  Insights ({len(results['insights'])} matches):")
            for r in results["insights"]:
                print(f"    [{r['type']}] {r['content']}")
        if not found:
            print("No results found.")
        print()


def cmd_status(args):
    """Show memory status summary."""
    summary = get_context_summary()
    print(f"\n  Agent Memory Status")
    print(f"  {'─'*40}")
    print(f"  Conversations:  {summary['total_conversations']}")
    print(f"  Messages:       {summary['total_messages']}")
    print(f"  Preferences:    {summary['total_preferences']}")
    print(f"  Insights:       {summary['total_insights']} active", end="")
    if summary.get('archived_insights', 0) > 0:
        print(f", {summary['archived_insights']} archived", end="")
    print()
    if summary.get('preference_changes', 0) > 0:
        print(f"  Pref changes:   {summary['preference_changes']}")
    if summary["preference_categories"]:
        print(f"\n  Preference categories:")
        for cat in summary["preference_categories"]:
            print(f"    {cat['category']}: {cat['cnt']} items")
    if summary["recent_conversations"]:
        print(f"\n  Recent conversations:")
        for c in summary["recent_conversations"]:
            print(f"    {c['started_at'][:10]}  {c['title'] or 'Untitled'}")
    print()


def cmd_export(args):
    """Export all memory as JSON."""
    from src.conversations import list_conversations, get_conversation
    from src.preferences import list_all_preferences
    from src.search import get_context_summary

    convs = list_conversations(limit=9999)
    full_convs = [get_conversation(c["id"]) for c in convs]
    prefs = list_all_preferences()
    insights = get_insights(limit=9999)

    data = {
        "conversations": full_convs,
        "preferences": prefs,
        "insights": insights,
        "summary": get_context_summary(),
    }
    output = json.dumps(data, indent=2, default=str)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Exported to {args.output}")
    else:
        print(output)


# ── Argument Parser ───────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent-memory",
        description="Agent Memory — persistent memory for AI assistant interactions",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="Initialize the database")

    # log (quick single interaction)
    p = sub.add_parser("log", help="Log a quick interaction")
    p.add_argument("user", help="Your message")
    p.add_argument("-a", "--assistant", help="Assistant's response")
    p.add_argument("-t", "--title", help="Conversation title")
    p.add_argument("--tags", help="Comma-separated tags")
    p.add_argument("-s", "--summary", help="Conversation summary")

    # start (multi-message conversation)
    p = sub.add_parser("start", help="Start a new conversation")
    p.add_argument("-t", "--title", help="Conversation title")
    p.add_argument("--tags", help="Comma-separated tags")

    # msg
    p = sub.add_parser("msg", help="Add a message to a conversation")
    p.add_argument("conversation_id", help="Conversation ID")
    p.add_argument("role", choices=["user", "assistant"], help="Message role")
    p.add_argument("content", help="Message content")

    # end
    p = sub.add_parser("end", help="End a conversation")
    p.add_argument("conversation_id", help="Conversation ID")
    p.add_argument("-s", "--summary", help="Conversation summary")

    # show
    p = sub.add_parser("show", help="Show a conversation")
    p.add_argument("conversation_id", help="Conversation ID")

    # list
    p = sub.add_parser("list", help="List recent conversations")
    p.add_argument("-n", "--limit", type=int, default=10, help="Max results")
    p.add_argument("--tag", help="Filter by tag")

    # pref
    p = sub.add_parser("pref", help="Manage preferences")
    p.add_argument("action", choices=["add", "list", "categories", "history"])
    p.add_argument("--category", "-c", help="Preference category")
    p.add_argument("--key", "-k", help="Preference key")
    p.add_argument("--value", "-v", help="Preference value")
    p.add_argument("--confidence", type=float, help="Confidence 0.0-1.0")
    p.add_argument("-n", "--limit", type=int, help="Max results (for history)")

    # insight
    p = sub.add_parser("insight", help="Manage insights")
    p.add_argument("action", choices=["add", "list", "all", "archive", "activate", "update", "supersede"])
    p.add_argument("--type", "-t", choices=["decision", "pattern", "goal", "context"])
    p.add_argument("--content", help="Insight content")
    p.add_argument("--id", type=int, help="Insight ID (for archive/activate/update/supersede)")
    p.add_argument("-n", "--limit", type=int, default=20)

    # search
    p = sub.add_parser("search", help="Search across all memory")
    p.add_argument("query", help="Search query")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.add_argument("-m", "--messages-only", action="store_true")

    # status
    sub.add_parser("status", help="Show memory status summary")

    # export
    p = sub.add_parser("export", help="Export all memory as JSON")
    p.add_argument("-o", "--output", help="Output file path")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "init": cmd_init,
        "log": cmd_log,
        "start": cmd_start,
        "msg": cmd_msg,
        "end": cmd_end,
        "show": cmd_show,
        "list": cmd_list,
        "pref": cmd_pref,
        "insight": cmd_insight,
        "search": cmd_search,
        "status": cmd_status,
        "export": cmd_export,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
