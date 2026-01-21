: << 'CMDBLOCK'
@echo off
REM Polyglot script - works as both Windows batch and Unix shell
REM On Windows: .cmd extension triggers batch execution
REM On Unix: executed as shell script (CMDBLOCK is a here-doc that discards batch code)

setlocal EnableDelayedExpansion

set "HOOK_DIR=%~dp0"
set "SCRIPT_NAME=%~1"

if "%SCRIPT_NAME%"=="" (
    echo {"decision":"block","reason":"No script name provided to run-hook.cmd"}
    exit /b 1
)

REM Shift arguments so %* contains only args after script name
shift

REM If script is a .py file, run with Python directly
if "%SCRIPT_NAME:~-3%"==".py" (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        python "%HOOK_DIR%%SCRIPT_NAME%" %1 %2 %3 %4 %5 %6 %7 %8 %9
        exit /b !errorlevel!
    )
    echo {"decision":"block","reason":"Python not found. Please install Python 3.8 or later."}
    exit /b 0
)

REM If script is a .sh file, run with Git Bash
if "%SCRIPT_NAME:~-3%"==".sh" (
    REM Try common Git Bash locations
    if exist "C:\Program Files\Git\bin\bash.exe" (
        "C:\Program Files\Git\bin\bash.exe" -c "cd '%HOOK_DIR%' && ./'%SCRIPT_NAME%' %1 %2 %3 %4 %5 %6 %7 %8 %9"
        exit /b !errorlevel!
    )
    if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
        "C:\Program Files (x86)\Git\bin\bash.exe" -c "cd '%HOOK_DIR%' && ./'%SCRIPT_NAME%' %1 %2 %3 %4 %5 %6 %7 %8 %9"
        exit /b !errorlevel!
    )
    REM Try bash from PATH
    where bash >nul 2>&1
    if !errorlevel! equ 0 (
        bash -c "cd '%HOOK_DIR%' && ./'%SCRIPT_NAME%' %1 %2 %3 %4 %5 %6 %7 %8 %9"
        exit /b !errorlevel!
    )
    echo {"decision":"block","reason":"Git Bash not found. Please install Git for Windows."}
    exit /b 0
)

REM Unknown script type
echo {"decision":"block","reason":"Unknown script type: %SCRIPT_NAME%"}
exit /b 1

endlocal
exit /b 0
CMDBLOCK

# Unix shell script starts here
# The batch code above is consumed by the here-doc

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$1"
shift

if [ -z "$SCRIPT_NAME" ]; then
    echo '{"decision":"block","reason":"No script name provided to run-hook.cmd"}'
    exit 1
fi

# Execute the script
if [ -f "${SCRIPT_DIR}/${SCRIPT_NAME}" ]; then
    "${SCRIPT_DIR}/${SCRIPT_NAME}" "$@"
    exit $?
else
    echo "{\"decision\":\"block\",\"reason\":\"Script not found: ${SCRIPT_NAME}\"}"
    exit 1
fi
