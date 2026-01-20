import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HOOKS_DIR = join(__dirname, '..', 'hooks');
const HOOK_PATH = join(HOOKS_DIR, 'protect-directories.mjs');

let TEST_DIR;

/**
 * Run the hook with given input and return { status, output }
 */
async function runHook(input) {
  return new Promise((resolve) => {
    const proc = spawn('node', [HOOK_PATH], {
      cwd: TEST_DIR
    });

    let output = '';
    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.stderr.on('data', (data) => { output += data.toString(); });

    proc.on('close', (status) => {
      resolve({ status, output: output.trim() });
    });

    proc.stdin.write(typeof input === 'string' ? input : JSON.stringify(input));
    proc.stdin.end();
  });
}

/**
 * Check if output indicates blocking
 */
function isBlocked(output) {
  return output.includes('"decision"') && output.includes('"block"');
}

/**
 * Create Edit tool input JSON
 */
function makeEditInput(filePath) {
  return JSON.stringify({
    tool_name: 'Edit',
    tool_input: {
      file_path: filePath,
      old_string: 'old',
      new_string: 'new'
    }
  });
}

/**
 * Create Write tool input JSON
 */
function makeWriteInput(filePath) {
  return JSON.stringify({
    tool_name: 'Write',
    tool_input: {
      file_path: filePath,
      content: 'test content'
    }
  });
}

/**
 * Create Bash tool input JSON
 */
function makeBashInput(command) {
  return JSON.stringify({
    tool_name: 'Bash',
    tool_input: { command }
  });
}

/**
 * Create NotebookEdit tool input JSON
 */
function makeNotebookInput(notebookPath) {
  return JSON.stringify({
    tool_name: 'NotebookEdit',
    tool_input: {
      notebook_path: notebookPath,
      cell_number: 0,
      new_source: '# test'
    }
  });
}

/**
 * Create a .block file
 */
function createBlockFile(dir, content = '') {
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, '.block'), content);
}

/**
 * Create a .block.local file
 */
function createLocalBlockFile(dir, content = '') {
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, '.block.local'), content);
}

/**
 * Setup test directory
 */
