"""
data_fetcher.py
===============
Scraping de Transfermarkt y FotMob para alimentar la herramienta.

Por que estas fuentes:
- FBref activo anti-bot agresivo en agosto 2025, libreria fbrefdata bloqueada.
- Transfermarkt: HTML scraping clasico. Plantillas, valor mercado, fichajes, lesiones.
- FotMob: API JSON interna no oficial. Stats avanzadas (xG, xA, etc.).

Disenado para ser ejecutado desde notebooks. NO desde la app.
La app lee los CSV resultantes de data/processed/.

Estrategia anti-baneo:
- User-Agent realista (Chrome reciente)
- Sleep minimo 5 segundos entre requests
- Cache local agresivo (no re-descargar si existe)
- Reintentos con backoff exponencial
"""
from __future__ import annotations
from pathlib import Path
import time
import json
import re
from typing import Optional
from dataclasses import dataclass

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)


# ============================================================================
# CONFIG ANTI-BANEO
# ============================================================================
SLEEP_SECONDS = 5

HEADERS_BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


# ============================================================================
# TRANSFERMARKT
# ============================================================================
TM_BASE = "https://www.transfermarkt.es"
CLUB_RAYADOS_TM_ID = 2407   # CF Monterrey Rayados (verificado)

# IDs de Transfermarkt para las 4 ligas (verificados)
TM_LEAGUES = {
    "Liga MX":            "MEX1",
    "Brasileirao":        "BRA1",
    "Primera Argentina":  "AR1N",
    "Segunda Espanola":   "ES2",
}


