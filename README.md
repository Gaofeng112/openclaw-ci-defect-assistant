# OpenClaw CI Defect Assistant

基于 OpenClaw 的 CI 流水线触发与缺陷助手后端工具服务。

## 当前进度

- 已完成 `GET /health`。
- 已完成 `POST /tools/jenkins/trigger` 本地 mock 接口。
- 已完成 `POST /tools/bugs/create` 本地 mock 接口。
- 已完成 Jenkins job 白名单校验。
- 已完成基于用户角色的 Jenkins 触发权限校验。

## 本地启动

```powershell
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## Docker 部署

先确认 Docker Desktop 已启动。

构建镜像：

```powershell
docker build -t openclaw-ci-defect-assistant:local .
```

直接运行容器：

```powershell
docker run --rm -p 8000:8000 --env-file .env openclaw-ci-defect-assistant:local
```

使用 Docker Compose：

```powershell
docker compose up --build
```

如果本机 `8000` 端口已经被本地 uvicorn 占用，可以临时映射到 `8001`：

```powershell
$env:HOST_PORT=8001
docker compose up --build
```

验证容器服务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 配置说明

`configs/jobs.yaml` 配置 Jenkins job 白名单：

```yaml
smoke:
  job_path: "QA/smoke-test"
  allowed_envs:
    - test
    - pre
  required_params:
    - env
    - branch
  allowed_roles:
    - qa
    - admin
  confirm_required: true
```

`configs/users.yaml` 配置用户角色：

```yaml
u001:
  name: "QA User"
  roles:
    - qa
```

权限规则：

```text
用户 roles 和 job.allowed_roles 有交集，则允许触发。
否则返回无权限。
```

## Jenkins 接口验证

未确认时不会触发 Jenkins：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"test","branch":"release/1.0.0"}'
```

确认后触发 Jenkins：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"test","branch":"release/1.0.0","confirmed":true}'
```

无权限用户：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u002","job":"smoke","env":"test","branch":"release/1.0.0"}'
```

管理员触发：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"admin001","job":"regression","env":"test","branch":"release/1.0.0"}'
```

非法任务：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"unknown","env":"test","branch":"release/1.0.0"}'
```

非法环境：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"prod","branch":"release/1.0.0"}'
```

缺少 branch：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"test"}'
```

## 真实 Jenkins 配置

`.env` 需要填写：

```env
JENKINS_BASE_URL=http://your-jenkins-host
JENKINS_USER=your-user
JENKINS_TOKEN=your-api-token
```

接口仍然只允许传 `job=smoke`、`job=regression` 这类白名单别名。真实 Jenkins 路径必须来自 `configs/jobs.yaml` 的 `job_path`。

当前实现会调用：

```text
POST {JENKINS_BASE_URL}/job/QA/job/smoke-test/buildWithParameters
```

参数来自请求体：

```text
env
branch
parameters
```

## 自然语言触发 Jenkins

钉钉/OpenClaw 接入说明见：

```text
docs/dingtalk-jenkins-flow.md
```

推荐自然语言入口：

```text
POST /assistant/chat
```

Jenkins 专用自然语言入口：

```text
POST /assistant/jenkins/trigger
```

钉钉机器人直接回调入口：

```text
POST /callbacks/dingtalk
```

请求中可以传 `conversation_id`。同一个 `conversation_id` 下，系统会记住前面已经解析出的 `job/env/branch`。响应中的 `reply` 可以直接发回聊天窗口或钉钉群。

缺参数时会返回 `missing_fields`：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/assistant/chat -ContentType 'application/json' -Body '{"user_id":"u001","conversation_id":"demo-chat-1","text":"帮我执行 ci_test"}'
```

补充参数后，不会立即触发 Jenkins，会先要求确认：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/assistant/chat -ContentType 'application/json' -Body '{"user_id":"u001","conversation_id":"demo-chat-1","text":"环境 test，分支 main"}'
```

文本包含确认意图时才会触发真实 Jenkins：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/assistant/chat -ContentType 'application/json' -Body '{"user_id":"u001","conversation_id":"demo-chat-1","text":"确认"}'
```

当前支持的解析方式：

```text
job：匹配 jobs.yaml 中的别名或 Jenkins job 名称
env：识别 “环境 test”、"env=test"、"测试环境"、"预发环境"
branch：识别 “分支 main”、"branch=main"
confirmed：文本包含 “确认”、“可以执行”、“同意执行” 等确认意图
```

## Bug 接口验证

缺字段时返回 `missing_fields`：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/bugs/create -ContentType 'application/json' -Body '{"user_id":"u001","title":"登录失败","description":"输入正确密码后仍提示失败","severity":"P2","module":"auth"}'
```

字段齐全时 mock 创建成功：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/bugs/create -ContentType 'application/json' -Body '{"user_id":"u001","title":"登录失败","project_id":"demo-project","tasklist_id":"demo-tasklist","module":"auth","severity":"P2","env":"test","steps":"输入正确账号密码后点击登录","expected":"进入首页","actual":"提示500"}'
```
