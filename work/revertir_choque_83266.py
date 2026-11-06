"""Devuelve al texto de Taiwan los campos que la memoria tradujo como
"Rank Promotion Medal" por el choque de ID 83266 (medalla propia aqui,
huevo de mascota en TW). Solo toca filas que no son la 83266."""
import pathlib, re, sys
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'tools'))
import tw_migracion as tw
tw_set = tw.indice_tw(True)
base = tw.IGG / 'update26' / 'setting'
total = 0
for f in base.rglob('*.xml'):
    raw = f.read_bytes()
    txt = raw.decode('utf-8-sig', errors='replace')
    if 'Rank Promotion Medal' not in txt:
        continue
    r = tw.normal(str(f.relative_to(tw.IGG / 'update26')))
    if r not in tw_set:
        continue
    ft = tw.filas(tw.leer(tw_set[r][1]))
    n = 0

    def fila(m):
        global n
        i = m.group(2)
        if i in tw.IDS_PROPIOS or i not in ft:
            return m.group(0)
        orig = tw.atributos(ft[i])
        def attr(a):
            k, v = a.group(1), a.group(2)
            if v == 'Rank Promotion Medal' and k in orig:
                return ' %s="%s"' % (k, orig[k])
            return a.group(0)
        return re.sub(r' ([^\s=<>"]+)="([^"]*)"', attr, m.group(0))
    nuevo = tw.RE_FILA.sub(fila, txt)
    if nuevo != txt:
        f.write_bytes(b'\xef\xbb\xbf' * raw.startswith(b'\xef\xbb\xbf') + nuevo.encode('utf-8'))
        total += 1
        print('revertido en', f.name)
print('archivos:', total)
