# -*- coding: utf-8 -*-
"""
collect_outputs.py —— DBS Solutions 层：把某一天 AI 生成的图从画布里收集到一个文件夹。

为什么需要它：出图只存在画布上，Joe 常忘了导出；而且**画布只显示当前那一版**，
重跑一次旧版就从卡片上消失了——但文件还在 media 目录里。本工具连被覆盖的旧版一起收。

判定规则（2026-07-29 踩出来的，别改坏）：
  · 产出 = 被蓝图里的生图卡（GS / GS1 / S1 / SKU1-6）引用过的文件
  · 拖进来的 = 被输入卡（IN*/INR）或"用户拖图产生的游离卡"（ref 是一串 uuid）引用的文件
  · 同一张图两边都占（Joe 把产出拖回输入槽当图源）→ **算产出**
  · 今天有、但谁都没引用的 → 是被重跑覆盖掉的旧版，也收，标注"已被覆盖"
  ★ 卡片产出在 `data.results` / `data.imageUrl`，**不在卡片顶层的 results**——踩过这个坑。

用法：
  py -X utf8 collect_outputs.py [--date 2026-07-29] [--out 目录] [--selfcheck]
默认日期=今天，默认输出目录 E:\\Studio-Assets\\周周的内衣内裤项目\\内裤\\成品_<日期>\\
只读+复制，不改画布、不删 media 里的原文件。
"""
import json
import os
import shutil
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

from PIL import Image

GEN_REFS = {"GS", "GS1", "S1"} | {f"SKU{i}" for i in range(1, 7)}
OUT_BASE = Path(r"E:\Studio-Assets\周周的内衣内裤项目\内裤")
KIND = {(1792, 2400): "场景图3比4", (2048, 2048): "白底或单件1比1"}


def _agent_json():
    for c in (Path(r"D:\LumaXFlow\data\agent\agent.json"),
              Path(r"E:\LumaX Flow\data\agent\agent.json"),
              Path(os.environ.get("APPDATA", "")) / "com.ai-canvas.desktop" / "agent" / "agent.json"):
        if c.exists():
            return json.loads(c.read_text(encoding="utf-8"))
    raise SystemExit("找不到 agent.json（LumaX Flow 没开？）")


def _get(cfg, path):
    req = urllib.request.Request(f"http://127.0.0.1:{cfg['port']}/agent/v1{path}",
                                 headers={"Authorization": f"Bearer {cfg['token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def card_urls(card):
    """一张卡引用的所有图片 url：产出历史 data.results 优先，再加当前 data.imageUrl。"""
    d = card.get("data") or {}
    out = [r["url"] for r in (d.get("results") or []) if isinstance(r, dict) and r.get("url")]
    if d.get("imageUrl"):
        out.append(d["imageUrl"])
    return out


def classify(cards_by_project):
    """返回 (产出文件 -> (画布标签, 卡ref), 拖进来的文件集合)。cards_by_project: [(标签, [卡])]"""
    owner, dragged = {}, set()
    for tag, cards in cards_by_project:
        for card in cards:
            ref = card.get("ref") or ""
            for u in card_urls(card):
                name = u.rsplit("/", 1)[-1]
                if ref in GEN_REFS:
                    owner.setdefault(name, (tag, ref))
                else:
                    dragged.add(name)
    return owner, dragged - set(owner)


def main(argv):
    day = date.fromisoformat(argv[argv.index("--date") + 1]) if "--date" in argv else date.today()
    outdir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_BASE / f"成品_{day}"

    cfg = _agent_json()
    projects = _get(cfg, "/projects")
    plist = projects if isinstance(projects, list) else projects.get("projects", [])
    per_project = []
    for p in plist:
        try:
            g = _get(cfg, f"/projects/{p['id']}/graph")
        except Exception as e:
            print(f"  跳过 {p.get('title','')}：{e}")
            continue
        per_project.append((p.get("title", "").split("-")[0].strip(), g.get("cards", [])))
    owner, dragged = classify(per_project)

    media = Path(cfg["dataDir"]) / "media" / "images"
    rows = []
    for f in media.iterdir():
        if not f.is_file() or f.name in dragged:
            continue
        ts = f.stat().st_mtime
        if date.fromtimestamp(ts) != day:
            continue
        try:
            with Image.open(f) as im:
                wh = im.size
        except Exception:
            continue
        rows.append((ts, f, wh))
    rows.sort()

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"{day} AI 生成的图 {len(rows)} 张\n")
    for i, (ts, f, wh) in enumerate(rows, 1):
        tag, ref = owner.get(f.name, ("已被覆盖", KIND.get(wh, f"{wh[0]}x{wh[1]}")))
        dst = outdir / f"{i:02d}_{datetime.fromtimestamp(ts):%H%M}_{tag}_{ref}.jpg"
        shutil.copy2(f, dst)
        mark = "" if f.name in owner else "   ← 旧版，画布上已看不到"
        print(f"  {datetime.fromtimestamp(ts):%H%M}  {wh[0]}x{wh[1]:<5} "
              f"{f.stat().st_size/1024:6.0f}KB  ->  {dst.name}{mark}")
    print(f"\n输出目录：{outdir}")


def selfcheck():
    """离线自检：只测分类规则这段真逻辑，不连网关。"""
    cards = [
        {"ref": "GS", "data": {"results": [{"url": "media/images/a.jpg"}], "imageUrl": "media/images/b.jpg"}},
        {"ref": "IN1", "data": {"imageUrl": "media/images/c.jpg"}},
        {"ref": "INR", "data": {"imageUrl": "media/images/b.jpg"}},          # 产出被拖回输入槽
        {"ref": "7092ae0d-189e-4316-8dac-2ecd83fa43e3", "data": {"imageUrl": "media/images/d.jpg"}},  # 游离卡
        {"ref": "S1", "data": {"results": [], "imageUrl": "media/images/e.jpg"}},
    ]
    owner, dragged = classify([("V14.9", cards)])
    assert set(owner) == {"a.jpg", "b.jpg", "e.jpg"}, owner
    assert owner["a.jpg"] == ("V14.9", "GS") and owner["e.jpg"] == ("V14.9", "S1"), owner
    assert dragged == {"c.jpg", "d.jpg"}, dragged      # b.jpg 两边都占 -> 算产出，不在这里
    assert card_urls({"data": {"results": [{"url": "x"}], "imageUrl": "y"}}) == ["x", "y"]
    assert card_urls({"results": [{"url": "顶层的不算"}], "data": {}}) == []
    print("selfcheck OK  产出3张(含被拖回输入槽的1张) / 拖进来的2张(输入卡+游离卡) / 顶层 results 正确忽略")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        main(sys.argv[1:])
