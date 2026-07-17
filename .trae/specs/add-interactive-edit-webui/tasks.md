# Tasks

- [ ] Task 1: 改造 generate.py — 新增 `--session` 参数和 `generate_from_session()` 方法
  - 新增 CLI 参数 `--session` / `-S`，与 `--prompt` 互斥
  - 新增 `generate_from_session(session_data, **kwargs)` 函数
  - main() 中处理 `--session` 逻辑：读取 session.json → 提取 prompt 和图片路径 → 调用 `single_generate()`

- [ ] Task 2: 创建 edit_session.py — session 读写 CLI 工具
  - 实现 `summary` 子命令：显示 session 摘要
  - 实现 `get-prompt` 子命令：输出 prompt 字段
  - 实现 `set-prompt` 子命令：更新 prompt 字段
  - 实现 `list-images` 子命令：列出图片路径

- [ ] Task 3: 创建 edit_webui.py — WebUI 后端
  - CLI 参数：`--port`, `--preload`
  - 启动时：生成 UUID，创建目录，处理预加载图片，创建 session.json，输出路径
  - API 端点：`/healthz`, `/`, `/*`, `/api/upload`, `/api/save`, `/api/session-info`
  - `/api/upload`：SHA256 哈希去重保存
  - `/api/save`：解码 dataUrl 为本地文件，写入 session.json

- [ ] Task 4: 创建前端文件 (static/) — 基于 demo 改造
  - `static/index.html`：页面结构
  - `static/app.js`：交互逻辑（上传、标注、保存）
  - `static/styles.css`：样式

- [ ] Task 5: 更新 SKILL.md — 补充交互编辑工作流

# Task Dependencies

- Task 3 依赖 Task 4（后端需要前端文件）
- 其他任务无依赖，可并行