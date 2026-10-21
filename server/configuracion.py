"""
Configuracion del Servidor y Multiplicadores de Eventos.

Aqui puedes cambiar los multiplicadores de experiencia, habilidades y drops
sin tener que modificar la logica del servidor.
"""
import datetime

# Reconstruccion de servicios Lyceum: las probabilidades no vienen en los
# XML publicos. Son parametros de compatibilidad, NO tasas oficiales IGG.
ASTRO_PESOS_NORMAL = (1, 1, 1)  # intensidades I / II / III
ASTRO_PESOS_CRISTAL = (1, 1, 4)  # el tooltip promete mayor chance de III
STRAW_DROP_PROBABILIDAD = 0.50  # provisional; usuario recuerda caida alta


# =====================================================================
# MULTIPLICADORES BASE (Valores por defecto del servidor)
# =====================================================================
# 1.0 = Experiencia normal oficial
# 2.0 = Doble experiencia, etc.
TASA_EXP_BASE = 2000.0           # Multiplicador de EXP de personaje
TASA_SKILL_EXP_BASE = 1000.0     # Multiplicador de EXP de habilidades (stamina/skills)
TASA_DROP_BASE = 0.001          # Multiplicador de probabilidad de drop de items
TASA_ORO_BASE = 7.5           # Multiplicador de oro obtenido de monstruos

