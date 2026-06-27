"""
process_opta_liga_mx.py
=======================
Procesa los datos Opta de Liga MX 2024-25 desde el ZIP de eventing.

Genera 3 CSVs que reemplazan dummys de la app:
  1) data/rayados_squad.csv       - plantilla actual con stats REALES
  2) data/players_scouting.csv    - pool de candidatos Liga MX (~400 jugadores con 500+ min)
  3) data/teams_benchmark.csv     - benchmark equipos: Rayados, America, Toluca

NIVEL 4 del plan.

Ejecutar desde la raiz del proyecto:
    python process_opta_liga_mx.py
"""
from pathlib import Path
import zipfile
import io
import pandas as pd
import numpy as np
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parent
ZIP_PATH = Path(r"C:\Users\msanr\Datos\EVENTING_LIGAS\testeo_ligas_norteamerica.zip")
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

SEASON = "2024-2025"
MIN_MINUTES_POOL = 500   # filtro pool scouting

# Equipos benchmark (carpetas como vienen en el ZIP)
EQUIPOS_BENCHMARK = {
    "CF_Monterrey": "Rayados",
    "CF_América": "America",
    "Deportivo_Toluca_FC": "Toluca",
}


# ============================================================================
# 1. UTILIDADES
# ============================================================================
def norm(s):
    """Quita acentos, lowercase, strip - para matching de nombres."""
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def list_team_csvs(zf: zipfile.ZipFile, season: str = SEASON) -> list[tuple[str, str]]:
    """Devuelve [(equipo_carpeta, path_dentro_zip)] para CSVs seasonstats."""
    prefix = f"testeo_ligas_norteamerica/Mexico_Liga_MX/{season}/equipos/"
    out = []
    for n in zf.namelist():
        if n.startswith(prefix) and n.endswith("_jugadores_seasonstats.csv"):
            parts = n[len(prefix):].split("/")
            if len(parts) >= 2:
                team = parts[0]
                out.append((team, n))
    return out


def read_team_csv(zf: zipfile.ZipFile, path: str) -> pd.DataFrame:
    """Lee un CSV de jugadores-stats desde el ZIP."""
    raw = zf.read(path)
    return pd.read_csv(io.BytesIO(raw))


def per_90(value, mins):
    """Convierte total a por 90 minutos. Acepta NaN, 0, etc."""
    if pd.isna(value) or pd.isna(mins) or mins == 0:
        return 0.0
    return round(float(value) / float(mins) * 90, 2)


def safe_div(num, den):
    """Division segura: 0 si denominator es 0 o NaN."""
    if pd.isna(num) or pd.isna(den) or den == 0:
        return 0.0
    return round(float(num) / float(den) * 100, 1)


def get(row, col, default=0):
    """Lee columna con default si no existe o es NaN."""
    if col not in row.index:
        return default
    v = row[col]
    return default if pd.isna(v) else v


