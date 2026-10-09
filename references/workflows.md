# 麦当劳 MCP 工作流详解（字段级）

> 所有 `storeCode` / `beCode` / `addressId` / `productCode` / `skuId` 示例均为**占位符**，实际值必须来自上游工具返回，禁止照抄。  
> 参数全集见 `tools.md`。

---

## 〇、先确认取餐方式（所有点餐 / 门店请求的入口）

**先问取餐方式，再决定问什么** —— 不要一上来就搜门店或菜单。

| 用户选择 | beType | 紧接着先问             | 再走             |
| ---- | ------ | ----------------- | -------------- |
| 到店自取 | `1`    | **你在哪儿**（城市 + 地标） | 「二、到店自取 / 得来速」 |
| 得来速  | `5`    | **你在哪儿**（开车去哪个区域） | 「二、到店自取 / 得来速」 |
| 麦乐送  | `2`    | **用哪个配送地址**       | 「一、外送（麦乐送）全流程」 |

- **只有自取 / 得来速才需要位置**；**麦乐送不问「你在哪」**，门店由配送地址决定。
- 位置问法（低成本）：先查 `order-list` 问「你现在是不是在常去那家 XX 店附近？」，答否再问「城市 + 地标」。

---

## 一、外送（麦乐送）全流程

### Step 1 取地址

```
delivery-query-addresses            # 无入参，返回用户已有配送地址列表（含 addressId）
```

需要新增地址时：

```
delivery-create-address
{
  "contactName": "张三",
  "phone": "13800000000",        # 必须 11 位纯数字
  "gender": "男",
  "city": "北京市",
  "address": "朝阳区xx路xx号xx小区",
  "addressDetail": "3号楼2单元501"
}
```

必填：`contactName` `phone` `city` `address` `addressDetail`。

### Step 2 取门店与 beCode

```
delivery-query-stores { "beType": 2, "addressId": "<addressId>" }
```

→ 返回该地址可配送的 `storeCode` 及配对的 **`beCode`**。

### Step 3 看菜单

```
query-meals { "storeCode": "<storeCode>", "beCode": "<beCode>", "orderType": 2, "beType": 2 }
query-meal-detail { "storeCode": "...", "beCode": "...", "orderType": 2, "beType": 2, "code": "<productCode>" }
```

> 促销商品在 `query-meal-detail` 可能取不到，用 `query-meals` 全量兜底。

### Step 4 算价（必做）

```
calculate-price
{
  "storeCode": "...", "beCode": "...", "orderType": 2, "beType": 2,
  "addressId": "<addressId>",
  "needTableware": false,
  "items": [ { "productCode": "P001", "quantity": 1 } ]
}
```

→ 返回总价、优惠明细。**把明细展示给用户并确认。**

### Step 5 下单

```
create-order
{
  "storeCode": "...", "beCode": "...", "orderType": 2, "beType": 2,
  "addressId": "<addressId>",
  "needTableware": false,
  "items": [ { "productCode": "P001", "quantity": 1 } ]
}
```

→ 返回支付链接 / 订单号。

### Step 6 查进度

```
query-order      { "orderId": "<orderId>" }
order-list                                        # 无入参，历史订单
cancel-order     { "orderId": "<orderId>", "cancelReasonCode": "1" }
# cancelReasonCode: 取消原因码，默认 "1"。
# ⚠ 未实测：配餐中/配送中的订单可能被门店拒绝取消（接口能调通但业务返回失败）。
#    取消前务必先向用户确认——这是不可逆的消耗性操作（见铁律 14）。
#    建议先 query-order 看 orderStatus，再决定是否真的取消。
```

---

## 二、到店自取 / 得来速

### 找店规则（实测结论）

| searchType | 语义    | 实测行为                                                               |
| ---------- | ----- | ------------------------------------------------------------------ |
| `1`        | 收藏餐厅  | 有收藏时直接返回门店；**该 beType 无收藏时报 `600050 收藏餐厅列表为空`**（得来速 beType=5 实测为空） |
| `2`        | 按位置搜索 | **必须 `city` 与 `keyword` 同时传**；只传其一会报 `600058 城市名或者关键词不能为空`         |

稳妥顺序：先试 `searchType=1`，若报 600050 再改用 `searchType=2` + `city` + `keyword`。  
取门店用 `data[].storeCode`；`data[].beCode` **不为空时**才带上（自取场景实测无 `beCode`）。

### 自取（beType=1）

