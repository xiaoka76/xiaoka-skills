# 重构 seedream5pro-image 为可安装包 Spec

## Why

现有三个脚本（`generate.py`、`edit_session.py`、`edit_webui.py`）相互独立，无统一入口，无法通过 `uv tool install` 安装为全局命令。输出目录 `seedream-output/` 未隐藏，无 `.env` 自动加载，import 路径需要手动 `sys.path.append`。

## What Changes

- **BREAKING**: 删除 `scripts/` 目录下的三个独立脚本，迁入 `src/seedream/` 包结构
- **BREAKING**: 默认输出目录从 `seedream-output/` 改为 `.seedream/`（隐藏目录）
- 创建 `pyproject.toml`，支持 `uv tool install` 安装为全局 `seedream` 命令
- 统一 CLI 入口：`seedream generate`、`seedream session`、`seedream webui` 三个子命令
- 添加 `python -m seedream` 入口
- 自动加载 `.env` 文件（`python-dotenv`）
- 提取公共常量和工具函数到 `config.py`，复用代码
- `static/` 移入包内 `src/seedream/static/`，确保打包后 WebUI 可用
- 保留 `single_generate()` 纯函数 API，agent 可直接 `from seedream.generate import single_generate`

## Impact

- Affected specs: `add-interactive-edit-webui`（WebUI 后端路径需更新）
- Affected code: `scripts/generate.py`, `scripts/edit_session.py`, `scripts/edit_webui.py`, `static/`（全部迁移）
- 引用旧脚本的 agent 调用需更新为新入口

## ADDED Requirements

### Requirement: 包结构
系统 SHALL 提供 `src/seedream/` 包结构，包含 `pyproject.toml`。

#### Scenario: uv tool install
- **WHEN** 用户执行 `uv tool install .`
- **THEN** `seedream` 命令全局可用

#### Scenario: python -m
- **WHEN** 用户执行 `python -m seedream generate --help`
- **THEN** 显示生成子命令的帮助信息

### Requirement: 统一 CLI
系统 SHALL 提供 `seedream generate`、`seedream session`、`seedream webui` 三个子命令。

#### Scenario: generate 子命令
- **WHEN** 用户执行 `seedream generate -p "一只猫"`
- **THEN** 执行文生图，输出到 `.seedream/` 目录

#### Scenario: session 子命令
- **WHEN** 用户执行 `seedream session summary <path>`
- **THEN** 显示 session 摘要信息

#### Scenario: webui 子命令
- **WHEN** 用户执行 `seedream webui --port 8090`
- **THEN** 启动 FastAPI 服务，打开交互编辑 WebUI

### Requirement: 环境变量加载
系统 SHALL 自动从 `.env` 文件加载 `ARK_API_KEY` 等环境变量。

#### Scenario: .env 文件存在
- **WHEN** 运行目录下存在 `.env` 文件
- **THEN** 自动加载，无需手动 export

### Requirement: 输出目录
系统 SHALL 默认输出到 `.seedream/` 目录，支持 `--output-dir` 覆盖。

#### Scenario: 默认输出
- **WHEN** 用户未指定 `--output-dir`
- **THEN** 图片保存到运行目录下的 `.seedream/`

#### Scenario: 自定义输出
- **WHEN** 用户指定 `--output-dir ./my-images`
- **THEN** 图片保存到 `./my-images/`

## MODIFIED Requirements

### Requirement: 坐标转换工具
函数签名和功能不变，仍可通过 `from seedream.generate import normalize_coords` 导入。

## REMOVED Requirements

### Requirement: 旧脚本入口
**Reason**: 统一为包结构
**Migration**: `python generate.py` → `seedream generate` 或 `python -m seedream generate`