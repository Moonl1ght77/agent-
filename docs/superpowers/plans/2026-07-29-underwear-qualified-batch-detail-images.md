# 周周内裤 2026-07-29 合格批次详情图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 Photoshop 把 8 张合格图片制作为统一的保色轻盈杂志风详情图，并输出 8 张 PNG 和 8 张可编辑 PSD。

**Architecture:** 复用上一批已验收 JSX 的字体、颜色与三种版式函数，建立本批独立输入映射与输出目录。7 张竖图原尺寸处理；1 张方图等比缩放后扩展近白画布。最终用文件检查、逐像素亮度检查、联系表与 Photoshop 图层面板验收。

**Tech Stack:** Adobe Photoshop 2026、ExtendScript/JSX、Photoshop PSD/PNG、Pillow/NumPy 只用于只读验收与联系表。

## Global Constraints

- 输入仅限 `成品_2026-07-29\合格` 下 8 张 JPG。
- 输出统一 1792×2400、RGB、8 bit。
- 不改变产品、logo、件数、颜色与亮度。
- 不增加白雾、曝光或调色图层。
- 文案必须为 Photoshop 可编辑文字层。
- 不运行 LumaX Flow 计费节点。

---

### Task 1: 建立本批 Photoshop 脚本

**Files:**
- Create: `scratchpad/underwear_qualified_detail_20260729.jsx`

**Interfaces:**
- Consumes: 8 个源文件绝对名称及设计说明中的文案映射。
- Produces: `makeOne(item, number)`，逐张建立可编辑图层并导出 PSD/PNG。

- [x] **Step 1: 复制已验收视觉函数**

保留 `buildLeft`、`buildRight`、`buildRailLeft`、`buildRailRight`、`addTitleStack`、字体搜索与形状/文字图层函数；删除所有渐隐、曝光和调色逻辑。

- [x] **Step 2: 写入 8 条新映射**

映射必须包含 `file`、`out`、`family`、`english`、`titleA`、`titleB`、`subtitle`、`micro`；用 `validateItems()` 验证数量、文件名与输出名唯一。

- [x] **Step 3: 处理方形图**

当源图为 2048×2048 时，先等比缩放到 1792×1792，再以画布中心为锚扩展到 1792×2400；背景使用接近源图的近白色，产品不裁切。

- [x] **Step 4: 静态自检**

确认脚本包含两个“合格批次_保色版”输出目录、8 条映射、方图分支，且不包含 `addSoftCloud`、曲线或色彩调整调用。

### Task 2: 在 Photoshop 批量生成

**Files:**
- Execute: `scratchpad/underwear_qualified_detail_20260729.jsx`
- Produce: `详情图_合格批次_保色版\*.png`
- Produce: `PSD可编辑_详情图_合格批次_保色版\*.psd`

**Interfaces:**
- Consumes: Task 1 的 JSX。
- Produces: 8 张 PNG 与 8 张分层 PSD。

- [x] **Step 1: 运行 JSX**

通过 Photoshop `文件 > 脚本 > 浏览` 执行脚本；等待完成提示，不操作 LumaX Flow。

- [x] **Step 2: 检查完成状态**

确认 Photoshop 无错误弹窗，最后一张文档可见，商品未被文字遮挡。

### Task 3: 文件与视觉验收

**Files:**
- Inspect: `详情图_合格批次_保色版\*.png`
- Inspect: `PSD可编辑_详情图_合格批次_保色版\*.psd`
- Create: `scratchpad/underwear_qualified_detail_20260729_contactsheet.jpg`

**Interfaces:**
- Consumes: Task 2 输出。
- Produces: 文件验收结果、联系表与异常清单。

- [x] **Step 1: 核对数量、名称与尺寸**

检查 PNG=8、PSD=8、PNG 全部 1792×2400 RGB，且最小文件大小非零。

- [x] **Step 2: 核对保色**

对 7 张同尺寸场景图逐像素比较源图与输出的非文案商品区，面积性新增亮度不得超过验收阈值；方图只检查产品内容区。

- [x] **Step 3: 视觉检查**

制作 8 张联系表，逐张检查标题、乱码、裁切、遮挡、系列感与方图扩展边缘。

- [x] **Step 4: 检查 PSD 可编辑性**

在 Photoshop 打开至少 1 张 PSD，确认标题、副标题、英文字标、编号和细线为独立图层，原图层存在且锁定。

- [x] **Step 5: 更新执行结果**

把数量、尺寸、亮度和图层验收证据回写本计划；若有异常，只修受影响项并重新验收。

## 执行结果

- Photoshop JSX 静态检查通过：8 条输入、8 条输出、方图分支、保色输出目录均存在；无 `addSoftCloud` 或亮度/颜色调整调用。
- Photoshop 原生脚本接口执行返回，生成 PNG=8、PSD=8；全部 PNG 为 1792×2400 RGB。
- 7 张同尺寸场景图在商品区域 `y=700..2299` 与源 JPG 对比：平均亮度差为 −0.0065～+0.0004，新增亮度 >12 的像素 7/7 均为 0。
- 方形白底图等比缩放并上下延展为竖版，商品完整、延展边缘无明显断层。
- 已检查 8 张联系表，并以原尺寸检查 02、03、06；无标题裁切、乱码或商品遮挡。
- Photoshop 逐份打开 8 个 PSD：全部为 1792×2400，均检测到 7 个可编辑文字层及 `原图_锁定` 层。
- 联系表：`scratchpad/underwear_qualified_detail_20260729_contactsheet.jpg`。
