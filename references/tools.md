# 麦当劳 MCP 工具手册

> 来源：MCP Server `mcd-mcp` v1.0.0（`https://mcp.mcd.cn`）`tools/list` 实时导出，共 **35** 个工具。
> 参数名后带 `*` 为必填。enum 取值已标注。

## 关键概念（务必先理解）

> **`keyword` 要用具体地标/小区名，不要用行政区名**（实测）：以「北京市」为例，
> `keyword=密云`（区名）返回 **0 家**；`keyword=长安小区`（小区名）返回 **5 家**且按距离升序。
> 用户给详细地址时，**取其中的小区名/地标名**当 keyword（如「密云区长安小区西区20号院3号楼」→ `长安小区`）。

| 概念 | 取值 | 含义 |
|---|---|---|
| `beType` | 1 | 到店取餐（自取） |
| `beType` | 2 | 麦乐送到家（外送） |
| `beType` | 5 | 得来速 DT（车道取餐，到店类） |
| `beType` | 6 | 企业团餐 |
| `orderType` | 1 | 到店（含到店自取 + 得来速） |
| `orderType` | 2 | 外送（含麦乐送 + 企业团餐） |
| `storeCode` | - | 门店编码，菜单/算价/下单必传 |
| `beCode` | - | 业务编码，**与 storeCode 配对**。到店自取(beType=1)不传，其余场景必传 |
| `addressId` | - | 外送地址 ID，来自 `delivery-query-addresses` |
| `reservationDate` | `yyyy-MM-dd HH:mm` | 仅预约场景传，非预约**不要传** |

**beCode 来源对照**：到店自取 beType=1 → 不传；得来速 beType=5 → `query-nearby-stores`；麦乐送 beType=2 → `delivery-query-stores`；团餐 beType=6 → `delivery-query-stores`。

**已实测的调用陷阱**（细节见 `../SKILL.md` 铁律）：

- `query-nearby-stores`：`searchType=1` 查收藏店，该 beType 无收藏时返回 `600050`；`searchType=2` 按位置，**必须 `city` 与 `keyword` 同时传**，缺一报 `600058`。
- `query-meals`：餐品编码在 `data.categories[].meals[].code`；响应**外层**的 `code` 是业务状态码（200），勿混用。
- `calculate-price`：`orderType=1` 返回 `data.takeWayList[].code`（`create-order` 的 `takeWayCode` 来源）；`orderType=2` 不返回该项。
- 业务成败以响应 `success` 字段为准（结构化返回），工具调用不报错 ≠ 业务成功。
- **返回形态有两类**：① 字段说明 + 原始 JSON（多数工具，按字段取值）；② **服务端已渲染的 Markdown**（实测 `available-coupons`、`query-my-coupons`、`campaign-calendar`）—— 直接原样展示，不要解析字段，也无 `success` 可判。
- **`draw-lottery` 结果在 `data` 层下**：`data.status.code`（`SUCCESS` 才算成功）/ `data.win` / `data.prizes[]` / `data.consumePoint`。**不是顶层 `status`** —— 按顶层读会拿到 None 并把成功抽奖误判为失败（实测踩过）。
- **餐品命名不统一**：同一餐品在**到店**与**外送**菜单里名称可能不同（实测：到店叫「麦辣鸡腿堡四件套」，外送叫「麦辣鸡腿汉堡」/「麦辣鸡腿汉堡套餐」）。按名称找餐品时用**短关键词**（如「麦辣」「四件套」）遍历 `data.meals` 全量名称，不要用完整商品名精确匹配。
- **`campaign-calendar` 不稳定**：实测出现「返回 0 字符」与 **60s 读超时**。调用时超时给到 ≥90s；空结果应重试 1–2 次；**不要**把空返回当作「当月无活动」告诉用户。
- **`query-meal-detail` 返回很长**（实测 1.8 万字符）：开头是服务端的「输出格式要求」说明文本，JSON 夹在中间。取值必须按**整体响应对象**（`success` / `data`）解析，不要取最大的那个子对象。
- **`query-party-store` 的门店编码在 `data[].code`**（**不是** `storeCode`）——该值就是下一步 `query-party-store-date` / `query-party-store-session` 的 `storeCode` 入参。实测链路：city(安康市 610900) → `data[].code`=1960713 → 可约日期 → 场次(12:00-13:30 / 18:30-20:00，5–12 人，¥138/场，`price=13800` 分为单位)。
- **券必须用「券自己绑定的商品编码」**（实测坑）：
  `query-store-coupons` 返回的每张券都带 `products[].productCode`。例：「麦旋风任选」券绑定的是 **`9900014239`（麦旋风任选1）**，
  **把券配到同类但不同编码的商品上会报 `600012 促销规则不支持该商品`**。
  ⚠️ 券专属商品**可能不出现在 `query-meals` 的分类里** —— 要用券返回的那个 code，别自己去菜单里挑同类品。
- **用券必须 `couponId` + `couponCode` 同时传**：只传其一报 `600010 使用优惠券需要couponId和couponCode`。
- **积分商城商品券（类目 `1>4`）实测全部是「到店专用」**：麦乐送/外送订单**用不了**。给外送单推荐积分券前先确认适用场景。
- **找门店要「先用常去门店试问，再问地标」**：`query-nearby-stores` **不接受经纬度**，只能按 `city` + `keyword` 搜。没有可靠位置来源时：
  ① 先查 `order-list` 统计**最常去的门店**，问用户「你现在是不是在 XX 店附近？」；
  ② 答否再问「城市 + 地标」。**不要猜，也不要声称自己知道用户位置。**
  距离字段实测：`searchType=1`（收藏门店）的 `distance` 恒为 `0`，不能用来判断远近；`searchType=2`（`city` + `keyword`）返回**真实距离且结果按 `distance` 升序**，取第一条即最近门店。
