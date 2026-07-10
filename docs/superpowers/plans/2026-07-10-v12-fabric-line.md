# V12 奢牌面料成衣线（Fabric-to-Garment）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已批准的架构设计（`完全体/direction/V12面料成衣线架构设计.md`）落地 V12 产品线：面料图/类目文字 → 虚拟打样（3张样衣）→ 4分镜奢牌展示大片，双模式（A图驱动 / B类目文驱动）共用单份规则引擎。

**Architecture:** DBS三层解耦。Blueprints 层新增 `workflow_spec_v12.json`（31卡/81连/7组；`variants.b` 删除面料图卡=29卡/67连）+ 15份 v12 提示词；Solutions 层只对 `build_lxf.py::load_spec` 做一次向后兼容扩展（variant 支持 `removeCards`），verify_lxf/apply_to_app/verify_canvas 通过 import 自动继承；改动后对 V9.2/V10/V11 三条旧线跑回归构建核验。

**Tech Stack:** Python 3.12（`py -X utf8` 启动）、LumaX Flow .lxf（Zip/store）、GPT-5.5 编排 + GPT-Image 2 渲染。

---

## 背景与真源（执行者必读）

- 设计真源：`完全体/direction/V12面料成衣线架构设计.md`（已获 Joe 全节批准，含双模式/4分镜/三轴类目库）。
- 工程规矩：`通用框架/`（铁律21条）。本计划已内置关键铁律：连线顺序=槽位顺序=前缀声明序（铁律1/8）；蓝图唯一真源（铁律2）；多图LLM节点按内容认图（铁律3）；禁环（铁律5）；抽取器只抽取（铁律7）；发布闭环四步（铁律16）；修复三点落地（铁律17）；枚举强制令（铁律19）。
- 所有构建/核验命令在 `E:\Projects\agent全自动生图\完全体\solutions\` 下执行，用 `py -X utf8`。
- 每个任务结束跑一次对应验证命令，**以脚本结论为准**；commit 信息结尾带 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- run 计费：本计划不含任何 run 操作；apply 免费幂等。

## 文件地图

| 文件 | 动作 | 职责 |
|---|---|---|
| `完全体/solutions/build_lxf.py` | 修改（+7行） | variant 机制支持 removeCards（删卡+级联删连线+清分组） |
| `完全体/blueprints/assets/fabric_detail_sample.jpg` | 新增 | INF1 占位图（乐顺8416细节图） |
| `完全体/blueprints/assets/fabric_card_sample.jpg` | 新增 | INF2 占位图（乐顺8416色卡图） |
| `完全体/blueprints/prompts/REQ1_品类与输出_v12.txt` 等15份 | 新增 | V12 全部提示词（见各任务） |
| `完全体/blueprints/workflow_spec_v12.json` | 新增 | V12 结构真源（含 variants.b） |
| `完全体/direction/回归防线.md` | 修改 | 产品线登记表新增 V12 行 |
| 交付 | 构建产物 | `V12奢牌面料成衣线4分镜.lxf` + `V12奢牌面料成衣线4分镜_模式B.lxf` |

## 拓扑速查（写 spec 与查错用）

```
REQ1/REQ2 ─┬→ F1面料锁 ─┬→ D1设计官 ─┬→ CS打样编译 → PS1/2/3抽取 → GS1样衣正面(2K)/GS2背面(1K)
INF1面料图 ─┤(模式B无)   │            │                              GS1+INF1 → GS3定妆照(1K)
INF2色卡图 ─┘            │            └────────→ SP1氛围导演（托管场景+4分镜）
                         └───────────────────────→ C 总控（也直收F1锁卡，防二次压缩）
GS1/GS2/INF1 → A1成衣锁；GS3/D1 → A2人物锁
A1/A2/SP1/F1 + GS3/GS1/INF1图 → C → P1-4 → G1-4(2K, 槽1=GS3 槽2=GS1 槽3=INF1)
GS3/GS1/GS2/INF1 + G1-4 + C → QA → R → RG(同G槽位)
INF1/GS1/G3 → X1四宫格；G4/GS1 → X2首屏
模式B(--variant b)：删INF1/INF2卡，所有触及连线自动消失（Task 1 扩展负责）
```

---

### Task 1: build_lxf.py 扩展 removeCards（含三线回归）

**Files:**
- Modify: `完全体/solutions/build_lxf.py:35-43`（load_spec 的 variant 覆盖段）

- [ ] **Step 1: 修改 load_spec**

在 `load_spec` 中 `for c in spec["cards"]:` 循环结束后（`global CHAT_DEFAULT` 之前）插入：

```python
        rm = set(v.get("removeCards", []))
        if rm:
            spec["cards"] = [c for c in spec["cards"] if c["ref"] not in rm]
            spec["connections"] = [p for p in spec["connections"]
                                   if p[0] not in rm and p[1] not in rm]
            for g in spec["groups"]:
                g["members"] = [m for m in g["members"] if m not in rm]
            spec["groups"] = [g for g in spec["groups"] if g["members"]]
```

同时更新文件头 docstring 用法行为：`py build_lxf.py [--spec xxx.json] [--variant half|b]`（variant 支持 titles/promptFiles/removeCards 覆盖）。

- [ ] **Step 2: 三条旧线回归构建+核验（改共用文件必做，铁律21）**

```powershell
cd "E:\Projects\agent全自动生图\完全体\solutions"
py -X utf8 build_lxf.py;                                py -X utf8 verify_lxf.py
py -X utf8 build_lxf.py --variant half;                 py -X utf8 verify_lxf.py --variant half
py -X utf8 build_lxf.py --spec workflow_spec_v11.json;  py -X utf8 verify_lxf.py --spec workflow_spec_v11.json
```

Expected: 三次构建各打印 `OK 已生成`，三次核验各打印 `✅ 全量一致 …… 零漂移`。任何一条失败=改动破坏旧线，回滚重来。

- [ ] **Step 3: Commit**

```powershell
git add "完全体/solutions/build_lxf.py"
git commit -m "V12工具层: variant机制支持removeCards(删卡级联删连线清分组), V9.2/V10/V11回归零漂移"
```

### Task 2: 面料占位图资产入库

**Files:**
- Create: `完全体/blueprints/assets/fabric_detail_sample.jpg`
- Create: `完全体/blueprints/assets/fabric_card_sample.jpg`

- [ ] **Step 1: 复制乐顺8416素材为占位图（ASCII文件名，蓝图自包含，铁律12）**

```powershell
Copy-Item "E:\微信小程序开发总文件\02-assets\client-jiajufu\乐顺小程序\8416#兰精莫代尔2x2罗纹\面料细节图.jpg" "E:\Projects\agent全自动生图\完全体\blueprints\assets\fabric_detail_sample.jpg"
Copy-Item "E:\微信小程序开发总文件\02-assets\client-jiajufu\乐顺小程序\8416#兰精莫代尔2x2罗纹\面料色卡图.jpg" "E:\Projects\agent全自动生图\完全体\blueprints\assets\fabric_card_sample.jpg"
```

- [ ] **Step 2: 验证存在**

```powershell
Get-ChildItem "E:\Projects\agent全自动生图\完全体\blueprints\assets\fabric_*.jpg"
```
Expected: 两个文件，各 >100KB。

- [ ] **Step 3: Commit**

```powershell
git add "完全体/blueprints/assets/fabric_detail_sample.jpg" "完全体/blueprints/assets/fabric_card_sample.jpg"
git commit -m "V12蓝图资产: 面料细节图/色卡图占位(乐顺8416实拍)"
```

### Task 3: 需求卡与使用说明（4份文本卡）

**Files:**
- Create: `完全体/blueprints/prompts/REQ1_品类与输出_v12.txt`
- Create: `完全体/blueprints/prompts/REQ2_面料与硬指令_v12.txt`
- Create: `完全体/blueprints/prompts/DOC1_使用说明_v12.txt`
- Create: `完全体/blueprints/prompts/DOC1_使用说明_v12b.txt`

- [ ] **Step 1: 写 REQ1_品类与输出_v12.txt**（完整内容如下）

```
【需求卡①：品类与输出（用户可编辑，改这里即可，不用改任何提示词）】
品类（用途轴）：家居服
性别与年龄感：女，25-35，松弛优雅
最终用途：面料商展示（首页外观提升位）
输出：4 张展示图（3:4，2K）+ 3 张虚拟样衣（白底正背 + 模特定妆照）

参考图角色（固定，不要改语义）：
图1 = 面料细节图（模式A必填：颜色纹理真源；不放图请改用模式B画布）
图2 = 面料色卡图（选填：印有克重/成分等参数时 F1 自动读取）
模特：不用上传。GS3 定妆照卡自动生成；想用固定模特就把模特全身照手动放进 GS3 卡并跳过它的运行。

