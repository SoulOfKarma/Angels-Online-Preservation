"""Read installed IGG PAKs and preview house assets, without changing the client."""
import argparse
import json
import mmap
import re
import struct
import zlib
from pathlib import Path

def render_frame(raw, start=0, palette_offset=None):
    """Small dependency-free TLHS diagnostic decoder; no client file edits."""
    width, height = struct.unpack_from('<II', raw, start + 20)
    if not (0 < width <= 1024 and 0 < height <= 1024):
        return None
    pal = palette_offset if palette_offset is not None else struct.unpack_from('<I', raw, start + 64)[0]
    colors = []
    for i in range(256):
        word = struct.unpack_from('<H', raw, pal + 2 * i)[0]
        colors.append(bytes((((word >> 11) & 31) * 255 // 31,
                             ((word >> 5) & 63) * 255 // 63,
                             (word & 31) * 255 // 31, 255 if i else 0)))
    pixels = bytearray(width * height * 4)
    for y in range(height):
        row = start + struct.unpack_from('<I', raw, start + 80 + y * 4)[0]
        while row + 8 <= len(raw):
            count, x, source = struct.unpack_from('<hhI', raw, row)
            row += 8
            if count < 0 or x < 0:
                break
            for j in range(count):
                if 0 <= x + j < width and start + source + j < len(raw):
                    off = (y * width + x + j) * 4
                    pixels[off:off + 4] = colors[raw[start + source + j]]
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    scanlines = b''.join(b'\0' + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def index_pak(data):
    pos = max(data.rfind(b'OD\x05\x06'), data.rfind(b'PK\x05\x06'))
    if pos < 0:
        raise ValueError('PAK directory not found')
    rec = bytearray(data[pos:pos + 22])
    if rec[:2] == b'OD':
        for i in range(4, 22):
            rec[i] ^= (i * 3 + 0xa5) & 255
    comp, _, _, size, offset, _ = struct.unpack_from('<IHHIIH', rec, 4)
    if comp:
        blob = bytearray(data[offset + 4:offset + 4 + comp])
        blob[0] ^= 0x7a
        directory = zlib.decompress(blob)
    else:
        directory = data[offset:offset + size]
    pos = 0
    while pos + 46 <= len(directory) and directory[pos:pos + 4] in (b'OD\x01\x02', b'PK\x01\x02'):
        method = struct.unpack_from('<H', directory, pos + 10)[0]
        packed = struct.unpack_from('<I', directory, pos + 20)[0]
        n, extra, comment = struct.unpack_from('<HHH', directory, pos + 28)
        offset = struct.unpack_from('<I', directory, pos + 42)[0]
        name = directory[pos + 46:pos + 46 + n].decode('latin1').replace('\\', '/').lower()
        yield name, (offset, packed, method)
        pos += 46 + n + extra + comment


def audit(client, dest):
    dest.mkdir(parents=True, exist_ok=True)
    pak_paths = [p for p in client.iterdir() if re.fullmatch(r'(data1|update\d*)\.pak', p.name, re.I)]
    pak_paths.sort(key=lambda p: -1 if p.stem.lower() == 'data1' else int(p.stem[6:] or 0))
    assets, matches = {}, {}
    for path in pak_paths:
        with path.open('rb') as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for name, (offset, size, method) in index_pak(data):
                maid = any(s in name for s in ('n262/', 'n1062/', '40262', '41062'))
                stage = name.startswith('shape/stage/24/') and any(s in name for s in ('24-009-', '24-021-', '24-101-')) and name.endswith('u0.shp')
                if maid or stage or name == 'setting/npc.obd':
                    raw = data[offset:offset + size]
                    raw = zlib.decompress(raw, -15) if method == 8 else raw
                    assets[name] = raw
                    matches[name] = path.name
    (dest / 'sources.json').write_text(json.dumps(matches, indent=2), encoding='utf-8')
    previews = []
    for name, raw in assets.items():
        if raw[:4] == b'EWSP':
            pal = struct.unpack_from('<I', raw, 16)[0]
            starts = [m.start() for m in re.finditer(b'TLHS', raw)]
            for i, start in enumerate(starts[:5]):
                frame = render_frame(raw, start, pal)
                if frame:
                    previews.append((name + '-' + str(i), frame))
        elif raw[:4] == b'TLHS':
            img = render_frame(raw)
            if img:
                previews.append((name, img))
    for name, png in previews:
        (dest / (name.split('/')[-1] + '.png')).write_bytes(png)
    print('Maid assets:', {k: v for k, v in matches.items() if 'npc/' in k})
    npc = assets.get('setting/npc.obd', b'').decode('big5', errors='replace')
    match = re.search(r'\[OBJECT\][^[]*Sequence\s*=\s*40262\b[^[]*', npc)
    print('Installed Maid definition:', match.group(0)[:1200] if match else 'not defined')
    print('Previews:', dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', type=Path, default=Path('C:/AO/Angels Online'))
    parser.add_argument('--dest', type=Path, default=Path(__file__).resolve().parents[1] / 'scratch/house_visual_audit')
    args = parser.parse_args()
    audit(args.client, args.dest)
