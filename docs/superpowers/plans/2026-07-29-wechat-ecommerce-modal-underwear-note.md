# WeChat Ecommerce Modal Underwear Note Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一份带 8 张已验收详情图、可直接参考微信发布顺序的莫代尔内裤 Word 图文笔记。

**Architecture:** 用一份 JSON 保存标题、商品参数和 8 个图文段落，Python 构建器读取 JSON 后用 `python-docx` 生成 DOCX，并仅为文档嵌入用途等比缩小源 PNG。最后做 OOXML 结构检查、文本事实检查和 DOCX→PNG 全页视觉验收。

**Tech Stack:** Codex bundled Python 3、`python-docx`、Pillow、LibreOffice、documents skill `render_docx.py`

## Global Constraints

- 最终文件固定为 `E:\Studio-Assets\周周的内衣内裤项目\内裤\成品_2026-07-29\微信电商笔记_软糯莫代尔舒适内裤.docx`。
- 图片严格按 `01` 至 `08` 顺序嵌入，源目录为 `详情图_合格批次_保色版`。
- 尺码只能使用：L 80–110 斤、XL 110–135 斤、2XL 135–160 斤。
- 面料只能写：95% 莫代尔、5% 氨纶；裆部只能写：100% 棉。
- 颜色统一为：浅蓝、浅绿、浅咖、肤色、浅粉、浅紫。
- 版型统一为：中高腰、包臀、贴合腿口。
- 禁止把 `10A 抑菌`、`水洗 300 次`、`17CM`、医疗功效和绝对化承诺写入正式正文。
- 图片只允许为文档嵌入等比缩小，不允许调亮、调色、裁切或覆盖新文字。
- 不运行 LumaX Flow，不产生计费。
- 当前环境禁止委派子代理，因此本计划使用 `superpowers:executing-plans` 在当前会话内执行。

---

### Task 1: 建立正式发布文案数据

**Files:**
- Create: `scratchpad/wechat_ecommerce_modal_underwear_note_20260729.json`
- Create: `scratchpad/validate_wechat_ecommerce_modal_underwear_note_20260729.py`

**Interfaces:**
- Consumes: 已确认商品数据、8 个 PNG 绝对路径、设计规格中的图文顺序。
- Produces: UTF-8 JSON 对象，字段为 `title`、`alternateTitles`、`productInfo`、`lead`、`sections`、`closing`。

- [ ] **Step 1: 写入 JSON 内容结构**

JSON 顶层必须符合：

```json
{
  "title": "穿一整天，也想不起它的存在｜软糯莫代尔舒适内裤",
  "alternateTitles": [
    "贴身衣物选得对，日常舒适真的不一样",
    "六种温柔配色，把软糯舒适穿进每一天",
    "中高腰包裹不紧绷，久坐通勤也更自在"
  ],
  "productInfo": [
    {"label": "商品名称", "value": "软糯莫代尔舒适内裤"}
  ],
  "lead": [
    "内裤舒不舒服，不只看刚穿上的那一刻。",
    "真正影响一天状态的，是久坐以后腰腹会不会紧、走动时腿口会不会磨、弯腰时会不会反复跑位。"
  ],
  "sections": [
    {
      "heading": "01 亲肤裸感",
      "copy": [
        "95%莫代尔带来柔滑细腻的触感，加入5%氨纶后，多了一点顺应身体动作的柔韧。",
        "贴身穿着不需要靠过度紧绷来固定，让日常久穿更轻松。"
      ],
      "image": "E:\\Studio-Assets\\周周的内衣内裤项目\\内裤\\成品_2026-07-29\\详情图_合格批次_保色版\\01_亲肤裸感.png",
      "alt": "浅色莫代尔内裤多色平铺展示"
    }
  ],
  "closing": [
    "六种低饱和配色，可以按日常衣橱和换洗习惯自由选择。",
    "尺码：L（80–110斤）、XL（110–135斤）、2XL（135–160斤）。"
  ]
}
```

`sections` 必须恰好 8 项，图片 basename 依次为：

```text
01_亲肤裸感.png
02_四色好搭.png
03_高腰包裹.png
04_六色随心.png
05_日常百搭.png
06_柔韧高弹.png
07_包臀不夹.png
08_细腻包边.png
```

