#!/bin/bash
# Claude Code Directory Protection Hook
# Blocks file modifications when .claude-block or .claude-block.local exists in target directory or parent
#
# Configuration files:
#   .claude-block       - Main configuration file (committed to git)
#   .claude-block.local - Local configuration file (not committed, add to .gitignore)
#
# When both files exist in the same directory, they are merged:
#   - blocked patterns: combined (union - more restrictive)
#   - allowed patterns: local overrides main
#   - guide messages: local takes precedence
#   - Mixing allowed/blocked modes between files is an error
#
# .claude-block file format (JSON):
#   Empty file or {} = block everything
#   { "allowed": ["pattern1", "pattern2"] } = only allow matching paths, block everything else
#   { "blocked": ["pattern1", "pattern2"] } = only block matching paths, allow everything else
#   { "guide": "message" } = common guide shown when blocked (fallback for patterns without specific guide)
#   Both allowed and blocked = error (invalid configuration)
#
# Patterns can be strings or objects with per-pattern guides:
#   "pattern" = simple pattern (uses common guide as fallback)
#   { "pattern": "...", "guide": "..." } = pattern with specific guide
#
# Examples:
#   { "blocked": ["*.secret", { "pattern": "config/**", "guide": "Config files protected." }] }
#   { "allowed": ["docs/**", { "pattern": "src/gen/**", "guide": "Generated files." }], "guide": "Fallback" }
#
# Guide priority: pattern-specific guide > common guide > default message
#
# Patterns support wildcards:
#   * = any characters except path separator
#   ** = any characters including path separator (recursive)
#   ? = single character

MARKER_FILE_NAME=".claude-block"
LOCAL_MARKER_FILE_NAME=".claude-block.local"

# Check if jq is available - FAIL CLOSED if missing
if ! command -v jq &> /dev/null; then
    echo "BLOCKED: jq is required for directory protection hook but is not installed." >&2
    echo "Install jq to enable file operations, or remove .claude-block files to disable protection." >&2
    exit 2
fi

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Parse input JSON
TOOL_NAME=$(echo "$HOOK_INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ -z "$TOOL_NAME" ]]; then
    exit 0  # Allow on parse error
fi

# Convert wildcard pattern to regex
convert_wildcard_to_regex() {
    local pattern="$1"

    # Normalize path separators
    pattern="${pattern//\\//}"

    # Process character by character to handle escaping properly
    local result=""
    local i=0
    local len=${#pattern}

    while [[ $i -lt $len ]]; do
        local char="${pattern:$i:1}"
        local next="${pattern:$((i+1)):1}"

        case "$char" in
            '*')
                if [[ "$next" == '*' ]]; then
                    # ** = match anything including /
                    result+=".*"
                    ((i++))
                else
                    # * = match anything except /
                    result+="[^/]*"
                fi
                ;;
            '?')
                # ? = match single character
                result+="."
                ;;
            '.'|'^'|'$'|'['|']'|'('|')'|'{'|'}'|'+'|'|'|'\\')
                # Escape regex special characters
                result+="\\${char}"
                ;;
            *)
                result+="$char"
                ;;
        esac
        ((i++))
    done

    echo "^${result}$"
}

# Test if path matches a pattern
test_path_matches_pattern() {
    local path="$1"
    local pattern="$2"
    local base_path="$3"

    # Normalize paths
    path="${path//\\//}"
    base_path="${base_path//\\//}"
    base_path="${base_path%/}"  # Remove trailing slash

    # Make path relative to base path (case-insensitive comparison for Windows compatibility)
    # Use tr for POSIX compatibility (macOS ships with Bash 3.2 which doesn't support ${var,,})
    local lower_path
    local lower_base
    lower_path=$(echo "$path" | tr '[:upper:]' '[:lower:]')
    lower_base=$(echo "$base_path" | tr '[:upper:]' '[:lower:]')

    if [[ "$lower_path" == "$lower_base"* ]]; then
        local relative_path="${path:${#base_path}}"
        relative_path="${relative_path#/}"  # Remove leading slash
    else
        relative_path="$path"
    fi

    local regex
    regex=$(convert_wildcard_to_regex "$pattern")

    if [[ "$relative_path" =~ $regex ]]; then
        return 0  # Match
    else
        return 1  # No match
    fi
}

