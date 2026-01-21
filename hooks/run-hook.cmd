: << 'CMDBLOCK'
@echo off
REM Polyglot entry point - works as both Windows batch and Unix shell
REM Calls protect_directories.py with Python

setlocal EnableDelayedExpansion
set "HOOK_DIR=%~dp0"

REM Quick check: walk up directory tree looking for .block files
set "CHECK_DIR=%CD%"
:check_loop
if exist "%CHECK_DIR%\.block" goto found_block
if exist "%CHECK_DIR%\.block.local" goto found_block
REM Move to parent directory
for %%I in ("%CHECK_DIR%\..") do set "PARENT_DIR=%%~fI"
if "%PARENT_DIR%"=="%CHECK_DIR%" goto no_block
set "CHECK_DIR=%PARENT_DIR%"
goto check_loop

:no_block
REM No .block file found in hierarchy, allow operation
exit /b 0

:found_block
REM .block file exists, need Python to evaluate protection rules
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

# Quick check: walk up directory tree looking for .block files
check_dir="$(pwd)"
while [ -n "$check_dir" ]; do
    if [ -f "$check_dir/.block" ] || [ -f "$check_dir/.block.local" ]; then
        # .block file exists, need Python to evaluate protection rules
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
    fi
    parent_dir="$(dirname "$check_dir")"
    [ "$parent_dir" = "$check_dir" ] && break
    check_dir="$parent_dir"
done

# No .block file found in hierarchy, allow operation
exit 0
