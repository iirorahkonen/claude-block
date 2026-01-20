@echo off
REM Windows wrapper for protect_directories.py
REM Calls Python with the hook script

setlocal

set "HOOK_DIR=%~dp0"

REM Try python3 first, then python
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    python3 "%HOOK_DIR%protect_directories.py"
    exit /b %errorlevel%
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%HOOK_DIR%protect_directories.py"
    exit /b %errorlevel%
)

echo {"decision":"block","reason":"Python not found. Please install Python 3.8 or later."}
exit /b 0