# =====================================================================
# CONFIGURACION DE CASAS, BAILES Y PET ROOM
# =====================================================================
MULTIPLICADOR_EXP_PET = 1.0           # Multiplicador de EXP para mascotas en el patio de crianza (477..486)
EXP_BASE_PET_ROOM_TICK = 15           # EXP base por tick (~5 segundos) para mascotas entrenando en casa
COOLDOWN_BAILE_SEGUNDOS = 60          # Cooldown en segundos para volver a usar un Ball Ticket (por defecto 60s para testing rapido)
TIEMPO_PREPARACION_BAILE_SEGUNDOS = 180 # Tiempo de preparacion antes del baile (oficial 180s = 3 minutos)
DURACION_BAILE_SEGUNDOS = 60           # Duracion del baile una vez iniciado (por defecto 60s)

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
    tasa base + evento semanal + buffs o tarjetas de doble EXP activas + bonos de casa/maid."""
    m = TASA_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_EXP
    if buffs:
        if buffs.get('doble_exp'):
            m *= 2.0
        if buffs.get('triple_exp'):
            m *= 3.0
        # House cleanliness belongs to the house magic index. Eilian's
        # 2292..2295 affect equipment enhancement, never character EXP.
        import lyceum_services
        m *= 1 + lyceum_services.bono(buffs, 'exp_extra_pct') / 100
    return m


def multiplicador_skill_exp(buffs: dict = None) -> float:
    """Calcula el multiplicador total de EXP de habilidades teniendo en cuenta:
    tasa base + evento semanal + cartas de skill exp activas."""
    m = TASA_SKILL_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_SKILL
    if buffs and buffs.get('doble_skill_exp'):
        m *= 2.0
    if buffs:
        import lyceum_services
        m *= 1 + lyceum_services.bono(buffs, 'skill_exp_extra_pct') / 100
    return m


def multiplicador_drop() -> float:
    """Calcula el multiplicador total de drops."""
    m = TASA_DROP_BASE
    if es_fin_de_semana():
        m *= 1.5
    return m


# =====================================================================
# MODO PRUEBAS / DEBUG
# =====================================================================
# Si es True, cualquier compra en tiendas NPC cuesta solo 1 de oro por item.
# Si es False, se cobra el precio normal de item.xml.
FLAG_ORO = False
COMPRAS_1_DE_ORO = FLAG_ORO

# Creditos de rango con los que entra el personaje.
#
# La ficha muestra "Credit:" y, encima, el rango: son los nombres 1700 a 1719
# de string.xml, de "Growing Power" a "God's Mouthpiece". En la captura del
# 28/09/2026 el personaje tenia 4.610.115 creditos y la ficha decia "Order
# founder", que es el 1716, o sea el rango 17 contando "Growing Power" como
# el 1.
#
# ENCONTRADOS (05/10/2026): los cortes entre un rango y otro SI estan en el
# cliente. Son la columna 功勳 de setting/level.xml, y hay exactamente 20
# valores, uno por rango:
#
#   1:0        2:1000      3:2400      4:4500      5:8500
#   6:17000    7:33000     8:60000     9:103000   10:170000
#  11:280000  12:457000   13:730000   14:1130000  15:1690000
#  16:2745000 17:4250000  18:6380000  19:9370000  20:15750000
#
# Cuadran con lo medido: 4.610.115 cae entre el 17 y el 18, y la ficha de la
# captura decia "Order founder", que es el 17. La tabla la lee
# combate.creditos_de_rango() del propio xml, no esta copiada a mano, y al
# subir de rango el servidor pone los creditos que le tocan.
#
# En cero no se manda nada y la ficha queda como estaba.
CREDITOS_INICIALES = 0

# Objetos con los que empieza el almacen del banco, como {ranura: item_id}.
#
# Esto esta aqui por una duda que no se ha podido resolver leyendo: el paquete
# del almacen (0x004E) lleva el mismo cuerpo que el inventario -- un LE32 con
# el numero de entradas y detras las entradas, de 86 bytes las corrientes y
# 119 las equipables -- y en la captura del servidor real llevaba OCHO. El
# nuestro sale con cero porque el personaje no tiene nada guardado, y la
# ventana no se abre.
#
# Las dos funciones del cliente que crean la ventana del banco solo lo hacen
# cuando el primer LE32 dividido por 1000 vale 2 o 3, pero en la captura vale
# 8, que da 0 por esa cuenta. Asi que la ventana no la abre ese numero: o la
# abre el cliente solo al elegir la opcion del dialogo, y entonces necesita
# tener contenido que mostrar, o hay un camino que todavia no se ha visto.
#
# Con esto se prueba lo primero. Si con un objeto dentro el almacen abre, era
# la lista vacia; en cuanto se sepa, esto sobra y se quita.
ALMACEN_INICIAL = {}

# =====================================================================
# REGENERACION DE HP Y MP
# =====================================================================
# Antes era plana: +6 MP y +12 HP por tick, vinieran de donde vinieran. A
# nivel bajo se nota, pero a nivel 300, con 121.440 de MP, llenar la barra a
# seis por segundo son CINCO HORAS Y MEDIA.
#
# Ahora es un porcentaje del maximo, y el porcentaje sube con el nivel. Se
# mantiene el minimo plano de antes para que a nivel 1 no regenere menos de
# lo que regeneraba.
#
# De pie hay que llevar dos segundos quieto y fuera de combate; sentado
# (tecla Insert) el tick es cada segundo y el porcentaje mucho mayor.
#
#   por tick = maximo * (base + nivel * por_nivel) / 100
#
# A nivel 1 de pie sale 0,5% cada dos segundos y sentado 2% cada segundo. A
# nivel 300, 2% y 8%: la barra de MP se llena en unos 70 segundos de pie y en
# unos 13 sentado.
REGEN_PIE_BASE = 0.5          # % del maximo, a nivel 1
REGEN_PIE_POR_NIVEL = 0.005   # % que se suma por cada nivel
REGEN_SENTADO_BASE = 2.0
REGEN_SENTADO_POR_NIVEL = 0.02
REGEN_MINIMO_HP_PIE = 6       # los valores planos de antes, como suelo
REGEN_MINIMO_MP_PIE = 6
REGEN_MINIMO_HP_SENTADO = 12
# Sentado el MP tenia el mismo suelo que de pie, seis, asi que a nivel 1
# sentarse no servia de nada para el mana. Se sube a doce, como el HP.
REGEN_MINIMO_MP_SENTADO = 12


def regenera(maximo: int, nivel: int, sentado: bool, es_hp: bool) -> int:
    """Cuanto se recupera en un tick."""
    if sentado:
        pct = REGEN_SENTADO_BASE + nivel * REGEN_SENTADO_POR_NIVEL
        piso = REGEN_MINIMO_HP_SENTADO if es_hp else REGEN_MINIMO_MP_SENTADO
    else:
        pct = REGEN_PIE_BASE + nivel * REGEN_PIE_POR_NIVEL
        piso = REGEN_MINIMO_HP_PIE if es_hp else REGEN_MINIMO_MP_PIE
    return max(piso, int(round(maximo * pct / 100.0)))

# =====================================================================
# MEJORAS DE EQUIPO (morteros, martillos, piensos y gemas)
# =====================================================================
# Si es True, TODA mejora sale bien: morteros, piensos de montura y de
# mascota, y martillos de perforar. Es para probar sin gastar cien objetos.
#
# Con ella en False se usa mejoras.probabilidad(), que NO esta medida: no hay
# ninguna captura de un fallo. Es una curva inventada que empieza segura y
# baja hasta el 20% en la ultima mejora. En cuanto haya numeros de verdad se
# cambia ahi.
MEJORAS_SIEMPRE_EXITO = True

# Si es True, el martillo verde da el MAXIMO de todos los stats que puede dar
# en vez de sortear cada uno dentro de su rango. El cuadro del juego enseña
# esos rangos: "Attack 0 (0-210), Rigor 3 (0-54), Movement Speed 37 (0-40)".
MARTILLO_VERDE_TODOS_LOS_STATS = True

# El rango con el que entra el personaje: 1 es "Growing Power" y 20 "God's
# Mouthpiece". Viaja en el byte 93 del 0x0002, pegado a los creditos, y NO se
# calcula de ellos: los cortes entre un rango y otro no estan en los datos del
# cliente, asi que lo decide el servidor.
RANGO_INICIAL = 1

# ID del consumible custom (Rank Promotion Medal, basado en el sprite 8921 de
# la General's Medal 5873, agregado al final de item9.xml del update26) que
# sube +1 rango automaticamente por cada uso (hasta el rango maximo 20).
ITEM_MEDALLA_RANGO = 83266


# =====================================================================
# MUNICION DE ARQUEROS (Arcos + Flechas / Hondas + Bolitas)
# =====================================================================
# Si es True (como en el servidor Global actual), las flechas y bolitas/balas
# equipadas en la mano izquierda (ranura 4) son infinitas y no se gastan al atacar.
# Si es False, cada disparo con arco u honda consume 1 unidad de municion.
FLECHAS_INFINITAS = True


# =====================================================================
# MODO ESTACIONAL DEL CLIENTE Y ACTUALIZADOR LOCAL (START.EXE)
# =====================================================================
# Controla el tema visual del Angel Lyceum (map041.mpc) que el servidor
# sincroniza automaticamente con el cliente local:
#   - 'normal'    : Angel Lyceum clasico sin nieve (update25/map041.mpc)
#   - 'navidad'   : Angel Lyceum nevado de Navidad (update26/map041.mpc)
#   - 'halloween' : Angel Lyceum de Halloween (041halloween.mpc)
#   - 'sakura'    : Angel Lyceum de cerezos en flor (041sakura.mpc)
#   - 'verano'    : Angel Lyceum de festival de verano / Matsuri (041matsuri.mpc)
MODO_ESTACION = 'normal'

# Ruta local del cliente para sincronizar el modo estacional y el launcher START.EXE
# Donde esta el cliente. Es solo una PISTA: si no esta ahi, el servidor lo
# busca solo (cliente_local.ruta_cliente). Da por bueno cualquier directorio
# que tenga Angel.exe y al menos un .pak, y mira en este orden: la variable
# de entorno AO_CLIENTE, esta ruta, los sitios habituales de instalacion, y
# los vecinos del propio repo -- que es lo normal, el cliente al lado del
# servidor. Dejarla vacia tambien vale.
RUTA_CLIENTE = r'C:\AO\Angels Online'
PUERTO_UPDATE_FTP = 2121
# 8080 cae dentro de un intervalo TCP reservado por Windows en algunas
# instalaciones (por ejemplo 8067-8166), lo que produce WinError 10013 aun
# cuando ningun proceso lo este escuchando. 8280 conserva el mismo largo en
# la URL parcheada de START.EXE y queda fuera de ese intervalo.
PUERTO_UPDATE_HTTP = 8280


# A que nivel sale una mascota nueva. Los stats los saca de petattrib con su
# clase y este nivel, y estan comprobados: una Battlemaid (item 20012) a
# nivel 246 da 12100 de ataque, 15755 de defensa, 3137 de ataque magico,
# 4431 de defensa magica, 1947 de rigor, 1127 de agilidad, 18775 de vida y
# 9074 de mana, que es exactamente la ficha que enseñaba el juego.
#
# A nivel 1 la mascota es inservible, asi que aqui se pone a que nivel
# quieres que aparezcan las que da el comando /item.
MASCOTA_NIVEL_INICIAL = 1

# Deja en blanco la pantalla del logo que sale al abrir el cliente.
# Solo toca UPDATE21.PAK, y siempre deja un .bak antes.
QUITAR_LOGO_ARRANQUE = True

# Quita las once reglas de exclusion entre ramas de habilidad (Life<->Wraith,
# Chaos<->Earth, Meditate<->Enhance, Grapple<->Snipe y el trio
# Mantle/Garment/Vestment). Son el atributo 互斥N de setting/eng/skill.xml;
# el servidor nunca las comprobo, quien se negaba era el selector del
# cliente. Se deja un skill.xml suelto en el cliente, y para deshacerlo
# basta borrarlo.
RAMAS_SIN_EXCLUSION = True
