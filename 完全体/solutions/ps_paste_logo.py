# -*- coding: utf-8 -*-
"""
ps_paste_logo.py —— 驱动 Photoshop 把真 logo 印回 AI 生成图。

为什么要用 PS（纯 Python 版 paste_real_logo 的两个天花板）：
  1. 擦旧 logo：PS 的【内容识别填充】会拿周围布料纹理**重建**那块区域；
     纯代码只能填平成纯色，一放大就看得出。
  2. 贴新 logo：PS 的【正片叠底】只让墨迹压暗，底下布料纹理原样透上来，
     像印在布上；纯代码的 alpha 混合总会带进真源的布色和织纹。

流程：Python 定位 + 算缩放 → 生成 JSX → COM 交给 PS 执行 → 存 JPG。
配套：logo 印章由 make_logo_stamp.py 产出（白底+墨迹，已旋正）。

前提：本机装了 Photoshop（COM 名 Photoshop.Application）。脚本会启动它。

用法：  py -X utf8 ps_paste_logo.py <目标图> <印章png> <输出图>
        py -X utf8 ps_paste_logo.py --batch <目标目录> <印章png> <输出目录>
        py -X utf8 ps_paste_logo.py --dry <目标图> <印章png> <输出图>   # 只生成 JSX 不执行
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from paste_real_logo import color_seed_bbox, full_logo_bbox, _expand

JSX = r"""
#target photoshop
app.displayDialogs = DialogModes.NO;
var oldUnits = app.preferences.rulerUnits;
app.preferences.rulerUnits = Units.PIXELS;

var doc = app.open(new File("%(target)s"));

// 1) 选中旧 logo 区域，内容识别填充 —— 用周围布料纹理重建，而不是填平
var sel = [[%(ex0)d,%(ey0)d],[%(ex1)d,%(ey0)d],[%(ex1)d,%(ey1)d],[%(ex0)d,%(ey1)d]];
doc.selection.select(sel);
doc.selection.feather(2);
var d = new ActionDescriptor();
d.putEnumerated(charIDToTypeID("Usng"), charIDToTypeID("FlCn"), stringIDToTypeID("contentAware"));
d.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), 100);
d.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Nrml"));
executeAction(charIDToTypeID("Fl  "), d, DialogModes.NO);
doc.selection.deselect();

// 2) 把印章贴成新图层
var stamp = app.open(new File("%(stamp)s"));
stamp.selection.selectAll();
stamp.selection.copy();
stamp.close(SaveOptions.DONOTSAVECHANGES);
app.activeDocument = doc;
doc.paste();
var lay = doc.activeLayer;

// 3) 正片叠底：只有墨迹压暗，布料纹理原样透上来
lay.blendMode = BlendMode.MULTIPLY;
lay.opacity = %(opacity)d;
lay.resize(%(scale).4f, %(scale).4f, AnchorPosition.MIDDLECENTER);

// 4) 按 logo 图形（紫环）中心对齐，而不是按图层框对齐
var b = lay.bounds;
var lx = b[0].as("px"), ly = b[1].as("px"), lw = b[2].as("px") - lx, lh = b[3].as("px") - ly;
var curX = lx + lw * %(relx).4f, curY = ly + lh * %(rely).4f;
lay.translate(%(tx).1f - curX, %(ty).1f - curY);

doc.flatten();
var opts = new JPEGSaveOptions();
opts.quality = 11;
doc.saveAs(new File("%(out)s"), opts, true, Extension.LOWERCASE);
doc.close(SaveOptions.DONOTSAVECHANGES);
app.preferences.rulerUnits = oldUnits;
"""


def plan(target_path, stamp_path):
    """算出：擦除框、缩放比、印章里 logo 中心的相对位置、目标 logo 中心。"""
    tgt = Image.open(target_path).convert("RGB")
    tseed, tctx = color_seed_bbox(tgt)
    if not tseed:
        raise ValueError("目标图没找到 logo")
    tk = tctx[1]
    tbox = tuple(int(v * tk) for v in tseed)
    # 擦除框要小：内容识别填充的采样范围是整张图，框给大了它就会把别处的
    # 缝线/包边"发挥"进来（实测把腿口包边复制到了 logo 下方）。够盖住旧 logo 即可。
    ebox = _expand(full_logo_bbox(tgt) or tbox, 0.18, *tgt.size)

    stamp = Image.open(stamp_path).convert("RGB")
    sseed, sctx = color_seed_bbox(stamp)
    if not sseed:
        raise ValueError("印章里没找到 logo")
    sbox = tuple(int(v * sctx[1]) for v in sseed)

    # 尺度基准用彩色图形（紫环）：两边都能可靠检出，比用整框稳
    scale = (tbox[2] - tbox[0]) / max(1, sbox[2] - sbox[0]) * 100
    relx = ((sbox[0] + sbox[2]) / 2) / stamp.width
    rely = ((sbox[1] + sbox[3]) / 2) / stamp.height
    tx, ty = (tbox[0] + tbox[2]) / 2, (tbox[1] + tbox[3]) / 2
    return dict(ex0=ebox[0], ey0=ebox[1], ex1=ebox[2], ey1=ebox[3],
                scale=scale, relx=relx, rely=rely, tx=tx, ty=ty)


def build_jsx(target_path, stamp_path, out_path, opacity=92):
    p = plan(target_path, stamp_path)
    esc = lambda s: str(Path(s).resolve()).replace("\\", "\\\\")
    return JSX % dict(p, target=esc(target_path), stamp=esc(stamp_path),
                      out=esc(out_path), opacity=opacity), p


def run_ps(jsx_text):
    f = Path(tempfile.gettempdir()) / "ps_paste_logo.jsx"
    f.write_text(jsx_text, encoding="utf-8")
    ps = (f'$a = New-Object -ComObject Photoshop.Application; '
          f'$a.DoJavaScriptFile("{f}"); "done"')
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    if r.returncode != 0 or "done" not in r.stdout:
        raise RuntimeError((r.stderr or r.stdout).strip()[:400])


def main(args):
    dry = "--dry" in args
    pos = [a for a in args if not a.startswith("--")]

    if "--batch" in args:
        srcdir, stamp, dstdir = Path(pos[0]), pos[1], Path(pos[2])
        dstdir.mkdir(parents=True, exist_ok=True)
        for f in sorted(srcdir.glob("*.jpg")):
            try:
                jsx, p = build_jsx(f, stamp, dstdir / f"{f.stem}_ps.jpg")
                if not dry:
                    run_ps(jsx)
                print(f"  {f.name}  缩放{p['scale']:.0f}% 中心({p['tx']:.0f},{p['ty']:.0f})")
            except Exception as e:
                print(f"  {f.name}  失败: {e}")
    else:
        jsx, p = build_jsx(pos[0], pos[1], pos[2])
        if dry:
            print(jsx)
        else:
            run_ps(jsx)
            print(f"缩放{p['scale']:.0f}% 中心({p['tx']:.0f},{p['ty']:.0f}) -> {pos[2]}")


if __name__ == "__main__":
    main(sys.argv[1:])
