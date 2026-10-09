---
name: mcdonalds
description: 麦当劳中国官方 MCP 全能助手。当用户提到麦当劳、麦乐送、开心乐园餐、麦麦省优惠券、领券、点麦当劳、外送到家、得来速、麦当劳积分、积分抽奖、积分商城兑换、麦当劳餐品热量/营养、麦当劳订单查询或取消、麦当劳周边玩具与活动时使用。覆盖官方 35 个工具的全部能力，内置领券、到店点餐、外送、玩具雷达、积分抽奖、热量计算、优惠计算器七大工作流。
agent_created: true
---

# 麦当劳 MCP 全能助手

通过麦当劳中国官方 MCP Server（`mcd-mcp` @ `https://mcp.mcd.cn`）为用户完成从领券、比价、点餐、外送到积分抽奖、营养计算的全流程。共 **35 个工具**，全部能力见 `references/tools.md`。

## 前置条件

1. `~/.workbuddy/mcp.json` 中需存在 `mcpServers.mcd-mcp`（含 `Authorization: Bearer <token>`）。Token 获取：https://open.mcd.cn/mcp
2. 该 MCP 需在「连接器管理」中点击**信任**后，工具才会出现在可用工具列表里。

## 两种调用通道

| 通道 | 适用 | 说明 |
|---|---|---|
| **A. 直接调用 MCP 工具**（首选） | MCP 已被信任 | 直接调用工具名，如 `query-meals`。参数严格按 `references/tools.md` |
| **B. 命令行脚本**（备选/排障） | MCP 未信任、或需在终端验证 | `python scripts/mcd_cli.py call <工具名> '<json>'`；`list` 列工具、`desc` 查参数 |

通道 B 示例：

```bash
python scripts/mcd_cli.py list 优惠
python scripts/mcd_cli.py call auto-bind-coupons
python scripts/mcd_cli.py call query-nearby-stores '{"beType":1,"searchType":1,"city":"北京"}'
```

## 通用铁律（违反会直接报错或下错单）

1. **`beType` 决定一切**：`1`=到店自取、`2`=麦乐送外送、`5`=得来速、`6`=企业团餐。
2. **`orderType`**：到店类（含自取 + 得来速）= `1`；外送类（含麦乐送 + 团餐）= `2`。
3. **`beCode` 与 `storeCode` 配对**：到店自取(`beType=1`)**不传** `beCode`；得来速从 `query-nearby-stores` 取；麦乐送/团餐从 `delivery-query-stores` 取。传错会报错。
4. **`query-nearby-stores.searchType` 必须传对**（实测坑）：
   - `searchType=1` 查**收藏餐厅**；该 `beType` 无收藏时返回 `600050 收藏餐厅列表为空`。到店自取(beType=1)通常有收藏店，得来速(beType=5)常为空。
   - `searchType=2` 按位置搜索，**必须 `city` 与 `keyword` 同时传**；只传其一必报 `600058 城市名或者关键词不能为空`。
   - 稳妥路径：先试 `searchType=1`，报 600050 则改用 `searchType=2` + `city` + `keyword`。
5. **菜单编码路径**：`query-meals` 的餐品编码在 **`data.categories[].meals[].code`**，详情在 `data.meals.{code}`（含 `name`/`currentPrice`/`originalPrice`）。
   ⚠️ **不要误取响应外层的 `code`**——那是业务状态码（`200`），不是餐品编码。
6. **绝不臆造编码**：`storeCode`、`beCode`、`addressId`、`productCode`、`couponId`、`skuId` 都必须来自上游工具返回，不得凭空生成。
7. **`reservationDate` 仅预约场景传**（格式 `yyyy-MM-dd HH:mm`），非预约**不要传**。门店返回 `reservation=true` 时，其 `reservationTimeOptions` 必须**完整展示**，缺项会导致用户无法预约。
8. **下单前必须 `calculate-price`**，把明细与总价展示给用户并取得明确确认，再调 `create-order`。禁止跳过算价直接下单。
9. **到店场景（`orderType=1`）下单必传 `takeWayCode`**，取值只能来自 `calculate-price` 返回的 `data.takeWayList[].code`（实测取值：`eat-in` / `take-in-store`）；外送/团餐（`orderType=2`）**不要传**（其算价返回**不含** `takeWayList`）。
10. **抽奖必须两段式**：先 `query-lottery-info` 展示 `drawDecision.nextConsumption`，用户明确确认后才可 `draw-lottery`。禁止试抽、自动抽、连续抽。
11. **业务成败看 `success` 字段**（仅适用于结构化返回）：工具调用不报错 ≠ 业务成功。响应 JSON 中 `success=false` 即失败（如 `60006 商品已售罄`、`600058 城市名为空`），须如实转述 `message`，不得改写或掩盖。
12. **返回有两种形态，别搞混**：
    - **结构化返回**（多数工具）：字段说明 + 原始 JSON，按字段取值。
    - **服务端已渲染的 Markdown**（实测 `available-coupons`、`query-my-coupons`、`campaign-calendar`）：**直接原样展示给用户**，不要试图解析字段、也没有 `success` 可判。空文本即视为无数据。
