# seedream5pro-image 测试

## 为什么放在这里（而不是 `skills/seedream5pro-image/tests/`）

**放在技能目录里会被一起安装。** qwenpaw 安装技能时，`hub.py:_github_collect_tree_files()` 从
`SKILL.md` 所在目录**递归收集全部文件**（不看扩展名、没有排除名单），`_normalize_bundle()` 再把
`references/`、`scripts/` 以外的文件统统塞进 `extra_files` 兜底桶 —— 也就是说
`skills/seedream5pro-image/` 下新增的任何东西都会被打进四个安装目标。

更实际的理由：安装前的安全扫描有 **100 文件上限**（`scanner.py`，超出部分**根本不扫**）。
技能目录**当前已 109 个文件**，早就越过上限；再往里塞测试只会让未被扫描的盲区更大。
放在仓库根的 `tests/` 里，既不进安装包，也不占用扫描额度。

## 怎么跑

```bash
# 全跑（约 1~2 分钟）
bash tests/seedream5pro-image/run_all.sh

# 或单独跑
python3 tests/seedream5pro-image/verify_tags.py   # 标签引擎（纯函数，最快）
python3 tests/seedream5pro-image/verify_cli.py    # 四个子命令 + 生成记录 + 校验
python3 tests/seedream5pro-image/verify_mark.py   # mark 标记预览（像素级）
```

依赖：Python ≥3.11、Pillow（`pip install pillow`）。退出码非 0 表示有失败项。

## 三个套件覆盖什么

| 套件 | 覆盖 |
|------|------|
| `verify_tags.py` | 坐标标签的校验与换算：基本换算、**边界值口径**（网格标 `x=width`，校验就必须接受 `width`）、形态/格式校验（个数、小数、百分号、逗号、框写反、框宽高为 0）、**普通尖括号放行**（`<重点>`/`<checkbox>`/`<3>` 不该误杀文生图）、真坐标形态仍拦截、多图归属、对外文案不含「归一化」 |
| `verify_cli.py` | 四个生成子命令的**请求体**与 `run.json` 契约、生成记录（`ls`/`show`/`replay`）、**两个提示词口径**（`prompt` 像素 / `prompt_sent` 仅审计）、幽灵条目、失败也保存输入、参数校验、**图层拆分专属预检**、接口只回 `url` 的回退下载、`data:` URI 输入、底图尺寸异常降级、`run_id` 同秒不撞车、帮助文案与实际能力一致 |
| `verify_mark.py` | 网格默认开与画布几何、标记渲染与编号顺序（点选在前）、提交模式、输出格式由后缀决定、**分辨率自动降档**（真 2K 噪点图）、参考图超限、中文标签 |

## 设计原则

- **零成本**：`verify_cli.py` 起一个本地 mock HTTP 服务拦请求，**绝不调用真实接口**；
  另外两个套件完全不联网。
- **真跑**：CLI 用子进程启动，走真实参数解析、真实落盘、真实 `run.json` 组装 ——
  只在 HTTP 边界上换了 mock。
- **坏输入必须不发请求**：被本地校验拦下的用例都会断言「没有发出请求」且「没有留下任务目录」。
- **像素级断言**：`mark` 的检查不只看退出码，还会去量输出图里的留白与刻度区域。
- **体积行为要用噪点图测**：纯色图 PNG 压得极小，测不出「产物超 2MB 自动降档」这类行为。

## 已知未覆盖

- WebUI 已在 v3.0.0 移除，故无相关测试。
- 真实 API 的出图效果（画质、语义还原度）需要真跑，不在自动化范围内。
- `tests/*/work*/` 是运行时产物（临时图、mock 落盘、临时数据根），已被 `.gitignore` 忽略。
