"""
calc_liga_benchmark.py
Calcula promedios /90 de TODOS los equipos de Liga MX 2024-25 para normalizar radares.
Genera data/liga_benchmark.csv (18 equipos).
"""
import pandas as pd, zipfile, json
from pathlib import Path
from collections import defaultdict

ZIP = Path(r"C:\Users\msanr\Datos\EVENTING_LIGAS\testeo_ligas_norteamerica.zip")
ROOT = "testeo_ligas_norteamerica/Mexico_Liga_MX/2024-2025"

# tasas xG reales del dataset
dfp = pd.read_csv("data/player_events_stats.csv")
def tasa(tc, gc):
    t=dfp[tc].sum(); g=dfp[gc].sum(); return g/t if t>0 else 0
TASAS={"peq":tasa("tiros_area_pequena","goles_area_pequena"),
       "gra":tasa("tiros_area_grande","goles_area_grande"),
       "fue":tasa("tiros_fuera_area","goles_fuera_area")}

# acumuladores por equipo
S = defaultdict(lambda: defaultdict(float))
PJ = defaultdict(int)

# typeIds
GOL=16; SHOTS={13,14,15,16}; PASE=1; RECUP=49; TACKLE=7; INTER=8
QUAL_KEYPASS=210

with zipfile.ZipFile(ZIP) as z:
    partidos=[n for n in z.namelist() if n.startswith(f"{ROOT}/partidos/") and n.endswith(".json")]
    for pth in partidos:
        d=json.loads(z.read(pth))
        mi=d.get("matchInfo",{}); ld=d.get("liveData",{})
        cs=mi.get("contestant",[])
        if len(cs)<2: continue
        hid=cs[0].get("id"); aid=cs[1].get("id")
        hname=cs[0].get("name"); aname=cs[1].get("name")
        acc={hid:defaultdict(float), aid:defaultdict(float)}
        for ev in ld.get("event",[]):
            cid=ev.get("contestantId"); tid=ev.get("typeId"); x=ev.get("x",0)
            if cid not in acc: continue
            a=acc[cid]
            if tid==GOL: a["goles"]+=1
            if tid in SHOTS:
                a["tiros"]+=1
                if x>=94: a["xg"]+=TASAS["peq"]
                elif x>=83: a["xg"]+=TASAS["gra"]
                else: a["xg"]+=TASAS["fue"]
            if tid==RECUP: a["recuperaciones"]+=1
            if tid==TACKLE and ev.get("outcome",0)==1: a["entradas"]+=1
            if tid==INTER: a["intercepciones"]+=1
            if tid==PASE:
                for q in ev.get("qualifier",[]):
                    if q.get("qualifierId")==QUAL_KEYPASS: a["pases_clave"]+=1; break
        # asignar (goles concedidos y xGA = del rival)
        for me,opp,name in [(hid,aid,hname),(aid,hid,aname)]:
            PJ[name]+=1
            S[name]["goles_90"]+=acc[me]["goles"]
            S[name]["goles_concedidos_90"]+=acc[opp]["goles"]
            S[name]["tiros_90"]+=acc[me]["tiros"]
            S[name]["xg_90"]+=acc[me]["xg"]
            S[name]["xga_90"]+=acc[opp]["xg"]
            S[name]["recuperaciones_90"]+=acc[me]["recuperaciones"]
            S[name]["entradas_90"]+=acc[me]["entradas"]
            S[name]["intercepciones_90"]+=acc[me]["intercepciones"]
            S[name]["pases_clave_90"]+=acc[me]["pases_clave"]

rows=[]
for name,pj in PJ.items():
    r={"equipo":name,"partidos":pj}
    for k,v in S[name].items():
        r[k]=round(v/pj,2)
    rows.append(r)
df=pd.DataFrame(rows).sort_values("xg_90",ascending=False)
df.to_csv("data/liga_benchmark.csv",index=False)
print(f"Generado liga_benchmark.csv con {len(df)} equipos")
print(df[["equipo","goles_90","goles_concedidos_90","xg_90","pases_clave_90","entradas_90","recuperaciones_90"]].to_string(index=False))