- **能力边界（2026-10-09 实测）**：MCP **没有**「麦金卡 / 会员卡有效期」相关接口。`query-my-account` 只返回积分字段（可用/累计/已用/本月与下月将过期等），卡包 `query-my-coupons` 也不含麦金卡。用户问麦金卡有效期时，如实告知需去麦当劳 App/小程序查看，**不得编造日期**。

---

## 门店与菜单

### `query-nearby-stores`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beType`* | int | ✅ | beType必传，1：到店自提, 5-得来速车道取餐(Drive Through) （枚举：1, 5） |
| `city` | string |  | 城市名 |
| `keyword` | string |  | 关键词 |
| `searchType`* | int | ✅ | searchType=2 按位置进行搜索， searchType=1 搜索收藏餐厅，默认searchType=1 （枚举：1, 2） （默认 1） |

<details><summary>完整说明</summary>

```text
Description: 到店场景下，查询用户可点餐门店，需要用户明确是到店自取还是车道取餐
- beType=1(到店自提): 返回的门店无 beCode，后续工具调用不传 beCode
- beType=5(得来速): 返回的门店有 beCode，后续工具调用必须传 beCode
When：
- 用户询问"我想到店", "我想驾车去麦当劳"
- 看看我附近有哪些麦当劳的门店
Input:
- searchType: 必传，searchType=2 按位置进行搜索， searchType=1 搜索收藏餐厅，默认searchType=1
- city: 城市，searchType=2 时必填
- keyword: 位置关键词，searchType=2 时必填
- beType: 必填，1-到店自取, 5-得来速车道取餐(Drive Through)
On Error：
- 用户没有收藏记录，可使用搜索功能进行搜索
Next：
- 展示门店的 storeCode 和 beCode（beType=5 时）
- reservation=true 时完整展示 reservationTimeOptions，today=true 标记"(今天)"
- 引导用户选择门店
```

</details>

### `delivery-query-stores`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `addressId`* | string | ✅ | 地址ID，来源delivery-query-address |
| `beType`* | int | ✅ | beType：2: 麦乐送，6：团餐 |

<details><summary>完整说明</summary>

```text
Description: 外送场景下，用户选择完地址后，需要根据地址ID，查询用户当前地址可配送的门店
When:
- 外送场景下，用户选择完配送地址后
- 用户问"这个地址能送到哪些店"
注意：到店场景请使用 query-nearby-stores
Input:
- addressId: 地址ID，来源delivery-query-address
- beType: 必填，2: 麦乐送，6：团餐
```

</details>

### `query-meals`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | 业务编码，与storeCode 配对使用，从query-nearby-stores或delivery-query-stores返回结果中获取。得来速(beType=5)/外送(orderType=2)/团餐场景必传，到店自取(beType=1)场景不传 |
| `beType`* | int | ✅ | 1-到店取餐，2-麦乐送到家，5-得来速(DT)，6-企业团餐 （枚举：1, 2, 5, 6） |
| `orderType`* | int | ✅ | 订单类型，1-到店（含到店自取+得来速车道取餐），2-外送（含麦乐送+企业团餐） （枚举：1, 2） |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式:yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |

<details><summary>完整说明</summary>

```text
Description: 餐品列表, 支持到店自提(orderType=1)和外送(orderType=2)两种场景
企业团餐场景下，可按照这个规则给用户进行搭配
- **20元以下**: 小食
- **20-30元**：汉堡+小食 或 汉堡+饮料
- **30-40元**：汉堡+薯条/小食+饮料
- **40-50元**：汉堡+薯条+小食+饮料
- **50元以上**：丰富组合，优先不重复小食
When:
- 当用户要购买某个餐品时，需要查询一下餐品列表
- 当用户要查看餐品时价格时，需要查询一下餐品列表
- 用户要搭配任何商品时进行下单，都需要查询餐品列表，获取商品code
Input:
- storeCode: 门店编码，必填
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
到店自取(beType=1) → orderType=1，不传 beCode
得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
```

</details>

### `query-meal-detail`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | 业务编码，与storeCode 配对使用，从query-nearby-stores或delivery-query-stores返回结果中获取。得来速(beType=5)/外送(orderType=2)/团餐场景必传，到店自取(beType=1)场景不传 |
| `beType`* | int | ✅ | 1-到店取餐，2-麦乐送到家，5-得来速(DT)，6-企业团餐 （枚举：1, 2, 5, 6） |
| `code`* | string | ✅ | 餐品唯一编码，快餐门店内唯一标识单个餐品的编码 |
| `orderType`* | int | ✅ | 到店自提场景:orderType=1 && beCode 是个无效参数，不要传，传了会报错；外送场景:orderType=2 && beCode 为delivery-query-address中的beCode；得来速(DT)场景：orderType=1 && beCode 为query-nearby-store中的beCode （枚举：1, 2） |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式:yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |

<details><summary>完整说明</summary>

