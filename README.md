# OpenClaw CI Defect Assistant

OpenClaw CI Defect Assistant 是一个给 OpenClaw / 钉钉使用的本地执行器。

它让用户可以在钉钉里用自然语言触发 Jenkins、创建 Teambition 缺陷、查询执行结果。OpenClaw 负责理解用户意图，本项目负责真正执行：权限检查、二次确认、Jenkins 调用、Teambition 调用、审计日志和结果返回。

```text
钉钉 -> OpenClaw -> openclaw-ci-defect-assistant -> Jenkins / Teambition -> 钉钉回复
```

## 能做什么

- 触发 Jenkins 任务。
- 查询最近一次 Jenkins / Teambition 执行结果。
- 根据一句白话生成完整 Teambition 缺陷字段。
- 创建缺陷前返回完整预览，用户确认后才真正创建。
- 按钉钉用户 ID 做权限控制。

## 不能直接做到什么

安装插件后，OpenClaw 只是多了一个可调用工具。要让 OpenClaw 主动调用这个工具，还需要把本项目提供的路由提示词配置到 OpenClaw 的 Agent 提示词或工作区规则里。

如果不配置这一步，OpenClaw 可能只会自己回答，不会真正执行 Jenkins 或创建 Teambition 缺陷。

路由提示词文件：

```text
docs/openclaw-tool-router-prompt.md
```

## 环境要求

- Python 3.11+
- Node.js / npm
- 已安装并配置 OpenClaw
- Windows PowerShell，或 Mac / Linux bash
- Jenkins 访问凭证
- Teambition 访问凭证

## 快速开始

### 1. 获取项目

克隆仓库，或解压项目 zip。

### 2. 安装

Windows：

```powershell
.\scripts\install.ps1
```

Mac / Linux：

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

安装脚本会自动创建 `.venv/`、`runtime/` 和 `.env`，并安装 OpenClaw 插件。

插件会调用本地 CLI，所以 OpenClaw 安装插件时会要求使用 `--dangerously-force-unsafe-install` 明确确认。

### 3. 填写 `.env`

Windows：

```powershell
notepad .env
```

Mac / Linux：

```bash
nano .env
```

至少填写：

```text
JENKINS_BASE_URL=
JENKINS_USER=
JENKINS_TOKEN=

TEAMBITION_APP_ID=
TEAMBITION_APP_SECRET=
TEAMBITION_OPERATOR_ID=
```

完整字段见 `.env.example`。

### 4. 检查配置文件

常改文件：

```text
configs/users.yaml      谁可以用，钉钉 sender id 写在这里
configs/jobs.yaml       Jenkins job、环境、角色
```

同一个 Teambition 项目和同一套缺陷表单通常不用改：

```text
configs/teambition.yaml
configs/teambition_bug_form.v1.yaml
```

如果换了 Teambition 项目或缺陷表单，需要重新确认项目 ID、任务列表 ID、字段 ID、选项 ID、人员 ID。

### 5. 生成 Teambition 登录态

创建 Teambition 缺陷前，需要在本机生成：

```text
runtime/teambition_har/teambition_headers.json
```

Windows：

```powershell
.\.venv\Scripts\python.exe scripts\save_teambition_cookie.py
```

Mac / Linux：

```bash
./.venv/bin/python scripts/save_teambition_cookie.py
```

按脚本提示在浏览器登录 Teambition。生成的登录态只放本机，不要提交，也不要发给别人。

### 6. 配置 OpenClaw 路由规则

把下面文件的内容加入 OpenClaw 的 Agent 提示词或工作区规则：

```text
docs/openclaw-tool-router-prompt.md
```

核心要求是：遇到 Jenkins、CI、Teambition、bug、缺陷、确认、结果查询等请求时，OpenClaw 必须调用工具：

```text
ci_defect_assistant_chat
```

### 7. 重启并检查 OpenClaw

```powershell
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
openclaw status --deep
```

## 使用示例

### 触发 Jenkins

钉钉里发送：

```text
执行 ci_test 环境 test 分支 develop
```

系统会返回预览和确认码。用户确认后才会执行：

