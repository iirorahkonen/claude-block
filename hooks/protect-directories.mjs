#!/usr/bin/env node
/**
 * Claude Code Directory Protection Hook
 * Blocks file modifications when .block or .block.local exists in target directory or parent
 *
 * Configuration files:
 *   .block       - Main configuration file (committed to git)
 *   .block.local - Local configuration file (not committed, add to .gitignore)
 *
 * When both files exist in the same directory, they are merged:
 *   - blocked patterns: combined (union - more restrictive)
 *   - allowed patterns: local overrides main
 *   - guide messages: local takes precedence
 *   - Mixing allowed/blocked modes between files is an error
 *
 * .block file format (JSON):
 *   Empty file or {} = block everything
 *   { "allowed": ["pattern1", "pattern2"] } = only allow matching paths, block everything else
 *   { "blocked": ["pattern1", "pattern2"] } = only block matching paths, allow everything else
 *   { "guide": "message" } = common guide shown when blocked (fallback for patterns without specific guide)
 *   Both allowed and blocked = error (invalid configuration)
 *
 * Patterns can be strings or objects with per-pattern guides:
 *   "pattern" = simple pattern (uses common guide as fallback)
 *   { "pattern": "...", "guide": "..." } = pattern with specific guide
 *
 * Examples:
 *   { "blocked": ["*.secret", { "pattern": "config/**", "guide": "Config files protected." }] }
 *   { "allowed": ["docs/**", { "pattern": "src/gen/**", "guide": "Generated files." }], "guide": "Fallback" }
 *
 * Guide priority: pattern-specific guide > common guide > default message
 *
 * Patterns support wildcards:
 *   * = any characters except path separator
 *   ** = any characters including path separator (recursive)
 *   ? = single character
 */

import { readFileSync, existsSync, statSync } from 'node:fs';
import { dirname, basename, resolve, isAbsolute } from 'node:path';

const MARKER_FILE_NAME = '.block';
const LOCAL_MARKER_FILE_NAME = '.block.local';

/**
 * Normalize path separators (Windows backslashes to forward slashes)
 */
function normalizePath(path) {
  return path.replace(/\\/g, '/');
}

/**
 * Convert wildcard pattern to regex
 */
function convertWildcardToRegex(pattern) {
  pattern = normalizePath(pattern);

  let result = '';
  let i = 0;

  while (i < pattern.length) {
    const char = pattern[i];
    const next = pattern[i + 1];

    if (char === '*') {
      if (next === '*') {
        // ** = match anything including /
        result += '.*';
        i++;
      } else {
        // * = match anything except /
        result += '[^/]*';
      }
    } else if (char === '?') {
      // ? = match single character
      result += '.';
    } else if ('.^$[](){}+|\\'.includes(char)) {
      // Escape regex special characters
      result += '\\' + char;
    } else {
      result += char;
    }
    i++;
  }

  return new RegExp(`^${result}$`);
}

/**
 * Test if path matches a pattern
 */