```
query-nearby-stores { "beType": 1, "searchType": 2, "city": "北京市", "keyword": "国贸" }
   → data[].storeCode = "1950564"（实测）
query-meals      { "storeCode": "1950564", "orderType": 1, "beType": 1 }    # 不传 beCode
calculate-price  { "storeCode": "1950564", "orderType": 1, "beType": 1, "items": [...] }
   → data.takeWayList = [{"code":"eat-in"},{"code":"take-in-store"}]        # 实测
create-order     { ..., "takeWayCode": "take-in-store", "items": [...] }
```

### 得来速（beType=5）

```
query-nearby-stores { "beType": 5, "searchType": 2, "city": "北京市", "keyword": "..." }  # 收藏店实测为空，直接走 2
   → 取 storeCode + beCode
query-meals { "storeCode": "...", "beCode": "...", "orderType": 1, "beType": 5 }
```

其余同自取（`orderType=1` + 传 `beCode`）。

> **`takeWayCode` 是 `orderType=1` 下单的必传项**，值只能来自 `calculate-price` 返回的 `data.takeWayList[].code`。  
> 外送/团餐（`orderType=2`）**不要传**——实测其算价返回**不含** `takeWayList`。

---

## 三、菜单返回结构与 items 数组构造

### query-meals 返回结构（实测）

```
data.categories[]                  # 分类列表（实测 15 个分类）
  └ .meals[].code                  # ← 餐品编码，即 productCode
data.meals.{code}                  # 详情映射表（实测 123 条）
  └ .name / .image / .currentPrice / .originalPrice / .discountType / .canWithOrder / .withOrder
```

⚠️ **易错**：响应**外层**也有一个 `code` 字段，那是业务状态码（`200`），**不是**餐品编码。  
取餐品编码必须走 `data.categories[].meals[].code`。

### 单点商品

```json
{ "productCode": "P001", "quantity": 2 }
```

### 带特制（去冰、不加酱…）

```json
{
  "productCode": "P001",
  "quantity": 1,
  "modification": {
    "values": [
      { "key": "<modifierKey>", "code": "<modifierCode>", "quantity": 1 }
    ]
  }
}
```

`key` / `code` 来自 `query-meal-detail` 返回的特制选项定义。

### 带用券

```json
{ "productCode": "P001", "quantity": 1, "couponId": "<couponId>", "couponCode": "<couponCode>" }
```

### 套餐 / 口味「选一」（roundList）★ 实测

```json
{
  "productCode": "COMBO01",
  "quantity": 1,
  "roundList": [
    {
      "round": "<round标识>",
      "comboItemList": [
        { "code": "<子商品编码>", "quantity": 1,
          "modification": { "values": [ { "key": "...", "code": "...", "quantity": 1 } ] } }
      ]
    }
  ]
}
```

`round` 与可选子商品来自 `query-meal-detail` 的 `data.rounds[]`：

```
rounds[].{ id, name, minQuantity, maxQuantity,
           choices[].{ code, name, quantity, isDefault, diffPrice } }
```

实例：`9900014239`（麦旋风任选1）→ `rounds[0] = {id:1, name:"选择麦旋风", minQuantity:1, maxQuantity:1,
choices:[{code:"4900",name:"草莓麦旋风",quantity:1,isDefault:1},{code:"1217",name:"奥利奥麦旋风",quantity:0}]}`

⚠️ **实测（易错）**：`round` 必须传 `rounds[].id` 的**字符串**（如 `"1"`）；
传 round 名称（`"选择麦旋风"`）或省略 `round` 字段 → 直接 **500 服务器未知的错误**。
`choices[].quantity=1` 只是**默认选中**项，仍须让用户确认口味（**点单前必查，见铁律 13**）。

### 随单购

`create-order` 的 `withOrder` 传随单购商品（来自 `query-meals`），可享随单购优惠。

---

## 四、优惠计算器（比价）

```
# 1) 先补齐可领券
auto-bind-coupons

# 2) 查该门店该场景可用券
query-store-coupons { "storeCode": "...", "orderType": 1, "beType": 1 }
#   外送：query-store-coupons { "storeCode":"...", "beCode":"...", "orderType":2, "beType":2 }
#   到店自取：orderType=1 且不传 beCode；得来速：orderType=1 且传 beCode

# 3) 逐方案算价
calculate-price { ..., "items": [ { "productCode":"P001","quantity":1 } ] }                    # 方案A 不用券
calculate-price { ..., "items": [ { "productCode":"P001","quantity":1,
                                    "couponId":"C1","couponCode":"CC1" } ] }                     # 方案B 用券
```

**输出格式建议**（两列对比）：

| 方案    | 商品小计  | 优惠     | 实付    | 省         |
| ----- | ----- | ------ | ----- | --------- |
| 不用券   | ¥52.0 | ¥0     | ¥52.0 | -         |
| 用券 C1 | ¥52.0 | -¥12.0 | ¥40.0 | **¥12.0** |