```text
确认 7d1f9a
```

### 创建 Teambition 缺陷

钉钉里发送：

```text
企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷
```

系统会先返回完整字段预览，例如标题、描述、缺陷环境、负责人、严重程度、迭代等。用户确认后才会真正创建：

```text
确认 7d1f9a
```

## OpenClaw 工具说明

插件暴露的工具名：

```text
ci_defect_assistant_chat
```

参数：

```text
user_id: "{{ding_user_id}}"
conversation_id: "{{ding_conversation_id}}"
text: "{{original_user_text}}"
fields_json: 可选，OpenClaw 从用户原文里理解出的结构化字段 JSON 字符串
```

规则：

- `user_id` 使用真实钉钉发送人 ID。
- `conversation_id` 使用真实会话 ID。群聊必须用 `Conversation info.chat_id`。
- `text` 传当前用户原文。
- 创建 Teambition 缺陷时，OpenClaw 尽量用语义理解生成 `fields_json`，不要只按关键词拆文本。
- 工具返回后，只把 JSON 里的 `reply` 字段发回钉钉。
- 不要直接调用 Jenkins 或 Teambition。

## 本地验证

只检查 CLI 和插件，不安装到 OpenClaw：

Windows：

```powershell
.\scripts\install.ps1 -SkipOpenClawInstall
```

Mac / Linux：

```bash
./scripts/install.sh --skip-openclaw-install
```

Jenkins mock：

Windows：

```powershell
$env:JENKINS_MOCK='1'
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id demo --text "确认 <上一步返回的确认码>"
```

Mac / Linux：

```bash
export JENKINS_MOCK=1
./.venv/bin/ci-defect-assistant chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
./.venv/bin/ci-defect-assistant chat --user-id u001 --conversation-id demo --text "确认 <上一步返回的确认码>"
unset JENKINS_MOCK
```

Teambition 预览：

Windows：

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id bug-demo --text "企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷"
```

Mac / Linux：

```bash
./.venv/bin/ci-defect-assistant chat --user-id u001 --conversation-id bug-demo --text "企业版正服中国上市检索生僻字会报错，给AITester创建一个tb缺陷"
```

## 交付给别人

可以交付：

```text
app/
configs/
docs/
openclaw-plugin/
scripts/
skills/
.env.example
pyproject.toml
README.md
requirements.txt
```

不要交付：

```text
.env
.venv/
runtime/
HAR/
openclaw-plugin/node_modules/
openclaw-plugin/dist/
*.har
*.log
```

同一个 Teambition 项目和同一套缺陷表单，可以复用 `configs/teambition.yaml` 和 `configs/teambition_bug_form.v1.yaml`。换项目或换表单时，需要重新抓取 ID。

## 目录说明

```text
app/                         Python CLI 和核心执行逻辑
configs/                     Jenkins、用户权限、Teambition ID 配置
docs/openclaw-tool-router-prompt.md  OpenClaw 路由提示词
openclaw-plugin/             OpenClaw 插件壳
scripts/install.ps1          Windows 安装脚本
scripts/install.sh           Mac / Linux 安装脚本
scripts/save_teambition_cookie.py    生成 Teambition 登录态
runtime/                     本地运行数据，自动生成，不提交
.venv/                       Python 虚拟环境，自动生成，不提交
```

## 常见问题

### 安装插件后，为什么钉钉里还是只回答、不创建缺陷？

通常是 OpenClaw 没有调用插件。检查是否已经把 `docs/openclaw-tool-router-prompt.md` 配进 OpenClaw 的 Agent 提示词或工作区规则。

### 为什么不能把 `.env` 和 `runtime/` 发给别人？

这里面有本机密钥、Cookie、Token 和运行数据，只能放在自己的机器上。

### 别人能不能直接复用 Teambition ID？

同一个 Teambition 项目和同一套缺陷表单可以复用。换项目或换表单时不建议复用，需要重新确认 ID。

### 这个项目是 Skill 还是插件？

它主要是插件和本地 CLI。Skill 更像说明书，插件和 CLI 才是真正执行 Jenkins 和 Teambition 的部分。
