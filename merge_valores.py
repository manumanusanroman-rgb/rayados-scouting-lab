import os, shutil
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SCOUT = os.path.join(ROOT, "data", "players_scouting.csv")
POOL = os.path.join(ROOT, "data", "raw", "tm_pool_progress.csv")

sc = pd.read_csv(SCOUT)
pool = pd.read_csv(POOL)

# base previa (idempotente)
base_val = sc["valor_estimado"] if "valor_estimado" in sc.columns else sc["valor_mercado_meur"]

def norm_pid(s):
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
sc["_pid"] = norm_pid(sc["player_id"])
pool["_pid"] = norm_pid(pool["player_id"])

p = (pool[["_pid", "valor_mercado_meur"]]
     .dropna(subset=["_pid"]).drop_duplicates("_pid", keep="first")
     .rename(columns={"valor_mercado_meur": "valor_tm"}))

for c in ["valor_tm", "valor_origen", "valor_estimado"]:
    if c in sc.columns:
        sc = sc.drop(columns=c)

sc["valor_estimado"] = base_val
sc = sc.merge(p, on="_pid", how="left")

val_tm = pd.to_numeric(sc["valor_tm"], errors="coerce")
base_num = pd.to_numeric(sc["valor_estimado"], errors="coerce")
usar_tm = val_tm.notna() & (val_tm > 0)
sc["valor_mercado_meur"] = np.where(usar_tm, val_tm, base_num).round(2)
sc["valor_origen"] = np.where(usar_tm, "TM", "estimada")

sc = sc.drop(columns=["_pid", "valor_tm"])

bak = SCOUT + ".bak_valor"
if not os.path.exists(bak):
    shutil.copy(SCOUT, bak)
sc.to_csv(SCOUT, index=False)

print("Jugadores:", len(sc))
print("Con valor real de TM :", int((sc["valor_origen"] == "TM").sum()))
print("Sin valor TM         :", int((sc["valor_origen"] == "estimada").sum()))
vv = pd.to_numeric(sc["valor_mercado_meur"], errors="coerce").replace(0, np.nan)
print("Valor medio (>0)     :", round(vv.mean(), 2), "M EUR")
print()
print("TOP 10 por valor:")
print(sc.nlargest(10, "valor_mercado_meur")[["nombre", "club", "valor_mercado_meur", "valor_origen"]].to_string(index=False))