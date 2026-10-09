<div align="center">

# 麦麦全能助手 · McOmni

**一句话，搞定吃麦全流程**

领券 → 选店 → 配餐 → 比价 → 下单 → 派对预约 → 积分止损

[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-blue)](https://open.mcd.cn/mcp)
[![Tools](https://img.shields.io/badge/MCP%20Tools-35%20%2F%2035-success)](#能力总览)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)](#快速开始)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

基于**麦当劳中国官方 MCP Server**（`mcd-mcp` @ `https://mcp.mcd.cn`）构建的全能助手 Skill。

</div>

> **关于徽章**：图片来自 shields.io，个别网络环境下可能加载较慢。README 的全部信息在正文中都有文字说明，徽章缺失不影响阅读。

---

## 目录

- [它解决什么问题](#它解决什么问题)
- [能力总览](#能力总览)
- [快速开始](#快速开始)
- [七大核心工作流](#七大核心工作流)
- [为什么它靠谱](#为什么它靠谱)
- [项目结构](#项目结构)
- [排障速查](#排障速查)
- [安全与边界](#安全与边界)

---

## 它解决什么问题

麦当劳把 **35 个能力**开放给了 AI。但在真实账号上跑一遍就会知道：**能调用 ≠ 会用**。

```text
用户：想点个麦当劳
  └─ 怎么取餐？    到店自取 / 麦乐送 / 得来速
       └─ 去哪家店？   query-nearby-stores  →  storeCode (+ beCode)
            └─ 吃什么？  query-meals        →  productCode
                 └─ 多少钱？ calculate-price →  takeWayCode
                      └─ 下单  create-order  →  orderId

每一环都必须来自上一环的返回值；中间任何一环猜错，订单就下不出去。
```

同时还要管住三件事：**① `beType` / `orderType` 的组合**（决定取餐方式）、**② 有副作用的操作不能误触发**（下单 / 领券 / 抽奖）、**③ 花积分类的取舍不能替用户拍板**。

McOmni 的价值不在"能调用工具"，而在**知道什么时候不该调用**——它把踩过的坑固化成硬约束，让 AI 在你的真实账号上安全地跑完整个流程。

---

## 能力总览

**35 / 35 工具全覆盖**，不只是检索类接口。

| 分组 | 数量 | 代表能力 |
|---|:--:|---|
| 活动与优惠 | 4 | 当月活动日历、可领券、一键领券、我的券 |
| 到店点餐 | 7 | 门店查询、菜单、详情、算价、下单、取消、订单详情 |
| 麦乐送外送 | 3 | 地址管理、可配送门店 |
| 积分与商城 | 7 | 积分账户、抽奖、奖品、商城兑换、商城订单 |
| 营养数据 | 2 | 160+ 条餐品营养（能量 / 蛋白 / 脂肪 / 碳水 / 钠 / 钙）|
| 派对与活动预约 | 5 | 城市 → 门店 → 日期 → 场次 → 下单 |
| 企业团餐 | 3 | 团餐门店、助餐服务、促销规则 |
| 其他 | 4 | 服务器时间、历史订单、满意度奖券、门店级用券 |

三种取餐方式全部支持：**到店自取** / **麦乐送外送** / **得来速车道取餐**。

---

## 快速开始

### 第 1 步 · 拿 Token

访问 <https://open.mcd.cn/mcp>，手机号登录 → 控制台 → 激活，一键复制 Token。

### 第 2 步 · 让助手能用上它

**方式 A：作为 WorkBuddy Skill（推荐）**

```bash
cp -r . ~/.workbuddy/skills/mcdonalds
```

然后在「连接器 → 自定义连接器」中填入配置（参考 `mcp-config.example.json`），把 `${MCD_MCP_TOKEN}` 换成你自己的 Token。

**方式 B：只用命令行通道（不需要任何 AI 客户端）**

```bash
export MCD_MCP_TOKEN=<你的Token>
python scripts/mcd_cli.py list 优惠

# 找门店（searchType=2 按位置搜，city 与 keyword 必须同时传）
python scripts/mcd_cli.py call query-nearby-stores \
  '{"beType":1,"searchType":2,"city":"北京市","keyword":"鼓楼南街"}'
```

Token 解析顺序（任选其一即可）：

| 顺序 | 来源 |
|:--:|---|
| 1 | 环境变量 `MCD_MCP_TOKEN` |
| 2 | 环境变量 `MCD_MCP_CONFIG` 指向的 JSON 文件 |
| 3 | `~/.workbuddy/mcp.json` |
| 4 | 项目根目录 / 当前目录下的 `mcp.json` |

### 第 3 步 · 用起来

```bash
# 看有什么券，然后一键领掉
python scripts/mcd_cli.py call available-coupons
python scripts/mcd_cli.py call auto-bind-coupons

# 积分快过期了？先 dry-run 看方案，再决定花不花
python scripts/points_expiry_draw.py
```

---

## 七大核心工作流

| # | 工作流 | 工具链 |
|:--:|---|---|
| 0 | **入口 · 确认取餐方式** | 先问「到店自取 / 麦乐送 / 得来速」，再决定后续全部参数 |
| 1 | **领券** | `available-coupons` → `auto-bind-coupons` → `query-my-coupons` |
| 2 | **点餐（到店 / 得来速）** | `query-nearby-stores` → `query-meals` → `query-meal-detail` → `calculate-price` → `create-order` |
| 3 | **外送（麦乐送）** | `delivery-query-addresses` → `delivery-query-stores` → `query-meals` → `calculate-price` → `create-order` |
| 4 | **周边玩具雷达** | `campaign-calendar` + `mall-points-products(2>8)` + `query-meals` 组合拼出 |
| 5 | **积分抽奖 / 到期止损** | `query-my-account` → `query-lottery-info` → `draw-lottery` → `query-my-prizes` |
| 6 | **热量计算** | `list-nutrition-foods` / `query-meal-detail` |
| 7 | **优惠计算器** | `query-store-coupons` → `calculate-price`（用券 / 不用券 两组对比）|

> 工作流 4 需要特别说明：MCP **没有**原生"玩具"接口，这是**组合能力**。若接口未返回玩具字段，助手会如实说明「本期接口未返回玩具信息」，**不会编造款式**。

---

## 为什么它靠谱

### 14 条防错铁律（节选）

| # | 规则 | 不遵守的后果 |
|:--:|---|---|
| 1 | `beType` 决定一切（1 自取 / 2 麦乐送 / 5 得来速 / 6 团餐）| 取餐方式错乱 |
| 2 | `orderType`：到店类 = 1，外送类 = 2 | 下单到错误渠道 |
| 3 | 到店自取**不传** `beCode`；得来速 / 外送**必传** | 直接报错 |
| 4 | 菜单编码取 `data.categories[].meals[].code` | 会误取外层状态码 `200` |
| 5 | 到店下单**必传** `takeWayCode`，只能来自 `calculate-price` | 下单失败 |
| 6 | `searchType=2` 必须 `city` + `keyword` **同时传** | 报 `600058` |
| 7 | **绝不臆造编码**，一切 code 来自上游返回 | 下单到不存在的商品 |
| 8 | 下单前**必须**算价并让用户确认 | 花冤枉钱 |
| 9 | 抽奖**两段式**：先看 `drawDecision` 再执行 | 误消耗积分 |
| 10 | 判定成败看 `success` 字段，而非是否报错 | 把失败当成功 |

完整 14 条见 [`SKILL.md`](SKILL.md)。

### 三条设计原则

```text
① 绝不臆造编码      一切 code 必须来自上游工具的返回值
② 副作用必二次确认   下单前必算价；抽奖前必展示消耗明细
③ 消耗性取舍交用户   不替用户决定花多少积分、要不要溢出
```

### 积分到期止损：一个具体例子

麦当劳积分会过期。实测扣减顺序是 **先扣将过期积分，不足才从其他积分扣**，所以：

```text
「是否溢出」 = 总消耗 > 「本月将过期积分」   （超出 1 分也算溢出）
```

```bash
python scripts/points_expiry_draw.py                          # 默认 dry-run，列出两套方案的代价
python scripts/points_expiry_draw.py --yes                    # 只花将过期积分
python scripts/points_expiry_draw.py --yes --allow-overflow   # 用户明确同意后才可溢出
```

不加 `--allow-overflow` 时、若会溢出，脚本**以退出码 2 拒绝执行**——把决定权留给你，而不是"帮你想开一点"。

---

## 项目结构

```text
.
├── SKILL.md                     # 主文件：14 条铁律 + 7 大工作流 + 触发对照表
├── README.md
├── MCP_INTEGRATION.md           # 实际使用的 Server / Tool / 调用流程 / 业务价值
├── CONTEST_DECLARATION.md       # 参赛声明（官方原文件，未改动）
├── mcp-config.example.json      # 脱敏配置示例（仅环境变量占位符）
├── LICENSE
├── scripts/
│   ├── mcd_cli.py               # 零依赖 MCP 命令行通道（list / desc / call / raw）
│   └── points_expiry_draw.py    # 积分到期止损（dry-run / --yes / --allow-overflow）
└── references/
    ├── tools.md                 # 35 个工具完整参数手册
    └── workflows.md             # 字段级示例与 items 数组构造
```

---

## 排障速查

| 现象 | 原因与处理 |
|---|---|
| 工具不在可用列表里 | MCP 未信任。到「连接器管理」信任 `mcd-mcp`；或改用 `scripts/mcd_cli.py` |
| `401` / 无工具返回 | Token 失效，到 <https://open.mcd.cn/mcp> 重新激活 |
| `502` / 连接失败 | 多为系统代理拦截；`mcd_cli.py` 已默认绕过代理 |
| 报 `600050` | 该 `beType` 无收藏餐厅 → 改用 `searchType=2` + `city` + `keyword` |
| 报 `600058` | `searchType=2` 时 `city` 或 `keyword` 为空 |
| 「操作太频繁」 | 抽奖频控，稍后再试，**不要重试轰炸** |
| 菜单查不到某商品 | 促销品用 `query-meals` 全量兜底，`query-meal-detail` 可能取不到 |

---

## 安全与边界

- **Token 即身份**：本项目**不保存、不打印**你的 Token。仓库中只保留 `mcp-config.example.json` 占位符示例，**不包含任何真实凭证**。
- **有副作用的操作需明确确认**：下单、领券、抽奖、兑换均需用户确认后才执行。
- **本项目非麦当劳官方产品**。餐品信息、价格与供应状态**以麦当劳官方渠道的实时结果为准**；项目输出仅供参考。

---

## 参与的活动

本项目为「**麦当劳程序员创意开发大赛（M-CODE 1024）**」参赛作品，由参赛者独立开发。

开发过程使用 **腾讯 WorkBuddy**，完整对话上下文见 [`workbuddy.md`](workbuddy.md)。

## License

[MIT](LICENSE)
