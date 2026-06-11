import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

const DEFAULT_PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const DEFAULT_COMMAND = process.platform === "win32"
  ? resolve(DEFAULT_PROJECT_ROOT, ".venv", "Scripts", "ci-defect-assistant.exe")
  : resolve(DEFAULT_PROJECT_ROOT, ".venv", "bin", "ci-defect-assistant");
const ConfigSchema = Type.Object({
  projectRoot: Type.Optional(Type.String()),
  command: Type.Optional(Type.String()),
});

export default defineToolPlugin({
  id: "openclaw-ci-defect-assistant",
  name: "OpenClaw CI Defect Assistant",
  description: "Route Jenkins and Teambition ChatOps requests through ci-defect-assistant.",
  configSchema: ConfigSchema,
  tools: (tool) => [
    tool({
      name: "ci_defect_assistant_chat",
      description: "Handle one DingTalk/OpenClaw Jenkins or Teambition message through the local ci-defect-assistant CLI.",
      parameters: Type.Object({
        user_id: Type.String({ description: "Real DingTalk sender id." }),
        conversation_id: Type.String({ description: "Real DingTalk conversation id. In group chat use Conversation info.chat_id." }),
        text: Type.String({ description: "Original user message text." }),
      }),
      execute: async ({ user_id, conversation_id, text }, config) => {
        return runCli(config.command || DEFAULT_COMMAND, config.projectRoot || DEFAULT_PROJECT_ROOT, [
          "chat",
          "--user-id",
          user_id,
          "--conversation-id",
          conversation_id,
          "--text",
          text,
        ]);
      },
    }),
  ],
});

async function runCli(command: string, projectRoot: string, args: string[]) {
  const { stdout, stderr, code } = await run(command, args, projectRoot);
  if (code !== 0) {
    return { success: false, code: "cli_failed", message: stderr || stdout || `CLI exited with ${code}` };
  }
  try {
    return JSON.parse(stdout);
  } catch {
    return { success: false, code: "invalid_cli_json", message: stdout || "CLI returned empty output" };
  }
}

function run(command: string, args: string[], cwd: string): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      shell: process.platform === "win32",
      env: { ...process.env, CI_DEFECT_ASSISTANT_HOME: cwd },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolve({ stdout, stderr: error.message, code: 1 });
    });
    child.on("close", (code) => {
      resolve({ stdout: stdout.trim(), stderr: stderr.trim(), code });
    });
  });
}
