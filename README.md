# OpenClaw CI Defect Assistant

基于 OpenClaw 的 CI 流水线触发与缺陷助手后端工具服务骨架。

## 当前能力

- `GET /health`：健康检查。
- `POST /tools/jenkins/trigger`：mock 触发 Jenkins 任务。
- `POST /tools/bugs/create`：mock 创建 Teambition 缺陷。
- `configs/jobs.yaml`：Jenkins 任务白名单。
- `configs/users.yaml`：用户角色与任务权限。
- `configs/bug_fields.yaml`：缺陷必填字段与字段映射。

## 本地启动

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

接口文档默认地址：

```text
http://127.0.0.1:8000/docs
```

## 示例请求

合法触发：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"test","branch":"release/1.0.0"}'
```

非法任务：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"unknown","env":"test","branch":"release/1.0.0"}'
```

非法环境：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"prod","branch":"release/1.0.0"}'
```

无权限用户：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u002","job":"smoke","env":"test","branch":"release/1.0.0"}'
```

缺少 branch：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/jenkins/trigger -ContentType 'application/json' -Body '{"user_id":"u001","job":"smoke","env":"test"}'
```

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/tools/bugs/create -ContentType 'application/json' -Body '{"user_id":"u001","title":"登录失败","description":"输入正确密码后仍提示失败","severity":"P2","module":"auth"}'
```
