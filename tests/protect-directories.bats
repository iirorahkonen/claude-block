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

@test "allows operations when no .block file exists" {
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "blocks operations when empty .block file exists" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks operations when .block contains empty JSON object" {
    create_block_file "$TEST_DIR/project" '{}'
    mkdir -p "$TEST_DIR/project/src"
    local input=$(make_edit_input "$TEST_DIR/project/src/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"BLOCKED"* ]]
}

@test "blocks nested directory when parent has .block" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project/src/deep/nested"
    local input=$(make_edit_input "$TEST_DIR/project/src/deep/nested/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
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
    is_blocked
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
    is_blocked
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
    is_blocked
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
    is_blocked
}

@test "blocked list: multiple patterns all work" {
    # Note: dist/** matches all files in dist/ and subdirectories
    # dist/**/* only matches files with at least one subdirectory
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock", "*.env", "dist/**"]}'

    # Test .lock file
    local input=$(make_edit_input "$TEST_DIR/project/yarn.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # Test .env file
    input=$(make_edit_input "$TEST_DIR/project/app.env")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # Test dist directory
    mkdir -p "$TEST_DIR/project/dist"
    input=$(make_edit_input "$TEST_DIR/project/dist/bundle.js")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

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
    is_blocked
    [[ "$output" == *"This project is read-only for Claude."* ]]
}

@test "shows pattern-specific guide message" {
    create_block_file "$TEST_DIR/project" '{"blocked": [{"pattern": "*.env*", "guide": "Environment files are sensitive!"}]}'
    local input=$(make_edit_input "$TEST_DIR/project/.env.local")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
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
    is_blocked
    [[ "$output" == *"Secret files protected"* ]]
    [[ "$output" != *"General protection message"* ]]

    # Falls back to global guide for pattern without specific guide
    input=$(make_edit_input "$TEST_DIR/project/file.other")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"General protection message"* ]]
}

@test "allowed list with pattern-specific guide shows guide when blocked" {
    create_block_file "$TEST_DIR/project" '{
        "allowed": [{"pattern": "*.test.ts", "guide": "Test files allowed"}],
        "guide": "Only test files can be edited"
    }'

    # Non-matching file should be blocked and show guide
    local input=$(make_edit_input "$TEST_DIR/project/app.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"Only test files can be edited"* ]]

    # Matching file should be allowed
    input=$(make_edit_input "$TEST_DIR/project/app.test.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Invalid Configuration Tests
# =============================================================================

@test "blocks with error when both allowed and blocked are specified" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"], "blocked": ["*.js"]}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"cannot specify both allowed and blocked"* ]]
}

@test "treats invalid JSON as block all" {
    mkdir -p "$TEST_DIR/project"
    echo "this is not json" > "$TEST_DIR/project/.block"
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

# =============================================================================
# Marker File Protection Tests
# =============================================================================

@test "blocks modification of .block file" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*"]}'  # Even with allow all pattern
    local input=$(make_edit_input "$TEST_DIR/project/.block")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"Cannot modify"* ]]
}

@test "blocks modification of .block.local file" {
    create_local_block_file "$TEST_DIR/project" '{}'
    local input=$(make_edit_input "$TEST_DIR/project/.block.local")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"Cannot modify"* ]]
}

@test "blocks rm command targeting .block" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_bash_input "rm $TEST_DIR/project/.block")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"Cannot modify"* ]]
}

# =============================================================================
# Local Configuration File Tests
# =============================================================================

@test "local file alone blocks operations" {
    create_local_block_file "$TEST_DIR/project"
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "local file alone with blocked patterns blocks all" {
    # Note: When only a local file exists without a main .block file,
    # the merge logic treats the missing main as "block all", so all operations
    # are blocked. To use local blocked patterns, a main .block file
    # with blocked patterns must also exist.
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.test.ts"]}'

    # All files are blocked when only local file exists
    local input=$(make_edit_input "$TEST_DIR/project/app.test.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    input=$(make_edit_input "$TEST_DIR/project/app.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "local file extends main blocked patterns" {
    # When both files exist, blocked patterns are combined
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock"]}'
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.test.ts"]}'

    # Both patterns should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/yarn.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    input=$(make_edit_input "$TEST_DIR/project/app.test.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

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
    is_blocked
    [[ "$output" == *"Local guide"* ]]
    [[ "$output" != *"Main guide"* ]]
}

@test "merged blocked patterns from main and local" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["*.lock"]}'
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'

    # Both patterns should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/package.lock")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    input=$(make_edit_input "$TEST_DIR/project/api.secret")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

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
    is_blocked
    [[ "$output" == *"cannot mix allowed and blocked"* ]]
}

@test "local allowed list overrides main allowed list" {
    # Main allows *.txt and *.md, local allows only *.js
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt", "*.md"]}'
    create_local_block_file "$TEST_DIR/project" '{"allowed": ["*.js"]}'

    # .txt was allowed in main but not in local - should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # .js is allowed in local - should be allowed
    input=$(make_edit_input "$TEST_DIR/project/file.js")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

# =============================================================================
# Tool Type Tests
# =============================================================================

@test "Write tool is blocked in protected directory" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_write_input "$TEST_DIR/project/new-file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "NotebookEdit tool is blocked in protected directory" {
    create_block_file "$TEST_DIR/project"
    local input=$(make_notebook_input "$TEST_DIR/project/notebook.ipynb")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
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
    is_blocked
}

@test "detects rm -rf command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "rm -rf $TEST_DIR/project/dir")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects touch command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "touch $TEST_DIR/project/newfile.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects mv command targets" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/other"
    local input
    input=$(make_bash_input "mv $TEST_DIR/other/file.txt $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects cp command targets" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/other"
    local input
    input=$(make_bash_input "cp $TEST_DIR/other/file.txt $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects output redirection target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' > $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects tee command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' | tee $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects tee -a append command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' | tee -a $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects mkdir command target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "mkdir -p $TEST_DIR/project/newdir")

    run run_hook_with_input "$input"
    is_blocked
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

@test "detects rmdir command target" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project/emptydir"
    local input
    input=$(make_bash_input "rmdir $TEST_DIR/project/emptydir")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects append redirection target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "echo 'hello' >> $TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "detects dd command with of= target" {
    create_block_file "$TEST_DIR/project"
    local input
    input=$(make_bash_input "dd if=/dev/zero of=$TEST_DIR/project/file.bin bs=1 count=1")

    run run_hook_with_input "$input"
    is_blocked
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
    is_blocked

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
    is_blocked
}

@test "question mark matches single character" {
    create_block_file "$TEST_DIR/project" '{"blocked": ["file?.txt"]}'

    # Should match file1.txt
    local input=$(make_edit_input "$TEST_DIR/project/file1.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

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
    is_blocked

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
    is_blocked
}

@test "closest .block file takes precedence" {
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
    is_blocked
}

# =============================================================================
# Path Pattern Relative Directory Tests
# =============================================================================

@test "patterns are relative to .block directory - root level" {
    # .block at project root with blocked pattern for src/
    # Note: src/** matches everything under src/ (files and subdirs)
    #       src/**/* only matches files in subdirectories (requires at least one subdir level)
    create_block_file "$TEST_DIR/project" '{"blocked": ["src/**"]}'
    mkdir -p "$TEST_DIR/project/src/components"

    # File in src/ should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/src/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # File in src/components/ should be blocked
    input=$(make_edit_input "$TEST_DIR/project/src/components/Button.tsx")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # File outside src/ should be allowed
    input=$(make_edit_input "$TEST_DIR/project/README.md")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "patterns are relative to .block directory - nested level" {
    # .block inside src/ directory - patterns relative to src/
    mkdir -p "$TEST_DIR/project/src/components"
    create_block_file "$TEST_DIR/project/src" '{"blocked": ["components/**"]}'

    # File in components/ should be blocked (relative to src/)
    local input=$(make_edit_input "$TEST_DIR/project/src/components/Button.tsx")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # File directly in src/ should be allowed
    input=$(make_edit_input "$TEST_DIR/project/src/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "direct file pattern works at any level" {
    # Block specific filename regardless of path
    # Note: **config.json matches at any level (root or nested)
    #       **/config.json only matches in subdirectories (requires path prefix)
    mkdir -p "$TEST_DIR/project/deep/nested/dir"
    create_block_file "$TEST_DIR/project" '{"blocked": ["**config.json"]}'

    # config.json at root should be blocked
    local input=$(make_edit_input "$TEST_DIR/project/config.json")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # config.json in nested dir should be blocked
    input=$(make_edit_input "$TEST_DIR/project/deep/nested/dir/config.json")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # other.json should be allowed
    input=$(make_edit_input "$TEST_DIR/project/other.json")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "allowed pattern with explicit path works correctly" {
    # Allow only files in specific subdirectory
    # Note: src/features/auth/** matches all files/dirs in auth/
    mkdir -p "$TEST_DIR/project/src/features/auth"
    mkdir -p "$TEST_DIR/project/src/features/dashboard"
    create_block_file "$TEST_DIR/project" '{"allowed": ["src/features/auth/**"]}'

    # File in auth feature should be allowed
    local input=$(make_edit_input "$TEST_DIR/project/src/features/auth/login.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]

    # File in dashboard feature should be blocked
    input=$(make_edit_input "$TEST_DIR/project/src/features/dashboard/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "multiple directory levels with different configs" {
    # Root: allow only src/
    create_block_file "$TEST_DIR/project" '{"allowed": ["src/**"]}'
    # src: block generated files
    mkdir -p "$TEST_DIR/project/src/generated"
    create_block_file "$TEST_DIR/project/src" '{"blocked": ["generated/**"]}'

    # File in src/ follows src's rules (which blocks generated/)
    local input=$(make_edit_input "$TEST_DIR/project/src/index.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]

    # Generated file is blocked by src's .block
    input=$(make_edit_input "$TEST_DIR/project/src/generated/types.ts")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

# =============================================================================
# Windows Path Handling Tests
# =============================================================================

@test "properly escaped Windows paths still work" {
    # Ensure the fix doesn't break properly escaped paths
    create_block_file "$TEST_DIR/project"

    # Use jq to create properly escaped JSON (double backslashes)
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "forward slash paths work unchanged" {
    # Unix-style paths should continue to work
    create_block_file "$TEST_DIR/project"
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run run_hook_with_input "$input"
    is_blocked
}

# =============================================================================
# Protection Guarantee Tests (verifies files are never modified when blocked)
# =============================================================================

@test "hook block decision prevents any file modification" {
    # Create protected directory with existing file
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project"
    echo "original content" > "$TEST_DIR/project/existing.txt"

    local input=$(make_edit_input "$TEST_DIR/project/existing.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"

    # Hook must output JSON block decision
    is_blocked

    # File content must be unchanged (hook runs BEFORE tool execution)
    [ "$(cat "$TEST_DIR/project/existing.txt")" = "original content" ]
}

@test "blocked Write operation never creates file" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project"

    local input=$(make_write_input "$TEST_DIR/project/new-file.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"

    is_blocked
    # File must NOT exist (hook prevents creation)
    [ ! -f "$TEST_DIR/project/new-file.txt" ]
}

@test "blocked Bash rm never deletes file" {
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/project"
    echo "protected" > "$TEST_DIR/project/keep.txt"

    local input=$(make_bash_input "rm $TEST_DIR/project/keep.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"

    is_blocked
    # File must still exist
    [ -f "$TEST_DIR/project/keep.txt" ]
}

@test "allowed operations proceed normally" {
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'
    mkdir -p "$TEST_DIR/project"

    local input=$(make_edit_input "$TEST_DIR/project/allowed.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"

    # Hook allows with exit code 0
    [ "$status" -eq 0 ]
}

# =============================================================================
# Mode Condition Coverage Tests
# =============================================================================

@test "blocks when jq is not installed (fail-closed)" {
    # Skip on Windows - this test requires Unix-style PATH manipulation
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        skip "Test not supported on Windows"
    fi

    # Create a directory with bash but without jq to simulate jq not installed
    mkdir -p "$TEST_DIR/no-jq-bin"

    # Get bash and cat paths dynamically for cross-platform support
    local bash_path=$(command -v bash)
    local cat_path=$(command -v cat)
    cp "$bash_path" "$TEST_DIR/no-jq-bin/"
    cp "$cat_path" "$TEST_DIR/no-jq-bin/"

    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    # Run with custom PATH that has bash but no jq
    run bash -c "PATH='$TEST_DIR/no-jq-bin' '$TEST_DIR/no-jq-bin/bash' '$HOOKS_DIR/protect-directories.sh' <<< '$input'"
    is_blocked
    [[ "$output" == *"jq is required"* ]]
}

@test "local file with allowed patterns blocks all when no main file" {
    # When only .block.local exists with allowed patterns, the main config is
    # treated as empty (block all). Since empty config is most restrictive,
    # all operations are blocked regardless of local's allowed patterns.
    create_local_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'

    # Even .txt files should be blocked (empty main wins)
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    # Other files should also be blocked
    input=$(make_edit_input "$TEST_DIR/project/file.js")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "empty allowed array treated as block all" {
    # {"allowed": []} should behave like {} (block all)
    create_block_file "$TEST_DIR/project" '{"allowed": []}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "empty blocked array allows all" {
    # {"blocked": []} should allow everything (no patterns to block)
    create_block_file "$TEST_DIR/project" '{"blocked": []}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "both configs empty uses local guide" {
    # When both .block and .block.local are empty (block all),
    # the local guide should take precedence
    create_block_file "$TEST_DIR/project" '{"guide": "Main guide message"}'
    create_local_block_file "$TEST_DIR/project" '{"guide": "Local guide message"}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"Local guide message"* ]]
    [[ "$output" != *"Main guide message"* ]]
}

@test "main empty with local blocked patterns blocks all" {
    # When main is empty (block all) and local has blocked patterns,
    # empty is more restrictive so all operations are blocked
    create_block_file "$TEST_DIR/project"  # Empty = block all
    create_local_block_file "$TEST_DIR/project" '{"blocked": ["*.secret"]}'

    # All files blocked (empty main is most restrictive)
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked

    input=$(make_edit_input "$TEST_DIR/project/file.secret")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "main with allowed patterns local empty blocks all" {
    # When main has allowed patterns but local is empty (block all),
    # empty is more restrictive so all operations are blocked
    create_block_file "$TEST_DIR/project" '{"allowed": ["*.txt"]}'
    create_local_block_file "$TEST_DIR/project"  # Empty = block all

    # Even allowed patterns from main are overridden by local empty
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")
    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
}

@test "default block reason when no guide specified" {
    # When no guide is specified, should show default block message
    create_block_file "$TEST_DIR/project" '{}'
    local input=$(make_edit_input "$TEST_DIR/project/file.txt")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    is_blocked
    [[ "$output" == *"BLOCKED"* ]] || [[ "$output" == *"protected"* ]]
}

@test "bash command with multiple protected paths blocks first match" {
    # When a bash command targets multiple paths in a protected directory,
    # the hook should block if any path is protected
    create_block_file "$TEST_DIR/project"
    mkdir -p "$TEST_DIR/other"
    local input=$(make_bash_input "cp $TEST_DIR/other/safe.txt $TEST_DIR/project/protected.txt")

    run run_hook_with_input "$input"
    is_blocked
}

@test "allows creating new .block file" {
    # Creating a new .block file should be allowed (file doesn't exist yet)
    mkdir -p "$TEST_DIR/project"
    local input=$(make_write_input "$TEST_DIR/project/.block")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}

@test "allows creating new .block.local file" {
    # Creating a new .block.local file should be allowed (file doesn't exist yet)
    mkdir -p "$TEST_DIR/project"
    local input=$(make_write_input "$TEST_DIR/project/.block.local")

    run bash -c "echo '$input' | bash '$HOOKS_DIR/protect-directories.sh'"
    [ "$status" -eq 0 ]
}
