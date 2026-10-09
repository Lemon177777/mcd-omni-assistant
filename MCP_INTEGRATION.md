# MCP 集成说明 · McOmni

本文说明 McOmni **实际使用**的麦当劳 MCP Server、Tool、调用流程与业务价值。所有请求/响应均为**真实调用**记录（个人信息已脱敏）。

---

## 1. 接入信息

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp` |
| 端点 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（**不支持 WebSocket**） |
| 认证方式 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| 协议版本 | `2024-11-05` |
| Token 申请 | <https://open.mcd.cn/mcp>（手机号登录 → 控制台 → 激活） |

握手实测（`initialize`）：

```json
{"jsonrpc":"2.0","id":1,"result":{"capabilities":{"tools":{}},
 "protocolVersion":"2024-11-05","serverInfo":{"name":"mcd-mcp","version":"1.0.0"}}}
```

`tools/list` 实测返回 **35 个工具**。

---

## 2. 使用的 Tool（35 / 35 全覆盖）

### 2.1 活动与优惠（4）

| Tool | 用途 |
|---|---|
| `campaign-calendar` | 当月营销活动日历（进行中 / 往期 / 未来），支持 `specifiedDate` 锚点 |
| `available-coupons` | 麦麦省可领取券列表 |
| `auto-bind-coupons` | 一键领取全部可领券（无入参） |
| `query-my-coupons` | 卡包已有券资产 |

### 2.2 到店点餐链路（7）

| Tool | 用途 |
|---|---|
| `query-nearby-stores` | 到店/得来速门店查询（`searchType=1` 收藏、`=2` 按位置） |
| `query-meals` | 门店餐品列表 |
| `query-meal-detail` | 餐品详情（规格 `rounds` / 特制 / 营养） |
| `calculate-price` | 算价（返回 `takeWayList` 供下单使用） |
| `create-order` | 创建订单（到店需 `takeWayCode`） |
| `cancel-order` | 取消订单 |
| `query-order` | 订单详情 / 配送进度 |

### 2.3 麦乐送外送链路（3）

| Tool | 用途 |
|---|---|
| `delivery-query-addresses` | 配送地址列表 |
| `delivery-create-address` | 新增配送地址 |
| `delivery-query-stores` | 按 `addressId` 查可配送门店 |

### 2.4 积分与商城（7）

| Tool | 用途 |
|---|---|
| `query-my-account` | 积分账户（可用 / 累计 / 本月将过期 / 已过期） |
| `query-lottery-info` | 抽奖活动信息与 `drawDecision` |
| `draw-lottery` | 执行抽奖（服务端原子扣减） |
| `query-my-prizes` | 我的奖品 |
| `mall-points-products` | 积分商城可兑换商品（支持 `catRuleIds` 类目筛选） |
| `mall-product-detail` | 商品详情（取 `skuId`） |
| `mall-create-order` | 积分兑换下单 |
| `mall-order-list` / `mall-order-detail` | 商城订单 |

### 2.5 营养（2）

| Tool | 用途 |
|---|---|
| `list-nutrition-foods` | 全量餐品营养（能量 / 蛋白质 / 脂肪 / 碳水 / 钠 / 钙） |
| `query-meal-detail` | 单餐品营养 |

### 2.6 派对与活动预约（5）

| Tool | 用途 |
|---|---|
| `query-party-city` | 支持派对的场次城市列表（需 `spuId`） |
| `query-party-store` | 指定城市可举办派对的门店 |
| `query-party-store-date` | 可预约日期 |
| `query-party-store-session` | 场次列表 |
| `party-order-create` | 创建派对订单（仅 `shopId=5`） |

### 2.7 企业团餐（3）

| Tool | 用途 |
|---|---|
| `delivery-query-stores(beType=6)` | 团餐门店 |
| `query-meal-assistance` | 助餐服务（取 `gmServiceCode`） |
| `query-promotions` | 团餐满减/满折规则 |

### 2.8 其他（3）

| Tool | 用途 |
|---|---|
| `now-time-info` | 服务器时间（活动/预约日期基准） |
| `order-list` | 历史订单 |
| `query-survey-coupon` | 满意度奖券 |

### 2.9 门店级用券（1）

| Tool | 用途 |
|---|---|
| `query-store-coupons` | 指定门店 + 订单类型下的可用券（比价用） |

---

## 3. 三条关键调用链

### 链 A · 到店点餐（含防错）

```
query-nearby-stores {beType:1, searchType:2, city:"北京市", keyword:"鼓楼南街"}
   → storeCode（自取不传 beCode）
query-meals {storeCode, orderType:1, beType:1}
   → 餐品编码位于 data.categories[].meals[].code  ← 不是外层 code（外层是状态码 200）
query-meal-detail {storeCode, orderType:1, beType, code}
   → 若含 rounds（选一/套餐组）必须先让用户选
calculate-price {storeCode, orderType:1, beType, items:[{productCode, quantity}]}
   → 取 data.takeWayList[].code（实测 eat-in / take-in-store）
create-order {storeCode, orderType:1, beType, takeWayCode, items:[...]}
```

**关键约束**：`orderType=1` 下单**必传** `takeWayCode`，且只能来自 `calculate-price`；到店自取**不传** `beCode`；`reservationDate` 仅预约场景传。

### 链 B · 领券 + 比价

```
available-coupons            → 发现新券
auto-bind-coupons            → 先领满
query-store-coupons {storeCode, orderType}
   → 取 couponId / couponCode
