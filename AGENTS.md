# CLAUDE.md —— agent全自动生图

## 记忆（每次必做）
- 本项目记忆：`E:\AI-Memory\vault\20-项目记忆\电商作图\agent全自动生图\`
- 开工先读三份记忆：项目地图.md、当前进度.md、踩坑记录.md
- 收工按三问（长期有用/会复用/能验证）主动更新记忆，并输出【记忆存档回执】
- 完整规则见 `E:\AI-Memory\vault\INDEX.md`

## 项目要点
- LumaX Flow 平台上的商用级服装一致性生图工作流（V9.0完全体：6图输入→3分析Agent→总控8分镜→生图→QA→返修→详情页）
- 唯一真源是 `完全体\blueprints\`（结构+提示词）；改动后用 `完全体\solutions\build_lxf.py` 重新产 .lxf、`apply_to_app.py` 直搭画布
- 硬禁区：连线顺序=参考图槽位顺序，不得乱动；run 计费，批量运行前必须 Joe 确认
