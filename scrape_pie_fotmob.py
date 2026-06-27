# -*- coding: utf-8 -*-
"""scrape_pie_fotmob.py  (v3 - endpoint suggest OK)
Completa el 'pie' de laterales/extremos s/d usando FotMob.
Busqueda: apigw.fotmob.com/searchapi/suggest  ->  "Nombre|ID"
Pie:      varias rutas de playerData

USO:
  python scrape_pie_fotmob.py pie 30981   -> DIAG: ver de donde sacar el pie de 1 id
  python scrape_pie_fotmob.py             -> lote de prueba (10)
  python scrape_pie_fotmob.py 999         -> todos
  python scrape_pie_fotmob.py selftest    -> logica sin red
"""
import os, sys, time, json, unicodedata, difflib
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

IN = "data/laterales_sin_pie.csv"
OUT = "data/pie_fotmob_resultado.csv"
SEARCH = "https://apigw.fotmob.com/searchapi/suggest?term={term}&lang=es,en"
PLAYER_URLS = [
    "https://www.fotmob.com/api/data/playerData?id={pid}",
    "https://www.fotmob.com/api/playerData?id={pid}",
]
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*",
     "Referer": "https://www.fotmob.com/", "Origin": "https://www.fotmob.com"}
PAUSA, TIMEOUT = 1.3, 15
FOOT_MAP = {"left": "Izquierdo", "right": "Derecho", "both": "Ambidiestro",
            "izquierdo": "Izquierdo", "derecho": "Derecho", "ambidiestro": "Ambidiestro"}

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    for ch in ".,'-_": s = s.replace(ch, " ")
    return " ".join(s.split())
def _sim(a, b): return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()

def _get(url):
    import requests
    for k in range(2):
        try:
            r = requests.get(url, headers=H, timeout=TIMEOUT)
            if r.status_code == 200:
                try: return r.json(), None
                except Exception: return None, "no-json"
            return None, "HTTP %d" % r.status_code
        except Exception as e:
            if k == 1: return None, "ERR " + type(e).__name__
            time.sleep(1.2)
    return None, "ERR"

def parse_suggest(data):
    """Devuelve lista de (nombre, id) desde la respuesta de /suggest."""
    out = []
    try:
        for blk in data.get("squadMemberSuggest", []) or []:
            for opt in blk.get("options", []) or []:
                txt = opt.get("text", "")
                if "|" in txt:
                    nm, pid = txt.rsplit("|", 1)
                    if pid.strip().isdigit():
                        out.append((nm.strip(), pid.strip()))
    except Exception:
        pass
    return out

def variantes_nombre(nombre_completo, jugador_abrev=""):
    """Genera variantes de busqueda, de mas probable a menos.
    FotMob indexa por nombre futbolistico corto, no por el nombre legal largo."""
    nc = " ".join(str(nombre_completo).split())
    toks = nc.split()
    vs = []
    if len(toks) >= 2:
        vs.append(toks[0] + " " + toks[-1])        # primer nombre + ultimo apellido
        vs.append(toks[0] + " " + toks[-2])        # primer nombre + penultimo apellido
    if len(toks) >= 3:
        vs.append(toks[-2] + " " + toks[-1])       # los dos ultimos apellidos
        vs.append(toks[0] + " " + toks[1])         # dos primeros tokens
    vs.append(nc)                                   # nombre completo tal cual
    if jugador_abrev and "." in jugador_abrev:      # "B. Gonzalez" -> "Gonzalez"
        ap = jugador_abrev.split(".")[-1].strip()
        if ap: vs.append(ap)
    # unicos preservando orden
    seen, out = set(), []
    for v in vs:
        k = _norm(v)
        if k and k not in seen:
            seen.add(k); out.append(v)
    return out

def buscar_id_multi(nombre_completo, club, jugador_abrev=""):
    """Prueba varias variantes del nombre; devuelve el mejor match con pie disponible."""
    for v in variantes_nombre(nombre_completo, jugador_abrev):
        data, err = _get(SEARCH.format(term=v.replace(" ", "%20")))
        if err:
            continue
        ops = parse_suggest(data)
        if not ops:
            continue
        # elegir por parecido con el nombre completo real
        best, mejor = -1.0, None
        for nm, pid in ops:
            sc = max(_sim(nombre_completo, nm), _sim(v, nm))
            if sc > best: best, mejor = sc, (pid, nm)
        if mejor and best >= 0.55:
            return mejor[0], mejor[1], "ok(%.2f via '%s')" % (best, v)
    return None, "", "sin match en variantes"

