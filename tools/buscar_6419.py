import glob

for p in sorted(glob.glob('extracted_paks/**/*.xml', recursive=True)):
    if 'itemicon' in p:
        continue
    try:
        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
            for idx, line in enumerate(f, 1):
                if '2786' in line and any(w in line for w in ['egg', 'gashapon', '扭蛋', 'random', 'box', 'casket', '編號="2786"', 'id="2786"']):
                    print(f'{p}:{idx}: {line.strip()[:160]}')
    except Exception as e:
        pass
