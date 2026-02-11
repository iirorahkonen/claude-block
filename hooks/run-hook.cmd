: << 'CMDBLOCK'
@echo off
REM Polyglot entry point - works as both Windows batch and Unix shell
REM Calls protect_directories.py with Python

setlocal EnableDelayedExpansion
set "HOOK_DIR=%~dp0"

REM Call Python to evaluate protection rules
where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%HOOK_DIR%protect_directories.py"
    exit /b !errorlevel!
)

echo {"decision":"block","reason":"Python 3.8+ is required to use .block file protection. Install Python from https://python.org"}
exit /b 0
CMDBLOCK

# Unix: here-doc above discards batch code
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# Call Python to evaluate protection rules
if command -v python3 >/dev/null 2>&1; then
    python3 "$HOOK_DIR/protect_directories.py"
    exit $?
fi
if command -v python >/dev/null 2>&1; then
    python "$HOOK_DIR/protect_directories.py"
    exit $?
fi

echo '{"decision":"block","reason":"Python 3.8+ is required to use .block file protection. Install Python from https://python.org"}'
exit 0
