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


def full_logo_bbox(im, grow=2.2, dark=0.90):
    """完整 logo 框（含非彩色小字）。只靠彩色簇会漏掉灰字，擦除不够就留残影（G3 实测）。"""
    seed, ctx = color_seed_bbox(im)
    if not seed:
        return None
    sm, k = ctx
    w, h = sm.size
    px = sm.load()
    sx0, sy0, sx1, sy1 = seed
    cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    sw, sh = (sx1 - sx0) * grow, (sy1 - sy0) * grow
    wx0, wy0 = max(0, int(cx - sw)), max(0, int(cy - sh))
    wx1, wy1 = min(w, int(cx + sw)), min(h, int(cy + sh))

    lum = sorted(sum(px[x, y]) / 3
                 for y in range(wy0, wy1, 2) for x in range(wx0, wx1, 2))
    cloth = lum[int(len(lum) * 0.75)]           # 偏亮分位 = 布料本色
    xs, ys = [sx0, sx1], [sy0, sy1]
    for y in range(wy0, wy1):
        for x in range(wx0, wx1):
            if sum(px[x, y]) / 3 < cloth * dark:
                xs.append(x)
                ys.append(y)
    return tuple(int(v * k) for v in (min(xs), min(ys), max(xs), max(ys)))


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

    # 1) 擦掉假 logo：实心填布料底色 + 叠回低频光影。滤波法对粗笔画会留残影，别用。
    ebox = _expand(full_logo_bbox(tgt) or tbox, erase_pad, W, H)
    region = tgt.crop(ebox)
    rw, rh = ebox[2] - ebox[0], ebox[3] - ebox[1]
    base = _edge_mean(region)
    low = region.filter(ImageFilter.GaussianBlur(rw / 3.5))
    low_mean = _edge_mean(low)
    cleaned = Image.new("RGB", (rw, rh))
    cl, ll = cleaned.load(), low.load()
    for y in range(rh):
        for x in range(rw):
            cl[x, y] = tuple(max(0, min(255, int(base[i] + ll[x, y][i] - low_mean[i])))
                             for i in range(3))
    # 羽化按短边算：logo 框都是扁的，按宽度算会让羽化吃掉大半个蒙版、中心擦不实
    em = Image.new("L", (rw, rh), 0)
    pad = max(2, min(rw, rh) // 14)
    ImageDraw.Draw(em).rectangle((pad, pad, rw - pad, rh - pad), fill=255)
    tgt.paste(cleaned, ebox, em.filter(ImageFilter.GaussianBlur(pad / 2.5)))

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
        """浅色布 + 一个彩色圆环（彩色种子）。
        stray=True 再画一条中性灰杠（不满足彩色判据、只能靠"暗于布料"被完整框吃到），
        它只存在于假图里，用来验证擦除真的生效。"""
        im = Image.new("RGB", (600, 400), (238, 225, 220))
        dr = ImageDraw.Draw(im)
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
