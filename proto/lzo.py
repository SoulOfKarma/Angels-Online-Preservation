"""
Descompresion LZO1X.

Identificada leyendo sub_827330 en el binario del cliente: la firma
(`primer byte > 17`, los umbrales 0x10/0x20/0x40, los acumuladores +=255)
es la de lzo1x_decompress.

Los frames con el bit 7 de flags (FLAG_CMP) vienen comprimidos asi. Nuestro
servidor NO necesita comprimir -- el flag le dice al cliente si debe
descomprimir o no -- pero si necesita descomprimir para poder LEER las
capturas.
"""


def descomprimir(src: bytes, salida_max: int = 1 << 20) -> bytes:
    dst = bytearray()
    ip = 0
    n = len(src)

    def lit(t):
        nonlocal ip
        dst.extend(src[ip:ip + t])
        ip += t

    t = src[ip]
    if t > 17:
        t -= 17
        ip += 1
        if t < 4:
            # cae directo a match_next
            lit(t)
            t = src[ip]; ip += 1
            estado = 'match'
        else:
            lit(t)
            estado = 'primera_corrida'
    else:
        estado = 'inicio'

    while True:
        if estado == 'inicio':
            if ip >= n: break
            t = src[ip]; ip += 1
            if t >= 16:
                estado = 'match'; continue
            if t == 0:
                while src[ip] == 0:
                    t += 255; ip += 1
                t += 15 + src[ip]; ip += 1
            lit(t + 3)
            estado = 'primera_corrida'
            continue

        if estado == 'primera_corrida':
            if ip >= n: break
            t = src[ip]; ip += 1
            if t >= 16:
                estado = 'match'; continue
            pos = len(dst) - (1 + 0x0800) - (t >> 2) - (src[ip] << 2)
            ip += 1
            for _ in range(3):
                dst.append(dst[pos]); pos += 1
            estado = 'fin_match'
            continue

        if estado == 'match':
            while True:
                if t >= 64:
                    pos = len(dst) - 1 - ((t >> 2) & 7) - (src[ip] << 3)
                    ip += 1
                    largo = (t >> 5) - 1
                elif t >= 32:
                    t &= 31
                    if t == 0:
                        while src[ip] == 0:
                            t += 255; ip += 1
                        t += 31 + src[ip]; ip += 1
                    pos = len(dst) - 1 - (int.from_bytes(src[ip:ip+2], 'little') >> 2)
                    ip += 2
                    largo = t
                elif t >= 16:
                    pos = len(dst) - ((t & 8) << 11)
                    t &= 7
                    if t == 0:
                        while src[ip] == 0:
                            t += 255; ip += 1
                        t += 7 + src[ip]; ip += 1
                    pos -= int.from_bytes(src[ip:ip+2], 'little') >> 2
                    ip += 2
                    if pos == len(dst):
                        return bytes(dst)           # fin
                    pos -= 0x4000
                    largo = t
                else:
                    pos = len(dst) - 1 - (t >> 2) - (src[ip] << 2)
                    ip += 1
                    dst.append(dst[pos]); dst.append(dst[pos + 1])
                    break

                if pos < 0 or len(dst) > salida_max:
                    raise ValueError(f"LZO: referencia invalida (pos={pos})")
                for _ in range(largo + 2):
                    dst.append(dst[pos]); pos += 1
                break

            # fin_match
            t = src[ip - 2] & 3
            if t == 0:
                estado = 'inicio'
                continue
            lit(t)
            if ip >= n: break
            t = src[ip]; ip += 1
            estado = 'match'
            continue

        if estado == 'fin_match':
            t = src[ip - 2] & 3
            if t == 0:
                estado = 'inicio'; continue
            lit(t)
            if ip >= n: break
            t = src[ip]; ip += 1
            estado = 'match'
            continue

    return bytes(dst)