function setupTestDir() {
  TEST_DIR = join(tmpdir(), `block-test-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(TEST_DIR, { recursive: true });
}

/**
 * Cleanup test directory
 */
function teardownTestDir() {
  if (TEST_DIR && existsSync(TEST_DIR)) {
    rmSync(TEST_DIR, { recursive: true, force: true });
  }
}

// =============================================================================
// Basic Protection Tests
// =============================================================================

describe('Basic Protection Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('allows operations when no .block file exists', async () => {
    mkdirSync(join(TEST_DIR, 'project', 'src'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'src', 'file.txt'));

    const { status, output } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('blocks operations when empty .block file exists', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'project', 'src'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'src', 'file.txt'));

    const { status, output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('BLOCKED') || output.includes('protected'));
  });

  it('blocks operations when .block contains empty JSON object', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{}');
    mkdirSync(join(TEST_DIR, 'project', 'src'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'src', 'file.txt'));

    const { status, output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('blocks nested directory when parent has .block', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'project', 'src', 'deep', 'nested'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'src', 'deep', 'nested', 'file.txt'));

    const { status, output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });
});

// =============================================================================
// Allowed Pattern Tests
// =============================================================================

describe('Allowed Pattern Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('allowed list: allows matching file', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('allowed list: blocks non-matching file', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.js'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('allowed list: allows nested matching file with **', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["src/**/*.ts"]}');
    mkdirSync(join(TEST_DIR, 'project', 'src', 'deep'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'src', 'deep', 'file.ts'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('allowed list: blocks file outside allowed pattern', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["src/**/*.ts"]}');
    mkdirSync(join(TEST_DIR, 'project', 'lib'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'lib', 'file.ts'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('allowed list: allows multiple patterns', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.md", "*.txt", "docs/**/*"]}');
    mkdirSync(join(TEST_DIR, 'project', 'docs', 'guide'), { recursive: true });

    // Test .md file
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'README.md')));
    assert.strictEqual(result.status, 0);

    // Test .txt file
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'notes.txt')));
    assert.strictEqual(result.status, 0);

    // Test docs subdirectory
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'docs', 'guide', 'intro.html')));
    assert.strictEqual(result.status, 0);
  });
});

// =============================================================================
// Blocked Pattern Tests
// =============================================================================

describe('Blocked Pattern Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('blocked list: blocks matching file', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.secret"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'config.secret'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('blocked list: allows non-matching file', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.secret"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'config.json'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('blocked list: blocks nested directory with **', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["node_modules/**/*"]}');
    mkdirSync(join(TEST_DIR, 'project', 'node_modules', 'package', 'dist'), { recursive: true });
    const input = makeEditInput(join(TEST_DIR, 'project', 'node_modules', 'package', 'dist', 'index.js'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('blocked list: multiple patterns all work', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.lock", "*.env", "dist/**"]}');
    mkdirSync(join(TEST_DIR, 'project', 'dist'), { recursive: true });

    // Test .lock file
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'yarn.lock')));
    assert(isBlocked(result.output), 'Expected .lock file to be blocked');

    // Test .env file
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'app.env')));
    assert(isBlocked(result.output), 'Expected .env file to be blocked');

    // Test dist directory
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'dist', 'bundle.js')));
    assert(isBlocked(result.output), 'Expected dist file to be blocked');

    // Non-blocked file should be allowed
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'index.ts')));
    assert.strictEqual(result.status, 0);
  });
});

// =============================================================================
// Guide Message Tests
// =============================================================================

describe('Guide Message Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('shows global guide message when blocked', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"guide": "This project is read-only for Claude."}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('This project is read-only for Claude.'));
  });

  it('shows pattern-specific guide message', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": [{"pattern": "*.env*", "guide": "Environment files are sensitive!"}]}');
    const input = makeEditInput(join(TEST_DIR, 'project', '.env.local'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Environment files are sensitive!'));
  });

  it('pattern-specific guide takes precedence over global guide', async () => {
    createBlockFile(join(TEST_DIR, 'project'), JSON.stringify({
      blocked: [{ pattern: '*.secret', guide: 'Secret files protected' }, '*.other'],
      guide: 'General protection message'
    }));

    // Pattern-specific guide
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'api.secret')));
    assert(isBlocked(result.output), 'Expected operation to be blocked');
    assert(result.output.includes('Secret files protected'));
    assert(!result.output.includes('General protection message'));

    // Falls back to global guide
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'file.other')));
    assert(isBlocked(result.output), 'Expected operation to be blocked');
    assert(result.output.includes('General protection message'));
  });
});

// =============================================================================
// Invalid Configuration Tests
// =============================================================================

describe('Invalid Configuration Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('blocks with error when both allowed and blocked are specified', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt"], "blocked": ["*.js"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('cannot specify both allowed and blocked'));
  });

  it('treats invalid JSON as block all', async () => {
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });
    writeFileSync(join(TEST_DIR, 'project', '.block'), 'this is not json');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });
});

// =============================================================================
// Marker File Protection Tests
// =============================================================================

describe('Marker File Protection Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('blocks modification of .block file', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', '.block'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Cannot modify'));
  });

  it('blocks modification of .block.local file', async () => {
    createLocalBlockFile(join(TEST_DIR, 'project'), '{}');
    const input = makeEditInput(join(TEST_DIR, 'project', '.block.local'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Cannot modify'));
  });

  it('blocks rm command targeting .block', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`rm ${join(TEST_DIR, 'project', '.block')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Cannot modify'));
  });
});

// =============================================================================
// Local Configuration File Tests
// =============================================================================

