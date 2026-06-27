# -*- coding: utf-8 -*-
"""crear_insignias_nuevas.py
Calcula y anade 3 insignias nuevas (columnas *_medalla / *_pts) a:
  data/players_scouting.csv  (el pool, referencia de percentiles)
  data/rayados_squad.csv     (squad, percentiles referidos al pool)

  - progresor_medalla : carreras_progresivas_90 + pases_progresivos_90 (percentil x posicion)
  - paradon_medalla   : paradas_pct, SOLO porteros (percentil entre porteros)
  - diamante_medalla  : edad<=23 + valor < mediana de su posicion + ya tiene
                        medalla de rendimiento (nivel = la mejor que tenga)
Niveles: ORO>=p85, PLATA>=p70, BRONCE>=p55. Backup + idempotente.
"""
import sys, os, shutil, datetime
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import numpy as np, pandas as pd

POOL = "data/players_scouting.csv"
SQUAD = "data/rayados_squad.csv"
PERF = ["tirador_lejano_medalla", "cabeceador_medalla", "recuperador_puro_medalla",
        "presionador_alto_medalla", "definidor_medalla", "creador_medalla",
        "desequilibrante_medalla", "muro_medalla", "motor_medalla"]
LV = {"ORO": 3, "PLATA": 2, "BRONCE": 1, "": 0, "nan": 0}

def medal_from_pct(p):
    if pd.isna(p): return ""
    if p >= 85: return "ORO"
    if p >= 70: return "PLATA"
    if p >= 55: return "BRONCE"
    return ""

def pct_vs_ref(df, ref, valcol):
    """percentil del valor de df dentro de la distribucion de ref, por posicion."""
    out = pd.Series(np.nan, index=df.index)
    refv = pd.to_numeric(ref[valcol], errors="coerce")
    for pos in df["posicion"].dropna().astype(str).unique():
        ref_s = refv[ref["posicion"].astype(str) == pos].dropna()
        if ref_s.empty: continue
        m = df["posicion"].astype(str) == pos
        vals = pd.to_numeric(df.loc[m, valcol], errors="coerce")
        out.loc[m] = vals.map(lambda v: float((ref_s <= v).mean() * 100) if pd.notna(v) else np.nan)
    return out

def best_perf_level(row):
    best = 0
    for c in PERF:
        if c in row.index:
            best = max(best, LV.get(str(row[c]).upper(), 0))
    return best

def add_insignias(df, ref):
    df = df.copy()
    # Progresor
    for d in (df, ref):
        d["_prog_tmp"] = (pd.to_numeric(d.get("carreras_progresivas_90"), errors="coerce").fillna(0)
                          + pd.to_numeric(d.get("pases_progresivos_90"), errors="coerce").fillna(0))
    p = pct_vs_ref(df, ref, "_prog_tmp")
    df["progresor_pts"] = p.round(0)
    df["progresor_medalla"] = p.map(medal_from_pct)
    # Paradon (solo porteros)
    pk = pct_vs_ref(df[df["posicion"].astype(str) == "Portero"], ref[ref["posicion"].astype(str) == "Portero"], "paradas_pct") \
        if "paradas_pct" in df.columns else pd.Series(dtype=float)
    df["paradon_pts"] = 0.0
    df["paradon_medalla"] = ""
    if len(pk):
        df.loc[pk.index, "paradon_pts"] = pk.round(0)
        df.loc[pk.index, "paradon_medalla"] = pk.map(medal_from_pct)
    # Diamante: joven + barato + con medalla de rendimiento
    edad = pd.to_numeric(df.get("edad"), errors="coerce")
    valor = pd.to_numeric(df.get("valor_mercado_meur"), errors="coerce")
    med_pos = df.assign(_v=valor).groupby(df["posicion"].astype(str))["_v"].transform("median")
    joven = edad <= 23
    barato = valor < med_pos
    perf = df.apply(best_perf_level, axis=1)
    dia_lv = np.where(joven & barato & (perf > 0), perf, 0)
    inv = {3: "ORO", 2: "PLATA", 1: "BRONCE", 0: ""}
    df["diamante_medalla"] = [inv[int(x)] for x in dia_lv]
    df["diamante_pts"] = [ {3:100,2:70,1:50,0:0}[int(x)] for x in dia_lv ]
    df = df.drop(columns=["_prog_tmp"], errors="ignore")
    return df

def main():
    if not os.path.exists(POOL):
        print("ERROR: ejecuta dentro de rayados_scouting_lab."); return
    pool = pd.read_csv(POOL)
    pool2 = add_insignias(pool, pool)
    bak = POOL + ".bak_insig_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy(POOL, bak); pool2.to_csv(POOL, index=False, encoding="utf-8")
    print("POOL listo. Backup:", bak)
    for m in ["progresor_medalla", "paradon_medalla", "diamante_medalla"]:
        print("  ", m, "->", pool2[m].replace("", np.nan).dropna().value_counts().to_dict())
    if os.path.exists(SQUAD):
        sq = pd.read_csv(SQUAD)
        sq2 = add_insignias(sq, pool)   # squad referido al pool
        bak2 = SQUAD + ".bak_insig_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(SQUAD, bak2); sq2.to_csv(SQUAD, index=False, encoding="utf-8")
        print("SQUAD listo. Backup:", bak2)

if __name__ == "__main__":
    main()
