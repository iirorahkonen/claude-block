#!/usr/bin/env python3
"""
Claude Code Directory Protection Hook

Blocks file modifications when .block or .block.local exists in target directory or parent.

Configuration files:
  .block       - Main configuration file (committed to git)
  .block.local - Local configuration file (not committed, add to .gitignore)

When both files exist in the same directory, they are merged:
  - blocked patterns: combined (union - more restrictive)
  - allowed patterns: local overrides main
  - guide messages: local takes precedence
  - Mixing allowed/blocked modes between files is an error

.block file format (JSON):
  Empty file or {} = block everything
  { "allowed": ["pattern1", "pattern2"] } = only allow matching paths, block everything else
  { "blocked": ["pattern1", "pattern2"] } = only block matching paths, allow everything else
  { "guide": "message" } = common guide shown when blocked (fallback for patterns without specific guide)
  Both allowed and blocked = error (invalid configuration)

Patterns can be strings or objects with per-pattern guides:
  "pattern" = simple pattern (uses common guide as fallback)
  { "pattern": "...", "guide": "..." } = pattern with specific guide

Patterns support wildcards:
  * = any characters except path separator
  ** = any characters including path separator (recursive)
  ? = single character
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

MARKER_FILE_NAME = ".block"
LOCAL_MARKER_FILE_NAME = ".block.local"


def has_block_file_in_hierarchy(directory: str) -> bool:
    """Check if .block file exists in directory hierarchy (quick check)."""
    directory = directory.replace("\\", "/")
    path = Path(directory)

    while path:
        if (path / MARKER_FILE_NAME).exists() or (path / LOCAL_MARKER_FILE_NAME).exists():
            return True
        parent = path.parent
        if parent == path:
            break
        path = parent
    return False


def extract_path_without_json(input_str: str) -> Optional[str]:
    """Extract file path from JSON without full parsing (fallback)."""
    import re
    match = re.search(r'"(file_path|notebook_path)"\s*:\s*"([^"]*)"', input_str)
    if match:
        return match.group(2)
    return None


def convert_wildcard_to_regex(pattern: str) -> str:
    """Convert wildcard pattern to regex."""
    pattern = pattern.replace("\\", "/")
    result = []
    i = 0

    while i < len(pattern):
        char = pattern[i]
        next_char = pattern[i + 1] if i + 1 < len(pattern) else ""

        if char == "*":
            if next_char == "*":
                result.append(".*")
                i += 1
            else:
                result.append("[^/]*")
        elif char == "?":
            result.append(".")
        elif char in ".^$[](){}+||\\":
            result.append(f"\\{char}")
        else:
            result.append(char)
        i += 1

    return f"^{(''.join(result))}$"


def test_path_matches_pattern(path: str, pattern: str, base_path: str) -> bool:
    """Test if path matches a pattern."""
    path = path.replace("\\", "/")
    base_path = base_path.replace("\\", "/").rstrip("/")

    lower_path = path.lower()
    lower_base = base_path.lower()

    if lower_path.startswith(lower_base):
        relative_path = path[len(base_path):].lstrip("/")
    else:
        relative_path = path

    regex = convert_wildcard_to_regex(pattern)

    try:
        return bool(re.match(regex, relative_path))
    except re.error:
        return False


def get_lock_file_config(marker_path: str) -> dict:
    """Get lock file configuration."""
    config = {
        "allowed": [],
        "blocked": [],
        "guide": "",
        "is_empty": True,
        "has_error": False,
        "error_message": "",
        "has_allowed_key": False,
        "has_blocked_key": False
    }

    if not os.path.isfile(marker_path):
        return config

    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return config

    if not content or content.isspace():
        return config

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return config

    has_allowed = "allowed" in data
    has_blocked = "blocked" in data

    if has_allowed and has_blocked:
        config["has_error"] = True
        config["error_message"] = "Invalid .block: cannot specify both allowed and blocked lists"
        return config

    config["guide"] = data.get("guide", "")

    if has_allowed:
        config["allowed"] = data["allowed"]
        config["has_allowed_key"] = True
        config["is_empty"] = False

    if has_blocked:
        config["blocked"] = data["blocked"]
        config["has_blocked_key"] = True
        config["is_empty"] = False

    return config


def merge_configs(main_config: dict, local_config: Optional[dict]) -> dict:
    """Merge two configs (main and local)."""
    if not local_config:
        return main_config

    if main_config.get("has_error"):
        return main_config
    if local_config.get("has_error"):
        return local_config

    main_empty = main_config.get("is_empty", True)
    local_empty = local_config.get("is_empty", True)

    if main_empty or local_empty:
        local_guide = local_config.get("guide", "")
        main_guide = main_config.get("guide", "")
        effective_guide = local_guide if local_guide else main_guide

        return {
            "allowed": [],
            "blocked": [],
            "guide": effective_guide,
            "is_empty": True,
            "has_error": False,
            "error_message": "",
            "has_allowed_key": False,
            "has_blocked_key": False
        }

    # Check if keys are present (not just if arrays have items)
    main_has_allowed_key = main_config.get("has_allowed_key", False)
    main_has_blocked_key = main_config.get("has_blocked_key", False)
    local_has_allowed_key = local_config.get("has_allowed_key", False)
    local_has_blocked_key = local_config.get("has_blocked_key", False)

    # Check for mode mixing
    if (main_has_allowed_key and local_has_blocked_key) or (main_has_blocked_key and local_has_allowed_key):
        return {
            "allowed": [],
            "blocked": [],
            "guide": "",
            "is_empty": False,
            "has_error": True,
            "error_message": "Invalid configuration: .block and .block.local cannot mix allowed and blocked modes",
            "has_allowed_key": False,
            "has_blocked_key": False
        }

    local_guide = local_config.get("guide", "")
    main_guide = main_config.get("guide", "")
    merged_guide = local_guide if local_guide else main_guide

    if main_has_blocked_key or local_has_blocked_key:
        main_blocked = main_config.get("blocked", [])
        local_blocked = local_config.get("blocked", [])
        merged_blocked = list(main_blocked) + list(local_blocked)
        seen = set()
        unique_blocked = []
        for item in merged_blocked:
            key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
            if key not in seen:
                seen.add(key)
                unique_blocked.append(item)

        return {
            "allowed": [],
            "blocked": unique_blocked,
            "guide": merged_guide,
            "is_empty": False,
            "has_error": False,
            "error_message": "",
            "has_allowed_key": False,
            "has_blocked_key": True
        }

    if main_has_allowed_key or local_has_allowed_key:
        if local_has_allowed_key:
            merged_allowed = local_config.get("allowed", [])
        else:
            merged_allowed = main_config.get("allowed", [])

        return {
            "allowed": merged_allowed,
            "blocked": [],
            "guide": merged_guide,
            "is_empty": False,
            "has_error": False,
            "error_message": "",
            "has_allowed_key": True,
            "has_blocked_key": False
        }

    return {
        "allowed": [],
        "blocked": [],
        "guide": merged_guide,
        "is_empty": True,
        "has_error": False,
        "error_message": "",
        "has_allowed_key": False,
        "has_blocked_key": False
    }


def get_full_path(path: str) -> str:
    """Get full/absolute path."""
    if os.path.isabs(path) or (len(path) >= 2 and path[1] == ":"):
        return path
    return os.path.join(os.getcwd(), path)


def test_directory_protected(file_path: str) -> Optional[dict]:
    """Test if directory is protected, returns protection info or None."""
    if not file_path:
        return None

    file_path = get_full_path(file_path)
    file_path = file_path.replace("\\", "/")
    directory = os.path.dirname(file_path)

    if not directory:
        return None

    while directory:
        marker_path = os.path.join(directory, MARKER_FILE_NAME)
        local_marker_path = os.path.join(directory, LOCAL_MARKER_FILE_NAME)
        has_main = os.path.isfile(marker_path)
        has_local = os.path.isfile(local_marker_path)

        if has_main or has_local:
            if has_main:
                main_config = get_lock_file_config(marker_path)
                effective_marker_path = marker_path
            else:
                main_config = {
                    "allowed": [],
                    "blocked": [],
                    "guide": "",
                    "is_empty": True,
                    "has_error": False,
                    "error_message": ""
                }
                effective_marker_path = None

            if has_local:
                local_config = get_lock_file_config(local_marker_path)
                if not has_main:
                    effective_marker_path = local_marker_path
                else:
                    effective_marker_path = f"{marker_path} (+ .local)"
            else:
                local_config = None

            merged_config = merge_configs(main_config, local_config)

            return {
                "target_file": file_path,
                "marker_path": effective_marker_path,
                "marker_directory": directory,
                "config": merged_config
            }

        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent

    return None


def get_bash_target_paths(command: str) -> list:
    """Extract target paths from bash commands."""
    if not command:
        return []

    paths = []

    patterns = [
        (r'\brm\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)', 1),
        (r'\btouch\s+([^\s|;&]+)', 1),
        (r'\bmkdir\s+(?:-p\s+)?([^\s|;&]+)', 1),
        (r'\brmdir\s+([^\s|;&]+)', 1),
        (r'>\s*([^\s|;&>]+)', 1),
        (r'\btee\s+(?:-a\s+)?([^\s|;&]+)', 1),
        (r'\bof=([^\s|;&]+)', 1),
    ]

    for pattern, group in patterns:
        for match in re.finditer(pattern, command):
            path = match.group(group).strip("'\"")
            if path and not path.startswith("-"):
                paths.append(path)

    mv_match = re.search(r'\bmv\s+(?:-[fiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)', command)
    if mv_match:
        for g in [1, 2]:
            path = mv_match.group(g).strip("'\"")
            if path and not path.startswith("-"):
                paths.append(path)

    cp_match = re.search(r'\bcp\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)', command)
    if cp_match:
        for g in [1, 2]:
            path = cp_match.group(g).strip("'\"")
            if path and not path.startswith("-"):
                paths.append(path)

    return list(set(paths))


def test_is_marker_file(file_path: str) -> bool:
    """Check if path is a marker file (main or local)."""
    if not file_path:
        return False
    filename = os.path.basename(file_path)
    return filename in (MARKER_FILE_NAME, LOCAL_MARKER_FILE_NAME)


def block_marker_removal(target_file: str) -> None:
    """Block marker file removal."""
    filename = os.path.basename(target_file)
    message = f"""BLOCKED: Cannot modify {filename}

