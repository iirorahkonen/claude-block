#!/bin/bash
# Unix wrapper for protect_directories.py
# Calls Python with the hook script

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Try python3 first, then python
if command -v python3 &> /dev/null; then
    python3 "$HOOK_DIR/protect_directories.py"
    exit $?
fi

if command -v python &> /dev/null; then
    python "$HOOK_DIR/protect_directories.py"
    exit $?
fi

echo '{"decision":"block","reason":"Python not found. Please install Python 3.8 or later."}'
exit 0
