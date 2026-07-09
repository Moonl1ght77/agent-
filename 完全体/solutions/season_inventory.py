# -*- coding: utf-8 -*-
"""season_inventory.py —— DBS Solutions 层：整季白底图 款式 + 颜色清单（PANTONE TCX比对）。

纯像素分析，无AI、零幻觉、零串味。回答：这一季有哪些款、每款几个配色、各对应哪个PANTONE。

它只做纯代码可靠的事：
  1. 把每张图分为 全身平铺 / 特写 —— 用四周白边占比（全身图四周留白多）。
  2. 对每款全身图提真实主色HEX（像素·可信），按主色归并配色。
  3. 每个配色的主色 → 最近邻 PANTONE TCX 服装色（Lab ΔE 感知色差），给出 色号+官方色名+ΔE。
     颜色命名全部来自真实数据集 pantone_tcx.json，禁止代码自造色名。

诚实边界（电商下单前务必知道）：
  - 真实HEX可信；但"照片→PANTONE色号"本质是近似——受棚拍灯光/白平衡/屏幕校准影响。
  - ΔE 是匹配可信度：<2难辨 / 2-5接近 / 5-10可感差异 / >10仅供缩小范围。
  - 下单以工厂 tech pack 官方色号或实物色卡为准；本清单用于快速盘点，不作最终色号依据。
  - 细节图/logo裁剪不在本工具职责内（纯代码不稳），由人自行裁切。

用法：
  python season_inventory.py <整季根目录>
输出：<根目录>/_季度款色清单.txt（人可读）+ _季度款色清单.json（机器可读）
依赖：Pillow；同目录 pantone_tcx.json（TCX/TPG 2310色，源 github Margaret2/pantone-colors）
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

HERE = Path(__file__).resolve().parent
# PANTONE 服装色参考表（TCX/TPG，2310色）。来源：github Margaret2/pantone-colors（公开近似值，
# 非官方授权）。颜色命名以此为底层真源，禁止代码自造色名。照片→色号本质是近似，需实物色卡复核。
PANTONE_FILE = HERE / "pantone_tcx.json"

THUMB_W = 400            # 分析缩略图宽度
WHITE_MIN = 235          # 近白阈值（min(R,G,B) 高于此视为白底）
BORDER_FRAC = 0.04       # 取四周 4% 边环采样白边占比
FULL_WHITE_RATIO = 0.55  # 边环白占比 ≥ 此值 → 判为全身平铺
COLORWAY_DIST = 42       # 两件全身图主色 RGB 距离 < 此值 → 同一配色
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def rgb_to_lab(rgb):
    """sRGB(0-255) → CIE Lab（D65）。纯确定性公式，供 ΔE 感知色差用。"""
    def f_inv(c):
        c /= 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = (f_inv(v) for v in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722)
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def load_pantone():
    """加载 TCX 参考表 → [(code, name, (r,g,b), lab), ...]。"""
    d = json.loads(PANTONE_FILE.read_text(encoding="utf-8"))
    table = []
    for code, rec in d.items():
        hx = rec["hex"].lstrip("#")
        rgb = (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
        table.append((code, rec["name"], rgb, rgb_to_lab(rgb)))
    return table


_PANTONE = None


def nearest_pantone(rgb):
    """给一个真实主色RGB，返回 (TCX码, 色名, 参考hex, ΔE76色差)。ΔE越小越接近。"""
    global _PANTONE
    if _PANTONE is None:
        _PANTONE = load_pantone()
    lab = rgb_to_lab(rgb)
    best, bd = None, 1e18
    for code, name, prgb, plab in _PANTONE:
        d = (lab[0] - plab[0]) ** 2 + (lab[1] - plab[1]) ** 2 + (lab[2] - plab[2]) ** 2
        if d < bd:
            bd, best = d, (code, name, "#%02X%02X%02X" % prgb)
    return best[0], best[1], best[2], round(bd ** 0.5, 1)


def _sat(c):
    """相对饱和度 = 色度/最亮通道。深色低饱和即近黑，浅色需更高饱和才算有色（感知均匀）。"""
    mx = max(c)
    return 0.0 if mx == 0 else (mx - min(c)) / mx


def compatible(a, b):
    """一个中性色(近灰/黑/白)一个有色，绝不归为同一配色——分开黑与暗酒红/藏青这类深色，
    同时不误拆带冷调的浅白（用相对饱和度而非绝对色度）。"""
    na, nb = _sat(a) < 0.12, _sat(b) < 0.12
    ca, cb = _sat(a) >= 0.18, _sat(b) >= 0.18
    return not ((na and cb) or (nb and ca))


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


def group_colorways(colors):
    """把多件全身图的主色按邻近距离归并成配色簇，返回 [每配色dict, ...]。"""
    clusters = []   # 每个: [sumR,sumG,sumB,count]
    for c in colors:
        placed = False
        for cl in clusters:
            avg = (cl[0] / cl[3], cl[1] / cl[3], cl[2] / cl[3])
            dist2 = (c[0] - avg[0]) ** 2 + (c[1] - avg[1]) ** 2 + (c[2] - avg[2]) ** 2
            if dist2 < COLORWAY_DIST ** 2 and compatible(c, avg):
                cl[0] += c[0]; cl[1] += c[1]; cl[2] += c[2]; cl[3] += 1
                placed = True
                break
        if not placed:
            clusters.append([c[0], c[1], c[2], 1])
    out = []
    for cl in sorted(clusters, key=lambda x: -x[3]):
        avg = (round(cl[0] / cl[3]), round(cl[1] / cl[3]), round(cl[2] / cl[3]))
        code, name, ref_hex, de = nearest_pantone(avg)
        out.append({
            "true_hex": "#%02X%02X%02X" % avg,   # 从像素提的真实主色（可信）
            "pantone_tcx": code, "pantone_name": name,
            "pantone_hex": ref_hex, "deltaE": de,  # 最近邻TCX + 色差（越小越准）
            "shots": cl[3],
        })
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
    return {
        "style": folder.name,
        "colorways": group_colorways(full_colors),
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

    lines = [f"# 季度款色清单（PANTONE TCX 服装色比对）  根目录：{root}",
             f"# 款数：{len(styles)}   每款每配色：真实HEX（像素提取·可信） → 最近PANTONE TCX + 色名 + ΔE色差",
             f"# ΔE越小越接近：<2肉眼难辨/2-5接近/5-10可感差异/>10仅供缩小范围。照片推色号本质是近似，",
             f"#   下单前请以工厂tech pack官方色号或实物为准。数据源：github Margaret2/pantone-colors。\n"]
    for r in report:
        lines.append(f"款 {r['style']}：{len(r['colorways'])} 个配色")
        for c in r["colorways"]:
            flag = "" if c["deltaE"] <= 5 else ("  ⚠匹配较远仅参考" if c["deltaE"] > 10 else "  (中等)")
            lines.append(f"    {c['true_hex']}({c['shots']}张) → PANTONE {c['pantone_tcx']} {c['pantone_name']}"
                         f"  ΔE={c['deltaE']}{flag}")
        if not r["colorways"]:
            lines.append("    （无全身图，需人工检查）")
    (root / "_季度款色清单.txt").write_text("\n".join(lines), encoding="utf-8")
    (root / "_季度款色清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    total_cw = sum(len(r["colorways"]) for r in report)
    far = sum(1 for r in report for c in r["colorways"] if c["deltaE"] > 10)
    print(f"OK 款色清单完成：{len(styles)}款 / 合计 {total_cw} 个配色 → {root / '_季度款色清单.txt'}")
    print(f"   PANTONE TCX最近邻比对；ΔE>10（匹配较远仅参考）的配色数：{far}")
    print("   照片推色号是近似，下单以官方tech pack色号/实物为准。")


if __name__ == "__main__":
    main()
