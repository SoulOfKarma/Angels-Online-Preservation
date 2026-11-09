# -*- coding: utf-8 -*-
"""
Traduce los 172 nombres de conjuntos (sets de equipo) en extracted_paks/update26/setting/eng/itemset.xml
que contenían caracteres en chino tradicional, eliminando las cadenas '??-??' del cliente.
"""
import pathlib
import re
import shutil
import datetime

XML_PATH = pathlib.Path('extracted_paks/update26/setting/eng/itemset.xml')

PREFIXES = [
    ('聖耀', 'Holy Radiance-'),
    ('聖熾', 'Holy Blazing-'),
    ('煌耀', 'Brilliant-'),
    ('幻祈', 'Phantom Prayer-'),
    ('幻玟-', 'Phantom Wave-'),
    ('愛月-', 'Ailun-'),
    ('煌威', 'Radiant Might-'),
    ('幻熾', 'Phantom Flame-'),
    ('煌璃-', 'Radiant Glass-'),
    ('幻羽-', 'Phantom Feather-'),
    ('煌日-', 'Radiant Sun-'),
    ('幻瑛-', 'Phantom Blossom-'),
    ('幻珀-', 'Phantom Amber-'),
    ('幻玥-', 'Lunarad-'),
    ('咒雷-', 'Thunder Curse-'),
    ('靈鎖-', 'Spirit Lock-'),
    ('邪疫-', 'Plague-'),
    ('黎明-', 'Dawn-'),
]

EXACT_MAP = {
    '黎明-天道': "Dawn-Heaven's Path (P)",
    '黎明-不朽龍魂': "Dawn-Amaranton (P)",
    '邪疫-旋風（P）': "Plague-Whirlwind (P)",
    '邪疫-黑曜（P）': "Plague-Obsidian (P)",
    '邪疫-絲蒂（P）': "Plague-Sidi (P)",
    '靈鎖-潛伏者（P）': "Spirit Lock-Lurker (P)",
    '靈鎖-鬥牛（P）': "Spirit Lock-Corrida (P)",
    '靈鎖-神秘月光（P）': "Spirit Lock-Mystic Moonlight (P)",
    '潛伏者(P)': "Lurker (P)",
    '鬥牛(P)': "Corrida (P)",
    '神秘月光(P)': "Mystic Moonlight (P)",
    '優皮(P)': "Quality (P)",
    '鎖鏈強化(P)': "Intensified Chain (P)",
    '奇幻(P)': "Fantastic (P)",
    '咒雷-優皮': "Thunder Curse-Quality",
    '咒雷-鎖鏈強化': "Thunder Curse-Intensified Chain",
    '咒雷-奇幻': "Thunder Curse-Fantastic",
    '幻玥-星空準影': "Lunarad-Skyblue",
    '幻玥-鷹眼突刺': "Lunarad-Hawkeye",
    '幻玥-茂森巫袍': "Lunarad-Greenwich",
    '幻玥-探險': "Lunarad-Adventure",
    '幻玥-強護': "Lunarad-Intensified",
    '幻玥-魔法師': "Lunarad-Magian",
    '幻珀-柔毛絨兔': "Phantom-Tenderbun",
    '幻珀-狂鐘鋼甲': "Phantom-Bellsteel",
    '幻珀-釘時闇法': "Phantom-Temporan",
    '狩人': "Hunter",
    '天滅': "Heaven's End",
    '神鳥': "Divine Bird",
    '魔蜂': "Magic Bee",
    '風雷虎威': "Storm Tiger",
    '王族聖者': "Royal Crusader",
    '聖者意志': "Devout Will",
    '神隼': "Falcon",
    '孤高': "Aloof",
    '誓浄': "Vow of Purity",
    '鉄壁生産シリーズ': "Iron Wall Crafting Series",
    '三日月': "Crescent Moon",
    '紅炎飛官': "Red Flame Pilot",
    '黑色猛虎': "Black Tiger",
    '聚神探靈': "Soul Gatherer",
    '奧拉的祝福': "Aura's Blessing",
    '倒數50號前告知程式': "Test-Notice50",
}