# Get lock file configuration
get_lock_file_config() {
    local marker_path="$1"

    # Initialize config as JSON
    local config='{"allowed":[],"blocked":[],"guide":"","is_empty":true,"has_error":false,"error_message":""}'

    if [[ ! -f "$marker_path" ]]; then
        echo "$config"
        return
    fi

    local content
    content=$(cat "$marker_path" 2>/dev/null)

    # Empty file = block everything
    if [[ -z "$content" || "$content" =~ ^[[:space:]]*$ ]]; then
        echo "$config"
        return
    fi

    # Try to parse JSON
    if ! echo "$content" | jq empty 2>/dev/null; then
        # Invalid JSON, treat as empty (block everything)
        echo "$config"
        return
    fi

    # Check for both allowed and blocked (error)
    local has_allowed has_blocked
    has_allowed=$(echo "$content" | jq 'has("allowed")' 2>/dev/null)
    has_blocked=$(echo "$content" | jq 'has("blocked")' 2>/dev/null)

    if [[ "$has_allowed" == "true" && "$has_blocked" == "true" ]]; then
        config=$(echo "$config" | jq '.has_error=true | .error_message="Invalid .claude-block: cannot specify both allowed and blocked lists"')
        echo "$config"
        return
    fi

    # Extract guide
    local guide
    guide=$(echo "$content" | jq -r '.guide // ""' 2>/dev/null)
    config=$(echo "$config" | jq --arg g "$guide" '.guide=$g')

    # Extract allowed list
    if [[ "$has_allowed" == "true" ]]; then
        local allowed
        allowed=$(echo "$content" | jq '.allowed' 2>/dev/null)
        config=$(echo "$config" | jq --argjson a "$allowed" '.allowed=$a | .is_empty=false')
    fi

    # Extract blocked list
    if [[ "$has_blocked" == "true" ]]; then
        local blocked
        blocked=$(echo "$content" | jq '.blocked' 2>/dev/null)
        config=$(echo "$config" | jq --argjson b "$blocked" '.blocked=$b | .is_empty=false')
    fi

    echo "$config"
}

