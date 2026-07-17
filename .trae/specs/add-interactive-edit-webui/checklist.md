# Checkpoints

- [x] generate.py 新增 `--session` 参数，与 `--prompt` 互斥逻辑正确
- [x] generate.py `generate_from_session()` 方法能正确读取 session.json 并执行生成
- [x] edit_session.py 四个子命令正常工作（summary, get-prompt, set-prompt, list-images）
- [x] edit_webui.py CLI 参数正确，`--preload` 能预加载图片
- [x] edit_webui.py 启动时创建 session.json 并输出路径
- [x] edit_webui.py `/api/upload` 正确保存图片并按 SHA256 哈希去重
- [x] edit_webui.py `/api/save` 正确解码 dataUrl 为本地文件并写入 session.json
- [x] 前端图片上传、点选、框选、标注删除功能正常
- [x] 前端保存按钮将标注 + 意图 + 图片数据提交到 `/api/save`
- [x] 前端去掉"生成"按钮，改为"编辑意图"文本框 + "保存"按钮
- [x] SKILL.md 包含交互编辑工作流说明