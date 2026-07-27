# -*- coding: utf-8 -*-
"""
wb_correct.py —— DBS Solutions 层：暖光实拍原片的白平衡校正（纯代码，零幻觉）。

为什么要它：ins 桌搭那种暖光环境会把浅色织物的冷色相压没（2026-07-27 实锤，
浅蓝款原片 b*=+3.5 偏黄，校正后 b*=-3.6 才现出蓝）。喂给生图卡的图颜色不对，
出图颜色就不对——生图模型只会忠实还原它看到的东西，不会替你把蓝找回来。

原理：取画面最亮 pct% 像素当白点（书页/白键盘/白纸这类中性物），
按最大通道归一算增益，只补不压——不整体提亮，只把偏色拉回中性。

★ 局限（写清楚，别当色卡用）：这是"照片白平衡"，不是"实物色准"。
  它保证的是"去掉光源色偏后照片该是什么样"，不保证等于实物颜色。
  真要色准还是得拍摄时放灰卡，或按 tech pack 的 PANTONE 号校（pantone_tcx.json 可反查）。
  画面里没有中性白物体时（全暖木色台面），白点估计会失效，输出会偏冷——目视核对一眼。

用法：
  py -X utf8 wb_correct.py <文件或目录> [--out 输出目录] [--pct 1.0] [--chroma 1.0] [--selfcheck]
输出：默认写到 <输入目录>_白平衡校正\，同名文件。

--chroma 是留给人眼的旋钮：白平衡只还原"照片去色偏后的样子"，这批浅色织物校正后色度仍只有
C*≈3-5（很淡），生图模型容易再压没。目视觉得该更明显时才往上调（1.4 / 1.6 试），
**调多少要看着实物定，不要凭想象加**——这一步是主观增强，不是色准。
"""
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def white_gains(im, pct=1.0):
    """取最亮 pct% 像素当白点，返回 (Gr, Gg, Gb)，按最大通道归一（只补不压）。"""
    w, h = im.size
    small = im.resize((200, max(1, int(200 * h / w))))
    px = sorted(small.getdata(), key=lambda t: -(t[0] + t[1] + t[2]))
    top = px[: max(1, int(len(px) * pct / 100))]
    n = len(top)
    wr, wg, wb = (sum(t[i] for t in top) / n for i in range(3))
    m = max(wr, wg, wb)
    return m / wr, m / wg, m / wb


def correct(src: Path, dst: Path, pct=1.0, chroma=1.0):
    im = Image.open(src).convert("RGB")
    gr, gg, gb = white_gains(im, pct)
    out = im.point([min(255, int(i * gr)) for i in range(256)] +
                   [min(255, int(i * gg)) for i in range(256)] +
                   [min(255, int(i * gb)) for i in range(256)])
    if chroma != 1.0:
        out = ImageEnhance.Color(out).enhance(chroma)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, quality=95, subsampling=0)
    return gr, gg, gb


def selfcheck():
    """造一张已知偏暖的中性灰图，校正后蓝通道应被拉回、三通道趋于相等。"""
    warm = Image.new("RGB", (64, 64), (240, 232, 212))  # 暖白，蓝缺 12%
    tmp = Path(__file__).parent / "_wb_selfcheck.jpg"
    warm.save(tmp, quality=95)
    out = tmp.with_name("_wb_selfcheck_out.jpg")
    gr, gg, gb = correct(tmp, out, pct=100.0)  # 纯色图，全部像素当白点
    r, g, b = Image.open(out).convert("RGB").getpixel((32, 32))
    tmp.unlink(); out.unlink()
    spread = max(r, g, b) - min(r, g, b)
    assert gb > gg > gr >= 1.0, f"增益方向错: R{gr:.3f} G{gg:.3f} B{gb:.3f}"
    assert spread <= 2, f"校正后三通道未趋同: ({r},{g},{b}) 极差 {spread}"
    print(f"selfcheck OK  增益 R{gr:.3f} G{gg:.3f} B{gb:.3f} -> ({r},{g},{b}) 极差 {spread}")


def main(argv):
    if "--selfcheck" in argv:
        selfcheck()
        return
    if not argv:
        print(__doc__)
        return
    src = Path(argv[0])
    pct = float(argv[argv.index("--pct") + 1]) if "--pct" in argv else 1.0
    chroma = float(argv[argv.index("--chroma") + 1]) if "--chroma" in argv else 1.0
    if "--out" in argv:
        outdir = Path(argv[argv.index("--out") + 1])
    else:
        base = src if src.is_dir() else src.parent
        outdir = base.with_name(base.name + "_白平衡校正")
    files = sorted(f for f in src.iterdir() if f.suffix.lower() in EXTS) if src.is_dir() else [src]
    if not files:
        print(f"没找到图片: {src}")
        return
    for f in files:
        gr, gg, gb = correct(f, outdir / f.name, pct, chroma)
        print(f"{f.name:28s} 增益 R{gr:.3f} G{gg:.3f} B{gb:.3f}")
    print(f"\n共 {len(files)} 张 -> {outdir}" + (f"  (chroma x{chroma})" if chroma != 1.0 else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
