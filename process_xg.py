"""
process_xg.py - xG por zonas con tasas reales del propio dataset
Calcula xG de cada jugador usando tasas de conversion observadas por zona+cuerpo.
"""
import pandas as pd
from pathlib import Path

DATA = Path("data")
df = pd.read_csv(DATA / "player_events_stats.csv")

# 1) CALCULAR TASAS REALES POR ZONA (goles/tiros del dataset completo)
zonas = {
    "area_pequena": ("tiros_area_pequena", "goles_area_pequena"),
    "area_grande":  ("tiros_area_grande",  "goles_area_grande"),
    "fuera_area":   ("tiros_fuera_area",   "goles_fuera_area"),
}
print("=== TASAS DE CONVERSION REALES (xG por zona) ===")
tasas = {}
for zona, (tcol, gcol) in zonas.items():
    t = df[tcol].sum(); g = df[gcol].sum()
    tasa = g / t if t > 0 else 0
    tasas[zona] = tasa
    print(f"  {zona}: {int(g)} goles / {int(t)} tiros = {tasa:.4f} xG/tiro")

# penalti: tasa estandar reconocida
TASA_PENALTI = 0.79
print(f"  penalti: {TASA_PENALTI} (estandar)")

# 2) xG POR JUGADOR (suma de tiros x tasa de su zona)
df["xg"] = (
    df["tiros_area_pequena"] * tasas["area_pequena"]
    + df["tiros_area_grande"]  * tasas["area_grande"]
    + df["tiros_fuera_area"]   * tasas["fuera_area"]
    + df["penales_tirados"]    * TASA_PENALTI
).round(2)

# xg sobre/bajo rendimiento (goles reales - xg)
df["g_menos_xg"] = (df["goles"] - df["xg"]).round(2)

df.to_csv(DATA / "player_events_stats.csv", index=False)
print(f"\nGUARDADO. Columna 'xg' anadida a {len(df)} jugadores.")

# 3) TOP overperformers (mas goles que su xG = finalizadores letales)
print("\n=== TOP 10 FINALIZADORES (goles por encima de xG) ===")
top = df[df["tiros"] >= 20].nlargest(10, "g_menos_xg")[["nombre","goles","xg","g_menos_xg"]]
print(top.to_string(index=False))