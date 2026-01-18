#!/bin/bash
# Session start hook: Check if jq is installed
# Warns user if jq is missing (required for directory protection)

if ! command -v jq &> /dev/null; then
    echo "WARNING: jq is not installed. Directory protection (.claude-block) requires jq." >&2
    echo "File operations in protected directories will be blocked until jq is installed." >&2
fi

# Always exit 0 - don't block session start, just warn
exit 0
