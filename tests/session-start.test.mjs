import { describe, it } from 'node:test';
import assert from 'node:assert';
import { spawn } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const HOOKS_DIR = join(__dirname, '..', 'hooks');
const HOOK_PATH = join(HOOKS_DIR, 'session-start.mjs');

/**
 * Run the session-start hook
 */
async function runHook() {
  return new Promise((resolve) => {
    const proc = spawn('node', [HOOK_PATH]);

    let output = '';
    proc.stdout.on('data', (data) => { output += data.toString(); });
    proc.stderr.on('data', (data) => { output += data.toString(); });

    proc.on('close', (status) => {
      resolve({ status, output: output.trim() });
    });
  });
}

describe('Session Start Hook Tests', () => {
  it('exits with 0', async () => {
    const { status } = await runHook();
    assert.strictEqual(status, 0);
  });

  it('returns continue decision', async () => {
    const { output } = await runHook();
    const parsed = JSON.parse(output);
    assert.strictEqual(parsed.decision, 'continue');
  });

  it('produces valid JSON output', async () => {
    const { output } = await runHook();
    assert.doesNotThrow(() => JSON.parse(output));
  });
});
