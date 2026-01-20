# Block

**A Claude Code plugin to protect files from unwanted modifications.**

Drop a `.block` file in any directory to control what Claude can and cannot edit. Protect configs, lock files, migrations, or entire directories with simple pattern rules.

## Why use this?

- **Prevent accidents** — Stop Claude from touching lock files, CI workflows, or database migrations
- **Scope to features** — Keep Claude focused on relevant directories, not unrelated code
- **Guide Claude** — Custom messages explain why files are protected and what to do instead
- **Zero friction** — Once set up, protection works automatically on every session

## Requirements

- **Python 3.8+** — Required for the protection hook

## Installation

1. Register the marketplace:

```
/plugin marketplace add kodroi/block-marketplace
```

2. Install the plugin:

```
/plugin install block@block-marketplace
```

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

The plugin hooks into Claude's file operations. When Claude tries to modify a file, it checks for `.block` files in the target directory and parents, then allows or blocks based on your rules.

- `.block` files themselves are always protected
- Protection cascades to all subdirectories
- Closest configuration to the target file takes precedence

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
│   ├── protect_directories.py   # Main protection logic
│   ├── protect-directories.sh   # Unix wrapper
│   └── protect-directories.cmd  # Windows wrapper
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
│   └── create.md                # Interactive command
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata
└── pyproject.toml               # Python project config
```

## License

MIT
