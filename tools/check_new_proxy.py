import json
from inspect_skills_detail import inspect_lines

with open('logs/proxy/mundo_181238_268869_orden.jsonl', 'r', encoding='utf-8') as f:
    total = sum(1 for _ in f)

print(f"Total lines in mundo_181238_268869_orden.jsonl: {total}")
inspect_lines('logs/proxy/mundo_181238_268869_orden.jsonl', max(0, total - 120), total)

