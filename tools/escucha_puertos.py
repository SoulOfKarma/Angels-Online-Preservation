"""
Detecta a que puerto intenta conectar el cliente.

El binario muestra que la IP y el puerto del mundo NO salen del redirect, sino
de una entrada de 372 bytes de la lista de servidores (sub_51A370 los lee de
+64 y +80). Antes de seguir leyendo codigo, conviene MEDIR: este script abre
un rango de puertos y avisa cual toca el cliente.

Uso (con el servidor principal APAGADO):
    python tools/escucha_puertos.py
"""
import asyncio
import logging

log = logging.getLogger('escucha')
RANGO = list(range(16760, 16790)) + [6768, 30000, 30001, 24131, 24132]


async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    abiertos = []

    def hacer(p):
        async def h(r, w):
            addr = w.get_extra_info('peername')
            log.info('>>> EL CLIENTE CONECTO AL PUERTO %s (desde %s)', p, addr)
            try:
                d = await asyncio.wait_for(r.read(4096), 3)
                if d:
                    log.info('    y mando %s bytes: %s', len(d), d[:48].hex(' '))
                else:
                    log.info('    y cerro sin mandar nada')
            except asyncio.TimeoutError:
                log.info('    y se quedo esperando respuesta (no mando nada)')
            w.close()
        return h

    for p in RANGO:
        try:
            s = await asyncio.start_server(hacer(p), '127.0.0.1', p)
            abiertos.append(s)
        except OSError:
            pass
    log.info('escuchando en %s puertos: %s ...', len(abiertos), RANGO[:6])
    log.info('arranca el cliente, logueate y apreta Enter game')
    log.info('')
    await asyncio.gather(*(s.serve_forever() for s in abiertos))


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