describe('Local Configuration File Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('local file alone blocks operations', async () => {
    createLocalBlockFile(join(TEST_DIR, 'project'));
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('local file extends main blocked patterns', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.lock"]}');
    createLocalBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.test.ts"]}');

    // Both patterns should be blocked
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'yarn.lock')));
    assert(isBlocked(result.output), 'Expected .lock file to be blocked');

    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'app.test.ts')));
    assert(isBlocked(result.output), 'Expected .test.ts file to be blocked');

    // Non-blocked file should be allowed
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'app.ts')));
    assert.strictEqual(result.status, 0);
  });

  it('local guide overrides main guide', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"guide": "Main guide"}');
    createLocalBlockFile(join(TEST_DIR, 'project'), '{"guide": "Local guide"}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Local guide'));
    assert(!output.includes('Main guide'));
  });

  it('cannot mix allowed and blocked between main and local', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt"]}');
    createLocalBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.secret"]}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('cannot mix allowed and blocked'));
  });

  it('local allowed list overrides main allowed list', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt", "*.md"]}');
    createLocalBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.js"]}');

    // .txt was allowed in main but not in local - should be blocked
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'file.txt')));
    assert(isBlocked(result.output), 'Expected .txt file to be blocked');

    // .js is allowed in local - should be allowed
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'file.js')));
    assert.strictEqual(result.status, 0);
  });
});

// =============================================================================
// Tool Type Tests
// =============================================================================

describe('Tool Type Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('Write tool is blocked in protected directory', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeWriteInput(join(TEST_DIR, 'project', 'new-file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('NotebookEdit tool is blocked in protected directory', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeNotebookInput(join(TEST_DIR, 'project', 'notebook.ipynb'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('unknown tools are allowed', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = JSON.stringify({
      tool_name: 'UnknownTool',
      tool_input: { path: join(TEST_DIR, 'project', 'file.txt') }
    });

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });
});

// =============================================================================
// Bash Command Detection Tests
// =============================================================================

describe('Bash Command Detection Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('detects rm command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`rm ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects rm -rf command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`rm -rf ${join(TEST_DIR, 'project', 'dir')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects touch command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`touch ${join(TEST_DIR, 'project', 'newfile.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects mv command targets', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'other'), { recursive: true });
    const input = makeBashInput(`mv ${join(TEST_DIR, 'other', 'file.txt')} ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects cp command targets', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'other'), { recursive: true });
    const input = makeBashInput(`cp ${join(TEST_DIR, 'other', 'file.txt')} ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects output redirection target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`echo 'hello' > ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects tee command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`echo 'hello' | tee ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects mkdir command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`mkdir -p ${join(TEST_DIR, 'project', 'newdir')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('allows read-only bash commands', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`cat ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('allows ls command in protected directory', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`ls -la ${join(TEST_DIR, 'project')}/`);

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('detects rmdir command target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'project', 'emptydir'), { recursive: true });
    const input = makeBashInput(`rmdir ${join(TEST_DIR, 'project', 'emptydir')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects append redirection target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`echo 'hello' >> ${join(TEST_DIR, 'project', 'file.txt')}`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('detects dd command with of= target', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    const input = makeBashInput(`dd if=/dev/zero of=${join(TEST_DIR, 'project', 'file.bin')} bs=1 count=1`);

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });
});

// =============================================================================
// Wildcard Pattern Tests
// =============================================================================

describe('Wildcard Pattern Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('single asterisk does not match path separator', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["src/*.ts"]}');
    mkdirSync(join(TEST_DIR, 'project', 'src', 'deep'), { recursive: true });

    // Should match direct child
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'index.ts')));
    assert(isBlocked(result.output), 'Expected direct child to be blocked');

    // Should NOT match nested file
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'deep', 'nested.ts')));
    assert.strictEqual(result.status, 0);
  });

  it('double asterisk matches path separator', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["src/**/*.ts"]}');
    mkdirSync(join(TEST_DIR, 'project', 'src', 'deep', 'nested'), { recursive: true });

    // Should match nested file
    const result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'deep', 'nested', 'file.ts')));
    assert(isBlocked(result.output), 'Expected nested file to be blocked');
  });

  it('question mark matches single character', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["file?.txt"]}');

    // Should match file1.txt
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'file1.txt')));
    assert(isBlocked(result.output), 'Expected file1.txt to be blocked');

    // Should NOT match file12.txt
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'file12.txt')));
    assert.strictEqual(result.status, 0);
  });

  it('pattern with dots works correctly', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": ["*.config.ts"]}');

    // Should match
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'app.config.ts')));
    assert(isBlocked(result.output), 'Expected app.config.ts to be blocked');

    // Should NOT match (dots are literal)
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'appXconfigXts')));
    assert.strictEqual(result.status, 0);
  });
});

