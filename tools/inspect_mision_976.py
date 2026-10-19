import json

d = json.load(open('server/plantillas/misiones_completas.json', encoding='utf-8'))
m976 = d['misiones'].get('976')
if m976:
    print("Mision 976:", m976.get('nombre'))
    for idx, p in enumerate(m976.get('pasos', [])):
        print(f"Paso {idx+1}: tipo={p.get('tipo')} | npc={p.get('npc')} | obj={p.get('objetivos')} | texto={p.get('texto')[:60]}")
    print("Premios:", m976.get('premios'))

