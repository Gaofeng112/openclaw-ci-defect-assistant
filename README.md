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

安装脚本会自动创建 `.venv/`、`runtime/` 和 `.env`。

插件会调用本地 CLI，所以 OpenClaw 安装插件时会要求使用 `--dangerously-force-unsafe-install` 明确确认。

3. 填写 `.env`。

```powershell
notepad .env
```

至少填写 Jenkins 和 Teambition 凭证。字段说明见 `.env.example`。

4. 检查或修改配置文件。

如果你和交付方使用同一个 Jenkins job、同一个 Teambition 项目、同一套缺陷表单，大多数配置可以直接用默认值。

5. 重启并检查 OpenClaw：

```powershell
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
openclaw status --deep
```

6. 在钉钉里测试。

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

## 配置说明

最常改的是这 3 个地方：

```text
.env                    本机密钥和访问凭证，不提交
configs/users.yaml      谁可以用，钉钉 sender id 要写在这里
configs/jobs.yaml       Jenkins job 名称、允许环境、允许角色
```

一般不用改的是：

```text
configs/teambition.yaml              同一个 Teambition 项目可直接用
configs/teambition_bug_form.v1.yaml  同一套缺陷表单可直接用
```

如果换了 Teambition 项目或缺陷表单，才需要重新确认项目 ID、任务列表 ID、字段 ID、选项 ID、人员 ID。

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

## Skill 和插件的区别

Skill 更像“说明书”，能告诉 Codex 应该怎么处理这类任务。

插件和 CLI 是“执行器”，负责真的触发 Jenkins、创建 Teambition 缺陷、查结果、做权限和确认。

所以如果只是自己在 Codex 里用，Skill 看起来更轻；如果要让钉钉里的 OpenClaw 真正执行任务，仍然需要插件、CLI 和 `.env` 配置。

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