calculate-price items=[{productCode, quantity, couponId?, couponCode?}]
   → 逐方案算价，输出「不用券 / 用最优券」对比
```

### 链 C · 积分到期止损（本项目特色）

```
query-my-account     → currentMouthExpirePoint（本月将过期）、availablePoint
query-lottery-info   → drawPoint（单次消耗）、drawDecision
可抽次数 N = floor(currentMouthExpirePoint / drawPoint)
   → 展示「抽 N 次、消耗 X、剩余 Y 仍会过期」并获用户确认
draw-lottery × N     → 逐次执行，间隔 ≥1s，遇限流立即停止、不重试
```

**实测扣减顺序**：**先扣将过期积分，不足才从其他积分扣**。
故「是否溢出」= 总消耗 > 将过期积分（超 1 分也算），把两套方案的代价摊给用户决定。

---

## 4. 真实调用验证记录（脱敏）

| # | Tool | 入参 | 返回摘要 | 结论 |
|---|---|---|---|---|
| 1 | `initialize` | — | `serverInfo.name=mcd-mcp`, `version=1.0.0` | ✅ 握手成功 |
| 2 | `tools/list` | — | `tools.length = 35` | ✅ 工具面确认 |
| 3 | `now-time-info` | — | `2026-10-09T18:17:31.608+08:00`, `dayOfWeek=FRIDAY` | ✅ 时间基准可用 |
| 4 | `query-my-account` | — | 返回 `availablePoint` / `accumulativePoint` / `currentMouthExpirePoint` 等 10 个字段 | ✅ 积分止损链路成立 |
| 5 | `campaign-calendar` | — | 返回 10 月活动：9.9 元早餐两件套（10/8–10/21）、G-DRAGON 联动韩式系列、厚松饼堡回归、麦当劳 × PEACEMINUSONE 周边、麦金喜抽奖（10/10 00:00）等 | ✅ 活动雷达可用 |
| 6 | `available-coupons` | — | 6 张已领取（麦旋风任选、巧克力味厚松饼猪柳蛋套餐等）、3 张可领取（免费脆薯饼、人气麦旋风买一送一、9.9 元中杯冰美式） | ✅ 领券链路可用 |
| 7 | `query-nearby-stores` | `{beType:1, searchType:2, city:"北京", keyword:"昌平"}` | 5 家门店，含 `storeCode`、`distance`、`reservation=true` 及**完整** `reservationTimeOptions`（早餐 06:44–10:15、午餐 10:44–14:15、下午茶、夜市、宵夜） | ✅ 门店/预约数据可用 |
| 8 | `mall-points-products` | `{catRuleIds:"1>6>20,1>6>21,1>6>22,1>6>34"}` | 19 个亲子/派对商品，含 `spuId`（如亲子读书会 1830、过家家派对 6370、趣读派对 5643/10675）与价格 | ✅ 派对预约链路入口可用 |
| 9 | `list-nutrition-foods` | — | **160 条**餐品营养记录，字段为 `energyKj/energyKcal/protein/fat/carbohydrate/sodium/calcium` | ✅ 控卡配餐可用 |

> 说明：出于隐私考虑，账号相关数值（积分余额、券数量明细）已在本文档中作概括性描述，未记录具体数值。

**以上 9 次调用全部为真实请求**，非构造数据；调用脚本见 `scripts/mcd_cli.py`（`call` 子命令），复现方式：

```bash
python scripts/mcd_cli.py call now-time-info
python scripts/mcd_cli.py call query-nearby-stores '{"beType":1,"searchType":2,"city":"北京","keyword":"昌平"}'
```

---

## 5. 业务价值

| 面向 | 价值 |
|---|---|
| **消费者** | 把「翻活动 → 手动领券 → 挑门店 → 配餐 → 比价 → 下单」的多页面操作压缩成一句话；并把「即将过期的积分」变成可执行的止损方案 |
| **麦当劳** | 提升券的领取率与核销率、带动积分消耗与复购；派对/体验营等**非餐品业务**获得新的发现入口（原本藏在商城深处）|
| **开发者** | 提供一套「强依赖工具链如何可靠编排」的参考实现：`beType`/`orderType` 组合规则、编码传递路径、二次确认边界，均可直接复用 |

---

## 6. 可靠性设计（编排规则摘要）

完整 14 条见 `SKILL.md`，要点：

1. **`beType` 决定一切**（1 自取 / 2 麦乐送 / 5 得来速 / 6 团餐），`orderType` 到店类=1、外送类=2；
2. **`searchType=2` 必须 `city` 与 `keyword` 同时传**（只传其一报 `600058`）；
3. **菜单编码取 `data.categories[].meals[].code`**，勿取响应外层 `code`；
4. **绝不臆造编码**：所有 code 必须来自上游工具返回；
5. **下单前必须 `calculate-price`** 并取得用户确认；
6. **抽奖两段式**：先展示 `drawDecision.nextConsumption`，再执行；
7. **判定成败看 `success` 字段**（结构化返回），`success=false` 即失败，须如实转述 `message`；
8. **消耗性取舍不替用户决定**：把每个方案的代价摊开，由用户拍板。