# ============================================================================
# 2. MAPEO POSICION OPTA -> CATEGORIA INTERNA
# ============================================================================
def map_position(opta_pos: str, row=None) -> tuple[str, str]:
    """
    Mapea posicion Opta (Forward/Midfielder/Defender/Goalkeeper) a categoria
    interna mas fina usando heuristica de stats.

    Devuelve: (posicion, perfil_natural_default)
    """
    if not opta_pos or pd.isna(opta_pos):
        return "Mediocentro", "Mediocentro mixto"
    p = str(opta_pos).strip().lower()

    if "goalkeeper" in p or "portero" in p:
        return "Portero", "Shot-stopper"

    if "defender" in p or "defensa" in p:
        # heuristica: si tiene cualquier centro completado o lo intento varias veces
        # -> lateral. Los centrales puros nunca centran.
        if row is not None:
            mins = get(row, "Time Played", 1) or 1
            cruces_ok = get(row, "Successful Crosses open play", 0)
            cruces_ko = get(row, "Unsuccessful Crosses open play", 0)
            total_cruces = cruces_ok + cruces_ko
            # umbral muy bajo: 0.3 centros/90 (1 centro cada 3 partidos = lateral)
            if mins > 0 and (total_cruces / mins * 90) >= 0.3:
                return "Lateral", "Lateral ofensivo"
            # alternativa: tackles altos suelen ser laterales que cubren banda
            entradas = get(row, "Total Tackles", 0)
            if mins > 0 and (entradas / mins * 90) >= 3.0:
                # podria ser lateral defensivo o pivote - depender de pases clave
                pases_clave = get(row, "Key Passes (Attempt Assists)", 0)
                if (pases_clave / mins * 90) >= 0.3:
                    return "Lateral", "Lateral ofensivo"
        return "Defensa central", "Central dominante defensivo"

    if "forward" in p or "delantero" in p:
        if row is not None:
            cruces = get(row, "Successful Crosses & Corners", 0)
            regates = get(row, "Successful Dribbles", 0)
            mins = get(row, "Time Played", 1)
            # si centra mucho + regatea -> extremo
            if mins > 0 and (cruces / mins * 90 > 0.8 or regates / mins * 90 > 1.2):
                return "Extremo", "Extremo creativo"
        return "Delantero", "Finalizador de area"

    if "midfielder" in p or "medi" in p:
        if row is not None:
            mins = get(row, "Time Played", 1)
            if mins > 0:
                pases_clave = get(row, "Key Passes (Attempt Assists)", 0)
                recuperaciones = get(row, "Recoveries", 0)
                cruces = get(row, "Successful Crosses & Corners", 0)
                # extremo si centra mucho o pases clave altos
                if (cruces / mins * 90) > 1.0:
                    return "Extremo", "Extremo creativo"
                if (pases_clave / mins * 90) > 1.5:
                    return "Mediocentro", "Mediocentro organizador"
                if (recuperaciones / mins * 90) > 4.0:
                    return "Mediocentro", "Pivote defensivo"
        return "Mediocentro", "Mediocentro mixto"

    return "Mediocentro", "Mediocentro mixto"


# ============================================================================
# 3. MAPEO STATS OPTA -> METRICAS APP
# ============================================================================
def estimate_salary_meur(posicion: str, minutos: int, goles_90: float, asist_90: float) -> tuple[float, float]:
    """
    Estima rango salarial anual en MEUR basado en posicion + rendimiento.
    Esto es un PLACEHOLDER hasta integrar datos reales de Capology/TM.

    Returns (sal_min, sal_max).
    """
    # base por posicion (Liga MX promedio)
    base_por_pos = {
        "Portero": 0.4,
        "Defensa central": 0.5,
        "Lateral": 0.5,
        "Mediocentro": 0.6,
        "Extremo": 0.7,
        "Delantero": 0.8,
    }
    base = base_por_pos.get(posicion, 0.5)

    # multiplicador por minutos (mas minutos = jugador mas valioso)
    if minutos >= 2000:
        mult_mins = 1.5
    elif minutos >= 1500:
        mult_mins = 1.2
    elif minutos >= 1000:
        mult_mins = 1.0
    else:
        mult_mins = 0.7

    # bonus por produccion (goles + asistencias)
    bonus = (goles_90 + asist_90) * 0.3   # cada 1 G+A/90 = 0.3 MEUR

    estimacion = base * mult_mins + bonus
    return round(estimacion * 0.8, 2), round(estimacion * 1.3, 2)


