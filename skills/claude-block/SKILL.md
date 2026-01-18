---
name: claude-block
description: Create and manage .claude-block files for directory protection. Use when you need to protect directories from Claude modifications.
---

# .claude-block Creator

This skill helps you create .claude-block files to protect directories from Claude Code modifications.

## When to Use

- User wants to protect a directory from Claude modifications
- User asks about .claude-block files
- User wants to restrict which files Claude can edit
- User says "lock", "protect", or "restrict" in context of files/directories

## .claude-block Format Reference

### Block All (Empty or `{}`)
```json
{}
```
Blocks all file modifications in the directory.

### Allowed List Mode
```json
{
  "allowed": ["*.test.ts", "tests/**/*"]
}
```
Only files matching these patterns can be edited.

### Blocked List Mode
```json
{
  "blocked": ["*.config.js", "secrets/**/*"]
}
```
Files matching these patterns are protected; all others can be edited.

### With Guide Messages
```json
{
  "blocked": ["migrations/**/*"],
  "guide": "This directory contains database migrations. Ask the user before modifying."
}
```

### Pattern-Specific Guides
```json
{
  "blocked": [
    { "pattern": "*.env*", "guide": "Environment files contain secrets." }
  ]
}
```

## Workflow

### Step 1: Ask Protection Mode

Use AskUserQuestion to determine the protection mode:

```
Question: "What type of protection do you need?"
Header: "Mode"
Options:
1. "Block all" - "Prevent all modifications in this directory"
2. "Allowed list" - "Only allow specific file patterns to be edited"
3. "Blocked list" - "Protect specific file patterns, allow everything else"
```

### Step 2: Ask Directory Location

```
Question: "Where should the .claude-block file be created?"
Header: "Location"
Options:
1. "Current directory" - "Create in the current working directory"
2. "Specify path" - "Enter a custom directory path"
```

If user chooses "Specify path", ask them to provide the path.

### Step 3: Ask for Patterns (if not Block All)

If the user chose "Allowed list" or "Blocked list":

**Do NOT use AskUserQuestion here.** Instead, ask the user in plain text to describe what files they want to protect or allow. Let them describe in their own words.

Example prompt:
> "What files should be [allowed/protected]? Describe in your own words - for example: 'test files', 'the migrations folder', 'environment files', 'anything in src/generated'."

After the user describes what they want, translate their description into glob patterns:
- "test files" -> `*.test.ts`, `*.spec.ts`, `**/*.test.*`
- "migrations folder" -> `migrations/**/*`
- "environment files" -> `*.env*`, `.env.*`
- "generated code" -> `src/generated/**/*`

Pattern syntax reference:
- `*` - matches any characters except path separator
- `**` - matches any characters including path separator (recursive)
- `?` - matches single character
- `{a,b}` - matches either a or b

### Step 4: Ask About Guide Message

**Do NOT use AskUserQuestion here.** Ask in plain text:

> "Would you like to add a guide message? This message is shown to Claude when it tries to modify protected files. For example: 'These are migration files - ask before modifying' or 'This folder contains generated code - do not edit manually'."

If the user provides a message, include it. If they say no or skip, omit the guide field.

### Step 5: Generate the File

Based on the collected information, generate the .claude-block file:

**Block All Mode:**
```json
{}
```

**Allowed List Mode:**
```json
{
  "allowed": ["pattern1", "pattern2"],
  "guide": "Optional guide message"
}
```

**Blocked List Mode:**
```json
{
  "blocked": ["pattern1", "pattern2"],
  "guide": "Optional guide message"
}
```

Write the file to the specified location using the Write tool.

### Step 6: Confirm Creation

After creating the file, confirm to the user:
- File location
- Protection mode
- Patterns configured (if any)
- Guide message (if any)

Remind the user that they can edit the file manually to adjust settings.
