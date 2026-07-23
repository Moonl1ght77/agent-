# -*- coding: utf-8 -*-
"""
make_logo_stamp.py —— 从产品实拍图里提取 logo，做成一张「透过率印章」PNG。

印章 = 白底 + 墨迹（transmittance = 像素 / 局部布料底色）。
它的用途是在 Photoshop 里用【正片叠底】贴到目标图上：
  白色区域(255) 相乘后不改变底图 → 布料纹理原样透上来；
  墨迹区域 <255 → 按原始浓淡压暗，像印在布上，而不是贴一块图片上去。

同时把印章旋正：真源多半是手持斜拍的，斜着贴上去一眼假。
测角用投影法——文字行水平时，逐行墨迹量的方差最大（比 PCA 主轴可靠得多，
PCA 对"圆环+文字"这种图形估出来的角度是错的，实测转完更歪）。

用法：  py -X utf8 make_logo_stamp.py <产品图(白底或浅底)> <输出印章.png> [--pad 0.12]
        py -X utf8 make_logo_stamp.py --selfcheck
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from paste_real_logo import color_seed_bbox, full_logo_bbox, _expand


def _ink_mask(patch):
    """墨迹强度图：局部布料底色比该像素暗多少。"""
    cloth = patch.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(8))
    pl, cl = patch.load(), cloth.load()
    w, h = patch.size
    m = Image.new("L", (w, h))
    ml = m.load()
    for y in range(h):
        for x in range(w):
            p, c = pl[x, y], cl[x, y]
            d = max((c[i] - p[i]) / max(c[i], 1) for i in range(3))
            ml[x, y] = max(0, min(255, int(d * 340)))
    return m, cloth


def _deskew_angle(mask, span=14.0, step=0.5):
    """文字行水平时逐行墨迹量方差最大 —— 扫一遍角度取最大者。"""
    best, best_var = 0.0, -1.0
    a = -span
    while a <= span:
        r = mask.rotate(a, Image.BILINEAR, fillcolor=0)
        w, h = r.size
        rl = r.load()
        rows = [sum(rl[x, y] for x in range(0, w, 2)) for y in range(h)]
        mean = sum(rows) / len(rows)
        var = sum((v - mean) ** 2 for v in rows) / len(rows)
        if var > best_var:
            best, best_var = a, var
        a += step
    return best


def make_alpha_png(src_path, out_path, pad=0.12, deskew=True):
    """输出透明底 PNG：只有 logo 墨迹，没有布料。PS 里拖进去直接用，不用管混合模式。

    墨色要从布上「反解」出来，不能直接拿原像素：
    半透明边缘的像素是 墨×a + 布×(1-a) 混出来的，直接用会带一圈粉色布底。
    反解公式 color = (像素 - 布色×(1-a)) / a，得到的是纯墨色。
    """
    src = Image.open(src_path).convert("RGB")
    box = _logo_box(src, pad)
    patch = src.crop(box)
    mask, cloth = _ink_mask(patch)

    tight = mask.point(lambda v: 255 if v > 150 else 0).getbbox()
    if tight:
        m = int(max(tight[2] - tight[0], tight[3] - tight[1]) * 0.06)
        box = (box[0] + max(0, tight[0] - m), box[1] + max(0, tight[1] - m),
               box[0] + min(patch.width, tight[2] + m),
               box[1] + min(patch.height, tight[3] + m))
        patch = src.crop(box)
        mask, cloth = _ink_mask(patch)

    angle = _deskew_angle(mask) if deskew else 0.0
    w, h = patch.size
    pl, cl, ml = patch.load(), cloth.load(), mask.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ol = out.load()
    # 软阈值：布料织纹的 ink 值约 10-30、褶皱阴影能到 50-80，都必须归零，
    # 否则透明 PNG 里会带着一整块半透明的布（实测）。墨迹本身远高于 70。
    lo, hi = 70, 200
    for y in range(h):
        for x in range(w):
            a = ml[x, y]
            a = 0 if a <= lo else min(255, int((a - lo) / (hi - lo) * 255))
            if a < 6:                       # 布料，纯透明
                continue
            af = a / 255.0
            p, c = pl[x, y], cl[x, y]
            col = tuple(max(0, min(255, int((p[i] - c[i] * (1 - af)) / af)))
                        for i in range(3))
            ol[x, y] = col + (a,)

    if abs(angle) > 0.25:
        out = out.rotate(angle, Image.BICUBIC, expand=True)
    bb = out.getbbox()
    if bb:
        out = out.crop(bb)
    out.save(out_path)
    return box, angle, out.size


def _logo_box(src, pad):
    seed, ctx = color_seed_bbox(src)
    if not seed:
        raise ValueError("没找到 logo（彩色簇）")
    box = full_logo_bbox(src) or tuple(int(v * ctx[1]) for v in seed)
    return _expand(box, pad, *src.size)


def make_stamp(src_path, out_path, pad=0.12, deskew=True):
    src = Image.open(src_path).convert("RGB")
    seed, ctx = color_seed_bbox(src)
    if not seed:
        raise ValueError("没找到 logo（彩色簇）")
    box = full_logo_bbox(src) or tuple(int(v * ctx[1]) for v in seed)
    box = _expand(box, pad, *src.size)
    patch = src.crop(box)

    mask, cloth = _ink_mask(patch)
    # 按真实墨迹收紧到 logo 本身：检测框会带进大片空白布料，
    # 框松了印章就带着一大块布，Multiply 时把布纹也压到目标图上 = "贴了块布"的痕迹
    # 阈值要高：布料褶皱的阴影也暗于布料底色，阈值低了框会被阴影撑大
    tight = mask.point(lambda v: 255 if v > 150 else 0).getbbox()
    if tight:
        m = int(max(tight[2] - tight[0], tight[3] - tight[1]) * 0.06)
        box = (box[0] + max(0, tight[0] - m), box[1] + max(0, tight[1] - m),
               box[0] + min(patch.width, tight[2] + m),
               box[1] + min(patch.height, tight[3] + m))
        patch = src.crop(box)
        mask, cloth = _ink_mask(patch)

    angle = _deskew_angle(mask) if deskew else 0.0

    # 透过率：像素 / 布料底色，落到白底上
    pl, cl = patch.load(), cloth.load()
    w, h = patch.size
    stamp = Image.new("RGB", (w, h), "white")
    sl = stamp.load()
    for y in range(h):
        for x in range(w):
            p, c = pl[x, y], cl[x, y]
            t = [min(255, int(255 * p[i] / max(c[i], 1))) for i in range(3)]
            # 弱墨迹=布料织纹，一律归白。留着的话 Multiply 会把真源的织纹压到目标布上，
            # 目标那块就多出一层别的布纹 = 一眼看出贴过
            sl[x, y] = (255, 255, 255) if min(t) > 225 else tuple(t)

    if abs(angle) > 0.25:
        stamp = stamp.rotate(angle, Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    stamp.save(out_path)
    return box, angle, stamp.size


def selfcheck():
    """造一张倾斜的假 logo：印章必须被转正（残余角接近 0）、白底必须是白的。"""
    d = Path(__file__).parent
    tmp, out = d / "_stamp_in.jpg", d / "_stamp_out.png"
    im = Image.new("RGB", (700, 500), (150, 140, 130))
    dr = ImageDraw.Draw(im)
    dr.rectangle((120, 90, 580, 410), fill=(236, 224, 218))
    dr.ellipse((250, 210, 310, 270), outline=(110, 70, 100), width=6)
    for i in range(3):                                   # 三行“文字”
        dr.rectangle((330, 215 + i * 22, 470, 223 + i * 22), fill=(45, 45, 55))
    im.rotate(-7, Image.BICUBIC, fillcolor=(150, 140, 130)).save(tmp, quality=95)

    box, angle, size = make_stamp(tmp, out)
    assert abs(angle - 7) < 3.0, f"测角不对，应≈7°，实得 {angle:.1f}°"
    st = Image.open(out).convert("RGB")
    assert min(st.getpixel((2, 2))) > 240, f"印章底不是白的：{st.getpixel((2,2))}"
    darkest = min(min(p) for p in st.getdata())
    assert darkest < 150, f"印章里没有墨迹，最暗 {darkest}"
    tmp.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    print(f"selfcheck OK  测角 {angle:.1f}°  印章 {size[0]}x{size[1]}")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        args = sys.argv[1:]
        pad = float(args[args.index("--pad") + 1]) if "--pad" in args else 0.12
        pos = [a for i, a in enumerate(args)
               if not a.startswith("--") and args[i - 1] != "--pad"]
        fn = make_alpha_png if "--alpha" in args else make_stamp
        box, angle, size = fn(pos[0], pos[1], pad)
        kind = "透明PNG" if "--alpha" in args else "印章"
        print(f"logo 框 {box}  旋正 {angle:+.1f}°  {kind} {size[0]}x{size[1]} -> {pos[1]}")
