"""Reparaciones conservadoras del marcado de color de textos IGG.

El cliente consume UN caracter de color tras /c$: en /c$25 el 2 es el
color y el 5 es texto (cantidad de Pink Diamonds). No borrar ese 5.
"""
import re

COLOR_CON_ESPACIO = re.compile(r'/c\$[ \t]+(?=[0-9])')


def normalizar_colores(texto: str) -> str:
    texto = COLOR_CON_ESPACIO.sub('/c$', texto)
    # Omisiones concretas de IGG. MSG.XML oficial TW confirma /c$2 en
    # 5394/5395 (Level 50/51) y 89911/89927 (fishing).
    texto = texto.replace('/c$ Level ', '/c$2 Level ')
    return texto.replace('/c$ fishing/c*', '/c$2 fishing/c*')
