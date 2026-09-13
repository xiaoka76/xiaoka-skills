# byted-web-search v1.4.4

火山引擎豆包搜索 API Skill，适用于 Claw / OpenClaw Agent。支持 **Custom / Global 双引擎**。

## 目录结构

```
byted-web-search-v1.4.4/
├── SKILL.md                  # Agent 运行时指令（主文件，精简版）
├── references/
│   ├── setup-guide.md        # 开通、配置与计费（凭证/双引擎认证/免费额度）
│   └── docs-index.md         # 官方文档 & 控制台链接索引
├── scripts/
│   └── web_search.py         # 搜索脚本（内置全部错误处理/首次回复/充值引导）
├── LICENSE                   # Apache 2.0
└── README.md                 # 本文件
```

## 快速开始

1. 将本目录放入 Claw 技能目录
2. 获取 API Key：[联网搜索控制台](https://console.volcengine.com/search-infinity/api-key) 或 [Agent Plan  控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentPlan)以及[Agent Plan 企业版控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentEnterprise)
3. 在聊天框直接发送 Key 给 Agent 即可

## v1.4.4 变更（错误处理全部内置 CLI，文档精简）

- **CLI**：`web_search.py` 内置全部错误处理——ERROR_HINTS 错误码→处理办法（14 条，额度类附完整充值引导）、缺凭证时输出完整首次回复模板（可直接复制给用户）、403/未授权错误从响应体解析错误码输出提示；移除所有"详见 references"的文档指引
- **删除**：`references/troubleshooting.md`（错误码表 CLI 已内置）、`references/no-credential-reply.md`（首次回复模板并入 CLI）
- **精简**：`docs-index.md` 删旧故障表；`setup-guide.md` 常见问题删除错误码条目（运行时错误由 CLI 输出）
- **SKILL.md**：第 2/7 节改为「直接看 `web_search.py` 输出即可」，不引导 agent 读额外文档（避免污染上下文/耗 token）

## v1.4.3 变更（进一步精简主文档）

- **author**：`volcengine-search-team` → `银狼 (silver-wolf)`
- **description**：去掉 API Key / 双引擎描述（属实现细节，description 只用于路由注入）
- **删除**：`# Byted Web Search` 凭证获取段落（移入 setup-guide）、「路由」章节（description 已承担路由职责）、实测结论对比表（只留结论）
- **移动**：双引擎认证/计费/免费额度、Global 按量后付费 Key 要求 → `references/setup-guide.md` 第 5 节
- **重排**：SKILL.md 章节连续编号（0-7）

## v1.4.2 变更（精简 SKILL.md，低频内容移 references/）

- **精简**：SKILL.md 从 283 行 → 206 行（-27% token），只保留正常调用必用内容（路由/核心身份/搜索策略/参数）
- **新增**：`references/no-credential-reply.md`（缺凭证首次回复模板，触发时读）、`references/troubleshooting.md`（错误码速查+充值引导）
- **删除**：行为固化（长期搜索习惯）章节——记忆管理属 Agent 框架职责，非搜索技能职责，触发率极低，整体移除
- **改动**：SKILL.md 第 3/9 节改为简短指引 + 指向对应 references 文件；第 10 节充值引导并入 troubleshooting.md

## v1.4.1 变更（实测结论入文档）

- **文档**：SKILL.md 新增「实测结论」——4 组文搜文 + 1 组图搜图双引擎实测对比（中文日常/英文新闻/中文科技/英文技术/图搜图），明确 Custom=中文生态、Global=全球生态，附给 Agent 的选择依据

## v1.4.0 变更（新增 Global 版双引擎）

- **新增**：`--engine global` 切换豆包搜索 Global 版（全球站点覆盖、摘要长度可调）
- **新增**：图搜图 `--type visual`（支持 `--image-url` / `--image-base64` / `--image-file` / `--roi` 感兴趣区域）
- **新增**：Global 版参数 `--max-snippet-length` / `--max-image-count` / `--icp-host-only` / `--enable-waiting` / 文搜图 `--short-edge-min/max` / `--aspect-ratio-min/max`
- **认证**：Global 版仅支持 API Key（按量后付费 Key），Custom 版保持 API Key / AK/SK 双通道
- **文档**：SKILL.md 增加双引擎选择章节，docs-index.md 补 Global 版文档入口

## v1.3.3 变更（基于 v1.3.2）

- **修正**：`--time-range` 支持自定义日期区间 `YYYY-MM-DD..YYYY-MM-DD`（脚本已支持，文档原缺失）
- **优化**：自然语言→参数映射示例增加时间区间场景
- **精简**：SKILL.md 与 references/ 去重，总上下文减少 26%
- **修正**：环境变量名统一为 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`
- **修正**：Key 来源提示统一为「其他来源 Key 不通用」
- **新增**：Coding Plan 控制台获取凭证路径
- **架构**：SKILL.md 为运行时指令，references/ 为补充参考文档，分离关注点

## 许可证

Apache License 2.0
