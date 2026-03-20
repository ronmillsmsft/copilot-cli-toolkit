#!/usr/bin/env python3
"""
Copilot CLI Toolkit Updater
============================
Self-contained script that updates toolkit components from the GitHub repo
while protecting user-customized files. Zero external dependencies.

Commands:
    check   - Check if updates are available (no changes made)
    update  - Download and apply updates (with backup)
    status  - Show current version, last update date, file inventory
    restore - List available backups and restore a specific one
    diff    - Show what would change for a specific file

Usage:
    python toolkit-update.py check
    python toolkit-update.py update [--yes]
    python toolkit-update.py status
    python toolkit-update.py restore
    python toolkit-update.py diff <file>
"""

import argparse
import filecmp
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_OWNER = "ronmillsmsft"
REPO_NAME = "copilot-cli-toolkit"
BRANCH = "master"

# GitHub API endpoints (public, no auth required)
API_COMMITS_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{BRANCH}"
)
API_ZIPBALL_URL = (
    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/zipball/{BRANCH}"
)

# Local marker files
VERSION_FILE = ".toolkit-version"
BACKUP_DIR = ".toolkit-backup"

# ---------------------------------------------------------------------------
# File classification lists
# ---------------------------------------------------------------------------

# USER FILES - never overwrite. Patterns checked with exact match or glob-style
# prefix matching. These represent personalized content.
USER_FILE_PATTERNS = [
    "copilot-instructions.md",          # found in starter/ or any location
    "USER.md",                          # in instructions/ or root
    "SOUL.md",                          # in instructions/ or root
    "memory/memory.db",                 # persistent memory database
    "seed-memory.sh",                   # user's memory seeding script
]

# Any .db file is user data; protected separately via extension check.
USER_EXTENSIONS = [".db"]

# Directories that are entirely user-owned; anything inside is protected.
USER_DIRECTORIES = [
    "instructions",
]

# TOOLKIT FILES - safe to replace during updates. Relative to repo root.
TOOLKIT_FILES = [
    "workflows/action-tracker/action_tracker.py",
    "workflows/meeting-prep/meeting_prep.py",
    "workflows/standup-prep/standup_prep.py",
    "workflows/daily-ops/daily_ops.py",
    "advanced/dashboard/ops_dashboard.py",
    "advanced/dashboard/README.md",
    "memory/cli.py",
    "memory/setup_db.py",
    "starter/setup-wizard.html",
    "starter/QUICK-START.md",
    "index.html",
    "README.md",
    "toolkit-update.py",
]

# TOOLKIT GLOB PATTERNS - directories where all files are toolkit-owned.
# We expand these at runtime against the downloaded archive.
TOOLKIT_GLOB_PREFIXES = [
    "workflows/",        # catches workflows/*/README.md and sub-files
    "memory/src/",       # memory/src/*
    "docs/",             # docs/*
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_toolkit_root() -> Path:
    """Return the toolkit root directory (where this script lives)."""
    return Path(__file__).resolve().parent


def github_api_get(url: str) -> dict:
    """
    Make a GET request to the GitHub API and return parsed JSON.
    Handles rate limiting and network errors gracefully.
    """
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "copilot-cli-toolkit-updater/1.0")

    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 403:
            # Likely rate-limited
            print(
                "Error: GitHub API rate limit reached (60 requests/hour "
                "for unauthenticated calls)."
            )
            print("Try again later or wait a few minutes.")
            sys.exit(1)
        elif exc.code == 404:
            print(f"Error: Repository or branch not found at {url}")
            sys.exit(1)
        else:
            print(f"Error: GitHub API returned HTTP {exc.code}: {exc.reason}")
            sys.exit(1)
    except URLError as exc:
        print(f"Error: Could not reach GitHub. Check your internet connection.")
        print(f"  Detail: {exc.reason}")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: Unexpected failure contacting GitHub: {exc}")
        sys.exit(1)


def download_zipball(url: str, dest_path: Path) -> None:
    """Download the repo zipball to a local file."""
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "copilot-cli-toolkit-updater/1.0")

    try:
        with urlopen(req, timeout=60) as resp:
            with open(dest_path, "wb") as f:
                # Read in chunks to handle large archives
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
    except HTTPError as exc:
        if exc.code == 403:
            print("Error: GitHub API rate limit reached while downloading.")
            sys.exit(1)
        print(f"Error: Download failed with HTTP {exc.code}: {exc.reason}")
        sys.exit(1)
    except URLError as exc:
        print(f"Error: Download failed. Check your internet connection.")
        print(f"  Detail: {exc.reason}")
        sys.exit(1)


