"""Buscar en Angel_unpacked.c los opcodes que abren ventanas (Repair, Warehouse, Skill, etc.)."""
import re

with open(r'f:\Ao Proyect\AO\Angel_unpacked.c', 'r', encoding='latin-1') as f:
    for line_num, line in enumerate(f, 1):
        if any(k in line for k in ['WND_', 'OpenRepair', 'OpenShop', 'OpenBank', 'OpenWarehouse', 'OpenSkill']):
            print(f"{line_num}: {line.strip()[:100]}")
        if '0x0034' in line or '0x002B' in line or '0x002A' in line:
            if 'case' in line or 'if' in line:
                print(f"OP {line_num}: {line.strip()[:100]}")

