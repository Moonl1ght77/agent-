# -*- coding: utf-8 -*-
"""
finish_sku.py —— DBS Solutions 层：S1 跑完之后的收尾，一条命令出成品白底 SKU 图。

它替代的手工步骤：回读画布拿 S1 出图 → 找对应的参考图 → recolor_sku 补色 → cutout_white 转白底 → 起名归档。

为什么颜色不交给画布上的 agent 做（2026-07-27 实测三次的结论）：
  ① LLM 读不出像素值，它只能"看着像浅绿"再写个色名；而色名这条通道本项目已证伪两次
     （A1 把淡藕写成 blush pink，下游放大成糖果粉）。
  ② 就算指令写准，渲染层也不照做——同一条内裤，输入 a*=-6.22/b*=+3.23，
     S1 输出 a*=-4.14/b*=+6.71，恒定往暖黄推。提示词三轮、白平衡输入、黑底、加分析卡，
     四种手段每次只挪一点，拦不住。
  所以颜色走代码：本工具直接量 INR 那张参考图的像素，一个色差都不差，且不需要人指定任何东西。

真源就在画布上：INR = 参考图（颜色真源），S1 = 形态真源。两张都从画布回读，无需传参。

用法：
  py -X utf8 finish_sku.py <projectId> [--out 输出目录] [--full-light] [--selfcheck]
  --full-light  连明度一起对齐参考图（默认只搬色相，保留 S1 的通透亮度）
输出：默认 E:\\Studio-Assets\\周周的内衣内裤项目\\内裤\\SKU白底图_V14最终\\，
     文件名自动按最接近的那张校正原片命名（比对缩略图找，不用人对号）。
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF_DIR = Path(r"E:\Studio-Assets\周周的内衣内裤项目\内裤\原片_白平衡校正")
OUT_DIR = Path(r"E:\Studio-Assets\周周的内衣内裤项目\内裤\SKU白底图_V14最终")
COLOR_NAMES = {"IMG_1178": "粉色", "IMG_1179": "米白色", "IMG_1180": "亮粉",
               "IMG_1181": "浅蓝色", "IMG_1182": "绿色", "IMG_1183": "微棕色"}


def _agent_json():
    import os
    for c in (Path(r"D:\LumaXFlow\data\agent\agent.json"),
              Path(r"E:\LumaX Flow\data\agent\agent.json"),
              Path(os.environ.get("APPDATA", "")) / "com.ai-canvas.desktop" / "agent" / "agent.json"):
        if c.exists():
            return json.loads(c.read_text(encoding="utf-8"))
    raise SystemExit("找不到 agent.json（LumaX Flow 没开？）")


def canvas_images(pid):
    """回读画布，返回 {ref: 本地图片路径}，只取 INR 和 S1。"""
    import urllib.request
    cfg = _agent_json()
    req = urllib.request.Request(
        f"http://127.0.0.1:{cfg['port']}/agent/v1/projects/{pid}/graph",
        headers={"Authorization": f"Bearer {cfg['token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        g = json.loads(r.read().decode("utf-8"))
    data_dir = Path(cfg["dataDir"])
    out = {}
    for c in g["cards"]:
        if c.get("ref") in ("INR", "S1"):
            url = (c.get("data") or {}).get("imageUrl")
            if url:
                out[c["ref"]] = data_dir / url.replace("/", "\\")
    return out


def thumb(p, n=48):
    return list(Image.open(p).convert("RGB").resize((n, n)).getdata())


def match_ref(inr_path):
    """把 INR 跟六张校正原片比缩略图，返回最像的那张（用它当颜色真源+命名依据）。"""
    if not REF_DIR.exists():
        return None, None
    a = thumb(inr_path)
    best, bd = None, None
    for f in sorted(REF_DIR.glob("IMG_*.JPG")):
        b = thumb(f)
        d = sum(abs(x[i] - y[i]) for x, y in zip(a, b) for i in range(3)) / len(a)
        if bd is None or d < bd:
            best, bd = f, d
    return best, bd


def run(script, *args):
    cmd = [sys.executable, "-X", "utf8", str(HERE / script), *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"{script} 失败:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def finish(s1_img, ref_img, out_path, keep_light=True):
    tmp = out_path.with_name(out_path.stem + "_tmp补色.png")
    args = [s1_img, "--ref", ref_img, "--out", tmp] + (["--keep-light"] if keep_light else [])
    print(run("recolor_sku.py", *args))
    print(run("cutout_white.py", tmp, out_path))
    tmp.unlink(missing_ok=True)


def selfcheck():
    """离线自检：造一张"黑底+中性灰产品"当 S1 出图、一张偏绿参考图，跑完整收尾链。"""
    d = HERE
    s1 = Image.new("RGB", (400, 400), (0, 0, 0))
    ImageDraw.Draw(s1).ellipse([80, 80, 319, 319], fill=(205, 205, 205))
    ref = Image.new("RGB", (200, 200), (185, 200, 188))          # 偏绿
    ps, pr, po = d / "_fs_s1.png", d / "_fs_ref.png", d / "_fs_out.png"
    s1.save(ps); ref.save(pr)
    finish(ps, pr, po)
    got = Image.open(po).convert("RGB")
    w, h = got.size
    corner, mid = got.getpixel((2, 2)), got.getpixel((w // 2, h // 2))
    for p in (ps, pr, po):
        p.unlink(missing_ok=True)
    assert corner == (255, 255, 255), f"背景不是纯白: {corner}"
    assert mid[1] > mid[0] and mid[1] > mid[2], f"绿没搬过来: {mid}"
    print(f"selfcheck OK  背景 {corner}  产品 {mid}（G 最高 = 绿色相已对齐参考图）")


def main(argv):
    if "--selfcheck" in argv:
        selfcheck()
        return
    pos = [a for a in argv if not a.startswith("--")]
    skip = {argv[i + 1] for i, a in enumerate(argv) if a == "--out" and i + 1 < len(argv)}
    pos = [a for a in pos if a not in skip]
    if not pos:
        print(__doc__)
        return
    pid = pos[0]
    outdir = Path(argv[argv.index("--out") + 1]) if "--out" in argv else OUT_DIR
    imgs = canvas_images(pid)
    if "S1" not in imgs:
        raise SystemExit("画布上 S1 还没出图")
    if "INR" not in imgs:
        raise SystemExit("画布上 INR 没放图——它是颜色真源，必须有")
    ref, dist = match_ref(imgs["INR"])
    if ref is None:
        raise SystemExit(f"找不到校正原片目录 {REF_DIR}，先跑 wb_correct.py")
    name = COLOR_NAMES.get(ref.stem, ref.stem)
    print(f"S1 出图 : {imgs['S1'].name}")
    print(f"颜色真源: {ref.name} -> 认作「{name}」(缩略图平均差 {dist:.1f})")
    if dist > 25:
        print("  ⚠ 差异偏大，确认一下 INR 放的是不是校正原片")
    outdir.mkdir(parents=True, exist_ok=True)
    finish(imgs["S1"], ref, outdir / f"{name}_{ref.stem}.png", "--full-light" not in argv)
    print(f"\n成品 -> {outdir / f'{name}_{ref.stem}.png'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
