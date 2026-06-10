# 交接文档

**日期：** 2026-06-09
**交接自：** Codex
**项目：** `C:\2_PROJECT\proj\openclaw-ci-defect-assistant`

---

## 目标

继续做 OpenClaw / 钉钉机器人创建 Teambition 缺陷的真实字段配置。目标不是立刻创建任务，而是先把公司 Teambition bug 表单需要的字段、字段 ID、选项 ID、人员 ID 等整理成可开发的初版配置，后续再安全接入代码。

本轮用户特别强调：不要创建任务，避免干扰企业正常工作。

## 已完成

- ✅ 读取了老师通过接口抓取的配置文件：`C:\2_PROJECT\proj\config-v1.md`。
- ✅ 确认 `config-v1.md` 是 UTF-8 文件，PowerShell 直接显示会乱码，但 Python UTF-8 读取正常。
- ✅ 解析出老师配置中已有的关键字段：
  - `project_id: 6539bbd14c06f79e66aaf526`
  - `scenariofieldconfig_id: 6539bbd2e9176a0f484edd97`
  - `taskflow_id: 65558b56d28952fb4b0e6fea`
  - `default_status_id: 65558b56d28952fb4b0e6fed`
  - 多个自定义字段 ID 和选项 ID，如缺陷分类、严重程度、BUG/遗留、缺陷环境、缺陷来源、服务组织、是否为研发立项、相关产品。
- ✅ 生成了初版配置草稿：`C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\teambition_bug_form.v1.yaml`。
- ✅ 该配置草稿没有接入运行代码，只作为后续开发参考，避免误触发真实创建。
- ✅ 用 Python 校验了 `configs\teambition_bug_form.v1.yaml` 可以正常被 YAML 解析。
- ✅ 只调用了 Teambition GET / 查询接口，没有调用创建接口。
- ✅ 用当前 `.env` 的 Teambition OpenAPI 查询过以前本地测试项目里创建过的任务，拿到旧测试任务的创建后字段形态：
  - `tasklistId: 6a219252d859396314d11b8c`
  - `sfcId: 6a219252d859396314d11b9f`
  - `stageId: 6a219252d859396314d11b95`
  - `tfsId: 6a219252d859396314d11b89 / 6a219252d859396314d11b8a`
  - `priority` 见到过 `-10` 和 `0`
  - `visible: projectMembers`
- ✅ 检查 Chrome 状态：
  - Chrome 当前未运行。
  - Codex Chrome Extension 已安装并启用。
  - Native host manifest 正常。

## 失败的尝试

- ❌ 尝试用当前 `.env` 的 Teambition OpenAPI 读取老师配置里的公司项目 `6539bbd14c06f79e66aaf526`。
  - 结果：接口返回 `Resource not belong to tenant`。
  - 原因：当前 `.env` 里的 Teambition 应用和公司项目不属于同一个租户或没有该项目权限。

- ❌ 尝试连接 Chrome 读取公司 Teambition 页面。
  - 结果：`Browser is not available: extension`。
  - 后续检查发现 Chrome 未运行；扩展和 Native host 本身正常。
  - 按 Chrome 插件规则，不能擅自打开 Chrome，需要用户确认或手动打开后再继续。

- ❌ 当前还没有真正抓到公司项目里“以前创建完的需求/缺陷”详情。
  - 原因：OpenAPI 被租户权限挡住，Chrome 未运行。
  - 目前配置初版主要来自老师的接口抓取文件、前一次页面只读观察、以及旧测试项目的创建后字段形态。

## 关键决策

- 决策：先新增 `configs\teambition_bug_form.v1.yaml`，不直接改 `configs\teambition.yaml`。
  - 原因：当前仓库已有较多未提交改动，且真实创建字段还没补全；直接接入运行配置风险高。

- 决策：初版配置明确区分“已确认”和“待补充”。
  - 原因：老师配置已包含大量字段 ID，但仍缺 `tasklist_id`、priority 数值、迭代、人员、相关项目、相关数据库等真实创建必需信息。

- 决策：不写创建逻辑，不调用创建接口。
  - 原因：用户明确要求不要创建任务，当前阶段只做配置准备。

- 决策：人员字段必须走本地映射，不能让模型猜 Teambition userId。
  - 原因：测试人员、缺陷解决人、执行者都需要真实成员 ID；模型只能理解中文名或角色，本地工具负责映射 ID。

## 当前状态

当前有一个可继续开发的初版配置文件：

`C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\teambition_bug_form.v1.yaml`

它已经通过 YAML 读取校验，但还不能直接用于真实创建。主要缺口写在文件的 `still_missing_for_real_create` 里：

- 公司项目 `tasklist_id`
- 公司项目 priority 的真实数值
- 迭代列表和默认 `sprintId`
- 测试人员、缺陷解决人、执行者的成员 ID
- 相关项目选项 ID
- 相关数据库选项 ID
- 是否允许不传 `executorId` 来保持“待认领”

当前工作区本来就有未提交改动：

- `.env.example`
- `app/config.py`
- `app/tools/teambition_tool.py`
- `configs/teambition.yaml`
- `scripts/call_ci_assistant.py`
- `交接文档/`

本轮新增了：

- `configs/teambition_bug_form.v1.yaml`
- 本交接文档

## 下一步

1. 如果要继续抓公司项目已有需求/缺陷详情，先让用户打开 Chrome 并登录 Teambition，然后继续连接 Chrome 读取页面自己的 GET 接口。不要点击“完成”或创建按钮。

2. 如果要继续走 OpenAPI，让管理员确认当前 `.env` 的 Teambition 应用是否属于公司项目租户，或者给它开公司项目只读权限。当前报错是：

   ```text
   Resource not belong to tenant
   ```

3. 继续补齐 `configs\teambition_bug_form.v1.yaml` 的缺口：

   ```text
   tasklist_id
   priority values
   sprintId
   member IDs
   related_project options
   related_database options
   executorId 是否可省略
   ```

4. 等配置补齐后，再开发真实创建逻辑。建议先新增独立 adapter 或在 `app/tools/teambition_tool.py` 中按新配置结构改造，但先只做 payload 构造和 dry-run，不直接创建。

5. 开发时先验证只读和 dry-run：

   ```powershell
   $env:PYTHONUTF8='1'
   .\.venv\Scripts\python.exe -m py_compile app\config.py app\tools\teambition_tool.py scripts\ci_executor.py scripts\call_ci_assistant.py
   .\.venv\Scripts\python.exe - <<'PY'
   import yaml
   from pathlib import Path
   p = Path('configs/teambition_bug_form.v1.yaml')
   print(yaml.safe_load(p.read_text(encoding='utf-8')).keys())
   PY
   ```

6. 真实创建接口只有在用户明确同意后再测。默认不要创建公司项目任务。

## 相关文件

- `C:\2_PROJECT\proj\config-v1.md` - 老师通过接口抓取的原始配置草稿。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\teambition_bug_form.v1.yaml` - 本轮生成的 Teambition 缺陷表单初版配置。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\configs\teambition.yaml` - 当前运行代码读取的旧 Teambition 配置，不要直接覆盖。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\app\config.py` - 当前配置读取逻辑。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\app\tools\teambition_tool.py` - 当前 Teambition 创建逻辑，仍偏普通任务创建，后续要改为真实缺陷字段映射。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\scripts\ci_executor.py` - 当前本地执行器入口。
- `C:\2_PROJECT\proj\openclaw-ci-defect-assistant\scripts\call_ci_assistant.py` - OpenClaw/钉钉调用本地执行器的包装脚本。
