# -*- coding: utf-8 -*-
"""make_detail_crop.py —— DBS Solutions 层：从高清白底商品图裁出刺绣/Logo细节参考图。

纯像素裁剪，无AI、零幻觉——裁出来的就是原片真实细节，作为 IN3 细节参考喂给生图卡，
解决"多数款式没拍细节图 + 全身构图下小刺绣像素不足画错"的问题。

原理：在缩略图上找"高饱和度紧凑色块"（彩色刺绣在灰/白底服装上的特征），
过滤掉横贯全幅的条纹/罗纹（长宽比与占宽过滤），把命中区域映射回原图裁剪并留出上下文边距。

用法：
  python make_detail_crop.py <商品图>                      # 自动定位，输出 <商品图>_细节.jpg
  python make_detail_crop.py <商品图> --box 0.55,0.30,0.12,0.10   # 手动指定相对区域 x,y,w,h（0-1）
  python make_detail_crop.py --batch <目录>                # 目录下每个款式子文件夹取第一张jpg批量产出
依赖：Pillow（缺失时：python -m pip install pillow --break-system-packages）
"""
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("缺少 Pillow：python -m pip install pillow --break-system-packages")

sys.stdout.reconfigure(encoding="utf-8")

ANALYZE_W = 480          # 分析用缩略图宽度
SAT_MIN = 70             # 饱和度阈值（0-255）
VAL_MIN, VAL_MAX = 40, 245   # 亮度范围（排除纯黑纯白）
MAX_W_FRAC = 0.22        # 色块宽度超过图宽22% -> 视为条纹/装饰条，丢弃
MIN_AREA = 6             # 缩略图上最小像素数
PAD_SCALE = 2.2          # 裁剪框相对色块外扩倍数
OUT_MIN = 700            # 裁剪框最小边长（原图像素），保证细节图有上下文


def find_embroidery_box(img):
    """返回原图坐标系的 (x, y, w, h)，找不到返回 None。"""
    w0, h0 = img.size
    scale = ANALYZE_W / w0
    small = img.convert("RGB").resize((ANALYZE_W, int(h0 * scale)))
    hsv = small.convert("HSV")
    W, H = small.size
    px = hsv.load()

    mask = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            _, s, v = px[x, y]
            if s >= SAT_MIN and VAL_MIN <= v <= VAL_MAX:
                mask[y][x] = True

    seen = [[False] * W for _ in range(H)]
    best, best_score = None, 0.0
    for y in range(H):
        for x in range(W):
            if not mask[y][x] or seen[y][x]:
                continue
            stack, comp = [(x, y)], []
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < W and 0 <= ny < H and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(comp) < MIN_AREA:
                continue
            xs = [p[0] for p in comp]
            ys = [p[1] for p in comp]
            bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if bw > W * MAX_W_FRAC:          # 横贯的条纹/罗纹边
                continue
            sat_sum = sum(hsv.load()[p[0], p[1]][1] for p in comp)
            score = sat_sum * (len(comp) / (bw * bh + 1))   # 饱和度总量×紧凑度
            if score > best_score:
                best_score = score
                best = (min(xs), min(ys), bw, bh)
    if not best:
        return None
    bx, by, bw, bh = best
    return (int(bx / scale), int(by / scale), int(bw / scale), int(bh / scale))


def crop_with_context(img, box):
    x, y, w, h = box
    W, H = img.size
    side = max(int(max(w, h) * PAD_SCALE), OUT_MIN)
    cx, cy = x + w // 2, y + h // 2
    x1 = max(0, min(cx - side // 2, W - side))
    y1 = max(0, min(cy - side // 2, H - side))
    return img.crop((x1, y1, min(x1 + side, W), min(y1 + side, H)))


def process(path, rel_box=None, out=None):
    img = Image.open(path)
    if rel_box:
        rx, ry, rw, rh = rel_box
        W, H = img.size
        box = (int(rx * W), int(ry * H), int(rw * W), int(rh * H))
    else:
        box = find_embroidery_box(img)
        if not box:
            print(f"⚠ 未定位到高饱和色块（可能无彩色刺绣）：{path}  —— 请用 --box 手动指定")
            return None
    crop = crop_with_context(img, box)
    out = Path(out) if out else Path(path).with_name(Path(path).stem + "_细节.jpg")
    crop.convert("RGB").save(out, quality=95)
    print(f"OK {Path(path).name} -> {out.name}  (定位色块 {box[2]}x{box[3]}px，裁出 {crop.size[0]}x{crop.size[1]}px)")
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if "--batch" in args:
        root = Path(args[args.index("--batch") + 1])
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            jpgs = sorted(sub.glob("*.jpg")) + sorted(sub.glob("*.JPG"))
            if jpgs:
                process(jpgs[0])
        return
    rel_box = None
    if "--box" in args:
        rel_box = tuple(float(v) for v in args[args.index("--box") + 1].split(","))
    out = args[args.index("--out") + 1] if "--out" in args else None
    src = [a for i, a in enumerate(args)
           if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--box", "--out", "--batch"))][0]
    process(src, rel_box, out)


if __name__ == "__main__":
    main()
