#!/bin/bash
# Session start hook: Check if jq is installed
# Warns user if jq is missing (required for directory protection)

if ! command -v jq &> /dev/null; then
    printf '{"decision": "continue", "systemMessage": "⚠️  jq is not installed. Directory protection (.block) requires jq. File operations in protected directories will be blocked until jq is installed."}\n'
else
    # jq is installed - return valid JSON with continue decision
    printf '{"decision": "continue"}\n'
fi

# Always exit 0 - don't block session start, just warn
exit 0
