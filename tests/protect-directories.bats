#!/usr/bin/env bats
# Tests for protect-directories.sh hook

load 'test_helper'

setup() {
    setup_test_dir
}

teardown() {
    teardown_test_dir
}

# =============================================================================
# Basic Protection Tests
# =============================================================================

@test "allows operations when no .claude-block file exists" {
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "blocks operations when empty .claude-block file exists" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks operations when .claude-block contains empty JSON object" {
    create_block_file "$TEST_DIR/project" '{}'
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks nested directory when parent has .claude-block" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project/src/deep/nested"
    local input=$(make_edit_input "$TEST_DIR/project/src/deep/nested/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

# =============================================================================
# Allowed Pattern Tests
# =============================================================================

@test "allowed list: allows matching file" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "allowed list: blocks non-matching file" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'
    local input=$(make_edit_input "$TEST_DIR/project/file.js")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "allowed list: allows nested matching file with **" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["src/**/*.ts"]}'
    mkdir -p "$TEST_DIR/project/src/deep"
    local input=$(make_edit_input "$TEST_DIR/project/src/deep/file.ts")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "allowed list: blocks file outside allowed pattern" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["src/**/*.ts"]}'
    mkdir -p "$TEST_DIR/project/lib"
    local input=$(make_edit_input "$TEST_DIR/project/lib/file.ts")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "allowed list: allows multiple patterns" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.md", "*.txt", "docs/**/*"]}'
    mkdir -p "$TEST_DIR/project/docs/guide"

    # Test .md file
    local input=$(make_edit_input "$TEST_DIR/project/README.md")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]

    # Test .txt file
    input=$(make_edit_input "$TEST_DIR/project/notes.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]

    # Test docs subdirectory
    input=$(make_edit_input "$TEST_DIR/project/docs/guide/intro.html")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Blocked Pattern Tests
# =============================================================================

@test "blocked list: blocks matching file" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'
    local input=$(make_edit_input "$TEST_DIR/project/config.secret")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"BLOCKED"* ]]
}