```text
Description: 餐品详情, 支持到店自提(orderType=1)和外送(orderType=2)两种场景
When:
- 用户想要了解餐品有哪些组成
- 用户想要更换套餐的组成或者更换特制商品
Input:
- storeCode: 门店编码，必填
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
到店自取(beType=1) → orderType=1，不传 beCode
得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- reservationDate: 预约时间，仅当用户要预约下单时，该字段必传，格式形如 2020-08-08 09:30
Output展示规则（必须遵守）：
- 若 data.supportModify=true，在商品名称后面标注【可特调】
- 若 choice.supportModify=true，在该 choice 名称后面标注【可特调】
- 不要主动展开特调选项列表，仅当用户主动询问时才展示 modification 内容
- 展示完详情后，总结当前默认选中的搭配（isDefault=1的choices），并引导用户："如需查看或修改特调选项，请回复'查看特调'"
```

</details>

### `list-nutrition-foods`

无入参。

<details><summary>完整说明</summary>

```text
获取麦当劳常见餐品的营养成分数据，包括能量、蛋白质、脂肪、碳水化合物、钠、钙等信息，当用户咨询麦当劳餐品的热量、营养，帮助用户搭配指定热量套餐时有用
```

</details>

---

## 优惠券

### `available-coupons`

无入参。

<details><summary>完整说明</summary>

```text
查询用户当前可领取的麦麦省的优惠券列表。返回券名称、图片、状态和促销标签。当用户询问有什么优惠、可以领什么券时使用此工具。
```

</details>

### `auto-bind-coupons`

无入参。

<details><summary>完整说明</summary>

```text
自动领取麦麦省所有当前可用的麦当劳优惠券。无需指定具体的优惠券和couponId，系统会自动领取用户可领的所有券。当用户说"帮我领券"、"自动领取优惠券"、"一键领券"时使用此工具。
```

</details>

### `query-my-coupons`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `page` | string |  | 页码，默认第1页，最多5页 |
| `pageSize` | string |  | 每页条数，默认200条，最大200条 |

<details><summary>完整说明</summary>

```text
获取用户卡包中的优惠券资产信息，用于“我有什么券 / 券详情查看”等展示与管理场景。 注意：该接口返回的是用户拥有的券，不进行门店、渠道、配送方式等下单规则校验，因此不承诺可用于当前订单。 若业务目标是“当前门店/当前订单可用的券”，请调用 query-store-coupons
```

</details>

### `query-store-coupons`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | 业务编码，与storeCode 配对使用，从query-nearby-stores或delivery-query-stores返回结果中获取。得来速(beType=5)/外送(orderType=2)/团餐场景必传，到店自取(beType=1)场景不传 |
| `beType`* | int | ✅ | 1-到店取餐，2-麦乐送到家，5-得来速(DT)，6-企业团餐 （枚举：1, 2, 5, 6） |
| `orderType`* | int | ✅ | 订单类型, 1-到店（含到店自取+得来速车道取餐），2-外送（含麦乐送+企业团餐） （枚举：1, 2） |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式 yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码必须全部由数字组成 |

<details><summary>完整说明</summary>

```text
Description: 查询【指定门店+订单类型】下可使用的优惠券，支持到店(orderType=1,含到店自取和得来速)和外送(orderType=2,含麦乐送和团餐)
When：
- 当用户已获取到门店时，用户询问"我有什么优惠券可以用"
- 当用户已获取到门店时，用户想在某门店下单前查看可用优惠
- 当用户已获取到门店时，用户选择了商品后想看能用哪些券
- 当用户已获取到门店时，用户问"这个门店能用什么券"
Input：
- storeCode: 门店编码，必填，
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
  到店自取(beType=1) → orderType=1，不传 beCode
  得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
  麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
  团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
```

</details>

### `query-survey-coupon`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `orderId`* | string | ✅ | 订单号。必填。类型为字符串，仅允许字母、数字、下划线和连字符，最长 64 位，格式示例：1030108270000795607354880945。数据来源为用户明确提供的订单号或上游订单查询工具返回的订单号；Agent 不要自行编造或改写该值。 |

<details><summary>完整说明</summary>

```text
Description: 按订单号查询当前 MCP 用户本人订单的 CSAT 满意度答卷，并返回该订单关联奖券的标题、核销时间、核销状态和点餐方式。
When: 用户询问某个订单的满意度答卷结果时使用；用户询问某个订单关联奖券的内容、核销时间、是否已核销、适用于到店还是外送时使用。
Input: orderId 为用户提供的订单号；Agent 不要自行生成。
Next: 将返回的满意度描述、奖券标题、核销时间、核销状态和点餐方式告知用户；未返回的原始答卷、会员号、couponId、couponCode 不要猜测。
```

</details>

---

## 下单与订单

### `calculate-price`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | 业务编码，与storeCode 配对使用，从query-nearby-stores或delivery-query-stores返回结果中获取。得来速(beType=5)/外送(orderType=2)/团餐场景必传，到店自取(beType=1)场景不传 |
| `beType`* | int | ✅ | 1-到店取餐，2-麦乐送到家，5-得来速(DT)，6-企业团餐 （枚举：1, 2, 5, 6） |
| `gmServiceCode` | string |  | 团餐-助餐服务码 |
| `items` | array |  | 待价格计算的商品列表 |
| `needTableware` | bool |  | 是否需要餐具，true需要，false不需要 |
| `orderType`* | int | ✅ | 订单类型，1-到店（含到店自取+得来速车道取餐），2-外送（含麦乐送+企业团餐） （枚举：1, 2） |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式:yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |
| `withOrder` | object |  | 随单购商品 |

<details><summary>完整说明</summary>