def pie_de(pid):
    for url in PLAYER_URLS:
        data, err = _get(url.format(pid=pid))
        if err: continue
        foot = ""
        try:
            # ruta confirmada: playerInformation -> item 'Preferred foot' -> value.key
            for it in (data.get("playerInformation") or []):
                ttl = str(it.get("title", "")).lower()
                tk = str(it.get("translationKey", "")).lower()
                if "foot" in ttl or "foot" in tk or ttl in ("pie",):
                    v = it.get("value", {})
                    if isinstance(v, dict):
                        foot = v.get("key") or v.get("fallback") or ""
                    else:
                        foot = v or ""
                    break
            if not foot:
                foot = data.get("preferredFoot") or (data.get("origin") or {}).get("preferredFoot") or ""
        except Exception:
            pass
        if foot: return FOOT_MAP.get(_norm(foot), foot), "ok"
    return "", "sin pie en playerData"

def diag_pie(pid):
    """Imprime crudo el playerData para localizar donde esta el pie."""
    import requests
    for url in PLAYER_URLS:
        u = url.format(pid=pid)
        try:
            r = requests.get(u, headers=H, timeout=TIMEOUT)
            print("URL:", u, "| status", r.status_code, "| bytes", len(r.content))
            if r.status_code == 200:
                low = r.text.lower()
                idx = low.find("foot")
                if idx >= 0:
                    print("  ...contexto de 'foot':", r.text[max(0,idx-60):idx+80].replace("\n"," "))
                else:
                    print("  (no aparece 'foot'); primeros 400:", r.text[:400].replace("\n"," "))
                return
        except Exception as e:
            print("ERR", type(e).__name__, u)
    print(">>> pega esto al asistente")

def selftest():
    canned = {"squadMemberSuggest":[{"options":[
        {"text":"Lionel Messi|30981"}, {"text":"Lionel Messina|99999"}]}]}
    op = parse_suggest(canned)
    assert ("Lionel Messi","30981") in op, op
    best,mejor=-1,None
    for nm,pid in op:
        sc=_sim("Lionel Messi",nm)
        if sc>best: best,mejor=sc,(pid,nm)
    assert mejor[0]=="30981", mejor
    assert FOOT_MAP[_norm("Left")]=="Izquierdo"
    # extraccion del pie con la estructura REAL de playerData
    player = {"playerInformation":[
        {"title":"Height","value":{"key":None,"fallback":"170 cm"}},
        {"value":{"key":"left","fallback":"Left"},"title":"Preferred foot","translationKey":"preferred_foot"}]}
    foot = ""
    for it in player["playerInformation"]:
        if "foot" in str(it.get("title","")).lower():
            foot = it["value"]["key"]; break
    assert FOOT_MAP[_norm(foot)] == "Izquierdo", foot
    # variantes: nombre legal largo -> formas cortas futbolisticas
    vs = variantes_nombre("Aldo Jafid Cruz Sanchez", "A. Cruz")
    assert "Aldo Sanchez" in vs or "Aldo Cruz" in vs, vs
    print("SELFTEST OK -> parsea ID, extrae pie y genera variantes de nombre corto.")

def procesar(limit):
    import pandas as pd
    if not os.path.exists(IN): print("ERROR: falta", IN); sys.exit(1)
    df = pd.read_csv(IN).head(limit).copy()
    filas = []
    print("Procesando", len(df), "jugadores...\n")
    for i, r in df.iterrows():
        # buscar por nombre completo si existe; si no, por 'jugador'
        nombre_busq = str(r.get("nombre_completo") or r.get("jugador") or "").strip()
        nombre_orig = str(r.get("jugador", nombre_busq))
        club = str(r.get("club",""))
        pid, fnm, nota = buscar_id_multi(nombre_busq, club, nombre_orig)
        foot, estado, conf = "", nota, "BAJA"
        if pid:
            foot, estado = pie_de(pid)
            nm_sim = _sim(nombre_busq, fnm)
            if foot and nm_sim >= 0.6: conf = "ALTA"
            elif foot: conf = "MEDIA"
        filas.append({"_row": r.get("_row", i), "jugador": nombre_orig,
                      "nombre_completo": nombre_busq, "club": club,
                      "fotmob_name": fnm, "pie_fotmob": foot, "confianza": conf, "estado": estado})
        print("  %-22s -> %-11s [%s] %s" % (nombre_busq[:22], foot or "-", conf, "("+str(fnm)[:20]+")"))
        time.sleep(PAUSA)
    out = pd.DataFrame(filas); out.to_csv(OUT, index=False, encoding="utf-8")
    ok = (out["pie_fotmob"].astype(str).str.len() > 0).sum()
    print("\nLISTO ->", OUT, "| con pie: %d/%d (ALTA %d)" %
          (ok, len(out), (out["confianza"]=="ALTA").sum()))
    if ok == 0:
        print(">>> 0 pies. Corre: python scrape_pie_fotmob.py pie 30981  (y pega salida)")

if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "10"
    if a == "selftest": selftest()
    elif a == "pie": diag_pie(sys.argv[2] if len(sys.argv) > 2 else "30981")
    else:
        try: lim = int(a)
        except: lim = 10
        procesar(lim)
