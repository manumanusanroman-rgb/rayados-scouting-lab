"""
process_scouting_multi.py
==========================
Lee los CSVs de seasonstats de las 8 ligas y construye players_scouting.csv
con TODOS los jugadores con 500+ min jugados.

Lee tambien squad.json de cada liga para enriquecer con nombre completo,
nacionalidad real y posicion oficial.
"""
from pathlib import Path
import zipfile
import io
import json
import pandas as pd
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
ZIPS_DIR = Path(r"C:\Users\msanr\Datos\EVENTING_LIGAS")

MIN_MIN = 500   # filtro minimo de minutos

LIGAS_CONFIG = [
    ("testeo_ligas_norteamerica.zip", "testeo_ligas_norteamerica", "Mexico_Liga_MX", "2024-2025", "Liga MX"),
    ("testeo_ligas_norteamerica.zip", "testeo_ligas_norteamerica", "USA_MLS", "2025", "MLS"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Brazil_Serie_A", "2025", "Brasil A"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Brazil_Serie_B", "2025", "Brasil B"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Argentina_Liga_Profesional", "2024", "Argentina"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Chile_Primera_Division", "2024", "Chile"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Colombia_Primera_A", "2024", "Colombia"),
    ("testeo_ligas_sudamerica.zip", "testeo_ligas_sudamerica", "Ecuador_Liga_Pro", "2025", "Ecuador"),
]

NAT_MAP = {
    "Mexico": "MEX", "Argentina": "ARG", "Brazil": "BRA", "Brasil": "BRA",
    "Spain": "ESP", "Colombia": "COL", "Uruguay": "URU", "Chile": "CHI",
    "Paraguay": "PAR", "Ecuador": "ECU", "Venezuela": "VEN",
    "United States": "USA", "Peru": "PER", "Costa Rica": "CRC",
    "Honduras": "HON", "Panama": "PAN", "France": "FRA",
    "Portugal": "POR", "Germany": "GER", "Italy": "ITA",
    "Netherlands": "NED", "Croatia": "CRO", "Serbia": "SRB",
    "Senegal": "SEN", "Ghana": "GHA", "Nigeria": "NGA",
    "Morocco": "MAR", "Japan": "JPN", "South Korea": "KOR",
    "Canada": "CAN", "Jamaica": "JAM", "Bolivia": "BOL",
    "El Salvador": "SLV", "Guatemala": "GUA", "Curacao": "CUW",
    "England": "ENG", "Belgium": "BEL", "Switzerland": "SUI",
    "Poland": "POL", "Turkey": "TUR", "Australia": "AUS",
    "Montenegro": "MNE",
}


def norm(s):
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def nat_code(nat):
    if not nat:
        return ""
    return NAT_MAP.get(nat, nat[:3].upper())


def find_col(df, name_part):
    """Busca columna tolerante a espacios extras."""
    target = name_part.replace(" ", "").lower()
    for c in df.columns:
        if c.replace(" ", "").lower() == target:
            return c
    for c in df.columns:
        if target in c.replace(" ", "").lower():
            return c
    return None


def get_val(row, col, default=0):
    if col is None or col not in row.index:
        return default
    v = row[col]
    return default if pd.isna(v) else v


def map_position(opta_pos, row=None):
    if not opta_pos or pd.isna(opta_pos):
        return "Mediocentro"
    p = str(opta_pos).strip().lower()
    if "goalkeeper" in p:
        return "Portero"
    if "defender" in p or "defensa" in p:
        if row is not None:
            mins_col = find_col(pd.DataFrame([row]), "Time Played")
            cruces_ok = get_val(row, find_col(pd.DataFrame([row]), "Successful Crosses open play"), 0)
            cruces_ko = get_val(row, find_col(pd.DataFrame([row]), "Unsuccessful Crosses open play"), 0)
            mins_v = get_val(row, mins_col, 1) or 1
            total_cruces = cruces_ok + cruces_ko
            if mins_v > 0 and (total_cruces / mins_v * 90) >= 0.3:
                return "Lateral"
        return "Defensa central"
    if "forward" in p or "striker" in p:
        return "Delantero"
    if "midfielder" in p:
        return "Mediocentro"
    return "Mediocentro"


def estimate_salary(posicion, minutos, goles_90=0, asist_90=0):
    base = {"Portero": 0.4, "Defensa central": 0.5, "Lateral": 0.5,
            "Mediocentro": 0.6, "Extremo": 0.7, "Delantero": 0.8}.get(posicion, 0.5)
    if minutos >= 2000:
        mult = 1.5
    elif minutos >= 1500:
        mult = 1.2
    elif minutos >= 1000:
        mult = 1.0
    else:
        mult = 0.7
    bonus = (goles_90 + asist_90) * 0.3
    est = base * mult + bonus
    return round(est * 0.8, 2), round(est * 1.3, 2)


def per90(value, mins):
    if pd.isna(value) or pd.isna(mins) or mins == 0:
        return 0.0
    return round(float(value) / float(mins) * 90, 2)


def safe_div(num, den):
    if pd.isna(num) or pd.isna(den) or den == 0:
        return 0.0
    return round(float(num) / float(den) * 100, 1)


def load_squad_lookup(zf, root, liga, temp):
    """Lee squad.json de TODOS los equipos de una liga, devuelve dict por player_id."""
    prefix = f"{root}/{liga}/{temp}/equipos/"
    squad_files = [n for n in zf.namelist()
                   if n.startswith(prefix) and n.endswith("/jsons/squad.json")]
    lookup = {}
    for path in squad_files:
        try:
            data = json.loads(zf.read(path))
            for team_block in data.get("squad", []):
                for person in team_block.get("person", []):
                    if person.get("type") != "player":
                        continue
                    pid = person.get("id")
                    if not pid:
                        continue
                    fn = person.get("firstName", "")
                    ln = person.get("lastName", "")
                    known = person.get("knownName")
                    full_name = known if known else f"{fn} {ln}".strip()
                    lookup[pid] = {
                        "full_name": full_name,
                        "match_name": person.get("matchName", ""),
                        "nationality": nat_code(person.get("nationality", "")),
                        "nationality_name": person.get("nationality", ""),
                        "second_nationality": nat_code(person.get("secondNationality", "")),
                        "shirt_number": person.get("shirtNumber"),
                        "place_of_birth": person.get("placeOfBirth", ""),
                        "active": person.get("active", "yes"),
                    }
        except Exception:
            pass
    return lookup


def process_liga(zf, root, liga, temp, liga_display):
    """Procesa una liga: lee CSVs por equipo, genera filas con stats por 90."""
    prefix = f"{root}/{liga}/{temp}/equipos/"
    csvs = [n for n in zf.namelist()
            if n.startswith(prefix) and n.endswith("_jugadores_seasonstats.csv")]

    if not csvs:
        print(f"  [SKIP] {liga_display} {temp}: 0 CSVs")
        return []

    # cargar squad.json lookup
    squad_lookup = load_squad_lookup(zf, root, liga, temp)
    print(f"  squad.json: {len(squad_lookup)} jugadores")

    all_rows = []
    for csv_path in csvs:
        try:
            raw = zf.read(csv_path)
            df = pd.read_csv(io.BytesIO(raw))
        except Exception:
            continue

        time_col = find_col(df, "Time Played")
        if time_col is None:
            continue

        # filtrar minutos suficientes
        df_active = df[df[time_col].fillna(0) >= MIN_MIN]
        if df_active.empty:
            continue

        equipo_col = find_col(df, "equipo")
        nombre_col = find_col(df, "nombre")
        pos_col = find_col(df, "posicion")
        id_col = find_col(df, "id")

        for _, row in df_active.iterrows():
            mins = get_val(row, time_col, 0)
            pid = get_val(row, id_col, "")
            nombre = str(get_val(row, nombre_col, "")).strip()
            equipo = str(get_val(row, equipo_col, "")).strip()
            posicion = map_position(get_val(row, pos_col, None), row)

            goles = get_val(row, find_col(df, "Goals"), 0)
            asist = get_val(row, find_col(df, "Goal Assists"), 0)
            tiros = get_val(row, find_col(df, "Total Shots"), 0)
            pases_clave = get_val(row, find_col(df, "Key Passes"), 0)
            regates_ok = get_val(row, find_col(df, "Successful Dribbles"), 0)
            pases_ok = get_val(row, find_col(df, "Total Successful Passes"), 0)
            pases_ko = get_val(row, find_col(df, "Total Unsuccessful Passes"), 0)
            duelos_ok = get_val(row, find_col(df, "Duels won"), 0)
            duelos_ko = get_val(row, find_col(df, "Duels lost"), 0)
            duelos_aereos_ok = get_val(row, find_col(df, "Aerial Duels won"), 0)
            duelos_aereos_ko = get_val(row, find_col(df, "Aerial Duels lost"), 0)
            entradas_ok = get_val(row, find_col(df, "Tackles Won"), 0)
            intercepciones = get_val(row, find_col(df, "Interceptions"), 0)
            recuperaciones = get_val(row, find_col(df, "Recoveries"), 0)
            despejes = get_val(row, find_col(df, "Total Clearances"), 0)
            paradas = get_val(row, find_col(df, "Saves Made"), 0)
            goles_conc = get_val(row, find_col(df, "Goals Conceded"), 0)

            goles90 = per90(goles, mins)
            asist90 = per90(asist, mins)
            sal_min, sal_max = estimate_salary(posicion, int(mins), goles90, asist90)

            # enriquecer desde squad.json
            sq = squad_lookup.get(pid, {})

            all_rows.append({
                "player_id": pid,
                "nombre": nombre,
                "nombre_completo": sq.get("full_name", nombre),
                "jugador": nombre,
                "club": equipo,
                "equipo": equipo,
                "liga": liga_display,
                "posicion": posicion,
                "perfil_natural": posicion,
                "edad": 26,    # placeholder
                "nacionalidad": sq.get("nationality", "") or "—",
                "nacionalidad_nombre": sq.get("nationality_name", ""),
                "segunda_nacionalidad": sq.get("second_nationality", ""),
                "lugar_nacimiento": sq.get("place_of_birth", ""),
                "dorsal_opta": sq.get("shirt_number") if sq.get("shirt_number") is not None else "",
                "activo_en_club": sq.get("active", ""),
                "minutos": int(mins),
                "salario_meur": round((sal_min + sal_max) / 2, 2),
                "salario_min_meur": sal_min,
                "salario_max_meur": sal_max,
                "valor_mercado_meur": 0,
                "contrato_hasta": 2027,
                # metricas /90
                "goles_90": goles90,
                "xg_90": 0,
                "xa_90": 0,
                "tiros_90": per90(tiros, mins),
                "asistencias_90": asist90,
                "pases_clave_90": per90(pases_clave, mins),
                "regates_completados_90": per90(regates_ok, mins),
                "carreras_progresivas_90": per90(get_val(row, find_col(df, "Forward Passes"), 0), mins),
                "pases_completados_pct": safe_div(pases_ok, pases_ok + pases_ko),
                "pases_progresivos_90": per90(get_val(row, find_col(df, "Forward Passes"), 0), mins),
                "entradas_90": per90(entradas_ok, mins),
                "intercepciones_90": per90(intercepciones, mins),
                "recuperaciones_90": per90(recuperaciones, mins),
                "duelos_ganados_pct": safe_div(duelos_ok, duelos_ok + duelos_ko),
                "duelos_aereos_ganados_pct": safe_div(duelos_aereos_ok, duelos_aereos_ok + duelos_aereos_ko),
                "despejes_90": per90(despejes, mins),
                "paradas_pct": safe_div(paradas, paradas + goles_conc),
                "paradas_90": per90(paradas, mins),
                "centros_completados_pct": 0,
                "tiros_area_90": 0,
                "conversion_pct": safe_div(goles, tiros),
            })

    return all_rows


def main():
    print("=" * 70)
    print("POOL DE SCOUTING MULTI-LIGA")
    print("=" * 70)

    all_rows = []
    zip_handles = {}

    try:
        for cfg in LIGAS_CONFIG:
            zip_name, root, liga, temp, liga_display = cfg
            zip_path = ZIPS_DIR / zip_name
            if not zip_path.exists():
                print(f"\n[SKIP] {liga_display}: no encuentro {zip_name}")
                continue
            if zip_name not in zip_handles:
                print(f"\n[ZIP] Abriendo {zip_name}...")
                zip_handles[zip_name] = zipfile.ZipFile(zip_path, "r")
            zf = zip_handles[zip_name]
            print(f"\n>>> {liga_display} ({temp})...")
            rows = process_liga(zf, root, liga, temp, liga_display)
            all_rows.extend(rows)
            print(f"  Anadidos {len(rows)} jugadores con {MIN_MIN}+ min")
    finally:
        for zf in zip_handles.values():
            zf.close()

    df = pd.DataFrame(all_rows)

    # excluir Rayados (no scouteamos a nuestros)
    df_no_rayados = df[~df["equipo"].str.contains("Monterrey", case=False, na=False)]
    print(f"\nTotal jugadores: {len(df_no_rayados)} (excluyendo Rayados)")

    output_path = DATA_DIR / "players_scouting.csv"
    df_no_rayados.to_csv(output_path, index=False)
    print(f"Guardado: {output_path}")

    print(f"\nDistribucion por liga:")
    print(df_no_rayados["liga"].value_counts().to_string())
    print(f"\nDistribucion por posicion:")
    print(df_no_rayados["posicion"].value_counts().to_string())


if __name__ == "__main__":
    main()