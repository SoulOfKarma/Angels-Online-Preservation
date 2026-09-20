import re, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')

msg_path = pathlib.Path(r'f:\Ao Proyect\AO\data\game_xml\msg.xml')
if msg_path.exists():
    text = msg_path.read_text(encoding='latin-1')
    print(f"msg.xml size: {len(text)} bytes")

    for phrase in ["your tutor in the angels lyceum", "tutor in the angel", "Director Wolay", "Cupid", "Checkpoint", "Save point"]:
        matches = [m.start() for m in re.finditer(re.escape(phrase), text, re.IGNORECASE)]
        print(f"\nMatches for '{phrase}': {len(matches)}")
        for idx in matches[:3]:
            snippet = text[max(0, idx-100):min(len(text), idx+200)]
            print("---")
            print(snippet)