# Merge two configs (main and local)
# Local file extends/overrides main file
# - If either has error: merged has error
# - If either is empty (block all): merged is empty (block all)
# - If both have blocked: combine arrays (union - more restrictive)
# - If both have allowed: local overrides main
# - If one has allowed, other has blocked: error
# - Guide: local takes precedence, falls back to main
merge_configs() {
    local main_config="$1"
    local local_config="$2"

    # If no local config, return main as-is
    if [[ -z "$local_config" || "$local_config" == "null" ]]; then
        echo "$main_config"
        return
    fi

    # Check for errors in either config
    local main_error local_error
    main_error=$(echo "$main_config" | jq -r '.has_error')
    local_error=$(echo "$local_config" | jq -r '.has_error')

    if [[ "$main_error" == "true" ]]; then
        echo "$main_config"
        return
    fi
    if [[ "$local_error" == "true" ]]; then
        echo "$local_config"
        return
    fi

    # Check if either is empty (block all) - most restrictive wins
    local main_empty local_empty
    main_empty=$(echo "$main_config" | jq -r '.is_empty')
    local_empty=$(echo "$local_config" | jq -r '.is_empty')

    if [[ "$main_empty" == "true" || "$local_empty" == "true" ]]; then
        # Return empty config (block all), but prefer local guide if available
        local local_guide main_guide effective_guide
        local_guide=$(echo "$local_config" | jq -r '.guide // ""')
        main_guide=$(echo "$main_config" | jq -r '.guide // ""')
        if [[ -n "$local_guide" ]]; then
            effective_guide="$local_guide"
        else
            effective_guide="$main_guide"
        fi
        jq -n --arg guide "$effective_guide" \
            '{"allowed":[],"blocked":[],"guide":$guide,"is_empty":true,"has_error":false,"error_message":""}'
        return
    fi

    # Check for mode compatibility
    local main_has_allowed main_has_blocked local_has_allowed local_has_blocked
    main_has_allowed=$(echo "$main_config" | jq '.allowed | length > 0')
    main_has_blocked=$(echo "$main_config" | jq '.blocked | length > 0')
    local_has_allowed=$(echo "$local_config" | jq '.allowed | length > 0')
    local_has_blocked=$(echo "$local_config" | jq '.blocked | length > 0')

    # Mixed modes = error
    if [[ "$main_has_allowed" == "true" && "$local_has_blocked" == "true" ]] || \
       [[ "$main_has_blocked" == "true" && "$local_has_allowed" == "true" ]]; then
        echo '{"allowed":[],"blocked":[],"guide":"","is_empty":false,"has_error":true,"error_message":"Invalid configuration: .claude-block and .claude-block.local cannot mix allowed and blocked modes"}'
        return
    fi

    # Determine guide (local takes precedence)
    local merged_guide
    local local_guide main_guide
    local_guide=$(echo "$local_config" | jq -r '.guide // ""')
    main_guide=$(echo "$main_config" | jq -r '.guide // ""')
    if [[ -n "$local_guide" ]]; then
        merged_guide="$local_guide"
    else
        merged_guide="$main_guide"
    fi

    # Merge based on mode
    if [[ "$main_has_blocked" == "true" || "$local_has_blocked" == "true" ]]; then
        # Blocked mode: combine arrays (union)
        local main_blocked local_blocked merged_blocked
        main_blocked=$(echo "$main_config" | jq '.blocked')
        local_blocked=$(echo "$local_config" | jq '.blocked')
        merged_blocked=$(jq -n --argjson a "$main_blocked" --argjson b "$local_blocked" '$a + $b | unique')

        jq -n \
            --argjson blocked "$merged_blocked" \
            --arg guide "$merged_guide" \
            '{"allowed":[],"blocked":$blocked,"guide":$guide,"is_empty":false,"has_error":false,"error_message":""}'
    elif [[ "$main_has_allowed" == "true" || "$local_has_allowed" == "true" ]]; then
        # Allowed mode: local overrides main (if local has allowed), otherwise use main
        local merged_allowed
        if [[ "$local_has_allowed" == "true" ]]; then
            merged_allowed=$(echo "$local_config" | jq '.allowed')
        else
            merged_allowed=$(echo "$main_config" | jq '.allowed')
        fi

        jq -n \
            --argjson allowed "$merged_allowed" \
            --arg guide "$merged_guide" \
            '{"allowed":$allowed,"blocked":[],"guide":$guide,"is_empty":false,"has_error":false,"error_message":""}'
    else
        # Both configs have no patterns, return block all with merged guide
        jq -n --arg guide "$merged_guide" \
            '{"allowed":[],"blocked":[],"guide":$guide,"is_empty":true,"has_error":false,"error_message":""}'
    fi
}

