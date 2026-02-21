: << 'CMDBLOCK'
@echo off
REM Polyglot entry point - works as both Windows batch and Unix shell
REM Calls subagent_tracker.py with Python (silent exit if Python not found)

setlocal EnableDelayedExpansion
set "HOOK_DIR=%~dp0"

REM Call Python to track subagent events
where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%HOOK_DIR%subagent_tracker.py"
    exit /b 0
)

REM Python not found - tracker is optional, exit silently
exit /b 0
CMDBLOCK

# Unix: here-doc above discards batch code
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# Call Python to track subagent events
if command -v python3 >/dev/null 2>&1; then
    python3 "$HOOK_DIR/subagent_tracker.py"
    exit 0
fi
if command -v python >/dev/null 2>&1; then
    python "$HOOK_DIR/subagent_tracker.py"
    exit 0
fi

# Python not found - tracker is optional, exit silently
exit 0
