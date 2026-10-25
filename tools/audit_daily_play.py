"""Summarize native Daily generator/event links without starting the server."""
import collections,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
import daily_events as d,eventos
for stage in sorted(d.STAGES):
    data=d.datos(stage);rows=data['spawns'];native=eventos.del_stage(stage)
    print(stage,'active',sum(not r.get('apagado') for r in rows),'inactive',sum(bool(r.get('apagado')) for r in rows),
          'zones',dict(collections.Counter(r.get('zona') for r in rows)),'bosses',len(data['bosses']))
    if stage in (178,374,375,376):
        print('TYPES',[(k,rs[0]['nombre']) for k,rs in __import__('itertools').groupby(sorted(rows,key=lambda r:r['npc_type']),lambda r:r['npc_type']) for rs in [list(rs)]])
        print('MONSTER_LINKS',native.get('monstruos'))
        print('EVENT_SAMPLE',list(eventos.disparadores(stage))[:3])