# Get full/absolute path
get_full_path() {
    local path="$1"

    # If already absolute, normalize it
    if [[ "$path" == /* ]] || [[ "$path" =~ ^[A-Za-z]: ]]; then
        # For Windows paths or Unix absolute paths
        echo "$path"
    else
        # Make relative path absolute
        echo "$(pwd)/$path"
    fi
}

# Test if directory is protected, returns protection info JSON or empty
test_directory_protected() {
    local file_path="$1"

    [[ -z "$file_path" ]] && return 1

    # Get absolute path
    file_path=$(get_full_path "$file_path")

    # Normalize path separators for cross-platform
    file_path="${file_path//\\//}"

    # Get parent directory of the file
    local directory
    directory=$(dirname "$file_path")

    [[ -z "$directory" ]] && return 1

    # Walk up directory tree checking for marker files
    while [[ -n "$directory" ]]; do
        local marker_path="${directory}/${MARKER_FILE_NAME}"
        local local_marker_path="${directory}/${LOCAL_MARKER_FILE_NAME}"
        local has_main=false
        local has_local=false

        [[ -f "$marker_path" ]] && has_main=true
        [[ -f "$local_marker_path" ]] && has_local=true

        if [[ "$has_main" == "true" || "$has_local" == "true" ]]; then
            local main_config local_config merged_config
            local effective_marker_path

            # Get configs from both files
            if [[ "$has_main" == "true" ]]; then
                main_config=$(get_lock_file_config "$marker_path")
                effective_marker_path="$marker_path"
            else
                main_config='{"allowed":[],"blocked":[],"guide":"","is_empty":true,"has_error":false,"error_message":""}'
            fi

            if [[ "$has_local" == "true" ]]; then
                local_config=$(get_lock_file_config "$local_marker_path")
                # If we have local but no main, use local as the effective marker
                [[ "$has_main" != "true" ]] && effective_marker_path="$local_marker_path"
                # If we have both, mention both in marker path
                [[ "$has_main" == "true" ]] && effective_marker_path="$marker_path (+ .local)"
            else
                local_config=""
            fi

            # Merge configs
            merged_config=$(merge_configs "$main_config" "$local_config")

            # Return protection info as JSON
            jq -n \
                --arg target "$file_path" \
                --arg marker "$effective_marker_path" \
                --arg dir "$directory" \
                --argjson config "$merged_config" \
                '{target_file: $target, marker_path: $marker, marker_directory: $dir, config: $config}'
            return 0
        fi

        # Move to parent directory
        local parent
        parent=$(dirname "$directory")

        # Check if we've reached root
        if [[ "$parent" == "$directory" ]]; then
            break
        fi
        directory="$parent"
    done

    return 1  # No protection found
}

# Extract target paths from bash commands
get_bash_target_paths() {
    local command="$1"
    local paths=()

    [[ -z "$command" ]] && echo "" && return

    # Patterns for file-modifying commands
    # rm command
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\brm\s+(-[rRfiv]+\s+)*([^ |;&]+)' | sed -E 's/\brm\s+(-[rRfiv]+\s+)*//g' | tr -d "'" | tr -d '"')

    # mv command (both source and dest)
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\bmv\s+(-[fiv]+\s+)*[^ |;&]+\s+[^ |;&]+' | sed -E 's/\bmv\s+(-[fiv]+\s+)*//g' | tr ' ' '\n' | tr -d "'" | tr -d '"')

    # cp command (both source and dest)
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\bcp\s+(-[rRfiv]+\s+)*[^ |;&]+\s+[^ |;&]+' | sed -E 's/\bcp\s+(-[rRfiv]+\s+)*//g' | tr ' ' '\n' | tr -d "'" | tr -d '"')

    # touch command
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\btouch\s+[^ |;&]+' | sed 's/\btouch\s*//g' | tr -d "'" | tr -d '"')

    # mkdir command
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\bmkdir\s+(-p\s+)?[^ |;&]+' | sed -E 's/\bmkdir\s+(-p\s+)?//g' | tr -d "'" | tr -d '"')

    # rmdir command
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\brmdir\s+[^ |;&]+' | sed 's/\brmdir\s*//g' | tr -d "'" | tr -d '"')

    # Output redirection > or >>
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '>\s*[^ |;&>]+' | sed 's/>\s*//g' | tr -d "'" | tr -d '"')

    # tee command
    while read -r match; do
        [[ -n "$match" && ! "$match" =~ ^- ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\btee\s+(-a\s+)?[^ |;&]+' | sed -E 's/\btee\s+(-a\s+)?//g' | tr -d "'" | tr -d '"')

    # dd command with of=
    while read -r match; do
        [[ -n "$match" ]] && paths+=("$match")
    done < <(echo "$command" | grep -oE '\bof=[^ |;&]+' | sed 's/of=//g' | tr -d "'" | tr -d '"')

    # Return unique paths
    printf '%s\n' "${paths[@]}" | sort -u | tr '\n' ' '
}

# Check if path is a marker file (main or local)
test_is_marker_file() {
    local file_path="$1"

    [[ -z "$file_path" ]] && return 1

    local filename
    filename=$(basename "$file_path")

    [[ "$filename" == "$MARKER_FILE_NAME" || "$filename" == "$LOCAL_MARKER_FILE_NAME" ]]
}

# Block marker file removal
block_marker_removal() {
    local target_file="$1"
    local filename
    filename=$(basename "$target_file")

    cat >&2 << EOF
BLOCKED: Cannot modify $filename

Target file: $target_file

The $filename file is protected and cannot be modified or removed by Claude.
This is a safety mechanism to ensure directory protection remains in effect.

To remove protection, manually delete the file using your file manager or terminal.
EOF
    exit 2
}

# Block config error
block_config_error() {
    local marker_path="$1"
    local error_message="$2"

    cat >&2 << EOF
BLOCKED: Invalid $MARKER_FILE_NAME configuration

Marker file: $marker_path
Error: $error_message

Please fix the configuration file. Valid formats:
  - Empty file or {} = block everything
  - { "allowed": ["pattern"] } = only allow matching paths
  - { "blocked": ["pattern"] } = only block matching paths
EOF
    exit 2
}

# Block with message
block_with_message() {
    local target_file="$1"
    local marker_path="$2"
    local reason="$3"
    local guide="$4"

    # If guide is provided, just show the guide text
    if [[ -n "$guide" ]]; then
        echo "$guide" >&2
        exit 2
    fi

    # Otherwise show short default message
    echo "BLOCKED by .claude-block: $marker_path" >&2
    exit 2
}

# Test if operation should be blocked
test_should_block() {
    local file_path="$1"
    local protection_info="$2"

    local config marker_dir guide
    config=$(echo "$protection_info" | jq '.config')
    marker_dir=$(echo "$protection_info" | jq -r '.marker_directory')
    guide=$(echo "$config" | jq -r '.guide // ""')

    # Config error = always block
    local has_error
    has_error=$(echo "$config" | jq -r '.has_error')
    if [[ "$has_error" == "true" ]]; then
        local error_msg
        error_msg=$(echo "$config" | jq -r '.error_message')
        echo '{"should_block":true,"reason":"'"$error_msg"'","is_config_error":true,"guide":""}'
        return
    fi

    # Empty config = block everything
    local is_empty
    is_empty=$(echo "$config" | jq -r '.is_empty')
    if [[ "$is_empty" == "true" ]]; then
        jq -n --arg g "$guide" '{"should_block":true,"reason":"This directory tree is protected from Claude edits (full protection).","is_config_error":false,"guide":$g}'
        return
    fi

    # Allowed list = block unless path matches
    local allowed_count
    allowed_count=$(echo "$config" | jq '.allowed | length')
    if [[ "$allowed_count" -gt 0 ]]; then
        local i=0
        while [[ $i -lt $allowed_count ]]; do
            local entry pattern entry_guide
            entry=$(echo "$config" | jq ".allowed[$i]")

            # Handle string or object pattern
            if [[ $(echo "$entry" | jq 'type') == '"string"' ]]; then
                pattern=$(echo "$entry" | jq -r '.')
                entry_guide=""
            else
                pattern=$(echo "$entry" | jq -r '.pattern // ""')
                entry_guide=$(echo "$entry" | jq -r '.guide // ""')
            fi

            if test_path_matches_pattern "$file_path" "$pattern" "$marker_dir"; then
                echo '{"should_block":false,"reason":"","is_config_error":false,"guide":""}'
                return
            fi
            ((i++))
        done

        jq -n --arg g "$guide" '{"should_block":true,"reason":"Path is not in the allowed list.","is_config_error":false,"guide":$g}'
        return
    fi

    # Blocked list = allow unless path matches
    local blocked_count
    blocked_count=$(echo "$config" | jq '.blocked | length')
    if [[ "$blocked_count" -gt 0 ]]; then
        local i=0
        while [[ $i -lt $blocked_count ]]; do
            local entry pattern entry_guide
            entry=$(echo "$config" | jq ".blocked[$i]")

            # Handle string or object pattern
            if [[ $(echo "$entry" | jq 'type') == '"string"' ]]; then
                pattern=$(echo "$entry" | jq -r '.')
                entry_guide=""
            else
                pattern=$(echo "$entry" | jq -r '.pattern // ""')
                entry_guide=$(echo "$entry" | jq -r '.guide // ""')
            fi

            if test_path_matches_pattern "$file_path" "$pattern" "$marker_dir"; then
                # Use pattern-specific guide, fall back to common guide
                local effective_guide="$entry_guide"
                [[ -z "$effective_guide" ]] && effective_guide="$guide"

                jq -n --arg g "$effective_guide" --arg p "$pattern" \
                    '{"should_block":true,"reason":("Path matches blocked pattern: " + $p),"is_config_error":false,"guide":$g}'
                return
            fi
            ((i++))
        done

        echo '{"should_block":false,"reason":"","is_config_error":false,"guide":""}'
        return
    fi

    # Default = block
    jq -n --arg g "$guide" '{"should_block":true,"reason":"This directory tree is protected from Claude edits.","is_config_error":false,"guide":$g}'
}

# Main logic - determine paths to check based on tool type
paths_to_check=()

case "$TOOL_NAME" in
    "Edit")
        path=$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // empty')
        [[ -n "$path" ]] && paths_to_check+=("$path")
        ;;
    "Write")
        path=$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // empty')
        [[ -n "$path" ]] && paths_to_check+=("$path")
        ;;
    "NotebookEdit")
        path=$(echo "$HOOK_INPUT" | jq -r '.tool_input.notebook_path // empty')
        [[ -n "$path" ]] && paths_to_check+=("$path")
        ;;
    "Bash")
        command=$(echo "$HOOK_INPUT" | jq -r '.tool_input.command // empty')
        if [[ -n "$command" ]]; then
            while read -r bash_path; do
                [[ -n "$bash_path" ]] && paths_to_check+=("$bash_path")
            done < <(get_bash_target_paths "$command" | tr ' ' '\n')
        fi
        ;;
    *)
        exit 0  # Allow unknown tools
        ;;