券的可用性以 `query-store-coupons` 为准；`query-my-coupons`（卡包）不校验门店规则。

**用券三步（实测，务必照做）**：

1. `query-store-coupons` 取券 → 记下 **`couponId` + `couponCode` + `products[].productCode`**（三个都要）；
2. `items` 里**用券自己的 `productCode`**（不是菜单里的同类商品！配错报 `600012 促销规则不支持该商品`）；
3. `couponId` 与 `couponCode` **必须同时传**（只传其一报 `600010`）。

```json
{ "storeCode": "...", "beCode": "...", "orderType": 2, "beType": 2, "addressId": "...",
  "items": [ { "productCode": "<券的 products[].productCode>", "quantity": 1,
               "couponId": "<couponId>", "couponCode": "<couponCode>" } ] }
```

> 券专属商品（如「麦旋风任选1」`9900014239`）**不一定出现在 `query-meals` 的分类里**，所以必须直接引用券返回的 code。  
> **积分商城商品券（`1>4`）实测全部为「到店专用」**，外送单用不了。

---

## 五、团餐（beType=6）

```
delivery-query-stores { "beType": 6, "addressId": "<addressId>" }       # 拿 storeCode + beCode
query-meals           { "storeCode":"...", "beCode":"...", "orderType":2, "beType":6 }
query-promotions      { "storeCode":"...", "beCode":"...", "orderType":2, "beType":6 }   # 满减/满折规则
query-meal-assistance { "storeCode":"...", "beCode":"...", "orderType":2, "beType":6 }   # 助餐服务
   → 选一项，取 gmServiceCode
calculate-price       { ..., "beType":6, "gmServiceCode":"<...>", "items":[...] }
create-order          { ..., "beType":6, "gmServiceCode":"<...>", "items":[...] }
```

`query-promotions` 返回字段：`promotionType`（31-满额减 / 33-订单折扣）、`ruleCategory`（30-满折 / 40-满减）。

---

## 六、积分商城兑换

```
mall-points-products                                  # 可加 catRuleIds 筛选
   # 类目：商品券 1>4｜实物商品 2｜周边产品 2>8｜实物礼品卡 2>9
   #      生日类派对 1>6>20｜主题类派对 1>6>21｜麦麦体验营 1>6>22
   #      品鉴会 1>6>25｜读书会 1>6>34｜积分兑换活动 1>6>40
mall-product-detail { "spuId": <spuId> }              # 看 SKU，选 skuId
mall-create-order   { "skuId": <skuId>, "spuCategory": "1" }          # 虚拟商品（券）
mall-create-order   { "skuId": <skuId>, "spuCategory": "2", "count": 1,
                      "addressId": "<addressId>" }                     # 实物，必传地址
mall-order-list / mall-order-detail { "orderId": "<...>" }
```

**规则**：单个商品一个订单；多个商品**必须分别下单并排队**（等上一单成功响应后再发下一单）。仅支持 `shopId=2`。  
需要门店+场次的活动（生日派对等）走「派对预约」，不用 `mall-create-order`。

---

## 七、派对 / 活动预约

```
now-time-info                    # 先取服务器时间做基准
mall-points-products (catRuleIds=1>6>20 等) → 取活动 spuId
query-party-city     { "spuId": <spuId> }                       # 选城市 → 取 code / 经纬度
query-party-store    { "code": "<城市code>", "spuId": <spuId>, "latitude": .., "longitude": .. }
query-party-store-date    { "storeCode": "...", "spuId": <spuId> }        # 可预约日期
query-party-store-session { "storeCode": "...", "spuId": <spuId>, "dateStr": "yyyy-MM-dd" }  # 场次/余位
party-order-create   { "partyType": 1, ... }    # 1-包场, 2-拼团；其余字段(storeCode/skuId/dateStr/id/leftNum/
                                                # timeStart/timeEnd/partyTimeInfo/count/spuId/code)取自上一接口
```

---

## 八、积分与抽奖

```
query-my-account                 # 积分余额、过期积分
query-lottery-info               # 活动/消耗/剩余次数/奖品/drawDecision
   ↓ 展示 drawDecision.nextConsumption 并获用户明确确认（resourceEligible 必须为 true）
draw-lottery
query-my-prizes { "pageNum": 1, "pageSize": 10 }
```

`drawDecision` 字段：`resourceEligible`（是否够资源）、`nextConsumption`（本次实际消耗）、`fallbackConsumption`（兜底消耗，非 null 时需说明「先扣次数、次数用完转扣积分」）。

### draw-lottery 返回结构（实测）

结果**在 `data` 层下**，不在顶层：