def build_player_row(row: pd.Series) -> dict:
    """
    Construye una fila en el formato que la app espera, a partir de stats Opta.
    Todas las metricas son por 90 minutos.
    """
    mins = get(row, "Time Played", 0)
    posicion, perfil = map_position(get(row, "posicion", None), row)

    # totales
    goles = get(row, "Goals", 0)
    asist = get(row, "Goal Assists", 0)
    tiros = get(row, "Total Shots", 0)
    tiros_area = get(row, "Total Touches In Opposition Box", 0)
    pases_clave = get(row, "Key Passes (Attempt Assists)", 0)
    regates_ok = get(row, "Successful Dribbles", 0)
    regates_ko = get(row, "Unsuccessful Dribbles", 0)
    pases_ok = get(row, "Total Successful Passes ( Excl Crosses & Corners )", 0)
    pases_ko = get(row, "Total Unsuccessful Passes ( Excl Crosses & Corners )", 0)
    pases_largos_ok = get(row, "Successful Long Passes", 0)
    pases_largos_ko = get(row, "Unsuccessful Long Passes", 0)
    pases_progresivos = get(row, "Forward Passes", 0)
    entradas_ok = get(row, "Tackles Won", 0)
    intercepciones = get(row, "Interceptions", 0)
    recuperaciones = get(row, "Recoveries", 0)
    duelos_ok = get(row, "Duels won", 0)
    duelos_ko = get(row, "Duels lost", 0)
    duelos_aereos_ok = get(row, "Aerial Duels won", 0)
    duelos_aereos_ko = get(row, "Aerial Duels lost", 0)
    despejes = get(row, "Total Clearances", 0)
    cruces_ok = get(row, "Successful Crosses open play", 0)
    cruces_ko = get(row, "Unsuccessful Crosses open play", 0)
    paradas = get(row, "Saves Made", 0)
    goles_concedidos = get(row, "Goals Conceded", 0)

    # metricas calculadas
    goles90 = per_90(goles, mins)
    asist90 = per_90(asist, mins)
    sal_min, sal_max = estimate_salary_meur(posicion, int(mins), goles90, asist90)

    return {
        "nombre": str(get(row, "nombre", "")).strip(),
        "jugador": str(get(row, "nombre", "")).strip(),    # alias por compat
        "club": str(get(row, "equipo", "")).strip(),
        "equipo": str(get(row, "equipo", "")).strip(),     # alias por compat
        "liga": "Liga MX",                      # todos los del pool actual
        "posicion": posicion,
        "perfil_natural": perfil,
        "edad": 26,                             # placeholder mediana (Opta no trae edad)
        "nacionalidad": "MEX",                  # default Liga MX
        "minutos": int(mins),
        "salario_meur": round((sal_min + sal_max) / 2, 2),
        "salario_min_meur": sal_min,
        "salario_max_meur": sal_max,
        "valor_mercado_meur": 0,                # se completa con TM despues
        "contrato_hasta": 2027,                 # default
        # ofensivas
        "goles_90": goles90,
        "xg_90": 0,                             # no calculamos xG aproximado (decision)
        "xa_90": 0,                             # no calculamos xA aproximado
        "tiros_90": per_90(tiros, mins),
        "asistencias_90": asist90,
        "pases_clave_90": per_90(pases_clave, mins),
        "regates_completados_90": per_90(regates_ok, mins),
        "carreras_progresivas_90": per_90(pases_progresivos, mins),
        # distribucion
        "pases_completados_pct": safe_div(pases_ok, pases_ok + pases_ko),
        "pases_progresivos_90": per_90(pases_progresivos, mins),
        # defensivas
        "entradas_90": per_90(entradas_ok, mins),
        "intercepciones_90": per_90(intercepciones, mins),
        "recuperaciones_90": per_90(recuperaciones, mins),
        "duelos_ganados_pct": safe_div(duelos_ok, duelos_ok + duelos_ko),
        "duelos_aereos_ganados_pct": safe_div(duelos_aereos_ok, duelos_aereos_ok + duelos_aereos_ko),
        "despejes_90": per_90(despejes, mins),
        # portero
        "paradas_pct": safe_div(paradas, paradas + goles_concedidos),
        "paradas_90": per_90(paradas, mins),
        # creacion
        "centros_completados_pct": safe_div(cruces_ok, cruces_ok + cruces_ko),
        "tiros_area_90": per_90(tiros_area, mins),
        "conversion_pct": safe_div(goles, tiros),
    }


# ============================================================================
# 4. PROCESAMIENTO PRINCIPAL
# ============================================================================
def process_team(zf, team_folder, team_path) -> pd.DataFrame:
    """Procesa los jugadores de un equipo."""
    print(f"  -> {team_folder}")
    df = read_team_csv(zf, team_path)
    if df.empty:
        return pd.DataFrame()
    # filtrar jugadores con al menos 1 minuto
    df = df[df["Time Played"].fillna(0) > 0]
    rows = [build_player_row(r) for _, r in df.iterrows()]
    return pd.DataFrame(rows)