```text
Description: 计算商品的价格（含优惠），支持到店自提(orderType=1)和外送(orderType=2)两种场景
When：
- 用户问"这些商品多少钱"
- 用户问"总价是多少"
Input:
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
- storeCode: 门店编码
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
  到店自取(beType=1) → orderType=1，不传 beCode
  得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
  麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
  团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- items: 商品列表（数组）
  - productCode: 商品编码，必填
  - quantity: 商品数量，必填，大于等于1
  - couponId: 优惠券ID，选填（如果用户要使用优惠券）
  - couponCode: 优惠券编码，选填（如果用户要使用优惠券）
  - modification: 特制选项（来自 query-meal-detail 返回的 modification 信息）
    - values[]: 特制选项列表
      - code: 特调商品code
      - key: 特制key（⚠️ 重要规则见下方）
      - quantity: 特制数量
    ⚠️ key 传参规则：
    - 用户选中的特调项：key = query-meal-detail 返回的 selectedKey
    - 用户未选中的特调项：若该项的 unselectedKey 不为空，key = unselectedKey，也必须传入
    - 即：对于包含 unselectedKey 的特调组，该组内所有特调项都必须传入，选中的用 selectedKey 作为 key，未选中的用 unselectedKey 作为 key
- gmServiceCode: 企业团餐场景下，助餐服务code
- withOrder: 随单购商品，随单购商品来自query-meals，用户可以选择随单购，随单购可享受随单购优惠
- needTableware: 是否需要餐具费
Next：
- 计算成功后：返回的价格字段单位为"分"，展示时需除以100转为"元"
- 引导用户："确认价格后，可以说'创建订单'进行下单"
```

</details>

### `create-order`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `addressId` | string |  | 配送地址id，外送or团餐的地址 |
| `beCode` | string |  | 业务编码，与storeCode 配对使用，从query-nearby-stores或delivery-query-stores返回结果中获取。得来速(beType=5)/外送(orderType=2)/团餐场景必传，到店自取(beType=1)场景不传 |
| `beType`* | int | ✅ | 1-到店取餐，2-麦乐送到家，5-得来速(DT)，6-企业团餐 （枚举：1, 2, 5, 6） |
| `gmServiceCode` | string |  | 企业团餐场景(beType=6)下，必传，参数来自query-meal-assistance |
| `items` | array |  | 待价格计算的商品列表 |
| `needTableware` | bool |  | 是否需要餐具，true需要，false不需要 |
| `orderType`* | int | ✅ | 订单类型，1-到店（含到店自取+得来速车道取餐），2-外送（含麦乐送+企业团餐） （枚举：1, 2） |
| `remark` | string |  | 订单备注（选填，最多50字），如"无接触配送"，仅orderType=2场景下需要引导用户填写 |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式:yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |
| `takeWayCode` | string |  | 到店/得来速场景(orderType=1)必传，外送/团餐场景(orderType=2)不传。值从 calculate-price 返回的takeWayList[].code 中选取 |
| `withOrder` | object |  | 随单购商品 |

<details><summary>完整说明</summary>

```text
Description: 创建麦当劳订单，支持到店(orderType=1)和外送(orderType=2)两种场景下单, 必须先确定订单类型，必填 (1：到店，2外送)
When：
- 用户说"我要下单"
- 用户说"创建订单"
Input:
- addressId: 配送地址ID， orderType=2时必填
- storeCode: 必填
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
  到店自取(beType=1) → orderType=1，不传 beCode
  得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
  麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
  团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- takeWayCode: orderType=1时必传，取值来自 calculate-price 返回的 data.takeWayList[].code
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
- items: 商品列表（数组）
 - productCode: 商品编码，必填
 - quantity: 商品数量，必填
 - couponId: 优惠券ID，选填（如果用户要使用优惠券）
 - couponCode: 优惠券编码，选填（如果用户要使用优惠券）
 - modification: 特制选项（来自 query-meal-detail 返回的 modification 信息）
    - values[]: 特制选项列表
      - code: 特调商品code
      - key: 特制key（⚠️ 重要规则见下方）
      - quantity: 特制数量
    ⚠️ key 传参规则：
    - 用户选中的特调项：key = query-meal-detail 返回的 selectedKey
    - 用户未选中的特调项：若该项的 unselectedKey 不为空，key = unselectedKey，也必须传入
    - 即：对于包含 unselectedKey 的特调组，该组内所有特调项都必须传入，选中的用 selectedKey 作为 key，未选中的用 unselectedKey 作为 key
 - withOrder: 随单购商品，随单购商品来自query-meals，用户可以选择随单购，随单购可享受随单购优惠
 - remark: 订单备注（选填，最多50字），如"无接触配送"，仅orderType=2场景下需要引导用户填写
 - needTableware: 是否需要餐具费
Next：
- 引导用户："您可以通过支付链接扫码或者打开麦当劳APP完成支付，支付完成后请回复'支付完成'或'支付失败'，会帮您查询最新的订单状态"
```

</details>

### `order-list`

无入参。

<details><summary>完整说明</summary>

```text
Description: 查询麦当劳历史订单，非商城订单，商城订单需要使用mall-order-list
When：
- 用户询问"帮我查询一下历史订单"
- 用户询问"我买了什么麦当劳餐品"
```

</details>

### `query-order`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `orderId`* | string | ✅ | No comments found. |

<details><summary>完整说明</summary>

```text
Description: 查询订单详细信息
When：
- 用户询问"查下订单详情"、"订单状态"、"我的订单"
- 用户提供了麦当劳订单编号想查询配送进度
- 用户说我已支付或者支付失败时，查询一下最新的订单状态
```

</details>

### `cancel-order`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `cancelReasonCode`* | string | ✅ | 取消原因code，默认为1 |
| `orderId`* | string | ✅ | 订单号 |

<details><summary>完整说明</summary>