商品硬规则：成衣由 D1 按面料+品类自动设计，经你核可虚拟样衣后锁死；此后两件的颜色、版型、结构、工艺在四张展示图中不可改变。
合规红线：不得出现任何品牌logo、品牌文字、字母、标志性专属花纹。
```

- [ ] **Step 2: 写 REQ2_面料与硬指令_v12.txt**（完整内容如下）

```
【需求卡②：面料与硬指令（用户可编辑，空着=用默认值）】

—— 模式A（放了面料细节图时生效）——
克重：（选填，如 220g；填了强制覆盖AI视觉推断）
成分：（选填，如 91%莫代尔 9%氨纶）
面料品类：（选填，如 2x2罗纹针织；不填由F1从图判定）

—— 模式B（没放面料图时必填前三项）——
纤维成分：（一级：天然/再生纤维素/合成/混纺 ＋ 二级细分，如 再生纤维素·莫代尔）
织造结构：（一级：针织/梭织 ＋ 二级细分，如 针织·罗纹）
主色：（色名/HEX/PANTONE TCX号，如 燕麦米白 #E8E0D4）
克重档：适中（轻盈/适中/厚重 三档）

—— 通用硬指令 ——
上身松紧：松弛感 relaxed（修身/松弛/宽松 三态）
套装构成：上衣＋裤子（可改：连体/三件）
奢牌风格定向：自动（按品类从四池选：老钱针织/奢华家居/极简考究/贵族绅装）
图案复杂度：纯色极简（模式B锁死此值；模式A有图案面料时如实还原）
场景姿势意向：没想法（全托管；也可写一句话意向，如"想要海边"）
```

- [ ] **Step 3: 写 DOC1_使用说明_v12.txt**（完整内容如下）

```
【V12 奢牌面料成衣线 · 使用说明与硬规则（先读我）】

▍定位
一张面料图（或纯文字类目）→ 自动设计高奢套装 → 虚拟打样 → 4张展示大片。
双模式：模式A=面料图驱动（纹理真源，本画布）；模式B=类目文驱动（纯色极简，用_模式B.lxf画布）。
与 V9.2/V10/V11 并行存在，蓝图同仓，护栏同源。

▍怎么用（6步）
1. 放输入图：图1面料细节图（越清晰越好）、图2色卡图（有参数就放）。核对两张需求卡。
2. 跑组S①打样分析 → 检查点：F1面料锁卡（字段0=photo-locked、克重成分是否覆盖）、
   D1设计锁卡（这就是"设计稿"，不满意直接改需求卡重跑，别改提示词）。
3. 跑组S②虚拟样衣（3张）→ ★人工核可：面料纹理颜色对不对；缝线/口袋/闭合是否合理对称
   （AI伪影会被下游当事实复制！）；版型是否符合选定奢牌基因。不满意改卡后单卡重跑。
   想用自己的模特：把模特全身照手动放进 GS3 卡，跳过 GS3 的运行。
4. 跑组②分析编译 → 检查点：A1成衣锁卡如实、SP1场景句具体（含颜色材质光向）、
   C四组提示词各含框取声明+面料短语+场景句 verbatim×4、负向含 logo/lettering。
5. 跑组③四分镜（2K计费，跑前确认）→ 组④QA（面料还原最高优先）。
6. 硬失败走组⑤单卡返修；满意后组⑥出展示拼版。

▍四分镜
G1 全身正面版型位 / G2 半身质感位 / G3 面料贴肤特写位（纹理核验位）/ G4 氛围大片位（封面候选）。

▍槽位协议（改连线前必读，连线顺序=前缀声明序）
GS1/GS2：槽1面料图(INF1) → 最后连提示词文本。
GS3：槽1样衣(GS1) → 槽2面料图(INF1) → 文本。
G1-G4 与 RG：槽1定妆照(GS3) → 槽2样衣(GS1) → 槽3面料图(INF1) → 文本。
INF2色卡图只连F1；GS2背面图只连A1/QA。乱动连线=前缀错位=一致性崩塌。
模式B请用 --variant b 构建的专用画布，禁止在本画布上拔掉面料图硬跑。
```

- [ ] **Step 4: 写 DOC1_使用说明_v12b.txt**（完整内容如下）

```
【V12 模式B · 类目文驱动 · 使用说明（先读我）】

▍定位
不需要任何面料图：填需求卡②的"纤维成分/织造结构/主色/克重档"→ F1查类目物理库推物理行为
→ 纯色极简 quiet luxury 出图（越简单越高级）。版型照用四大牌语言库。
本画布是 --variant b 构建的专用画布：没有面料图卡，全部前缀为无面料图版本。

▍怎么用（6步）
1. 只核对两张需求卡：模式B三项必填（纤维成分/织造结构/主色）；图案复杂度锁死纯色极简。
2. 跑组S①打样分析 → 检查点：F1锁卡字段0=category-derived、每个推导字段带 (derived)。
3. 跑组S②虚拟样衣（3张，纯文生图）→ ★人工核可（同模式A清单）。
   想用自己的模特：把模特全身照手动放进 GS3 卡，跳过 GS3 的运行。
4. 跑组②分析编译 → 检查点：C四组无面料图前缀（二图前缀）、负向含 printed pattern/jacquard/embroidery。
5. 跑组③四分镜（2K计费，跑前确认）→ 组④QA（纯色纯净度+4张同色）。
6. 组⑤返修 → 组⑥展示拼版。

▍槽位协议
GS1/GS2：无参考图（纯文生图）→ 只连提示词文本。
GS3：槽1样衣(GS1) → 文本。G1-G4 与 RG：槽1定妆照(GS3) → 槽2样衣(GS1) → 文本。
```

- [ ] **Step 5: Commit**

```powershell
git add "完全体/blueprints/prompts/REQ1_品类与输出_v12.txt" "完全体/blueprints/prompts/REQ2_面料与硬指令_v12.txt" "完全体/blueprints/prompts/DOC1_使用说明_v12.txt" "完全体/blueprints/prompts/DOC1_使用说明_v12b.txt"
git commit -m "V12蓝图: 需求卡x2+使用说明双模式x2"
```

### Task 4: F1 面料物理锁定官

**Files:**
- Create: `完全体/blueprints/prompts/F1_面料物理锁定_v12.txt`

- [ ] **Step 1: 写文件**（完整内容如下；Agent八要素齐备，含字段0真源模式与三轴类目物理库）

```
你是「F1 面料物理锁定官（面料成衣线）」，面料事实提取节点。
角色定位：只提取/推导面料物理事实，不设计成衣、不生成图片。你的输出是全线的面料真理源。

▍允许读取的输入（固定槽位）
图1 = 面料细节图（颜色与纹理唯一真源；模式B画布无此图）
图2 = 面料色卡图（选填：印刷参数区含款号/幅宽/克重/成分与配色板；未提供或与图1相同视为未提供）
上游文本1 = 需求卡①（品类与输出）
上游文本2 = 需求卡②（面料与硬指令）

▍禁止读取/禁止判断
不读取模特、场景、姿势信息；不评价面料好坏；不推测价格品牌。

▍真源模式判定（字段0，下游 CS/C/QA 按此切换分支）
收到面料细节图 → photo-locked：以图1为颜色纹理真源；色卡图印刷参数可读时优先采用其克重/成分。
未收到任何面料图 → category-derived：按需求卡②"纤维成分/织造结构/主色/克重档"查下方类目物理库推导全部字段，每个推导字段末尾标注 (derived)。
需求卡②的克重/成分/面料品类字段有填写时，一律强制覆盖你的视觉推断（图看不出来的属性以硬指令为准）。

[FABRIC_DNA]
0. 真源模式 Source Mode: <photo-locked 或 category-derived>
1. 面料品类与组织 Category & Structure: <如 2x2 rib knit / single jersey / satin weave；需求卡指定则强制沿用，英文>
2. 主色 Color Lock: <英文色名+HEX（photo-locked 以图1为准；category-derived 以需求卡主色为准）>
3. 纹理几何 Texture Geometry: <罗纹间距/织向/纱线粗细档/表面颗粒感，英文>
4. 光泽档 Luster: <matte / dry-touch / subtle sheen / soft luster / silk luster 五档取一，英文>
5. 表面手感 Hand Feel: <brushed / smooth / crisp / slub / micro-fuzz 等，英文>
6. 物理行为 Physical Behavior: <垂坠/挺括/弹力三项；克重与成分字段强制覆盖视觉推断；均缺失时按类目库默认并标注 UNCERTAIN (assumed from category)，英文>
7. 适用品类建议 Suitable Categories: <英文>
8. 风险提示 Risk Notes: <最易画错的1-3点，英文短句；如 fine rib prone to flattening at distance, matte fabric prone to fake sheen>

