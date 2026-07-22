# -*- coding: utf-8 -*-
"""verify_canvas.py —— DBS Solutions 层：回读画布项目并核验与蓝图一致（发布闭环第4步）。
比对项：每卡content、每个目标卡的入边槽位顺序、分组数。
用户编辑过的需求卡（REQ1/REQ2）出现 content 差异属预期，会单独标注不计为失败。
用法：  python verify_canvas.py <projectId>
"""
import json, sys, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
BP = HERE.parent / 'blueprints'
PROMPTS = BP / 'prompts'
def _find_agent_json():
    """按 AGENTS.md 发现顺序找 agent.json（家机 D:/公司机 E:/APPDATA 回退），取第一个存在的。"""
    import os
    cands = [Path(r'D:\LumaXFlow\data\agent\agent.json'),
             Path(r'E:\LumaX Flow\data\agent\agent.json'),
             Path(os.environ.get('APPDATA', '')) / 'com.ai-canvas.desktop' / 'agent' / 'agent.json']
    for c in cands:
        if c.exists():
            return c
    raise FileNotFoundError(
        "找不到 agent.json（LumaX Flow 没开或没开自动化接口？）。已查:\n  " + "\n  ".join(map(str, cands)))


AGENT_JSON = _find_agent_json()
USER_EDITABLE = {'REQ1', 'REQ2'}   # 用户卡：差异只提示不判失败

from build_lxf import load_spec, variant_from_argv, spec_from_argv, OPT_WITH_VALUE

_args = sys.argv[1:]
PID = [a for i, a in enumerate(_args)
       if not a.startswith('--') and (i == 0 or _args[i - 1] not in OPT_WITH_VALUE)][0]
cfg = json.loads(AGENT_JSON.read_text(encoding='utf-8'))
base = f"http://127.0.0.1:{cfg['port']}/agent/v1"

def api(path):
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {cfg['token']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

spec = load_spec(variant_from_argv(_args), spec_from_argv(_args))

def expected_content(c):
    if c.get('promptFile'):
        return (PROMPTS / c['promptFile']).read_text(encoding='utf-8').strip()
    return c.get('content', '')

g = api(f'/projects/{PID}/graph')
cards, conns = g['cards'], g['connections']
print(f'画布: 卡 {len(cards)} | 连 {len(conns)} | 组 {len(g.get("groups", []))}  '
      f'(蓝图: {len(spec["cards"])}/{len(spec["connections"])}/{len(spec["groups"])}；画布多出的无连线游离卡不计)')

ref2card = {c.get('ref'): c for c in cards if c.get('ref')}
problems, notes = [], []
for sc in spec['cards']:
    ac = ref2card.get(sc['ref'])
    if not ac:
        problems.append(f'缺卡: {sc["ref"]} {sc["title"]}')
        continue
    d = ac.get('data') or {}
    if isinstance(d, str):
        d = json.loads(d) if d else {}
    actual = (d.get('content') or '').strip()
    if expected_content(sc).strip() != actual:
        msg = f'{sc["ref"]} {sc["title"]}: content 与蓝图不同 (蓝图{len(expected_content(sc))}字/画布{len(actual)}字)'
        (notes if sc['ref'] in USER_EDITABLE else problems).append(msg)

act = [(x['from'], x['to']) for x in conns]
exp = [(a, b) for a, b in spec['connections']]
if act != exp:
    from collections import defaultdict
    def per_target(pairs):
        d = defaultdict(list)
        for a, b in pairs:
            d[b].append(a)
        return d
    pa, pe = per_target(act), per_target(exp)
    bad = [t for t in pe if pa.get(t) != pe[t]]
    for t in bad:
        problems.append(f'{t} 入边槽位顺序不一致:\n    期望 {pe[t]}\n    实际 {pa.get(t)}')
    if not bad:
        print('（连接全序列排列不同，但每个目标卡的入边槽位顺序全部一致——槽位安全）')

print('\n========== 结论 ==========')
for n in notes:
    print('ℹ️ 用户编辑（预期差异）:', n)
if problems:
    print(f'❌ 发现 {len(problems)} 处不一致:')
    for p in problems:
        print(' -', p)
    sys.exit(1)
print('✅ 画布与蓝图一致：系统卡内容、槽位顺序全部正确。')
