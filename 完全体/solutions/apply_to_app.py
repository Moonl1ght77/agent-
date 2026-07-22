# -*- coding: utf-8 -*-
"""
apply_to_app.py —— DBS Solutions 层：通过 LumaX Flow 本地自动化接口（Automation Gateway），
把 blueprints 蓝图声明式搭建到正在运行的软件画布里。

- apply 不计费、不生成、幂等（按 ref upsert），可放心反复执行。
- 注意：apply 的 data 白名单不含 imageUrl，8 张输入卡搭好后需用户手动放入图片。

用法：  py apply_to_app.py [项目标题]                         # 新建项目并全量搭图
        py apply_to_app.py --project <id> --refs A3,C,QA      # 热更新已有项目的指定卡（仅content，不碰连线/图片）
前提：  软件正在运行、已登录、设置→自动化→本地自动化接口 已开启。
"""
import json
import sys
import urllib.request
from pathlib import Path

from build_lxf import load_spec, variant_from_argv, spec_from_argv, OPT_WITH_VALUE

HERE = Path(__file__).resolve().parent
BP = HERE.parent / "blueprints"
PROMPTS = BP / "prompts"
def _find_agent_json():
    """按 AGENTS.md 发现顺序找 agent.json（家机 D:/公司机 E:/APPDATA 回退），取第一个存在的。"""
    import os
    cands = [Path(r"D:\LumaXFlow\data\agent\agent.json"),
             Path(r"E:\LumaX Flow\data\agent\agent.json"),
             Path(os.environ.get("APPDATA", "")) / "com.ai-canvas.desktop" / "agent" / "agent.json"]
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError(
        "找不到 agent.json（LumaX Flow 没开或没开自动化接口？）。已查:\n  " + "\n  ".join(map(str, cands)))


AGENT_JSON = _find_agent_json()

DATA_WHITELIST = {"content", "model", "provider", "size", "resolution", "quality"}


def api(base, token, method, path, body=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def card_content(card):
    if card.get("promptFile"):
        return (PROMPTS / card["promptFile"]).read_text(encoding="utf-8").strip()
    return card.get("content", "")


def main():
    args = sys.argv[1:]
    spec = load_spec(variant_from_argv(args), spec_from_argv(args))
    pid = None
    only_refs = None
    if "--project" in args:
        pid = args[args.index("--project") + 1]
    if "--refs" in args:
        only_refs = set(args[args.index("--refs") + 1].split(","))

    cfg = json.loads(AGENT_JSON.read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{cfg['port']}/agent/v1"
    token = cfg["token"]

    ping = api(base, token, "GET", "/ping")
    assert ping.get("ok"), "接口未就绪"

    if pid and only_refs:
        # 热更新模式：只发指定卡的 ref+type+content（不碰连线/图片/其他卡，幂等安全）
        cards = [{"ref": c["ref"], "type": c["type"],
                  "data": {"content": card_content(c)}}
                 for c in spec["cards"] if c["ref"] in only_refs]
        assert len(cards) == len(only_refs), f"有 ref 不存在于蓝图: {only_refs - {c['ref'] for c in cards}}"
        applied = api(base, token, "POST", f"/projects/{pid}/apply", {"cards": cards})
        print(f"热更新成功: {sorted(only_refs)} -> 项目 {pid}")
        return

    pos = [a for i, a in enumerate(args)
           if not a.startswith("--") and (i == 0 or args[i - 1] not in OPT_WITH_VALUE)]
    title = pos[0] if pos else spec["project_title"]
    proj = api(base, token, "POST", "/projects", {"title": title})
    pid = proj["id"]
    print(f"已建项目: {title}  id={pid}")

    cards = []
    for c in spec["cards"]:
        data = {"content": card_content(c)}
        if c["type"] == "ai_chat":
            data.update(spec["defaults"]["chat"])
        elif c["type"] == "ai_image":
            data.update(spec["defaults"]["image"])
            data.update(c.get("data", {}))
        data = {k: v for k, v in data.items() if k in DATA_WHITELIST}
        cards.append({
            "ref": c["ref"], "type": c["type"], "title": c["title"],
            "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"],
            "data": data,
        })

    graph = {
        "cards": cards,
        "connections": [{"from": a, "to": b} for a, b in spec["connections"]],
        "groups": [{"ref": g["ref"], "title": g["title"], "color": g["color"],
                    "cardRefs": g["members"]} for g in spec["groups"]],
    }
    applied = api(base, token, "POST", f"/projects/{pid}/apply", graph)
    print(f"apply 成功: 卡片 {len(applied.get('cards', []))} | "
          f"连接 {len(applied.get('connections', []))} | 分组 {len(applied.get('groups', []))}")
    print("下一步：按画布左侧「①使用说明」卡给输入卡放图，然后按组 ①→②（查锁卡）→③→④ 运行。")


if __name__ == "__main__":
    main()
