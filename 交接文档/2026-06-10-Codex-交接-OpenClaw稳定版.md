# 交接文档

**日期：** 2026-06-10
**交接自：** Codex
**项目：** C:\2_PROJECT\proj\openclaw-ci-defect-assistant

---

## 目标

当前目标是把钉钉私聊机器人接入 OpenClaw，用自然语言触发 Jenkins 自动化测试，并在后续接入 TB/Teambition 缺陷创建。用户现在处于验证阶段，但要求方案尽量稳定，不能只靠提示词和临时命令跑通。

## 已完成

- 已确认钉钉私聊机器人能到达 OpenClaw，群聊机器人之前因为权限问题不能稳定测试，当前建议优先用私聊测试。
- 已确认当前私聊用户 ID 是 `17797610609074237`，`configs/users.yaml` 已包含该用户，Jenkins 权限已能通过。
- Jenkins 自动化测试链路已经真实跑通过，审计日志里有多次 `build_success`，包括 `#18` 和 `#19`，链接形如 `http://113.249.104.79:8090/job/openclaw-ci-test/19/`。
- 已修复 `scripts/call_ci_assistant.py` 的路由问题，使“执行 Jenkins ... 等待执行结果”走 `jenkins.trigger`，不是误走 `jenkins.query`。
- 已确认 Jenkins 本身不是问题，问题出在 OpenClaw `exec` 对长任务提前返回 `Command still running`，模型收到中间结果后提前发了“正在执行”。
- 已设置 `C:\Users\DELL\.openclaw\openclaw.json` 的 `tools.exec.backgroundMs = 60000`，让 OpenClaw 默认等 60 秒再决定是否进入后台。
- 已更新 `C:\Users\DELL\.openclaw\workspace\AGENTS.md`：CI/Jenkins/TB wrapper 命令必须使用 `yieldMs: 60000`，如果仍返回 `Command still running`，必须 `process poll` 到最终 JSON 后再回复。
- 已更新 `C:\Users\DELL\.openclaw\workspace\TOOLS.md`：补充 wrapper 使用 `exec` 时必须设置 `yieldMs: 60000`。
- 已把 OpenClaw 工作区规则里残留的旧直聊 ID `36665056041252632` 改成当前私聊 ID `17797610609074237`。
- 已执行 `openclaw config validate`，结果为 `Config valid: ~\.openclaw\openclaw.json`。
- 已执行 `openclaw gateway restart`，结果为 `Restarted Scheduled Task: OpenClaw Gateway`。
- 已执行 `openclaw status --deep`，DingTalk 状态为 `OK configured`，Gateway 可达。
- 已执行 `openclaw channels status`，结果显示 DingTalk `enabled, configured, running, connected`。
- 已调研稳定版路线：短期保留 Python executor，长期建议做成 OpenClaw 原生工具插件，而不是继续依赖 `exec`。

## 失败的尝试

- 试过群聊机器人测试，但群聊权限不足，后续改为私聊测试。
- 之前机器人/企业应用走过旧配置，导致不在真实的“重庆康洲大数据”应用场景里，后续切换到了真实应用。
- DingTalk AICard 创建出现过 403，日志里显示会降级为普通消息模式；这不是 Jenkins 失败，但会影响流式卡片体验。
- 只靠工作区提示词要求模型在 `Command still running` 后轮询，仍然不够稳，因为模型可能先发“正在执行”。因此补了 `tools.exec.backgroundMs = 60000` 和 `yieldMs: 60000`。
- 继续使用 `exec` 可以跑通验证，但它不是最终稳定方案，因为仍依赖模型遵守规则。

## 关键决策

- 决策：Jenkins 不能直接暴露给模型随意调用，必须通过本地可信 executor。
  原因：executor 已经处理权限、确认、参数校验、审计、Jenkins 轮询和结果格式。
- 决策：当前验证阶段继续保留 `scripts/call_ci_assistant.py`。
  原因：它已经跑通 Jenkins 真实结果，改动最小。
- 决策：稳定版应做成 OpenClaw 原生工具插件。
  原因：OpenClaw 原生工具是结构化调用，比 `exec` 跑命令稳定，能减少模型提前回复和命令拼错。
- 决策：MCP 暂不作为第一阶段。
  原因：MCP 更适合多个客户端复用同一套工具；当前只服务 OpenClaw，原生插件更短、更稳。
