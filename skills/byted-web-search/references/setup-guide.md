# Byted Web Search — 开通与配置

**开箱即用**：注册 → 开通 → 拿 Key → **直接在聊天框把 Key 发给我**（无需编辑配置）→ 完成，后续机器人自动操作。

## 1. 注册

https://www.volcengine.com → 注册（手机/飞书/抖音）→ 实名认证

## 2. 开通

[联网搜索开通](https://console.volcengine.com/search-infinity/web-search) →【正式开通】
用户每月都会自动获得500次免费使用额度。

## 3. 获取凭证

**方式 A（推荐）**：[API Key 管理](https://console.volcengine.com/search-infinity/api-key) →【创建 API Key】→ 复制保存

**方式 B（AK/SK）**：控制台头像 → API 访问密钥 → 创建。需配置 `VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`。SK 仅显示一次，请及时保存。子账号需授权 `TorchlightApiFullAccess`。

**方式 C（Coding Plan）**[Agent Plan 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentPlan)（coding plan企业用户[Agent Plan企业版控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentEnterprise)）→【使用配置-配置Harness】→【联网搜索】→点击【查看API Key】 → 复制 API Key

## 4. 配置（把 Key 交给 Claw）

**优先**：拿 Key 后直接在聊天框发给我即可，无需编辑任何配置文件。

**或** 在 Claw 技能/凭证配置中填写 `WEB_SEARCH_API_KEY`：
- **OpenClaw**：编辑 `~/.openclaw/openclaw.json`，在 `skills.entries` 下添加：
  ```json
  "byted-web-search": {
    "enabled": true,
    "env": { "WEB_SEARCH_API_KEY": "您复制的Key" }
  }
  ```
- **其他 Claw**：在技能配置界面填写 `WEB_SEARCH_API_KEY` 即可

**本地使用**：skill 根目录创建 `.env`（内容 `WEB_SEARCH_API_KEY=your_key`），或 `export WEB_SEARCH_API_KEY="..."` 写入 ~/.bashrc。

## 5. 计费与认证（双引擎）

| | Custom | Global |
|---|---|---|
| 认证 | API Key **或** AK/SK | **仅 API Key** |
| 计费 | 按量 + 订阅套餐 | **仅按量后付费** |
| 免费额度 | 500次/月 | 500次/月（两版**共用**） |

**⚠️ Global 版 Key 要求**：必须使用[控制台「按量后付费」tab](https://console.volcengine.com/search-infinity/api-key?tab=post_paid)创建的 API Key；订阅套餐/Agent Plan 签发的 Key 调 Global 会报 `700901 invalid_api_key`。同一个 `WEB_SEARCH_API_KEY` 只要来自按量后付费 tab，两版通用。

## 6. 验证

```bash
python3 scripts/web_search.py "北京今日天气"
```

## 常见问题

| 问题 | 解答 |
|------|------|
| SK 忘了 | 无法找回，删除旧密钥重建 |
| 权限错误 | 检查已开通、子账号已授权 TorchlightApiFullAccess |
| 额度用完 | 正式开通后按量计费 |
| 欠费 | 后付费 24h 内充值可恢复 |
| 403 | 检查开通状态与账户 |

> 运行时错误（错误码/限流/凭证无效等）由 `web_search.py` 直接输出处理办法，无需查阅本文档。