@test "blocked list: allows non-matching file" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'
    local input=$(make_edit_input "$TEST_DIR/project/config.json")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "blocked list: blocks nested directory with **" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["node_modules/**/*"]}'
    mkdir -p "$TEST_DIR/project/node_modules/package/dist"
    local input=$(make_edit_input "$TEST_DIR/project/node_modules/package/dist/index.js")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "blocked list: multiple patterns all work" {
    # Note: dist/** matches all files in dist/ and subdirectories
    # dist/**/* only matches files with at least one subdirectory
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock", "*.env", "dist/**"]}'

    # Test .lock file
    local input=$(make_edit_input "$TEST_DIR/project/yarn.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Test .env file
    input=$(make_edit_input "$TEST_DIR/project/app.env")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Test dist directory
    mkdir -p "$TEST_DIR/project/dist"
    input=$(make_edit_input "$TEST_DIR/project/dist/bundle.js")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Non-blocked file should be allowed
    input=$(make_edit_input "$TEST_DIR/project/src/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Guide Message Tests
# =============================================================================

@test "shows global guide message when blocked" {
    create_block_file "$TEST_DIR/project" '{"guide": "This project is read-only for Claude."}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"This project is read-only for Claude."* ]]
}

@test "shows pattern-specific guide message" {
    create_block_file "$TEST_DIR/project" '{"blocked": [{"pattern": "*.env*", "guide": "Environment files are sensitive!"}]}'
    local input=$(make_edit_input "$TEST_DIR/project/.env.local")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Environment files are sensitive!"* ]]
}

@test "pattern-specific guide takes precedence over global guide" {
    create_block_file "$TEST_DIR/project" '{
        "blocked": [{"pattern": "*.secret", "guide": "Secret files protected"}, "*.other"],
        "guide": "General protection message"
    }'

    # Pattern-specific guide
    local input=$(make_edit_input "$TEST_DIR/project/api.secret")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Secret files protected"* ]]
    [[ "$output" != *"General protection message"* ]]

    # Falls back to global guide for pattern without specific guide
    input=$(make_edit_input "$TEST_DIR/project/file.other")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"General protection message"* ]]
}

# =============================================================================
# Invalid Configuration Tests
# =============================================================================

@test "blocks with error when both allowed and blocked are specified" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"], "blocked": ["*.js"]}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"cannot specify both allowed and blocked"* ]]
}

@test "treats invalid JSON as block all" {
    mkdir -p "$TEST_DIR/project"
    echo "this is not json" > "$TEST_DIR/project/.claude-block"
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

# =============================================================================
# Marker File Protection Tests
# =============================================================================

@test "blocks modification of .claude-block file" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*"]}'  # Even with allow all pattern
    local input=$(make_edit_input "$TEST_DIR/project/.claude-block")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Cannot modify"* ]]
}

@test "blocks modification of .claude-block.local file" {
    create_local_block_file "$TEST_DIR/project" '{}'
    local input=$(make_edit_input "$TEST_DIR/project/.claude-block.local")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Cannot modify"* ]]
}

@test "blocks rm command targeting .claude-block" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_bash_input "rm $TEST_DIR/project/.claude-block")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Cannot modify"* ]]
}

# =============================================================================
# Local Configuration File Tests
# =============================================================================

@test "local file alone blocks operations" {
    create_local_block_file "$TEST_DIR/project"
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "local file alone with blocked patterns blocks all" {
    # Note: When only a local file exists without a main .claude-block file,
    # the merge logic treats the missing main as "block all", so all operations
    # are blocked. To use local blocked patterns, a main .claude-block file
    # with blocked patterns must also exist.
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.test.ts"]}'

    # All files are blocked when only local file exists
    local input=$(make_edit_input "$TEST_DIR/project/app.test.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    input=$(make_edit_input "$TEST_DIR/project/app.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "local file extends main blocked patterns" {
    # When both files exist, blocked patterns are combined
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock"]}'
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.test.ts"]}'

    # Both patterns should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/yarn.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    input=$(make_edit_input "$TEST_DIR/project/app.test.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Non-blocked file should be allowed
    input=$(make_edit_input "$TEST_DIR/project/app.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "local guide overrides main guide" {
    create_block_file "$TEST_DIR/project" '{"guide": "Main guide"}'
    create_local_block_file "$TEST_DIR/project" '{"guide": "Local guide"}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"Local guide"* ]]
    [[ "$output" != *"Main guide"* ]]
}

@test "merged blocked patterns from main and local" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock"]}'
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'

    # Both patterns should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/package.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    input=$(make_edit_input "$TEST_DIR/project/api.secret")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Non-blocked file should be allowed
    input=$(make_edit_input "$TEST_DIR/project/config.json")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "cannot mix allowed and blocked between main and local" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
    [[ "$output" == *"cannot mix allowed and blocked"* ]]
}

# =============================================================================
# Tool Type Tests
# =============================================================================

@test "Write tool is blocked in protected directory" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_write_input "$TEST_DIR/project/new-file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "NotebookEdit tool is blocked in protected directory" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_notebook_input "$TEST_DIR/project/notebook.ipynb")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "unknown tools are allowed" {
    create_block_file "$TEST_DIR/project"
    local input='{"tool_name": "UnknownTool", "tool_input": {"path": "'$TEST_DIR'/project/file.txt"}}'

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Bash Command Detection Tests
# =============================================================================

@test "detects rm command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "rm $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects rm -rf command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "rm -rf $TEST_DIR/project/dir")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects touch command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "touch $TEST_DIR/project/newfile.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects mv command targets" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/other"
    local input
    input=$(make_bash_input "mv $TEST_DIR/other/file.txt $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects cp command targets" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/other"
    local input
    input=$(make_bash_input "cp $TEST_DIR/other/file.txt $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects output redirection target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' > $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects tee command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' | tee $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "detects mkdir command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "mkdir -p $TEST_DIR/project/newdir")

    run run_hook_with_input "$input"
    [ "$status" -eq 2 ]
}

@test "allows read-only bash commands" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "cat $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    [ "$status" -eq 0 ]
}

@test "allows ls command in protected directory" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "ls -la $TEST_DIR/project/")

    run run_hook_with_input "$input"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Wildcard Pattern Tests
# =============================================================================

@test "single asterisk does not match path separator" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["src/*.ts"]}'
    mkdir -p "$TEST_DIR/project/src/deep"

    # Should match direct child
    local input=$(make_edit_input "$TEST_DIR/project/src/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Should NOT match nested file (single * doesn't cross directories)
    input=$(make_edit_input "$TEST_DIR/project/src/deep/nested.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "double asterisk matches path separator" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["src/**/*.ts"]}'
    mkdir -p "$TEST_DIR/project/src/deep/nested"

    # Should match nested file
    local input=$(make_edit_input "$TEST_DIR/project/src/deep/nested/file.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "question mark matches single character" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["file?.txt"]}'

    # Should match file1.txt
    local input=$(make_edit_input "$TEST_DIR/project/file1.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Should NOT match file12.txt
    input=$(make_edit_input "$TEST_DIR/project/file12.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "pattern with dots works correctly" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.config.ts"]}'

    # Should match
    local input=$(make_edit_input "$TEST_DIR/project/app.config.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]

    # Should NOT match (dots are literal)
    input=$(make_edit_input "$TEST_DIR/project/appXconfigXts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Edge Cases
# =============================================================================

@test "handles empty input gracefully" {
    run bash -c "echo '' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "handles malformed JSON input gracefully" {
    run bash -c "echo 'not json' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "handles missing tool_name gracefully" {
    run bash -c "echo '{}' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "handles paths with spaces" {
    mkdir -p "$TEST_DIR/my project"
    create_block_file "$TEST_DIR/my project"
    local input=$(make_edit_input "$TEST_DIR/my project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}

@test "closest .claude-block file takes precedence" {
    # Parent directory blocks everything
    create_block_file "$TEST_DIR/project"
    # Child directory allows .txt files
    create_block_file "$TEST_DIR/project/src" '{"allowed": ["*.txt"]}'

    # File in child directory should follow child's rules
    local input=$(make_edit_input "$TEST_DIR/project/src/notes.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]

    # Non-allowed file should be blocked
    input=$(make_edit_input "$TEST_DIR/project/src/code.js")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 2 ]
}
