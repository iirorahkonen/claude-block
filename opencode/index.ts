/**
 * Block plugin for OpenCode
 *
 * Provides file and directory protection using .block configuration files.
 * Intercepts file modification tools (edit, write, bash, patch) and blocks
 * them based on protection rules defined in .block files.
 *
 * This is the OpenCode equivalent of the Claude Code PreToolUse hook.
 */
import type { Plugin } from "@opencode-ai/plugin";
import { resolve } from "path";

/** Tools that modify files and should be checked against .block rules. */
const PROTECTED_TOOLS = new Set(["edit", "write", "bash", "patch"]);

/**
 * Maps OpenCode tool names to the names expected by protect_directories.py.
 * The Python script was originally written for Claude Code's tool naming.
 */
const TOOL_NAME_MAP: Record<string, string> = {
  edit: "Edit",
  write: "Write",
  bash: "Bash",
  patch: "Write",
};

/**
 * Build the JSON input that protect_directories.py expects on stdin.
 *
 * Claude Code hook input format:
 *   { "tool_name": "Edit", "tool_input": { "file_path": "..." } }
 *   { "tool_name": "Bash", "tool_input": { "command": "..." } }
 *
 * OpenCode uses camelCase args: filePath for edit/write/patch, command for bash.
 */
function buildHookInput(
  tool: string,
  args: Record<string, unknown>,
): string | null {
  const toolName = TOOL_NAME_MAP[tool];
  if (!toolName) return null;

  const toolInput: Record<string, unknown> = {};

  if (tool === "bash") {
    if (!args.command) return null;
    toolInput.command = args.command;
  } else {
    // edit, write, patch — OpenCode provides the path as "filePath"
    if (!args.filePath) return null;
    toolInput.file_path = args.filePath;
  }

  return JSON.stringify({ tool_name: toolName, tool_input: toolInput });
}

/**
 * Locate protect_directories.py relative to this plugin file.
 *
 * NOTE: import.meta.dir is a Bun-specific API. OpenCode runs plugins via Bun,
 * so this is safe. Packages installed via npm are cached under
 * ~/.cache/opencode/node_modules/.
 *
 * When installed via npm the layout is:
 *   node_modules/opencode-block/protect_directories.py  (copied by prepack)
 *   node_modules/opencode-block/index.ts
 *
 * When used from the repo directly:
 *   opencode/index.ts
 *   hooks/protect_directories.py
 */
function findScript(): string {
  const pluginDir = import.meta.dir;
  // npm-installed: protect_directories.py is copied alongside index.ts
  const colocated = resolve(pluginDir, "protect_directories.py");
  try {
    const fs = require("fs");
    if (fs.existsSync(colocated)) return colocated;
  } catch {
    // Fall through to repo layout
  }
  // Repo layout: ../hooks/protect_directories.py
  return resolve(pluginDir, "..", "hooks", "protect_directories.py");
}

export const BlockPlugin: Plugin = async ({ $ }) => {
  const scriptPath = findScript();

  return {
    "tool.execute.before": async (input, output) => {
      if (!PROTECTED_TOOLS.has(input.tool)) return;

      const hookInput = buildHookInput(
        input.tool,
        output.args as Record<string, unknown>,
      );
      if (!hookInput) return;

      try {
        const result =
          await $`echo ${hookInput} | python3 ${scriptPath}`.quiet();
        const stdout = result.stdout.toString().trim();
        if (!stdout) return;

        const decision = JSON.parse(stdout);
        if (decision.decision === "block") {
          throw new Error(decision.reason);
        }
      } catch (err: unknown) {
        if (err instanceof SyntaxError) {
          // Python output wasn't JSON — not a block, ignore
          return;
        }
        // Block errors from our own throw above — re-throw
        if (err instanceof Error && err.message) {
          const msg = err.message;
          // Infrastructure failures (python3 not found, spawn errors) should
          // not prevent the operation — log a warning and let it proceed.
          if (
            (err as NodeJS.ErrnoException).code === "ENOENT" ||
            msg.includes("not found") ||
            msg.includes("No such file") ||
            msg.includes("python3")
          ) {
            console.warn(`[block] Protection check skipped: ${msg}`);
            return;
          }
        }
        // Re-throw actual block errors and other unexpected failures
        throw err;
      }
    },
  };
};
