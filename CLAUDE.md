# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This plugin provides file and directory protection using `.block` configuration files. It supports both **Claude Code** and **OpenCode**. When installed, the plugin intercepts file modification operations and blocks them based on protection rules.

## Architecture

The core protection logic lives in `hooks/protect_directories.py` (Python, no external dependencies). Both Claude Code and OpenCode integrations call this script.

### Claude Code integration
- **PreToolUse hook**: Runs `protect_directories.py` to check if the target file is protected before allowing Edit, Write, NotebookEdit, or Bash operations
- `hooks/hooks.json` - Hook configuration
- `hooks/run-hook.cmd` - Cross-platform entry point (polyglot script)
- `commands/create.md` - Interactive command for creating `.block` files
- `.claude-plugin/plugin.json` - Plugin metadata

### OpenCode integration
- **tool.execute.before hook**: TypeScript plugin that calls `protect_directories.py` before edit, write, bash, or patch operations
- `opencode/index.ts` - Plugin entry point
- `opencode/package.json` - npm package metadata

## Dependencies

- **Python 3.8+** - Required for the protection hook (no external packages needed)
- **pytest** - For running tests (dev dependency only)

## Testing

Run the test suite with pytest:

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_basic_protection.py -v

# Run with coverage
pytest tests/ -v --cov=hooks --cov-report=term-missing
```

## Testing the Plugin Locally

To test protection locally:
1. Ensure Python 3.8+ is installed
2. Create a test directory with a `.block` file
3. Attempt to modify files in that directory - operations should be blocked

## Git Worktrees

When creating git worktrees, use the `.worktree` folder in the project root:
```
git worktree add .worktree/<worktree-name> <branch-name>
```
