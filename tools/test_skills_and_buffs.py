import os
import sys
import struct
import time

sys.path.insert(0, os.path.abspath('server'))
import combate as cb
import inventario as iv

def test_skill_classification():
    # 601 Slicing Hit I (Swordsman attack)
    s601 = cb.datos_magia(601)
    assert s601['es_ataque'] is True, "601 must be attack"
    assert s601['es_cura'] is False, "601 must not be heal"
    assert s601['es_buff'] is False, "601 must not be buff"

    # 602 Swiftness Song I (Swordsman buff)
    s602 = cb.datos_magia(602)
    assert s602['es_ataque'] is False, "602 must not be attack"
    assert s602['es_cura'] is False, "602 must not be heal"
    assert s602['es_buff'] is True, "602 must be buff"

    # 603 Injury Cure I (Swordsman regen buff)
    s603 = cb.datos_magia(603)
    assert s603['es_ataque'] is False, "603 must not be attack"
    assert s603['es_cura'] is False, "603 must not be direct heal"
    assert s603['es_buff'] is True, "603 must be buff"

    # 701 Basic Beating I (Warrior Axe attack)
    s701 = cb.datos_magia(701)
    assert s701['es_ataque'] is True, "701 must be attack"
    assert s701['es_cura'] is False, "701 must not be heal"
    assert s701['es_buff'] is False, "701 must not be buff"

    # 702 Ferocious Song I (Warrior Axe buff: +5 crit)
    s702 = cb.datos_magia(702)
    assert s702['es_ataque'] is False, "702 must not be attack"
    assert s702['es_cura'] is False, "702 must not be heal"
    assert s702['es_buff'] is True, "702 must be buff"
    assert s702['crit_rate'] == 5, f"702 crit_rate must be 5, got {s702['crit_rate']}"

    # 703 Fighting Shield I (Warrior Axe buff: 5% mitigation)
    s703 = cb.datos_magia(703)
    assert s703['es_ataque'] is False, "703 must not be attack"
    assert s703['es_cura'] is False, "703 must not be heal"
    assert s703['es_buff'] is True, "703 must be buff"
    assert s703['phys_mit'] == 5, f"703 phys_mit must be 5, got {s703['phys_mit']}"

    # 2 Cure Spell I (Priest real heal)
    s2 = cb.datos_magia(2)
    assert s2['es_cura'] is True, "2 must be heal"
    print("test_skill_classification passed!")

def test_visual_packets():
    pkgs = cb.efecto_magia_self(1001, 141, 702, cast_time=100)
    assert len(pkgs) == 2, "efecto_magia_self must return 2 packets (phase 0x00 and 0x80)"
    p0, p1 = pkgs[0], pkgs[1]
    assert p0[:2] == b'\x11\x00', "p0 opcode must be 0x0011"
    assert p0[2] == 141, "p0 ef must be 141"
    assert p0[3] == 0x00, "p0 phase must be 0x00"
    cast_t = struct.unpack_from('<H', p0, 20)[0]  # offset 18 in body = 20 in packet
    assert cast_t == 100, f"cast_time must be 100, got {cast_t}"
    assert p0[22] == 2, "type must be 2"

    assert p1[3] == 0x80, "p1 phase must be 0x80"
    cast_t1 = struct.unpack_from('<H', p1, 20)[0]
    assert cast_t1 == 0, f"p1 cast_time must be 0, got {cast_t1}"
    assert p1[22] == 2, "type must be 2"

    # GCD packet
    gcd = cb.gcd_paquete()
    assert len(gcd) == 38, f"GCD packet len must be 38, got {len(gcd)}"
    assert gcd[:2] == struct.pack('<H', 0x0149), "GCD opcode must be 0x0149"
    assert struct.unpack_from('<I', gcd, 10)[0] == 500, "GCD duration must be 500ms"
    print("test_visual_packets passed!")

def test_stats_with_buffs():
    # Base stats
    st_base = iv.stats({})
    dfs_base = struct.unpack_from('<I', st_base, 36 + 2)[0]
    c_base, c_eff_base = struct.unpack_from('<HH', st_base, 64 + 2)
    assert c_eff_base == 6, f"Base crit_eff should be 6, got {c_eff_base}"

    # Buff Ferocious Song I (+5 crit)
    buffs = {702: {'fin': time.time() + 300, 'crit': 5}}
    st_buff = iv.stats({}, buffs=buffs)
    dfs_buff = struct.unpack_from('<I', st_buff, 36 + 2)[0]
    c_b, c_eff_buff = struct.unpack_from('<HH', st_buff, 64 + 2)
    assert dfs_buff == dfs_base, f"Dfs must NOT change with Ferocious Song ({dfs_buff} vs {dfs_base})"
    assert c_eff_buff == 11, f"crit_eff must be 11 (6+5), got {c_eff_buff}"

    # Buff Fighting Shield I (5% damage reduction)
    buffs_shield = {703: {'fin': time.time() + 300, 'mit': 5}}
    st_shield = iv.stats({}, buffs=buffs_shield)
    dfs_shield = struct.unpack_from('<I', st_shield, 36 + 2)[0]
    assert dfs_shield == dfs_base, f"Dfs must NOT change with Fighting Shield ({dfs_shield} vs {dfs_base})"

    # Damage mitigation test
    raw_damage = 100
    mit_pct = buffs_shield[703]['mit']
    mitigated_damage = max(1, int(round(raw_damage * (1.0 - mit_pct / 100.0))))
    assert mitigated_damage == 95, f"100 damage with 5% mitigation must be 95, got {mitigated_damage}"
    print("test_stats_with_buffs passed!")

if __name__ == '__main__':
    test_skill_classification()
    test_visual_packets()
    test_stats_with_buffs()
    print("\nALL SKILL & BUFF TESTS PASSED SUCCESSFULLY!")

