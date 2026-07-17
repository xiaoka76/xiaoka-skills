# Checklist

- [x] `src/seedream/` 目录结构创建完成，包含 `__init__.py`、`__main__.py`、`config.py`
- [x] `pyproject.toml` 配置正确，依赖声明完整，scripts 入口指向 `seedream.cli:app`
- [x] `static/` 已移入 `src/seedream/static/`，路径更新正确
- [x] 核心生成函数（`single_generate`, `normalize_coords`, `generate_from_session`）已迁移且签名不变
- [x] Session 读写函数已迁移，状态机逻辑完整
- [x] CLI 入口 `seedream generate` 可正常调用，参数与旧版一致
- [x] CLI 入口 `seedream session summary|get-prompt|set-prompt|list-images` 可正常调用
- [x] CLI 入口 `seedream webui` 可正常启动 WebUI 服务
- [x] `.env` 文件自动加载正常工作
- [x] 默认输出目录 `.seedream/` 创建正确，`--output-dir` 参数覆盖生效
- [x] `python -m seedream generate ...` 可正常调用
- [x] 旧脚本文件 `scripts/` 目录删除（generate.py, edit_session.py, edit_webui.py）
- [x] SKILL.md 文档已更新（安装、CLI、API、输出目录）
- [x] `uv tool install .` 安装后 `seedream` 命令全局可用