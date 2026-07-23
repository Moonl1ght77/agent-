# -*- coding: utf-8 -*-
"""
cutout_white.py —— DBS Solutions 层：深色背景的产品实拍图 → 纯白底产品图。

纯像素、无 AI、零幻觉：颜色 / logo / 版型 / 缝线全部是原片像素，不存在生成式漂移。
用途 = 给生图工作流产出可信的 IN1 输入图，以及直接可交付的白底 SKU 图底稿。

★ 边界（与 season_inventory 同）：这是离线图片工具，**不接进生图工作流**，
  不进 blueprints、不做节点。产物由人挑选后手动拖进画布输入卡。

做法：缩图上按亮度阈值二值化 → 从四边 flood fill 标出真背景（产品内部的暗缝线不会被误删）
     → 边缘内缩去掉阈值残留的深色描边 → 放大回原尺寸羽化 → 合成白底 → 按外接框裁成正方形。

前提：背景明显暗于产品（黑布/深色桌面拍浅色产品）。浅色产品拍在浅色背景上不适用。

用法：  py -X utf8 cutout_white.py <输入图> <输出图>
        py -X utf8 cutout_white.py --batch <输入目录> <输出目录> [--pattern IMG_11*.JPG]
        py -X utf8 cutout_white.py --selfcheck
调参：  --thresh 90   亮度阈值，产品偏暗时调低
        --size 2048   输出边长
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

WORK = 900          # 掩膜工作尺寸，够用且快
PAD = 0.04          # 产品外接框留白比例
FEATHER = 2.0       # 边缘羽化半径（原尺寸像素）
ERODE = 5           # 边缘内缩核；阈值边界必留一圈背景像素，不收边就是黑描边


def _opt(args, name, default, cast=int):
    return cast(args[args.index(name) + 1]) if name in args else default


def _keep_main_blob(mask: Image.Image):
    """只保留产品那一块，丢掉背景里的碎片（黑布上的拉链反光等亮斑）。

    从画面中心 flood fill：产品是主体，中心几乎必落在它身上。
    ponytail: 只认一块连通域。产品被拍成分离的两半时会丢一半，
    真出现（拍多件同框）就改成扫描所有连通域取最大的。
    """
    w, h = mask.size
    seed = None
    for dy in range(0, h // 3, 4):          # 中心不在前景就沿垂直方向找
        for y in (h // 2 - dy, h // 2 + dy):
            if 0 <= y < h and mask.getpixel((w // 2, y)) == 255:
                seed = (w // 2, y)
                break
        if seed:
            break
    if seed is None:
        return mask                          # 找不到种子就不动，交给下游判断
    filled = mask.copy()
    ImageDraw.floodfill(filled, seed, 200)
    return filled.point(lambda v: 255 if v == 200 else 0, mode="L")


def cutout(src: Path, dst: Path, thresh=90, size=2048):
    im = Image.open(src).convert("RGB")
    W, H = im.size

    small = im.convert("L").resize((WORK, int(WORK * H / W)), Image.LANCZOS)
    w, h = small.size
    binary = small.point(lambda v: 255 if v > thresh else 0, mode="L")

    # 从四边 flood fill：真背景连到画面边缘；产品内部的暗缝线/阴影不连边，不会被吃掉
    bg = binary.copy()
    for x in range(0, w, 8):
        for y in (0, h - 1):
            if bg.getpixel((x, y)) == 0:
                ImageDraw.floodfill(bg, (x, y), 128)
    for y in range(0, h, 8):
        for x in (0, w - 1):
            if bg.getpixel((x, y)) == 0:
                ImageDraw.floodfill(bg, (x, y), 128)

    mask = bg.point(lambda v: 0 if v == 128 else 255, mode="L")
    mask = mask.filter(ImageFilter.MedianFilter(5))
    mask = _keep_main_blob(mask)
    mask = mask.filter(ImageFilter.MinFilter(ERODE))
    mask = mask.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(FEATHER))

    white = Image.new("RGB", (W, H), "white")
    white.paste(im, mask=mask)

    box = mask.point(lambda v: 255 if v > 128 else 0).getbbox()
    if box is None:
        raise ValueError("掩膜为空：阈值不合适或背景不够暗")
    px, py = int((box[2] - box[0]) * PAD), int((box[3] - box[1]) * PAD)
    box = (max(0, box[0] - px), max(0, box[1] - py),
           min(W, box[2] + px), min(H, box[3] + py))
    crop = white.crop(box)
    side = max(crop.size)
    out = Image.new("RGB", (side, side), "white")
    out.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    out.resize((size, size), Image.LANCZOS).save(dst, quality=95)

    fill = (box[2] - box[0]) * (box[3] - box[1]) / (W * H)
    return box, fill


def selfcheck():
    """最小自检：暗背景上一块亮方块，抠完角落必须是白、外接框必须贴住方块。"""
    tmp = Path(__file__).with_name("_cutout_selfcheck_in.jpg")
    out = Path(__file__).with_name("_cutout_selfcheck_out.jpg")
    im = Image.new("RGB", (400, 400), (10, 10, 10))
    ImageDraw.Draw(im).rectangle((100, 100, 300, 300), fill=(230, 220, 215))
    im.save(tmp)
    box, _ = cutout(tmp, out, size=400)
    assert 60 < box[0] < 130 and 60 < box[1] < 130, f"外接框不对: {box}"
    corner = Image.open(out).convert("RGB").getpixel((10, 10))
    assert min(corner) >= 235, f"角落应为白底，实际 {corner}"   # JPEG 压缩会把纯白压到 240 上下
    tmp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    print("selfcheck OK", box)


def main(args):
    if "--selfcheck" in args:
        return selfcheck()

    thresh, size = _opt(args, "--thresh", 90), _opt(args, "--size", 2048)
    pos = [a for i, a in enumerate(args)
           if not a.startswith("--") and args[i - 1] not in ("--thresh", "--size", "--pattern")]

    if "--batch" in args:
        srcdir, dstdir = Path(pos[0]), Path(pos[1])
        pattern = _opt(args, "--pattern", "*.JPG", str)
        dstdir.mkdir(parents=True, exist_ok=True)
        files = sorted(srcdir.glob(pattern))
        print(f"批量 {len(files)} 张 -> {dstdir}")
        for f in files:
            try:
                box, fill = cutout(f, dstdir / f"{f.stem}_white.jpg", thresh, size)
                # 产品占比过小 = 多半是特写图或抠飞了，标出来让人复核
                flag = "  ← 占比小，请复核" if fill < 0.25 else ""
                print(f"  {f.name}  产品占画面 {fill:.0%}{flag}")
            except Exception as e:
                print(f"  {f.name}  失败: {e}")
    else:
        box, fill = cutout(Path(pos[0]), Path(pos[1]), thresh, size)
        print(f"外接框 {box} 产品占画面 {fill:.0%} -> {pos[1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