// =============================================================================
// Edge Cases
// =============================================================================

describe('Edge Cases', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('handles empty input gracefully', async () => {
    const { status } = await runHook('');
    assert.strictEqual(status, 0);
  });

  it('handles malformed JSON input gracefully', async () => {
    const { status } = await runHook('not json');
    assert.strictEqual(status, 0);
  });

  it('handles missing tool_name gracefully', async () => {
    const { status } = await runHook('{}');
    assert.strictEqual(status, 0);
  });

  it('handles paths with spaces', async () => {
    mkdirSync(join(TEST_DIR, 'my project'), { recursive: true });
    createBlockFile(join(TEST_DIR, 'my project'));
    const input = makeEditInput(join(TEST_DIR, 'my project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('closest .block file takes precedence', async () => {
    // Parent directory blocks everything
    createBlockFile(join(TEST_DIR, 'project'));
    // Child directory allows .txt files
    createBlockFile(join(TEST_DIR, 'project', 'src'), '{"allowed": ["*.txt"]}');

    // File in child directory should follow child's rules
    let result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'notes.txt')));
    assert.strictEqual(result.status, 0);

    // Non-allowed file should be blocked
    result = await runHook(makeEditInput(join(TEST_DIR, 'project', 'src', 'code.js')));
    assert(isBlocked(result.output), 'Expected .js file to be blocked');
  });
});

// =============================================================================
// Protection Guarantee Tests
// =============================================================================

describe('Protection Guarantee Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('hook block decision prevents any file modification', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });
    writeFileSync(join(TEST_DIR, 'project', 'existing.txt'), 'original content');

    const input = makeEditInput(join(TEST_DIR, 'project', 'existing.txt'));
    const { output } = await runHook(input);

    assert(isBlocked(output), 'Expected operation to be blocked');
    assert.strictEqual(readFileSync(join(TEST_DIR, 'project', 'existing.txt'), 'utf-8'), 'original content');
  });

  it('blocked Write operation never creates file', async () => {
    createBlockFile(join(TEST_DIR, 'project'));
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });

    const input = makeWriteInput(join(TEST_DIR, 'project', 'new-file.txt'));
    const { output } = await runHook(input);

    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(!existsSync(join(TEST_DIR, 'project', 'new-file.txt')));
  });

  it('allowed operations proceed normally', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": ["*.txt"]}');
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });

    const input = makeEditInput(join(TEST_DIR, 'project', 'allowed.txt'));
    const { status } = await runHook(input);

    assert.strictEqual(status, 0);
  });
});

// =============================================================================
// Mode Condition Coverage Tests
// =============================================================================

describe('Mode Condition Coverage Tests', () => {
  beforeEach(() => setupTestDir());
  afterEach(() => teardownTestDir());

  it('empty allowed array treated as block all', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"allowed": []}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
  });

  it('empty blocked array allows all', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"blocked": []}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('both configs empty uses local guide', async () => {
    createBlockFile(join(TEST_DIR, 'project'), '{"guide": "Main guide message"}');
    createLocalBlockFile(join(TEST_DIR, 'project'), '{"guide": "Local guide message"}');
    const input = makeEditInput(join(TEST_DIR, 'project', 'file.txt'));

    const { output } = await runHook(input);
    assert(isBlocked(output), 'Expected operation to be blocked');
    assert(output.includes('Local guide message'));
    assert(!output.includes('Main guide message'));
  });

  it('allows creating new .block file', async () => {
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });
    const input = makeWriteInput(join(TEST_DIR, 'project', '.block'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });

  it('allows creating new .block.local file', async () => {
    mkdirSync(join(TEST_DIR, 'project'), { recursive: true });
    const input = makeWriteInput(join(TEST_DIR, 'project', '.block.local'));

    const { status } = await runHook(input);
    assert.strictEqual(status, 0);
  });
});