```text
Description: 取消订单，非商城订单
When：
- 用户说"取消订单"、"我要取消"
- 用户说"帮我取消一下订单"
Input:
- cancelReasonCode: 取消原因code，必填，可选值：1=改主意了, 2=重复下单, 3=点错了/点多了/点少了, 4=地址/电话填错了, 5=送达时间选错了, -1=其它原因
Next：
- 提示用户"订单已取消"
```

</details>

---

## 外送地址

### `delivery-query-addresses`

无入参。

<details><summary>完整说明</summary>

```text
Description: 外送场景下，查询用户配送地址列表
When：
- 用户想点麦乐送
- 用户想吃麦当劳，并配送到家
- 我想点团餐
Next：
- 1:引导用户创建新的配送地址
- 2:当用户选择企业团餐时，需要引导用户提供预算金额和人数，以便于计算人均预算
```

</details>

### `delivery-create-address`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `address`* | string | ✅ | 配送地址 |
| `addressDetail`* | string | ✅ | 配送地址门牌号 |
| `city`* | string | ✅ | 城市 |
| `contactName`* | string | ✅ | 联系人姓名 |
| `gender` | string |  | 性别 |
| `phone`* | string | ✅ | 要求为11位纯数字 |

<details><summary>完整说明</summary>

```text
Description: 创建用户配送地址
When：
- 用户想添加新的配送地址
Input:
- city: 城市名称，必填，必须从用户输入中获取实际城市名称，如"南京市"
- contactName: 联系人姓名，必填，必须从用户输入中获取实际联系人姓名，如"李明"
- gender: 性别，必须从用户输入中获取实际联系人性别，如"先生"、"女士"
- phone: 联系人手机号码，必填，格式为11位纯数字（以1开头），如"18616646686"。
- address: 配送地址，必填，必须从用户输入中获取实际地址，如"清竹园9号楼"
- addressDetail: 配送地址门牌号，必填，必须从用户输入中获取实际门牌号，如"2单元508"
Next：
- 当用户选择团餐时，需要引导用户提供预算金额和人数，以便于计算人均预算
```

</details>

---

## 积分与抽奖

### `query-my-account`

无入参。

<details><summary>完整说明</summary>

```text
查询用户积分账户详情 - 当用户询问"我有多少积分"、"查下我的积分"、"积分余额"、"查询过期积分"时使用
```

</details>

### `query-lottery-info`

无入参。

<details><summary>完整说明</summary>

```text
Description: 查看当前积分抽奖活动信息，包括活动基本信息、抽奖消耗规则、单次所需积分、剩余可抽次数、当前可用积分与公开奖品列表，不执行抽奖。
When：
- 用户询问"积分抽奖有什么奖品"
- 用户询问"抽一次要多少积分"
- 用户询问"这个积分抽奖活动什么时候结束"
Output:
- activityCode/activityName: 活动号/活动名称
- activityStatusText: 活动状态文案（未开始/进行中/已结束/活动不存在）
- beginTime/endTime: 活动起止时间
- drawPoint: 单次所需积分
- drawTypeText: 抽奖消耗规则（无/消耗积分抽奖/消耗任务完成次数/先消耗次数再消耗积分抽奖）
- availableTimes: 剩余可抽次数（消耗任务完成次数、先消耗次数再消耗积分时返回）
- availablePoint: 当前可用积分（消耗积分、先消耗次数再消耗积分时返回）
- drawDecision: 服务端计算的本次资源决策，包含能否因积分/次数资源参与、本次实际消耗及后续兜底消耗
- prizes: 奖品列表[{name, imageUrl, typeText}]
Next：
- 若用户接下来想抽奖，调用 draw-lottery 前必须展示 drawDecision.nextConsumption 并得到用户明确确认
- 抽奖资格和本次实际消耗必须以 drawDecision.resourceEligible/drawDecision.nextConsumption 为准；严禁根据 availableTimes 为 0/null 或 drawTypeText 自行推断能否抽奖。混合规则中 availableTimes=0 且 nextConsumption.type=POINTS，表示仍可使用积分抽奖。
```

</details>

### `draw-lottery`

无入参。

<details><summary>完整说明</summary>

```text
Description: 使用后台配置的抽奖消耗规则参加一次当前积分抽奖并返回结果，服务端原子完成次数或积分扣减与抽奖。
重要约束：仅能在向用户展示 query-lottery-info 返回的 drawDecision.nextConsumption 并得到明确确认后调用。
- 必须以 drawDecision.resourceEligible 判断积分/次数资源是否满足，以 nextConsumption 说明本次实际扣减；不得根据 availableTimes 为 0/null 或 drawTypeText 自行判断。
- 若 fallbackConsumption 不为 null，需说明“本次优先消耗次数；次数用完后将改为消耗积分”。
必须使用 query-lottery-info 返回的实时数据展示消耗/剩余，严禁试抽、自动抽或连续抽。
频次限制：同一用户短时间内重复调用会返回"操作太频繁，请稍后再试"，不扣积分。
When：
- 用户明确表达"我要抽奖"并确认本次配置对应的消耗后调用
前置条件：
- 已向用户展示 query-lottery-info 查询到的 drawDecision.nextConsumption；resourceEligible 为 false 时不得调用
- 用户已明确确认执行抽奖（"试试看""如果可以就抽"不视为确认）
Output:
- status: {code, message}，code 非 SUCCESS 时 message 为具体失败原因，直接展示给用户，不要自行改写
- win: 是否中奖
- prizes: 中奖奖品数组[{name, imageUrl, typeText, validDateInfo}]，未中奖为空数组
```

