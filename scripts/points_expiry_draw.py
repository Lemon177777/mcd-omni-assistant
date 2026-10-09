#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""积分到期止损 · 一键用「即将过期积分」抽奖。

策略：只消耗「本月将过期积分」(currentMouthExpirePoint) 去抽奖，抽到这部分积分
覆盖不了下一次为止就停，**不动用其他积分**。避免即将过期的积分白白浪费。

用法:
    python points_expiry_draw.py                                    # dry-run：给出「不溢出」「溢出」两方案
    python points_expiry_draw.py --yes                              # 执行「不溢出」方案
    python points_expiry_draw.py --yes --times 12 --allow-overflow  # 用户确认溢出后执行 12 次

★ 是否「溢出」（超出将过期积分、动用其他积分）属**用户决策**：
  脚本只摊开两套方案的代价，绝不自行选择；不加 --allow-overflow 一律拒绝溢出。

安全约束（遵守 MCP 官方要求，勿绕过）:
    1. 执行前必须展示本次活动消耗 drawDecision.nextConsumption；
    2. 每次抽奖间隔 1.2s，遇限流/失败**立即停止且不重试**；
    3. 默认次数 = floor(将过期积分 / 单次消耗)，不自动追加；超出须用户显式同意；
    4. 不加 --yes 时永远只做 dry-run。
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcd_cli as M  # noqa: E402  复用 MCP RPC 通道

DEC = json.JSONDecoder()


def extract_json(txt):
    best, bl, i = None, -1, 0
    while i < len(txt):
        j = txt.find("{", i)
        if j < 0:
            break
        try:
            obj, _ = DEC.raw_decode(txt[j:])
            s = len(json.dumps(obj))
            if s > bl:
                best, bl = obj, s
            i = j + 1
        except Exception:
            i = j + 1
    return best


RAW = {"t": ""}


def call(name, args=None):
    for m in M.parse(M.rpc("tools/call", {"name": name, "arguments": args or {}}, rid=2)):
        if m.get("error"):
            raise RuntimeError(json.dumps(m["error"], ensure_ascii=False))
        if "result" in m:
            c = m["result"].get("content") or []
            txt = c[0].get("text", "") if c else ""
            RAW["t"] = txt
            return extract_json(txt)
    raise RuntimeError("无返回结果：" + name)


def main():
    ap = argparse.ArgumentParser(description="用即将过期积分抽奖（到期止损）")
    ap.add_argument("--yes", action="store_true", help="真正执行（否则只出方案）")
    ap.add_argument("--times", type=int, default=None,
                    help="指定抽奖次数；默认=将过期积分可覆盖的次数（即不溢出）")
    ap.add_argument("--allow-overflow", action="store_true",
                    help="允许超出将过期积分、动用其他积分。**必须经用户明确同意才可加**")
    ap.add_argument("--interval", type=float, default=1.2, help="每次抽奖间隔秒数，默认 1.2")
    a = ap.parse_args()

    acct = call("query-my-account") or {}
    d = acct.get("data") or {}
    avail = float(d.get("availablePoint") or 0)
    exp = float(d.get("currentMouthExpirePoint") or 0)      # 本月将过期
    exp_next = float(d.get("nextMouthExpirePoint") or 0)    # 下月将过期

    info = call("query-lottery-info") or {}
    li = info.get("data") or {}
    dec = li.get("drawDecision") or {}
    nc = dec.get("nextConsumption") or {}
    cost = float(li.get("drawPoint") or 0)

    print("=" * 62)
    print("活动：%s（%s）" % (li.get("activityName"), li.get("activityStatusText")))
    print("有效期：%s → %s" % (li.get("beginTime"), li.get("endTime")))
    print("规则：%s   单次消耗：%g 积分" % (li.get("drawTypeText"), cost))
    print("-" * 62)
    print("当前可用积分：%g" % avail)
    print("本月将过期积分：%g   ← 本次要抢救的部分" % exp)
    print("下月将过期积分：%g" % exp_next)
    print("本次消耗说明：%s" % nc.get("text"))
    print("-" * 62)

    if not dec.get("resourceEligible"):
        print("✗ 资源不满足，不能抽奖：%s" % dec.get("reason"))
        return 1

    if cost <= 0:
        print("该活动不消耗积分（或规则非积分制），本脚本仅处理积分消耗型。")
        return 0

    base = int(exp // cost)                      # 完全由将过期积分承担的最大次数
    leftover = round(exp - base * cost, 2)
    print("方案 A（不溢出）：最多 %d 次（消耗 %g 分，全部由将过期积分承担）" % (base, base * cost))
    print("   将过期积分剩 %g 分 —— 不足单独抽 1 次，不处理会顺延到月底失效" % leftover)
    print("方案 B（溢出）  ：第 %d 次起需「其他积分」补足（当前可用 %g 分）" % (base + 1, avail))
    print("   扣减顺序：先扣将过期积分，不足部分才从其他积分扣（2026-10-09 实测确认）")
    print("   ⚠ 是否溢出、抽几次，由用户决定 —— 脚本不替你选。")

    n = a.times if a.times is not None else base

    if n > base and not a.allow_overflow:
        print("\n⚠ 你指定 %d 次 > 将过期积分能独立承担的 %d 次，这属于「溢出」。" % (n, base))
        print("  若要动用其他积分补足，请加 --allow-overflow 重跑；否则请把次数降到 %d 以内。" % base)
        return 2

    if n <= 0:
        print("\n将过期积分 %g 分不足一次消耗（%g）。" % (exp, cost))
        print("  可从其他积分（当前可用 %g 分）补足来抽，但需用户确认 —— 脚本不自行决定。" % avail)
        return 0

    total = n * cost
    used_exp = min(total, exp)                   # 先扣将过期积分，余下才由其他积分承担
    used_other = max(0, total - exp)
    print("\n拟定：抽 %d 次 ｜ 共消耗 %g 分 ｜ 其中将过期积分 %g 分%s ｜ 其他积分 %g 分"
          % (n, total, used_exp, "（全部用上）" if (exp > 0 and used_exp >= exp) else "", used_other))
    if not a.yes:
        print("[dry-run] 未执行任何抽奖。确认无误后加 --yes 执行。")
        return 0

    print("\n开始抽奖 …\n")
    wins, i = [], 0
    for i in range(1, n + 1):
        r = call("draw-lottery") or {}
        d = r.get("data") or {}                      # ⚠ 抽奖结果在 data 层下，不在顶层
        st = d.get("status") if isinstance(d.get("status"), dict) else {}
        code = st.get("code")
        if code != "SUCCESS":
            print("第 %d 次未成功：code=%s message=%s → 停止（不重试）" % (i, code, st.get("message")))
            break
        prizes = d.get("prizes") or []
        win = d.get("win")
        if prizes:
            names = "、".join(str(p.get("name")) for p in prizes if isinstance(p, dict))
            extra = "（有效期：%s）" % prizes[0].get("validDateInfo") if prizes[0].get("validDateInfo") else ""
            print("第 %d 次：中奖 → %s%s" % (i, names, extra))
        else:
            print("第 %d 次：未中奖（win=%s）" % (i, win))
        wins.append(r)
        if i < n:
            time.sleep(a.interval)

    print("\n共成功抽奖 %d 次" % len(wins))
    acct2 = call("query-my-account") or {}
    d2 = acct2.get("data") or {}
    print("抽后可用积分：%s   本月将过期：%s" % (d2.get("availablePoint"), d2.get("currentMouthExpirePoint")))
    print("提示：奖品到账情况可用 query-my-prizes 查看。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
