"""
scrape_edades_tm.py
===================
Saca la EDAD real (y de regalo el valor de mercado) de los 3.340 jugadores
del pool, scrapeando Transfermarkt POR CLUB en vez de por jugador.

Por que por club:
- 159 clubs => 159 plantillas, no 3.340 busquedas por nombre.
- Mucho mas fiable: emparejar un apellido dentro de la plantilla de SU club
  no falla; buscar el nombre suelto en todo TM trae homonimos.
- Reutiliza el parser de plantilla que ya funciona en src/data_fetcher.py.

Flujo:
  nombre de club  ->  buscar ID en TM (filtrando por pais de la liga)
                  ->  bajar plantilla de ese club
                  ->  emparejar cada jugador del pool por apellido
                  ->  guardar edad + valor + confianza del match

Es RETOMABLE: si se corta, al relanzar salta clubs/plantillas ya hechos.

USO (desde la carpeta del proyecto, con el entorno 'rayados' activado):
    python scrape_edades_tm.py test     <- prueba con los primeros 3 clubs
    python scrape_edades_tm.py full      <- scrapea los 159 clubs

Salida:
    data/raw/tm_pool_progress.csv   (jugador del pool + edad_tm + valor + score)
    data/raw/tm_club_ids.csv        (cache: club -> tm_id, pais)
    data/raw/tm_club_overrides.csv  (correcciones manuales de club, si hicieran falta)
    data/raw/tm_club_squads/*.csv   (cache de cada plantilla)
"""
from __future__ import annotations

import sys
import time
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- Reutilizamos las piezas ya probadas del bloque 1 -----------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.data_fetcher import (  # noqa: E402
    HEADERS_BROWSER,
    _tm_parse_squad_row,
    _tm_parse_value,
    save_debug_html,
    TM_BASE,
)

# ============================================================================
# CONFIG
# ============================================================================
DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
SQUAD_CACHE = RAW / "tm_club_squads"
RAW.mkdir(parents=True, exist_ok=True)
SQUAD_CACHE.mkdir(parents=True, exist_ok=True)

POOL_CSV = DATA / "players_scouting.csv"
CLUB_ID_CACHE = RAW / "tm_club_ids.csv"
OVERRIDES_CSV = RAW / "tm_club_overrides.csv"
PROGRESS_CSV = RAW / "tm_pool_progress.csv"

SLEEP = 5            # segundos entre requests (anti-baneo)
SEASON = 2025        # temporada para la URL /kader
TEST_N_CLUBS = 3     # cuantos clubs en modo 'test'

# Pais(es) esperados por liga -> para descartar clubs homonimos de otro pais.
# TM (sitio .es) muestra los paises en espanol.
LIGA_COUNTRY = {
    "Liga MX":   {"mexico"},
    "MLS":       {"estados unidos", "canada"},   # MLS tiene clubs canadienses
    "Brasil A":  {"brasil"},
    "Brasil B":  {"brasil"},
    "Argentina": {"argentina"},
    "Chile":     {"chile"},
    "Colombia":  {"colombia"},
    "Ecuador":   {"ecuador"},
}

# Paises que pueden salir en los resultados (para leer la bandera por su 'title')
COUNTRY_WORDS = {
    "mexico", "brasil", "argentina", "chile", "colombia", "ecuador",
    "estados unidos", "canada", "uruguay", "bolivia", "paraguay", "peru",
    "venezuela", "espana", "italia", "francia", "alemania", "inglaterra",
    "portugal", "japon", "rusia", "estados unidos de america",
}

# Filiales / juveniles / femenino a descartar al elegir el club senior
RESERVE_PAT = re.compile(
    r"(?:^|\s)(ii|iii|b|sub\s?-?\d+|u\s?-?\d+|juveniles?|reserva|reservas|"
    r"academy|youth|fem(?:enino)?|sub20|sub23|proyeccion)(?:$|\s)", re.I
)

# Umbrales de confianza del emparejado
SCORE_ACCEPT = 0.60   # >= se acepta
SCORE_REVIEW = 0.40   # entre REVIEW y ACCEPT -> se guarda pero marcado needs_review