13. **点单前必须检查「口味 / 套餐选项」**：任何商品在算价/下单前都要用 `query-meal-detail` 看它有没有 `rounds`（选一/套餐组）或特制（modification）。**有选项就必须先让用户选**，不能默认带过——`rounds[].choices[].quantity=1` 的只是默认项，不代表用户已选。
14. **消耗性取舍不得替用户决定**：凡是「要不要多花积分 / 多下单 / 溢出到其他资产」这类取舍，必须把**每个方案的代价**（花多少、分别来自哪部分资产）摊开给用户，由用户拍板。脚本与 agent 只负责给方案，**不预设默认、不自行选择**。典型场景：抽奖是否「溢出」到非将过期积分。

## 七大核心工作流

### 0. 入口：先确认取餐方式（凡涉及门店 / 菜单 / 下单，都必须先走这一步）

**不要一上来就搜门店或菜单**。先问用户一句：

> 「你要怎么取餐？① 到店自取 ② 麦乐送外送 ③ 得来速（车道取餐）」

| 用户选择 | beType | 紧接着**必须先问** | 之后 |
|---|---|---|---|
| ① 到店自取 | `1` | **「你在哪儿？」**（城市 + 地标） | `query-nearby-stores(searchType=2, city, keyword)` → 按 `distance` 升序取最近 |
| ② 麦乐送外送 | `2` | **「用哪个配送地址？」** | `delivery-query-addresses` → 选中或新增地址 → `delivery-query-stores` |
| ③ 得来速 | `5` | **「你在哪儿？」**（开车去哪个区域） | `query-nearby-stores(searchType=2, city, keyword)`（`beType=5`） |

- **自取 / 得来速**：位置是必需输入 → 用「低成本问法」：先查 `order-list` 问「你现在是不是在常去那家 XX 店附近？」，答否再问「城市 + 地标」。
- **麦乐送**：**不要问「你在哪」** —— 由配送地址决定门店；没有地址就先问地址或帮用户新增。
- 门店菜单/玩具/活动等查询同理：先定取餐方式，再定门店，最后才取菜单。

### 1. 领券

触发：「帮我领券」「有什么优惠券」「领麦麦省的券」

```
available-coupons      → 展示当前可领取的券（名称/图片/状态/标签）
auto-bind-coupons      → 一键领取全部可领券（无入参）
query-my-coupons       → 查卡包已有券（page/pageSize）
```

> `query-my-coupons` 不校验门店与下单规则；要看「这家店这个订单能用的券」须用 `query-store-coupons`（见工作流 7）。

### 2. 点餐（到店自取 / 得来速）

```
# 前置：第 0 步已确认「自取 / 得来速」并问到位置
# ① 找店：用「城市 + 地标」搜（searchType=2），结果按 distance 升序，第一条即最近
query-nearby-stores {beType:1(自取)/5(得来速), searchType:2, city:"北京市", keyword:"长安小区"}
  → 取 storeCode；得来速(beType=5)另需 beCode
# ② 菜单：餐品编码在 data.categories[].meals[].code
query-meals {storeCode, orderType:1, beType}
query-meal-detail {storeCode, orderType:1, beType, code}    # 规格 / 特制 / 营养
# ③ 算价：返回 data.takeWayList[].code —— 下一步下单要用
calculate-price {storeCode, orderType:1, beType, items:[{productCode, quantity}]}
# ④ 下单：orderType=1 必带 takeWayCode
create-order {storeCode, orderType:1, beType, takeWayCode:"take-in-store", items:[...]}
```