def aggregate_team_from_raw(raw_df: pd.DataFrame, team_name: str) -> dict:
    """
    Genera benchmark del equipo SUMANDO totales de todos sus jugadores
    desde el CSV crudo y dividiendo por el numero de partidos jugados.

    Logica: si suma minutos / 11 = total partidos del equipo (en 90's),
    entonces goles_equipo / partidos = goles por 90 del equipo.
    """
    if raw_df.empty:
        return {}
    # filtrar solo jugadores con tiempo jugado
    df = raw_df[raw_df["Time Played"].fillna(0) > 0].copy()
    if df.empty:
        return {}

    total_mins = df["Time Played"].sum()
    # 11 jugadores en cancha simultaneamente -> dividir total_mins por 11
    # da el equivalente a "minutos de equipo en cancha"
    # Y eso / 90 = partidos jugados
    team_90s = total_mins / 11 / 90   # partidos equivalentes
    if team_90s == 0:
        return {}

    # Buscar columnas con tolerancia a espacios extras
    def find_col(name_part):
        """Busca columna que contenga name_part, ignorando espacios."""
        target = name_part.replace(" ", "").lower()
        for c in df.columns:
            if c.replace(" ", "").lower() == target:
                return c
        # match parcial
        for c in df.columns:
            if target in c.replace(" ", "").lower():
                return c
        return None

    def sum_col(name_part):
        c = find_col(name_part)
        if c is None: return 0
        return df[c].fillna(0).sum()

    def per_team_90(name_part):
        return round(sum_col(name_part) / team_90s, 2) if team_90s > 0 else 0

    def pct(num_part, *den_parts):
        num = sum_col(num_part)
        den = sum(sum_col(p) for p in den_parts)
        return round(num / den * 100, 1) if den > 0 else 0

    return {
        "equipo": team_name,
        "partidos_equivalentes": round(team_90s, 1),
        "goles_90": per_team_90("Goals"),
        "goles_concedidos_90": per_team_90("Goals Conceded"),
        "tiros_90": per_team_90("Total Shots"),
        "tiros_concedidos_90": 0,    # no calculable sin datos del rival - placeholder
        "tiros_puerta_90": per_team_90("Shots On Target"),
        "xg_90": 0,                  # placeholder (Fase C: modelo xG propio)
        "xga_90": 0,                 # placeholder
        "xa_90": 0,                  # placeholder
        "posesion": 0,               # placeholder (no en agregados Opta)
        "pases_clave_90": per_team_90("Key Passes (Attempt Assists)"),
        "pases_completados_pct": pct(
            "Total Successful Passes",
            "Total Successful Passes",
            "Total Unsuccessful Passes"
        ),
        "duelos_ganados_pct": pct("Duels won", "Duels won", "Duels lost"),
        "duelos_aereos_ganados_pct": pct("Aerial Duels won", "Aerial Duels won", "Aerial Duels lost"),
        "intercepciones_90": per_team_90("Interceptions"),
        "recuperaciones_90": per_team_90("Recoveries"),
        "regates_completados_90": per_team_90("Successful Dribbles"),
        "entradas_90": per_team_90("Tackles Won"),
        "despejes_90": per_team_90("Total Clearances"),
    }


