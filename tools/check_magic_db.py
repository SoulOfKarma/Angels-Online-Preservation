import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('f:/Ao Proyect/AO 2/corpus/content.db')
c = conn.cursor()

c.execute("PRAGMA table_info(magic)")
cols = [col[1] for col in c.fetchall()]

c.execute("SELECT * FROM magic WHERE id IN ('601', '602', '603', '701', '702', '703', '801', '802', '803')")
for row in c.fetchall():
    d = dict(zip(cols, row))
    print(f"ID {d.get('id')}: {d.get('name')} | effect={d.get('特效編號')} | cast_time={d.get('施法時間')} | cd={d.get('後置時間')} | dur={d.get('持續時間')} | mp={d.get('消耗MP')} | sp={d.get('消耗SP')} | act={d.get('動作編號')}")

conn.close()