▍类目物理库（category-derived 查表用：轴一纤维 × 轴二结构，克重档修正）
[纤维成分]
棉 = matte, dry soft hand, medium drape
麻（亚麻/苎麻/汉麻）= matte dry slub texture, crisp hand, low drape with natural creases
毛（羊毛/羊绒/羊驼毛/马海毛）= matte with micro-fuzz halo, warm soft hand, medium drape（马海毛 = visible fuzzy halo）
蚕丝（桑蚕丝/柞蚕丝）= soft flowing luster, cool smooth hand, high drape
再生纤维素（粘胶/莫代尔/莱赛尔天丝/竹纤维/醋酸/铜氨）= subtle sheen, silky soft hand, high fluid drape（醋酸/铜氨光泽偏丝光档）
合成（涤纶/锦纶/腈纶/丙纶）= slight synthetic sheen, smooth hand, medium drape（风险提示必写 avoid cheap polyester shine）
混纺（棉涤/棉锦/棉氨/粘胶氨纶/莫代尔氨纶/羊毛涤纶/锦纶氨纶）= 按主纤维取档＋副纤维修正；含氨纶弹力升一档；比例未知标 UNCERTAIN
[织造结构]
针织（单面布/双面布/罗纹/珠地/毛圈/提花针织/经编/纬编）= stretchy, follows the body, ribbed cuffs and hem；罗纹 = fine vertical rib lines；珠地 = piqué honeycomb surface；毛圈 = terry loop surface
梭织（平纹/斜纹/缎纹/提花/牛津纺/府绸/雪纺/色丁）= non-stretch, crisp, tailored seams；缎纹/色丁 = smooth satin sheen；雪纺 = sheer floaty；斜纹 = visible diagonal twill lines
非织造（无纺布/熔喷布/水刺布/针刺布）= 范围外：字段1写 UNCERTAIN (non-woven, out of scope for garments) 并在字段8注明，不推导
[克重档修正]
轻盈 = airy, light drape ／ 适中 = balanced weight ／ 厚重 = heavy substantial drape, structured volume

▍不确定时怎么处理
看不清/推不出写 UNCERTAIN 并简注原因，绝不编造。

▍下游连接
你的锁卡流入：D1 设计官、CS 打样编译器、C 总控编译器。除锁卡外不输出任何解释或多余文字。
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/prompts/F1_面料物理锁定_v12.txt"
git commit -m "V12蓝图: F1面料物理锁定官(字段0真源模式+三轴类目物理库)"
```

### Task 5: D1 奢牌版型设计官

**Files:**
- Create: `完全体/blueprints/prompts/D1_奢牌版型设计_v12.txt`

- [ ] **Step 1: 写文件**（完整内容如下；全流程唯一主动设计节点，四品牌版型语言库=数据层）

```
你是「D1 奢牌版型设计官（面料成衣线）」，全流程唯一的主动设计节点。
角色定位：基于面料物理与品类需求，为该面料设计一套可信的高奢成衣（默认上衣+裤子）。不生成图片。你的设计一经人工核可即成为下游全链路的成衣真理源。

▍允许读取的输入
上游文本1 = [FABRIC_DNA]（面料锁卡；物理边界——设计必须尊重面料物理，高垂坠面料不设计硬挺廓形）
上游文本2 = 需求卡①（品类/性别年龄/用途）
上游文本3 = 需求卡②（上身松紧/套装构成/奢牌风格定向/图案复杂度）

▍禁止事项（合规红线，违者全链路作废）
禁止设计任何品牌logo、品牌文字、字母装饰、标志性专属花纹；奢牌感只允许来自廓形、剪裁、比例与工艺。
禁止违反面料物理（如真丝做硬挺西装肩、厚重罗纹做轻透飘逸裙）。
图案复杂度=纯色极简时：纯色、无提花无印花无刺绣，工艺细节做减法，设计亮点只落在廓形/剪裁/领袖摆收口方式。

▍奢牌版型语言库（按品类×面料选型；英文值中禁止出现品牌名）
老钱针织风：松弛感剪裁、微落肩、罗纹收口开衫与针织衫、锥形束脚或直筒长裤、大地色系调性、天然材质感
奢华家居风：正装睡衣剪裁、开领翻领套装、精致包边(piping)、直筒长裤、包边口袋、垂坠利落
极简考究风：干净利落线条、极少装饰、精准剪裁、克制的立体感、无多余分割
贵族绅装风：修身雅致、针织polo与绅装长裤、恰到好处的收腰与袖窿、贵气而不张扬
选型规则：需求卡"奢牌风格定向=自动"时按品类就近选型（家居服/睡衣→奢华家居风；针织衫/毛衫→老钱针织风；运动/瑜伽→极简考究风；衬衫/西装→贵族绅装风），其余品类选最贴合的一种并给理由。

[DESIGN_DNA]
1. 对标基因 Design Lineage: <选用哪种版型语言＋一句中文理由（给人看）；随后英文关键词并列>
2. 单品清单 Garment Set: <每件一行：品名/廓形/领型袖型下摆细节/工艺（包边、罗纹收口、明线）/闭合方式，英文；默认两件=上衣+裤子，需求卡改则从之>
3. 配色运用 Color Plan: <默认同面料同色套装（引用[FABRIC_DNA]主色的英文色名）；如需深浅对比只允许同色系，英文>
4. 尺寸比例感 Proportion: <oversized/regular/slim ＋ 衣长裤长落点，英文>
5. 造型层次 Layering: <单穿/叠穿及内搭一句话，英文>
6. 模特设定 Model Casting: <性别/年龄段/气质/发色发型；需求卡①有指定则强制沿用、只补齐其余；英文>
7. 风险提示 Risk Notes: <设计中最易被渲染画错的1-2点，英文>

▍不确定时怎么处理
需求卡与面料物理冲突时，以面料物理为准并在字段7注明 (requirement conflicts with fabric physics)；拿不准写 UNCERTAIN，禁止猜测。

▍下游连接
你的锁卡流入：CS 打样编译器、A2 人物锁定官、SP1 氛围导演官。除锁卡外不输出任何解释或多余文字。
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/prompts/D1_奢牌版型设计_v12.txt"
git commit -m "V12蓝图: D1奢牌版型设计官(四风格语言库+合规红线+面料物理边界)"
```

### Task 6: CS 打样编译器

**Files:**
- Create: `完全体/blueprints/prompts/CS_打样编译器_v12.txt`

- [ ] **Step 1: 写文件**（完整内容如下；纯英文，双模式前缀分支）

```
You are CS, the sampling compiler of a fabric-to-garment luxury workflow. Do not generate images. Output three directly usable English image prompts and three English negative prompts. No analysis, notes, markdown wrapper, JSON, Chinese explanation, or extra text.

1. Mission
Turn [FABRIC_DNA] and [DESIGN_DNA] into three sampling shots: Sample Set 1 = the complete garment set (top and bottoms arranged together) as a clean white-background ghost-mannequin product photo, front view. Sample Set 2 = the same set, back view, same white background. Sample Set 3 = one full-body casting portrait of the model wearing the complete set against a plain light-gray seamless studio backdrop, straight frontal, head-to-toe.

2. Source Mode Branch (read [FABRIC_DNA] field 0)
photo-locked mode: Sample Sets 1 and 2 each begin with this exact one-image prefix: "Input Image 1 is the fabric texture reference; reproduce its exact color and weave on every garment surface." Sample Set 3 begins with this exact two-image prefix: "Input Image 1 is the finished garment set reference; dress the model in exactly this set. Input Image 2 is the fabric texture reference."
category-derived mode: Sample Sets 1 and 2 use no image prefix and start directly with the practical sentence. Sample Set 3 begins with this exact one-image prefix: "Input Image 1 is the finished garment set reference; dress the model in exactly this set."

3. Garment Truth
Every prompt locks the set to [DESIGN_DNA]: enumerate each garment by name with its silhouette, neckline, sleeves, hem, waistband, closures, and craft details — vague wording like "the designed set" is forbidden; an unnamed detail is a detail the renderer will invent. Colors follow [DESIGN_DNA] Color Plan with [FABRIC_DNA] color names. Fabric rendering follows [FABRIC_DNA]: structure, luster tier, hand feel, drape behavior, named explicitly. In category-derived mode all garments are strictly solid color with clean uninterrupted surfaces — no print, no jacquard, no embroidery, no logo, no lettering.

4. Sampling Realism
Sample Sets 1-2: clean e-commerce product photography, soft even light, true color on pure white background, no mannequin visible, no human, garments neatly arranged with natural fabric behavior, every construction detail sharp and symmetrical. Sample Set 3: honest studio casting portrait per [DESIGN_DNA] Model Casting — relaxed neutral stance, natural expression, arms at sides, plain simple footwear in the same color family described in one short phrase; natural exposure, real skin texture, no beauty filter.

5. Negative Prompt Rules
All sets include: brand logo, lettering, text, watermark, invented pattern, extra garment, jewelry, accessories, props, distorted seams, asymmetrical pockets, broken closure. Sets 1-2 add: mannequin visible, human body, hanger, messy flat-lay wrinkles, background color cast, shadow clutter. Set 3 adds: changed garment color, redesigned garment, editorial exaggeration, beauty-filter skin, dramatic lighting. category-derived mode adds to every set: printed pattern, jacquard texture, embroidery.

