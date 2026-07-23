# -*- coding: utf-8 -*-
"""
paste_real_logo.py —— DBS Solutions 层：把真实 logo 贴回 AI 生成图，替换掉 AI 画的假字。

为什么要有它：生图模型不会写汉字（V13.2 实测，A1 拿到 600px 高清特写仍转写错字，
出图 logo 从"勉强能读"劣化到"纯乱码"）。提示词救不了能力边界，只能出图后用真像素替换。

流程（纯像素，无 AI）：
  1. 在目标图上定位 logo：紫色/彩色簇当种子 → 再把种子周围暗于布料的像素（灰色小字）圈进来
  2. 擦掉 AI 画的假 logo：该区域填布料底色 + 叠回原图低频光影（滤波擦不掉粗笔画，实测会留残影）
  3. 从真源图算"墨迹透过率"，只把墨迹以 alpha 贴上去——布料完全用目标图的，不贴方块

★ 边界（与 cutout_white 同）：离线图片工具，**不接进生图工作流**，不进 blueprints。

★ 适用前提（不满足就别用，会出洋相）：
  - logo 落在近似正对镜头的平面上（平铺/悬挂/折叠位都满足；强透视、大褶皱上的 logo 不行）
  - logo 是画面里最显著的深色/彩色簇（产品本身有深色印花或图案时会误定位）
  - 擦除区域的布料纹理会被抹平成纯色+光影，正常尺寸看不出，100% 放大看得出

用法：  py -X utf8 paste_real_logo.py <目标图> <logo真源图> <输出图>
        py -X utf8 paste_real_logo.py --batch <目标目录> <logo真源图> <输出目录>
        py -X utf8 paste_real_logo.py --selfcheck
调参：  --scale 1.24  贴片相对检测框的放大系数
        --erase 0.62  擦除范围相对完整 logo 框的外扩比例（留残影就调大）
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

WORK = 1000     # 定位用的缩图宽度


def _opt(args, name, default, cast=float):
    return cast(args[args.index(name) + 1]) if name in args else default


def color_seed_bbox(im, work=WORK):
    """彩色 logo 簇的外接框。判据=偏暗 + 蓝多于绿 + 非中性（本品牌是紫标；其它彩色标同理）。"""
    W, H = im.size
    sm = im.resize((work, int(work * H / W)), Image.LANCZOS)
    w, h = sm.size
    px = sm.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r + g + b < 560 and b > g + 6 and r > g:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None, None
    return (min(xs), min(ys), max(xs), max(ys)), (sm, W / w)


def full_logo_bbox(im, grow=1.6, dark=0.86, cap=0.7):
    """完整 logo 框（含非彩色小字）。只靠彩色簇会漏掉灰字，擦除不够就留残影（G3 实测）。

    ★ 必须夹紧（G1 实测惨案）：画面里比产品更暗的东西（亚麻背景、道具、阴影、缝线）
      同样满足"暗于布料"，不夹紧就会把背景圈进来，框炸开成一大片，擦除直接把产品抹平。
      两道保险：搜索窗只在种子框附近；结果按 cap 硬夹在种子框的有限外扩内。
    """
    seed, ctx = color_seed_bbox(im)
    if not seed:
        return None
    sm, k = ctx
    w, h = sm.size
    px = sm.load()
    sx0, sy0, sx1, sy1 = seed
    sw, sh = sx1 - sx0, sy1 - sy0
    cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    wx0, wy0 = max(0, int(cx - sw * grow)), max(0, int(cy - sh * grow))
    wx1, wy1 = min(w, int(cx + sw * grow)), min(h, int(cy + sh * grow))

    # 布料本色只从种子框紧邻的一圈取，别用整个搜索窗（窗里可能已经有背景）
    ring = [sum(px[x, y]) / 3
            for y in range(max(0, sy0 - 3), min(h, sy1 + 3))
            for x in (max(0, sx0 - 3), min(w - 1, sx1 + 2))]
    ring += [sum(px[x, y]) / 3
             for x in range(max(0, sx0 - 3), min(w, sx1 + 3))
             for y in (max(0, sy0 - 3), min(h - 1, sy1 + 2))]
    cloth = sorted(ring)[len(ring) // 2]

    xs, ys = [sx0, sx1], [sy0, sy1]
    for y in range(wy0, wy1):
        for x in range(wx0, wx1):
            if sum(px[x, y]) / 3 < cloth * dark:
                xs.append(x)
                ys.append(y)

    # 硬夹：无论找到什么，框都不许超过种子框的 cap 倍外扩
    bx0 = max(min(xs), int(sx0 - sw * cap))
    by0 = max(min(ys), int(sy0 - sh * cap))
    bx1 = min(max(xs), int(sx1 + sw * cap))
    by1 = min(max(ys), int(sy1 + sh * cap))
    return tuple(int(v * k) for v in (bx0, by0, bx1, by1))


def _expand(box, k, W, H):
    w, h = box[2] - box[0], box[3] - box[1]
    dx, dy = int(w * k), int(h * k)
    return (max(0, box[0] - dx), max(0, box[1] - dy),
            min(W, box[2] + dx), min(H, box[3] + dy))


def _edge_mean(im):
    """边缘环均值 = 纯布料底色（logo 不到边）。"""
    w, h = im.size
    b = max(2, w // 12)
    ring = [im.crop((0, 0, w, b)), im.crop((0, h - b, w, h)),
            im.crop((0, 0, b, h)), im.crop((w - b, 0, w, h))]
    px = [p for r in ring for p in r.getdata()]
    return [sum(p[i] for p in px) / len(px) for i in range(3)]


def paste(target_path, logo_src_path, out_path, scale=1.24, erase_pad=0.62):
    tgt = Image.open(target_path).convert("RGB")
    W, H = tgt.size
    seed, ctx = color_seed_bbox(tgt)
    if not seed:
        raise ValueError("目标图没找到 logo（彩色簇），跳过")
    k = ctx[1]
    tbox = tuple(int(v * k) for v in seed)

    # 1) 擦掉假 logo —— 只擦墨迹，不擦矩形。
    #    矩形硬擦（填底色/滤波）对框大小极敏感：框稍大就把腰头、缝线、产品边缘一起抹平（G1 实测惨案）。
    #    改成逐像素——只有暗于局部布料的像素才换成布料色，布料本身一个像素不动，框大小不再敏感。
    ebox = _expand(full_logo_bbox(tgt) or tbox, erase_pad, W, H)
    region = tgt.crop(ebox)
    rw, rh = ebox[2] - ebox[0], ebox[3] - ebox[1]
    fill = region.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
    rl, fl = region.load(), fill.load()
    ink = Image.new("L", (rw, rh))
    il = ink.load()
    for y in range(rh):
        for x in range(rw):
            p, c = rl[x, y], fl[x, y]
            d = max((c[i] - p[i]) / max(c[i], 1) for i in range(3))
            # 死区要够大：布料织纹的 d 约 0.03-0.08，死区太小会把纹理也算成墨迹，
            # 于是整个框被轻微提亮、框边界肉眼可见（实测）。logo 墨迹 d 远大于 0.12。
            il[x, y] = max(0, min(255, int((d - 0.12) * 700)))
    ink = ink.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    tgt.paste(fill, ebox, ink)

    # 2) 真源里的 logo 贴片 + 它的布料底色（用于算墨迹）
    src = Image.open(logo_src_path).convert("RGB")
    sseed, sctx = color_seed_bbox(src)
    if not sseed:
        raise ValueError("真源图没找到 logo")
    sbox = _expand(tuple(int(v * sctx[1]) for v in sseed), 0.12, *src.size)
    patch = src.crop(sbox)
    cloth = patch.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(8))

    tw = int((tbox[2] - tbox[0]) * scale)
    th = max(1, int(tw * patch.height / patch.width))
    patch = patch.resize((tw, th), Image.LANCZOS)
    cloth = cloth.resize((tw, th), Image.LANCZOS)

    # 3) 只贴墨迹：alpha = 布料底色比墨迹暗多少。布料处≈0，所以不会贴出色块
    pl, cw = patch.load(), cloth.load()
    alpha = Image.new("L", (tw, th))
    al = alpha.load()
    for y in range(th):
        for x in range(tw):
            p, c = pl[x, y], cw[x, y]
            d = max((c[i] - p[i]) / max(c[i], 1) for i in range(3))
            al[x, y] = max(0, min(255, int(d * 340)))

    cx, cy = (tbox[0] + tbox[2]) // 2, (tbox[1] + tbox[3]) // 2
    pos = (cx - tw // 2, cy - th // 2)
    tgt.paste(patch, pos, alpha)
    tgt.save(out_path, quality=95)
    return tbox, (tw, th)


def selfcheck():
    """最小自检：浅色布上画一个深紫假标 -> 贴上真标 -> 假标必须消失、真标必须出现。"""
    d = Path(__file__).parent
    fake, real, out = d / "_pl_fake.jpg", d / "_pl_real.jpg", d / "_pl_out.jpg"

    def make(path, ring, stray):
        """深色背景 + 浅色产品块 + 彩色圆环（彩色种子）。
        ★ 背景必须比产品暗：这正是 G1 惨案的条件（亚麻背景暗于产品→被当成 logo 圈进框
          →擦除把产品抹平）。自检不带这个条件就抓不到框炸开的 bug。
        stray=True 再画一条中性灰杠（不满足彩色判据、只能靠"暗于布料"被完整框吃到），
        它只存在于假图里，用来验证擦除真的生效。"""
        im = Image.new("RGB", (600, 400), (150, 140, 130))          # 暗背景
        dr = ImageDraw.Draw(im)
        dr.rectangle((120, 90, 480, 330), fill=(238, 225, 220))      # 浅色产品
        dr.ellipse((240, 170, 300, 230), outline=ring, width=6)
        if stray:
            dr.rectangle((250, 245, 290, 253), fill=(60, 60, 60))
        im.save(path, quality=95)

    make(fake, ring=(150, 110, 140), stray=True)     # 假标：浅紫环 + 独有灰杠
    make(real, ring=(80, 40, 75), stray=False)       # 真标：深紫环
    tbox, size = paste(fake, real, out)
    assert tbox[0] > 0 and tbox[2] > tbox[0], f"定位框不对: {tbox}"
    res = Image.open(out).convert("RGB")
    # 假图独有的灰杠必须被擦掉：它不满足彩色判据，只有完整框（暗于布料）才吃得到
    px = res.getpixel((270, 249))
    assert min(px) > 180, f"假 logo 的灰杠没擦干净，(270,249)={px}"
    # 圆环处必须换成真标的深色墨迹（贴上去了，而不是只擦不贴）
    ring_px = min(res.getpixel((243, 200)), res.getpixel((297, 200)), key=min)
    assert min(ring_px) < 120, f"真 logo 没贴上，圆环处={ring_px}"
    # ★ 擦除范围不许失控：产品边角必须原样保留（框炸开时这里会被填成纯色）
    for pt in ((130, 100), (470, 100), (130, 320), (470, 320)):
        px3 = res.getpixel(pt)
        assert abs(px3[0] - 238) < 12 and abs(px3[2] - 220) < 12, \
            f"擦除范围失控，产品边角 {pt} 被改成 {px3}"
    # 背景也不许被动过
    assert abs(res.getpixel((30, 30))[0] - 150) < 12, "背景被误擦"
    for f in (fake, real, out):
        f.unlink(missing_ok=True)
    print("selfcheck OK", tbox, size)


def main(args):
    if "--selfcheck" in args:
        return selfcheck()
    scale, erase = _opt(args, "--scale", 1.24), _opt(args, "--erase", 0.62)
    pos = [a for i, a in enumerate(args)
           if not a.startswith("--") and args[i - 1] not in ("--scale", "--erase")]

    if "--batch" in args:
        srcdir, logo, dstdir = Path(pos[0]), pos[1], Path(pos[2])
        dstdir.mkdir(parents=True, exist_ok=True)
        for f in sorted(srcdir.glob("*.jpg")):
            try:
                tbox, size = paste(f, logo, dstdir / f"{f.stem}_logo.jpg", scale, erase)
                print(f"  {f.name}  框{tbox} 贴片{size[0]}x{size[1]}")
            except Exception as e:
                print(f"  {f.name}  跳过: {e}")
    else:
        tbox, size = paste(pos[0], pos[1], pos[2], scale, erase)
        print(f"框 {tbox} 贴片 {size[0]}x{size[1]} -> {pos[2]}")


if __name__ == "__main__":
    main(sys.argv[1:])