> **不知道用户在哪儿 → 先问，而且用「低成本问法」**：
> ① 先查 `order-list` 历史订单（和收藏门店），统计**用户最常去的门店**，直接问：「你现在是不是在 XX 店附近？」
> ② 用户答否，再问「在哪个城市 + 附近哪个地标」，然后用 `searchType=2` + `city` + `keyword` 搜。
>
> `searchType=2` 返回**真实距离且结果按 `distance` 升序**，第一条即最近门店；`searchType=1`（收藏店）的 `distance` 恒为 `0`，不能用来判断远近。
> **keyword 取「具体地标」而非行政区名**（实测：`密云` 命中 0 家，`长安小区` 命中 5 家）。用户给详细地址时，剥出其中的小区名/地标名当 keyword。
> **不要猜位置、也不要声称自己知道用户在哪。**

### 3. 外送（麦乐送）

**前置**：第 0 步已确认取餐方式，且已问到**用哪个配送地址**（外送**不问「你在哪」**，由地址决定门店）。

```
delivery-query-addresses                    → 取 addressId（无地址则先 delivery-create-address）
delivery-query-stores (beType=2, addressId)  → 取 storeCode + beCode
query-meals (storeCode, beCode, orderType=2, beType=2)
calculate-price (addressId, storeCode, beCode, orderType=2, beType=2, items=[...])
create-order → 生成支付链接
```

配送进度：`query-order(orderId)`。详细字段示例见 `references/workflows.md`。

### 4. 周边玩具雷达

MCP **没有**独立「玩具」接口，这是**组合能力**，按下列顺序拼出玩具/周边上新情报：

```
campaign-calendar (specifiedDate=当月)     → 当月活动：主题派对、品鉴会、麦麦体验营等
mall-points-products (catRuleIds 含 "2>8")  → 积分商城「周边产品」类目
query-meals (门店菜单)                      → 找含玩具的套餐（开心乐园餐等）
query-promotions (仅团餐门店)               → 门店满减/折扣规则
```

输出建议：**玩具/周边 × 获取途径 × 时间窗** 三列表。若接口未返回玩具字段，如实说明「本期接口未返回玩具信息」，不要编造款式名称。

### 5. 积分抽奖

```
query-my-account      → 积分余额（可选，用于展示）
query-lottery-info    → 活动名/状态/单次消耗 drawPoint/剩余次数/奖品列表/drawDecision
   ↓ 必须展示 drawDecision.nextConsumption 并获用户明确确认
draw-lottery          → 抽奖（服务端原子扣减）
query-my-prizes       → 我的奖品（pageNum/pageSize）
```

> `drawDecision.resourceEligible=false` 时**禁止**调用 `draw-lottery`。返回「操作太频繁」时如实转述，不要重试。

#### 5.1 到期止损：一键用「即将过期积分」抽奖

触发：「用快过期的积分抽奖」「别让积分白白过期」「把将过期积分花掉」

```
query-my-account    → currentMouthExpirePoint（本月将过期）、availablePoint
query-lottery-info  → drawPoint（单次消耗）、drawDecision
可抽次数 N = floor(currentMouthExpirePoint / drawPoint)
   ↓ 展示「抽 N 次、消耗 X 分、剩余 Y 分仍会过期」并获确认
draw-lottery × N    → 逐次执行，间隔 ≥1s；遇限流/失败立即停止，不重试
```

现成脚本（推荐直接用）：

```bash
python scripts/points_expiry_draw.py                                     # dry-run：摊开「不溢出 / 溢出」两方案
python scripts/points_expiry_draw.py --yes                               # 执行「不溢出」方案
python scripts/points_expiry_draw.py --yes --times 12 --allow-overflow   # 用户同意溢出后才可执行
```

**是否溢出由用户决定**（见铁律 14）：脚本默认只花将过期积分；`--times` 超出可覆盖次数时必须再加 `--allow-overflow`，否则以退出码 2 拒绝；将过期积分不足一次消耗时只提示「可改用其他积分」，不自行执行。

> **扣减顺序（实测）**：**先扣将过期积分，不足部分才从其他积分扣**。
> 例：将过期 17.1 + 抽 1 次（24 分）→ 17.1 来自将过期、6.9 来自其他积分，抽后 `currentMouthExpirePoint` 归 0。
> 故「溢出」= **总消耗 > 将过期积分**（超 1 分也算）；拆分按**金额** `min(总消耗, 将过期积分)`，**不是**按次数取整。
> `draw-lottery` 结果在 **`data` 层下**：`data.status.code`（`SUCCESS` 才算成功）、`data.win`、`data.prizes[]`（含 `name`/`validDateInfo`）、`data.consumePoint`。
> ⚠️ **不是顶层 `status`** —— 按顶层读会把「已中奖」误判为失败并中断（实测踩过）。

