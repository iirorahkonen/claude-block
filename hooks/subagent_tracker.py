#!/usr/bin/env python3
"""
Subagent Tracker for Claude Code

Handles SubagentStart and SubagentStop events to maintain a tracking file
that maps active subagent IDs to their agent types.

Tracking file location: {dirname(transcript_path)}/subagents/.agent_types.json

This script is invoked by Claude Code hooks and should:
- Never block (always exit 0)
- Never produce stdout output (no JSON response)
- Use file locking for concurrent safety
"""

import json
import os
import sys
import time

_LOCK_SIZE = 1024
_LOCK_TIMEOUT = 10  # seconds


def _lock_file(f):
    """Acquire an exclusive lock on a file (platform-specific, blocking)."""
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            # LK_LOCK only retries for 1 second; use LK_NBLCK with our own
            # retry loop for a longer timeout to handle slow CI environments
            deadline = time.monotonic() + _LOCK_TIMEOUT
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, _LOCK_SIZE)
                    return  # Lock acquired
                except OSError:
                    if time.monotonic() >= deadline:
                        return  # Give up but don't crash
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
    except (OSError, ImportError):
        pass  # Best-effort locking


def _unlock_file(f):
    """Release the lock on a file (platform-specific)."""
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, _LOCK_SIZE)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_UN)
    except (OSError, ImportError):
        pass


def _get_tracking_path(transcript_path: str) -> str:
    """Derive the tracking file path from the transcript path."""
    transcript_dir = os.path.dirname(transcript_path)
    return os.path.join(transcript_dir, "subagents", ".agent_types.json")


def _read_tracking_file(tracking_path: str) -> dict:
    """Read the tracking file, returning empty dict if missing or invalid."""
    try:
        with open(tracking_path, encoding="utf-8") as f:
            data = json.loads(f.read())
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _write_tracking_file(tracking_path: str, agent_map: dict) -> None:
    """Write the tracking file with file locking."""
    os.makedirs(os.path.dirname(tracking_path), exist_ok=True)

    lock_path = tracking_path + ".lock"
    try:
        with open(lock_path, "a+b") as lock_f:
            _lock_file(lock_f)
            try:
                # Re-read inside lock to avoid races
                current = _read_tracking_file(tracking_path)
                current.update(agent_map)
                # Write atomically-ish
                with open(tracking_path, "w", encoding="utf-8") as f:
                    json.dump(current, f)
            finally:
                _unlock_file(lock_f)
    except OSError:
        pass


def _remove_from_tracking_file(tracking_path: str, agent_id: str) -> None:
    """Remove an agent from the tracking file with file locking."""
    if not os.path.isfile(tracking_path):
        return

    lock_path = tracking_path + ".lock"
    try:
        with open(lock_path, "a+b") as lock_f:
            _lock_file(lock_f)
            try:
                current = _read_tracking_file(tracking_path)
                current.pop(agent_id, None)
                with open(tracking_path, "w", encoding="utf-8") as f:
                    json.dump(current, f)
            finally:
                _unlock_file(lock_f)
    except OSError:
        pass


def handle_start(data: dict) -> None:
    """Handle SubagentStart event: add agent to tracking file."""
    agent_id = data.get("agent_id", "")
    agent_type = data.get("agent_type", "")
    transcript_path = data.get("transcript_path", "")

    if not agent_id or not transcript_path:
        return

    if not agent_type:
        agent_type = "unknown"

    tracking_path = _get_tracking_path(transcript_path)
    _write_tracking_file(tracking_path, {agent_id: agent_type})


def handle_stop(data: dict) -> None:
    """Handle SubagentStop event: remove agent from tracking file."""
    agent_id = data.get("agent_id", "")
    transcript_path = data.get("transcript_path", "")

    if not agent_id or not transcript_path:
        return

    tracking_path = _get_tracking_path(transcript_path)
    _remove_from_tracking_file(tracking_path, agent_id)


def main():
    """Main entry point. Never blocks, never outputs to stdout."""
    try:
        hook_input = sys.stdin.read()
        if not hook_input or hook_input.isspace():
            sys.exit(0)

        data = json.loads(hook_input)
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    event_type = data.get("hook_type", "")

    if event_type == "SubagentStart":
        handle_start(data)
    elif event_type == "SubagentStop":
        handle_stop(data)

    sys.exit(0)


if __name__ == "__main__":
    main()
