# -*- coding: utf-8 -*-
"""
apply_to_app.py —— DBS Solutions 层：通过 LumaX Flow 本地自动化接口（Automation Gateway），
把 blueprints 蓝图声明式搭建到正在运行的软件画布里。

- apply 不计费、不生成、幂等（按 ref upsert），可放心反复执行。
- 注意：apply 的 data 白名单不含 imageUrl，6 张输入卡搭好后需用户手动放入图片。

用法：  py apply_to_app.py [项目标题]
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
    title = sys.argv[1] if len(sys.argv) > 1 else spec["project_title"]

    cfg = json.loads(AGENT_JSON.read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{cfg['port']}/agent/v1"
    token = cfg["token"]

    ping = api(base, token, "GET", "/ping")
    assert ping.get("ok"), "接口未就绪"

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
    print("下一步：在画布上给 6 张输入卡放入你的图片，然后按组 ①→②→③→④ 运行。")


if __name__ == "__main__":
    main()