SUFFIXES = [
    ('不朽龍魂', 'Amaranton'),
    ('天道', "Heaven's Path"),
    ('雷霆夜行', 'Thunder Walk'),
    ('鋼鱗重力', 'Steel Scale'),
    ('邪神靈咒', 'Affliction'),
    ('紅焰玄鋼', 'Pyre-Chalcum'),
    ('天罡北斗', 'Starry-Plough'),
    ('天晶幻靈', 'Crystal Phantom'),
    ('魔熔血焰', 'Bloodflame'),
    ('創世星雲', 'Genesis Nebula'),
    ('神隼好戰', 'Falcon Militant'),
    ('橫行獨步', 'Rampant Strider'),
    ('真誠淨織', 'Sincere Weave'),
    ('泰格憑依', 'Tiger Possessed'),
    ('司芬克絲', 'Sphinx'),
    ('輝耀祭祀', 'Radiant Priest'),
    ('不羈豪傑', 'Wild Hero'),
    ('逐風機走', 'Wind Chaser'),
    ('馭風者', 'Wind Rider'),
    ('榮耀海盜', 'Ahoy Pirate'),
    ('傲吼戰狼', 'Warhowl Wolf'),
    ('焰燼術師', 'Nitelite Mage'),
    ('巡空者', 'Skywatch'),
    ('蒼穹翱翔', 'Flier'),
    ('幽藍爵士', 'Ducbleu'),
    ('極地狼蹤', 'Winterwolf'),
    ('新月天鉤', 'Crescentia'),
    ('深淵呢喃', 'Abysmal'),
    ('乾漠迴盪者', 'Desert Wanderer'),
    ('龍爪戰神', 'Dragonclaw War God'),
    ('天玄太極', 'Octogram'),
    ('森語捍衛', 'Forest Warden'),
    ('神翼審判', 'Divine Wing Judgment'),
    ('聖裁光言', 'Holy Sanction'),
    ('戰地英豪', 'Battlefield Hero'),
    ('風暴機能', 'Storm Mechanism'),
    ('競風塵羽', 'Dustfeather'),
    ('幻霓炫羽', 'Neon Feather'),
    ('聖潔戰華', 'Holy Blossom'),
    ('星月睿智', 'Star-Moon Wisdom'),
    ('飛鷹勇者', 'Eagle Brave'),
    ('無懼戰魂', 'Fearless Soul'),
    ('熾言術士', 'Flaming Words Mage'),
    ('聖德天祈', 'Holy Virtue Prayer'),
    ('雪翼衛士', 'Snow Wing Guard'),
    ('秘法賢者', 'Arcane Sage'),
    ('神羽遊俠', 'Divine Feather Ranger'),
    ('鐵面聖衛', 'Iron Face Holy Guard'),
    ('異世咒法', 'Otherworld Incantation'),
    ('祕林尋者', 'Secret Forest Seeker'),
    ('鐵甲王蟲', 'Iron Beetle'),
    ('皎潔天恩', 'Radiant Grace'),
    ('祕蹤探險', 'Venturer'),
    ('御風無痕', 'Gale'),
    ('淨法先知', 'High Prophet'),
    ('清雪淨語', 'Alabaster'),
    ('狂怒猛擊', 'Exotron'),
    ('薰紫蒼神', 'Soulent'),
    ('風行夜靈', 'Night Goblin'),
    ('晶心動魄', 'Stirring Crystal'),
    ('魔力蜂暴', 'Crazy Bee'),
    ('迅獵部落', 'Falconer'),
    ('冰封', 'Boreal'),
    ('楓紅', 'Burgundier'),
    ('古龍骨', 'Drake Bone'),
    ('魔刃', 'Hellion Blade'),
    ('熾焰', 'Flaming'),
    ('風雷虎威', 'Storm Tiger'),
    ('王族聖者', 'Royal Crusader'),
    ('聖者意志', 'Devout Will'),
]

def translate_name(name: str) -> str:
    if name in EXACT_MAP:
        return EXACT_MAP[name]
    
    for pfx_zh, pfx_en in PREFIXES:
        if name.startswith(pfx_zh):
            rest = name[len(pfx_zh):]
            if rest in EXACT_MAP:
                return f"{pfx_en}{EXACT_MAP[rest]}"
            for sfx_zh, sfx_en in SUFFIXES:
                if rest == sfx_zh:
                    return f"{pfx_en}{sfx_en}"
            return f"{pfx_en}{rest}"
            
    for sfx_zh, sfx_en in SUFFIXES:
        if name == sfx_zh:
            return sfx_en
            
    return name

def procesar():
    if not XML_PATH.exists():
        raise FileNotFoundError(f"No existe {XML_PATH}")

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak_path = XML_PATH.with_suffix(f'.xml.bak_{stamp}')
    shutil.copy2(XML_PATH, bak_path)
    print(f"Backup creado en: {bak_path}")

    content = XML_PATH.read_text(encoding='utf-8')
    ch = re.compile(r'[\u4e00-\u9fff]')
    pattern = re.compile(r'名稱="([^"]+)"')

    reemplazos = 0
    def repl(m):
        nonlocal reemplazos
        val = m.group(1)
        if ch.search(val):
            nuevo = translate_name(val)
            reemplazos += 1
            return f'名稱="{nuevo}"'
        return m.group(0)

    nuevo_content = pattern.sub(repl, content)

    # Validar que ningún valor de 名稱 tenga CJK
    restantes = [m.group(1) for m in pattern.finditer(nuevo_content) if ch.search(m.group(1))]
    if restantes:
        raise ValueError(f"Aún quedan valores con CJK en 名稱: {restantes}")

    XML_PATH.write_text(nuevo_content, encoding='utf-8')
    print(f"Éxito: {reemplazos} nombres de conjuntos traducidos en {XML_PATH}")

if __name__ == '__main__':
    procesar()