- 决策：TB 缺陷创建后续也应进入同一个工具插件，不要继续靠长命令和提示词兜住。
  原因：TB 必填字段多，字段映射必须由本地 executor 控制。

## 当前状态

OpenClaw、DingTalk 私聊、Jenkins executor 都处于可用状态。Jenkins 已有真实成功构建记录。当前最新修复已经重启网关并通过健康检查。

还未验证的是：用户在钉钉私聊里重新发送 Jenkins 测试请求后，机器人是否已经不再回复“正在执行”，而是等待 Jenkins 完成后直接返回最终 SUCCESS 和链接。

当前项目工作区存在较多未提交改动，包括：

- `app/auth.py`
- `app/schemas.py`
- `app/tools/teambition_tool.py`
- `configs/users.yaml`
- `docs/openclaw-tool-router-prompt.md`
- `scripts/call_ci_assistant.py`
- `scripts/ci_executor.py`

这些改动不是本次 offwork 写文档时产生的，后续不要随意回退。

## 下一步

1. 让用户在钉钉私聊机器人里发送：

   ```text
   执行 Jenkins 自动化测试任务 api-auto-test，环境 pre，分支 develop，等待执行结果。
   ```

2. 机器人返回确认提示后，用户发送：

   ```text
   确认
   ```

3. 观察钉钉回复是否直接返回最终结果，期望格式类似：

   ```text
   Jenkins 任务执行完成: SUCCESS
   任务：api-auto-test
   环境：pre
   分支：develop
   状态：SUCCESS
   链接：http://113.249.104.79:8090/job/openclaw-ci-test/<n>/
   ```

4. 同时查看审计日志：

   ```powershell
   Get-Content -Path 'runtime\audit\2026-06-10.jsonl' -Tail 30
   ```

5. 如果钉钉仍回复“正在执行”，检查最新轨迹文件：

   ```powershell
   Get-ChildItem -Path 'C:\Users\DELL\.openclaw\agents\main\sessions' -Filter '*.trajectory.jsonl' | Sort-Object LastWriteTime -Descending | Select-Object -First 3
   ```

6. 如果轨迹里仍出现 `Command still running` 后模型直接回复，不要继续加提示词补丁，直接进入原生工具插件方案。

7. 稳定版实现路线：

   - 新建本地 OpenClaw 插件，例如 `openclaw-kz-ci-tools`。
   - 插件注册 `ci_request_jenkins_run`、`ci_confirm_jenkins_run`、`ci_query_jenkins_result`。
   - 插件内部继续调用现有 Python executor，不重写业务逻辑。
   - 工具参数只暴露 `job_key`、`env`、`branch`、`wait_result`。
   - 用户 ID、会话 ID从钉钉上下文取，不让模型猜。
   - 验证插件工具注册：

     ```powershell
     openclaw plugins inspect <plugin-id> --runtime --json
     ```

8. Jenkins 稳定后，再把 TB 缺陷创建做成同一插件内的工具：

   - `tb_create_defect`
   - `tb_query_defect`

## 相关文件

- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\scripts\call_ci_assistant.py` - 钉钉/OpenClaw 文本进入本地 executor 的 wrapper。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\scripts\ci_executor.py` - Jenkins/TB 真实执行入口。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\users.yaml` - 用户权限配置，当前私聊 ID 已加入。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\jobs.yaml` - Jenkins job、环境、分支等配置。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\teambition.yaml` - TB/Teambition 字段和项目配置。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\runtime\audit\2026-06-10.jsonl` - 当前验证最重要的审计日志。
- `C:\Users\DELL\.openclaw\openclaw.json` - OpenClaw 主配置，已设置 `tools.exec.backgroundMs = 60000`。
- `C:\Users\DELL\.openclaw\workspace\AGENTS.md` - OpenClaw agent 工作区规则，已补 Jenkins/TB wrapper 强制规则。
- `C:\Users\DELL\.openclaw\workspace\TOOLS.md` - OpenClaw 本地工具说明，已补 `yieldMs: 60000`。
- `C:\Users\DELL\AppData\Local\Temp\openclaw\openclaw-2026-06-10.log` - OpenClaw 当日日志。
- `C:\Users\DELL\.openclaw\agents\main\sessions\*.trajectory.jsonl` - OpenClaw 对话轨迹，可查模型是否提前回复。
