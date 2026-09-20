import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')
cur = con.cursor()

# Check magic 601
cols = [c[1] for c in cur.execute('pragma table_info(magic)').fetchall()]
row = cur.execute('select * from magic where id="601"').fetchone()
if row:
    d = dict(zip(cols, row))
    print("Magic 601 data:")
    for k, v in d.items():
        if v is not None and v != '' and v != '0':
            print(f"  {k}: {repr(v)}")
else:
    print("Magic 601 not found!")

# Check other sword skills in magic
rows_sw = cur.execute('select id, name, "消耗MP", "特效編號", "desc" from magic where name like "%Slicing%" or name like "%Sword%" limit 10').fetchall()
print("\nSword magics:")
for r in rows_sw:
    print(r)

# Check skills for Swordsman (skill IDs: 9, 12, 13, 15, 16, 33)
print("\nSkills table:")
for sid in ['9', '12', '13', '15', '16', '33']:
    row_sk = cur.execute('select * from skill where id=?', (sid,)).fetchone()
    cols_sk = [c[1] for c in cur.execute('pragma table_info(skill)').fetchall()]
    if row_sk:
        d_sk = dict(zip(cols_sk, row_sk))
        print(f"Skill {sid} ({d_sk.get('name')}): type={d_sk.get('type')}, desc={d_sk.get('desc')[:40] if d_sk.get('desc') else ''}")