function testPathMatchesPattern(filePath, pattern, basePath) {
  filePath = normalizePath(filePath);
  basePath = normalizePath(basePath).replace(/\/$/, ''); // Remove trailing slash

  // Make path relative to base path (case-insensitive for Windows compatibility)
  let relativePath;
  const lowerPath = filePath.toLowerCase();
  const lowerBase = basePath.toLowerCase();

  if (lowerPath.startsWith(lowerBase)) {
    relativePath = filePath.slice(basePath.length);
    relativePath = relativePath.replace(/^\//, ''); // Remove leading slash
  } else {
    relativePath = filePath;
  }

  const regex = convertWildcardToRegex(pattern);
  return regex.test(relativePath);
}

/**
 * Get lock file configuration
 */
function getLockFileConfig(markerPath) {
  const defaultConfig = {
    allowed: [],
    blocked: [],
    guide: '',
    is_empty: true,
    has_error: false,
    error_message: ''
  };

  if (!existsSync(markerPath)) {
    return defaultConfig;
  }

  let content;
  try {
    content = readFileSync(markerPath, 'utf-8');
  } catch {
    return defaultConfig;
  }

  // Empty file = block everything
  if (!content || content.trim() === '') {
    return defaultConfig;
  }

  // Try to parse JSON
  let parsed;
  try {
    parsed = JSON.parse(content);
  } catch {
    // Invalid JSON, treat as empty (block everything)
    return defaultConfig;
  }

  const config = { ...defaultConfig };

  // Check for both allowed and blocked (error)
  const hasAllowed = 'allowed' in parsed;
  const hasBlocked = 'blocked' in parsed;

  if (hasAllowed && hasBlocked) {
    config.has_error = true;
    config.error_message = 'Invalid .block: cannot specify both allowed and blocked lists';
    return config;
  }

  // Extract guide
  config.guide = parsed.guide || '';

  // Extract allowed list
  if (hasAllowed) {
    config.allowed = parsed.allowed;
    config.is_empty = false;
  }

  // Extract blocked list
  if (hasBlocked) {
    config.blocked = parsed.blocked;
    config.is_empty = false;
  }

  return config;
}

/**
 * Merge two configs (main and local)
 */
function mergeConfigs(mainConfig, localConfig) {
  // If no local config, return main as-is
  if (!localConfig) {
    return mainConfig;
  }

  // Check for errors in either config
  if (mainConfig.has_error) {
    return mainConfig;
  }
  if (localConfig.has_error) {
    return localConfig;
  }

  // Check if either is empty (block all) - most restrictive wins
  if (mainConfig.is_empty || localConfig.is_empty) {
    // Return empty config (block all), but prefer local guide if available
    const effectiveGuide = localConfig.guide || mainConfig.guide;
    return {
      allowed: [],
      blocked: [],
      guide: effectiveGuide,
      is_empty: true,
      has_error: false,
      error_message: ''
    };
  }

  // Check for mode compatibility
  const mainHasAllowed = mainConfig.allowed.length > 0;
  const mainHasBlocked = mainConfig.blocked.length > 0;
  const localHasAllowed = localConfig.allowed.length > 0;
  const localHasBlocked = localConfig.blocked.length > 0;

  // Mixed modes = error
  if ((mainHasAllowed && localHasBlocked) || (mainHasBlocked && localHasAllowed)) {
    return {
      allowed: [],
      blocked: [],
      guide: '',
      is_empty: false,
      has_error: true,
      error_message: 'Invalid configuration: .block and .block.local cannot mix allowed and blocked modes'
    };
  }

  // Determine guide (local takes precedence)
  const mergedGuide = localConfig.guide || mainConfig.guide;

  // Merge based on mode
  if (mainHasBlocked || localHasBlocked) {
    // Blocked mode: combine arrays (union)
    const mergedBlocked = [...new Set([
      ...mainConfig.blocked.map(b => typeof b === 'string' ? b : JSON.stringify(b)),
      ...localConfig.blocked.map(b => typeof b === 'string' ? b : JSON.stringify(b))
    ])].map(b => {
      try {
        return JSON.parse(b);
      } catch {
        return b;
      }
    });

    return {
      allowed: [],
      blocked: mergedBlocked,
      guide: mergedGuide,
      is_empty: false,
      has_error: false,
      error_message: ''
    };
  } else if (mainHasAllowed || localHasAllowed) {
    // Allowed mode: local overrides main (if local has allowed), otherwise use main
    const mergedAllowed = localHasAllowed ? localConfig.allowed : mainConfig.allowed;

    return {
      allowed: mergedAllowed,
      blocked: [],
      guide: mergedGuide,
      is_empty: false,
      has_error: false,
      error_message: ''
    };
  }

  // Both configs have no patterns, return block all with merged guide
  return {
    allowed: [],
    blocked: [],
    guide: mergedGuide,
    is_empty: true,
    has_error: false,
    error_message: ''
  };
}

/**
 * Get full/absolute path
 */
function getFullPath(path) {
  if (isAbsolute(path) || /^[A-Za-z]:/.test(path)) {
    return path;
  }
  return resolve(process.cwd(), path);
}

/**
 * Check if .block file exists in directory hierarchy
 */
function hasBlockFileInHierarchy(dir) {
  dir = normalizePath(dir);

  while (dir) {
    if (existsSync(`${dir}/.block`) || existsSync(`${dir}/.block.local`)) {
      return true;
    }
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return false;
}

/**
 * Test if directory is protected, returns protection info or null
 */
function testDirectoryProtected(filePath) {
  if (!filePath) return null;

  filePath = normalizePath(getFullPath(filePath));
  let directory = dirname(filePath);

  if (!directory) return null;

  // Walk up directory tree checking for marker files
  while (directory) {
    const markerPath = `${directory}/${MARKER_FILE_NAME}`;
    const localMarkerPath = `${directory}/${LOCAL_MARKER_FILE_NAME}`;
    const hasMain = existsSync(markerPath);
    const hasLocal = existsSync(localMarkerPath);

    if (hasMain || hasLocal) {
      let mainConfig, localConfig;
      let effectiveMarkerPath;

      // Get configs from both files
      if (hasMain) {
        mainConfig = getLockFileConfig(markerPath);
        effectiveMarkerPath = markerPath;
      } else {
        mainConfig = {
          allowed: [],
          blocked: [],
          guide: '',
          is_empty: true,
          has_error: false,
          error_message: ''
        };
      }

      if (hasLocal) {
        localConfig = getLockFileConfig(localMarkerPath);
        if (!hasMain) {
          effectiveMarkerPath = localMarkerPath;
        } else {
          effectiveMarkerPath = `${markerPath} (+ .local)`;
        }
      } else {
        localConfig = null;
      }

      // Merge configs
      const mergedConfig = mergeConfigs(mainConfig, localConfig);

      return {
        target_file: filePath,
        marker_path: effectiveMarkerPath,
        marker_directory: directory,
        config: mergedConfig
      };
    }

    // Move to parent directory
    const parent = dirname(directory);
    if (parent === directory) break;
    directory = parent;
  }

  return null;
}

/**
 * Extract target paths from bash commands
 */
function getBashTargetPaths(command) {
  if (!command) return [];

  const paths = new Set();

  // Helper to clean quotes from paths
  const cleanPath = (p) => p.replace(/['"]/g, '').trim();

  // rm command
  const rmMatches = command.match(/\brm\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)/g) || [];
  for (const match of rmMatches) {
    const path = match.replace(/\brm\s+(?:-[rRfiv]+\s+)*/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // mv command (both source and dest)
  const mvMatches = command.match(/\bmv\s+(?:-[fiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)/g) || [];
  for (const match of mvMatches) {
    const parts = match.replace(/\bmv\s+(?:-[fiv]+\s+)*/, '').split(/\s+/);
    for (const part of parts) {
      if (part && !part.startsWith('-')) paths.add(cleanPath(part));
    }
  }

  // cp command (both source and dest)
  const cpMatches = command.match(/\bcp\s+(?:-[rRfiv]+\s+)*([^\s|;&]+)\s+([^\s|;&]+)/g) || [];
  for (const match of cpMatches) {
    const parts = match.replace(/\bcp\s+(?:-[rRfiv]+\s+)*/, '').split(/\s+/);
    for (const part of parts) {
      if (part && !part.startsWith('-')) paths.add(cleanPath(part));
    }
  }

  // touch command
  const touchMatches = command.match(/\btouch\s+([^\s|;&]+)/g) || [];
  for (const match of touchMatches) {
    const path = match.replace(/\btouch\s*/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // mkdir command
  const mkdirMatches = command.match(/\bmkdir\s+(?:-p\s+)?([^\s|;&]+)/g) || [];
  for (const match of mkdirMatches) {
    const path = match.replace(/\bmkdir\s+(?:-p\s+)?/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // rmdir command
  const rmdirMatches = command.match(/\brmdir\s+([^\s|;&]+)/g) || [];
  for (const match of rmdirMatches) {
    const path = match.replace(/\brmdir\s*/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // Output redirection > or >>
  const redirectMatches = command.match(/>>?\s*([^\s|;&>]+)/g) || [];
  for (const match of redirectMatches) {
    const path = match.replace(/>>?\s*/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // tee command
  const teeMatches = command.match(/\btee\s+(?:-a\s+)?([^\s|;&]+)/g) || [];
  for (const match of teeMatches) {
    const path = match.replace(/\btee\s+(?:-a\s+)?/, '');
    if (path && !path.startsWith('-')) paths.add(cleanPath(path));
  }

  // dd command with of=
  const ddMatches = command.match(/\bof=([^\s|;&]+)/g) || [];
  for (const match of ddMatches) {
    const path = match.replace(/of=/, '');
    if (path) paths.add(cleanPath(path));
  }

  return [...paths];
}

/**
 * Check if path is a marker file
 */
function isMarkerFile(filePath) {
  if (!filePath) return false;
  const filename = basename(filePath);
  return filename === MARKER_FILE_NAME || filename === LOCAL_MARKER_FILE_NAME;
}

/**
 * Output JSON response and exit
 */
function output(response) {
  console.log(JSON.stringify(response));
  process.exit(0);
}

/**
 * Block marker file removal
 */
function blockMarkerRemoval(targetFile) {
  const filename = basename(targetFile);
  const message = `BLOCKED: Cannot modify ${filename}

Target file: ${targetFile}

The ${filename} file is protected and cannot be modified or removed by Claude.
This is a safety mechanism to ensure directory protection remains in effect.

To remove protection, manually delete the file using your file manager or terminal.`;

  output({ decision: 'block', reason: message });
}

/**
 * Block config error
 */
function blockConfigError(markerPath, errorMessage) {
  const message = `BLOCKED: Invalid ${MARKER_FILE_NAME} configuration

Marker file: ${markerPath}
Error: ${errorMessage}

Please fix the configuration file. Valid formats:
  - Empty file or {} = block everything
  - { "allowed": ["pattern"] } = only allow matching paths
  - { "blocked": ["pattern"] } = only block matching paths`;

  output({ decision: 'block', reason: message });
}

/**
 * Block with message
 */
function blockWithMessage(targetFile, markerPath, reason, guide) {
  const message = guide || `BLOCKED by .block: ${markerPath}`;
  output({ decision: 'block', reason: message });
}

/**
 * Test if operation should be blocked
 */
function testShouldBlock(filePath, protectionInfo) {
  const { config, marker_directory: markerDir } = protectionInfo;
  const guide = config.guide || '';

  // Config error = always block
  if (config.has_error) {
    return {
      should_block: true,
      reason: config.error_message,
      is_config_error: true,
      guide: ''
    };
  }

  // Empty config = block everything
  if (config.is_empty) {
    return {
      should_block: true,
      reason: 'This directory tree is protected from Claude edits (full protection).',
      is_config_error: false,
      guide
    };
  }

  // Allowed list = block unless path matches
  if (config.allowed.length > 0) {
    for (const entry of config.allowed) {
      let pattern, entryGuide;

      if (typeof entry === 'string') {
        pattern = entry;
        entryGuide = '';
      } else {
        pattern = entry.pattern || '';
        entryGuide = entry.guide || '';
      }

      if (testPathMatchesPattern(filePath, pattern, markerDir)) {
        return {
          should_block: false,
          reason: '',
          is_config_error: false,
          guide: ''
        };
      }
    }

    return {
      should_block: true,
      reason: 'Path is not in the allowed list.',
      is_config_error: false,
      guide
    };
  }

  // Blocked list = allow unless path matches
  if (config.blocked.length > 0) {
    for (const entry of config.blocked) {
      let pattern, entryGuide;

      if (typeof entry === 'string') {
        pattern = entry;
        entryGuide = '';
      } else {
        pattern = entry.pattern || '';
        entryGuide = entry.guide || '';
      }

      if (testPathMatchesPattern(filePath, pattern, markerDir)) {
        // Use pattern-specific guide, fall back to common guide
        const effectiveGuide = entryGuide || guide;

        return {
          should_block: true,
          reason: `Path matches blocked pattern: ${pattern}`,
          is_config_error: false,
          guide: effectiveGuide
        };
      }
    }

    return {
      should_block: false,
      reason: '',
      is_config_error: false,
      guide: ''
    };
  }

  // Default = block
  return {
    should_block: true,
    reason: 'This directory tree is protected from Claude edits.',
    is_config_error: false,
    guide
  };
}

/**
 * Extract file path from JSON without full parsing (for quick check)
 */
function extractPathWithoutParsing(input) {
  const match = input.match(/"(?:file_path|notebook_path)"\s*:\s*"([^"]*)"/);
  return match ? match[1] : null;
}

/**
 * Main function
 */
async function main() {
  // Read hook input from stdin
  let hookInput = '';
  for await (const chunk of process.stdin) {
    hookInput += chunk;
  }

  // Quick path extraction to check if .block exists
  const quickPath = extractPathWithoutParsing(hookInput);

  if (quickPath) {
    const quickDir = dirname(quickPath);
    const fullDir = isAbsolute(quickPath) || /^[A-Za-z]:/.test(quickPath)
      ? quickDir
      : resolve(process.cwd(), quickDir);

    // If no .block file in hierarchy, allow without full parsing
    if (!hasBlockFileInHierarchy(fullDir)) {
      process.exit(0); // No protection needed
    }
  }

  // Parse input JSON
  let input;
  try {
    input = JSON.parse(hookInput);
  } catch {
    process.exit(0); // Allow on parse error
  }

  const toolName = input.tool_name;
  if (!toolName) {
    process.exit(0); // Allow if no tool name
  }

  // Determine paths to check based on tool type
  const pathsToCheck = [];

  switch (toolName) {
    case 'Edit':
    case 'Write':
      if (input.tool_input?.file_path) {
        pathsToCheck.push(input.tool_input.file_path);
      }
      break;
    case 'NotebookEdit':
      if (input.tool_input?.notebook_path) {
        pathsToCheck.push(input.tool_input.notebook_path);
      }
      break;
    case 'Bash':
      if (input.tool_input?.command) {
        pathsToCheck.push(...getBashTargetPaths(input.tool_input.command));
      }
      break;
    default:
      process.exit(0); // Allow unknown tools
  }

  // Check each path for protection
  for (const path of pathsToCheck) {
    if (!path) continue;

    // First check if trying to modify/delete an existing marker file
    if (isMarkerFile(path)) {
      const fullPath = getFullPath(path);
      // Only block if the marker file already exists (allow creation, block modification/deletion)
      if (existsSync(fullPath)) {
        blockMarkerRemoval(fullPath);
      }
    }

    // Then check if the target is in a protected directory
    const protectionInfo = testDirectoryProtected(path);

    if (protectionInfo) {
      const { target_file: targetFile, marker_path: markerPath } = protectionInfo;
      const blockResult = testShouldBlock(targetFile, protectionInfo);

      if (blockResult.is_config_error) {
        blockConfigError(markerPath, blockResult.reason);
      } else if (blockResult.should_block) {
        blockWithMessage(targetFile, markerPath, blockResult.reason, blockResult.guide);
      }
    }
  }

  // No protection found, allow the operation
  process.exit(0);
}

// Run main
main().catch(() => process.exit(0));