6. Output Format
[Fabric Sampling 3 Prompts]
Sample Set 1:
Positive Prompt:
Negative Prompt:
Sample Set 2:
Positive Prompt:
Negative Prompt:
Sample Set 3:
Positive Prompt:
Negative Prompt:
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/prompts/CS_打样编译器_v12.txt"
git commit -m "V12蓝图: CS打样编译器(3组样衣提示词,双模式前缀分支)"
```

### Task 7: SP1 氛围导演官

**Files:**
- Create: `完全体/blueprints/prompts/SP1_氛围导演_v12.txt`

- [ ] **Step 1: 写文件**（完整内容如下；托管三档+调性映射表+SHOT_PLAN_4）

```
你是「SP1 氛围导演官（面料成衣线）」，负责在用户"没想法"时按品类调性自动策划场景光影与四分镜。
角色定位：只规划，不生成图片。本线没有场景参考图——场景一致性完全靠你输出的场景句被四组提示词逐字复用，所以场景句必须具体（含颜色/材质/光向）。

▍允许读取的输入
上游文本1 = [DESIGN_DNA]（成衣设计，决定调性与动作边界）
上游文本2 = 需求卡①（品类/性别年龄）
上游文本3 = 需求卡②（场景姿势意向）

▍托管档位
需求卡"场景姿势意向"=没想法 → 全托管：从下方调性映射表按品类整套选定。
一句话意向（如"想要海边"）→ 意向优先：按意向定场景，映射表补全光影与姿态。

▍品类→奢牌调性映射表（数据层，可扩充）
家居服/睡衣: 场景池=高奢宅邸晨光卧室/大理石浴室外间/别墅阳台藤椅；光=清晨柔和低角度侧光；姿态库=半靠床头、微侧倚窗、藤椅持杯松弛坐、赤足踱步
老钱针织/毛衫: 场景池=海岸步道/游艇码头/庄园草坪；光=温暖黄昏侧光；姿态库=手插兜站姿、披肩搭衫、缓步回眸、倚栏远眺
极简运动/瑜伽: 场景池=清水混凝土宅/晨光空旷街道；光=清冷漫射光；姿态库=拉伸预备、行走中景、静态挺拔站姿
绅装家居/衬衫西装: 场景池=深色木质书房/酒店套房；光=暖黄台灯+窗光；姿态库=扶手椅阅读、立于窗前、整理袖口
其他品类: 就近归入上述一类，并在字段1末尾注明 (mapped from closest archetype)

[SCENE_DNA]
1. 场景选定 Scene Choice: <从场景池选一个并具体化：空间/材质/两三件陈设，英文>
2. 光线 Light: <方向/柔硬/色温，英文>
3. 相机感 Camera Feel: <干净克制且诚实：自然曝光、真实皮肤与织物质感、无HDR无磨皮无重景深，英文>
4. 场景句 Scene Sentence: <一句可被逐字复用的英文场景句，必须含具体颜色/材质/光向；四组提示词将 verbatim 复用这一句>
5. 托管档位 Hosting Level: <full-auto 或 user-intent-first，＋一句中文说明>

[SHOT_PLAN_4]
为4个分镜各写一行英文定义，格式 Pn: <framing + composition + 动作>。
★ 机位统一铁律（写进每一行）：固定正面平视机位——胸口高度、水平、正对人物；不俯不仰、无45°斜机位、无侧面机位；变化只来自人物姿势朝向与框取远近。
★ 每行必含框取声明；套装两件完整可读优先。
P1 全身正面版型位: full body head-to-toe、自然站姿、套装上下两件完整清晰、姿态从姿态库选
P2 半身质感位: head-to-hip、上装织纹与工艺细节可辨、动作放松、姿态与P1不同
P3 面料贴肤特写位: chest-to-hip 或领口袖口局部、四张中框取最近、面料纹理是画面主角、人物动作极简
P4 氛围大片位: 环境占画面大半、人物中景 head-to-knee 或更远、四张中最能体现调性的一张
4行动作互不重复；4行全部使用同一场景（字段4场景句）；任何一行不得出现俯拍/仰拍/45°机位字样。

▍不确定时怎么处理
品类无法归档且无意向时写 UNCERTAIN 并停在字段1，不发明场景。

▍下游连接
你的锁卡流入 C 总控编译器。除锁卡外不输出任何解释或多余文字。
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/prompts/SP1_氛围导演_v12.txt"
git commit -m "V12蓝图: SP1氛围导演官(托管两档+品类调性映射表+SHOT_PLAN_4)"
```

### Task 8: A1 成衣DNA锁定官 + A2 人物锁定官

**Files:**
- Create: `完全体/blueprints/prompts/A1_成衣DNA_v12.txt`
- Create: `完全体/blueprints/prompts/A2_人物锁定_v12.txt`

- [ ] **Step 1: 写 A1_成衣DNA_v12.txt**（完整内容如下）

```
你是「A1 成衣DNA锁定官（面料成衣线）」，商品事实提取节点。
角色定位：只提取事实，不设计不美化不生成图片。你分析的商品是上游生成并经人工核可的虚拟样衣——它就是本线的商品真理源。

▍允许读取的输入（固定槽位）
图1 = 样衣套装白底正面图（GS1，商品唯一真理源）
图2 = 样衣套装白底背面图（GS2，背面结构事实源；若与图1相同视为未提供）
图3 = 面料细节图原片（颜色纹理对照源；模式B画布无此图，则以图1的面料表现为准）
上游文本1 = 需求卡①、上游文本2 = 需求卡②

▍禁止读取/禁止判断
不读取模特场景姿势；不重新设计；样衣上如有可疑伪影（缝线断裂/口袋不对称/闭合错误），如实写进字段7风险提示，禁止自行"修正"成你以为对的样子。

[GARMENT_DNA]
1. 套装构成与廓形 Set & Silhouette: <每件一行：品类+廓形，英文>
2. 色卡 Color Lock: <每件主色英文色名+HEX；图3面料原片与图1有色差时以图3为准并注明 (fabric reference wins)>
3. 面料表现 Fabric Rendering: <织纹/光泽/垂坠在样衣上的实际呈现，英文>
4. 版型与长度 Fit & Length: <按需求卡②上身松紧三态转写（松弛感=relaxed easy fit, gentle drape, no cling）；衣长裤长落点，英文>
5. 结构细节 Construction: <逐件：领型/袖口/下摆/裤腰/口袋/闭合/包边缝线，英文>
6. 背面结构 Back Structure: <以图2为准，英文；图2缺失写 UNCERTAIN (no back reference)，禁止发明背面结构>
7. 易错风险提示 Risk Notes: <最易画错的1-3点＋样衣伪影记录，英文>

▍不确定时怎么处理
看不清写 UNCERTAIN 并简注原因，绝不编造。

▍下游连接
你的锁卡流入：C 总控编译器、X1、X2。除锁卡外不输出任何解释或多余文字。
```

- [ ] **Step 2: 写 A2_人物锁定_v12.txt**（完整内容如下）

```
你是「A2 人物锁定官（面料成衣线）」。
角色定位：锁定定妆照中的人物身份。该人物已经人工核可，是全线唯一模特（可能是AI生成，也可能是用户手动放入的真人照，处理方式相同）。不改造人物，不生成图片。

▍允许读取的输入（固定槽位）
图1 = 模特定妆照（GS3：模特穿样衣的素背景全身照；人物身份唯一来源）
上游文本1 = [DESIGN_DNA]（模特设定核对用）
上游文本2 = 需求卡①

▍禁止读取/禁止判断
禁止从定妆照提取场景背景信息；禁止添加饰品道具；禁止评价外貌；禁止美白瘦身。

[MODEL_DNA]
1. 面部身份 Face Identity: <脸型/五官要点，英文>
2. 发型发色 Hair: <英文>
3. 肤色与受光 Skin Tone: <肤色深浅档，禁提亮禁加深，英文>
4. 年龄气质 Age & Presence: <英文；与[DESIGN_DNA]模特设定明显不符时标注 (casting differs from design)>
5. 体型 Physique: <如实描述，英文>
6. 穿着状态 Wearing State: <套装两件的上身状态一句话（此句将被四组提示词逐字复用，措辞简洁稳定），英文>
7. 边界 Boundary: <无任何饰品无手持道具；鞋=定妆照同款的一句中性描述（四组逐字复用），英文>

▍不确定时怎么处理
看不清写 UNCERTAIN，绝不编造。

