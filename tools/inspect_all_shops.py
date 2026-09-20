"""Buscar las tiendas de C Plan Seller, Ironsmith y Scroll Seller en corpus/content.db."""
import sqlite3

con = sqlite3.connect('corpus/content.db')

print("--- Todas las tiendas de content.db ---")
cols = [c[1] for c in con.execute('pragma table_info(shop)').fetchall()]
for r in con.execute('select id, name from shop limit 60').fetchall():
    print(f"Shop ID={r[0]:3s} Name={r[1]}")

