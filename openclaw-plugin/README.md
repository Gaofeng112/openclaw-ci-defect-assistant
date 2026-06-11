# OpenClaw CI Defect Assistant Plugin

这是 OpenClaw 插件壳，暴露一个工具：

```text
ci_defect_assistant_chat
```

工具会把 `user_id`、`conversation_id`、`text` 转给主项目 CLI：

```text
ci-defect-assistant chat
```

## 最小安装

先在项目根目录安装 CLI：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
ci-defect-assistant doctor
```

再进入插件目录校验插件：

```powershell
cd openclaw-plugin
npm install
npm run plugin:validate
cd ..
```

安装到 OpenClaw：

```powershell
openclaw plugins install --link .\openclaw-plugin --dangerously-force-unsafe-install
openclaw gateway restart
openclaw plugins inspect openclaw-ci-defect-assistant
openclaw plugins doctor
```

插件会调用本地 CLI，所以 OpenClaw 会要求使用 `--dangerously-force-unsafe-install` 明确确认。

## 配置

默认情况下，插件会从自身目录反推出仓库根目录，不需要写死本机路径。

如果插件目录不在仓库里的 `openclaw-plugin/` 下，或者 CLI 命令不在 `PATH` 里，可以配置：

```json
{
  "projectRoot": "D:\\path\\to\\openclaw-ci-defect-assistant",
  "command": "D:\\path\\to\\openclaw-ci-defect-assistant\\.venv\\Scripts\\ci-defect-assistant.exe"
}
```

`projectRoot` 会同时作为 CLI 工作目录和 `CI_DEFECT_ASSISTANT_HOME`。

## 开发校验

```powershell
npm test
```
