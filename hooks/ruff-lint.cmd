: << 'CMDBLOCK'
@echo off
REM Run ruff linter on Python files via python -m

python -m ruff check hooks\ tests\
if %errorlevel% neq 0 (
    if %errorlevel% equ 1 exit /b 1
    echo ruff not installed. Install with: pip install ruff
    exit /b 1
)
exit /b 0
CMDBLOCK

# Unix
if command -v python3 &> /dev/null; then
    python3 -m ruff check hooks/ tests/
elif command -v python &> /dev/null; then
    python -m ruff check hooks/ tests/
else
    echo "Python not found"
    exit 1
fi