</details>

### `query-my-prizes`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `pageNum` | string |  | 页码，默认第1页 |
| `pageSize` | string |  | 每页条数，默认10条，最大50条 |

<details><summary>完整说明</summary>

```text
Description: 查询当前登录会员通过积分抽奖获得的本期及历史奖品（可用/已使用/已过期/已领取/已失效）。
When：
- 用户询问"我抽中了什么奖品"
- 用户询问"我的奖品还有哪些能用"
- 用户询问"查我的抽奖记录"
Input:
- pageNum: 页码（可选，默认1）
- pageSize: 每页条数（可选，默认10，最大50）
Output:
- prizes: 奖品列表[{id, name, imageUrl, prizeType, recordTime, status, statusText, timeRemindText}]，按中奖时间(recordTime)倒序
- pageNum/pageSize: 当前页码/每页条数（归一化后的值）
- hasMore: 是否还有下一页
- nextCursor: 下一页游标，无更多时为空
- truncated: 可选，仅在返回被截断时出现（true）
```

</details>

---

## 积分商城

### `mall-points-products`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `catRuleIds` | string |  | 类目规则筛选，支持多选（逗号分隔），非必传，不传时默认查询所有类型。 可选值： - 1>4: 商品券（非预付优惠券） - 2: 实物商品 - 2>8: 周边产品 - 2>9: 实物礼品卡 - 1>6>20: 生日类派对 - 1>6>21: 主题类派对 - 1>6>22: 麦麦体验营 - 1>6>25: 品鉴会 - 1>6>34: 读书会 - 1>6>40: 积分兑换活动 示例：1>4,2 |

<details><summary>完整说明</summary>

```text
查询可兑换餐品券列表 - 当用户询问"有哪些积分兑换商品"、"积分可以兑换什么"、"查看积分商城"时使用
支持类目规则筛选：商品券(1>4)、实物商品(2)、周边产品(2>8)、实物礼品卡(2>9)、生日类派对(1>6>20)、主题类派对(1>6>21)、麦麦体验营(1>6>22)、品鉴会(1>6>25)、读书会(1>6>34)、积分兑换活动(1>6>40)
```

</details>

### `mall-product-detail`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `spuId`* | int | ✅ | 商品SPU ID，需要从查询可兑换餐品券列表让用户选择一个spu才可以 |

<details><summary>完整说明</summary>

```text
查询积分兑换商品详情 - 当用户询问"这个商品详情是什么"、"查看商品详细信息"、用户点击商品查看详情时使用
返回商品的所有SKU规格信息，用户需要选择具体SKU后才能下单兑换

前提条件：
- 已知商品SPU ID，需要从查询可兑换餐品券列表让用户选择一个spu才可以
```

</details>

### `mall-create-order`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `addressId` | string |  | 配送地址ID，spuCategory="2"时必填 |
| `count` | int |  | 兑换数量 |
| `skuId`* | int | ✅ | 商品SKU ID，需要从查询可兑换餐品券列表或查询商品详情中获取 |
| `spuCategory`* | string | ✅ | 类目，商品类别，"1"虚拟商品, "2"实体物品，需要从查询可兑换餐品券列表或查询商品详情中获取 |

<details><summary>完整说明</summary>

```text
创建积分兑换订单，仅支持shopId=2（从 mall-product-detail 获取） - 当用户询问"用积分兑换这个商品"、"兑换这个券"、用户确认兑换商品时使用,切记：如果单个商品一个订单下单；如果用户需要兑换多个商品‘必须’分别下单且‘需要排队’，等前面订单结束响应成功后再调用【mall-create-order】下新的订单
⚠️ 重要识别规则：
此工具仅适用于以下场景：
- 商品券兑换（虚拟商品，spuCategory=1）
- 实物商品兑换（无门店依赖，spuCategory=2）

❌ 不适用场景（请使用 party-order-create）：
- 生日派对/主题派对/麦麦体验营/品鉴会/读书会等需要选择门店和场次的活动
- 积分兑换活动（需要先选择城市、门店、日期、场次）

📋 判断依据：
当商品不包含门店和场次选择需求时，使用此工具
前提条件：
- 必须调用【mall-create-order】完成交易，**禁止**直接生成"下单成功"等结论性文字
- 必须调用【mall-create-order】完成交易，**禁止**直接返回已有订单
- 必须调用【mall-create-order】完成交易，**禁止**直接返回订单
- 仅支持shopId=2（从 mall-product-detail 获取）
- 已知商品SKU ID，需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId
- 用户积分充足
When：
- 用户询问"用积分兑换这个商品"
- 用户询问"我要兑换"
- 用户询问"兑换xxx商品"
- 用户询问"兑换这个券"
- 用户确认兑换商品
Input:
- skuId: 商品SKU ID，需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId
- spuCategory: 类目，商品类别，"1"虚拟商品, "2"实体物品，需要从查询可兑换餐品券列表或查询商品详情中获取
- addressId: 配送地址ID，spuCategory="2"时必填
  spuCategory="2"  → addressId（从 delivery-create-address 获取）
- count: 兑换数量，默认为1
Output:
- orderId: 订单ID
- coupons: 优惠券信息列表
- couponId: 优惠券ID
- orderItemId: 订单子项ID
- couponCodes: 优惠券码列表
- receiveQuantity: 领取数量
- orderItemStatus: 订单子项状态（1-成功，0-失败）
- orderStatus: 订单状态
- status: 响应状态（1-全部下单成功，2-部分成功，0-下单失败）
```

</details>

