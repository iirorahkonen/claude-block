# Changelog

All notable changes to this project are documented in this file.

## Unreleased

## v1.3.0 (2026-02-21)

- **Subagent-aware blocking rules** (Claude Code only): `.block` files can now scope protection rules to specific subagent types using new `agents` and `disable_main_agent` configuration keys. For example, `{"agents": ["Explore"], "disable_main_agent": true}` blocks only Explore subagents while allowing the main agent and other subagent types. Rules are backward-compatible — existing `.block` files without agent keys continue to block all agents. Agent fields are inherited through hierarchical and same-directory merges with child/local overrides. (PR #26)

## v1.2.1 (2026-02-19)

- Added `CHANGELOG.md` documenting all releases from v1.0.2 through v1.2.0.
- Updated `CLAUDE.md` with changelog maintenance instructions.

## v1.2.0 (2026-02-19)

- **OpenCode support** (PR #24): Plugin now works with both Claude Code and OpenCode. OpenCode users can install `opencode-block` from npm. The TypeScript plugin reuses the same `protect_directories.py` logic via `tool.execute.before` hook, intercepting edit, write, bash, and patch tools.
- Automated npm publishing via GitHub Actions with OIDC trusted publishing (no npm tokens needed).

## v1.1.14 (2026-02-18)

- **Parent directory protection** (PR #23): Running commands like `rm -rf parent/` no longer bypasses protection when a child directory (e.g. `parent/child/.block`) has a `.block` file. The hook now scans descendant directories for `.block` files when the target is a directory.

## v1.1.13 (2026-02-11)

- **Fix**: Restored execute permissions on `run-hook.cmd` that were lost during a prior commit. Without execute permissions, the hook silently failed on Linux and macOS (Unix/POSIX systems) where file permission bits are enforced.

## v1.1.12 (2026-02-11)

- **Fix**: Added execute permissions to `run-hook.cmd`. Same issue as v1.1.13 - the polyglot script needs the executable bit set on Unix/POSIX systems (Linux, macOS). Windows is unaffected as it doesn't use Unix permission bits.

## v1.1.11 (2026-01-21)

- **Hierarchical blocked pattern inheritance** (PR #22): Child `.block` files now inherit `blocked` patterns from all parent directories. For example, if `project/.block` blocks `*.log` and `project/src/.block` blocks `generated/**`, then files in `src/` are blocked if they match either pattern. Allowed patterns still override (no inheritance). Child guide messages take precedence over parent ones.

## v1.1.10 (2026-01-21)

- **Internal**: Removed unused `_extract_paths_from_tokens` function. Fixed pyproject.toml license format and package discovery (PR #20).
- **Testing**: Added tests verifying protection works based on the target file's actual path, not the current working directory (PR #19).

## v1.1.9 (2026-01-21)

- **Fix**: Removed buggy quick-check optimization from `run-hook.cmd` (PR #18). The quick check used the current working directory to look for `.block` files, but Claude Code's working directory is the project root, not the target file's directory. This caused the hook to miss `.block` files in subdirectories, allowing edits that should have been blocked.

## v1.1.8 (2026-01-21)

- **Cross-platform polyglot hook** (PR #17): Replaced separate `.sh` and `.cmd` wrapper scripts with a single `run-hook.cmd` polyglot script that works on both Windows (as a batch file) and Linux/macOS (as a shell script). Removed jq references from documentation. Moved hook tests from BATS shell framework to pytest.

## v1.1.7 (2026-01-21)

- **Migrated from Bash/jq to Python 3** (PR #16): Replaced `protect-directories.sh` with `protect_directories.py`. **jq is no longer required** - only Python 3.8+ is needed. Migrated all tests from BATS to pytest. Removed the experimental agent-specific permissions feature. Removed the `check-jq.sh` SessionStart hook (no longer needed).

## v1.1.6 (2026-01-20)

- **Fix**: Improved jq dependency handling (PR #15). Better error messages when jq is missing or broken. Fixed macOS compatibility issue where path extraction regex didn't work with macOS's grep.

## v1.1.5 (2026-01-20)

- **Fix**: Fixed `protect-directories.sh` to verify jq actually works, not just that the binary exists. Previously, a corrupted or incompatible jq installation would cause silent failures.

## v1.1.4 (2026-01-20)

- **Fix**: Fixed jq verification to test actual functionality (PR #13, #14). Fixed Windows compatibility in jq tests. Added E2E pipeline for testing hooks with Claude Code directly.

## v1.1.3 (2026-01-19)

- **Fix**: Synced changes from plugin cache (PR #12). Removed debug logging and unused `fix_windows_json_paths`. Fixed `check-jq.sh` to always return valid JSON (was producing empty output when jq was installed).

## v1.1.2 (2026-01-19)

- **Fix**: Fixed hooks failing silently on Windows (PR #11). When Claude Code runs from `cmd.exe`, the PATH is minimal (`npm;nodejs` only) and doesn't include Git/bash. Shell scripts failed silently with "Hook output does not start with {" errors. Added `.cmd` wrapper scripts that call `bash.exe` with full path and `-l` flag for login shell. Changed hook output from stderr to stdout JSON format.

## v1.1.1 (2026-01-19)

- **Migrated from Skill to Command format** (PR #10): `/block:create` is now a command instead of a skill for better discoverability in Claude Code.

## v1.1.0 (2026-01-19)

- Updated GitHub username from `iirorahkonen` to `kodroi` (PR #9). Updated all repository references and documentation.

## v1.0.4 (2026-01-19)

- **Fix**: Fixed Windows path handling in JSON input (PR #8). Windows backslash paths (e.g. `C:\Users\...`) weren't properly JSON-escaped, causing the protection check to fail. Now handles both unescaped and already-escaped paths.

## v1.0.3 (2026-01-19)

- **Fix**: Fixed `/block:create` skill not showing up in Claude Code (PR #7). Renamed skill directory and updated frontmatter to make it discoverable as `/block:create`.

## v1.0.2 (2026-01-19) - Initial Release

- File and directory protection using `.block` configuration files
- Allowed/blocked pattern lists with glob wildcards
- Custom guide messages explaining why files are protected
- `.block.local` support for personal/machine-specific rules (not committed to git) (PR #2)
- `/block:create` command for interactive `.block` file creation
- Intercepts Edit, Write, NotebookEdit, and Bash tool operations
- Bash command detection: rm, mv, cp, touch, mkdir, rmdir, tee, and redirects
- CI pipeline with tests on Linux, macOS, and Windows (PR #3)
- Comprehensive test suite (PR #4)
