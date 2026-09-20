"""
Configuracion del Servidor y Multiplicadores de Eventos.

Aqui puedes cambiar los multiplicadores de experiencia, habilidades y drops
sin tener que modificar la logica del servidor.
"""
import datetime


# =====================================================================
# MULTIPLICADORES BASE (Valores por defecto del servidor)
# =====================================================================
# 1.0 = Experiencia normal oficial
# 2.0 = Doble experiencia, etc.
TASA_EXP_BASE = 5.0           # Multiplicador de EXP de personaje
TASA_SKILL_EXP_BASE = 5.0     # Multiplicador de EXP de habilidades (stamina/skills)
TASA_DROP_BASE = 9.5          # Multiplicador de probabilidad de drop de items
TASA_ORO_BASE = 7.5           # Multiplicador de oro obtenido de monstruos

# =====================================================================
# CONFIGURACION DE EVENTOS DE FIN DE SEMANA / SEMANALES
# =====================================================================
# Si es True, activa automaticamente el bono de fin de semana (Viernes, Sabado y Domingo)
EVENTO_FIN_DE_SEMANA_AUTOMATICO = True

# Si prefieres forzar el evento encendido o apagado manualmente:
# Pon True para forzar evento activo siempre, o False para desactivarlo.
EVENTO_DOBLE_EXP_FORZADO = False

# Multiplicador adicional que se aplica durante el evento
BONUS_EVENTO_EXP = 2.0
BONUS_EVENTO_SKILL = 2.0


def es_fin_de_semana() -> bool:
    """Devuelve True si hoy es viernes (4), sabado (5) o domingo (6)."""
    if EVENTO_DOBLE_EXP_FORZADO:
        return True
    if not EVENTO_FIN_DE_SEMANA_AUTOMATICO:
        return False
    dia = datetime.datetime.now().weekday()
    return dia in (4, 5, 6)


def multiplicador_exp(buffs: dict = None) -> float:
    """Calcula el multiplicador total de EXP de personaje teniendo en cuenta:
    tasa base + evento semanal + buffs o tarjetas de doble EXP activas."""
    m = TASA_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_EXP
    if buffs and buffs.get('doble_exp'):
        m *= 2.0
    if buffs and buffs.get('triple_exp'):
        m *= 3.0
    return m


def multiplicador_skill_exp(buffs: dict = None) -> float:
    """Calcula el multiplicador total de EXP de habilidades teniendo en cuenta:
    tasa base + evento semanal + cartas de skill exp activas."""
    m = TASA_SKILL_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_SKILL
    if buffs and buffs.get('doble_skill_exp'):
        m *= 2.0
    return m


def multiplicador_drop() -> float:
    """Calcula el multiplicador total de drops."""
    m = TASA_DROP_BASE
    if es_fin_de_semana():
        m *= 1.5
    return m