def load_version_file(root: Path) -> dict | None:
    """
    Load the .toolkit-version file. Returns None if it does not exist
    or cannot be parsed.
    """
    vf = root / VERSION_FILE
    if not vf.exists():
        return None
    try:
        with open(vf, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_version_file(root: Path, commit_sha: str) -> None:
    """Write the .toolkit-version marker with current timestamp."""
    data = {
        "commit_sha": commit_sha,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": f"{REPO_OWNER}/{REPO_NAME}",
        "branch": BRANCH,
    }
    vf = root / VERSION_FILE
    with open(vf, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_user_file(rel_path: str) -> bool:
    """
    Determine if a relative path belongs to the user (protected) category.
    Returns True if the file must NOT be overwritten.
    """
    # Normalize separators to forward slash for comparison
    rel = rel_path.replace("\\", "/")
    basename = os.path.basename(rel)

    # Check extension-based protection (.db files)
    _, ext = os.path.splitext(rel)
    if ext.lower() in USER_EXTENSIONS:
        return True

    # Check exact filename matches (could appear in any directory)
    for pattern in USER_FILE_PATTERNS:
        # If pattern has no directory separator, match the basename anywhere
        if "/" not in pattern:
            if basename == pattern:
                return True
        else:
            # Match exact relative path
            if rel == pattern:
                return True

    # Check if the file lives inside a user-owned directory
    for user_dir in USER_DIRECTORIES:
        if rel.startswith(user_dir + "/") or rel == user_dir:
            return True

    return False


def is_toolkit_file(rel_path: str) -> bool:
    """
    Determine if a relative path belongs to the toolkit (updatable) category.
    Returns True if the file is safe to overwrite during an update.
    """
    rel = rel_path.replace("\\", "/")

    # Exact match against the explicit toolkit file list
    if rel in TOOLKIT_FILES:
        return True

    # Prefix match against toolkit directories
    for prefix in TOOLKIT_GLOB_PREFIXES:
        if rel.startswith(prefix):
            return True

    return False


def classify_file(rel_path: str) -> str:
    """
    Classify a file as 'user', 'toolkit', or 'unknown'.
    User files take priority; if a file matches both lists, it is protected.
    """
    if is_user_file(rel_path):
        return "user"
    if is_toolkit_file(rel_path):
        return "toolkit"
    return "unknown"


def extract_zip_to_dir(zip_path: Path, dest: Path) -> Path:
    """
    Extract a GitHub zipball and return the path to the extracted content.
    GitHub zips contain a single top-level directory like
    'ronmillsmsft-copilot-cli-toolkit-abc1234/'. This function strips
    that prefix and returns the inner directory path.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)

    # Find the single top-level directory GitHub creates
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]

    # Fallback: return dest itself if structure is unexpected
    return dest


def collect_repo_files(repo_dir: Path) -> list[str]:
    """
    Walk the extracted repo directory and return a sorted list of relative
    file paths (using forward slashes).
    """
    files = []
    for dirpath, _dirnames, filenames in os.walk(repo_dir):
        for fn in filenames:
            full = Path(dirpath) / fn
            rel = full.relative_to(repo_dir).as_posix()
            files.append(rel)
    return sorted(files)


def diff_file_contents(old_path: Path, new_path: Path) -> list[str]:
    """
    Produce a simple line-by-line diff between two text files.
    Returns a list of diff lines. Falls back to a binary notice
    if files cannot be decoded as UTF-8.
    """
    try:
        with open(old_path, "r", encoding="utf-8", errors="replace") as f:
            old_lines = f.readlines()
        with open(new_path, "r", encoding="utf-8", errors="replace") as f:
            new_lines = f.readlines()
    except OSError:
        return ["[Could not read one or both files for comparison]"]

    # Simple unified-style diff without importing difflib at module level
    import difflib

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"local/{old_path.name}",
        tofile=f"remote/{new_path.name}",
        lineterm="",
    )
    return [line.rstrip("\n") for line in diff]


def format_date(iso_str: str) -> str:
    """Format an ISO date string to a shorter human-readable form."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso_str or "unknown"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check(root: Path) -> None:
    """Check if updates are available without making any changes."""
    print("Copilot CLI Toolkit Updater")
    print("-" * 40)

    # Load local version info
    version_info = load_version_file(root)
    if version_info:
        local_sha = version_info.get("commit_sha", "unknown")
        local_date = format_date(version_info.get("updated_at", ""))
        print(f"Current version: {local_sha[:7]} (updated {local_date})")
    else:
        local_sha = None
        print("Current version: not tracked (first run)")

    # Fetch latest commit from GitHub
    print("Checking GitHub for updates...")
    commit_data = github_api_get(API_COMMITS_URL)
    remote_sha = commit_data.get("sha", "unknown")
    commit_date_str = (
        commit_data.get("commit", {}).get("committer", {}).get("date", "")
    )
    remote_date = format_date(commit_date_str)

    print(f"Latest version:  {remote_sha[:7]} ({remote_date})")
    print()

    if local_sha and local_sha == remote_sha:
        print("You are up to date. No changes needed.")
    else:
        print("Updates are available!")
        print("Run 'python toolkit-update.py update' to apply them.")


def cmd_update(root: Path, auto_yes: bool = False) -> None:
    """Download and apply updates with backup."""
    print("Copilot CLI Toolkit Updater")
    print("-" * 40)

    # Load local version info
    version_info = load_version_file(root)
    if version_info:
        local_sha = version_info.get("commit_sha", "unknown")
        local_date = format_date(version_info.get("updated_at", ""))
        print(f"Current version: {local_sha[:7]} (updated {local_date})")
    else:
        local_sha = None
        print("Current version: not tracked (first run)")

    # Fetch latest commit
    print("Checking GitHub for updates...")
    commit_data = github_api_get(API_COMMITS_URL)
    remote_sha = commit_data.get("sha", "unknown")
    commit_date_str = (
        commit_data.get("commit", {}).get("committer", {}).get("date", "")
    )
    remote_date = format_date(commit_date_str)
    print(f"Latest version:  {remote_sha[:7]} ({remote_date})")
    print()

    if local_sha and local_sha == remote_sha:
        print("You are up to date. No changes needed.")
        return

    # Download and extract the zipball
    print("Downloading latest version...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_file = tmp_path / "repo.zip"
        download_zipball(API_ZIPBALL_URL, zip_file)

        print("Extracting archive...")
        repo_dir = extract_zip_to_dir(zip_file, tmp_path / "extracted")

        # Collect all files from the downloaded repo
        repo_files = collect_repo_files(repo_dir)

        # Classify and compare files
        updated_files = []    # (rel_path, status) where status is UPDATED or NEW
        unchanged_files = []
        protected_files = []
        skipped_files = []    # files not in either list

        for rel in repo_files:
            classification = classify_file(rel)

            if classification == "user":
                protected_files.append(rel)
                continue

            if classification == "toolkit":
                local_file = root / rel.replace("/", os.sep)
                remote_file = repo_dir / rel

                if not local_file.exists():
                    updated_files.append((rel, "NEW"))
                elif sha256_file(local_file) != sha256_file(remote_file):
                    updated_files.append((rel, "UPDATED"))
                else:
                    unchanged_files.append(rel)
            else:
                # Unknown classification; these are repo files we do not
                # explicitly manage (e.g., .gitignore, LICENSE). Skip them.
                skipped_files.append(rel)

        # Display the change summary
        print("Changes available:")
        if updated_files:
            for rel, status in updated_files:
                print(f"  {status:<10} {rel}")
        if unchanged_files:
            print(f"  UNCHANGED  {len(unchanged_files)} files")
        print()

        # Show protected files
        if protected_files:
            # Summarize protected files
            named = []
            db_count = 0
            for pf in protected_files:
                if pf.endswith(".db"):
                    db_count += 1
                else:
                    named.append(os.path.basename(pf))
            summary_parts = named[:]
            if db_count > 0:
                summary_parts.append(
                    f"{db_count} database{'s' if db_count != 1 else ''}"
                )
            print(f"Protected (never updated):")
            print(f"  {', '.join(summary_parts)}")
            print()

        if not updated_files:
            print("No toolkit files need updating.")
            return

        # Confirmation prompt (unless --yes was passed)
        if not auto_yes:
            print("Apply these updates? [y/N]: ", end="", flush=True)
            try:
                answer = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nUpdate cancelled.")
                return
            if answer not in ("y", "yes"):
                print("Update cancelled.")
                return

        # Create backup directory with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
        backup_root = root / BACKUP_DIR / timestamp

        # Apply updates
        update_count = 0
        new_count = 0
        for rel, status in updated_files:
            local_file = root / rel.replace("/", os.sep)
            remote_file = repo_dir / rel

            # Back up existing file if it exists
            if local_file.exists():
                backup_dest = backup_root / rel.replace("/", os.sep)
                backup_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_file, backup_dest)

            # Ensure target directory exists
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy new version into place
            shutil.copy2(remote_file, local_file)

            if status == "NEW":
                new_count += 1
            else:
                update_count += 1

        # Save version marker
        save_version_file(root, remote_sha)

        # Final report
        print()
        print("Updates applied successfully.")
        parts = []
        if update_count:
            parts.append(
                f"{update_count} file{'s' if update_count != 1 else ''} updated"
            )
        if new_count:
            parts.append(
                f"{new_count} new file{'s' if new_count != 1 else ''} added"
            )
        print(f"  {', '.join(parts)}")

        if backup_root.exists():
            print(f"  Backups saved to {BACKUP_DIR}/{timestamp}/")

        print()
        print("Your personalized files were not touched:")
        if protected_files:
            basenames = sorted(set(os.path.basename(p) for p in protected_files))
            print(f"  {', '.join(basenames)}")
        else:
            print("  (none found in this update)")


def cmd_status(root: Path) -> None:
    """Show current version, last update date, and file inventory."""
    print("Copilot CLI Toolkit Updater - Status")
    print("-" * 40)

    version_info = load_version_file(root)
    if version_info:
        sha = version_info.get("commit_sha", "unknown")
        date = format_date(version_info.get("updated_at", ""))
        repo = version_info.get("repo", f"{REPO_OWNER}/{REPO_NAME}")
        branch = version_info.get("branch", BRANCH)
        print(f"Version:  {sha[:7]} (updated {date})")
        print(f"Repo:     {repo}")
        print(f"Branch:   {branch}")
    else:
        print("Version:  not tracked (never updated via this tool)")
    print()

    # Inventory of local toolkit files
    print("Toolkit file inventory:")
    present = 0
    missing = 0
    for rel in TOOLKIT_FILES:
        local_file = root / rel.replace("/", os.sep)
        if local_file.exists():
            present += 1
        else:
            missing += 1
            print(f"  MISSING  {rel}")

    # Also check glob-prefix directories
    for prefix in TOOLKIT_GLOB_PREFIXES:
        prefix_dir = root / prefix.replace("/", os.sep)
        if prefix_dir.exists():
            for dirpath, _dirs, fnames in os.walk(prefix_dir):
                for fn in fnames:
                    full = Path(dirpath) / fn
                    rel = full.relative_to(root).as_posix()
                    if not is_user_file(rel):
                        present += 1

    print(f"  {present} toolkit files present, {missing} missing")
    print()

    # Inventory of protected user files found locally
    print("Protected user files found:")
    user_found = []
    for pattern in USER_FILE_PATTERNS:
        if "/" in pattern:
            check = root / pattern.replace("/", os.sep)
            if check.exists():
                user_found.append(pattern)
        else:
            # Search common locations
            for candidate_dir in [".", "instructions", "starter"]:
                check = root / candidate_dir / pattern
                if check.exists():
                    user_found.append(f"{candidate_dir}/{pattern}")

    # Count .db files
    db_count = 0
    for dirpath, _dirs, fnames in os.walk(root):
        for fn in fnames:
            if fn.endswith(".db"):
                db_count += 1

    if user_found:
        for uf in user_found:
            print(f"  {uf}")
    if db_count:
        print(f"  {db_count} database file{'s' if db_count != 1 else ''}")
    if not user_found and db_count == 0:
        print("  (none found)")
    print()

    # Backup info
    backup_path = root / BACKUP_DIR
    if backup_path.exists():
        backups = sorted(
            [d.name for d in backup_path.iterdir() if d.is_dir()], reverse=True
        )
        if backups:
            print(f"Backups available: {len(backups)}")
            for b in backups[:5]:
                print(f"  {b}")
            if len(backups) > 5:
                print(f"  ... and {len(backups) - 5} more")
        else:
            print("Backups: none")
    else:
        print("Backups: none (no updates applied yet)")


def cmd_restore(root: Path) -> None:
    """List available backups and restore a chosen one."""
    print("Copilot CLI Toolkit Updater - Restore")
    print("-" * 40)

    backup_path = root / BACKUP_DIR
    if not backup_path.exists():
        print("No backups found. Nothing to restore.")
        return

    backups = sorted(
        [d for d in backup_path.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )

    if not backups:
        print("No backups found. Nothing to restore.")
        return

    print("Available backups:")
    for i, b in enumerate(backups, 1):
        # Count files in the backup
        file_count = sum(1 for _ in b.rglob("*") if _.is_file())
        print(f"  [{i}] {b.name}  ({file_count} files)")

    print()
    print("Enter backup number to restore (or 'q' to cancel): ", end="", flush=True)
    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("\nRestore cancelled.")
        return

    if choice.lower() == "q":
        print("Restore cancelled.")
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(backups):
            raise ValueError()
    except ValueError:
        print("Invalid selection.")
        return

    selected = backups[idx]
    print(f"\nRestoring from backup: {selected.name}")

    # Walk the backup and copy files back to their original locations
    restored = 0
    for dirpath, _dirs, fnames in os.walk(selected):
        for fn in fnames:
            backup_file = Path(dirpath) / fn
            rel = backup_file.relative_to(selected).as_posix()

            # Safety check: do not restore into user files
            if is_user_file(rel):
                print(f"  SKIPPED (user file) {rel}")
                continue

            dest = root / rel.replace("/", os.sep)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, dest)
            print(f"  RESTORED {rel}")
            restored += 1

    print(f"\n{restored} file{'s' if restored != 1 else ''} restored from {selected.name}.")


def cmd_diff(root: Path, file_path: str) -> None:
    """Show what would change for a specific toolkit file."""
    print("Copilot CLI Toolkit Updater - Diff")
    print("-" * 40)

    # Normalize the file path
    rel = file_path.replace("\\", "/").lstrip("/")

    # Verify it is a toolkit file
    if is_user_file(rel):
        print(f"'{rel}' is a protected user file. It will never be updated.")
        return

    if not is_toolkit_file(rel):
        print(f"'{rel}' is not a recognized toolkit file.")
        print("It will not be affected by updates.")
        return

    local_file = root / rel.replace("/", os.sep)
    if not local_file.exists():
        print(f"Local file does not exist: {rel}")
        print("This file would be created as NEW during an update.")
        return

    # Download the latest version to compare
    print("Downloading latest version for comparison...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_file = tmp_path / "repo.zip"
        download_zipball(API_ZIPBALL_URL, zip_file)

        repo_dir = extract_zip_to_dir(zip_file, tmp_path / "extracted")
        remote_file = repo_dir / rel

        if not remote_file.exists():
            print(f"File '{rel}' not found in the latest remote version.")
            return

        # Compare hashes first
        if sha256_file(local_file) == sha256_file(remote_file):
            print(f"No changes. '{rel}' is identical to the latest version.")
            return

        # Show diff
        print(f"Changes for: {rel}")
        print()
        diff_lines = diff_file_contents(local_file, remote_file)
        if diff_lines:
            for line in diff_lines:
                print(line)
        else:
            print("Files differ (possibly binary or whitespace-only changes).")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copilot CLI Toolkit Updater",
        epilog=(
            "Updates toolkit components from the GitHub repo while "
            "protecting your personalized files."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check
    subparsers.add_parser("check", help="Check if updates are available")

    # update
    update_parser = subparsers.add_parser("update", help="Download and apply updates")
    update_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and apply updates immediately",
    )

    # status
    subparsers.add_parser("status", help="Show version, update date, file inventory")

    # restore
    subparsers.add_parser("restore", help="List backups and restore one")

    # diff
    diff_parser = subparsers.add_parser(
        "diff", help="Show what would change for a specific file"
    )
    diff_parser.add_argument("file", help="Relative path to the toolkit file")

    args = parser.parse_args()
    root = get_toolkit_root()

    if args.command == "check":
        cmd_check(root)
    elif args.command == "update":
        cmd_update(root, auto_yes=args.yes)
    elif args.command == "status":
        cmd_status(root)
    elif args.command == "restore":
        cmd_restore(root)
    elif args.command == "diff":
        cmd_diff(root, args.file)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
