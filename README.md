# 麦麦全能助手 · McOmni

> 一句话，搞定吃麦全流程：领券 → 选店 → 配餐 → 比价 → 下单 → 预约派对 → 积分止损。

基于**麦当劳中国官方 MCP Server**（`mcd-mcp` @ `https://mcp.mcd.cn`）构建的全能助手 Skill，**完整覆盖官方 35 个工具**，内置 **7 条核心工作流** 与 **14 条防错铁律**，另附一个**零第三方依赖**的命令行通道，在 AI 客户端不可用时也能照常干活。

[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-blue)](https://open.mcd.cn/mcp)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](#)

---

## 它解决什么问题

麦当劳把 35 个能力开放给了 AI，但**能调 ≠ 会用**：

- 工具之间**强依赖**：`storeCode` / `beCode` / `takeWayCode` 拿错一个就下单失败；
- 参数**易混淆**：`beType` 与 `orderType` 组合错一步，取餐方式就变味；
- **有副作用**的操作（下单、领券、抽奖）一旦误触发，钱和积分就真花了。

McOmni 的价值不在"能调用工具"，而在**知道什么时候不该调用**——它把踩过的坑固化成规则，让 AI 在真实账号上安全地跑完整个流程。

---

## 差异化亮点

| 亮点 | 说明 |
|---|---|
| **35 / 35 工具全覆盖** | 不只是检索类工具，连订单取消、商城兑换、派对预约、企业团餐、满意度奖券都覆盖 |
| **14 条防错铁律** | 把实测踩过的坑写成硬约束（如"到店下单必传 `takeWayCode`，取值只能来自 `calculate-price`"）|
| **双调用通道** | 通道 A 直连 MCP 工具；通道 B 零依赖 Python CLI，MCP 未授权 / 客户端不支持时兜底 |
| **积分到期止损** | 自动算出"本月将过期积分能抽几次"，并**把"是否溢出到其他积分"的代价摊开**由用户拍板 |
| **消耗性操作二次确认** | 下单前必算价、抽奖前必展示 `drawDecision`，绝不替用户花钱 |
| **不编造编码** | 所有 `storeCode`/`beCode`/`productCode` 必须来自上游返回，杜绝臆造 |

---

## 前置条件

1. 申请麦当劳 MCP Token：访问 <https://open.mcd.cn/mcp>，手机号登录后在「控制台」激活 Token。
2. 该 MCP 需在 WorkBuddy 的「连接器管理 → 自定义连接器」中被**启用/信任**后，工具才会出现在可用列表里。

---

## 安装

### 方式一：作为 WorkBuddy Skill（推荐）

```bash
# 复制到用户级 Skills 目录（所有项目可用）
cp -r . ~/.workbuddy/skills/mcdonalds
```

然后在 WorkBuddy 中配置连接器（填入你自己的 Token）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer <你的Token>" }
    }
  }
}
```

### 方式二：仅用命令行通道（不需要 AI 客户端）

```bash
export MCD_MCP_TOKEN=<你的Token>
python scripts/mcd_cli.py list 优惠
```

Token 解析顺序（任选其一即可）：

1. 环境变量 `MCD_MCP_TOKEN`
2. 环境变量 `MCD_MCP_CONFIG` 指向的 JSON 文件
3. `~/.workbuddy/mcp.json`
4. 项目根目录 / 当前目录下的 `mcp.json`

---

## 快速开始

```bash
# 1. 看看有什么券可领，然后一键领掉
python scripts/mcd_cli.py call available-coupons
python scripts/mcd_cli.py call auto-bind-coupons

# 2. 找附近门店（searchType=2 按位置搜，city 与 keyword 必须同时传）
python scripts/mcd_cli.py call query-nearby-stores \
  '{"beType":1,"searchType":2,"city":"北京市","keyword":"鼓楼南街"}'

# 3. 查营养，配一份控卡套餐
python scripts/mcd_cli.py call list-nutrition-foods

# 4. 积分快过期了？先 dry-run 看看方案，再决定要不要花
python scripts/points_expiry_draw.py
```

---

## 七大核心工作流

| # | 工作流 | 工具链 |
|---|---|---|
| 0 | **入口：确认取餐方式** | 先问「到店自取 / 麦乐送 / 得来速」，再决定后续全部参数 |
| 1 | **领券** | `available-coupons` → `auto-bind-coupons` → `query-my-coupons` |
| 2 | **点餐（到店 / 得来速）** | `query-nearby-stores` → `query-meals` → `query-meal-detail` → `calculate-price` → `create-order` |
| 3 | **外送（麦乐送）** | `delivery-query-addresses` → `delivery-query-stores` → `query-meals` → `calculate-price` → `create-order` |
| 4 | **周边玩具雷达** | `campaign-calendar` + `mall-points-products(2>8)` + `query-meals` 组合拼出（MCP 无原生玩具接口）|
| 5 | **积分抽奖 / 到期止损** | `query-my-account` → `query-lottery-info` → `draw-lottery` → `query-my-prizes` |
| 6 | **热量计算** | `list-nutrition-foods` / `query-meal-detail` |
| 7 | **优惠计算器** | `query-store-coupons` → `calculate-price`（用券 / 不用券 两组对比）|

扩展能力：积分商城兑换、商城订单、订单管理（查询/取消/配送进度）、派对与活动预约、企业团餐、满意度奖券。

---

## 项目结构

```
.
├── SKILL.md                     # Skill 主文件：铁律 + 7 大工作流 + 触发对照表
├── README.md                    # 本文件
├── MCP_INTEGRATION.md           # 实际用到的 Server / Tool / 调用流程 / 业务价值
├── CONTEST_DECLARATION.md       # 参赛声明（官方原文件，未改动）
├── mcp-config.example.json      # 脱敏配置示例（仅环境变量占位符）
├── scripts/
│   ├── mcd_cli.py               # 零依赖 MCP 命令行通道（list / desc / call / raw）
│   └── points_expiry_draw.py    # 积分到期止损（dry-run / --yes / --allow-overflow）
└── references/
    ├── tools.md                 # 35 个工具完整参数手册
    └── workflows.md             # 字段级示例与 items 数组构造
```

---

## 安全与边界

- **Token 即身份**：本项目**不会**保存或打印你的 Token；请在本地通过环境变量或本地配置文件提供。仓库中仅保留 `mcp-config.example.json` 占位符示例。
- **有副作用的操作需明确确认**：下单、领券、抽奖、兑换均需用户确认后才执行；脚本默认 `dry-run`。
- 本项目非麦当劳官方产品，餐品信息、价格与供应状态**以麦当劳官方渠道实时结果为准**。

---

## 目标用户

- **高频吃麦党**：想用一句话完成领券 + 点单 + 比价，而不是在 App 里点十几下；
- **AI Agent 开发者**：想了解如何把 35 个强依赖工具编排成可靠工作流，可直接参考 `SKILL.md` 的铁律与工具链；
- **积分/优惠敏感用户**：需要把"即将过期的积分"和"哪张券更省"算清楚的人。

---

## License

MIT

> 本项目为「麦当劳程序员创意开发大赛」参赛作品，由参赛者独立开发。
