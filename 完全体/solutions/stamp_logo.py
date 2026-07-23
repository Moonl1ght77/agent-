# -*- coding: utf-8 -*-
"""
stamp_logo.py —— 把真 logo 印章「印」回 AI 生成图。纯像素，零 AI，零幻觉。

两步都用最朴素也最可控的做法：
  1. 擦旧 logo = 从旁边复制一块**真实的干净布料**盖上去（同一张图的像素，纹理天然连续）。
     不用 PS 的内容识别填充——它在大片纯色布上会硬造出缝线包边（实测把腿口包边搬了过来）。
  2. 贴新 logo = **正片叠底** out = 目标 × 印章 ÷ 255。
     印章白底(255) 相乘后目标不变 → 布料纹理原样保留；墨迹按原始浓淡压暗 → 像印在布上。
     早先用 alpha 混合是错的：半透明边缘会把真源的布色和织纹一起带过来，留下白晕。

配套：印章由 make_logo_stamp.py 产出（白底+墨迹、已旋正）。

用法：  py -X utf8 stamp_logo.py <目标图> <印章png> <输出图>
        py -X utf8 stamp_logo.py --batch <目标目录> <印章png> <输出目录>
        py -X utf8 stamp_logo.py --selfcheck
调参：  --opacity 0.92  墨迹浓度（1=照原样，小于1更淡更融）
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from paste_real_logo import color_seed_bbox, full_logo_bbox, _expand, _clean_patch


def stamp(target_path, stamp_path, out_path, opacity=0.92, erase_pad=0.22):
    tgt = Image.open(target_path).convert("RGB")
    W, H = tgt.size
    tseed, tctx = color_seed_bbox(tgt)
    if not tseed:
        raise ValueError("目标图没找到 logo")
    tbox = tuple(int(v * tctx[1]) for v in tseed)
    ebox = _expand(full_logo_bbox(tgt) or tbox, erase_pad, W, H)
    ew, eh = ebox[2] - ebox[0], ebox[3] - ebox[1]

    # 1) 用邻近干净布料盖掉旧 logo，边缘羽化融进去
    src = _clean_patch(tgt, ebox)
    if src is None:
        raise ValueError("附近找不到干净布料块")
    patch = tgt.crop((src[0], src[1], src[0] + ew, src[1] + eh))
    m = Image.new("L", (ew, eh), 0)
    pad = max(2, min(ew, eh) // 8)
    ImageDraw.Draw(m).rectangle((pad, pad, ew - pad, eh - pad), fill=255)
    tgt.paste(patch, ebox, m.filter(ImageFilter.GaussianBlur(pad / 1.8)))

    # 2) 印章缩放到与目标 logo 同尺度（用紫环宽度做基准，两边都检得准）
    st = Image.open(stamp_path).convert("RGB")
    sseed, sctx = color_seed_bbox(st)
    if not sseed:
        raise ValueError("印章里没找到 logo")
    sbox = tuple(int(v * sctx[1]) for v in sseed)
    k = (tbox[2] - tbox[0]) / max(1, sbox[2] - sbox[0])
    nw, nh = max(1, int(st.width * k)), max(1, int(st.height * k))
    st = st.resize((nw, nh), Image.LANCZOS)
    scx, scy = int((sbox[0] + sbox[2]) / 2 * k), int((sbox[1] + sbox[3]) / 2 * k)
    tcx, tcy = (tbox[0] + tbox[2]) // 2, (tbox[1] + tbox[3]) // 2
    ox, oy = tcx - scx, tcy - scy

    # 3) 正片叠底
    under = tgt.crop((ox, oy, ox + nw, oy + nh))
    ul, stl = under.load(), st.load()
    out = Image.new("RGB", (nw, nh))
    ol = out.load()
    for y in range(nh):
        for x in range(nw):
            u, s = ul[x, y], stl[x, y]
            ol[x, y] = tuple(
                min(255, int(u[i] * (255 - (255 - s[i]) * opacity) / 255))
                for i in range(3))
    tgt.paste(out, (ox, oy))
    tgt.save(out_path, quality=95)
    return tbox, (nw, nh), src


def selfcheck():
    """浅色布上有假 logo + 一条独有灰杠；印完后：假 logo 没了、真墨迹在、布料纹理还在。"""
    d = Path(__file__).parent
    tf, sf, of = d / "_st_tgt.jpg", d / "_st_stamp.png", d / "_st_out.jpg"

    tgt = Image.new("RGB", (700, 500), (150, 140, 130))
    dr = ImageDraw.Draw(tgt)
    dr.rectangle((80, 60, 620, 440), fill=(236, 224, 218))
    for x in range(80, 620, 4):                       # 布料织纹（竖条），必须活下来
        dr.line((x, 60, x, 440), fill=(228, 216, 210))
    dr.ellipse((300, 200, 360, 260), outline=(110, 70, 100), width=6)
    dr.rectangle((300, 275, 380, 283), fill=(60, 60, 60))   # 假 logo 独有的灰杠
    tgt.save(tf, quality=95)

    stm = Image.new("RGB", (200, 200), "white")       # 印章：只有一个环，无灰杠
    ImageDraw.Draw(stm).ellipse((60, 60, 140, 140), outline=(110, 70, 100), width=8)
    stm.save(sf)

    tbox, size, src = stamp(tf, sf, of)
    res = Image.open(of).convert("RGB")
    assert min(res.getpixel((340, 279))) > 190, "假 logo 的灰杠没被盖掉"
    ring = min(res.getpixel((302, 230)), res.getpixel((358, 230)), key=min)
    assert min(ring) < 170, f"真 logo 没印上，环处={ring}"
    # 印章白底区域必须保留底下的织纹（正片叠底的意义所在）
    col = [res.getpixel((x, 180))[0] for x in range(300, 360)]
    assert max(col) - min(col) > 4, "布料织纹被印章盖平了"
    for f in (tf, sf, of):
        f.unlink(missing_ok=True)
    print("selfcheck OK", tbox, size)


def main(args):
    if "--selfcheck" in args:
        return selfcheck()
    op = float(args[args.index("--opacity") + 1]) if "--opacity" in args else 0.92
    pos = [a for i, a in enumerate(args)
           if not a.startswith("--") and args[i - 1] != "--opacity"]

    if "--batch" in args:
        srcdir, st, dstdir = Path(pos[0]), pos[1], Path(pos[2])
        dstdir.mkdir(parents=True, exist_ok=True)
        for f in sorted(srcdir.glob("*.jpg")):
            try:
                tbox, size, src = stamp(f, st, dstdir / f"{f.stem}_logo.jpg", op)
                print(f"  {f.name}  印章{size[0]}x{size[1]} 取布于{src}")
            except Exception as e:
                print(f"  {f.name}  失败: {e}")
    else:
        tbox, size, src = stamp(pos[0], pos[1], pos[2], op)
        print(f"logo框{tbox} 印章{size[0]}x{size[1]} 取布于{src} -> {pos[2]}")


if __name__ == "__main__":
    main(sys.argv[1:])
