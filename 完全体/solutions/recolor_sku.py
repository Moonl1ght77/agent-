# -*- coding: utf-8 -*-
"""
recolor_sku.py —— DBS Solutions 层：把 AI 重绘白底图的颜色，用纯代码搬回真值。

为什么要它（2026-07-27 实锤的能力边界）：
  生图模型对**近白低色度**的织物有硬性归白倾向。浅蓝款喂进去 L*=80.7 / b*=-5.44（明确偏蓝），
  S1 吐出来 L*=92.7 / b*=+1.94 —— 不只是把色相压没，是**提亮 12 个 L* 往背景白靠、
  并把色相翻到暖侧**。提示词写死"不许中和成背景白"也拦不住，改输入（白平衡+加色度）也拦不住。
  结论同"生图模型不会写汉字"：这是能力边界，不是措辞问题，走真像素/真数值替换。

做法：S1 出形（形态、褶皱、光影、干净白底都归它），本工具只改颜色——
  从参考图量出布身真实 RGB，按三通道增益整体拉过去。增益是乘法，
  所以布料的相对明暗关系、织纹、褶皱阴影全部原样保留，只有色相和整体明度平移。
  背景用四角泛洪填充圈出来，不参与调色，纯白照旧。

★ 局限：
  - 参考图取样框默认是画面中心（横 35-65%、纵 35-55%），产品不在中间时用 --ref-box 指定。
  - 它对齐的是"参考图的颜色"。参考图本身不准（暖光没校正/没色卡），出来照样不准——
    先跑 wb_correct.py，或按 tech pack 的 PANTONE 号定目标（pantone_tcx.json 可反查）。
  - 只做整体平移，不修局部偏色。

用法：
  py -X utf8 recolor_sku.py <S1输出图> --ref <参考图> [--out 输出路径] [--keep-light]
                                       [--ref-box 0.35,0.35,0.65,0.55] [--selfcheck]
  --keep-light  只搬色相不搬明度（保留 S1 那种通透的亮度）。默认连明度一起搬回参考图的。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DEFAULT_BOX = (0.35, 0.35, 0.65, 0.55)


def mean_rgb(im, box):
    px = list(im.crop(box).getdata())
    n = len(px)
    return tuple(sum(p[i] for p in px) / n for i in range(3))


def background_mask(im, tol=18):
    """四角泛洪出纯白背景，返回 mask（255=背景）。产品内部的高光不会被误判为背景。"""
    flat = Image.new("L", im.size, 0)
    probe = im.convert("RGB").copy()
    w, h = im.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(probe, xy, (255, 0, 255), thresh=tol)
    flat.putdata([255 if p == (255, 0, 255) else 0 for p in probe.getdata()])
    return flat


def fabric_mean(im, bg):
    px, mk = list(im.getdata()), list(bg.getdata())
    sel = [p for p, m in zip(px, mk) if m == 0]
    if not sel:
        raise SystemExit("整张图都被判成背景了，检查 --tol 或这张图是不是白底")
    n = len(sel)
    return tuple(sum(p[i] for p in sel) / n for i in range(3)), n


def recolor(src: Path, ref: Path, dst: Path, ref_box=DEFAULT_BOX, keep_light=False):
    im = Image.open(src).convert("RGB")
    rf = Image.open(ref).convert("RGB")
    rw, rh = rf.size
    box = (int(rw * ref_box[0]), int(rh * ref_box[1]), int(rw * ref_box[2]), int(rh * ref_box[3]))
    target = mean_rgb(rf, box)

    bg = background_mask(im)
    cur, npx = fabric_mean(im, bg)

    if keep_light:  # 只搬色相：把目标缩放到当前的亮度水平
        s = sum(cur) / max(sum(target), 1e-6)
        target = tuple(c * s for c in target)

    gains = tuple(target[i] / max(cur[i], 1e-6) for i in range(3))
    tinted = im.point([min(255, int(i * gains[0])) for i in range(256)] +
                      [min(255, int(i * gains[1])) for i in range(256)] +
                      [min(255, int(i * gains[2])) for i in range(256)])
    out = Image.composite(im, tinted, bg)  # 背景保持原样（纯白），布料用调过色的
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, quality=95, subsampling=0)
    return cur, target, gains, npx


def selfcheck():
    """白底 + 一块中性灰方块，目标定成明确偏蓝；校正后方块应命中目标，背景必须仍是纯白。"""
    im = Image.new("RGB", (120, 120), (255, 255, 255))
    ImageDraw.Draw(im).rectangle([20, 20, 99, 99], fill=(200, 200, 200))
    ref = Image.new("RGB", (100, 100), (180, 190, 210))
    d = Path(__file__).parent
    ps, pr, po = d / "_rc_src.png", d / "_rc_ref.png", d / "_rc_out.png"
    im.save(ps); ref.save(pr)
    cur, target, gains, npx = recolor(ps, pr, po)
    got = Image.open(po).convert("RGB")
    px = got.getpixel((60, 60))
    corner = got.getpixel((2, 2))
    for p in (ps, pr, po):
        p.unlink()
    assert corner == (255, 255, 255), f"背景被染色了: {corner}"
    assert all(abs(px[i] - (180, 190, 210)[i]) <= 2 for i in range(3)), f"色块未命中目标: {px}"
    assert px[2] > px[0], f"蓝没搬过来: {px}"
    print(f"selfcheck OK  布料像素 {npx} 个 -> {px}（目标 180,190,210），背景 {corner}")


def main(argv):
    if "--selfcheck" in argv:
        selfcheck()
        return
    if not argv or "--ref" not in argv:
        print(__doc__)
        return
    src = Path(argv[0])
    ref = Path(argv[argv.index("--ref") + 1])
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else \
        src.with_name(src.stem + "_补色" + src.suffix)
    box = tuple(float(x) for x in argv[argv.index("--ref-box") + 1].split(",")) \
        if "--ref-box" in argv else DEFAULT_BOX
    cur, target, gains, npx = recolor(src, ref, out, box, "--keep-light" in argv)
    print(f"布料像素 {npx}")
    print(f"  当前 RGB=({cur[0]:.1f},{cur[1]:.1f},{cur[2]:.1f})")
    print(f"  目标 RGB=({target[0]:.1f},{target[1]:.1f},{target[2]:.1f})")
    print(f"  增益 R{gains[0]:.3f} G{gains[1]:.3f} B{gains[2]:.3f}")
    print(f"-> {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