### `mall-order-list`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `lastId` | number |  | 最后一个订单id |
| `size` | int |  | 查询数量，默认10，超过10按10条查询 （默认 10） |

<details><summary>完整说明</summary>

```text
Description: 查询麦麦商城订单列表
When：
- 用户询问"查看我的麦当劳商城订单列表"
```

</details>

### `mall-order-detail`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `orderId`* | string | ✅ | 订单号 |

<details><summary>完整说明</summary>

```text
Description: 查询麦麦商城订单详情
When：
- 用户询问"麦麦商城的订单详情"
Next:
- 引导用户："您可以打开麦当劳APP查看凭证等其他信息"
```

</details>

---

## 团餐

### `query-meal-assistance`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | BE编码（Business Entity Code） |
| `beType` | int |  | 固定传 6（企业团餐），此接口仅团餐场景使用 （枚举：6） |
| `orderType` | int |  | 到店自提场景: orderType=1 && beCode 是个无效参数，不要传，传了会报错 外送场景: orderType=2 && beCode 为delivery-query-address中的beCode 得来速(DT)场景：orderType=1 && beCode 为query-nearby-store中的beCode |
| `reservationDate` | string |  | 预约时间，仅当用户要预约下单时，该字段必传，格式形如 2020-08-08 09:30 |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |

<details><summary>完整说明</summary>

```text
Description: 仅支持企业团餐场景(beType=6)在calculate-price前需要获取当前门店可用的助餐服务
When：
- 企业团餐场景(beType=6)下，用户选完商品后、计算价格前
- 用户问"有什么助餐服务"、"团餐怎么送"
Preconditions：
- 仅企业团餐场景(beType=6)可用
- 已通过 delivery-query-stores 获取 storeCode 和 beCode
Input:
- storeCode: 门店编码，必填
- orderType 和 beCode 传递规则（根据用户选择的 beType 确定）：
到店自取(beType=1) → orderType=1，不传 beCode
得来速(beType=5)   → orderType=1，必传 beCode（从 query-nearby-stores 获取）
麦乐送(beType=2)   → orderType=2，必传 beCode（从 delivery-query-stores 获取）
团餐(beType=6)     → orderType=2，必传 beCode（从 delivery-query-stores 获取）
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
Next：
- 用户选择助餐服务后，将 gmServiceCode 传给 calculate-price
```

</details>

### `query-promotions`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `beCode` | string |  | 业务编码，与storeCode 配对使用，团餐场景必传（从 delivery-query-stores 获取） |
| `beType`* | int | ✅ | 业务类型，固定传 6（企业团餐） （枚举：6） |
| `orderType`* | int | ✅ | 订单类型，团餐场景固定传 2（外送） （枚举：2） |
| `reservationDate` | string |  | 预约场景必传，非预约场景不传。格式:yyyy-MM-dd HH:mm |
| `storeCode`* | string | ✅ | 门店编码（storeCode）, 不能为空 |

<details><summary>完整说明</summary>

```text
Description: 查询当前门店企业团餐场景下可用的促销规则（满减/满折），仅返回当前时间有效且适用在售餐品的规则原始数据
When：
- 企业团餐场景(beType=6)下，用户搭配方案前需要了解当前门店有哪些可用的促销活动/满减满折规则时
- 用户询问"有什么优惠"、"满多少减多少"、"打几折"时
Preconditions：
- 仅企业团餐场景(beType=6)可用
- 已通过 delivery-query-stores 获取 storeCode 和 beCode
Input:
- storeCode: 门店编码，必填
- beCode: 业务编码，团餐场景必传，与 storeCode 配对使用（从 delivery-query-stores 获取）
- orderType: 团餐场景固定传 2（外送）
- beType: 企业团餐固定传 6
- reservationDate: 预约场景必传，非预约场景不传。格式: yyyy-MM-dd HH:mm
Output:
- 返回当前门店有效的促销规则列表（原始结构），每条含 promotionId、promotionType、ruleCategory、beTypes、startTime、endTime、gmServiceCode、products、ruleDetail
- promotionType 含义：31-满额减，33-订单折扣
- ruleCategory 含义：30-满折/折扣，40-满减
- products 含义：适用餐品列表，type=1-包含、2-不包含、3-全部，productCode 为餐品编码
- 时间无效（已过期/未开始）或与在售餐品无交集的规则已被过滤
Next：
- 拿到规则后，由大模型自行根据规则解读优惠并计算搭配方案，工具不做最优推荐
```

</details>

---

## 派对与活动

### `campaign-calendar`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `specifiedDate` | string |  | 可选的查询基准日期（格式：yyyy-MM-dd）；若传入，则以该日为锚点，返回当天及时间线上与其最邻近的前后各一个有活动的日子（共三天）；若不填，默认返回当前月所有活动 |

<details><summary>完整说明</summary>

```text
查询麦当劳中国当月的营销活动日历，返回进行中、往期和未来日期的活动。适用于查看用户进行中和即将到来的可参与活动，还可查询用户对活动的订阅状态。
When：
  - 用户问"最近有什么活动"、"这个月有什么优惠活动"、"有什么可以参加的"
  - 用户想查看品鉴会、主题派对等活动信息
```

</details>

### `query-party-city`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `spuId`* | number | ✅ | spuId |

<details><summary>完整说明</summary>

```text
Description: 活动派对商品配置场次城市列表, 必须先确定spuId(从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取)
When：
- 用户询问"主题派对在哪些城市"
- 用户询问"我想参加主题派对"
- 用户询问"生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动"
Preconditions：
- 必须先确定spuId（从 mall-points-products 获取或从 mall-product-detail获取）
Input:
- spuId: spuId 需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId
```

