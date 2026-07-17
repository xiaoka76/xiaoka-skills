# TouchEdit Study Demo

这是给前端学习使用的 TouchEdit 画布演示版。它保留上传图片、缩放/平移画布、拖拽图片、点击/框选生成 grounding prompt 的交互，但不会调用任何模型或 API。

## 运行

```bash
cd /path/to/touch_edit_demo
bash run.sh
```

如果 `8090` 端口被占用，可以指定其他端口：

```bash
cd /path/to/touch_edit_demo
PORT=18090 bash run.sh
```

打开：

```text
http://localhost:8090
```

## 功能

- 普通模式：拖拽图片；拖画布空白区域平移画布。
- 点击模式：点击图片位置，自动追加 `图N<point>x y</point>`。
- 框选模式：在图片上拖框，自动追加 `图N<bbox>x1 y1 x2 y2</bbox>`。
- 坐标是相对单张图片归一化到 `0-1000`。
- 点击“生成”时只在右侧展示本地模型输入预览：最终 prompt 和每张输入图片。

## 依赖说明

项目只依赖本目录内文件和 Python 标准库，不依赖原项目、外部 venv、模型客户端或历史输出目录。