Target file: {target_file}

The {filename} file is protected and cannot be modified or removed by Claude.
This is a safety mechanism to ensure directory protection remains in effect.

To remove protection, manually delete the file using your file manager or terminal."""

    print(json.dumps({"decision": "block", "reason": message}))
    sys.exit(0)


def block_config_error(marker_path: str, error_message: str) -> None:
    """Block config error."""
    message = f"""BLOCKED: Invalid {MARKER_FILE_NAME} configuration

Marker file: {marker_path}
Error: {error_message}

Please fix the configuration file. Valid formats:
  - Empty file or {{}} = block everything
  - {{ "allowed": ["pattern"] }} = only allow matching paths
  - {{ "blocked": ["pattern"] }} = only block matching paths"""

    print(json.dumps({"decision": "block", "reason": message}))
    sys.exit(0)


def block_with_message(target_file: str, marker_path: str, reason: str, guide: str) -> None:
    """Block with message."""
    if guide:
        message = guide
    else:
        message = f"BLOCKED by .block: {marker_path}"

    print(json.dumps({"decision": "block", "reason": message}))
    sys.exit(0)


def test_should_block(file_path: str, protection_info: dict) -> dict:
    """Test if operation should be blocked."""
    config = protection_info["config"]
    marker_dir = protection_info["marker_directory"]
    guide = config.get("guide", "")

    if config.get("has_error"):
        return {
            "should_block": True,
            "reason": config.get("error_message", "Configuration error"),
            "is_config_error": True,
            "guide": ""
        }

    if config.get("is_empty"):
        return {
            "should_block": True,
            "reason": "This directory tree is protected from Claude edits (full protection).",
            "is_config_error": False,
            "guide": guide
        }

    # Check if we're in allowed mode (allowed key was present in config)
    has_allowed_key = config.get("has_allowed_key", False)
    allowed_list = config.get("allowed", [])
    if has_allowed_key:
        for entry in allowed_list:
            if isinstance(entry, str):
                pattern = entry
            else:
                pattern = entry.get("pattern", "")

            if test_path_matches_pattern(file_path, pattern, marker_dir):
                return {
                    "should_block": False,
                    "reason": "",
                    "is_config_error": False,
                    "guide": ""
                }

        return {
            "should_block": True,
            "reason": "Path is not in the allowed list.",
            "is_config_error": False,
            "guide": guide
        }

    # Check if we're in blocked mode (blocked key was present in config)
    has_blocked_key = config.get("has_blocked_key", False)
    blocked_list = config.get("blocked", [])
    if has_blocked_key:
        for entry in blocked_list:
            if isinstance(entry, str):
                pattern = entry
                entry_guide = ""
            else:
                pattern = entry.get("pattern", "")
                entry_guide = entry.get("guide", "")

            if test_path_matches_pattern(file_path, pattern, marker_dir):
                effective_guide = entry_guide if entry_guide else guide
                return {
                    "should_block": True,
                    "reason": f"Path matches blocked pattern: {pattern}",
                    "is_config_error": False,
                    "guide": effective_guide
                }

        # No pattern matched, allow (blocked mode with no matches = allow)
        return {
            "should_block": False,
            "reason": "",
            "is_config_error": False,
            "guide": ""
        }

    return {
        "should_block": True,
        "reason": "This directory tree is protected from Claude edits.",
        "is_config_error": False,
        "guide": guide
    }


def main():
    """Main entry point."""
    hook_input = sys.stdin.read()

    quick_path = extract_path_without_json(hook_input)

    if quick_path:
        quick_dir = os.path.dirname(quick_path)
        if not os.path.isabs(quick_path) and not (len(quick_path) >= 2 and quick_path[1] == ":"):
            quick_dir = os.path.join(os.getcwd(), quick_dir)

        if not has_block_file_in_hierarchy(quick_dir):
            sys.exit(0)

    try:
        data = json.loads(hook_input)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if not tool_name:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    paths_to_check = []

    if tool_name == "Edit":
        path = tool_input.get("file_path")
        if path:
            paths_to_check.append(path)
    elif tool_name == "Write":
        path = tool_input.get("file_path")
        if path:
            paths_to_check.append(path)
    elif tool_name == "NotebookEdit":
        path = tool_input.get("notebook_path")
        if path:
            paths_to_check.append(path)
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if command:
            paths_to_check.extend(get_bash_target_paths(command))
    else:
        sys.exit(0)

    for path in paths_to_check:
        if not path:
            continue

        if test_is_marker_file(path):
            full_path = get_full_path(path)
            if os.path.isfile(full_path):
                block_marker_removal(full_path)

        protection_info = test_directory_protected(path)

        if protection_info:
            target_file = protection_info["target_file"]
            marker_path = protection_info["marker_path"]

            block_result = test_should_block(target_file, protection_info)

            should_block = block_result["should_block"]
            is_config_error = block_result["is_config_error"]
            reason = block_result["reason"]
            result_guide = block_result["guide"]

            if is_config_error:
                block_config_error(marker_path, reason)
            elif should_block:
                block_with_message(target_file, marker_path, reason, result_guide)

    sys.exit(0)


if __name__ == "__main__":
    main()
