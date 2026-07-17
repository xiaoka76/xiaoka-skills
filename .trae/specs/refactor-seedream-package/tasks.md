# Tasks

## 任务依赖关系

- Task 1, 2, 3 无依赖，可并行
- Task 4 依赖 Task 1-3（必须先有 `src/seedream/` 目录结构）
- Task 5 依赖 Task 4（必须先确认包结构完整）
- Task 6 依赖 Task 1-5（全部完成后统一更新文档）

---

- [ ] Task 1: 创建包结构和配置文件
  - 创建 `src/seedream/` 目录结构
  - 创建 `pyproject.toml`（依赖：typer, fastapi, uvicorn, httpx, python-dotenv, pydantic）
  - 创建 `src/seedream/__init__.py`
  - 创建 `src/seedream/__main__.py`（`python -m seedream` 入口）
  - 创建 `src/seedream/config.py`（提取常量：MODEL_ID, API_KEY, API_BASE, DEFAULT_OUTPUT_DIR, 格式映射等）
  - 将 `static/` 目录从 `scripts/../static` 移入 `src/seedream/static/`

- [ ] Task 2: 实现核心生成模块
  - 创建 `src/seedream/generate.py`
  - 迁移 `generate.py` 中的纯函数：`normalize_coords`, `single_generate`, `generate_from_session`, `_resolve_image_path`, `_save_b64`, `_download_image`, `_save_metadata`
  - 注意：`_call_api` 和 `_build_request_body` 也从旧文件迁移
  - 确保 `single_generate()` 签名不变，保持向后兼容

- [ ] Task 3: 实现 Session 模块
  - 创建 `src/seedream/session.py`
  - 迁移 `edit_session.py` 中的逻辑：加载/保存 session, 格式化输出
  - 提取状态机常量（STATE_CREATED, STATE_EDITING, STATE_SAVED）和 `_transition_state` 函数
  - 提取 `_init_session`, `_write_session` 函数

- [ ] Task 4: 实现统一 CLI 入口
  - 创建 `src/seedream/cli.py`
  - 使用 Typer 创建三个子命令组：
    - `seedream generate`：文生图/图生图/交互编辑
    - `seedream session summary|get-prompt|set-prompt|list-images`：session 读写
    - `seedream webui`：启动 WebUI 服务
  - 在 `generate` 子命令中集成 `--output-dir` 参数（默认 `.seedream/`）
  - 在 CLI 入口处（`__init__.py` 或 `__main__.py`）调用 `load_dotenv()`

- [ ] Task 5: 实现 WebUI 模块
  - 创建 `src/seedream/webui.py`
  - 迁移 `edit_webui.py` 中的 FastAPI app 工厂函数 `create_app()`
  - 更新静态文件路径为 `Path(__file__).parent / "static"`
  - 更新 session 输出路径为 `.seedream/edit/{session_id}/`
  - 将 `main()` 函数简化，只保留 CLI 参数解析和 uvicorn 启动

- [ ] Task 6: 更新 SKILL.md 文档
  - 更新安装方式（uv tool install）
  - 更新 CLI 使用示例（`seedream generate` 替代 `python generate.py`）
  - 更新输出目录说明（默认 `.seedream/`）
  - 更新 Python API 导入路径（`from seedream.generate import single_generate`）