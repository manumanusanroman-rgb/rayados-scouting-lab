"""
process_squad.py
================
Procesa el CSV crudo scrapeado de Transfermarkt (data/raw/tm_squad__2407.csv)
y lo convierte al formato que la app espera (data/rayados_squad.csv).

Lo que hace:
- Lee datos REALES: nombre, edad, nacionalidad, valor de mercado
- Mapea posiciones TM (en espanol detallado) a categorias simplificadas
- Estima salario con un modelo basado en valor de mercado
- Deja stats deportivas vacias (las llenaremos con FotMob despues)

Ejecutar desde la raiz del proyecto:
    python process_squad.py
"""
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "tm_squad__2407.csv"
OUT_FILE = PROJECT_ROOT / "data" / "rayados_squad.csv"

# ---------------------------------------------------------------------------
# Mapeo de posiciones Transfermarkt -> categorias internas
# ---------------------------------------------------------------------------
POSITION_MAP = {
    # Porteros
    "Portero": "Portero",
    "Goalkeeper": "Portero",

    # Defensas centrales
    "Defensa central": "Defensa central",
    "Defensa - Central": "Defensa central",
    "Centre-Back": "Defensa central",

    # Laterales
    "Lateral derecho": "Lateral",
    "Lateral izquierdo": "Lateral",
    "Defensa - Lateral derecho": "Lateral",
    "Defensa - Lateral izquierdo": "Lateral",
    "Right-Back": "Lateral",
    "Left-Back": "Lateral",

    # Mediocentros
    "Pivote": "Mediocentro",
    "Mediocentro": "Mediocentro",
    "Mediocentro defensivo": "Mediocentro",
    "Mediocentro ofensivo": "Mediocentro",
    "Mediocampista": "Mediocentro",
    "Centrocampista": "Mediocentro",
    "Centrocampista ofensivo": "Mediocentro",
    "Centrocampista defensivo": "Mediocentro",
    "Central Midfield": "Mediocentro",
    "Defensive Midfield": "Mediocentro",
    "Attacking Midfield": "Mediocentro",

    # Extremos
    "Extremo izquierdo": "Extremo",
    "Extremo derecho": "Extremo",
    "Interior izquierdo": "Extremo",
    "Interior derecho": "Extremo",
    "Left Winger": "Extremo",
    "Right Winger": "Extremo",

    # Delanteros
    "Delantero": "Delantero",
    "Delantero centro": "Delantero",
    "Mediapunta": "Mediocentro",  # asumimos mediocentro ofensivo
    "Segundo delantero": "Delantero",
    "Centre-Forward": "Delantero",
    "Second Striker": "Delantero",
}


# Perfil natural por defecto segun posicion (sin stats, mejor que vacio)
DEFAULT_PROFILE = {
    "Portero": "Shot-stopper",
    "Defensa central": "Central dominante defensivo",
    "Lateral": "Lateral ofensivo",
    "Mediocentro": "Mediocentro mixto",
    "Extremo": "Extremo creativo",
    "Delantero": "Finalizador de area",
}


# Mapeo de nacionalidades a codigo de 3 letras
NATIONALITY_MAP = {
    "México": "MEX",
    "Argentina": "ARG",
    "Brasil": "BRA",
    "España": "ESP",
    "Colombia": "COL",
    "Uruguay": "URU",
    "Chile": "CHI",
    "Paraguay": "PAR",
    "Ecuador": "ECU",
    "Venezuela": "VEN",
    "Estados Unidos": "USA",
    "Perú": "PER",
    "Costa Rica": "CRC",
    "Honduras": "HON",
    "Panamá": "PAN",
    "Francia": "FRA",
    "Montenegro": "MNE",
    "Portugal": "POR",
    "Alemania": "GER",
    "Italia": "ITA",
    "Países Bajos": "NED",
    "Holanda": "NED",
    "Croacia": "CRO",
    "Serbia": "SRB",
    "Polonia": "POL",
    "Ucrania": "UKR",
    "Bélgica": "BEL",
    "Inglaterra": "ENG",
    "Escocia": "SCO",
    "Rusia": "RUS",
    "Senegal": "SEN",
    "Costa de Marfil": "CIV",
    "Nigeria": "NGA",
    "Ghana": "GHA",
    "Marruecos": "MAR",
    "Argelia": "ALG",
    "Japón": "JPN",
    "Corea del Sur": "KOR",
    "Australia": "AUS",
    "Canadá": "CAN",
    "Jamaica": "JAM",
}


