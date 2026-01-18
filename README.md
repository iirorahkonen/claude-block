# claude-block

**Protect sensitive files from accidental AI modifications.**

Drop a `.claude-block` file in any directory to control what Claude can and cannot edit. Protect configs, lock files, migrations, or entire directories with simple pattern rules.

## Why use this?

- **Prevent accidents** — Stop Claude from touching lock files, CI workflows, or database migrations
- **Scope to features** — Keep Claude focused on relevant directories, not unrelated code
- **Guide Claude** — Custom messages explain why files are protected and what to do instead
- **Zero friction** — Once set up, protection works automatically on every session

## Installation

1. Register the marketplace:

```
/plugin marketplace add iirorahkonen/claude-block-marketplace
```

2. Install the plugin:

```
/plugin install claude-block@claude-block-marketplace
```

## Usage

### Creating Protection Files

Use the `/claude-block` skill to interactively create a `.claude-block` file:

```
/claude-block
```

### Manual Creation

Create a `.claude-block` file in any directory you want to protect.

## .claude-block Format

The `.claude-block` file uses JSON format with three modes:

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

## How It Works

The plugin hooks into Claude's file operations. When Claude tries to modify a file, it checks for `.claude-block` files in the target directory and parents, then allows or blocks based on your rules.

**Key behaviors:**
- `.claude-block` files themselves are always protected (cannot be modified by Claude)
- Protection cascades to all subdirectories
- Closest `.claude-block` to the target file takes precedence

## License

MIT
