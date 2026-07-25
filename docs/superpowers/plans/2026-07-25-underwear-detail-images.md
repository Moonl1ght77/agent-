# 周周内裤 8 张详情卖点图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 Photoshop 把 8 张内裤场景图制作成统一的 A·奶油编辑杂志风详情卖点图，并输出 8 张可编辑 PSD 和 8 张 PNG。

**Architecture:** 使用一份一次性 Photoshop JSX 脚本读取固定的 8 张源图，为每张图创建独立文档和结构化图层，再保存 PSD 与 PNG。脚本只负责机械化排版；最终通过 Photoshop 窗口截图和文件级检查共同验收。

**Tech Stack:** Adobe Photoshop 27、ExtendScript/JSX、Photoshop 原生 PSD/PNG 导出、Windows Computer Use。

## Global Constraints

- 不修改或覆盖 8 张源 PNG。
- 不重绘商品，不修改商品颜色、版型或中文 logo。
- 输出尺寸固定为 1776×2368、RGB、8 bit。
- 标题与副标题必须保持 Photoshop 可编辑文字层。
- 不运行任何 LumaX Flow 计费流程。
- 输出目录固定为 `成品_A奶油编辑风` 与 `PSD可编辑_A奶油编辑风`。

---

### Task 1: 建立 Photoshop 批处理脚本

**Files:**
- Create: `scratchpad/underwear_detail_images_20260725.jsx`

**Interfaces:**
- Consumes: 8 张源 PNG 的绝对路径、设计说明中的文案与版式坐标。
- Produces: `runBatch()`，负责逐张打开、建图层、保存 PSD、导出 PNG。

- [ ] **Step 1: 写入 8 张输入映射**

每条映射包含源图文件名后缀、输出序号、标题、副标题、文字块位置和对齐方式。

- [ ] **Step 2: 实现图层结构**

每张图建立 `原图_锁定`、`文案底板`、`标题`、`副标题`、`装饰线` 图层，文字层不栅格化。

- [ ] **Step 3: 实现保存与导出**

PSD 保存到 `PSD可编辑_A奶油编辑风`，PNG 保存到 `成品_A奶油编辑风`，源文件不覆盖。

- [ ] **Step 4: 脚本静态自检**

检查 8 条映射唯一、输出名唯一、标题和副标题均非空，并确保所有路径均为本次任务的确定路径。

### Task 2: 在 Photoshop 中执行批处理

**Files:**
- Execute: `scratchpad/underwear_detail_images_20260725.jsx`

**Interfaces:**
- Consumes: Task 1 的 `runBatch()`。
- Produces: 8 张 PSD 与 8 张 PNG。

- [ ] **Step 1: 连接并激活 Photoshop**

通过 Windows Computer Use 找到 Photoshop 27；若未运行，使用已安装应用启动。

- [ ] **Step 2: 运行 JSX**

使用 Photoshop 的 `文件 > 脚本 > 浏览` 打开 JSX，等待批处理完成。

- [ ] **Step 3: 检查完成状态**

确认 Photoshop 无错误弹窗，最后一个文档可见且文字、底板与商品主体关系正常。

### Task 3: 文件级与视觉验收

**Files:**
- Inspect: `E:\Studio-Assets\周周的内衣内裤项目\详情图\成品_A奶油编辑风\*.png`
- Inspect: `E:\Studio-Assets\周周的内衣内裤项目\详情图\PSD可编辑_A奶油编辑风\*.psd`

**Interfaces:**
- Consumes: Task 2 的输出。
- Produces: 交付清单与异常列表。

- [ ] **Step 1: 核对数量与尺寸**

检查 PNG=8、PSD=8，全部 PNG 为 1776×2368。

- [ ] **Step 2: 逐张视觉检查**

查看 8 张 PNG，核对错字、乱码、裁切、遮挡、对比度和统一性。

- [ ] **Step 3: 检查 PSD 可编辑性**

在 Photoshop 中打开至少 1 张 PSD，确认标题和副标题为文字图层、原图层存在且锁定。

- [ ] **Step 4: 修正异常并复验**

若发现异常，只调整受影响图片的坐标、字号或底板尺寸，再重新导出并重复数量、尺寸和视觉检查。
