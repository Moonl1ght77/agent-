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

HERE = Path(__file__).resolve().parent
BP = HERE.parent / "blueprints"
PROMPTS = BP / "prompts"
AGENT_JSON = Path(r"E:\LumaX Flow\data\agent\agent.json")

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
    spec = json.loads((BP / "workflow_spec.json").read_text(encoding="utf-8"))

    args = sys.argv[1:]
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

    title = args[0] if args and not args[0].startswith("--") else spec["project_title"]
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
    print("下一步：在画布上给 8 张输入卡放入你的图片（图7无背面需求放主商品图副本、图8放版型上身参考），然后按组 ①→②→③→④ 运行。")


if __name__ == "__main__":
    main()
