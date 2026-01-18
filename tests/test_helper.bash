#!/bin/bash
# Test helper functions for claude-block hook tests

# Path to hooks directory
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../hooks" && pwd)"
TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create a temporary test directory
# Uses BATS_TEST_TMPDIR if available (BATS 1.5+), otherwise creates a unique temp dir
setup_test_dir() {
    if [[ -n "$BATS_TEST_TMPDIR" ]]; then
        TEST_DIR="$BATS_TEST_TMPDIR"
    else
        TEST_DIR=$(mktemp -d)
    fi
    export TEST_DIR
    # Don't cd into TEST_DIR - keep working from project root
    # This prevents issues with relative paths to HOOKS_DIR
}

# Clean up temporary test directory
teardown_test_dir() {
    # Only clean up if we created the temp dir ourselves (not using BATS_TEST_TMPDIR)
    if [[ -z "$BATS_TEST_TMPDIR" && -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
}

# Create a .claude-block file with given content
create_block_file() {
    local dir="${1:-.}"
    local content="${2:-}"

    mkdir -p "$dir"
    if [[ -n "$content" ]]; then
        echo "$content" > "$dir/.claude-block"
    else
        touch "$dir/.claude-block"
    fi
}

# Create a .claude-block.local file with given content
create_local_block_file() {
    local dir="${1:-.}"
    local content="${2:-}"

    mkdir -p "$dir"
    if [[ -n "$content" ]]; then
        echo "$content" > "$dir/.claude-block.local"
    else
        touch "$dir/.claude-block.local"
    fi
}

# Run the protect-directories hook with given input JSON
run_protect_hook() {
    local input="$1"
    echo "$input" | bash "$HOOKS_DIR/protect-directories.sh" 2>&1
    return "${PIPESTATUS[1]}"
}

# Run the protect-directories hook using printf (more robust for complex inputs)
# This is a wrapper that should be called with BATS 'run' command:
# run run_hook_with_input "$input"
# After calling, check $status for exit code and $output for stdout/stderr
run_hook_with_input() {
    local input="$1"
    printf '%s' "$input" | bash "$HOOKS_DIR/protect-directories.sh" 2>&1
}

# Run the check-jq hook
run_check_jq_hook() {
    bash "$HOOKS_DIR/check-jq.sh" 2>&1
    return $?
}

# Create a hook input JSON for Edit tool
make_edit_input() {
    local file_path="$1"
    jq -n --arg path "$file_path" '{
        tool_name: "Edit",
        tool_input: {
            file_path: $path,
            old_string: "old",
            new_string: "new"
        }
    }'
}

# Create a hook input JSON for Write tool
make_write_input() {
    local file_path="$1"
    jq -n --arg path "$file_path" '{
        tool_name: "Write",
        tool_input: {
            file_path: $path,
            content: "test content"
        }
    }'
}

# Create a hook input JSON for Bash tool
make_bash_input() {
    local command="$1"
    jq -n --arg cmd "$command" '{
        tool_name: "Bash",
        tool_input: {
            command: $cmd
        }
    }'
}

# Create a hook input JSON for NotebookEdit tool
make_notebook_input() {
    local notebook_path="$1"
    jq -n --arg path "$notebook_path" '{
        tool_name: "NotebookEdit",
        tool_input: {
            notebook_path: $path,
            cell_number: 0,
            new_source: "# test"
        }
    }'
}

# Assert that output contains a string
assert_output_contains() {
    local expected="$1"
    local actual="$2"
    if [[ "$actual" != *"$expected"* ]]; then
        echo "Expected output to contain: $expected"
        echo "Actual output: $actual"
        return 1
    fi
}

# Assert that output does not contain a string
assert_output_not_contains() {
    local not_expected="$1"
    local actual="$2"
    if [[ "$actual" == *"$not_expected"* ]]; then
        echo "Expected output to NOT contain: $not_expected"
        echo "Actual output: $actual"
        return 1
    fi
}