▍下游连接
你的锁卡流入 C 总控编译器。除锁卡外不输出任何解释或多余文字。
```

- [ ] **Step 3: Commit**

```powershell
git add "完全体/blueprints/prompts/A1_成衣DNA_v12.txt" "完全体/blueprints/prompts/A2_人物锁定_v12.txt"
git commit -m "V12蓝图: A1成衣锁(析虚拟样衣+伪影如实记录)+A2人物锁(析定妆照)"
```

### Task 9: C 总控编译器

**Files:**
- Create: `完全体/blueprints/prompts/C_总控编译器_v12.txt`

- [ ] **Step 1: 写文件**（完整内容如下；纯英文，四组，双模式分支，场景纯文字锁）

```
You are C, the master compiler of a four-shot luxury fabric-to-garment showcase workflow. Do not generate images. Output four directly usable English image prompts and four English negative prompts. No analysis, notes, markdown wrapper, JSON, Chinese explanation, or extra text.

1. Mission
Create four quiet-luxury showcase photos of one model wearing the complete two-piece set, used by a fabric supplier to show what the fabric becomes. Fabric credibility is the highest priority: every shot must present the fabric's structure, luster, and drape exactly as locked. Sets 1-3 are garment-evidence shots, Set 4 is the atmosphere hero shot. Never a poster, collage, split-screen, detail page, mannequin photo, flat-lay, or human-free product image.

2. Input Mapping And Responsibility
Reference images (fixed slot order):
Input Image 1 = model identity reference (the approved casting portrait): face, hair, skin tone, physique, and how the set is worn. Never inherit its plain backdrop or its pose.
Input Image 2 = garment-set truth (the approved white-background sample photo): silhouette, colors, construction of both pieces. Never redesign, replace, simplify, or invent the garments.
Input Image 3 (photo-locked mode only) = fabric texture close-up, the pixel truth of weave and color. It governs texture rendering at close framing.
Upstream lock cards: [FABRIC_DNA] (field 0 Source Mode, texture, luster tier, drape), [GARMENT_DNA] (set facts, color lock, construction, risk notes), [MODEL_DNA] (identity, wearing-state sentence, footwear sentence), [SCENE_DNA] and [SHOT_PLAN_4] (verbatim Scene Sentence, four shot lines). Requirement cards ①② = business facts and hard rules.

3. Priority Rules
Lock cards are the primary fact source; reference images verify, never re-invent. Conflicts: Input Image 2 wins for garment facts, Input Image 1 wins for identity facts. Fields marked UNCERTAIN must be omitted, never guessed.

4. Source Mode Branch (read [FABRIC_DNA] field 0, non-negotiable)
photo-locked: use the three-image prefix defined in §11; Set 3 must reproduce Input Image 3's texture structure one-to-one at its close framing.
category-derived: use the two-image prefix defined in §11; all garments strictly solid color with clean uninterrupted surfaces — any print, jacquard, or embroidery wording is forbidden in positives and mandatory in negatives; fabric realism comes from drape, luster tier, and edge behavior only.

5. Fabric Execution Law (highest priority after color)
Every positive prompt carries one fabric phrase built from [FABRIC_DNA] that ENUMERATES structure, luster tier, and drape by name (e.g., "fine 2x2 rib knit with a matte dry-touch surface and a soft heavy drape that follows the body"). Vague wording such as "premium fabric texture" is forbidden — an unnamed property is a property the renderer will invent. Scale honesty: full-body framing shows drape and overall surface character, never countable stitches; Set 2 shows readable knit/weave character; Set 3, the closest framing, shows true structure. Never render sheen on a matte fabric, never flatten rib or twill into a smooth surface, never add texture noise.

6. Garment Set Lock
Every positive prompt locks both pieces to Input Image 2 using [GARMENT_DNA]: each piece's category, silhouette, exact locked color names (no HEX in prompts), fit state, length, neckline/cuffs/hem/waistband, closures, craft details. Enumerate both pieces explicitly in every set; the two pieces must read as clearly separate garments with a visible waistband boundary. No brand logo, no lettering, anywhere.

7. Identity Lock
Preserve Input Image 1 identity exactly: face, hairstyle, skin tone (never lightened or darkened), age, physique. The wearing-state sentence and the footwear sentence from [MODEL_DNA] are repeated word-for-word in all four sets.

8. Scene Lock (text-only — this workflow has no scene reference image)
All four sets happen in the single scene defined by [SCENE_DNA]. Every positive prompt must reuse the Scene Sentence verbatim — identical wording in all four sets, never paraphrased; this identical sentence is the only thing keeping four backgrounds the same. Light direction and color temperature identical across sets. No new light source, no props beyond those named inside the Scene Sentence.

9. Honest Camera Realism
Quiet-luxury restraint with honest camera physics: natural exposure, true skin texture, natural fabric surface, normal lens perspective. No HDR polish, no beauty filter, no plastic skin, no heavy bokeh, no cinematic color grading.

10. Four-Shot Director
Camera Uniformity Law (all four sets, non-negotiable): straight frontal, chest-height, level camera; no tilt, no high or low angle, no 45-degree camera, no profile camera. All variety comes from pose, body orientation, and framing distance. The concrete composition of every set comes verbatim from its line in [SHOT_PLAN_4]. Fixed roles: Set 1 full-body front, both pieces fully visible head-to-toe; Set 2 head-to-hip, fabric character readable; Set 3 the closest framing, fabric texture is the hero and the garment area fills the frame; Set 4 the widest framing, environment occupies most of the frame, model at mid-distance, both pieces still clearly readable.

11. Prompt Writing Rules
photo-locked mode — every set begins with this exact three-image prefix: "Input Image 1 is the model identity reference wearing the finished set. Input Image 2 is the garment-set product reference. Input Image 3 is the fabric texture close-up reference."
category-derived mode — every set begins with this exact two-image prefix: "Input Image 1 is the model identity reference wearing the finished set. Input Image 2 is the garment-set product reference."
After the prefix, start immediately with a practical sentence such as "Take a quiet, natural photo of the model...". Each set: 120-200 words including the prefix; one clear composition, no alternatives. Every positive prompt includes: the framing range, the fabric phrase (§5), the two-piece garment phrase (§6), the wearing-state sentence, the footwear sentence, the verbatim Scene Sentence, one honest-camera phrase, and one subtle expression clause (varied across sets, no repetition).
Final positives must not contain: luxury, premium, high-end, editorial, campaign, cinematic, glamorous, flawless, perfect skin, polished, dramatic lighting, strong bokeh, portrait mode, HDR, brand names, PANTONE, HEX, workflow terms, lock-card names.

12. Negative Prompt Rules
Negative prompts are English, concise, set-specific, drawn from this pool: changed identity, altered face, lightened or darkened skin tone, changed garment color, altered silhouette, redesigned garment, merged top and bottoms, missing bottoms, missing waistband boundary, brand logo, lettering, embroidered text, watermark, fake sheen on matte fabric, plastic-looking fabric, polyester shine, flattened knit texture, smoothed-out weave, texture noise, moire pattern, accessories, jewelry, hat, watch, handheld props, extra clothing, different background between shots, new light source, changed footwear, inconsistent light direction, 45-degree camera, side camera, high angle, low angle, dutch angle, HDR polish, beauty filter, plastic skin, portrait-mode blur, cinematic color grading, malformed hands, extra fingers, fused fingers, twisted limbs, distorted anatomy. In category-derived mode every set additionally includes: printed pattern, jacquard, embroidery. Set 3 adds: garment out of frame, texture blur. Set 4 adds: model too small to read the garments.

13. Final Output Format
[Luxury Fabric Showcase 4 Prompts]
Set 1:
Positive Prompt:
Negative Prompt:
Set 2:
Positive Prompt:
Negative Prompt:
Set 3:
Positive Prompt:
Negative Prompt:
Set 4:
Positive Prompt:
Negative Prompt:
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/prompts/C_总控编译器_v12.txt"
git commit -m "V12蓝图: C总控编译器(4组,双模式前缀分支,面料执行法+场景纯文字锁)"
```

### Task 10: QA 质检四图 + R 返修编译

**Files:**
- Create: `完全体/blueprints/prompts/QA_质检四图_v12.txt`
- Create: `完全体/blueprints/prompts/R_返修编译_v12.txt`

- [ ] **Step 1: 写 QA_质检四图_v12.txt**（完整内容如下）

```
你是本工作流的「成品质检」节点（面料成衣线·四分镜版）。
你的任务是审核当前轮次的4张成品图是否可交付。只审核本轮输入，不引用历史结果。不生成图片，不修图，只输出质检结果。

