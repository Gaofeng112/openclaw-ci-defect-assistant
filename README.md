# CI Defect Assistant

CI Defect Assistant 是一个本地执行器，用来把钉钉里的白话请求转成可确认、可审计的 Jenkins / Teambition 操作。

```text
钉钉 -> OpenClaw / Hermes -> CI Defect Assistant -> Jenkins / Teambition -> 钉钉回复
```

它不替代 OpenClaw 或 Hermes。OpenClaw / Hermes 负责接收消息，本项目负责真正执行：权限检查、字段生成、二次确认、接口调用、审计记录和结果返回。

## 功能

- 触发 Jenkins 任务。
- 查询最近 Jenkins / Teambition 执行结果。
- 根据一句白话生成 Teambition 缺陷完整字段。
- 创建缺陷前先返回预览和确认码。
- 按钉钉用户 ID 做权限控制。

## 适用方式

### OpenClaw

OpenClaw 通过插件调用本项目。

```text
钉钉 -> OpenClaw -> openclaw-plugin -> ci-defect-assistant CLI
```

这种方式需要把路由提示词配进 OpenClaw：

```text
docs/openclaw-tool-router-prompt.md
```

### Hermes MCP

Hermes 可以通过 MCP 调用本项目。

```text
Hermes -> hermes-mcp -> ci-defect-assistant CLI
```

只注册 MCP 不等于 Hermes 一定会调用工具。模型可能自己回答。真实钉钉场景建议使用下面的 Hermes Gateway 直通方式。

### Hermes Gateway 直通

当前本机验证通过的是这个方式：

```text
钉钉 -> Hermes DingTalk Gateway -> ci-defect-assistant CLI
```

遇到 `tb缺陷`、`缺陷`、`提bug`、`Teambition`、`确认 xxxxxx` 这类消息时，DingTalk 入口直接调用本项目 CLI，不再让模型判断是否调用 MCP。

这个直通逻辑目前是本机 Hermes 适配器改动，不在本仓库里。别人复用时，需要在自己的 Hermes 环境里做同样接入，或继续使用 OpenClaw 插件方式。

## 环境要求

- Python 3.11+
- Node.js / npm
- Windows PowerShell，或 macOS / Linux shell
- Jenkins 凭证
- Teambition 凭证
- OpenClaw 或 Hermes 二选一

## 安装

Windows：

```powershell
.\scripts\install.ps1
```

macOS / Linux：

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

只使用 Hermes，不安装 OpenClaw 插件：

```powershell
.\scripts\install.ps1 -SkipOpenClawInstall
```

安装后会生成：

```text
.venv/
runtime/
.env
```

这些都是本机文件，不要提交。

## 配置

### 1. 填写 `.env`

至少填写：

```text
JENKINS_BASE_URL=
JENKINS_USER=
JENKINS_TOKEN=

TEAMBITION_APP_ID=
TEAMBITION_APP_SECRET=
TEAMBITION_OPERATOR_ID=
```

完整模板见：

```text
.env.example
```

### 2. 配置用户权限

```text
configs/users.yaml
```

钉钉真实用户 ID 必须写在这里，否则不能创建缺陷或触发 Jenkins。

示例：

```yaml
"17797610609074237":
  name: "DingTalk QA User"
  roles:
    - qa
```

### 3. 配置 Jenkins

```text
configs/jobs.yaml
```

这里配置 job、参数、环境和可用角色。

### 4. 配置 Teambition

同一个 Teambition 项目和同一套缺陷表单通常不用改：

```text
configs/teambition.yaml
configs/teambition_bug_form.v1.yaml
```

换项目或换表单时，需要重新确认项目 ID、任务列表 ID、字段 ID、选项 ID、成员 ID。

人员名映射在：

```text
configs/teambition_bug_form.v1.yaml
```

当前只配置了 `AITester`。如果希望“给张三创建”真的落到张三，需要补张三的 Teambition 成员 ID。

### 5. 生成 Teambition 登录态

```powershell
.\.venv\Scripts\python.exe scripts\save_teambition_cookie.py
```

生成文件：

```text
runtime/teambition_har/teambition_headers.json
```