# ============================================================================
# NORMALIZACION Y EMPAREJADO DE NOMBRES
# ============================================================================
def norm(s) -> str:
    """minusculas, sin acentos, solo letras/numeros/espacios."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_opta_name(opta_short: str, opta_full: str):
    """
    Extrae (inicial_nombre, apellido, set_tokens_nombre_completo) del pool.

    'S. Rodriguez' / 'Santiago ... Rodriguez' -> ('s', 'rodriguez', {...})
    'Matheus Doria'                            -> ('m', 'doria', {...})
    """
    s_toks = norm(opta_short).split()
    f_toks = norm(opta_full).split()

    # inicial del nombre de pila
    if s_toks and len(s_toks[0]) == 1:
        initial = s_toks[0]                    # 'S. Rodriguez' -> 's'
    elif s_toks:
        initial = s_toks[0][0]                 # 'Matheus Doria' -> 'm'
    elif f_toks:
        initial = f_toks[0][0]
    else:
        initial = ""

    # apellido: ultimo token "real" (>1 letra) del nombre abreviado o completo
    surname_src = [t for t in s_toks if len(t) > 1] or [t for t in f_toks if len(t) > 1]
    surname = surname_src[-1] if surname_src else ""

    full_set = {t for t in f_toks if len(t) > 1}
    return initial, surname, full_set


def name_match_score(opta_full: str, opta_short: str, tm_name: str) -> float:
    """
    Puntua 0..1 lo bien que un nombre de TM encaja con un jugador del pool.

    Reglas:
      - Sin apellido en comun -> 0 (no es match).
      - Apellido coincide Y la inicial del nombre de pila cuadra -> base 0.6.
      - Apellido coincide pero el nombre de pila NO -> solo 0.15
        (casi seguro otro jugador: evita asignar 'Diego Rodriguez'
         a 'Santiago Rodriguez').
      - + hasta 0.4 segun cuantos tokens del nombre completo aparezcan en TM.
    """
    nt = norm(tm_name)
    if not nt:
        return 0.0
    tm_toks = nt.split()
    tm_set = set(tm_toks)
    tm_first = tm_toks[0] if tm_toks else ""

    initial, surname, full_set = _parse_opta_name(opta_short, opta_full)
    if not surname or surname not in tm_set:
        return 0.0

    initial_ok = bool(initial) and tm_first.startswith(initial)
    score = 0.6 if initial_ok else 0.15
    if full_set:
        overlap = sum(1 for t in full_set if t in tm_set)
        score += 0.4 * (overlap / len(full_set))
    return min(score, 1.0)


def match_in_squad(opta_full: str, opta_short: str, squad: pd.DataFrame):
    """
    Devuelve (fila_tm, score, ambiguo) del mejor match en la plantilla.
    'ambiguo' = True si hay empate de score con otro jugador (mismo apellido).
    """
    if squad is None or squad.empty or "jugador" not in squad.columns:
        return None, 0.0, False

    scored = []
    for _, row in squad.iterrows():
        sc = name_match_score(opta_full, opta_short, str(row.get("jugador", "")))
        scored.append((sc, row))
    scored.sort(key=lambda x: x[0], reverse=True)

    best_score, best_row = scored[0]
    ambiguo = len(scored) > 1 and abs(scored[1][0] - best_score) < 1e-9 and best_score > 0
    return best_row, best_score, ambiguo


# ============================================================================
# TRANSFERMARKT: RESOLVER ID DE CLUB Y BAJAR PLANTILLA
# ============================================================================
def load_overrides() -> dict:
    """club (normalizado) -> {'tm_id', 'slug'} desde el CSV manual."""
    out = {}
    if OVERRIDES_CSV.exists():
        df = pd.read_csv(OVERRIDES_CSV)
        for _, r in df.iterrows():
            out[norm(str(r["club"]))] = {
                "tm_id": int(r["tm_id"]),
                "slug": str(r.get("slug", "")) or "club",
            }
    return out


def _outer_data_row(a):
    """
    En los resultados de busqueda, el <a> del nombre vive dentro de una
    tabla ANIDADA (foto+nombre). La fila de DATOS real (con pais/plantilla
    o edad/valor) es la <tr> que contiene esa tabla anidada, un nivel afuera.
    """
    inner_table = a.find_parent("table")
    if inner_table is not None:
        outer = inner_table.find_parent("tr")
        if outer is not None:
            return outer
    return a.find_parent("tr")


import time


def _club_query_variants(club_name: str):
    """Variantes de busqueda: nombre completo y versiones cada vez mas simples."""
    base = club_name.strip()
    out = [base]
    sin_par = re.sub(r"\s*\([^)]*\)", "", base).strip()
    if sin_par and sin_par not in out:
        out.append(sin_par)
    pref = {"club", "cd", "csd", "sc", "se", "ac", "ca", "aa", "af", "ad",
            "cf", "ec", "fbc", "fc", "fb", "sa", "sad"}
    core = [t for t in sin_par.split() if t.lower().strip(".") not in pref]
    n_core = " ".join(core).strip()
    if n_core and n_core not in out:
        out.append(n_core)
    if len(core) >= 2 and " ".join(core[:2]) not in out:
        out.append(" ".join(core[:2]))
    if core and core[0] not in out:
        out.append(core[0])
    return out


def resolve_club_id(club_name: str, liga: str, session: requests.Session):
    """
    Busca el club en TM y devuelve (tm_id, slug, pais) del mejor candidato
    cuyo pais cuadre con la liga. Devuelve (None, None, None) si no encuentra.
    """
    soup = None
    r = None
    for _q in _club_query_variants(club_name):
        _url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={requests.utils.quote(_q)}"
        print(f"    [buscar club] {_q!r} -> {_url}")
        r = session.get(_url, headers=HEADERS_BROWSER, timeout=30)
        r.raise_for_status()
        _soup = BeautifulSoup(r.text, "lxml")
        if _soup.find("a", href=re.compile(r"/startseite/verein/\d+")):
            soup = _soup
            break
        time.sleep(2.0)
    if soup is None:
        soup = BeautifulSoup(r.text, "lxml")

    paises_ok = LIGA_COUNTRY.get(liga, set())
    candidates = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/startseite/verein/\d+")):
        m = re.search(r"/([^/]+)/startseite/verein/(\d+)", a["href"])
        if not m:
            continue
        slug, vid = m.group(1), int(m.group(2))
        name = a.get_text(strip=True)
        if not name or vid in seen:
            continue
        seen.add(vid)

        row = _outer_data_row(a)
        pais = ""
        squad_size = 0
        if row is not None:
            cells = row.find_all("td", recursive=False)
            # pais: img cuyo 'title' sea un pais conocido (ignora escudo del club)
            for img in row.find_all("img"):
                t = norm(img.get("title", ""))
                if t in COUNTRY_WORDS:
                    pais = t
                    break
            # plantilla: celda con un entero "pelado" 0..60
            for td in cells:
                txt = td.get_text(strip=True)
                if txt.isdigit() and 0 <= int(txt) <= 60:
                    squad_size = int(txt)
                    break

        candidates.append({
            "slug": slug, "tm_id": vid, "name": name, "pais": pais,
            "squad_size": squad_size,
            "is_reserve": bool(RESERVE_PAT.search(name)),
        })

    if not candidates:
        save_debug_html(r.text, f"debug_buscar_{norm(club_name).replace(' ', '_')}.html")
        return None, None, None

    def country_ok(c):
        # aceptamos si no sabemos pais esperado, o si cuadra, o si no se leyo pais
        return (not paises_ok) or (c["pais"] in paises_ok) or (c["pais"] == "")

    # preferimos: pais correcto + NO filial; luego relajamos
    pool = [c for c in candidates if country_ok(c) and not c["is_reserve"]]
    if not pool:
        pool = [c for c in candidates if country_ok(c)]
    if not pool:
        pool = candidates

    qn = norm(club_name)
    qtoks = set(qn.split())

    def rank(c):
        cn = norm(c["name"])
        ctoks = set(cn.split())
        return (
            1 if (cn == qn or qn in cn or cn in qn) else 0,  # nombre encaja
            1 if c["pais"] in paises_ok else 0,               # pais correcto
            len(qtoks & ctoks),                                # solape tokens
            c["squad_size"],                                   # senior = mayor
        )

    pool.sort(key=rank, reverse=True)
    best = pool[0]
    print(f"      candidato: {best['name']} | pais={best['pais'] or '?'} "
          f"| plantilla={best['squad_size']} | id={best['tm_id']}")
    if paises_ok and best["pais"] and best["pais"] not in paises_ok:
        print(f"      [aviso] pais {best['pais']} != esperado {paises_ok} - revisar override")
    return best["tm_id"], best["slug"], best["pais"]


def fetch_squad(tm_id: int, slug: str, session: requests.Session) -> pd.DataFrame:
    """Baja (o lee de cache) la plantilla de un club."""
    cache = SQUAD_CACHE / f"{tm_id}.csv"
    if cache.exists():
        print(f"    [cache plantilla] {cache.name}")
        return pd.read_csv(cache)

    url = f"{TM_BASE}/{slug or 'club'}/kader/verein/{tm_id}/saison_id/{SEASON}/plus/1"
    print(f"    [plantilla] GET {url}")
    r = session.get(url, headers=HEADERS_BROWSER, timeout=30)
    print(f"        status: {r.status_code}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    table = (
        soup.find("table", {"class": "items"})
        or soup.select_one("div.responsive-table table")
    )
    if table is None or table.find("tbody") is None:
        save_debug_html(r.text, f"debug_plantilla_{tm_id}.html")
        raise RuntimeError(f"no encuentro tabla de plantilla para club {tm_id}")

    rows = []
    for tr in table.find("tbody").find_all("tr", recursive=False):
        try:
            parsed = _tm_parse_squad_row(tr)
            if parsed and parsed.get("jugador"):
                rows.append(parsed)
        except Exception as e:
            print(f"        skip fila: {type(e).__name__}: {e}")
            continue

    df = pd.DataFrame(rows)
    df.to_csv(cache, index=False)
    print(f"    [guardada] {cache.name} ({len(df)} jugadores)")
    time.sleep(SLEEP)
    return df


# ============================================================================
# FALLBACK: BUSQUEDA POR NOMBRE (para transferidos que no estan en su club)
# ============================================================================
def search_player_age(full_name: str, short_name: str, session: requests.Session):
    """
    Busca un jugador por nombre en TM y devuelve (edad, valor_meur,
    tm_nombre, tm_player_id, score, club_actual) del mejor candidato.
    Lee la edad/valor directo de la tabla de resultados (no entra al perfil).
    Si no encuentra, edad = None y score = 0.
    """
    query = requests.utils.quote(full_name)
    url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={query}"
    r = session.get(url, headers=HEADERS_BROWSER, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    cands = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/profil/spieler/\d+")):
        m = re.search(r"/profil/spieler/(\d+)", a["href"])
        if not m:
            continue
        pid = int(m.group(1))
        name = a.get_text(strip=True)
        if not name or pid in seen:
            continue
        seen.add(pid)

        row = _outer_data_row(a)
        edad = None
        valor = 0.0
        club_actual = ""
        if row is not None:
            for td in row.find_all("td", recursive=False):
                txt = td.get_text(" ", strip=True)
                if edad is None and txt.isdigit() and 15 <= int(txt) <= 45:
                    edad = int(txt)
                low = txt.lower()
                if "mill" in low or "mio" in low or " mil " in f" {low} ":
                    v = _tm_parse_value(txt)
                    if v:
                        valor = v
            # club actual: el escudo (img) cuyo title no es pais ni el jugador
            for img in row.find_all("img"):
                t = img.get("title", "")
                nt = norm(t)
                if t and nt not in COUNTRY_WORDS and nt != norm(name) and t != "Verificado":
                    club_actual = t
                    break

        cands.append({"pid": pid, "name": name, "edad": edad,
                      "valor": valor, "club_actual": club_actual})

    if not cands:
        return None, 0.0, "", None, 0.0, ""

    best, best_s = None, -1.0
    for c in cands:
        s = name_match_score(full_name, short_name, c["name"])
        if s > best_s:
            best_s, best = s, c

    return (best["edad"], best["valor"], best["name"], best["pid"],
            best_s, best["club_actual"])


# ============================================================================
# MAIN
# ============================================================================
def main(modo: str = "test"):
    if not POOL_CSV.exists():
        print(f"ERROR: no encuentro {POOL_CSV}")
        sys.exit(1)

    pool = pd.read_csv(POOL_CSV)
    print(f"Pool cargado: {len(pool)} jugadores, {pool['club'].nunique()} clubs")

    # clubs unicos con su liga
    clubs = (
        pool[["club", "liga"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["liga", "club"])
        .reset_index(drop=True)
    )
    if modo == "test":
        clubs = clubs.head(TEST_N_CLUBS)
        print(f"MODO TEST: solo {len(clubs)} clubs\n")
    else:
        print(f"MODO FULL: {len(clubs)} clubs\n")

    # caches / progreso retomable
    overrides = load_overrides()
    club_ids = {}
    if CLUB_ID_CACHE.exists():
        cid = pd.read_csv(CLUB_ID_CACHE)
        for _, r in cid.iterrows():
            club_ids[norm(str(r["club"]))] = r.to_dict()

    done_progress = pd.DataFrame()
    if PROGRESS_CSV.exists():
        done_progress = pd.read_csv(PROGRESS_CSV)
    done_ids = set(done_progress["player_id"]) if "player_id" in done_progress else set()

    session = requests.Session()
    new_rows = []
    club_id_rows = list(club_ids.values())

    for i, crow in clubs.iterrows():
        club, liga = crow["club"], crow["liga"]
        print(f"[{i+1}/{len(clubs)}] {club} ({liga})")

        # jugadores del pool de este club que falten
        sub = pool[(pool["club"] == club) & (pool["liga"] == liga)]
        sub = sub[~sub["player_id"].isin(done_ids)]
        if sub.empty:
            print("    (ya estaban todos sus jugadores, salto)")
            continue

        # resolver id de club (override > cache > buscar)
        key = norm(club)
        if key in overrides:
            tm_id, slug, pais = overrides[key]["tm_id"], overrides[key]["slug"], "(override)"
        elif key in club_ids:
            c = club_ids[key]
            tm_id, slug, pais = int(c["tm_id"]), str(c.get("slug", "club")), c.get("pais", "")
        else:
            try:
                tm_id, slug, pais = resolve_club_id(club, liga, session)
            except Exception as e:
                print(f"    [error buscando club] {type(e).__name__}: {e}")
                tm_id = None
            time.sleep(SLEEP)
            if tm_id is None:
                print("    [!] no resuelto, lo salto (revisar manualmente)")
                continue
            club_ids[key] = {"club": club, "liga": liga, "tm_id": tm_id,
                             "slug": slug, "pais": pais}
            club_id_rows.append(club_ids[key])
            pd.DataFrame(club_id_rows).drop_duplicates(
                subset=["tm_id"]).to_csv(CLUB_ID_CACHE, index=False)

        print(f"    club_id={tm_id} pais={pais}")

        # bajar plantilla
        try:
            squad = fetch_squad(tm_id, slug, session)
        except Exception as e:
            print(f"    [error plantilla] {type(e).__name__}: {e}")
            continue

        # emparejar cada jugador del pool (recolectamos primero, luego
        # resolvemos colisiones: un jugador de TM no puede ir a 2 del pool)
        club_matches = []
        for _, p in sub.iterrows():
            tm_row, score, ambiguo = match_in_squad(
                str(p.get("nombre_completo", "")),
                str(p.get("nombre", "")),
                squad,
            )
            club_matches.append({"p": p, "tm_row": tm_row, "score": score,
                                 "ambiguo": ambiguo})

        # Colisiones: si varios del pool apuntan al MISMO tm_player_id,
        # se queda el de mayor score; a los demas se les quita la edad
        # y se marcan para revision (probablemente transferidos).
        best_for_pid = {}
        for m in club_matches:
            if m["tm_row"] is None or m["score"] < SCORE_REVIEW:
                continue
            pid = m["tm_row"].get("tm_player_id")
            if pd.isna(pid):
                continue
            if pid not in best_for_pid or m["score"] > best_for_pid[pid]["score"]:
                best_for_pid[pid] = m

        for m in club_matches:
            p, tm_row, score, ambiguo = m["p"], m["tm_row"], m["score"], m["ambiguo"]
            colision = False
            valido = tm_row is not None and score >= SCORE_REVIEW
            if valido and not pd.isna(tm_row.get("tm_player_id")):
                pid = tm_row.get("tm_player_id")
                if best_for_pid.get(pid) is not m:
                    colision = True   # otro del pool encaja mejor con este de TM

            if not valido or colision:
                edad_tm = pd.NA
                valor = pd.NA
                tm_name = tm_row.get("jugador", "") if (tm_row is not None and colision) else ""
                tm_pid = pd.NA
            else:
                edad_tm = tm_row.get("edad", pd.NA)
                valor = tm_row.get("valor_mercado_meur", pd.NA)
                tm_name = tm_row.get("jugador", "")
                tm_pid = tm_row.get("tm_player_id", pd.NA)

            new_rows.append({
                "player_id": p["player_id"],
                "nombre": p.get("nombre", ""),
                "nombre_completo": p.get("nombre_completo", ""),
                "club": club,
                "liga": liga,
                "tm_id_club": tm_id,
                "tm_nombre_match": tm_name,
                "tm_player_id": tm_pid,
                "edad_tm": edad_tm,
                "valor_mercado_meur": valor,
                "match_score": round(score, 3),
                "needs_review": (not valido) or colision or (score < SCORE_ACCEPT) or ambiguo,
                "fuente": "club" if (valido and not colision) else "pendiente",
            })

        # checkpoint tras cada club
        combined = pd.concat(
            [done_progress, pd.DataFrame(new_rows)], ignore_index=True
        ).drop_duplicates(subset=["player_id"], keep="last")
        combined.to_csv(PROGRESS_CSV, index=False)
        print(f"    [checkpoint] {len(combined)} jugadores en {PROGRESS_CSV.name}\n")

    # ------------------------------------------------------------------
    # FASE B: fallback por nombre para los que quedaron 'pendiente'
    # ------------------------------------------------------------------
    prog = pd.read_csv(PROGRESS_CSV) if PROGRESS_CSV.exists() else pd.DataFrame()
    if not prog.empty and "fuente" in prog.columns:
        pend = prog[prog["fuente"] == "pendiente"]
        print(f"\n=== FASE B: fallback por nombre ({len(pend)} pendientes) ===")
        for n, (idx, row) in enumerate(pend.iterrows(), 1):
            full = str(row.get("nombre_completo", ""))
            short = str(row.get("nombre", ""))
            print(f"  [{n}/{len(pend)}] busco {short} ({full})")
            try:
                edad, valor, tm_name, tm_pid, score, club_act = search_player_age(
                    full, short, session)
            except Exception as e:
                print(f"      [error] {type(e).__name__}: {e}")
                time.sleep(SLEEP)
                continue
            time.sleep(SLEEP)

            if edad is not None and score >= SCORE_REVIEW:
                prog.at[idx, "edad_tm"] = edad
                prog.at[idx, "valor_mercado_meur"] = valor
                prog.at[idx, "tm_nombre_match"] = tm_name
                prog.at[idx, "tm_player_id"] = tm_pid
                prog.at[idx, "match_score"] = round(score, 3)
                prog.at[idx, "needs_review"] = True   # fallback siempre se revisa
                prog.at[idx, "fuente"] = "fallback"
                print(f"      -> {tm_name}, {edad} anios (score {score:.2f}, "
                      f"ahora en {club_act or '?'})")
            else:
                prog.at[idx, "fuente"] = "no_encontrado"
                print("      -> sin resultado fiable")

            if n % 10 == 0:   # checkpoint cada 10
                prog.to_csv(PROGRESS_CSV, index=False)
        prog.to_csv(PROGRESS_CSV, index=False)

    # resumen final
    final = pd.read_csv(PROGRESS_CSV) if PROGRESS_CSV.exists() else pd.DataFrame()
    if not final.empty:
        con_edad = final["edad_tm"].notna().sum()
        revisar = final["needs_review"].sum() if "needs_review" in final else 0
        print("=" * 50)
        print(f"TOTAL procesados: {len(final)}")
        print(f"  con edad encontrada: {con_edad}")
        if "fuente" in final.columns:
            print("  por fuente:")
            for k, v in final["fuente"].value_counts().items():
                print(f"     {k}: {v}")
        print(f"  a revisar (needs_review): {revisar}")
        print(f"Archivo: {PROGRESS_CSV}")


if __name__ == "__main__":
    modo = sys.argv[1].lower() if len(sys.argv) > 1 else "test"
    if modo not in ("test", "full"):
        print("Uso: python scrape_edades_tm.py [test|full]")
        sys.exit(1)
    main(modo)
