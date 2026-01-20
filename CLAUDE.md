# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code plugin that provides file and directory protection using `.block` configuration files. When installed, the plugin intercepts file modification operations (Edit, Write, NotebookEdit, Bash) and blocks them based on protection rules.

## Architecture

The plugin uses Claude Code's hook system with Node.js 24:
- **SessionStart hook**: Runs `session-start.mjs` (simple continue hook)
- **PreToolUse hook**: Runs `protect-directories.mjs` to check if the target file is protected before allowing Edit, Write, NotebookEdit, or Bash operations

Key files:
- `hooks/hooks.json` - Hook configuration that triggers protection checks
- `hooks/protect-directories.mjs` - Main protection logic (Node.js)
- `hooks/session-start.mjs` - Session start hook (Node.js)
- `commands/create.md` - Interactive command for creating `.block` files
- `.claude-plugin/plugin.json` - Plugin metadata

## Testing the Plugin

To test protection locally:
1. Ensure Node.js 24+ is installed
2. Run tests with `npm test`
3. Create a test directory with a `.block` file
4. Attempt to modify files in that directory - operations should be blocked

## Git Worktrees

When creating git worktrees, use the `.worktree` folder in the project root:
```
git worktree add .worktree/<worktree-name> <branch-name>
```
