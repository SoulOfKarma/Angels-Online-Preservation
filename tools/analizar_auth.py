"""
Identifica que parte del AUTH depende de la CONTRASENA.

EXPERIMENTO A CORRER:
  1. Borrar logs/auth_muestras/
  2. Entrar 3 veces seguidas con la clave  AAAAAA
  3. Entrar 3 veces seguidas con la clave  BBBBBB
  4. python tools/analizar_auth.py 3

Los bytes estables dentro de cada grupo y distintos entre grupos son
candidatos, no una prueba de que sean el hash de la contrasena.
No activar la validacion automaticamente con estos resultados.
"""
import sys, pathlib

n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
ms = sorted(pathlib.Path('logs/auth_muestras').glob('*.bin'))
d = [m.read_bytes() for m in ms if m.stat().st_size == 73]
if len(d) < 2 * n:
    print(f"hacen falta {2*n} muestras de 73 B; hay {len(d)}")
    print(__doc__)
    sys.exit(1)

A, B = d[:n], d[n:2 * n]
print(f"grupo A: {n} muestras   grupo B: {n} muestras\n")
cand = []
for o in range(73):
    iguales_A = len({x[o] for x in A}) == 1
    iguales_B = len({x[o] for x in B}) == 1
    distinto = A[0][o] != B[0][o]
    if iguales_A and iguales_B and distinto:
        cand.append(o)

print("bytes candidatos (estables dentro de cada grupo,")
print("distintos entre grupos):")
if not cand:
    print("   ninguno -- las dos claves dieron el mismo resultado, o la")
    print("   codificacion mezcla un nonce en cada byte")
else:
    tramos, ini, prev = [], cand[0], cand[0]
    for o in cand[1:]:
        if o != prev + 1:
            tramos.append((ini, prev)); ini = o
        prev = o
    tramos.append((ini, prev))
    for a, b in tramos:
        print(f"   +{a}..{b}  ({b-a+1} bytes)")
    print("\nNo activar VALIDAR_PASSWORD ni elegir solo el primer tramo.")
    print("Un byte igual entre A y B puede pertenecer al mismo campo;")
    print("un byte distinto tambien puede depender de la sesion.")
    print("Conserva estas muestras y agrega otros tres ingresos con AAAAAA,")
    print("reiniciando el cliente. Luego ejecuta de nuevo este analizador.")
    if len(d) >= 3 * n:
        C = d[2 * n:3 * n]
        confirmados = [o for o in cand
                       if all(x[o] == A[0][o] for x in C)]
        print(f"Candidatos que vuelven al valor de A: {len(confirmados)}/{len(cand)}")
        print("Esto sigue sin confirmar el algoritmo ni el campo completo.")