- [ ] **Step 2: 写内容校验器**

实现：

```python
def validate_content(data: dict) -> list[str]:
    """返回全部错误；空列表代表通过。"""
```

校验项：

```python
EXPECTED_IMAGES = [
    "01_亲肤裸感.png", "02_四色好搭.png", "03_高腰包裹.png",
    "04_六色随心.png", "05_日常百搭.png", "06_柔韧高弹.png",
    "07_包臀不夹.png", "08_细腻包边.png",
]
FORBIDDEN = ["10A", "水洗300", "水洗 300", "17CM", "治疗", "抗菌率", "绝对不勒", "完全无痕"]
REQUIRED = ["95%莫代尔", "5%氨纶", "100%棉", "L（80–110斤）", "XL（110–135斤）", "2XL（135–160斤）"]
```

同时检查 8 个图片路径都存在。

- [ ] **Step 3: 运行内容校验**

Run:

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scratchpad\validate_wechat_ecommerce_modal_underwear_note_20260729.py
```

Expected:

```text
CONTENT_VALIDATION=PASS
SECTION_COUNT=8
IMAGE_PATHS_EXIST=8
```

---

### Task 2: 构建带嵌入图片的 Word 笔记

**Files:**
- Create: `scratchpad/build_wechat_ecommerce_modal_underwear_note_20260729.py`
- Create: `scratchpad/wechat_note_embeds_20260729/`（运行时生成，仅供嵌入）
- Create: `E:\Studio-Assets\周周的内衣内裤项目\内裤\成品_2026-07-29\微信电商笔记_软糯莫代尔舒适内裤.docx`

**Interfaces:**
- Consumes: Task 1 JSON。
- Produces: 可正常打开的 DOCX，包含 8 张嵌入图和完整正文。

- [ ] **Step 1: 固化文档样式令牌**

采用 `narrative_proposal` 预设，命名覆盖 `wechat_editorial`：

```python
STYLE = {
    "page": {"size": "Letter", "margins_in": 1.0, "header_in": 0.492, "footer_in": 0.492},
    "font": "Microsoft YaHei",
    "body": {"size_pt": 11, "after_pt": 8, "line_spacing": 1.333, "color": "262220"},
    "title": {"size_pt": 27, "after_pt": 8, "color": "6E3345"},
    "subtitle": {"size_pt": 11, "after_pt": 22, "color": "7A6B70"},
    "h1": {"size_pt": 16, "before_pt": 14, "after_pt": 7, "color": "6E3345"},
    "h2": {"size_pt": 13, "before_pt": 10, "after_pt": 5, "color": "6E3345"},
    "table": {"width_dxa": 9360, "indent_dxa": 120, "columns_dxa": [1800, 7560]},
    "image_width_in": 5.1,
}
```

首屏使用 `editorial_cover` 的轻量变体：酒红色英文 kicker、左对齐中文标题、灰色副标题，不做独立空白封面。

- [ ] **Step 2: 实现构建函数**

实现以下边界明确的函数：

```python
def load_content(path: Path) -> dict: ...
def prepare_embed_image(source: Path, output_dir: Path) -> Path: ...
def configure_document(doc: Document) -> None: ...
def add_title_block(doc: Document, data: dict) -> None: ...
def add_product_info(doc: Document, items: list[dict]) -> None: ...
def add_copy_paragraphs(doc: Document, paragraphs: list[str]) -> None: ...
def add_image_section(doc: Document, section: dict) -> None: ...
def set_picture_alt_text(inline_shape, title: str, description: str) -> None: ...
def save_document(data: dict, output_path: Path) -> None: ...
```

`prepare_embed_image()` 只做：

```python
image.thumbnail((1200, 1608), Image.Resampling.LANCZOS)
image.save(output_path, format="PNG", optimize=True)
```

不得执行亮度、颜色、对比度、裁切或绘字操作。

- [ ] **Step 3: 生成 DOCX**

Run:

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scratchpad\build_wechat_ecommerce_modal_underwear_note_20260729.py
```

Expected:

```text
DOCX_CREATED=TRUE
EMBEDDED_IMAGES=8
OUTPUT=E:\Studio-Assets\周周的内衣内裤项目\内裤\成品_2026-07-29\微信电商笔记_软糯莫代尔舒适内裤.docx
```

---

### Task 3: 结构与视觉验收

**Files:**
- Create: `scratchpad/verify_wechat_ecommerce_modal_underwear_note_20260729.py`
- Create: `scratchpad/wechat_note_render_20260729/`（QA 中间产物）
- Modify: `docs/superpowers/plans/2026-07-29-wechat-ecommerce-modal-underwear-note.md`

**Interfaces:**
- Consumes: Task 2 DOCX。
- Produces: 结构验收输出、全页 PNG 和执行结果记录。

- [ ] **Step 1: 验证 DOCX 结构与正文**

校验器必须：

```python
with zipfile.ZipFile(docx_path) as archive:
    media = [name for name in archive.namelist() if name.startswith("word/media/")]
assert len(media) == 8
```

再用 `python-docx` 按文档顺序提取段落和图片关系，确认：

- 8 张图关系全部存在；
- 图片 basename 映射顺序为 `01` 至 `08`；
- 正文包含全部 REQUIRED；
- 正文不包含全部 FORBIDDEN；
- 文档没有空图片关系或外链图片。

- [ ] **Step 2: 运行结构验收**

Run:

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scratchpad\verify_wechat_ecommerce_modal_underwear_note_20260729.py
```

Expected:

```text
DOCX_STRUCTURE=PASS
MEDIA_COUNT=8
IMAGE_ORDER=PASS
FACTS=PASS
FORBIDDEN_CLAIMS=0
```

- [ ] **Step 3: 渲染 DOCX 为全页 PNG**

Run:

```powershell
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe C:\Users\Administrator\.codex\plugins\cache\openai-primary-runtime\documents\26.727.11326\skills\documents\render_docx.py "E:\Studio-Assets\周周的内衣内裤项目\内裤\成品_2026-07-29\微信电商笔记_软糯莫代尔舒适内裤.docx" --output_dir "E:\Projects\agent全自动生图\scratchpad\wechat_note_render_20260729"
```

Expected: `page-1.png` 至最后一页均存在。

- [ ] **Step 4: 逐页视觉检查并迭代**

检查每一页：

- 中文无缺字或乱码；
- 图片无拉伸、裁切、明显色变；
- 标题、正文、参数块无重叠或截断；
- 章节标题不孤立在页尾；
- 图片与对应文案顺序一致；
- 无异常大段空白。

发现问题时只修改 Task 2 构建器，重新生成、重新运行 Task 3 全部检查，直到通过。

- [ ] **Step 5: 回写执行结果**

在本计划末尾记录最终页数、媒体数量、正文事实检查和视觉检查结果。

---

### Task 4: 提交、共享记忆与交付

**Files:**
- Modify: `E:\AI-Memory\vault\20-项目记忆\电商作图\agent全自动生图\当前进度.md`

**Interfaces:**
- Consumes: 已通过 Task 3 的 DOCX。
- Produces: 项目提交、记忆库提交和最终交付回执。

- [ ] **Step 1: 更新项目记忆**

记录：最终 DOCX 路径、采用 A 尺码口径、8 图顺序、未写未经证实的抑菌/17CM 数据、结构与视觉验收结果。

- [ ] **Step 2: 检查并提交项目记录**

Run:

```powershell
git diff --check
git add docs/superpowers/plans/2026-07-29-wechat-ecommerce-modal-underwear-note.md
git commit -m "docs: record wechat underwear note delivery"
git push origin main
```

- [ ] **Step 3: 提交共享记忆**

Run:

```powershell
git -C E:\AI-Memory diff --check
git -C E:\AI-Memory add "vault/20-项目记忆/电商作图/agent全自动生图/当前进度.md"
git -C E:\AI-Memory commit -m "记录莫代尔内裤微信图文笔记交付"
git -C E:\AI-Memory push origin master
```

- [ ] **Step 4: 最终交付**

只向 Joe 交付最终 DOCX，不交付渲染 PNG、临时 JSON 或构建脚本；附数量、页数、事实校验、视觉验收和【记忆存档回执】。
