#!/bin/bash
# Test runner script for claude-block hooks
# Uses BATS (Bash Automated Testing System)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================"
echo "Claude Block Hook Tests"
echo "================================"
echo ""

# Check for required dependencies
check_dependency() {
    local dep="$1"
    local install_msg="$2"

    if ! command -v "$dep" &> /dev/null; then
        echo -e "${RED}Error: $dep is required but not installed.${NC}"
        echo "$install_msg"
        return 1
    fi
}

# Check dependencies
echo "Checking dependencies..."
check_dependency "jq" "Install jq: https://stedolan.github.io/jq/download/" || exit 1
check_dependency "bats" "Install bats: https://bats-core.readthedocs.io/en/stable/installation.html" || {
    echo -e "${YELLOW}BATS not found. Attempting to use local bats-core...${NC}"

    # Try to use bats from node_modules or download it
    if [[ -f "$PROJECT_ROOT/node_modules/.bin/bats" ]]; then
        BATS_CMD="$PROJECT_ROOT/node_modules/.bin/bats"
    elif [[ -f "$SCRIPT_DIR/bats-core/bin/bats" ]]; then
        BATS_CMD="$SCRIPT_DIR/bats-core/bin/bats"
    else
        echo "Downloading bats-core..."
        cd "$SCRIPT_DIR"
        if command -v git &> /dev/null; then
            git clone --depth 1 https://github.com/bats-core/bats-core.git 2>/dev/null || true
            BATS_CMD="$SCRIPT_DIR/bats-core/bin/bats"
        else
            echo -e "${RED}Cannot install bats automatically. Please install bats manually.${NC}"
            exit 1
        fi
    fi
}

# Use installed bats if available
BATS_CMD="${BATS_CMD:-bats}"

echo -e "${GREEN}Dependencies OK${NC}"
echo ""

# Run tests
echo "Running tests..."
echo ""

# Track overall status
OVERALL_STATUS=0

# Run protect-directories tests
echo "=== protect-directories.sh tests ==="
if $BATS_CMD "$SCRIPT_DIR/protect-directories.bats"; then
    echo -e "${GREEN}protect-directories tests PASSED${NC}"
else
    echo -e "${RED}protect-directories tests FAILED${NC}"
    OVERALL_STATUS=1
fi
echo ""

# Run check-jq tests
echo "=== check-jq.sh tests ==="
if $BATS_CMD "$SCRIPT_DIR/check-jq.bats"; then
    echo -e "${GREEN}check-jq tests PASSED${NC}"
else
    echo -e "${RED}check-jq tests FAILED${NC}"
    OVERALL_STATUS=1
fi
echo ""

# Summary
echo "================================"
if [[ $OVERALL_STATUS -eq 0 ]]; then
    echo -e "${GREEN}All tests PASSED!${NC}"
else
    echo -e "${RED}Some tests FAILED!${NC}"
fi
echo "================================"

exit $OVERALL_STATUS
