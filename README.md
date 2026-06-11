# OpenClaw CI Defect Assistant

这是一个给 OpenClaw / 钉钉使用的 CI 与缺陷助手。

流程：

```text
钉钉 -> OpenClaw -> ci-defect-assistant -> Jenkins / Teambition -> JSON 回复
```

OpenClaw 负责理解用户意图。本项目负责真正执行：权限检查、确认、Jenkins、Teambition、审计日志和结果查询。

## 使用步骤

1. 克隆或解压本仓库。

2. 在项目根目录安装：

```powershell
.\scripts\install.ps1
```

插件会调用本地 CLI，所以 OpenClaw 安装插件时会要求使用 `--dangerously-force-unsafe-install` 明确确认。

3. 复制环境变量文件：

```powershell
Copy-Item .env.example .env
```

4. 填写 `.env`。

至少需要填 Jenkins 和 Teambition 的访问凭证。字段说明已经写在 `.env.example` 里。

5. 检查或修改配置文件。

如果你和交付方使用同一个 Jenkins job、同一个 Teambition 项目、同一套缺陷表单，大多数配置可以直接用默认值。

6. 重启并检查 OpenClaw：

```powershell
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
openclaw status --deep
```

7. 在钉钉里测试。

示例：

```text
执行 ci_test 环境 test 分支 develop
```

创建缺陷会先停在确认步骤，用户回复 `确认` 后才会真正创建。

## 文件目录说明

```text
app/                         核心代码
scripts/install.ps1          一键安装脚本
scripts/call_ci_assistant.py 旧入口，保留兼容
configs/                     Jenkins、用户权限、Teambition ID 配置
openclaw-plugin/             OpenClaw 插件壳
release/交付说明.md          给别人交付时看的说明
.env.example                 环境变量模板，复制成 .env 后填写
runtime/                     本地运行数据，自动生成，不提交
.venv/                       Python 虚拟环境，自动生成，不提交
```

## 配置文件说明

### `.env`

放本机私有信息，例如 Jenkins token、Teambition app secret。

不要提交 `.env`。

### `configs/jobs.yaml`

配置 Jenkins 任务。

常改字段：

```text
job_path       Jenkins job 名称或路径
allowed_roles 允许哪些角色触发
params.env    允许的环境，例如 test、pre
params.branch 默认分支和分支格式
```

如果别人使用同一个 Jenkins job，可以先不改。

### `configs/users.yaml`

配置谁有权限触发任务。

钉钉用户 ID 必须作为 key 写进去，建议加引号：

```yaml
"17797610609074237":
  name: "QA User"
  roles:
    - qa
```

如果用户 ID 不在这里，请求会返回 `unauthorized`。

### `configs/teambition.yaml`

配置 Teambition 项目、任务列表、默认执行人等 ID。

如果使用同一个 Teambition 项目和同一套缺陷表单，可以先用默认值。

如果换了项目，至少要重新确认：

```text
project_id
default_tasklist_id
default_stage_id
taskflowstatus_id
bug_sfc_id
default_executor_id
```

### `configs/teambition_bug_form.v1.yaml`

保存已经抓到的 Teambition 缺陷表单字段 ID 和默认选项。

同一个 Teambition 项目、同一套表单可以复用。

换项目或表单后，这个文件里的字段 ID 大概率不能直接用，需要重新抓取或确认。

## OpenClaw 工具

插件暴露的工具名：

```text
ci_defect_assistant_chat
```

参数：

```text
user_id: "{{ding_user_id}}"
conversation_id: "{{ding_conversation_id}}"
text: "{{original_user_text}}"
```

规则：

- `user_id` 使用真实钉钉发送人 ID。
- `conversation_id` 使用真实会话 ID。群聊必须用 `Conversation info.chat_id`。
- `text` 传当前用户原文。
- 工具返回后，只把 JSON 里的 `reply` 字段发回钉钉。
- 不要直接调用 Jenkins 或 Teambition。

## 本地验证

只检查 CLI 和插件，不安装到 OpenClaw：

```powershell
.\scripts\install.ps1 -SkipOpenClawInstall
```

Jenkins mock：

```powershell
$env:JENKINS_MOCK='1'
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id demo --text "执行 ci_test 环境 test 分支 develop"
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id demo --text "确认"
```

Teambition 预览：

```powershell
.\.venv\Scripts\ci-defect-assistant.exe chat --user-id u001 --conversation-id bug-demo --text "创建缺陷 title: 登录失败 description: 点击保存后无响应"
```