def fetch_tm_club_squad(club_id: int = CLUB_RAYADOS_TM_ID,
                          force_refresh: bool = False) -> pd.DataFrame:
    """
    Descarga la plantilla actual de un club de Transfermarkt.

    Returns
    -------
    DataFrame con columnas:
        jugador, dorsal, posicion_tm, fecha_nacimiento, edad,
        nacionalidad, altura_cm, pie, contrato_hasta, valor_mercado_meur,
        tm_player_id (para descargas posteriores)
    """
    cache_file = DATA_RAW / f"tm_squad__{club_id}.csv"
    if cache_file.exists() and not force_refresh:
        print(f"  [cache] {cache_file.name}")
        return pd.read_csv(cache_file)

    import requests
    from bs4 import BeautifulSoup

    # URL: /kader/verein/{id}/saison_id/{anio}/plus/1
    # 'plus/1' = vista detallada con todas las columnas (valor mercado, contrato, etc.)
    # 'saison_id': anio de la temporada actual. TM acepta cualquier int reciente.
    season_id = 2025
    url = f"{TM_BASE}/cf-monterrey/kader/verein/{club_id}/saison_id/{season_id}/plus/1"
    print(f"  [tm] GET {url}")
    r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
    print(f"      status: {r.status_code}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    # En /kader la tabla detallada tiene class 'items'.
    # Si TM cambio el HTML, probar varios selectores.
    table = (
        soup.find("table", {"class": "items"})
        or soup.find("div", {"id": "yw1"}) and soup.find("div", {"id": "yw1"}).find("table")
        or soup.select_one("div.responsive-table table")
    )
    if table is None:
        raise RuntimeError(
            "No se encontro tabla de plantilla en /kader. "
            "Guarda el HTML para inspeccion."
        )

    rows = []
    for tr in table.find("tbody").find_all("tr", recursive=False):
        try:
            parsed = _tm_parse_squad_row(tr)
            if parsed:
                rows.append(parsed)
        except Exception as e:
            print(f"    skip row: {type(e).__name__}: {e}")
            continue

    df = pd.DataFrame(rows)
    df.to_csv(cache_file, index=False)
    print(f"  [saved] {cache_file.name}  ({len(df)} jugadores)")
    time.sleep(SLEEP_SECONDS)
    return df


def _tm_parse_squad_row(tr) -> Optional[dict]:
    """
    Parsea una fila de la tabla de plantilla TM.

    El HTML de Transfermarkt usa una tabla anidada para cada jugador
    (foto + nombre + posicion). Esta funcion extrae los campos clave.
    """
    cells = tr.find_all("td", recursive=False)
    if len(cells) < 4:
        return None

    # ---- Dorsal (primera celda con clase rn_nummer) ----
    dorsal_tag = tr.find("div", {"class": "rn_nummer"})
    dorsal = dorsal_tag.get_text(strip=True) if dorsal_tag else ""

    # ---- Nombre del jugador (clase hauptlink) ----
    nombre_tag = tr.find("td", {"class": "hauptlink"})
    if not nombre_tag:
        return None
    a_nombre = nombre_tag.find("a")
    nombre = a_nombre.get_text(strip=True) if a_nombre else nombre_tag.get_text(strip=True)

    # ---- Player ID (de la URL del enlace) ----
    tm_player_id = None
    if a_nombre and a_nombre.get("href"):
        m = re.search(r"/spieler/(\d+)", a_nombre["href"])
        if m:
            tm_player_id = int(m.group(1))

    # ---- Posicion (varias estrategias, TM cambia el HTML a veces) ----
    posicion = ""
    # Estrategia 1: tabla anidada bajo el nombre
    nested = nombre_tag.find("table")
    if nested:
        trs_nested = nested.find_all("tr")
        if len(trs_nested) >= 2:
            posicion = trs_nested[1].get_text(strip=True)

    # Estrategia 2: celda inline tras el hauptlink (caso comun ahora)
    if not posicion:
        # buscar td hermano de hauptlink que contenga texto que no sea numero/fecha
        siblings = nombre_tag.find_next_siblings("td")
        for sib in siblings[:3]:
            txt = sib.get_text(strip=True)
            # filtrar fechas, edades sueltas y banderas
            if txt and not re.match(r"^\d{1,2}[/.-]", txt) and not txt.isdigit() and len(txt) > 3:
                # criterio: el texto debe parecer una posicion
                pos_keywords = ["Portero","Defensa","central","Lateral","Mediocentro",
                                "Mediocampista","Pivote","Mediapunta","Centrocampista",
                                "Interior","Extremo","Delantero","Mediocampo","ofensivo","defensivo"]
                if any(k.lower() in txt.lower() for k in pos_keywords):
                    posicion = txt
                    break

    # Estrategia 3: linea de posicion como ultimo recurso (busca en toda la fila)
    if not posicion:
        all_text = tr.get_text(" ", strip=True)
        pos_keywords_simple = ["Portero","Defensa central","Lateral derecho","Lateral izquierdo",
                                "Pivote","Mediocentro","Mediapunta","Extremo izquierdo",
                                "Extremo derecho","Delantero centro","Delantero","Interior derecho",
                                "Interior izquierdo","Mediocampista"]
        for kw in pos_keywords_simple:
            if kw in all_text:
                posicion = kw
                break

    # ---- Fecha de nacimiento + edad ----
    # Suele estar en una td "zentriert" tras el nombre.
    # Formato: "23 ene 2002 (23)"
    fecha_nac, edad = "", None
    for td in cells:
        txt = td.get_text(strip=True)
        m = re.match(r"(.+?)\s*\((\d{1,2})\)$", txt)
        if m:
            fecha_nac = m.group(1).strip()
            edad = int(m.group(2))
            break

    # ---- Nacionalidad (img con class flaggenrahmen) ----
    nacionalidades = [img.get("title", "") for img in tr.find_all("img", {"class": "flaggenrahmen"})]
    nacion_principal = nacionalidades[0] if nacionalidades else ""

    # ---- Valor de mercado (siempre ultima celda con clase rechts) ----
    valor_meur = 0.0
    valor_cells = tr.find_all("td", {"class": "rechts"})
    if valor_cells:
        valor_txt = valor_cells[-1].get_text(strip=True)
        # En plantilla actual el valor casi siempre tiene sufijo, pero por si acaso
        # un numero sin sufijo se trata como millones.
        valor_meur = _tm_parse_value(valor_txt, assume_millions_if_bare=True)

    return {
        "jugador": nombre,
        "tm_player_id": tm_player_id,
        "dorsal": dorsal,
        "posicion_tm": posicion,
        "fecha_nacimiento": fecha_nac,
        "edad": edad,
        "nacionalidad": nacion_principal,
        "valor_mercado_meur": valor_meur,
    }


def _tm_parse_value(text: str, assume_millions_if_bare: bool = False) -> float:
    """
    Convierte texto de TM a millones de euros.

    Parameters
    ----------
    text : str
        Texto a parsear ('5,50 mill. €', 'Libre', 'Fin de cesion...', etc.)
    assume_millions_if_bare : bool
        Si True, un numero sin sufijo (ej. '5,00') se asume como millones.
        Util para valor de mercado de plantilla donde TM a veces omite el sufijo.
        Si False (default para transfers), un numero sin sufijo se considera basura.

    Casos posibles (version espanola):
        '5,50 mill. €'             -> 5.5
        '750 mil €'                -> 0.75
        '-'                        -> 0.0
        ''                         -> 0.0
        'Libre'                    -> 0.0
        'Fin de cesion30/06/2023'  -> 0.0
        'Cesion'                   -> 0.0
    """
    if not text or text in ("-", "?"):
        return 0.0
    text_clean = text.replace("€", "").replace("\xa0", " ").strip()
    lower = text_clean.lower()

    # Casos sin coste monetario explicito
    no_money_keywords = [
        "libre", "free", "fin de cesion", "fin de cesión", "end of loan",
        "leihende", "cesion", "cesión", "loan", "préstamo", "prestamo",
        "sub.", "subido", "promovido", "promoted",
    ]
    if any(kw in lower for kw in no_money_keywords):
        return 0.0

    is_mill = "mill" in lower or "mio" in lower
    is_mil = ("mil" in lower and not is_mill)

    # Extraer el numero
    m = re.search(r"([\d.,]+)", text_clean)
    if not m:
        return 0.0
    num_str = m.group(1)
    if "," in num_str:
        num_str = num_str.replace(".", "").replace(",", ".")
    try:
        num = float(num_str)
    except ValueError:
        return 0.0

    if is_mill:
        return num
    if is_mil:
        return num / 1000
    # Sin sufijo: depende del contexto
    if assume_millions_if_bare:
        return num
    return 0.0


# ============================================================================
# UTILIDADES DE DEBUG
# ============================================================================
def save_debug_html(html: str, name: str = "debug_tm.html") -> Path:
    """Guarda HTML crudo para inspeccion cuando un parser falla."""
    path = DATA_RAW / name
    path.write_text(html, encoding="utf-8")
    print(f"  [debug] HTML guardado en {path}")
    return path


# ============================================================================
# TRANSFERMARKT - HISTORICO DE FICHAJES
# ============================================================================
def fetch_tm_transfers_single_season(
    club_id: int,
    season_id: int,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Descarga fichajes (entradas y salidas) de un club para una temporada.

    Parameters
    ----------
    club_id    : int  - ID del club en TM (Rayados = 2407)
    season_id  : int  - Año inicio temporada. 2017 = temporada 2017/18.
    force_refresh : bool - si True, ignora cache local

    Returns
    -------
    DataFrame con columnas:
        direccion (in/out), jugador, edad, nacionalidad, posicion_tm,
        club_relacionado (de donde viene o a donde va), liga_relacionada,
        coste_meur, season_id
    """
    cache_file = DATA_RAW / f"tm_transfers__{club_id}__{season_id}.csv"
    if cache_file.exists() and not force_refresh:
        print(f"  [cache] {cache_file.name}")
        return pd.read_csv(cache_file)

    import requests
    from bs4 import BeautifulSoup

    url = f"{TM_BASE}/cf-monterrey/transfers/verein/{club_id}/saison_id/{season_id}"
    print(f"  [tm] GET {url}")
    r = requests.get(url, headers=HEADERS_BROWSER, timeout=30)
    print(f"      status: {r.status_code}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # TM tiene 2 tablas (Llegadas, Salidas) dentro de divs con class 'responsive-table'
    # Las identificamos por encabezados cercanos
    rows = []

    # Estrategia: buscar todas las tablas 'items' (suele haber 2)
    tables = soup.find_all("table", {"class": "items"})
    if not tables:
        # Fallback: buscar dentro de responsive-table
        for div in soup.find_all("div", {"class": "responsive-table"}):
            t = div.find("table")
            if t:
                tables.append(t)

    if not tables:
        raise RuntimeError(
            f"No se encontraron tablas de transfers para season {season_id}. "
            "Guarda el HTML para inspeccion."
        )

    print(f"      [info] {len(tables)} tablas encontradas")

    # En TM la primera tabla es Llegadas (in), la segunda Salidas (out)
    # Verificamos por el heading anterior si existe, sino usamos el orden
    for idx, table in enumerate(tables):
        # Estrategia 1: detectar por heading
        direction = _tm_detect_direction(table)
        # Estrategia 2 (fallback): orden de aparicion
        if direction == "unknown":
            direction = "in" if idx == 0 else "out"
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr", recursive=False):
            parsed = _tm_parse_transfer_row(tr, direction, season_id)
            if parsed:
                rows.append(parsed)

    df = pd.DataFrame(rows)
    df.to_csv(cache_file, index=False)
    print(f"  [saved] {cache_file.name}  ({len(df)} fichajes)")
    time.sleep(SLEEP_SECONDS)
    return df


def fetch_tm_transfers_multi_seasons(
    club_id: int = CLUB_RAYADOS_TM_ID,
    seasons: Optional[list[int]] = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Descarga el histórico de fichajes de varias temporadas y los une.

    Default: últimas 8 temporadas (2017/18 a 2024/25).
    """
    if seasons is None:
        seasons = list(range(2017, 2025))   # 2017/18 a 2024/25

    all_dfs = []
    for s in seasons:
        print(f"\n=== Temporada {s}/{(s+1) % 100:02d} ===")
        try:
            df = fetch_tm_transfers_single_season(club_id, s, force_refresh)
            all_dfs.append(df)
        except Exception as e:
            print(f"  [error] {type(e).__name__}: {e}")
            continue

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    out_file = DATA_RAW / f"tm_transfers__{club_id}__ALL.csv"
    combined.to_csv(out_file, index=False)
    print(f"\n[saved combined] {out_file.name}  ({len(combined)} fichajes totales)")
    return combined


def _tm_detect_direction(table) -> str:
    """
    Determina si una tabla es de Llegadas o Salidas.
    Mira el h2/box-headline mas cercano hacia arriba en el HTML.
    """
    # buscar hermanos previos
    parent = table.find_parent("div", {"class": "box"})
    if parent:
        headline = parent.find(["h2", "div"], {"class": ["content-box-headline", "table-header"]})
        if headline:
            text = headline.get_text(strip=True).lower()
            if "llegad" in text or "incoming" in text or "in" in text.split():
                return "in"
            if "salid" in text or "outgoing" in text or "out" in text.split() or "abgang" in text:
                return "out"
    # fallback heuristico: el primer 'header' encontrado en el documento es Llegadas
    return "unknown"


def _tm_parse_transfer_row(tr, direction: str, season_id: int) -> Optional[dict]:
    """
    Parsea una fila de la tabla de fichajes.

    Columnas tipicas TM (Llegadas y Salidas):
    [0] num | [1] nombre+posicion | [2] edad | [3] nacionalidad
    [4] valor mercado | [5] de/a (club, liga) | [6] coste
    """
    cells = tr.find_all("td", recursive=False)
    if len(cells) < 4:
        return None

    # ---- Nombre del jugador ----
    nombre_tag = tr.find("td", {"class": "hauptlink"})
    if not nombre_tag:
        return None
    a_nombre = nombre_tag.find("a")
    nombre = a_nombre.get_text(strip=True) if a_nombre else nombre_tag.get_text(strip=True)
    if not nombre:
        return None

    # ---- Player ID ----
    tm_player_id = None
    if a_nombre and a_nombre.get("href"):
        m = re.search(r"/spieler/(\d+)", a_nombre["href"])
        if m:
            tm_player_id = int(m.group(1))

    # ---- Posicion (3 estrategias, TM cambia el HTML segun temporada) ----
    posicion = ""
    # Estrategia 1: tabla anidada bajo el nombre (caso clasico)
    nested = nombre_tag.find("table")
    if nested:
        rows_inner = nested.find_all("tr")
        if len(rows_inner) >= 2:
            posicion = rows_inner[1].get_text(strip=True)

    # Estrategia 2: linea de posicion como texto entero de la celda hauptlink
    # (algunas filas tienen "Nombre / Posicion" en una sola linea)
    if not posicion:
        full_text = nombre_tag.get_text(" ", strip=True)
        # quitar el nombre del jugador
        if a_nombre:
            full_text = full_text.replace(a_nombre.get_text(strip=True), "").strip()
        if full_text:
            # filtrar caracteres no informativos
            pos_keywords = ["Portero","Defensa","central","Lateral","Pivote","Mediocentro",
                            "Mediapunta","Centrocampista","Mediocampista","Interior","Extremo",
                            "Delantero","Mediocampo","Goalkeeper","Back","Midfield","Winger","Forward","Striker"]
            if any(k.lower() in full_text.lower() for k in pos_keywords):
                posicion = full_text

    # Estrategia 3: buscar texto que parezca posicion en cualquier celda
    if not posicion:
        all_text = tr.get_text(" ", strip=True)
        pos_keywords_simple = ["Portero","Defensa central","Lateral derecho","Lateral izquierdo",
                                "Pivote","Mediocentro","Mediapunta","Extremo izquierdo",
                                "Extremo derecho","Delantero centro","Delantero","Interior derecho",
                                "Interior izquierdo","Mediocampista","Centrocampista ofensivo",
                                "Centrocampista defensivo","Mediocampo ofensivo"]
        for kw in pos_keywords_simple:
            if kw in all_text:
                posicion = kw
                break

    # ---- Edad (suele estar en celda 'zentriert' tras el nombre) ----
    edad = None
    zentr_cells = tr.find_all("td", {"class": "zentriert"})
    # primera celda zentriert tras el nombre suele ser edad
    for c in zentr_cells:
        txt = c.get_text(strip=True)
        if txt.isdigit() and 14 <= int(txt) <= 45:
            edad = int(txt)
            break

    # ---- Nacionalidad ----
    nacion = ""
    nat_img = tr.find("img", {"class": "flaggenrahmen"})
    if nat_img:
        nacion = nat_img.get("title", "")

    # ---- Club relacionado (de donde viene o a donde va) ----
    # TM usa una segunda celda 'hauptlink' con el club destino/origen
    club_relacionado = ""
    liga_relacionada = ""
    haupt_cells = tr.find_all("td", {"class": "hauptlink"})
    if len(haupt_cells) >= 2:
        # la segunda es el club opuesto
        club_link = haupt_cells[1].find("a")
        club_relacionado = club_link.get_text(strip=True) if club_link else haupt_cells[1].get_text(strip=True)
        # la liga puede estar en una celda hermana
        # buscar img de bandera de pais (que no sea la primera, esa es la del jugador)
        flags = tr.find_all("img", {"class": "flaggenrahmen"})
        if len(flags) >= 2:
            liga_relacionada = flags[1].get("title", "")

    # ---- Coste/Valor del fichaje (suele estar en una celda 'rechts hauptlink') ----
    coste_meur = 0.0
    coste_text = ""
    # buscar celda con clase rechts y texto monetario
    rechts_cells = tr.find_all("td", {"class": "rechts"})
    if rechts_cells:
        coste_text = rechts_cells[-1].get_text(strip=True)
        coste_meur = _tm_parse_value(coste_text)

    return {
        "season_id": season_id,
        "direccion": direction,
        "jugador": nombre,
        "tm_player_id": tm_player_id,
        "edad": edad,
        "nacionalidad": nacion,
        "posicion_tm": posicion,
        "club_relacionado": club_relacionado,
        "liga_relacionada": liga_relacionada,
        "coste_meur": coste_meur,
        "coste_texto_original": coste_text,
    }
