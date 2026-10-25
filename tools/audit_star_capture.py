"""Inspect only recent world Star packets, never login/authentication traffic."""
import pathlib,json,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
for path in sorted((ROOT/'logs/sesiones').glob('*_16769_*_orden.jsonl'),key=lambda p:p.stat().st_mtime)[-3:]:
    hits=[]
    for line in path.read_text('utf8',errors='replace').splitlines():
        try:r=json.loads(line)
        except ValueError:continue
        op=str(r.get('opcode','')).lower()
        if op not in ('0x017f','017f','383'):continue
        raw=bytes.fromhex(r.get('hex',''))
        hits.append((r.get('dir'),len(raw),raw[:18].hex(),raw.hex()))
    for direction,length,head,raw in hits[-2:]:print(path.name,direction,length,head,raw)
