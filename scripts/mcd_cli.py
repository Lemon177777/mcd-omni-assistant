#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦当劳 MCP 命令行工具 —— 纯 Python 标准库，零第三方依赖。

作用：在 MCP 客户端不可用 / 未授权时，直接以 HTTP 调用麦当劳官方 MCP Server
(https://mcp.mcd.cn)，完成 list / desc / call 三种操作。

用法:
    python mcd_cli.py list                       列出全部工具（名称 + 一句话说明）
    python mcd_cli.py list <关键字>              按关键字过滤工具
    python mcd_cli.py desc <工具名>              查看该工具的完整参数 schema
    python mcd_cli.py call <工具名> '<json入参>'  调用工具并打印结果
    python mcd_cli.py call <工具名>              等价于入参 {}
    python mcd_cli.py raw <method> '<json>'      发送任意 JSON-RPC 请求（调试用）

示例:
    python mcd_cli.py call now-time-info
    python mcd_cli.py call query-nearby-stores '{"beType":1,"searchType":1,"city":"北京"}'
    python mcd_cli.py call auto-bind-coupons
    python mcd_cli.py call query-meals '{"storeCode":"S001","orderType":1,"beType":1}'

Token 解析顺序:
    1. 环境变量 MCD_MCP_TOKEN（可写 "Bearer xxx" 或裸 token）
    2. 环境变量 MCD_MCP_CONFIG 指向的 JSON 文件
    3. ~/.workbuddy/mcp.json（WorkBuddy 默认配置）
    4. <项目根目录>/mcp.json、<当前工作目录>/mcp.json
    上述 JSON 均读取 mcpServers["mcd-mcp"].headers.Authorization

说明：
    - 默认绕过系统 HTTP 代理直连（部分环境代理会把请求拦成 502）。
    - 本脚本不保存、不打印 Token；请在本地配置，切勿把真实 Token 提交进仓库。

"""

import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("MCD_MCP_URL", "https://mcp.mcd.cn").rstrip("/")

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_CANDIDATES = [
    os.environ.get("MCD_MCP_CONFIG", "").strip(),
    os.path.join(os.path.expanduser("~"), ".workbuddy", "mcp.json"),
    os.path.normpath(os.path.join(_HERE, os.pardir, "mcp.json")),
    os.path.join(os.getcwd(), "mcp.json"),
]


def _token_from_config(path):
    """从 mcp.json 读取 mcd-mcp 的 Authorization；失败返回空串。"""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        srv = (cfg.get("mcpServers") or {}).get("mcd-mcp") or {}
        return ((srv.get("headers") or {}).get("Authorization") or "").strip()
    except Exception:
        return ""


def get_token():
    tok = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not tok:
        for path in CONFIG_CANDIDATES:
            if path and os.path.isfile(path):
                tok = _token_from_config(path)
                if tok:
                    break
    if not tok:
        tried = "\n    - ".join(p for p in CONFIG_CANDIDATES if p)
        sys.exit(
            "[错误] 未找到麦当劳 MCP Token。任选其一：\n"
            "    1) 设置环境变量 MCD_MCP_TOKEN=<你的token>\n"
            "    2) 准备一个 mcp.json（可用 MCD_MCP_CONFIG 指定路径），内含\n"
            "       mcpServers.mcd-mcp.headers.Authorization\n"
            "  已尝试的路径：\n    - %s\n"
            "  Token 获取：https://open.mcd.cn/mcp" % tried
        )
    return tok if tok.lower().startswith("bearer ") else "Bearer " + tok


def rpc(method, params=None, notify=False, rid=1):
    payload = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    if not notify:
        payload["id"] = rid
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", get_token())
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        resp = opener.open(req, timeout=90)
    except urllib.error.HTTPError as e:
        sys.exit("[HTTP %s] %s" % (e.code, e.read().decode("utf-8", "replace")[:800]))
    except Exception as e:
        sys.exit("[请求失败] %s" % e)
    return resp.read().decode("utf-8", "replace")


def parse(body):
    """解析 JSON 或 SSE(text/event-stream) 响应。"""
    msgs = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            chunk = line[5:].strip()
            try:
                msgs.append(json.loads(chunk))
            except Exception:
                pass
    if not msgs:
        try:
            msgs.append(json.loads(body))
        except Exception:
            pass
    return msgs


def handshake():
    """可选握手：某些 MCP Server 要求先 initialize。失败不阻断。"""
    try:
        rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "mcd-cli", "version": "1.0"}})
        rpc("notifications/initialized", {}, notify=True)
    except SystemExit:
        raise
    except Exception:
        pass


def need_result(msgs):
    """取第一个 result；若有 error 则退出。"""
    for m in msgs:
        if isinstance(m, dict) and m.get("error"):
            sys.exit("[MCP error] " + json.dumps(m["error"], ensure_ascii=False))
    for m in msgs:
        if isinstance(m, dict) and "result" in m:
            return m["result"]
    return None


def cmd_list(kw=None):
    handshake()
    res = need_result(parse(rpc("tools/list", {})))
    tools = (res or {}).get("tools") or []
    if not tools:
        sys.exit("[错误] 未获取到工具列表，请检查 Token 是否有效。")
    n = 0
    for t in tools:
        name = t.get("name", "")
        if kw and kw.lower() not in name.lower() and kw not in (t.get("description") or ""):
            continue
        first = (t.get("description") or "").replace("\n", " ").strip()
        first = first.split("|")[0]
        if len(first) > 70:
            first = first[:70] + "…"
        print("%-32s %s" % (name, first))
        n += 1
    print("\n共 %d 个工具%s。" % (n, "（关键字：%s）" % kw if kw else ""))


def cmd_desc(name):
    handshake()
    res = need_result(parse(rpc("tools/list", {})))
    for t in (res or {}).get("tools") or []:
        if t.get("name") == name:
            print("# " + name)
            print("\n" + (t.get("description") or "").strip())
            print("\n## inputSchema\n")
            print(json.dumps(t.get("inputSchema"), ensure_ascii=False, indent=2))
            return
    sys.exit("[错误] 未找到工具：%s（先执行 list 查看可用工具）" % name)


def cmd_call(name, args_json):
    try:
        args = json.loads(args_json) if args_json else {}
    except Exception as e:
        sys.exit("[入参不是合法 JSON] %s" % e)
    handshake()
    res = need_result(parse(rpc("tools/call", {"name": name, "arguments": args}, rid=2)))
    if res is None:
        sys.exit("[错误] 无返回结果")
    if isinstance(res, dict) and res.get("isError"):
        print("[工具返回错误]", file=sys.stderr)
    content = res.get("content") if isinstance(res, dict) else None
    if isinstance(content, list):
        for c in content:
            txt = c.get("text") if isinstance(c, dict) else None
            if txt is None:
                print(json.dumps(c, ensure_ascii=False, indent=2))
                continue
            try:
                print(json.dumps(json.loads(txt), ensure_ascii=False, indent=2))
            except Exception:
                print(txt)
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_raw(method, params_json):
    try:
        params = json.loads(params_json) if params_json else None
    except Exception as e:
        sys.exit("[params 不是合法 JSON] %s" % e)
    msgs = parse(rpc(method, params))
    for m in msgs:
        print(json.dumps(m, ensure_ascii=False, indent=2))


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    cmd = argv[0]
    if cmd == "list":
        cmd_list(argv[1] if len(argv) > 1 else None)
    elif cmd == "desc":
        if len(argv) < 2:
            sys.exit("用法: mcd_cli.py desc <工具名>")
        cmd_desc(argv[1])
    elif cmd == "call":
        if len(argv) < 2:
            sys.exit("用法: mcd_cli.py call <工具名> ['<json>']")
        cmd_call(argv[1], argv[2] if len(argv) > 2 else "")
    elif cmd == "raw":
        if len(argv) < 2:
            sys.exit("用法: mcd_cli.py raw <method> ['<json>']")
        cmd_raw(argv[1], argv[2] if len(argv) > 2 else "")
    else:
        sys.exit("未知命令：%s（可用：list / desc / call / raw）" % cmd)


if __name__ == "__main__":
    main()
