import os, shutil
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SCOUT = os.path.join(ROOT, "data", "players_scouting.csv")
POOL = os.path.join(ROOT, "data", "raw", "tm_pool_progress.csv")

sc = pd.read_csv(SCOUT)
pool = pd.read_csv(POOL)

# base estimada (idempotente: si ya existe edad_estimada, esa es la base)
base_edad = sc["edad_estimada"] if "edad_estimada" in sc.columns else sc["edad"]

# clave de cruce normalizada a texto (evita lios int/float y el ".0")
def norm_pid(s):
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
sc["_pid"] = norm_pid(sc["player_id"])
pool["_pid"] = norm_pid(pool["player_id"])

# lo util del pool, sin duplicados de player_id
p = (pool[["_pid", "edad_tm", "match_score", "needs_review"]]
     .dropna(subset=["_pid"]).drop_duplicates("_pid", keep="first")
     .rename(columns={"match_score": "edad_match_score",
                      "needs_review": "edad_needs_review"}))

# limpiamos columnas previas para que sea re-ejecutable
for c in ["edad_tm", "edad_origen", "edad_estimada", "edad_match_score", "edad_needs_review"]:
    if c in sc.columns:
        sc = sc.drop(columns=c)

sc["edad_estimada"] = base_edad
sc = sc.merge(p, on="_pid", how="left")

edad_tm_num = pd.to_numeric(sc["edad_tm"], errors="coerce")
base_num = pd.to_numeric(sc["edad_estimada"], errors="coerce")
sc["edad"] = edad_tm_num.fillna(base_num).round().astype("Int64")
sc["edad_origen"] = np.where(edad_tm_num.notna(), "TM", "estimada")

sc = sc.drop(columns="_pid")

bak = SCOUT + ".bak"
if not os.path.exists(bak):
    shutil.copy(SCOUT, bak)
sc.to_csv(SCOUT, index=False)

# resumen
print("Jugadores en scouting:", len(sc))
print("Con edad real de TM :", int((sc["edad_origen"] == "TM").sum()))
print("Con edad estimada   :", int((sc["edad_origen"] == "estimada").sum()))
print("Edad media ANTES:", round(base_num.mean(), 2),
      "  DESPUES:", round(pd.to_numeric(sc["edad"], errors="coerce").mean(), 2))
print()
print("Ejemplos donde cambio la edad:")
cambios = sc[edad_tm_num.notna() & (edad_tm_num.round() != base_num.round())]
print(cambios[["nombre", "edad_estimada", "edad_tm", "edad", "edad_origen"]].head(12).to_string(index=False))