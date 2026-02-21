# Block

**Protect files from unwanted AI modifications in [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenCode](https://opencode.ai).**

Drop a `.block` file in any directory to control what AI agents can and cannot edit. Protect configs, lock files, migrations, or entire directories with simple pattern rules.

## Why use this?

- **Prevent accidents** — Stop Claude from touching lock files, CI workflows, or database migrations
- **Scope to features** — Keep Claude focused on relevant directories, not unrelated code
- **Guide Claude** — Custom messages explain why files are protected and what to do instead
- **Zero friction** — Once set up, protection works automatically on every session

## Requirements

- **Python 3.8+** — Required for the protection hook

## Installation

### Claude Code

1. Register the marketplace:

```
/plugin marketplace add kodroi/block-marketplace
```

2. Install the plugin:

```
/plugin install block@block-marketplace
```

### OpenCode

Add the plugin to your `opencode.json` config:

```json
{
  "plugins": ["opencode-block"]
}
```

Or for local development, clone this repo and reference the plugin directly:

```json
{
  "plugins": ["file:///path/to/block/opencode/index.ts"]
}
```

You can also set up the plugin manually by copying files into your project. The plugin expects `hooks/protect_directories.py` to be a sibling of the directory containing `index.ts`:

```
your-project/
├── .opencode/
│   └── plugin/
│       └── index.ts              # copied from opencode/index.ts
├── hooks/
│   └── protect_directories.py    # copied from hooks/protect_directories.py
```

> **Note:** The `tool.execute.before` hook protects tools called by the primary agent. Tools invoked by subagents spawned via the `task` tool may not be intercepted.

## Usage

Use the `/block:create` command to interactively create a `.block` file:

```
/block:create
```

Or create a `.block` file manually in any directory you want to protect.

## .block Format

The `.block` file uses JSON format with three modes:

### Block All (Default)

Empty file or `{}` blocks all modifications:

```json
{}
```

### Allowed List

Only allow specific patterns, block everything else:

```json
{
  "allowed": ["*.test.ts", "tests/**/*", "docs/*.md"]
}
```

### Blocked List

Block specific patterns, allow everything else:

```json
{
  "blocked": ["*.lock", "package-lock.json", "migrations/**/*", ".github/**/*"]
}
```

### Guide Messages

Add a message shown when Claude tries to modify protected files:

```json
{
  "blocked": ["migrations/**/*"],
  "guide": "Database migrations are protected. Ask before modifying."
}
```

### Pattern-Specific Guides

Different messages for different patterns:

```json
{
  "blocked": [
    { "pattern": "*.lock", "guide": "Lock files are auto-generated. Run the package manager instead." },
    { "pattern": ".github/**/*", "guide": "CI workflows need manual review." }
  ],
  "guide": "This directory has protected files."
}
```

### Scope to Feature

Keep Claude focused on specific directories during feature work:

```json
{
  "allowed": ["src/features/auth/**/*", "src/components/auth/**/*", "tests/auth/**/*"],
  "guide": "Working on auth feature. Only touching auth-related files."
}
```

### Agent-Specific Rules (Claude Code only)

Scope protection to specific subagent types. For example, only allow a TDD agent to write test files:

```
tests/
└── .block      → {"agents": ["TDD_agent"], "disable_main_agent": true}
```

This blocks all subagents except `TDD_agent` from writing to `tests/`, while the main agent is also exempt.

| Key | Type | Description |
|-----|------|-------------|
| `agents` | `string[]` | Subagent types to block (e.g. `"TDD_agent"`, `"Bash"`) |
| `disable_main_agent` | `bool` | When `true`, the main agent is exempt from blocking |

**Truth table:**

| Config | Main agent | Listed subagents | Other subagents |
|--------|-----------|-----------------|-----------------|
| No agent keys | Blocked | Blocked | Blocked |
| `agents: ["TDD_agent"]` | Blocked | Blocked | Allowed |
| `disable_main_agent: true` | Allowed | Blocked | Blocked |
| Both keys set | Allowed | Blocked | Allowed |
| `agents: []` | Blocked | Allowed | Allowed |

Existing `.block` files without agent keys continue to block all agents (backward-compatible). Agent fields are inherited through hierarchical merges, with child/local files overriding parent values.

## Pattern Syntax

| Pattern | Description |
|---------|-------------|
| `*` | Matches any characters except path separator |
| `**` | Matches any characters including path separator (recursive) |
| `?` | Matches single character |

### Examples

| Pattern | Matches |
|---------|---------|
| `*.ts` | All TypeScript files in the directory |
| `**/*.ts` | All TypeScript files recursively |
| `src/**/*` | Everything under src/ |
| `*.test.*` | Files with .test. in the name |
| `config?.json` | config1.json, configA.json, etc. |

## Local Configuration Files

For personal or machine-specific protection rules that shouldn't be committed to git, use `.block.local`:

```json
{
  "blocked": [".env.local", ".env.*.local", "appsettings.Development.json"]
}
```

Add `.block.local` to your `.gitignore`.

When both files exist in the same directory:
- Blocked patterns are combined (union)
- Allowed patterns and guide messages use local file
- Cannot mix `allowed` and `blocked` modes between files

## How It Works

The plugin hooks into file operations from Claude Code and OpenCode. When the AI agent tries to modify a file, the plugin checks for `.block` files in the target directory and all parent directories, then combines their rules.

- **Claude Code**: Uses a PreToolUse hook to intercept Edit, Write, NotebookEdit, and Bash tools
- **OpenCode**: Uses a `tool.execute.before` hook to intercept edit, write, bash, and patch tools

- `.block` files themselves are always protected
- Protection cascades to all subdirectories

### Hierarchical Inheritance

When multiple `.block` files exist in the directory hierarchy:

**Blocked patterns are combined (union)**:
```
project/
├── .block          → {"blocked": ["*.log", "*.tmp"]}
└── src/
    └── .block      → {"blocked": ["generated/**"]}
```
Files in `src/` are blocked if they match ANY pattern from either file (`*.log`, `*.tmp`, OR `generated/**`).

**Allowed patterns override completely**:
```
project/
├── .block          → {"blocked": ["*.lock"]}
└── features/
    └── .block      → {"allowed": ["*.ts"]}
```
The `allowed` in `features/` completely overrides the parent — only `*.ts` files can be modified.

**Guide messages from the closest file take precedence**:
When files are blocked by an inherited pattern, the guide message from the closest `.block` file is shown.

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=hooks --cov-report=term-missing
```

### Project Structure

```
block/
├── hooks/
│   ├── protect_directories.py   # Main protection logic (Python)
│   ├── subagent_tracker.py      # Subagent event tracker (Claude Code)
│   ├── run-hook.cmd             # Cross-platform entry point (Claude Code)
│   └── run-subagent-hook.cmd    # Subagent hook entry point (Claude Code)
├── opencode/
│   ├── index.ts                 # OpenCode plugin entry point
│   └── package.json             # npm package metadata
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_basic_protection.py
│   ├── test_allowed_patterns.py
│   ├── test_blocked_patterns.py
│   ├── test_guide_messages.py
│   ├── test_local_config.py
│   ├── test_invalid_config.py
│   ├── test_marker_file_protection.py
│   ├── test_tool_types.py
│   ├── test_bash_commands.py
│   ├── test_wildcards.py
│   └── test_edge_cases.py
├── commands/
│   └── create.md                # Interactive command (Claude Code)
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata (Claude Code)
└── pyproject.toml               # Python project config
```

## License

MIT
