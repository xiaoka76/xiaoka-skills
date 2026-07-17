# Session 文件格式

## Edit Session

存储在 `.seedream/edit/{session_id}/session.json`，图片以 base64 格式直接嵌入 JSON：

```json
{
  "session_id": "a1b2c3d4e5f6",
  "state_machine": {
    "current_state": "saved",
    "history": [
      {"state": "created", "timestamp": "2024-01-01T00:00:00", "event": "session initialized"},
      {"state": "editing", "timestamp": "2024-01-01T00:01:00", "event": "image uploaded"},
      {"state": "saved", "timestamp": "2024-01-01T00:02:00", "event": "user saved intent"}
    ]
  },
  "images": [
    {
      "inputLabel": "图1",
      "name": "photo.jpg",
      "dataUrl": "data:image/jpeg;base64,/9j/4AAQ...",
      "naturalWidth": 1920,
      "naturalHeight": 1080,
      "x": 80, "y": 80, "width": 360, "height": 203
    }
  ],
  "annotations": [
    {
      "id": 1,
      "type": "bbox",
      "image_label": "图1",
      "normalized_coords": [179, 283, 796, 986],
      "token": "图1<bbox>179 283 796 986</bbox>"
    }
  ],
  "prompt": "把 图1<bbox>179 283 796 986</bbox> 的狗换成猫",
  "user_intent": "把这个狗换成更好看的猫",
  "intent_html": "<span>...</span>",
  "outputs": [
    {
      "image_path": ".../output/a1b2c3d4e5f6.jpg",
      "metadata_path": ".../output/a1b2c3d4e5f6.md",
      "uid": "a1b2c3d4e5f6",
      "generated_at": "2026-07-18T00:00:00"
    }
  ]
}
```

## Generate Session

存储在 `.seedream/generate/{session_id}/session.json`，记录执行状态和参数：

```json
{
  "session_id": "11dc2ec13331",
  "created_at": "2026-07-18T00:41:48",
  "status": "success",
  "error": null,
  "prompt": "水墨风格，一位身穿汉服的美少女...",
  "params": {
    "size": "2K",
    "output_format": "png",
    "watermark": false,
    "optimize": "standard"
  },
  "ref_images": [],
  "outputs": [
    {
      "image_path": ".../output/5deb99a800ea.png",
      "metadata_path": ".../output/5deb99a800ea.md",
      "uid": "5deb99a800ea"
    }
  ]
}
```

## Session 状态机

Edit session 状态迁移：`created → editing → saved`，保存后仍可回到 `editing` 继续编辑。

Generate session 状态机：`pending → running → success/error`。

## Agent 读取 Session

```bash
# 查看 session 摘要（含状态机状态、图片、标注、prompt）
seedream session summary .seedream/edit/{uuid}/session.json

# 获取当前 prompt
seedream session get-prompt .seedream/edit/{uuid}/session.json

# 更新 prompt（agent 润色后）
seedream session set-prompt .seedream/edit/{uuid}/session.json --prompt "..."

# 列出图片信息
seedream session list-images .seedream/edit/{uuid}/session.json
```

## 从 Session 生成

```bash
seedream generate --session .seedream/edit/{uuid}/session.json
seedream generate --session .seedream/edit/{uuid}/session.json --size 2K --output-format png
```

## 文件命名规则

- 图片: `{uuid前12位}.{扩展名}`（如 `a1b2c3d4e5f6.jpg`）
- 元数据: `{uuid前12位}.md`（如 `a1b2c3d4e5f6.md`），包含提示词、模型、尺寸、参数等完整信息
- 参考图: `{md5哈希前12位}.{扩展名}`（如 `431951c2e2f1.png`），以哈希值保存到 output 目录