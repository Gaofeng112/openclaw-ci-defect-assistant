import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const command = process.platform === "win32"
  ? resolve(projectRoot, ".venv", "Scripts", "ci-defect-assistant.exe")
  : resolve(projectRoot, ".venv", "bin", "ci-defect-assistant");

const server = new McpServer({
  name: "hermes-mcp-ci-defect-assistant",
  version: "0.1.0",
});

server.registerTool(
  "ci_defect_assistant_chat",
  {
    title: "CI Defect Assistant Chat",
    description: "Executor for Jenkins, CI, Teambition, bug, defect, issue, 缺陷, 创建缺陷, 提 bug, 确认, 状态, and 链接 requests. Pass the current user text verbatim.",
    inputSchema: {
      user_id: z.string().describe("Real DingTalk sender id."),
      conversation_id: z.string().describe("Real DingTalk conversation id. In group chat use Conversation info.chat_id."),
      text: z.string().describe("Current user message verbatim."),
      fields_json: z.string().optional().describe("Optional JSON object string for Teambition defect fields."),
    },
  },
  async ({ user_id, conversation_id, text, fields_json }) => {
    const reply = await callCli(user_id, conversation_id, text, fields_json);
    return { content: [{ type: "text", text: reply }] };
  },
);

await server.connect(new StdioServerTransport());

async function callCli(userId: string, conversationId: string, text: string, fieldsJson?: string) {
  const args = ["chat", "--user-id", userId, "--conversation-id", conversationId, "--text", text];
  let fieldsDir: string | undefined;
  if (fieldsJson && fieldsJson.trim() && fieldsJson.trim() !== "{}") {
    fieldsDir = mkdtempSync(join(tmpdir(), "ci-defect-assistant-"));
    const fieldsFile = join(fieldsDir, "fields.json");
    writeFileSync(fieldsFile, fieldsJson, "utf8");
    args.push("--fields-file", fieldsFile);
  }
  try {
    const { stdout, stderr, code } = await run(command, args);
    if (code !== 0) {
      return stderr || stdout || `CLI exited with ${code}`;
    }
    const result = JSON.parse(stdout);
    return typeof result?.reply === "string" ? result.reply : stdout;
  } finally {
    if (fieldsDir) {
      rmSync(fieldsDir, { recursive: true, force: true });
    }
  }
}

function run(args0: string, args: string[]): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolvePromise) => {
    const child = spawn(args0, args, {
      cwd: projectRoot,
      windowsHide: true,
      env: { ...process.env, CI_DEFECT_ASSISTANT_HOME: projectRoot },
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
      resolvePromise({ stdout, stderr: error.message, code: 1 });
    });
    child.on("close", (code) => {
      resolvePromise({ stdout: stdout.trim(), stderr: stderr.trim(), code });
    });
  });
}
