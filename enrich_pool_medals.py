"""
enrich_pool_medals.py
Une medallas + xG real al pool de scouting por player_id.
"""
import pandas as pd
from pathlib import Path

DATA = Path("data")
pool = pd.read_csv(DATA / "players_scouting.csv")
med  = pd.read_csv(DATA / "player_medals.csv")
ev   = pd.read_csv(DATA / "player_events_stats.csv")

print(f"Pool: {len(pool)} | Medallas: {len(med)} | Eventos: {len(ev)}")

# idempotente: quitar columnas de medallas/xg de una corrida anterior antes de re-crearlas
_drop = ["xg_90", "medallas"]
for _m in ["tirador_lejano", "cabeceador", "recuperador_puro", "presionador_alto",
           "definidor", "creador", "desequilibrante", "muro", "motor"]:
    _drop += [_m + "_medalla", _m + "_pts"]
pool = pool.drop(columns=[c for c in _drop if c in pool.columns])

# --- 1) xG real por 90 desde eventos ---
ev_xg = ev[["player_id", "xg"]].copy()
pool = pool.merge(ev_xg, on="player_id", how="left")
pool["xg"] = pool["xg"].fillna(0)
# xg_90 = xg total / minutos * 90
pool["xg_90"] = ((pool["xg"] / pool["minutos"].clip(lower=1)) * 90).round(2)
pool.loc[pool["xg_90"] > 1.6, "xg_90"] = 0
pool.drop(columns=["xg"], inplace=True)

# --- 2) Medallas (solo columnas relevantes) ---
med_cols = ["player_id",
            "tirador_lejano_medalla","tirador_lejano_pts",
            "cabeceador_medalla","cabeceador_pts",
            "recuperador_puro_medalla","recuperador_puro_pts",
            "presionador_alto_medalla","presionador_alto_pts",
            "definidor_medalla","definidor_pts",
            "creador_medalla","creador_pts",
            "desequilibrante_medalla","desequilibrante_pts",
            "muro_medalla","muro_pts",
            "motor_medalla","motor_pts"]
pool = pool.merge(med[med_cols], on="player_id", how="left")

# rellenar sin-medalla
for c in ["tirador_lejano_medalla","cabeceador_medalla","recuperador_puro_medalla","presionador_alto_medalla","definidor_medalla","creador_medalla","desequilibrante_medalla","muro_medalla","motor_medalla"]:
    pool[c] = pool[c].fillna("")
for c in ["tirador_lejano_pts","cabeceador_pts","recuperador_puro_pts","presionador_alto_pts","definidor_pts","creador_pts","desequilibrante_pts","muro_pts","motor_pts"]:
    pool[c] = pool[c].fillna(0)

# --- 3) columna resumen de medallas (emojis) para mostrar facil ---
EMOJI = {"ORO":"🥇","PLATA":"🥈","BRONCE":"🥉"}
ABREV = {"tirador_lejano_medalla":"TL","cabeceador_medalla":"CAB",
         "recuperador_puro_medalla":"REC","presionador_alto_medalla":"PRE",
         "definidor_medalla":"FIN","creador_medalla":"CRE",
         "desequilibrante_medalla":"REG","muro_medalla":"MUR",
         "motor_medalla":"MOT"}
def resumen(row):
    out = []
    for col, ab in ABREV.items():
        m = row[col]
        if m in EMOJI:
            out.append(f"{EMOJI[m]}{ab}")
    return " ".join(out)
pool["medallas"] = pool.apply(resumen, axis=1)

pool.to_csv(DATA / "players_scouting.csv", index=False)

# --- reporte ---
con_xg = (pool["xg_90"] > 0).sum()
con_med = (pool["medallas"] != "").sum()
print(f"\nGUARDADO.")
print(f"  Con xG_90 > 0: {con_xg}/{len(pool)}")
print(f"  Con al menos 1 medalla: {con_med}/{len(pool)}")
print(f"\nTOP 5 xG_90 del pool:")
print(pool.nlargest(5,"xg_90")[["nombre","club","xg_90","medallas"]].to_string(index=False))
print(f"\nEjemplos con medallas:")
print(pool[pool["medallas"]!=""].head(8)[["nombre","posicion","medallas"]].to_string(index=False))