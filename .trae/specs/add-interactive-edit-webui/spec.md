# 交互编辑 WebUI Spec

## Why

当前 Seedream 5.0 Pro 的交互编辑功能只能通过 CLI 使用，用户需要手动测量像素坐标并编写 `<point>/<bbox>` 标签，门槛高且缺乏视觉反馈。需要提供一个 WebUI 让用户通过鼠标直接操作图片，再结合 agent 的语义理解能力完善 prompt，形成完整的编辑工作流。

## What Changes

- **新增** `scripts/edit_webui.py` — WebUI 后端（HTTP 服务）
- **新增** `static/` 目录 — 前端页面（基于官方 touch_edit_demo 改造）
- **新增** `scripts/edit_session.py` — session 读写 CLI 工具
- **改造** `scripts/generate.py` — 新增 `--session` 参数和 `generate_from_session()` 方法
- **更新** `SKILL.md` — 补充交互编辑工作流说明

## Impact

- Affected specs: 图像生成技能（seedream5pro-image）
- Affected code:
  - `skills/seedream5pro-image/scripts/generate.py` — 修改
  - `skills/seedream5pro-image/scripts/edit_webui.py` — 新建
  - `skills/seedream5pro-image/scripts/edit_session.py` — 新建
  - `skills/seedream5pro-image/static/index.html` — 新建
  - `skills/seedream5pro-image/static/app.js` — 新建
  - `skills/seedream5pro-image/static/styles.css` — 新建
  - `skills/seedream5pro-image/SKILL.md` — 修改

## ADDED Requirements

### Requirement: WebUI 后端 (edit_webui.py)

系统 SHALL 提供一个基于 Python http.server 的 WebUI 后端。

#### CLI 参数
- `--port` / `-p`: 端口号（默认 8090）
- `--preload`: 预加载图片路径（可选，可多次指定）

#### 启动行为
- 生成 UUID 作为会话 ID
- 创建 `seedream-output/edit/{uuid}/` 目录
- 如果有 `--preload` 图片，复制到该目录下
- 创建 `seedream-output/edit/{uuid}/session.json` 文件
- 输出 session 文件路径到命令行
- 绑定 `0.0.0.0` 以支持远程访问

#### API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/healthz` | GET | 健康检查，返回 session 信息 |
| `/` | GET | 前端页面 |
| `/*` | GET | 静态文件服务 |
| `/api/upload` | POST | 上传图片，计算 SHA256 哈希，按哈希命名保存，避免重复 |
| `/api/save` | POST | 保存 session：接收前端 JSON，解码 dataUrl 为本地文件，写入 session.json |
| `/api/session-info` | GET | 返回 session 状态信息 |

**`/api/save` 数据处理逻辑**：
- 收到前端传来的 `{prompt, images[{inputLabel, name, dataUrl, naturalWidth, naturalHeight}]}`
- 将每个 `dataUrl`（base64）解码保存为本地文件到 `seedream-output/edit/{uuid}/` 目录
- 文件名 = 哈希值，保持原始扩展名
- 将 `dataUrl` 替换为 `local_path` 再写入 session.json
- 如果已有相同哈希的文件，复用已有文件路径

#### Session JSON 格式

```json
{
  "session_id": "uuid",
  "created_at": "2026-07-17T12:00:00",
  "status": "saved",
  "preloaded_images": ["path/to/preloaded.png"],
  "images": [
    {
      "inputLabel": "图1",
      "name": "photo.jpg",
      "local_path": "seedream-output/edit/{uuid}/abc123.jpg",
      "naturalWidth": 1920,
      "naturalHeight": 1080
    }
  ],
  "prompt": "把 图1<bbox>179 283 796 986</bbox> 的狗换成猫",
  "annotations": [
    {
      "id": 1,
      "type": "bbox",
      "image_label": "图1",
      "normalized_coords": [179, 283, 796, 986],
      "token": "图1<bbox>179 283 796 986</bbox>"
    }
  ],
  "user_intent": "把这个狗换成更好看的猫"
}
```

### Requirement: 前端 (static/)

系统 SHALL 提供一个基于 Canvas 的交互编辑前端，基于官方 touch_edit_demo 改造。

#### 功能
- 图片上传（点击上传 + 拖拽上传）
- 图片在画布中自由拖拽位置
- 画布平移（空格+拖拽 / 右键拖拽）
- 画布缩放（滚轮）
- 点选模式：点击图片位置生成 `<point>` 标注
- 框选模式：在图片上拖框生成 `<bbox>` 标注
- 标注可删除
- 编辑意图输入框（用户写模糊指令）
- 保存按钮：将标注 + 意图 + 图片数据提交到 `/api/save`

#### 改造点（相对于 demo）
- 去掉"生成"按钮和相关逻辑
- "编辑指令"改为"编辑意图"，用户写模糊自然语言
- 新增"保存"按钮
- 显示保存状态

### Requirement: Session 读写工具 (edit_session.py)

系统 SHALL 提供一个 CLI 工具，让 agent 能方便地读写 session.json。

#### 子命令

```bash
# 查看 session 摘要
python edit_session.py summary <session-path>

# 获取当前 prompt
python edit_session.py get-prompt <session-path>

# 更新 prompt（agent 润色后写回）
python edit_session.py set-prompt <session-path> --prompt "新的prompt"

# 列出图片路径
python edit_session.py list-images <session-path>
```

#### `summary` 输出示例
```
Session: a1b2c3
Status: saved
Images: 2 张
  - 图1: path/to/img1.jpg (1920x1080)
Annotations: 2 个
  - #1 bbox 图1: 179 283 796 986
  - #2 point 图1: 520 460
Prompt: 把 图1<bbox>179 283 796 986</bbox> 的狗换成猫
```

### Requirement: generate.py 改造

系统 SHALL 在 generate.py 中新增 `--session` 参数，支持直接传入 session.json 路径执行生成。

#### CLI 新增
```bash
python generate.py --session seedream-output/edit/{uuid}/session.json
```

#### `--session` 与 `--prompt` 互斥逻辑
- 如果传了 `--session`，从 session.json 读取 `prompt` 和 `images[].local_path`
- 使用 `_resolve_image_path()` 将本地路径转为 base64
- 调用 API 执行生成

#### 新增方法
```python
def generate_from_session(session_data: dict, **kwargs) -> dict:
    """从 session JSON 数据执行图像生成"""
```

### Requirement: SKILL.md 更新

在 SKILL.md 中补充"交互编辑工作流"章节，说明：
1. 启动 WebUI
2. 用户在 WebUI 中标注
3. agent 读取 session 并完善 prompt
4. 执行生成

## REMOVED Requirements

无