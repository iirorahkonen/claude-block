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

Examples:
  { "blocked": ["*.secret", { "pattern": "config/**", "guide": "Config files protected." }] }
  { "allowed": ["docs/**", { "pattern": "src/gen/**", "guide": "Generated files." }], "guide": "Fallback" }

Guide priority: pattern-specific guide > common guide > default message

Patterns support wildcards:
  * = any characters except path separator
  ** = any characters including path separator (recursive)
  ? = single character
"""

import json
import os
import re
import shlex
import sys
import warnings
from pathlib import Path
from typing import Optional, cast

# Regex special characters that need escaping
REGEX_SPECIAL_CHARS = ".^$[](){}+|\\"

MARKER_FILE_NAME = ".block"
LOCAL_MARKER_FILE_NAME = ".block.local"


def _create_empty_config(  # noqa: PLR0913
    allowed: Optional[list] = None,
    blocked: Optional[list] = None,
    guide: str = "",
    is_empty: bool = True,
    has_error: bool = False,
    error_message: str = "",
    has_allowed_key: bool = False,
    has_blocked_key: bool = False,
    allow_all: bool = False,
) -> dict:
    """Create an empty config dict with optional overrides."""
    return {
        "allowed": allowed if allowed is not None else [],
        "blocked": blocked if blocked is not None else [],
        "guide": guide,
        "is_empty": is_empty,
        "has_error": has_error,
        "error_message": error_message,
        "has_allowed_key": has_allowed_key,
        "has_blocked_key": has_blocked_key,
        "allow_all": allow_all,
    }


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
    match = re.search(r'"(file_path|notebook_path)"\s*:\s*"([^"]*)"', input_str)
    if match:
        return match.group(2)
    return None


def convert_wildcard_to_regex(pattern: str) -> str:
    """Convert wildcard pattern to regex."""
    pattern = pattern.replace("\\", "/")
    result = []
    i = 0
    at_start = True

    while i < len(pattern):
        char = pattern[i]
        next_char = pattern[i + 1] if i + 1 < len(pattern) else ""
        next2_char = pattern[i + 2] if i + 2 < len(pattern) else ""

        if char == "*":
            if next_char == "*":
                # **/ at start = optionally match any path + /
                if at_start and next2_char == "/":
                    result.append("(.*/)?")
                    # Skip 2 extra chars (second * and /), loop adds 1 for first * = 3 total
                    i += 2
                else:
                    result.append(".*")
                    # Skip 1 extra char (second *), loop adds 1 for first * = 2 total
                    i += 1
            else:
                result.append("[^/]*")
            at_start = False
        elif char == "?":
            result.append(".")
            at_start = False
        elif char == "/":
            result.append("/")
            # After a /, we might have **/ again - don't reset at_start
        elif char in REGEX_SPECIAL_CHARS:
            result.append(f"\\{char}")
            at_start = False
        else:
            result.append(char)
            at_start = False
        i += 1

    return f"^{''.join(result)}$"


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
    except re.error as e:
        warnings.warn(f"Invalid regex pattern '{pattern}' (converted: '{regex}'): {e}", stacklevel=2)
        return False


def get_lock_file_config(marker_path: str) -> dict:
    """Get lock file configuration."""
    config = _create_empty_config()

    if not os.path.isfile(marker_path):
        return config

    try:
        with open(marker_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return config

    if not content or content.isspace():
        return config

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return config

    # Extract guide (applies to all modes)
    config["guide"] = data.get("guide", "")

    # Check for top-level allowed/blocked
    has_allowed = "allowed" in data
    has_blocked = "blocked" in data

    if has_allowed and has_blocked:
        config["has_error"] = True
        config["error_message"] = "Invalid .block: cannot specify both allowed and blocked lists"
        return config

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

        return _create_empty_config(guide=effective_guide)

    # Check if keys are present (not just if arrays have items)
    main_has_allowed_key = main_config.get("has_allowed_key", False)
    main_has_blocked_key = main_config.get("has_blocked_key", False)
    local_has_allowed_key = local_config.get("has_allowed_key", False)
    local_has_blocked_key = local_config.get("has_blocked_key", False)

    # Check for mode mixing
    if (main_has_allowed_key and local_has_blocked_key) or (main_has_blocked_key and local_has_allowed_key):
        return _create_empty_config(
            is_empty=False,
            has_error=True,
            error_message="Invalid configuration: .block and .block.local cannot mix allowed and blocked modes",
        )

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

        return _create_empty_config(
            blocked=unique_blocked,
            guide=merged_guide,
            is_empty=False,
            has_blocked_key=True,
        )

    if main_has_allowed_key or local_has_allowed_key:
        if local_has_allowed_key:
            merged_allowed = local_config.get("allowed", [])
        else:
            merged_allowed = main_config.get("allowed", [])

        return _create_empty_config(
            allowed=merged_allowed,
            guide=merged_guide,
            is_empty=False,
            has_allowed_key=True,
        )

    return _create_empty_config(guide=merged_guide)


def get_full_path(path: str) -> str:
    """Get full/absolute path."""
    if os.path.isabs(path) or (len(path) >= 2 and path[1] == ":"):
        return path
    return os.path.join(os.getcwd(), path)


def _merge_hierarchical_configs(child_config: dict, parent_config: dict) -> dict:
    """Merge child and parent configs from different directory levels.

    Inheritance rules:
    - Child .block with specific patterns overrides parent's "block all"
    - Blocked patterns are combined (union) from both levels
    - Allowed patterns: child completely overrides parent (no inheritance)
    - Guide: child guide takes precedence over parent guide
    """
    if not parent_config:
        return child_config
    if not child_config:
        return parent_config

    # If either has an error, propagate it
    if child_config.get("has_error"):
        return child_config
    if parent_config.get("has_error"):
        return parent_config

    child_empty = child_config.get("is_empty", True)
    parent_empty = parent_config.get("is_empty", True)

    child_guide = child_config.get("guide", "")
    parent_guide = parent_config.get("guide", "")
    merged_guide = child_guide if child_guide else parent_guide

    # If child is empty (block all), it takes precedence over everything
    if child_empty:
        return _create_empty_config(guide=merged_guide)

    # Child has specific patterns - check what modes are being used
    child_has_allowed = child_config.get("has_allowed_key", False)
    child_has_blocked = child_config.get("has_blocked_key", False)
    parent_has_allowed = parent_config.get("has_allowed_key", False)
    parent_has_blocked = parent_config.get("has_blocked_key", False)

    # If child has allowed patterns, it completely overrides parent
    # (regardless of whether parent is empty or has blocked patterns)
    if child_has_allowed:
        return _create_empty_config(
            allowed=child_config.get("allowed", []),
            guide=merged_guide,
            is_empty=False,
            has_allowed_key=True,
        )

    # Child has blocked patterns - merge with parent's blocked patterns
    if child_has_blocked:
        child_blocked = child_config.get("blocked", [])

        # If parent is empty (block all), just use child's patterns
        # (child's patterns are more specific)
        if parent_empty:
            return _create_empty_config(
                blocked=child_blocked,
                guide=merged_guide,
                is_empty=False,
                has_blocked_key=True,
            )

        # Check for mode mixing
        if parent_has_allowed:
            return _create_empty_config(
                is_empty=False,
                has_error=True,
                error_message="Invalid configuration: parent and child .block files cannot mix allowed and blocked modes",
            )

        # Both have blocked patterns - combine them (union)
        if parent_has_blocked:
            parent_blocked = parent_config.get("blocked", [])
            merged_blocked = list(child_blocked) + list(parent_blocked)

            # Deduplicate while preserving order
            seen = set()
            unique_blocked = []
            for item in merged_blocked:
                key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
                if key not in seen:
                    seen.add(key)
                    unique_blocked.append(item)

            return _create_empty_config(
                blocked=unique_blocked,
                guide=merged_guide,
                is_empty=False,
                has_blocked_key=True,
            )

        # Parent has no blocked patterns, just use child's
        return _create_empty_config(
            blocked=child_blocked,
            guide=merged_guide,
            is_empty=False,
            has_blocked_key=True,
        )

    # Child has no patterns but is not empty (shouldn't happen, but handle gracefully)
    # Fall back to parent's config with merged guide
    if parent_has_allowed:
        return _create_empty_config(
            allowed=parent_config.get("allowed", []),
            guide=merged_guide,
            is_empty=False,
            has_allowed_key=True,
        )

    if parent_has_blocked:
        return _create_empty_config(
            blocked=parent_config.get("blocked", []),
            guide=merged_guide,
            is_empty=False,
            has_blocked_key=True,
        )

    return _create_empty_config(guide=merged_guide)


def test_directory_protected(file_path: str) -> Optional[dict]:
    """Test if directory is protected, returns protection info or None.

    Walks up the entire directory tree collecting all .block files,
    then merges their configurations. Child configs inherit parent
    blocked patterns (combined) but can override guides.
    """
    if not file_path:
        return None

    file_path = get_full_path(file_path)
    file_path = file_path.replace("\\", "/")

    # Explicit path traversal check per best practices
    # Block paths containing ".." components to prevent directory traversal attacks
    if ".." in file_path.split("/"):
        return None

    directory = os.path.dirname(file_path)

    if not directory:
        return None

    # Collect all configs from hierarchy (child to parent order)
    configs_with_dirs = []

    current_dir = directory
    while current_dir:
        marker_path = os.path.join(current_dir, MARKER_FILE_NAME)
        local_marker_path = os.path.join(current_dir, LOCAL_MARKER_FILE_NAME)
        has_main = os.path.isfile(marker_path)
        has_local = os.path.isfile(local_marker_path)

        if has_main or has_local:
            if has_main:
                main_config = get_lock_file_config(marker_path)
                effective_marker_path = marker_path
            else:
                main_config = _create_empty_config()
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
            configs_with_dirs.append({
                "config": merged_config,
                "marker_path": effective_marker_path,
                "marker_directory": current_dir,
            })

        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent

    if not configs_with_dirs:
        return None

    # Merge all configs from child to parent
    # Start with the closest (child) config and merge parents into it
    final_config = cast("dict", configs_with_dirs[0]["config"])
    closest_marker_path = cast("Optional[str]", configs_with_dirs[0]["marker_path"])
    closest_marker_dir = cast("str", configs_with_dirs[0]["marker_directory"])

    for i in range(1, len(configs_with_dirs)):
        parent_config = cast("dict", configs_with_dirs[i]["config"])
        final_config = _merge_hierarchical_configs(final_config, parent_config)

    # Build marker path description if multiple .block files are involved
    if len(configs_with_dirs) > 1:
        marker_paths = [cast("str", c["marker_path"]) for c in configs_with_dirs if c["marker_path"]]
        effective_marker_path = " + ".join(marker_paths)
    else:
        effective_marker_path = closest_marker_path

    return {
        "target_file": file_path,
        "marker_path": effective_marker_path,
        "marker_directory": closest_marker_dir,
        "config": final_config
    }


def _extract_paths_from_tokens(tokens: list, command_handlers: dict) -> list:
    """Extract paths from pre-tokenized command list."""
    paths = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in command_handlers:
            handler = command_handlers[token]
            args = []
            i += 1
            # Collect non-option arguments
            while i < len(tokens) and not tokens[i].startswith("-"):
                if tokens[i] in ("|", ";", "&", "&&", "||"):
                    break
                args.append(tokens[i])
                i += 1
            # Skip option arguments
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
                # Skip option values if needed
                if (
                    i < len(tokens)
                    and not tokens[i].startswith("-")
                    and tokens[i] not in ("|", ";", "&", "&&", "||")
                    and not tokens[i - 1].endswith("f")
                ):
                    continue
            # Apply handler to get paths from args
            paths.extend(handler(args))
        else:
            i += 1
    return paths


def get_bash_target_paths(command: str) -> list:
    """Extract target paths from bash commands.

    Uses shlex for proper handling of quoted paths with spaces.
    Falls back to regex-based extraction if shlex parsing fails.
    """
    if not command:
        return []

    paths = []

    # Try shlex-based extraction first for better quoted path handling
    try:
        tokens = shlex.split(command)
        # Commands that take paths as arguments
        single_path_cmds = {"touch", "mkdir", "rmdir", "tee"}
        multi_path_cmds = {"rm", "mv", "cp"}

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Handle redirection (>)
            if ">" in token and token != ">":
                # Handle cases like ">file" or ">>file"
                redirect_path = token.lstrip(">").strip()
                if redirect_path and not redirect_path.startswith("-"):
                    paths.append(redirect_path)
                i += 1
                continue

            if (token == ">" or token == ">>") and i + 1 < len(tokens):
                # Next token is the file
                path = tokens[i + 1]
                if path and not path.startswith("-"):
                    paths.append(path)
                i += 2
                continue

            # Handle of= for dd command
            if token.startswith("of="):
                path = token[3:]
                if path and not path.startswith("-"):
                    paths.append(path)
                i += 1
                continue

            if token in single_path_cmds:
                # Collect all non-option arguments as paths
                i += 1
                while i < len(tokens):
                    arg = tokens[i]
                    if arg.startswith("-"):
                        i += 1
                        continue
                    if arg in ("|", ";", "&", "&&", "||", ">", ">>"):
                        break
                    paths.append(arg)
                    i += 1
                continue

            if token in multi_path_cmds:
                # Collect all non-option arguments as paths
                i += 1
                while i < len(tokens):
                    arg = tokens[i]
                    if arg.startswith("-"):
                        i += 1
                        continue
                    if arg in ("|", ";", "&", "&&", "||", ">", ">>"):
                        break
                    paths.append(arg)
                    i += 1
                continue

            i += 1

    except ValueError:
        # shlex parsing failed (e.g., unmatched quotes), fall back to regex
        pass

    # Regex-based fallback for edge cases and additional coverage
    patterns = [
        (r'\brm\s+(?:-[rRfiv]+\s+)*"([^"]+)"', 1),
        (r"\brm\s+(?:-[rRfiv]+\s+)*'([^']+)'", 1),
        (r'\brm\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)', 1),
        (r'\btouch\s+"([^"]+)"', 1),
        (r"\btouch\s+'([^']+)'", 1),
        (r'\btouch\s+([^\s|;&]+)', 1),
        (r'\bmkdir\s+(?:-p\s+)?"([^"]+)"', 1),
        (r"\bmkdir\s+(?:-p\s+)?'([^']+)'", 1),
        (r'\bmkdir\s+(?:-p\s+)?([^\s|;&]+)', 1),
        (r'\brmdir\s+"([^"]+)"', 1),
        (r"\brmdir\s+'([^']+)'", 1),
        (r'\brmdir\s+([^\s|;&]+)', 1),
        (r'>\s*"([^"]+)"', 1),
        (r">\s*'([^']+)'", 1),
        (r'>\s*([^\s|;&>]+)', 1),
        (r'\btee\s+(?:-a\s+)?"([^"]+)"', 1),
        (r"\btee\s+(?:-a\s+)?'([^']+)'", 1),
        (r'\btee\s+(?:-a\s+)?([^\s|;&]+)', 1),
        (r'\bof="([^"]+)"', 1),
        (r"\bof='([^']+)'", 1),
        (r'\bof=([^\s|;&]+)', 1),
    ]

    for pattern, group in patterns:
        for match in re.finditer(pattern, command):
            path = match.group(group)
            if path and not path.startswith("-"):
                paths.append(path)

    # Handle mv and cp with quoted paths
    mv_patterns = [
        r'\bmv\s+(?:-[fiv]+\s+)*"([^"]+)"\s+"([^"]+)"',
        r"\bmv\s+(?:-[fiv]+\s+)*'([^']+)'\s+'([^']+)'",
        r'\bmv\s+(?:-[fiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)',
    ]
    for pattern in mv_patterns:
        mv_match = re.search(pattern, command)
        if mv_match:
            for g in [1, 2]:
                path = mv_match.group(g)
                if path and not path.startswith("-"):
                    paths.append(path)
            break

    cp_patterns = [
        r'\bcp\s+(?:-[rRfiv]+\s+)*"([^"]+)"\s+"([^"]+)"',
        r"\bcp\s+(?:-[rRfiv]+\s+)*'([^']+)'\s+'([^']+)'",
        r'\bcp\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)',
    ]
    for pattern in cp_patterns:
        cp_match = re.search(pattern, command)
        if cp_match:
            for g in [1, 2]:
                path = cp_match.group(g)
                if path and not path.startswith("-"):
                    paths.append(path)
            break

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

    # Check for allow_all flag (empty blocked array means "allow everything")
    if config.get("allow_all"):
        return {
            "should_block": False,
            "reason": "",
            "is_config_error": False,
            "guide": ""
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

    if tool_name == "Edit" or tool_name == "Write":
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
