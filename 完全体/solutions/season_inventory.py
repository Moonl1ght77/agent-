# -*- coding: utf-8 -*-
"""season_inventory.py —— DBS Solutions 层：整季白底图批量分拣 + 每款输入清单生成。

纯像素分析，无AI、零幻觉、零串味。解决"整季N款、每款十几张白底图，人工挑正面/背面/
细节图喂6个输入槽"的重复劳动——把它变成一条命令产出可人工复核的清单。

它只做两件确定性的事，绝不替人拍板：
  1. 把每张图分类为 全身平铺 / 特写(细节·五金) —— 用白边占比（全身图四周留白多，特写填满画面）。
  2. 对每款自动定位并裁出彩色logo/刺绣细节图（复用 make_detail_crop.find_embroidery_box）。
前后正背由人眼5秒确认（清单里列出所有全身图候选并标注"请确认front/back"），
因为纯代码分不清正背=可能串味，宁可交给人（组间检查点原则）。

用法：
  python season_inventory.py <整季根目录>              # 扫描每个款文件夹，产出清单
  python season_inventory.py <整季根目录> --crop        # 同时把logo细节图裁到各款文件夹
输出：<根目录>/_季度清单.txt（人可读）+ _季度清单.json（机器可读，供后续批量用）
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

# 复用细节裁剪逻辑，禁止复制（防工具层双份维护）
from make_detail_crop import find_embroidery_box, crop_with_context

sys.stdout.reconfigure(encoding="utf-8")

THUMB_W = 400            # 分析缩略图宽度
WHITE_MIN = 235          # 近白阈值（min(R,G,B) 高于此视为白底）
BORDER_FRAC = 0.04       # 取四周 4% 边环采样白边占比
FULL_WHITE_RATIO = 0.55  # 边环白占比 ≥ 此值 → 判为全身平铺（四周留白）
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")


def analyze(path):
    """返回 (shot_type, 特征字典)。shot_type ∈ {'full','closeup'}。"""
    img = Image.open(path).convert("RGB")
    w0, h0 = img.size
    small = img.resize((THUMB_W, max(1, int(h0 * THUMB_W / w0))))
    W, H = small.size
    px = small.load()

    # 边环白占比
    bw = max(2, int(W * BORDER_FRAC))
    bh = max(2, int(H * BORDER_FRAC))
    white = tot = 0
    for y in range(H):
        for x in range(W):
            on_border = x < bw or x >= W - bw or y < bh or y >= H - bh
            if not on_border:
                continue
            r, g, b = px[x, y]
            tot += 1
            if min(r, g, b) >= WHITE_MIN:
                white += 1
    border_white = white / max(1, tot)

    # 中心块明度（判深浅色，供曝光双保护路由）
    cx0, cx1 = int(W * 0.35), int(W * 0.65)
    cy0, cy1 = int(H * 0.35), int(H * 0.65)
    lum_sum = n = 0
    for y in range(cy0, cy1):
        for x in range(cx0, cx1):
            r, g, b = px[x, y]
            lum_sum += (r * 299 + g * 587 + b * 114) // 1000
            n += 1
    center_lum = lum_sum / max(1, n)

    shot = "full" if border_white >= FULL_WHITE_RATIO else "closeup"
    tone = "dark" if center_lum < 90 else "light" if center_lum > 200 else "mid"
    return shot, {
        "px": f"{w0}x{h0}",
        "portrait": h0 > w0,
        "border_white": round(border_white, 2),
        "center_lum": int(center_lum),
        "tone": tone,
    }


def color_logo_check(img, box):
    """判断检出框是不是真品牌彩色logo（紧凑·中等大小·多色相簇），
    而非文字/条纹/纯色/JPEG噪点。返回 (是否彩色logo, 色相簇数)。
    实测品牌小花在4480px宽原图里约70-130px（1.5-3%）；<1%是噪点、>8%是条纹或大图。"""
    x, y, w, h = box
    img_w = img.size[0]
    if not (max(30, img_w * 0.01) <= w <= img_w * 0.08):   # 尺寸闸
        return False, 0
    crop = img.convert("HSV").crop((x, y, x + w, y + h)).resize((40, 40))
    bins, sat_px = set(), 0
    for hh, s, v in crop.getdata():
        if s > 75 and 40 < v < 245:
            sat_px += 1
            bins.add(hh // 30)          # 12 个色相桶
    return (len(bins) >= 3 and sat_px >= 60), len(bins)


def process_style(folder, do_crop):
    imgs = sorted(p for p in folder.iterdir()
                  if p.suffix.lower() in IMG_EXT and "_细节" not in p.stem)
    fulls, closeups = [], []
    for p in imgs:
        try:
            shot, feat = analyze(p)
        except Exception as e:
            print(f"  ⚠ 读图失败 {p.name}: {e}")
            continue
        (fulls if shot == "full" else closeups).append((p, feat))

    # logo细节：只在全身图里找（细节特写的吊牌/水洗标/五金反光会误触发多色）
    crop_src = crop_box = None
    is_color = False
    clusters = 0
    for p, _ in fulls:
        im = Image.open(p)
        box = find_embroidery_box(im)
        if box:
            ok, nb = color_logo_check(im, box)
            if ok:                       # 命中真彩色logo，锁定
                crop_src, crop_box, is_color, clusters = p, box, True, nb
                break
            if crop_src is None:         # 记住第一个弱检出做兜底展示
                crop_src, crop_box, clusters = p, box, nb

    category = "彩色刺绣款" if is_color else "文字/纯色款"
    crop_out = None
    if is_color and crop_src and do_crop:
        out = crop_src.with_name(crop_src.stem + "_细节.jpg")
        crop_with_context(Image.open(crop_src).convert("RGB"), crop_box).save(out, quality=95)
        crop_out = out.name

    tones = [f["tone"] for _, f in fulls] or [f["tone"] for _, f in closeups]
    main_tone = max(set(tones), key=tones.count) if tones else "unknown"
    return {
        "style": folder.name,
        "category": category,
        "full_shots": [{"file": p.name, **f} for p, f in fulls],
        "closeups": [{"file": p.name, **f} for p, f in closeups],
        "logo_found": crop_src.name if (is_color and crop_src) else None,
        "logo_crop": crop_out,
        "hue_clusters": clusters,
        "main_tone": main_tone,
        "n_total": len(imgs),
    }


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    root = Path([a for a in args if not a.startswith("--")][0])
    do_crop = "--crop" in args
    styles = sorted(p for p in root.iterdir() if p.is_dir())

    report = [process_style(f, do_crop) for f in styles]
    color = [r for r in report if r["category"] == "彩色刺绣款"]
    text = [r for r in report if r["category"] != "彩色刺绣款"]

    lines = [f"# 季度素材分拣清单  根目录：{root}",
             f"# 款数：{len(styles)}   full=全身平铺候选 / closeup=细节特写；front/back请人工确认",
             f"# 建议分线（彩色logo已裁图供1秒复核，非最终判定）：",
             f"#   彩色刺绣款 {len(color)} 个 → 走V11刺绣线（IN3放裁出的_细节图）：{[r['style'] for r in color]}",
             f"#   文字/纯色款 {len(text)} 个 → 走文字印花线/卖点后期贴：{[r['style'] for r in text]}\n"]
    for r in report:
        lines.append(f"── 款 {r['style']}  【{r['category']}】 色相簇{r['hue_clusters']}  共{r['n_total']}张  主色调{r['main_tone']}")
        lines.append(f"   全身平铺候选（{len(r['full_shots'])}张，从中选 IN2正面/IN3背面）：")
        for s in r["full_shots"]:
            lines.append(f"      {s['file']}  {s['px']}  {'竖' if s['portrait'] else '横'}  白边{s['border_white']}  {s['tone']}")
        lines.append(f"   细节特写（{len(r['closeups'])}张）：{', '.join(s['file'] for s in r['closeups']) or '无'}")
        if r["category"] == "彩色刺绣款":
            lines.append(f"   彩色logo：{r['logo_found']}" + (f"  → 已裁 {r['logo_crop']}" if r['logo_crop'] else "  （加 --crop 生成细节图）"))
        else:
            lines.append(f"   彩色logo：无（文字/纯色款——卖点走后期贴图，或如需细节用 make_detail_crop --box 手动指定）")
        lines.append("")

    (root / "_季度清单.txt").write_text("\n".join(lines), encoding="utf-8")
    (root / "_季度清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK 分拣完成：{len(styles)}款 → {root / '_季度清单.txt'}")
    print(f"   自动分线：彩色刺绣款 {len(color)}（{[r['style'] for r in color]}）")
    print(f"            文字/纯色款 {len(text)}（{[r['style'] for r in text]}）")
    if do_crop:
        print(f"   已裁细节图：{sum(1 for r in report if r['logo_crop'])} 款")
    miss = [r['style'] for r in report if not r['full_shots']]
    if miss:
        print(f"   ⚠ 无全身候选需人工检查的款：{miss}")


if __name__ == "__main__":
    main()