这个文件包含登录态，只能放本机。

## OpenClaw 使用

安装后把下面文件内容加入 OpenClaw Agent 提示词或工作区规则：

```text
docs/openclaw-tool-router-prompt.md
```

检查：

```powershell
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
openclaw status --deep
```

## Hermes MCP 使用

安装 MCP：

```powershell
cd hermes-mcp
npm install
npm run build
cd ..
```

注册到 Hermes：

```powershell
$root = (Resolve-Path .).Path
hermes mcp add ci-defect-assistant --command node --args "$root\hermes-mcp\dist\index.js"
```

检查：

```powershell
hermes mcp test ci-defect-assistant
```

MCP 工具名：

```text
ci_defect_assistant_chat
```

参数：

```text
user_id
conversation_id
text
fields_json 可选
```

## Hermes DingTalk 使用

Hermes Gateway 使用钉钉 Stream 模式。钉钉后台创建企业内部机器人后，把凭证写入 Hermes 的 `.env`。

查看 Hermes `.env` 路径：

```powershell
hermes config env-path
```

需要填写：

```text
DINGTALK_CLIENT_ID=
DINGTALK_CLIENT_SECRET=
DINGTALK_ROBOT_CODE=
GATEWAY_ALLOW_ALL_USERS=true
```

启动：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
hermes gateway run --replace
```

后台运行时不要重复执行 `hermes gateway run`。查看状态：

```powershell
hermes gateway status
```

停止：

```powershell
hermes gateway stop
```

## 本地验证

### Jenkins mock

```powershell
$env:JENKINS_MOCK='1'
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
```

### Teambition 缺陷预览

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id 17797610609074237 --conversation-id demo --text "企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷"
```

期望返回：

```text
准备创建 Teambition 缺陷，请确认：
项目：药智数据企业版
类型：缺陷
标题：【中国上市】检索生僻字会报错
...
回复“确认 xxxxxx”创建
```

### Hermes MCP

```powershell
hermes mcp test ci-defect-assistant
```

应看到：

```text
Connected
Tools discovered: 1
ci_defect_assistant_chat
```

## 使用示例

### 创建缺陷

钉钉发送：

```text
企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷
```

系统返回完整预览。确认后创建：

```text
确认 7d1f9a
```

### 触发 Jenkins

钉钉发送：

```text
执行 ci_test 环境 test 分支 develop
```

系统返回预览。确认后执行：

```text
确认 7d1f9a
```

## 不要提交的文件

```text
.env
.venv/
runtime/
HAR/
hermes-mcp/node_modules/
hermes-mcp/dist/
openclaw-plugin/node_modules/
openclaw-plugin/dist/
*.har
*.log
```

## 交付给别人

可以交付：

```text
app/
configs/
docs/
hermes-mcp/
openclaw-plugin/
scripts/
skills/
.env.example
pyproject.toml
README.md
requirements.txt
```

别人需要自己准备：

```text
.env
Teambition 登录态
钉钉机器人凭证
Hermes / OpenClaw 本机配置
```

## 常见问题

### 为什么 Hermes 回复不像 OpenClaw？

通常是 Hermes 没有调用 MCP，而是模型自己回答。日志里如果看到 `tool_turns=0`，就是这个问题。

稳定方案是 DingTalk 入口直通本项目 CLI，或使用 OpenClaw 插件路由。

### 为什么钉钉回复没有换行？

钉钉 Markdown 需要强制换行。发送层要把 `\n` 转成 Markdown 换行：

```text
两个空格 + 换行
```

### 为什么“给张三创建”没有变成张三负责人？

因为配置里没有张三的 Teambition 成员 ID。补到 `configs/teambition_bug_form.v1.yaml` 的 `members.by_name` 后才会生效。

### 为什么报 `pydantic_core` 缺失？

通常是 Hermes 进程调用项目 CLI 时继承了 Hermes 的 Python 环境。应显式调用项目 `.venv` 的 Python，并清理 `PYTHONPATH`、`VIRTUAL_ENV`、`PYTHONHOME`。

### 能不能把 `.env` 和 `runtime/` 发给别人？

不能。这里面有密钥、Cookie、Token 和本机运行数据。