### 6. 热量计算

```
list-nutrition-foods        → 全量营养成分（能量/蛋白质/脂肪/碳水/钠/钙）（无入参）
query-meal-detail           → 单个餐品详情（含营养）
```

按用户目标（减脂/增肌/总热量上限）组合餐品，输出**热量-蛋白质-脂肪-碳水**表格并给出总热量。餐品缺失营养数据时标注「接口未提供」，不要估算填充。

### 7. 优惠计算器

目标：算出「用券 vs 不用券」哪个更省。

```
query-store-coupons (storeCode, orderType, beCode?, reservationDate?)  → 该店该场景可用券
   ↓ 取候选券的 couponId / couponCode
calculate-price (items=[{productCode, quantity, couponId?, couponCode?}])  → 逐方案算价
```

至少输出两组结果（不用券 / 用最优券）对比，标注节省金额。`available-coupons` 用于发现新券，`auto-bind-coupons` 补齐后再比价效果最佳。

## 扩展能力（MCP 中已有，按需使用）

| 场景 | 工具链 |
|---|---|
| **积分商城兑换** | `mall-points-products` → `mall-product-detail`(选 skuId) → `mall-create-order`（虚拟券/实物，`spuCategory=1/2`）。多商品**必须分别下单并排队** |
| **商城订单** | `mall-order-list` / `mall-order-detail` |
| **订单管理** | `order-list`（历史）/ `query-order`（详情、配送进度）/ `cancel-order`（需 `cancelReasonCode`） |
| **派对 / 活动预约** | `query-party-city` → `query-party-store` → `query-party-store-date` → `query-party-store-session` → `party-order-create`（生日派对、主题派对、麦麦体验营、品鉴会、读书会、积分兑换活动） |
| **企业团餐** | `delivery-query-stores(beType=6)` → `query-meals` → `query-meal-assistance`(取 `gmServiceCode`) → `query-promotions` → `calculate-price` → `create-order` |
| **满意度奖券** | `query-survey-coupon(orderId)` |
| **时间基准** | `now-time-info`（判断活动日期、预约时间前先取服务器时间） |

## 常见触发 → 工作流对照

| 用户说 | 走 |
|---|---|
| 「帮我领券」「有什么优惠」 | 工作流 1 |
| 「点个麦当劳」「到店取」 | 工作流 2 |
| 「叫个麦乐送」「送到家」 | 工作流 3 |
| 「有没有新玩具」「开心乐园餐送什么」 | 工作流 4 |
| 「积分抽奖」「抽一次」 | 工作流 5 |
| 「这个多少卡」「帮我配个 500 大卡」 | 工作流 6 |
| 「怎么买最划算」「有券便宜多少」 | 工作流 7 |
| 「我的积分」「兑换券」 | 扩展 · 积分商城 |
| 「订单到哪了」「取消订单」 | 扩展 · 订单管理 |

## 参考资源

- `references/tools.md` —— **35 个工具**完整参数手册（含 enum、必填、原始描述）
- `references/workflows.md` —— 外送/点餐/团餐的字段级示例与 `items` 数组构造
- `scripts/mcd_cli.py` —— 零依赖命令行调用器（`list` / `desc` / `call` / `raw`）
- `scripts/points_expiry_draw.py` —— **积分到期止损**：一键用将过期积分抽奖（dry-run / `--yes` / `--times N` / `--allow-overflow` / `--interval`）；**是否溢出由用户决定**

## 排障

| 现象 | 处理 |
|---|---|
| 工具不在可用列表 | 到「连接器管理」信任 `mcd-mcp`；或用通道 B 脚本 |
| 401 / 无工具返回 | Token 失效，重新到 open.mcd.cn/mcp 激活 |
| 502 / 连接失败 | 多为代理拦截，脚本已默认绕过代理；确认 `MCD_MCP_URL` 未被改写 |
| 「操作太频繁」 | 抽奖频控，如实告知用户稍后再试，不要重试 |
| 菜单查不到某商品 | 促销品用 `query-meals` 全量兜底，`query-meal-detail` 可能取不到 |
