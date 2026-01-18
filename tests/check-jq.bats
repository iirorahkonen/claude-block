#!/usr/bin/env bats
# Tests for check-jq.sh hook (SessionStart hook)

load 'test_helper'

@test "check-jq exits with 0 when jq is installed" {
    # jq should be installed in test environment
    run bash "$HOOKS_DIR/check-jq.sh"
    [ "$status" -eq 0 ]
}

@test "check-jq produces no error output when jq is installed" {
    # When jq is installed, there should be no warning
    run bash "$HOOKS_DIR/check-jq.sh"
    [ "$status" -eq 0 ]
    # Output should NOT contain warning about jq not installed
    [[ "$output" != *"jq is not installed"* ]]
}

@test "check-jq is a simple script that always exits 0" {
    # The check-jq.sh script always exits 0 to not block session start
    # Even if it produces warnings, it should not fail
    run bash "$HOOKS_DIR/check-jq.sh"
    [ "$status" -eq 0 ]
}
