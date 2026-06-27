"""
enrich_rayados_medals.py
Une medallas + xG real a la plantilla de Rayados por player_id.
"""
import pandas as pd
from pathlib import Path

DATA = Path("data")
sq  = pd.read_csv(DATA / "rayados_squad.csv")
med = pd.read_csv(DATA / "player_medals.csv")
ev  = pd.read_csv(DATA / "player_events_stats.csv")

print(f"Rayados: {len(sq)} jugadores")
print(f"squad tiene player_id: {'player_id' in sq.columns}")

if "player_id" not in sq.columns:
    # match por nombre si no hay player_id
    import unicodedata
    def norm(s):
        if pd.isna(s): return ""
        s=str(s).strip().lower()
        s=unicodedata.normalize("NFD",s)
        return "".join(c for c in s if unicodedata.category(c)!="Mn")
    ev["_n"]=ev["nombre"].apply(norm)
    sq["_n"]=sq["jugador"].apply(norm)
    ev_xg = ev[["_n","xg"]].drop_duplicates("_n")
    sq = sq.merge(ev_xg, on="_n", how="left")
    med["_n"]=med["nombre"].apply(norm)
    medm = med.drop_duplicates("_n")
    key="_n"
else:
    sq = sq.merge(ev[["player_id","xg"]], on="player_id", how="left")
    medm = med
    key="player_id"

sq["xg"]=sq["xg"].fillna(0)
sq["xg_90"]=((sq["xg"]/sq["minutos"].clip(lower=1))*90).round(2)
sq.drop(columns=["xg"],inplace=True)

med_cols=[key,"tirador_lejano_medalla","tirador_lejano_pts","cabeceador_medalla","cabeceador_pts",
          "recuperador_puro_medalla","recuperador_puro_pts","presionador_alto_medalla","presionador_alto_pts"]
med_cols=[c for c in med_cols if c in medm.columns]
sq = sq.merge(medm[med_cols], on=key, how="left")

for c in ["tirador_lejano_medalla","cabeceador_medalla","recuperador_puro_medalla","presionador_alto_medalla"]:
    if c in sq.columns: sq[c]=sq[c].fillna("")
for c in ["tirador_lejano_pts","cabeceador_pts","recuperador_puro_pts","presionador_alto_pts"]:
    if c in sq.columns: sq[c]=sq[c].fillna(0)

EMOJI={"ORO":"🥇","PLATA":"🥈","BRONCE":"🥉"}
ABREV={"tirador_lejano_medalla":"TL","cabeceador_medalla":"CAB",
       "recuperador_puro_medalla":"REC","presionador_alto_medalla":"PRE"}
def resumen(row):
    out=[]
    for col,ab in ABREV.items():
        if col in row and row[col] in EMOJI:
            out.append(f"{EMOJI[row[col]]}{ab}")
    return " ".join(out)
sq["medallas"]=sq.apply(resumen,axis=1)

if "_n" in sq.columns: sq.drop(columns=["_n"],inplace=True)
sq.to_csv(DATA / "rayados_squad.csv", index=False)

print(f"\nGUARDADO.")
print(f"  xg_90>0: {(sq['xg_90']>0).sum()}/{len(sq)}")
print(f"  con medalla: {(sq['medallas']!='').sum()}/{len(sq)}")
print(sq[["jugador","xg_90","medallas"]].to_string(index=False))