```
data.status.code        # SUCCESS 才算成功；非 SUCCESS 时 data.status.message 为失败原因
data.status.message
data.win                # 是否中奖（boolean）
data.prizes[]           # 中奖奖品：{ name, imageUrl, typeText, validDateInfo }，未中奖为空数组
data.consumePoint       # 本次消耗积分
```

⚠️ **易错**：按顶层 `status` 读会拿到 `None`，把成功抽奖误判为失败并中断流程（实测踩过，白停 1 次）。  
判定顺序：`data.status.code == "SUCCESS"` → 看 `data.win` / `data.prizes`。

### 到期止损：一键用将过期积分抽奖

```bash
python scripts/points_expiry_draw.py                                     # dry-run：摊开两套方案
python scripts/points_expiry_draw.py --yes                               # 执行「不溢出」方案
python scripts/points_expiry_draw.py --yes --times 12 --allow-overflow   # 用户同意溢出后执行
```

逻辑：`N = floor(currentMouthExpirePoint / drawPoint)`，**默认只花将过期那部分积分**；不足一次消耗时只提示、不执行；每次间隔 1.2s，遇限流/失败即停不重试。

**扣减顺序（实测，勿想当然）**：抽奖扣分**先扣「将过期积分」**，不足部分才从其他积分扣。  
实例：将过期 17.1 分 + 可用 1584.6 分，抽 1 次（24 分）→ **17.1 来自将过期、6.9 来自其他积分**，抽后 `currentMouthExpirePoint` 归 0。  
⚠️ 所以「溢出」的准确含义是：**总消耗 > 将过期积分**（哪怕只超 1 分也算），此时才需要 `--allow-overflow`。  
不要用 `floor(将过期积分/单次消耗)` 去拆「哪部分来自哪个池子」——积分是连续量，按**金额**拆分：`min(总消耗, 将过期积分)`。

**溢出规则（重要）**：当指定次数 > 将过期积分能独立承担的次数时，必须显式加 `--allow-overflow`，否则脚本以**退出码 2 拒绝执行**。  
**是否溢出一律由用户决定**——脚本只摊开方案与代价，不预设、不自行选择。（2026-10-09 实测：233.1 将过期 → 抽 9 次消耗 216 分，中 30 积分×2 + 甜辣小食组合 5 折券。）

---

## 九、热量计算

```
list-nutrition-foods     # 无入参，全量营养成分
query-meal-detail        # 单品详情（含营养）
```


**输出表格建议**：

| 餐品     | 数量 | 能量(kcal) | 蛋白质(g) | 脂肪(g) | 碳水(g) | 钠(mg) |
| ------ | -- | -------- | ------ | ----- | ----- | ----- |
| 巨无霸    | 1  | …        | …      | …     | …     | …     |
| **合计** |    | **…**    | …      | …     | …     | …     |

按用户目标给 1–2 套组合方案（如「500 kcal 以内」「高蛋白 ≈30g」）。接口未返回的字段标注「接口未提供」。

---

## 十、领券与卡包

```
available-coupons                       # 可领取的券
auto-bind-coupons                       # 一键全领（无入参）
query-my-coupons { "page": 1, "pageSize": 20 }     # 卡包已有券（不校验门店规则）
query-store-coupons { ... }                        # 指定门店+场景可用券（下单参考）
query-survey-coupon { "orderId": "<orderId>" }     # 订单满意度奖券
```

---

## 附：实测验证记录（2026-10-09，真实账号 + 真实门店）

| 项      | 实测结果                                                                             |
| ------ | -------------------------------------------------------------------------------- |
| 到店自取找店 | `searchType=1` 返回北京 2 家收藏店（含 `storeCode`，**无 `beCode`**）                         |
| 得来速找店  | `searchType=1` 报 `600050 收藏餐厅列表为空`；须改 `searchType=2` + city + keyword            |
| 按位置找店  | 只传 `city` 或只传 `keyword` → `600058`；两者同传 → 正常返回门店列表                               |
| 菜单     | `storeCode=1950564` 返回 15 个分类 / 123 个餐品；餐品编码形如 `9900016076`                      |
| 到店算价   | `orderType=1` 返回 `takeWayList = [{code:"eat-in"},{code:"take-in-store"}]`        |
| 外送算价   | `orderType=2` 返回**不含** `takeWayList`                                             |
| 门店可用券  | `query-store-coupons`（到店自取，不传 `beCode`）正常返回券列表                                   |
| 抽奖信息   | `query-lottery-info` 返回 `drawDecision`（含 `resourceEligible` / `nextConsumption`） |

| 积分商城 | `mall-points-products` → `spuId` → `mall-product-detail` → `skuId` + `spuCategory` |  
| 外送链路 | 地址 → `delivery-query-stores`(storeCode+beCode) → 菜单 → `calculate-price` 全通 |
