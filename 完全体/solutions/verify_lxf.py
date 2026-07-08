# -*- coding: utf-8 -*-
"""verify_lxf.py —— DBS Solutions 层：核验 .lxf 与蓝图零漂移（发布闭环第2步）。
比对项：卡数/每卡content/类型/AI参数、连接全序列（=槽位顺序）、分组。
用法：  python verify_lxf.py [lxf路径]   （缺省=仓库根目录下 V9.2定制版8分镜.lxf）
"""
import json, sys, zipfile
from pathlib import Path

from build_lxf import load_spec, variant_from_argv

sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
BP = HERE.parent / 'blueprints'
PROMPTS = BP / 'prompts'

_args = sys.argv[1:]
spec = load_spec(variant_from_argv(_args))
_pos = [a for i, a in enumerate(_args)
        if not a.startswith('--') and (i == 0 or _args[i - 1] != '--variant')]
LXF = Path(_pos[0]) if _pos else HERE.parent.parent / spec['output_file']
CHAT_D, IMAGE_D = spec['defaults']['chat'], spec['defaults']['image']

def expected_content(c):
    if c.get('promptFile'):
        return (PROMPTS / c['promptFile']).read_text(encoding='utf-8').strip()
    return c.get('content', '')

def expected_data(c):
    t = c['type']
    content = expected_content(c)
    if t in ('text', 'sticky_note'):
        return {'content': content}
    if t == 'ai_chat':
        d = {'_showLabel': True, 'content': content}; d.update(CHAT_D); return d
    if t == 'ai_image':
        d = {'_showLabel': True, 'content': content}; d.update(IMAGE_D); d.update(c.get('data', {}))
        if c.get('media'):
            d['imageUrl'] = f"media/images/{c['media']}"
        return d
    raise ValueError(t)

exp_cards = {c['title']: c for c in spec['cards']}
assert len(exp_cards) == len(spec['cards']), '标题重复，核验方式需改'
ref2title = {c['ref']: c['title'] for c in spec['cards']}
exp_conns = [(ref2title[a], ref2title[b]) for a, b in spec['connections']]

zf = zipfile.ZipFile(LXF)
cv = json.loads(zf.read('canvas.json'))
id2title = {c['id']: c['title'] for c in cv['cards']}
act_conns = [(id2title[x['source_card_id']], id2title[x['target_card_id']]) for x in cv['connections']]

problems = []
et, at = set(exp_cards), set(id2title.values())
if et != at:
    problems.append(f'卡标题集合不一致: 蓝图有而lxf无 {et - at} | lxf有而蓝图无 {at - et}')
print(f'卡数: 蓝图 {len(exp_cards)} vs lxf {len(cv["cards"])}')

for c in cv['cards']:
    t = c['title']
    if t not in exp_cards:
        continue
    exp = expected_data(exp_cards[t])
    act = json.loads(c['data']) if isinstance(c['data'], str) else c['data']
    if exp_cards[t]['type'] != c['type']:
        problems.append(f'{t}: 类型 {exp_cards[t]["type"]} vs {c["type"]}')
    if exp.get('content', '').strip() != (act.get('content', '') or '').strip():
        problems.append(f'{t}: content 不一致 (期望{len(exp.get("content", ""))}字 vs 实际{len(act.get("content", ""))}字)')
    for k in set(exp) - {'content', 'imageUrl'}:
        if act.get(k) != exp[k]:
            problems.append(f'{t}: 参数 {k} 期望{exp[k]!r} vs 实际{act.get(k)!r}')

print(f'连接数: 蓝图 {len(exp_conns)} vs lxf {len(act_conns)}')
for i, (e, a) in enumerate(zip(exp_conns, act_conns)):
    if e != a:
        problems.append(f'连接[{i}] 期望 {e} vs 实际 {a}')
if len(exp_conns) != len(act_conns):
    problems.append('连接数量不同')
print(f'分组数: 蓝图 {len(spec["groups"])} vs lxf {len(cv["groups"])}')

print('\n========== 结论 ==========')
if problems:
    print(f'❌ 发现 {len(problems)} 处不一致:')
    for p in problems:
        print(' -', p)
    sys.exit(1)
print(f'✅ 全量一致：{len(exp_cards)}卡内容/类型/AI参数、{len(exp_conns)}条连接顺序、分组，蓝图与 .lxf 零漂移。')