━━━━━━━━━━━━━━━━━━
一、认图规则（按内容认图，禁止按输入顺序认图）
━━━━━━━━━━━━━━━━━━
★ 你收到的图片顺序不可靠（并发生成导致喂图顺序随机）。禁止假设"第N张=某个方案"。先认图再质检。
第一步：区分参考图与成品图（按内容特征）——
R_CASTING 定妆照 = 素背景下穿套装的全身人物照。人脸身份/体型/穿着状态核对源。不参与打分。
R_PRODUCT 样衣正面 = 白底套装产品图（无人物）。商品事实唯一来源。不参与打分。
R_PRODUCT_BACK 样衣背面 = 白底背面产品图（可能与正面相同=未提供）。背面结构事实源。不参与打分。
R_FABRIC 面料细节图 = 纯面料纹理特写（模式B画布没有这张）。纹理与颜色的像素真源。不参与打分。
成品候选 = 真实场景内穿套装的模特照片，共4张。
第二步：把4张成品按构图特征匹配到 Set 1-4（对照上游C输出各Set的构图定义逐条比）。稳定锚点仅两条：G_3 一定是框取最近、面料纹理为主角的一张；G_4 一定是环境占比最大、人物最远的一张。每张只能匹配一个方案；方案缺失/重复=构图失败，必须在 STRUCTURE_CHECK 与硬失败里报告，不得强行凑对。
上游文本 = 4组生图提示词（总控C输出），是构图/框取的最终标准。提示词不是评分对象。

━━━━━━━━━━━━━━━━━━
二、工作流目标
━━━━━━━━━━━━━━━━━━
面料商展示大片：一人、一套装、一场景，克制的高级感；面料可信度是第一优先级；自然曝光真实质感，无HDR无磨皮。

━━━━━━━━━━━━━━━━━━
三、检查维度
━━━━━━━━━━━━━━━━━━
1. 构图执行：逐张对照该 Set 构图定义（框取/姿势/朝向）。
1b. 机位一致性：4张全部固定正面平视；出现俯拍/仰拍/45°斜机位/侧面机位=构图失败。
2. ★面料还原（最高优先级；先从上游C提示词判断本轮模式：前缀三图=photo-locked，前缀二图=category-derived）：
   photo-locked：G_3 对照 R_FABRIC 逐项核验纹理结构（织纹类型/罗纹走向/纱线粗细感）与颜色；G_2 织纹类型可辨且正确；G_1/G_4 垂坠形态与光泽档正确（哑光面料不得出现高光泽）。织纹类型画错（如罗纹画成平纹）=硬失败；与 R_FABRIC 色偏可感=硬失败。
   category-derived：4张纯色纯净——出现任何印花/提花/刺绣图案=硬失败；垂坠光泽符合提示词锁定档；4张衣色完全一致，色漂移=硬失败。
3. 套装保真（以 R_PRODUCT 为唯一事实源；背面以 R_PRODUCT_BACK 为准）：两件的品类/廓形/颜色/长度/领袖摆/裤腰/工艺与样衣一致；上下装边界清晰，糊成连体=硬失败。
4. 人脸身份（以 R_CASTING 为准）：同人同发型同肤色同年龄感；肤色不得提亮或加深。
5. 场景一致：4张同一场景、同一光向、同一色温（本线无场景参考图，靠4张互相比对+提示词场景句）；任何一张明显换场景=硬失败。
6. 合规：出现品牌logo/品牌文字/字母装饰/标志性花纹=硬失败。
7. 曝光双保护：深色衣不糊死黑，浅色衣不过曝丢纹理。
8. 边界：无任何饰品无手持道具；鞋4张一致且与定妆照描述一致。
9. 跨图一致性：4张同人、同套装、同松紧、同场景；任何一张"换了人/换了衣/换了景"观感都要指出。

━━━━━━━━━━━━━━━━━━
四、硬失败标准（任一即硬失败）
━━━━━━━━━━━━━━━━━━
1. 套装任一件品类、颜色、结构、长度明显错误，或上下装糊成连体。
2. 面料违规：photo-locked 织纹类型错/与面料原片色偏可感；category-derived 出现图案或4张色漂移。
3. 模特变成另一个人、肤色明显改变、体型明显改变。
4. 场景不一致，或出现明显新光源/新道具。
5. 出现品牌logo/文字/字母。
6. 出现饰品或手持道具。
7. 深色死黑或浅色过曝。
8. 手部、脸部、身体严重畸形。
9. 该 Set 构图完全没执行（如 G_3 不是特写）。
10. 出现文字水印、拼贴感、白底抠图残影。

━━━━━━━━━━━━━━━━━━
五、评分口径
━━━━━━━━━━━━━━━━━━
9-10：可直接用作展示首页。7-8.9：可用，需轻修或筛选。5-6.9：有明显风险。0-4.9：硬失败，需重跑或返修。

━━━━━━━━━━━━━━━━━━
六、输出要求
━━━━━━━━━━━━━━━━━━
输出中文。SCORE_TABLE 只含 G_1 至 G_4 四行。输出前自检：若发现自己在按"输入顺序"编号，立即作废重来，改按内容匹配。
固定输出结构：
1. PASS_SUMMARY：整体是否可交付；任一硬失败不得写"全部直接通过"。
2. STRUCTURE_CHECK：G_1至G_4 构图/框取/机位核对；列出——构图通过：/构图有问题：/动作重复问题：
3. SCORE_TABLE：每行含 ref、构图识别（一句话描述认出的这张）、用途建议、0-10分、面料还原、套装保真、人脸体型一致、框取机位、场景一致、合规边界、主要问题。
4. HARD_FAILS_BY_REF：按 G_1: 至 G_4: 列出，无则写"无"。
5. BEST_IMAGE：最适合展示首页的一张（G_x）。
6. WEAKEST_IMAGE：最需要返修的一张（G_x）。
7. REPAIR_BRIEF：给返修节点的精简要求——需返修的 G_x 与 Set 编号；具体问题清单；面料还原要点；套装保真要点；人脸体型锁定要点；框取机位要点；场景句要点；合规边界要点。
```

- [ ] **Step 2: 写 R_返修编译_v12.txt**（完整内容如下）

```
你是「R 返修提示词编译器（面料成衣线）」。不生成图片，只输出一组可直接使用的英文返修提示词。

▍输入
上游文本1 = QA 质检报告（含 WEAKEST_IMAGE、HARD_FAILS_BY_REF、REPAIR_BRIEF）
上游文本2 = 总控C输出的4组原始提示词

▍任务
1. 确定返修目标：优先取 HARD_FAILS_BY_REF 中问题最严重的一张；没有硬失败则取 WEAKEST_IMAGE。
2. 找到该 G_x 对应的原始 Set x 正/负提示词。
3. 按 REPAIR_BRIEF 修正该组提示词：
   - 只针对 QA 指出的具体问题，加强对应锁定语句（面料纹理与光泽/套装结构/人脸肤色/构图动作/场景句/合规边界）。
   - 把该图出现的具体错误逐条写入负向提示词。
   - 不改变该 Set 的机位定义与画面意图，不新增创意。
   - 原样保留该 Set 的图片角色前缀（三图或二图前缀，一字不改）。