</details>

### `query-party-store`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code`* | string | ✅ | 城市code |
| `latitude` | number |  | 纬度，从 query-party-city 返回结果的 data[].latitude 获取 |
| `longitude` | number |  | 经度，从 query-party-city 返回结果的 data[].longitude 获取 |
| `spuId` | number |  | spuId，从 mall-points-products 或 mall-product-detail 获取 |

<details><summary>完整说明</summary>

```text
Description: 查询指定城市下支持主题派对的门店列表。当用户选择了城市后，需要查看该城市有哪些门店可举办生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动时使用
Preconditions：
- 必须先通过 query-party-city 获取城市code和经纬度
- 必须先确定spuId（从 mall-points-products 获取或从 mall-product-detail获取）
Input:
- code: 城市code, 城市下的门店列表获取(query-party-city)
- latitude: 纬度, 城市下的门店列表获取(query-party-city)
- longitude: 经度, 城市下的门店列表获取(query-party-city)
- spuId: spuId, 从 mall-points-products 或 mall-product-detail 获取
```

</details>

### `query-party-store-date`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `spuId`* | number | ✅ | spuId |
| `storeCode`* | string | ✅ | 门店code |

<details><summary>完整说明</summary>

```text
Description: 查询指定门店支持生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动的可预约日期列表。当用户选择了门店后，需要查看该门店哪些日期可预约时使用。
When：
- 用户询问"这家店哪天可以预约"
- 用户询问"可预约日期"
- 用户询问"查看门店日历"
- 用户询问"哪天有场次"
- 用户选择门店后询问日期
Preconditions：
- 必须确定 spuId（从 mall-points-products 获取或从 mall-product-detail获取）
- 必须先通过 query-party-store 获取 storeCode
Input:
- storeCode: 门店code, 城市下的门店列表获取(query-party-store)
- spuId: spuId, 需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId
```

</details>

### `query-party-store-session`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `dateStr`* | string | ✅ | 门店日期 |
| `spuId`* | number | ✅ | spuId |
| `storeCode`* | string | ✅ | 门店code |

<details><summary>完整说明</summary>

```text
Description: 查询指定门店、指定日期下的生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动场次列表。当用户选择了日期后，需要查看当天有哪些场次可预约时使用。
When：
- 用户询问"查看主题活动场次列表"
- 用户询问"几点有场次"
Preconditions：
- 必须确定 spuId（从 mall-points-products 获取或从 mall-product-detail获取）
- 必须先通过 query-party-store 获取 storeCode
- 必须先通过 query-party-store-date 获取 dateStr
Input:
- spuId: spuId, 需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId
- storeCode: 门店code, 城市下的门店列表获取(query-party-store)
- dateStr: 门店日期, 城市下的门店列表获取(query-party-store-date)
```

</details>

### `party-order-create`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `code` | string |  | 城市code |
| `count` | int |  | count |
| `dateStr` | string |  | 店铺日期 |
| `id` | number |  | 场次Id |
| `leftNum` | int |  | 场次余位 |
| `partyTimeInfo` | object |  | 场次信息 |
| `partyType`* | int | ✅ | 派对类型，1-包场，2-拼团 |
| `skuId` | number |  | skuId |
| `spuId` | number |  | spuId |
| `storeCode` | string |  | 门店 |
| `timeEnd` | string |  | 场次结束时间 |
| `timeStart` | string |  | 场次开始时间 |

<details><summary>完整说明</summary>

```text
Description: 创建生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动, 仅支持shopId=5（从 mall-product-detail 获取）的调用，
  支持包场(partyType=1)、拼团(partyType=2)两种场景下单，必须先确认场次类型，必填 (1：包场，2：拼团)

When:
- 用户询问"生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动"
Preconditions：
- 仅支持shopId=5（从 mall-product-detail 获取）的调用
- 每一步完成后，必须等待用户明确选择，再继续下一步。不得跳步
Input:
- spuId: spuId, 需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的spuId（必填））
- skuId: 商品SKU ID，需要从查询可兑换商品列表（从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取）中让用户选择一个spu，获取对应的skuId（必填）
- partyType:
  派对类型（必填），判断规则：
  -若商品 partyType=1，则 partyType=1（仅包场）
  -若商品 partyType=2，则 partyType=2（仅拼团）
  -若商品 partyType=-1，需询问用户后确认（1：包场，2：拼团）
- code: 城市code，城市下的门店列表获取(query-party-city)（必填）
- storeCode: 门店code, 城市下的门店列表获取(query-party-store)（必填）
- dateStr: 门店日期, 城市下的门店列表获取(query-party-store-date)（必填）
- id: 场次id, 查询主题活动场次列表(query-party-store-session)（必填）
- timeStart: 场次开始时间, 查询主题活动场次列表(query-party-store-session)（必填）
- timeEnd: 场次结束时间, 查询主题活动场次列表(query-party-store-session)（必填）
- leftNum: 场次余位, 查询主题活动场次列表(query-party-store-session)（必填）
- count: 参与人数（必填）
Next：
- 引导用户："确认信息，可以说'创建订单'进行下单"
```

</details>

---

## 基础

### `now-time-info`

无入参。

<details><summary>完整说明</summary>

```text
获取当前时间信息 - 返回当前服务器的完整时间信息，包括：
- 时间戳（毫秒级）
- 格式化的日期时间
- 年月日信息
- 时区和UTC时间
在你不知道当前时间，并且用户需要指定日期查询活动日历的时候有用
```

</details>

---