def map_position(pos_tm: str) -> str:
    """Mapea posicion TM a categoria interna."""
    if not pos_tm or pd.isna(pos_tm):
        return "Mediocentro"
    pos_tm = str(pos_tm).strip()
    # match directo
    if pos_tm in POSITION_MAP:
        return POSITION_MAP[pos_tm]
    # match parcial (busca por palabras clave)
    pos_lower = pos_tm.lower()
    if "portero" in pos_lower or "goalkeeper" in pos_lower or pos_lower == "gk":
        return "Portero"
    if "central" in pos_lower or "centre-back" in pos_lower:
        return "Defensa central"
    if "lateral" in pos_lower or "back" in pos_lower:
        return "Lateral"
    if "extremo" in pos_lower or "winger" in pos_lower or "interior" in pos_lower:
        return "Extremo"
    if "delantero" in pos_lower or "forward" in pos_lower or "striker" in pos_lower:
        return "Delantero"
    if "medio" in pos_lower or "centrocamp" in pos_lower or "pivote" in pos_lower or "midfield" in pos_lower:
        return "Mediocentro"
    print(f"  [warn] posicion no reconocida: '{pos_tm}' -> Mediocentro por defecto")
    return "Mediocentro"


def estimate_salary(valor_mercado_meur: float, edad: int) -> float:
    """Estimacion grosera de salario anual en MEUR.

    Heuristica: 25-35% del valor de mercado anual, ajustado por edad.
    """
    if pd.isna(valor_mercado_meur) or valor_mercado_meur == 0:
        return 0.3   # salario minimo profesional
    base = valor_mercado_meur * 0.30
    # mayores de 30 cobran mas relativo a su valor (contratos largos)
    if edad and edad >= 30:
        base *= 1.20
    return round(base, 2)


def map_nationality(nat: str) -> str:
    """Convierte nombre completo a codigo 3 letras."""
    if not nat or pd.isna(nat):
        return "MEX"
    nat = str(nat).strip()
    if nat in NATIONALITY_MAP:
        return NATIONALITY_MAP[nat]
    # si ya viene como codigo de 3 letras, dejarlo
    if len(nat) == 3 and nat.isupper():
        return nat
    print(f"  [warn] nacionalidad no mapeada: '{nat}'")
    return nat[:3].upper()


def main():
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"No se encuentra {RAW_FILE}. Ejecuta primero el notebook "
            "01_tm_rayados_squad.ipynb para scrapear los datos."
        )

    print(f"Leyendo: {RAW_FILE.name}")
    raw = pd.read_csv(RAW_FILE)
    print(f"  {len(raw)} jugadores en el CSV crudo")

    # Construir el dataframe en el formato de la app
    rows = []
    for _, r in raw.iterrows():
        pos = map_position(r.get("posicion_tm"))
        nat = map_nationality(r.get("nacionalidad"))
        valor = float(r.get("valor_mercado_meur", 0) or 0)
        edad = int(r.get("edad", 0) or 0)

        row = {
            "jugador": r["jugador"],
            "posicion": pos,
            "perfil_natural": DEFAULT_PROFILE.get(pos, "Mediocentro mixto"),
            "edad": edad,
            "nacionalidad": nat,
            "minutos": 0,                       # se llenara con FotMob
            "salario_meur": estimate_salary(valor, edad),
            "valor_mercado_meur": valor,
            "contrato_hasta": 2027,             # estimado, TM lo trae pero no scrapeamos aun
        }
        # stats vacias por ahora
        for k in ["goles_90","xg_90","xa_90","tiros_90","pases_clave_90",
                   "regates_completados_90","carreras_progresivas_90",
                   "pases_completados_pct","pases_progresivos_90",
                   "entradas_90","intercepciones_90","recuperaciones_90",
                   "duelos_ganados_pct","duelos_aereos_ganados_pct","despejes_90",
                   "paradas_pct","paradas_90","centros_completados_pct",
                   "tiros_area_90","conversion_pct"]:
            row[k] = None
        rows.append(row)

    df = pd.DataFrame(rows)

    # Diagnostico
    print(f"\nResumen:")
    print(f"  Jugadores procesados: {len(df)}")
    print(f"  Distribucion posicion:")
    for pos, n in df["posicion"].value_counts().items():
        print(f"    {pos:20s}: {n}")
    print(f"  Edad media: {df['edad'].mean():.1f}")
    print(f"  Valor total: {df['valor_mercado_meur'].sum():.1f} ME")
    print(f"  Salario total estimado: {df['salario_meur'].sum():.1f} ME")
    print(f"  Nacionalidades: {df['nacionalidad'].value_counts().to_dict()}")

    # Backup del dummy anterior por si quieres comparar
    backup = OUT_FILE.with_suffix(".dummy_backup.csv")
    if OUT_FILE.exists() and not backup.exists():
        OUT_FILE.rename(backup)
        print(f"\n  [backup] dummy anterior guardado en {backup.name}")

    df.to_csv(OUT_FILE, index=False)
    print(f"\nGuardado: {OUT_FILE.name}")
    print(f"\nListo. Ya puedes lanzar la app y veras la plantilla REAL de Rayados.")
    print("  streamlit run app.py")


if __name__ == "__main__":
    main()