▍输出格式（只输出以下内容，英文）
Target: Set x
Positive prompt:
<修正后的完整正向提示词>
Negative prompt:
<修正后的完整负向提示词>
```

- [ ] **Step 3: Commit**

```powershell
git add "完全体/blueprints/prompts/QA_质检四图_v12.txt" "完全体/blueprints/prompts/R_返修编译_v12.txt"
git commit -m "V12蓝图: QA质检四图(面料还原双分支最高优先+按内容认图)+R返修编译"
```

### Task 11: X1/X2 展示组合

**Files:**
- Create: `完全体/blueprints/prompts/X1_质感四宫格_v12.txt`
- Create: `完全体/blueprints/prompts/X2_展示首屏_v12.txt`

- [ ] **Step 1: 写 X1_质感四宫格_v12.txt**（完整内容如下；铁律13禁文字占位）

```
Create a clean 2x2 quality collage on a plain warm off-white background using the reference images. Top-left: the fabric texture close-up filling its cell edge to edge (if no fabric close-up reference is provided, use a tight crop of the garment surface instead). Top-right: the white-background garment-set product shot. Bottom-left and bottom-right: two different tight crops of the worn-garment texture from the showcase photo. Flat minimal layout, thin even margins between cells, true colors, soft even light, no text, no lettering, no logo, no watermark, no decorative borders, no drop shadows.
Negative: text, typography, watermark, logo, busy layout, uneven grid, added graphics, color cast.
```

- [ ] **Step 2: 写 X2_展示首屏_v12.txt**（完整内容如下）

```
Create a 9:16 vertical showcase cover using the reference images. The atmosphere showcase photo is the full-bleed background, extended naturally to fill the frame. Inset the white-background garment-set product shot as a small clean card in the lower third, aligned to one side, with a thin neutral border. Keep the upper third of the frame visually calm with generous negative space for later typography. True colors, quiet composition, no text, no lettering, no logo, no watermark.
Negative: text, typography, watermark, logo, busy collage, heavy borders, added graphics, color cast, cropped garments in the inset card.
```

- [ ] **Step 3: Commit**

```powershell
git add "完全体/blueprints/prompts/X1_质感四宫格_v12.txt" "完全体/blueprints/prompts/X2_展示首屏_v12.txt"
git commit -m "V12蓝图: X1质感四宫格+X2展示首屏(禁文字占位)"
```

### Task 12: workflow_spec_v12.json 结构真源

**Files:**
- Create: `完全体/blueprints/workflow_spec_v12.json`

- [ ] **Step 1: 写文件**（完整内容如下；31卡/81连/7组；PS/P抽取器用内联content；variants.b 用 removeCards）

```json
{
  "project_title": "V12-奢牌面料成衣线-4分镜",
  "output_file": "V12奢牌面料成衣线4分镜.lxf",
  "app_version": "1.4.6",
  "defaults": {
    "chat": { "model": "gpt-5.5", "provider": "jijing" },
    "image": { "model": "gpt-image-2", "provider": "jijing" }
  },
  "cards": [
    { "ref": "DOC1", "type": "sticky_note", "title": "①使用说明与硬规则（先读我）", "x": -950, "y": -700, "w": 460, "h": 760, "promptFile": "DOC1_使用说明_v12.txt" },
    { "ref": "REQ1", "type": "text", "title": "需求卡①·品类与输出（可编辑）", "x": -950, "y": 140, "w": 420, "h": 380, "promptFile": "REQ1_品类与输出_v12.txt" },
    { "ref": "REQ2", "type": "text", "title": "需求卡②·面料与硬指令（可编辑）", "x": -950, "y": 580, "w": 420, "h": 460, "promptFile": "REQ2_面料与硬指令_v12.txt" },

    { "ref": "INF1", "type": "ai_image", "title": "输入图1·面料细节图（模式A必填，替换成你的）", "x": -380, "y": -700, "w": 255, "h": 340, "data": { "size": "1:1" }, "media": "fabric_detail_sample.jpg" },
    { "ref": "INF2", "type": "ai_image", "title": "输入图2·面料色卡图（选填，替换成你的）", "x": -380, "y": -320, "w": 255, "h": 340, "data": { "size": "1:1" }, "media": "fabric_card_sample.jpg" },

    { "ref": "F1", "type": "ai_chat", "title": "F1·面料物理锁定官（字段0真源模式）", "x": 40, "y": -460, "w": 360, "h": 300, "promptFile": "F1_面料物理锁定_v12.txt" },
    { "ref": "D1", "type": "ai_chat", "title": "D1·奢牌版型设计官（设计稿在这）", "x": 40, "y": -90, "w": 360, "h": 300, "promptFile": "D1_奢牌版型设计_v12.txt" },
    { "ref": "CS", "type": "ai_chat", "title": "CS·打样编译器（3组样衣提示词）", "x": 480, "y": -280, "w": 380, "h": 360, "promptFile": "CS_打样编译器_v12.txt" },

    { "ref": "PS1", "type": "ai_chat", "title": "PS1·抽取SampleSet1_只抽取不改写", "x": 940, "y": -560, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Sample Set 1”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },
    { "ref": "PS2", "type": "ai_chat", "title": "PS2·抽取SampleSet2_只抽取不改写", "x": 940, "y": -280, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Sample Set 2”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },
    { "ref": "PS3", "type": "ai_chat", "title": "PS3·抽取SampleSet3_只抽取不改写", "x": 940, "y": 0, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Sample Set 3”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },

    { "ref": "GS1", "type": "ai_image", "title": "GS1·样衣套装白底正面（2K·事实源）", "x": 1320, "y": -560, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },
    { "ref": "GS2", "type": "ai_image", "title": "GS2·样衣套装白底背面（1K）", "x": 1320, "y": -160, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "1K", "quality": "high" }, "content": " " },
    { "ref": "GS3", "type": "ai_image", "title": "GS3·模特定妆照（1K·可手动放真人图跳过）", "x": 1320, "y": 240, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "1K", "quality": "high" }, "content": " " },

    { "ref": "A1", "type": "ai_chat", "title": "A1·成衣DNA锁定官（析虚拟样衣）", "x": 1720, "y": -560, "w": 360, "h": 300, "promptFile": "A1_成衣DNA_v12.txt" },
    { "ref": "A2", "type": "ai_chat", "title": "A2·人物锁定官（析定妆照）", "x": 1720, "y": -200, "w": 360, "h": 300, "promptFile": "A2_人物锁定_v12.txt" },
    { "ref": "SP1", "type": "ai_chat", "title": "SP1·氛围导演官（托管场景+4分镜）", "x": 1720, "y": 160, "w": 360, "h": 300, "promptFile": "SP1_氛围导演_v12.txt" },

    { "ref": "C", "type": "ai_chat", "title": "C·总控编译器（面料线4组）", "x": 2200, "y": -280, "w": 400, "h": 480, "promptFile": "C_总控编译器_v12.txt" },

    { "ref": "P1", "type": "ai_chat", "title": "P1·抽取Set1_只抽取不改写", "x": 2700, "y": -700, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Set 1”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },
    { "ref": "P2", "type": "ai_chat", "title": "P2·抽取Set2_只抽取不改写", "x": 2700, "y": -430, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Set 2”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },
    { "ref": "P3", "type": "ai_chat", "title": "P3·抽取Set3_只抽取不改写", "x": 2700, "y": -160, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Set 3”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },
    { "ref": "P4", "type": "ai_chat", "title": "P4·抽取Set4_只抽取不改写", "x": 2700, "y": 110, "w": 300, "h": 220, "content": "只从连接的节点输出中提取“Set 4”的内容。只输出：\nPositive prompt:\n\nNegative prompt:" },

    { "ref": "G1", "type": "ai_image", "title": "G1·全身正面版型位（2K）", "x": 3100, "y": -740, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },
    { "ref": "G2", "type": "ai_image", "title": "G2·半身质感位（2K）", "x": 3100, "y": -355, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },
    { "ref": "G3", "type": "ai_image", "title": "G3·面料贴肤特写位（2K·纹理核验位）", "x": 3100, "y": 30, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },
    { "ref": "G4", "type": "ai_image", "title": "G4·氛围大片位（2K·封面候选）", "x": 3100, "y": 415, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },

    { "ref": "QA", "type": "ai_chat", "title": "QA·成品质检（面料还原最高优先）", "x": 3560, "y": -280, "w": 400, "h": 480, "promptFile": "QA_质检四图_v12.txt" },
    { "ref": "R", "type": "ai_chat", "title": "R·返修提示词编译器", "x": 3560, "y": 280, "w": 360, "h": 280, "promptFile": "R_返修编译_v12.txt" },
    { "ref": "RG", "type": "ai_image", "title": "RG·返修生图（单卡手动跑，2K）", "x": 3560, "y": 640, "w": 255, "h": 340, "data": { "size": "3:4", "resolution": "2K", "quality": "high" }, "content": " " },

    { "ref": "X1", "type": "ai_image", "title": "X1·质感四宫格", "x": 4060, "y": -280, "w": 255, "h": 340, "data": { "size": "1:1", "resolution": "1K", "quality": "high" }, "promptFile": "X1_质感四宫格_v12.txt" },
    { "ref": "X2", "type": "ai_image", "title": "X2·展示首屏（9:16）", "x": 4060, "y": 140, "w": 255, "h": 340, "data": { "size": "9:16", "resolution": "1K", "quality": "high" }, "promptFile": "X2_展示首屏_v12.txt" }
  ],
  "connections_note": "顺序即参考图槽位。GS1/GS2:槽1面料图(INF1,模式B无)。GS3:槽1样衣(GS1)/槽2面料图(INF1,模式B无)。G1-G4与RG:槽1定妆照(GS3)/槽2样衣(GS1)/槽3面料图(INF1,模式B无)。INF2只连F1；GS2只连A1/QA；文本最后连。",
  "connections": [
    ["INF1", "F1"], ["INF2", "F1"], ["REQ1", "F1"], ["REQ2", "F1"],
    ["F1", "D1"], ["REQ1", "D1"], ["REQ2", "D1"],
    ["F1", "CS"], ["D1", "CS"], ["REQ1", "CS"], ["REQ2", "CS"],
    ["CS", "PS1"], ["CS", "PS2"], ["CS", "PS3"],

    ["INF1", "GS1"], ["PS1", "GS1"],
    ["INF1", "GS2"], ["PS2", "GS2"],
    ["GS1", "GS3"], ["INF1", "GS3"], ["PS3", "GS3"],

    ["GS1", "A1"], ["GS2", "A1"], ["INF1", "A1"], ["REQ1", "A1"], ["REQ2", "A1"],
    ["GS3", "A2"], ["D1", "A2"], ["REQ1", "A2"],
    ["D1", "SP1"], ["REQ1", "SP1"], ["REQ2", "SP1"],

    ["GS3", "C"], ["GS1", "C"], ["INF1", "C"], ["F1", "C"], ["A1", "C"], ["A2", "C"], ["SP1", "C"], ["REQ1", "C"], ["REQ2", "C"],
    ["C", "P1"], ["C", "P2"], ["C", "P3"], ["C", "P4"],

    ["GS3", "G1"], ["GS1", "G1"], ["INF1", "G1"], ["P1", "G1"],
    ["GS3", "G2"], ["GS1", "G2"], ["INF1", "G2"], ["P2", "G2"],
    ["GS3", "G3"], ["GS1", "G3"], ["INF1", "G3"], ["P3", "G3"],
    ["GS3", "G4"], ["GS1", "G4"], ["INF1", "G4"], ["P4", "G4"],

    ["GS3", "QA"], ["GS1", "QA"], ["GS2", "QA"], ["INF1", "QA"],
    ["G1", "QA"], ["G2", "QA"], ["G3", "QA"], ["G4", "QA"], ["C", "QA"],

    ["QA", "R"], ["C", "R"],
    ["GS3", "RG"], ["GS1", "RG"], ["INF1", "RG"], ["R", "RG"],

    ["INF1", "X1"], ["GS1", "X1"], ["G3", "X1"],
    ["G4", "X2"], ["GS1", "X2"]
  ],
  "groups": [
    { "ref": "GRPS1", "title": "S①打样分析（先跑·锁卡=设计稿）", "color": "#7C3AED", "members": ["F1", "D1", "CS", "PS1", "PS2", "PS3"] },
    { "ref": "GRPS2", "title": "S②虚拟样衣（3张·人工核可后再往下）", "color": "#F59E0B", "members": ["GS1", "GS2", "GS3"] },
    { "ref": "GRP2", "title": "②分析与编译（跑完先检查锁卡）", "color": "#6366F1", "members": ["A1", "A2", "SP1", "C", "P1", "P2", "P3", "P4"] },
    { "ref": "GRP3", "title": "③四分镜大片（2K计费，跑前确认）", "color": "#10B981", "members": ["G1", "G2", "G3", "G4"] },
    { "ref": "GRP4", "title": "④质检（面料还原优先）", "color": "#EF4444", "members": ["QA"] },
    { "ref": "GRP5", "title": "⑤返修支线（按需）", "color": "#F97316", "members": ["R", "RG"] },
    { "ref": "GRP6", "title": "⑥展示组合", "color": "#3B82F6", "members": ["X1", "X2"] }
  ],
  "variants": {
    "b": {
      "project_title": "V12-奢牌面料成衣线-模式B类目文驱动-4分镜",
      "output_file": "V12奢牌面料成衣线4分镜_模式B.lxf",
      "removeCards": ["INF1", "INF2"],
      "promptFiles": { "DOC1": "DOC1_使用说明_v12b.txt" },
      "titles": {
        "DOC1": "①模式B使用说明（类目文驱动·先读我）",
        "GS1": "GS1·样衣套装白底正面（2K·纯文生图）",
        "GS2": "GS2·样衣套装白底背面（1K·纯文生图）"
      }
    }
  }
}
```

- [ ] **Step 2: Commit**

```powershell
git add "完全体/blueprints/workflow_spec_v12.json"
git commit -m "V12蓝图: workflow_spec_v12.json(31卡/81连/7组, variants.b删面料卡=29卡/67连)"
```

### Task 13: 构建+核验双模式 + 全线回归

- [ ] **Step 1: 构建并核验 V12 模式A**

```powershell
cd "E:\Projects\agent全自动生图\完全体\solutions"
py -X utf8 build_lxf.py --spec workflow_spec_v12.json
py -X utf8 verify_lxf.py --spec workflow_spec_v12.json
```
Expected: `OK 已生成 …… 卡片 31 | 连接 81 | 分组 7 | 媒体 2`；核验 `✅ 全量一致 …… 零漂移`。

- [ ] **Step 2: 构建并核验 V12 模式B**

```powershell
py -X utf8 build_lxf.py --spec workflow_spec_v12.json --variant b
py -X utf8 verify_lxf.py --spec workflow_spec_v12.json --variant b
```
Expected: `OK 已生成 …… 卡片 29 | 连接 67 | 分组 7 | 媒体 0`；核验 `✅ 全量一致`。若卡/连数不符：先数 spec 里 INF1/INF2 触及的连线（应为14条），排查 removeCards 逻辑。

- [ ] **Step 3: 三条旧线回归（共用 build_lxf 已改，铁律21）**

```powershell
py -X utf8 build_lxf.py;                                py -X utf8 verify_lxf.py
py -X utf8 build_lxf.py --variant half;                 py -X utf8 verify_lxf.py --variant half
py -X utf8 build_lxf.py --spec workflow_spec_v11.json;  py -X utf8 verify_lxf.py --spec workflow_spec_v11.json
```
Expected: 三次全部 `✅ 全量一致`。

- [ ] **Step 4: Commit（交付文件+产物）**

```powershell
git add -A
git commit -m "V12交付: 4分镜.lxf双模式构建通过, 蓝图零漂移, V9.2/V10/V11回归通过"
```

### Task 14: 回归防线登记（铁律17/21）

**Files:**
- Modify: `完全体/direction/回归防线.md`（产品线登记表）

- [ ] **Step 1: 读现有登记表格式，在产品线登记表追加 V12 行**

内容要点（按表格现有列适配）：产品线=V12奢牌面料成衣线（模式A/B）；spec=`workflow_spec_v12.json`（variants.b）；提示词=全部 `*_v12.txt` 独立（PS/P抽取器内联）；共用文件=`build_lxf.py`（本次新增 removeCards，已对 V9.2/V10/V11 回归通过）+ verify/apply 工具链；专属护栏=面料还原双分支（C§4-5 + QA维度2 + DOC检查点）、合规红线禁logo（D1 + C§6 + QA硬失败5）、样衣伪影拦截（A1字段7 + DOC核可清单）。

- [ ] **Step 2: Commit**

```powershell
git add "完全体/direction/回归防线.md"
git commit -m "V12登记: 产品线登记表新增V12行(共用build_lxf已回归,专属护栏三点落地)"
```

### Task 15: 发布画布（apply）+ 回读核验（铁律16第3/4步）

前提：公司机 LumaX Flow 运行中（`E:\LumaX Flow\data\agent\agent.json` 存在）。

- [ ] **Step 1: apply 模式A 新画布项目**

```powershell
cd "E:\Projects\agent全自动生图\完全体\solutions"
py -X utf8 apply_to_app.py --spec workflow_spec_v12.json
```
Expected: 输出新项目 id。记下 id。

- [ ] **Step 2: verify_canvas 回读核验**

```powershell
py -X utf8 verify_canvas.py --spec workflow_spec_v12.json --project <上一步的id>
```
Expected: 卡内容/连接槽位序/分组全量一致（apply 不写图，INF1/INF2 会缺图——属预期，提醒 Joe 手动放面料图）。

- [ ] **Step 3: apply + 回读 模式B 新画布项目**

```powershell
py -X utf8 apply_to_app.py --spec workflow_spec_v12.json --variant b
py -X utf8 verify_canvas.py --spec workflow_spec_v12.json --variant b --project <新id>
```
Expected: 同上，29卡且无输入图卡。

- [ ] **Step 4: 推送项目仓库**

```powershell
git push
```

### Task 16: 收工——记忆存档与双仓库同步

- [ ] **Step 1: 更新 `E:\AI-Memory\vault\20-项目记忆\电商作图\agent全自动生图\当前进度.md`**：V12 蓝图落地状态（两画布 id、下一步=Joe放面料图跑S①S②核可样衣、待实测假设7条待验）；踩坑记录如实新增本次实现中踩到的坑（没有就不加）。

- [ ] **Step 2: 双仓库提交推送 + 输出【记忆存档回执】**（格式见 INDEX.md）。

---

## Self-Review 记录（计划完成后已自查）

1. **Spec覆盖**：设计文档第1节输入协议→Task 3/12；第2节M矩阵→Task 4-8；第3节面料锁定→Task 4(F1)/9(C§4-5)/10(QA维度2)；第4节托管→Task 7；4.3分镜表→Task 7(SHOT_PLAN_4)/12(G卡)；判断5双模式单引擎→Task 6/9/10双分支+Task 1/12 variants.b；第6节X层→Task 11；第7节落盘→Task 12-15；铁律17登记→Task 14。无缺口。
2. **占位符扫描**：全部提示词/JSON/命令均为完整最终内容；无 TBD/TODO。
3. **类型一致性**：卡 ref（INF1/INF2/F1/D1/CS/PS1-3/GS1-3/A1/A2/SP1/C/P1-4/G1-4/QA/R/RG/X1/X2）在 spec、连线、提示词槽位声明、DOC 说明中全局一致；锁卡名 [FABRIC_DNA]/[DESIGN_DNA]/[GARMENT_DNA]/[MODEL_DNA]/[SCENE_DNA]/[SHOT_PLAN_4] 上下游一致；removeCards 触及连线=14条（81-67）与 Task 13 Step 2 预期一致。

