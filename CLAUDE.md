# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code plugin that provides file and directory protection using `.claude-block` configuration files. When installed, the plugin intercepts file modification operations (Edit, Write, NotebookEdit, Bash) and blocks them based on protection rules.

## Architecture

The plugin uses Claude Code's hook system:
- **SessionStart hook**: Runs `check-jq.sh` to verify `jq` is installed (required dependency)
- **PreToolUse hook**: Runs `protect-directories.sh` to check if the target file is protected before allowing Edit, Write, NotebookEdit, or Bash operations

Key files:
- `hooks/hooks.json` - Hook configuration that triggers protection checks
- `hooks/protect-directories.sh` - Main protection logic (bash script)
- `skills/claude-block/SKILL.md` - Interactive skill for creating `.claude-block` files
- `.claude-plugin/plugin.json` - Plugin metadata

## Testing the Plugin

To test protection locally:
1. Ensure `jq` is installed
2. Create a test directory with a `.claude-block` file
3. Attempt to modify files in that directory - operations should be blocked

## Git Worktrees

When creating git worktrees, use the `.worktree` folder in the project root:
```
git worktree add .worktree/<worktree-name> <branch-name>
```
