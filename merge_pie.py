import os, shutil
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(ROOT, "data", "players_scouting.csv")
RAW = os.path.join(ROOT, "data", "player_events_stats.csv")

pool = pd.read_csv(POOL)
raw = pd.read_csv(RAW)

idcol = next((x for x in ["player_id", "nombre"] if x in pool.columns and x in raw.columns), None)
if idcol is None:
    raise SystemExit("[ERROR] sin columna comun player_id/nombre")

def k(s): return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
raw["_k"] = k(raw[idcol]); pool["_k"] = k(pool[idcol])

izq = pd.to_numeric(raw.get("tiros_pie_izq"), errors="coerce").fillna(0)
der = pd.to_numeric(raw.get("tiros_pie_der"), errors="coerce").fillna(0)
agg = raw.assign(_i=izq, _d=der).groupby("_k")[["_i", "_d"]].sum().reset_index()
agg["_t"] = agg["_i"] + agg["_d"]

def pie_de(r):
    if r["_t"] < 4:
        return "s/d"
    rd = r["_d"] / r["_t"]
    return "Derecho" if rd >= 0.65 else ("Izquierdo" if rd <= 0.35 else "Ambidiestro")

agg["pie"] = agg.apply(pie_de, axis=1)
pool["pie"] = pool["_k"].map(dict(zip(agg["_k"], agg["pie"]))).fillna("s/d")
pool = pool.drop(columns=["_k"])

bak = POOL + ".bak_pie"
if not os.path.exists(bak): shutil.copy(POOL, bak)
pool.to_csv(POOL, index=False)

print("[OK] columna 'pie' anadida")
print(pool["pie"].value_counts().to_string())
print("Con dato:", int((pool["pie"] != "s/d").sum()), "/", len(pool))