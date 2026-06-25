import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
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
const TOOL_DESCRIPTION = `MUST be called for any DingTalk/OpenClaw Jenkins, CI, pipeline, build, test, Teambition, bug, defect, issue, 缺陷, 创建缺陷, 提 bug, 确认, 状态, or 链接 request. This is the executor. Do not use skill_workshop, shell commands, direct Jenkins/Teambition calls, or write your own reply. After the tool returns, send exactly the returned reply text. Do not summarize it.

The text argument is security-critical: pass the current user message verbatim. Never replace a full new request with "确认" because of earlier chat context. Only pass confirmation text when the current user message itself is confirmation-only, for example "确认 123456".

For confirmation, query, Jenkins, or non-defect requests, omit fields_json or pass "{}". For Teambition defect creation, understand the current user's natural Chinese message and fill fields_json with a JSON object string. Use semantic understanding, not keyword-only copying.

Business rules for fields:
- 标题：优先写成【模块或数据库】现象；【】里是出问题的模块或数据库。例：企业版正服中国上市检索生僻字会报错 -> 【中国上市】检索生僻字会报错。
- 描述：保留用户原始问题含义；信息少时用原话，不要编造复现步骤。
- 环境：正服/线上/生产 -> 正服；测服/测试服 -> 测服；预发布 -> 预发布。
- 缺陷分类：正服 -> 企业版线上缺陷；测服/预发布 -> 企业版迭代缺陷。
- 负责人：用户说“给 A 创建”就是 executor=A；resolver 默认同 executor。
- 测试人员：一般是当前发送人；不知道可不填。
- BUG/遗留：默认 BUG，除非用户明确说遗留。
- 来源：正服默认用户反馈；测服/预发布默认研发技术-测试。
- 是否研发立项：默认否。
- 产品：默认药智数据企业版。
- 项目：明确提到项目才填；否则填无。
- 数据库：选择语义最匹配的下拉项；例如“中国上市”通常是中国上市药品；找不到填无。
- 服务组织：默认集团公司。
- 严重程度：默认一般，除非用户明确说严重/致命/轻微。
- 时间：用户没说就不填，CLI 会用当天 08:30 和 22:00。
- 迭代：正服默认线上缺陷迭代；测服/预发布如果用户没说迭代，不要猜，让 CLI 追问。

fields_json example:
{"title":"【中国上市】检索生僻字会报错","description":"企业版正服中国上市检索生僻字会报错","environment":"正服","executor":"AITester","resolver":"AITester","related_database":"中国上市药品","related_project":"无"}

If meaning is unclear and a required business choice cannot be inferred, still call the tool with known fields in fields_json; the CLI will ask the user for the missing field.`;

export default defineToolPlugin({
  id: "openclaw-ci-defect-assistant",
  name: "OpenClaw CI Defect Assistant",
  description: "Mandatory executor for Jenkins, CI, Teambition, bug, defect, issue, 缺陷, 创建缺陷, 提 bug, 确认, 状态, and 链接 chat requests.",
  configSchema: ConfigSchema,
  tools: (tool) => [
    tool({
      name: "ci_defect_assistant_chat",
      description: TOOL_DESCRIPTION,
      parameters: Type.Object({
        user_id: Type.String({ description: "Real DingTalk sender id." }),
        conversation_id: Type.String({ description: "Real DingTalk conversation id. In group chat use Conversation info.chat_id." }),
        text: Type.String({ description: "Current user message verbatim. Do not rewrite a full task request into confirmation." }),
        fields_json: Type.Optional(Type.String({ description: "Optional JSON object string. For Teambition defect creation, fill semantic fields here. Use {} for confirmation/query/Jenkins." })),
      }),
      execute: async ({ user_id, conversation_id, text, fields_json }, config) => {
        const args = [
          "chat",
          "--user-id",
          user_id,
          "--conversation-id",
          conversation_id,
          "--text",
          text,
        ];
        let fieldsDir: string | undefined;
        if (fields_json && fields_json.trim() && fields_json.trim() !== "{}") {
          fieldsDir = mkdtempSync(join(tmpdir(), "ci-defect-assistant-"));
          const fieldsFile = join(fieldsDir, "fields.json");
          writeFileSync(fieldsFile, fields_json, "utf8");
          args.push("--fields-file", fieldsFile);
        }
        try {
          return await runCli(config.command || DEFAULT_COMMAND, config.projectRoot || DEFAULT_PROJECT_ROOT, args);
        } finally {
          if (fieldsDir) {
            rmSync(fieldsDir, { recursive: true, force: true });
          }
        }
      },
    }),
  ],
});

async function runCli(command: string, projectRoot: string, args: string[]) {
  const { stdout, stderr, code } = await run(command, args, projectRoot);
  if (code !== 0) {
    return { reply: stderr || stdout || `CLI exited with ${code}`, result: { success: false, code: "cli_failed" } };
  }
  try {
    const result = JSON.parse(stdout);
    return typeof result?.reply === "string" ? visibleReply(result.reply) : stdout;
  } catch {
    return stdout || "CLI returned empty output";
  }
}

function visibleReply(reply: string) {
  return `必须原样发送下面整段内容，不要摘要，不要改写，不要只发送确认码：\n${markdownLineBreaks(reply)}`;
}

function markdownLineBreaks(text: string) {
  return text.replace(/\n/g, "  \n");
}

function run(command: string, args: string[], cwd: string): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      windowsHide: true,
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