def main():
    print("=" * 70)
    print("PROCESAMIENTO OPTA - LIGA MX 2024-25 (Nivel 4)")
    print("=" * 70)

    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"No encuentro {ZIP_PATH}")

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        team_csvs = list_team_csvs(zf)
        print(f"\nEncontrados {len(team_csvs)} equipos en Liga MX {SEASON}\n")

        all_dfs = {}        # DFs procesados (player rows en formato app)
        all_raw_dfs = {}    # DFs crudos (para benchmarks de equipo)
        print("Procesando cada equipo:")
        for team, path in team_csvs:
            raw = read_team_csv(zf, path)
            all_raw_dfs[team] = raw
            # filtrar y procesar
            raw_active = raw[raw["Time Played"].fillna(0) > 0]
            if raw_active.empty:
                all_dfs[team] = pd.DataFrame()
                continue
            rows = [build_player_row(r) for _, r in raw_active.iterrows()]
            all_dfs[team] = pd.DataFrame(rows)
            print(f"  -> {team}")

    # -----------------------------------------------------------------
    # OUTPUT 1: PLANTILLA RAYADOS ACTUAL (con stats reales)
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("OUTPUT 1: rayados_squad.csv")
    print("=" * 70)
    rayados_df = all_dfs.get("CF_Monterrey", pd.DataFrame())
    if rayados_df.empty:
        print("  [WARN] no encuentro CF_Monterrey")
    else:
        # cargar plantilla scrapeada de TM para hacer merge con edad/valor mercado
        tm_squad_path = DATA_DIR / "raw" / "tm_squad__2407.csv"
        if tm_squad_path.exists():
            tm = pd.read_csv(tm_squad_path)
            tm["nombre_norm"] = tm["jugador"].apply(norm)
            rayados_df["nombre_norm"] = rayados_df["jugador"].apply(norm)
            # match parcial: buscar "aguirre" en "erick aguirre"
            def best_match(opta_name):
                if not opta_name: return None
                # exact match
                exact = tm[tm["nombre_norm"] == opta_name]
                if not exact.empty: return exact.iloc[0]
                # partial: usa apellido (ultima palabra)
                last_word = opta_name.split()[-1] if opta_name else ""
                if last_word:
                    partial = tm[tm["nombre_norm"].str.contains(last_word, na=False)]
                    if not partial.empty: return partial.iloc[0]
                return None
            # asegurar que columnas son float (no int) para evitar FutureWarning
            for col in ["edad", "valor_mercado_meur"]:
                if col in rayados_df.columns:
                    rayados_df[col] = rayados_df[col].astype(float)
            for idx, row in rayados_df.iterrows():
                m = best_match(row["nombre_norm"])
                if m is not None:
                    rayados_df.at[idx, "edad"] = float(m.get("edad", 0))
                    rayados_df.at[idx, "valor_mercado_meur"] = float(m.get("valor_mercado_meur", 0))
                    rayados_df.at[idx, "nacionalidad"] = str(m.get("nacionalidad", "MEX"))[:3].upper()
            rayados_df = rayados_df.drop(columns=["nombre_norm"])
            print(f"  Merge con TM: completado")

        rayados_df.to_csv(DATA_DIR / "rayados_squad.csv", index=False)
        print(f"  Guardado: {len(rayados_df)} jugadores")
        print(f"\n  TOP scorers Rayados:")
        top = rayados_df.nlargest(5, "goles_90")[["jugador","posicion","minutos","goles_90","pases_clave_90"]]
        print(top.to_string(index=False))

    # -----------------------------------------------------------------
    # OUTPUT 2: POOL SCOUTING - TODA LIGA MX (con filtro de minutos)
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("OUTPUT 2: players_scouting.csv")
    print("=" * 70)
    pool = pd.concat([df for df in all_dfs.values() if not df.empty], ignore_index=True)
    print(f"  Total jugadores antes de filtro: {len(pool)}")
    pool_filtrado = pool[pool["minutos"] >= MIN_MINUTES_POOL].copy()
    print(f"  Despues de filtro {MIN_MINUTES_POOL}+ min: {len(pool_filtrado)}")

    # excluir jugadores Rayados del pool (no quieres scoutear a tus propios)
    pool_filtrado = pool_filtrado[pool_filtrado["equipo"] != "CF Monterrey"]
    print(f"  Excluyendo plantilla Rayados: {len(pool_filtrado)}")

    pool_filtrado.to_csv(DATA_DIR / "players_scouting.csv", index=False)
    print(f"\n  Distribucion por posicion:")
    print(pool_filtrado["posicion"].value_counts().to_string())

    # -----------------------------------------------------------------
    # OUTPUT 3: BENCHMARK EQUIPOS (Rayados + America + Toluca)
    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("OUTPUT 3: teams_benchmark.csv")
    print("=" * 70)
    benchmark_rows = []
    for folder, display_name in EQUIPOS_BENCHMARK.items():
        raw_df = all_raw_dfs.get(folder, pd.DataFrame())
        if raw_df.empty:
            print(f"  [WARN] no datos para {folder}")
            continue
        agg = aggregate_team_from_raw(raw_df, display_name)
        if agg:
            benchmark_rows.append(agg)
            print(f"  {display_name}: {agg.get('goles_90', 0):.2f} goles/90, "
                  f"{agg.get('pases_completados_pct', 0):.1f}% pases ok, "
                  f"{agg.get('duelos_ganados_pct', 0):.1f}% duelos")

    if benchmark_rows:
        bm_df = pd.DataFrame(benchmark_rows)
        bm_df.to_csv(DATA_DIR / "teams_benchmark.csv", index=False)
        print(f"\n  Guardado: {len(bm_df)} equipos en benchmark")

    print("\n" + "=" * 70)
    print("LISTO. Recarga la app: streamlit run app.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
