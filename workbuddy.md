# WorkBuddy 开发上下文 · McOmni

本文件记录本项目在 **腾讯 WorkBuddy** 中的开发过程，用于核验「McOmni 确实使用 WorkBuddy 开发」并申请 WorkBuddy 专项积分奖励。

- 开发时间：2026-10-09
- 开发工具：腾讯 WorkBuddy（Agent 模式）
- 关联活动：麦当劳程序员创意开发大赛（M-CODE 1024）

---

## 1. 开发流程概览

| 阶段 | 在 WorkBuddy 中做的事 |
|---|---|
| 调研 | 抓取并阅读麦当劳官方大赛仓库（`M-China/mcd-developer-innovation-challenge`）的 README、活动规则、参赛声明、排行榜与全部报名 Issue，评估赛道饱和度 |
| 接入 | 将麦当劳 MCP（`https://mcp.mcd.cn`）配置为 WorkBuddy 自定义连接器并启用 |
| 验证 | 在 WorkBuddy 内直接调用 MCP 工具做真实验证（握手、工具枚举、账户、活动、券、门店、营养） |
| 开发 | 由 WorkBuddy 编写/改造 `scripts/mcd_cli.py`（多来源 Token 解析，提升可移植性）与全套交付文档 |
| 交付 | 由 WorkBuddy 生成 `README.md`、`MCP_INTEGRATION.md`、`mcp-config.example.json` 等参赛材料 |

---

## 2. WorkBuddy 中完成的真实 MCP 调用

以下调用均在 WorkBuddy 会话内通过连接器工具完成（真实请求，非构造）：

1. `now-time-info` —— 取得服务器时间基准（`GMT+08:00`），用于活动日期与预约判定；
2. `query-my-account` —— 读取积分账户字段（`availablePoint` / `accumulativePoint` / `currentMouthExpirePoint` …），确认「积分到期止损」链路成立；
3. `campaign-calendar` —— 拉取当月活动，确认活动雷达可用；
4. `available-coupons` —— 拉取麦麦省券（含已领取与可领取），确认领券链路可用；
5. `query-nearby-stores` —— 以 `{beType:1, searchType:2, city:"北京", keyword:"昌平"}` 实测门店查询，确认返回 `storeCode`、`distance` 与完整 `reservationTimeOptions`；
6. `mall-points-products` —— 以 `catRuleIds="1>6>20,1>6>21,1>6>22,1>6>34"` 拉取派对/体验营/读书会商品，取得可用 `spuId`；
7. `list-nutrition-foods` —— 拉取 160 条餐品营养记录，确认控卡配餐链路可用。

通过 WorkBuddy 的终端能力，还完成了：

- `initialize` 握手与 `tools/list` 枚举，确认服务端为 `mcd-mcp v1.0.0`、工具面 **35 个**；
- 用 `python scripts/mcd_cli.py list 积分` 验证命令行通道可用。

---

## 3. WorkBuddy 在本项目中承担的关键判断

1. **赛道分析**：WorkBuddy 拉取了官方仓库全部报名 Issue（70 条），指出「省钱/比价」与「营养/热量/健身」两类已高度饱和，建议差异化定位；
2. **合规核对**：WorkBuddy 从官方仓库**原样下载** `CONTEST_DECLARATION.md`（1522 字节，未改动），避免手写导致文件不合规；
3. **敏感信息处理**：识别出「Token 不得进入仓库」，因此 `mcp-config.example.json` 仅使用环境变量占位符 `${MCD_MCP_TOKEN}`；
4. **可移植性改造**：WorkBuddy 将 `mcd_cli.py` 的 Token 解析从「仅 WorkBuddy 配置路径」扩展为多来源（环境变量 / 指定配置文件 / WorkBuddy 默认路径 / 项目本地），使项目脱离 WorkBuddy 亦可独立运行；
5. **一致性校验**：WorkBuddy 反复核对了 `beType` / `orderType` / `beCode` / `takeWayCode` 的传递规则，并将其固化为 `SKILL.md` 的防错铁律。

---

## 4. 复现方式

在 WorkBuddy 中：

1. 打开左侧边栏【专家 · 技能 · 连接器】→【连接器】→ 右上角【自定义连接器】，配置并启用 `mcd-mcp`（配置内容见 `mcp-config.example.json`，替换为你自己的 Token）；
2. 将会话上下文指向本仓库，即可复现上述全部 MCP 调用；
3. 命令行通道：`python scripts/mcd_cli.py list`、`python scripts/mcd_cli.py call <tool> '<json>'`。

---

## 5. 说明

- 本文件为 WorkBuddy 开发过程的**对话上下文导出**，用于核验项目与 WorkBuddy 的关联；
- 文件中**不含任何真实 Token、密钥或账号凭证**；
- 本项目为麦当劳程序员创意开发大赛参赛作品，由参赛者独立开发，非麦当劳官方产品。
