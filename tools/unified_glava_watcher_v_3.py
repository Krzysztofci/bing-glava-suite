#!/usr/bin/env python3

import os
import time
import difflib
from pathlib import Path
from collections import defaultdict

# =============================================================================
# CONFIG
# =============================================================================

WATCH_PATHS = [
    os.path.expanduser("~/.config/glava"),
]

WATCH_EXTENSIONS = {
    ".glsl",
    ".conf",
    ".ini",
    ".json",
}

IGNORE_DIRS = {
    "backup_install",
    ".git",
    "__pycache__",
}

POLL_INTERVAL = 0.25

# compact | full | append
DIFF_MODE = "full"

SHOW_UNCHANGED = False

# =============================================================================
# COLORS
# =============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
GRAY = "\033[90m"

# =============================================================================
# HELPERS
# =============================================================================


def timestamp():
    return time.strftime("%H:%M:%S")



def should_ignore(path):
    path_parts = Path(path).parts

    for part in path_parts:
        if part in IGNORE_DIRS:
            return True

    return False



def should_watch(file_path):
    return Path(file_path).suffix.lower() in WATCH_EXTENSIONS


# =============================================================================
# SNAPSHOT
# =============================================================================


def build_snapshot():
    snapshot = {}

    for watch_root in WATCH_PATHS:
        if not os.path.exists(watch_root):
            continue

        for root, dirs, files in os.walk(watch_root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                full_path = os.path.join(root, file)

                if should_ignore(full_path):
                    continue

                if not should_watch(full_path):
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        snapshot[full_path] = {
                            "mtime": os.path.getmtime(full_path),
                            "lines": f.readlines(),
                        }

                except Exception as e:
                    print(f"{RED}[ERROR]{RESET} {full_path}: {e}")

    return snapshot


# =============================================================================
# DIFF FORMATTERS
# =============================================================================


def print_append_only(old_lines, new_lines):
    if len(new_lines) <= len(old_lines):
        return

    appended = new_lines[len(old_lines):]

    for line in appended:
        line = line.rstrip()

        if line:
            print(f"  {GREEN}+ {line}{RESET}")



def print_compact_diff(old_lines, new_lines):
    max_len = max(len(old_lines), len(new_lines))

    for i in range(max_len):
        old = old_lines[i].rstrip() if i < len(old_lines) else None
        new = new_lines[i].rstrip() if i < len(new_lines) else None

        if old == new:
            if SHOW_UNCHANGED:
                print(f"  {GRAY}= {old}{RESET}")
            continue

        if old is not None:
            print(f"  {RED}- {old}{RESET}")

        if new is not None:
            print(f"  {GREEN}+ {new}{RESET}")



def print_full_diff(old_lines, new_lines):
    diff = difflib.ndiff(old_lines, new_lines)

    for line in diff:
        prefix = line[:2]
        content = line[2:].rstrip()

        if not content:
            continue

        if prefix == "- ":
            print(f"  {RED}- {content}{RESET}")

        elif prefix == "+ ":
            print(f"  {GREEN}+ {content}{RESET}")

        elif prefix == "? ":
            print(f"  {YELLOW}? {content}{RESET}")

        elif SHOW_UNCHANGED:
            print(f"  {GRAY}= {content}{RESET}")


# =============================================================================
# EVENT HANDLERS
# =============================================================================


def print_file_header(event_type, path):
    relative = path

    for root in WATCH_PATHS:
        if path.startswith(root):
            relative = os.path.relpath(path, root)
            break

    color = {
        "MODIFIED": CYAN,
        "CREATED": GREEN,
        "DELETED": RED,
    }.get(event_type, RESET)

    print()
    print(f"{color}[{timestamp()}] {event_type}: {relative}{RESET}")



def handle_modified(path, old_data, new_data):
    print_file_header("MODIFIED", path)

    old_lines = old_data["lines"]
    new_lines = new_data["lines"]

    if DIFF_MODE == "append":
        print_append_only(old_lines, new_lines)

    elif DIFF_MODE == "compact":
        print_compact_diff(old_lines, new_lines)

    else:
        print_full_diff(old_lines, new_lines)



def handle_created(path):
    print_file_header("CREATED", path)



def handle_deleted(path):
    print_file_header("DELETED", path)


# =============================================================================
# MAIN LOOP
# =============================================================================


def main():
    print()
    print(f"{BOLD}=== GLava Unified Watcher v3 ==={RESET}")
    print()

    print(f"{CYAN}Watching paths:{RESET}")

    for path in WATCH_PATHS:
        print(f"  - {path}")

    print()
    print(f"{MAGENTA}Diff mode:{RESET} {DIFF_MODE}")
    print()

    previous = build_snapshot()

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            current = build_snapshot()

            previous_paths = set(previous.keys())
            current_paths = set(current.keys())

            created = current_paths - previous_paths
            deleted = previous_paths - current_paths
            common = current_paths & previous_paths

            # -------------------------------------------------------------
            # CREATED
            # -------------------------------------------------------------

            for path in sorted(created):
                handle_created(path)

            # -------------------------------------------------------------
            # DELETED
            # -------------------------------------------------------------

            for path in sorted(deleted):
                handle_deleted(path)

            # -------------------------------------------------------------
            # MODIFIED
            # -------------------------------------------------------------

            for path in sorted(common):
                old_data = previous[path]
                new_data = current[path]

                if old_data["lines"] != new_data["lines"]:
                    handle_modified(path, old_data, new_data)

            previous = current

    except KeyboardInterrupt:
        print()
        print(f"{YELLOW}Watcher stopped.{RESET}")
        print()


# =============================================================================
# ENTRY
# =============================================================================

if __name__ == "__main__":
    main()
