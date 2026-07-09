# -*- coding: utf-8 -*-
"""season_inventory.py —— DBS Solutions 层：整季白底图 款式 + 颜色清单。

纯像素分析，无AI、零幻觉、零串味。回答一个可靠的问题：
  这一季有哪些款、每款有几个配色、各是什么颜色。
（细节图/logo裁剪不在本工具职责内——那部分纯代码不够稳，由人自行裁切。）

它只做两件纯代码可靠的事：
  1. 把每张图分为 全身平铺 / 特写 —— 用四周白边占比（全身图四周留白多）。
  2. 对每款的全身图提主色、按主色归并出配色 —— 报出每款的配色数与颜色名+HEX。

用法：
  python season_inventory.py <整季根目录>
输出：<根目录>/_季度款色清单.txt（人可读）+ _季度款色清单.json（机器可读）
依赖：Pillow
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

try:
    from PIL import Image
except ImportError:
    sys.exit("缺少 Pillow：python -m pip install pillow --break-system-packages")

sys.stdout.reconfigure(encoding="utf-8")

THUMB_W = 400            # 分析缩略图宽度
WHITE_MIN = 235          # 近白阈值（min(R,G,B) 高于此视为白底）
BORDER_FRAC = 0.04       # 取四周 4% 边环采样白边占比
FULL_WHITE_RATIO = 0.55  # 边环白占比 ≥ 此值 → 判为全身平铺
COLORWAY_DIST = 42       # 两件全身图主色 RGB 距离 < 此值 → 同一配色
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

# 基础色名参考表（RGB）——最近邻命名，够电商配色描述用
COLOR_REF = {
    "黑": (28, 28, 30), "白": (242, 242, 240), "米白": (232, 226, 208),
    "浅灰": (188, 188, 190), "中灰": (140, 140, 142), "炭灰": (78, 80, 84),
    "藏青": (32, 42, 68), "蓝": (52, 96, 158), "浅蓝": (150, 185, 210),
    "墨绿": (40, 70, 55), "绿": (70, 120, 80), "军绿": (105, 110, 80),
    "棕": (78, 55, 44), "咖啡": (60, 45, 40), "卡其": (170, 148, 110),
    "红": (172, 52, 46), "酒红": (120, 45, 52), "橙": (205, 120, 55),
    "黄": (220, 180, 70), "紫": (95, 70, 120), "粉": (220, 170, 175),
}


def analyze(path):
    """返回 (shot_type, 主色RGB或None)。shot_type ∈ {'full','closeup'}。"""
    img = Image.open(path).convert("RGB")
    w0, h0 = img.size
    small = img.resize((THUMB_W, max(1, int(h0 * THUMB_W / w0))))
    W, H = small.size
    px = small.load()

    bw = max(2, int(W * BORDER_FRAC))
    bh = max(2, int(H * BORDER_FRAC))
    white = tot = 0
    for y in range(H):
        for x in range(W):
            if not (x < bw or x >= W - bw or y < bh or y >= H - bh):
                continue
            r, g, b = px[x, y]
            tot += 1
            if min(r, g, b) >= WHITE_MIN:
                white += 1
    shot = "full" if white / max(1, tot) >= FULL_WHITE_RATIO else "closeup"

    # 主色：中心 60% 区域内、排除近白背景的像素求均值
    rs = gs = bs = n = 0
    for y in range(int(H * 0.2), int(H * 0.8)):
        for x in range(int(W * 0.2), int(W * 0.8)):
            r, g, b = px[x, y]
            if min(r, g, b) >= WHITE_MIN:      # 跳过白底
                continue
            rs += r; gs += g; bs += b; n += 1
    color = (rs // n, gs // n, bs // n) if n else None
    return shot, color


def name_color(rgb):
    r, g, b = rgb
    best, bd = "?", 1e9
    for nm, (rr, gg, bb) in COLOR_REF.items():
        d = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
        if d < bd:
            bd, best = d, nm
    return best


def group_colorways(colors):
    """把多件全身图的主色按邻近距离归并成配色簇，返回 [(色名, HEX, 件数), ...]。"""
    clusters = []   # 每个: [sumR,sumG,sumB,count]
    for c in colors:
        placed = False
        for cl in clusters:
            cr, cg, cb = cl[0] / cl[3], cl[1] / cl[3], cl[2] / cl[3]
            if (c[0] - cr) ** 2 + (c[1] - cg) ** 2 + (c[2] - cb) ** 2 < COLORWAY_DIST ** 2:
                cl[0] += c[0]; cl[1] += c[1]; cl[2] += c[2]; cl[3] += 1
                placed = True
                break
        if not placed:
            clusters.append([c[0], c[1], c[2], 1])
    out = []
    for cl in sorted(clusters, key=lambda x: -x[3]):
        avg = (round(cl[0] / cl[3]), round(cl[1] / cl[3]), round(cl[2] / cl[3]))
        out.append((name_color(avg), "#%02X%02X%02X" % avg, cl[3]))
    return out


def process_style(folder):
    imgs = sorted(p for p in folder.iterdir()
                  if p.suffix.lower() in IMG_EXT and "_细节" not in p.stem)
    full_colors = []
    for p in imgs:
        try:
            shot, color = analyze(p)
        except Exception as e:
            print(f"  ⚠ 读图失败 {p.name}: {e}")
            continue
        if shot == "full" and color:
            full_colors.append(color)
    colorways = group_colorways(full_colors)
    return {
        "style": folder.name,
        "colorways": [{"name": nm, "hex": hx, "shots": n} for nm, hx, n in colorways],
        "n_full": len(full_colors),
        "n_total": len(imgs),
    }


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    root = Path([a for a in args if not a.startswith("--")][0])
    styles = sorted(p for p in root.iterdir() if p.is_dir())
    report = [process_style(f) for f in styles]

    lines = [f"# 季度款色清单  根目录：{root}",
             f"# 款数：{len(styles)}   每款列出配色（颜色名+HEX+该色全身图张数，通常正+背=2张/配色）",
             f"# 注：颜色名为最近邻命名供参考；条纹/花色款报的是主体底色。\n"]
    for r in report:
        cw = "  ｜  ".join(f"{c['name']} {c['hex']}({c['shots']}张)" for c in r["colorways"]) or "（无全身图，需人工检查）"
        lines.append(f"款 {r['style']}：{len(r['colorways'])} 个配色  →  {cw}")
    (root / "_季度款色清单.txt").write_text("\n".join(lines), encoding="utf-8")
    (root / "_季度款色清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    total_cw = sum(len(r["colorways"]) for r in report)
    print(f"OK 款色清单完成：{len(styles)}款 / 合计 {total_cw} 个配色 → {root / '_季度款色清单.txt'}")
    print("   （颜色名最近邻命名，请对着清单快速核一眼；细节图裁切按你自己流程做）")


if __name__ == "__main__":
    main()
