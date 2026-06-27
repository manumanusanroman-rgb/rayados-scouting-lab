import os, shutil
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SCOUT = os.path.join(ROOT, "data", "players_scouting.csv")
POOL = os.path.join(ROOT, "data", "raw", "tm_pool_progress.csv")

CAP_BAJA_CONFIANZA = 20.0   # un match dudoso no puede valer mas que esto
CAP_ABSURDO        = 60.0   # nadie en estas ligas vale mas que esto

sc = pd.read_csv(SCOUT)
pool = pd.read_csv(POOL)

def norm_id(s):
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

pool["_pid"] = norm_id(pool["player_id"])
pool["_tmid"] = norm_id(pool["tm_player_id"])
sc["_pid"] = norm_id(sc["player_id"])

# needs_review robusto (bool o texto)
nr = pool["needs_review"].astype(str).str.strip().str.lower()
confiable = nr.isin(["false", "0", "no"])

# colisiones: mismo tm_player_id en varios jugadores distintos
cnt = pool.groupby("_tmid")["_pid"].nunique()
dup_tmids = set(cnt[cnt > 1].index)
dup_tmids.discard("nan"); dup_tmids.discard("")

val = pd.to_numeric(pool["valor_mercado_meur"], errors="coerce")

es_colision   = pool["_tmid"].isin(dup_tmids)
dudoso_y_caro = (~confiable) & (val > CAP_BAJA_CONFIANZA)
absurdo       = (val > CAP_ABSURDO)
fiable = (val > 0) & (~es_colision) & (~dudoso_y_caro) & (~absurdo)

pool_ok = pool[fiable].copy()
pool_ok["valor_tm"] = val[fiable]
pool_ok = pool_ok[["_pid", "valor_tm"]]
pool_ok = pool_ok[pool_ok["_pid"] != "nan"].drop_duplicates("_pid", keep="first")

for c in ["valor_tm", "valor_origen"]:
    if c in sc.columns:
        sc = sc.drop(columns=c)

sc = sc.merge(pool_ok, on="_pid", how="left")
val_tm = pd.to_numeric(sc["valor_tm"], errors="coerce")
tiene_tm = val_tm.notna() & (val_tm > 0)

# estimado por mediana de (liga, posicion) usando solo valores reales
sc["_val_real"] = np.where(tiene_tm, val_tm, np.nan)
med_lp = sc.groupby(["liga", "posicion"])["_val_real"].transform("median")
med_liga = sc.groupby("liga")["_val_real"].transform("median")
med_glob = float(np.nanmedian(sc["_val_real"].values))
estimado = med_lp.fillna(med_liga).fillna(med_glob).round(2)

sc["valor_mercado_meur"] = np.where(tiene_tm, val_tm, estimado).round(2)
sc["valor_origen"] = np.where(tiene_tm, "TM", "estimada")

sc = sc.drop(columns=["_pid", "valor_tm", "_val_real"])

bak = SCOUT + ".bak_valor2"
if not os.path.exists(bak):
    shutil.copy(SCOUT, bak)
sc.to_csv(SCOUT, index=False)

print("Jugadores       :", len(sc))
print("Valor real de TM:", int((sc["valor_origen"] == "TM").sum()))
print("Valor estimado  :", int((sc["valor_origen"] == "estimada").sum()))
print("Con valor > 0   :", int((pd.to_numeric(sc["valor_mercado_meur"], errors="coerce") > 0).sum()))
print()
print("TOP 15 por valor (debe estar limpio):")
print(sc.nlargest(15, "valor_mercado_meur")[["nombre", "club", "liga", "valor_mercado_meur", "valor_origen"]].to_string(index=False))