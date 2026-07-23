# -*- coding: utf-8 -*-
"""
ps_cutout.py —— 用 Photoshop 的【选择主体】把产品从杂乱背景里抠出来，输出纯白底 SKU 图。

什么时候用它、什么时候用 cutout_white.py：
  - 背景明显暗于产品（黑布上拍）→ 用 `cutout_white.py`，纯像素、快、不依赖 PS。
  - 背景是浅色杂物（桌面、书、键盘、毯子）→ 阈值法失效，用本脚本，靠 PS 的 AI 主体识别。

流程：打开 → 选择主体 → 内缩1px去光晕 → 反选删除 → 垫白底 → 按主体裁切 → 补成正方形 → 存 JPG。

前提：本机装了 Photoshop（COM 名 Photoshop.Application）。

用法：  py -X utf8 ps_cutout.py <输入图> <输出图> [--size 1200]
        py -X utf8 ps_cutout.py --batch <输入目录> <输出目录> [--size 1200] [--pattern *.JPG]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

JSX = r"""
#target photoshop
app.displayDialogs = DialogModes.NO;
var oldUnits = app.preferences.rulerUnits;
app.preferences.rulerUnits = Units.PIXELS;

var doc = app.open(new File("%(src)s"));
doc.flatten();
doc.activeLayer.name = "layer0";          // 解锁背景层，否则删不了

// 选择主体（AI）
var d = new ActionDescriptor();
d.putBoolean(stringIDToTypeID("sampleAllLayers"), false);
executeAction(stringIDToTypeID("autoCutout"), d, DialogModes.NO);

// 内缩 1px 去掉边缘残留的背景色，再轻羽化
try { doc.selection.contract(1); } catch (e) {}
try { doc.selection.feather(0.8); } catch (e) {}

doc.selection.invert();
doc.selection.clear();
doc.selection.deselect();

// 垫白底
var bg = doc.artLayers.add();
bg.name = "white";
doc.selection.selectAll();
var w = new SolidColor(); w.rgb.red = 255; w.rgb.green = 255; w.rgb.blue = 255;
doc.selection.fill(w);
doc.selection.deselect();
bg.move(doc.layers[doc.layers.length - 1], ElementPlacement.PLACEAFTER);
doc.flatten();

// 按白底裁掉四周空白，留边，再补成正方形
doc.trim(TrimType.TOPLEFT, true, true, true, true);
var pad = Math.round(Math.max(doc.width.as("px"), doc.height.as("px")) * 0.06);
var side = Math.round(Math.max(doc.width.as("px"), doc.height.as("px"))) + pad * 2;
doc.resizeCanvas(side, side, AnchorPosition.MIDDLECENTER);
doc.resizeImage(%(size)d, %(size)d, 72, ResampleMethod.BICUBICSHARPER);

var opts = new JPEGSaveOptions();
opts.quality = 11;
doc.saveAs(new File("%(out)s"), opts, true, Extension.LOWERCASE);
doc.close(SaveOptions.DONOTSAVECHANGES);
app.preferences.rulerUnits = oldUnits;
"""


def run(src, out, size=1200):
    esc = lambda s: str(Path(s).resolve()).replace("\\", "\\\\")
    jsx = JSX % dict(src=esc(src), out=esc(out), size=size)
    f = Path(tempfile.gettempdir()) / "ps_cutout.jsx"
    f.write_text(jsx, encoding="utf-8")
    cmd = f'$a = New-Object -ComObject Photoshop.Application; $a.DoJavaScriptFile("{f}"); "done"'
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, text=True)
    if "done" not in r.stdout:
        raise RuntimeError((r.stderr or r.stdout).strip()[:400])


def main(args):
    size = int(args[args.index("--size") + 1]) if "--size" in args else 1200
    pattern = args[args.index("--pattern") + 1] if "--pattern" in args else "*.JPG"
    pos = [a for i, a in enumerate(args)
           if not a.startswith("--") and args[i - 1] not in ("--size", "--pattern")]

    if "--batch" in args:
        srcdir, dstdir = Path(pos[0]), Path(pos[1])
        dstdir.mkdir(parents=True, exist_ok=True)
        for f in sorted(srcdir.glob(pattern)):
            try:
                run(f, dstdir / f"{f.stem}_white.jpg", size)
                print(f"  {f.name}  OK")
            except Exception as e:
                print(f"  {f.name}  失败: {e}")
    else:
        run(pos[0], pos[1], size)
        print(f"OK -> {pos[1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
