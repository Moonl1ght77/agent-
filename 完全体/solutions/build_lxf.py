# -*- coding: utf-8 -*-
"""
build_lxf.py —— DBS Solutions 层：读取 blueprints 蓝图，生成 LumaX Flow .lxf 工程文件。

.lxf = Zip(store) 包，内含：
  canvas.json    卡片/连接/分组（导出形态，字段格式对拍自素材A V8.2）
  manifest.json  元信息与计数
  media/images/  输入卡示例占位图（用户导入后替换）

用法：  py build_lxf.py
输出：  E:\\Projects\\agent全自动生图\\V9.0完全体8分镜.lxf
"""
import json
import shutil
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BP = HERE.parent / "blueprints"
PROMPTS = BP / "prompts"
# 示例占位图来源：素材A解压目录（构建时复制进包）
MEDIA_SRC = Path(r"C:\Users\Administrator\AppData\Local\Temp\claude\E--Projects-agent-----\17e199f4-39d7-4cb4-bccd-cdcfc4a4411c\scratchpad\lxf_extract\media\images")
OUT_LXF = HERE.parent.parent / "V9.1定制版8分镜.lxf"

CHAT_DEFAULT = {}
IMAGE_DEFAULT = {}


def load_spec():
    spec = json.loads((BP / "workflow_spec.json").read_text(encoding="utf-8"))
    global CHAT_DEFAULT, IMAGE_DEFAULT
    CHAT_DEFAULT = spec["defaults"]["chat"]
    IMAGE_DEFAULT = spec["defaults"]["image"]
    return spec


def card_content(card):
    """content 优先级：promptFile > content 字段 > 空串。"""
    if card.get("promptFile"):
        return (PROMPTS / card["promptFile"]).read_text(encoding="utf-8").strip()
    return card.get("content", "")


def build_data(card):
    """按卡类型组装 data（JSON 字符串），字段集合对拍素材A导出格式。"""
    t = card["type"]
    content = card_content(card)
    if t in ("text", "sticky_note"):
        data = {"content": content}
    elif t == "ai_chat":
        data = {"_showLabel": True, "content": content}
        data.update(CHAT_DEFAULT)
    elif t == "ai_image":
        data = {"_showLabel": True, "content": content}
        data.update(IMAGE_DEFAULT)
        data.update(card.get("data", {}))
        if card.get("media"):
            data["imageUrl"] = f"media/images/{card['media']}"
    else:
        raise ValueError(f"未支持的卡片类型: {t}")
    return json.dumps(data, ensure_ascii=False)


def main():
    spec = load_spec()
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    created_at = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    updated_at = now.strftime("%Y-%m-%d %H:%M:%S")

    # ---- 校验 1：ref 唯一、连接端点存在 ----
    refs = [c["ref"] for c in spec["cards"]]
    assert len(refs) == len(set(refs)), "存在重复 ref"
    ref_set = set(refs)
    for a, b in spec["connections"]:
        assert a in ref_set and b in ref_set, f"连接端点不存在: {a}->{b}"

    # ---- 校验 2：无环（平台引擎禁环）----
    from collections import defaultdict, deque
    indeg = {r: 0 for r in refs}
    adj = defaultdict(list)
    for a, b in spec["connections"]:
        adj[a].append(b)
        indeg[b] += 1
    q = deque([r for r in refs if indeg[r] == 0])
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    assert seen == len(refs), "工作流存在环，平台无法拓扑排序"

    # ---- 生成卡片 ----
    id_of = {r: str(uuid.uuid4()) for r in refs}
    cards = []
    for c in spec["cards"]:
        cards.append({
            "id": id_of[c["ref"]],
            "project_id": project_id,
            "type": c["type"],
            "x": c["x"], "y": c["y"],
            "width": c["w"], "height": c["h"],
            "z_index": 1, "locked": False, "collapsed": False, "color": None,
            "title": c["title"],
            "data": build_data(c),
            "created_at": created_at,
            "updated_at": updated_at,
        })

    # ---- 生成连接（数组顺序 = 槽位顺序，与提示词前缀严格一致）----
    connections = [{
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "source_card_id": id_of[a],
        "target_card_id": id_of[b],
        "created_at": created_at,
    } for a, b in spec["connections"]]

    # ---- 生成分组（含成员包围盒）----
    pos = {c["ref"]: c for c in spec["cards"]}
    groups = []
    PAD = 60
    for g in spec["groups"]:
        xs = [pos[m]["x"] for m in g["members"]]
        ys = [pos[m]["y"] for m in g["members"]]
        x2 = [pos[m]["x"] + pos[m]["w"] for m in g["members"]]
        y2 = [pos[m]["y"] + pos[m]["h"] for m in g["members"]]
        groups.append({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "card_ids": json.dumps([id_of[m] for m in g["members"]]),
            "title": g["title"],
            "color": g["color"],
            "collapsed": False,
            "x": min(xs) - PAD, "y": min(ys) - PAD,
            "width": max(x2) - min(xs) + 2 * PAD,
            "height": max(y2) - min(ys) + 2 * PAD,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    canvas = {"cards": cards, "connections": connections, "groups": groups}

    # ---- 媒体清单 ----
    media_files = sorted({c["media"] for c in spec["cards"] if c.get("media")})
    for m in media_files:
        assert (MEDIA_SRC / m).exists(), f"找不到示例图: {m}"

    manifest = {
        "format_version": 1,
        "app_version": spec["app_version"],
        "exported_at": datetime.now().astimezone().isoformat(),
        "project": {"title": spec["project_title"], "thumbnail": None},
        "counts": {
            "cards": len(cards),
            "connections": len(connections),
            "groups": len(groups),
            "media": len(media_files),
            "media_missing": 0,
        },
    }

    # ---- 打包（store，无压缩，对拍素材A）----
    OUT_LXF.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_LXF, "w", zipfile.ZIP_STORED) as z:
        for m in media_files:
            z.write(MEDIA_SRC / m, f"media/images/{m}")
        z.writestr("canvas.json", json.dumps(canvas, ensure_ascii=False, indent=1))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))

    # ---- 回读自检 ----
    with zipfile.ZipFile(OUT_LXF) as z:
        cv = json.loads(z.read("canvas.json"))
        mf = json.loads(z.read("manifest.json"))
        assert len(cv["cards"]) == mf["counts"]["cards"]
        assert len(cv["connections"]) == mf["counts"]["connections"]
        names = set(z.namelist())
        for m in media_files:
            assert f"media/images/{m}" in names

    print(f"OK 已生成: {OUT_LXF}")
    print(f"   卡片 {len(cards)} | 连接 {len(connections)} | 分组 {len(groups)} | 媒体 {len(media_files)}")


if __name__ == "__main__":
    sys.exit(main())
