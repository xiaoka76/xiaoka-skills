# Byted Web Search 文档索引

火山引擎豆包搜索（原名 联网搜索/融合信息搜索）API 文档，详见官网。本 skill 支持 **Custom / Global 双引擎**。

## 核心文档

| 文档 | 链接 |
|------|------|
| 联网搜索 API（主文档） | https://www.volcengine.com/docs/85508/1650263 |
| 豆包搜索产品简介（版本差异） | https://www.volcengine.com/docs/87772/2272949 |
| Custom 版 API 参考（默认引擎） | https://www.volcengine.com/docs/87772/2272953 |
| **Global 版 API 参考（--engine global）** | https://www.volcengine.com/docs/87772/2548026 |
| 产品计费 | https://www.volcengine.com/docs/87772/2272951 |
| 新功能发布记录 | https://www.volcengine.com/docs/87772/2272950 |

## 版本差异速查

| | Custom（默认） | Global（--engine global） |
|---|---|---|
| URL | `open.feedcoopapi.com/search_api/web_search` | `open.feedcoopapi.com/search_api/global_search` |
| 认证 | API Key 或 AK/SK TOP网关 | 仅 API Key（按量后付费） |
| 搜索类型 | 文搜文 / 文搜图 | 文搜文 / 文搜图 / 图搜图 visual |
| 免费额度 | 500次/月 | 500次/月（两版共用） |

## 控制台

| 用途 | 链接 |
|------|------|
| 新用户开通 | https://console.volcengine.com/search-infinity/web-search |
| API Key 管理 | https://console.volcengine.com/search-infinity/api-key |
| Agent Plan 控制台 | https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentPlan |
| Agent Plan 企业版控制台 | https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentEnterprise |

## 凭证说明

> ⚠️ 本 skill 仅支持联网搜索控制台或 Coding Plan 签发的 Key，其他来源 Key 不通用。

相关但凭证不通用的产品：[火山方舟联网搜索](https://www.volcengine.com/docs/82379/1756990)（Ark 工具）。