esac

# Check each path for protection
for path in "${paths_to_check[@]}"; do
    [[ -z "$path" ]] && continue

    # First check if trying to modify/delete an existing marker file
    if test_is_marker_file "$path"; then
        full_path=$(get_full_path "$path")
        # Only block if the marker file already exists (allow creation, block modification/deletion)
        if [[ -f "$full_path" ]]; then
            block_marker_removal "$full_path"
        fi
    fi

    # Then check if the target is in a protected directory
    protection_info=$(test_directory_protected "$path")
    if [[ -n "$protection_info" ]]; then
        target_file=$(echo "$protection_info" | jq -r '.target_file')
        marker_path=$(echo "$protection_info" | jq -r '.marker_path')

        block_result=$(test_should_block "$target_file" "$protection_info")

        should_block=$(echo "$block_result" | jq -r '.should_block')
        is_config_error=$(echo "$block_result" | jq -r '.is_config_error')
        reason=$(echo "$block_result" | jq -r '.reason')
        result_guide=$(echo "$block_result" | jq -r '.guide')

        if [[ "$is_config_error" == "true" ]]; then
            block_config_error "$marker_path" "$reason"
        elif [[ "$should_block" == "true" ]]; then
            block_with_message "$target_file" "$marker_path" "$reason" "$result_guide"
        fi
    fi
done

# No protection found, allow the operation
exit 0
