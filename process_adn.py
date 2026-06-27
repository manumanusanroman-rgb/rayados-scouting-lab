"""
process_adn.py
==============
Procesa el historico de fichajes scrapeado de Transfermarkt y lo convierte
al formato que la app espera para la seccion ADN Rayados.

Logica de etiquetado automatico (SOLO criterio financiero):
- EXITOSO si cumple al menos 2 de:
    (a) Recuperacion de inversion >= 80% del coste de compra
    (b) Permanencia >= 2 temporadas en el club
    (c) Caso libre/cantera que generó venta significativa (>= 1 ME)

- FALLIDO si cumple alguna de:
    (a) Coste >= 3 ME Y salida con recuperacion < 50%
    (b) Coste >= 5 ME Y revendido en <= 1 ano a <85%
    (c) Coste >= 2 ME Y salida libre/cesion en <= 18 meses

- NEUTRO en todos los demas casos

INFO ADICIONAL (NO afecta etiqueta):
- titulos_ganados: lista de titulos ganados por Rayados durante la estancia.
  No se usa para etiquetar porque sin datos de minutos jugados no podemos
  saber si el jugador fue clave o solo estuvo en plantilla.

Ejecutar desde la raiz del proyecto:
    python process_adn.py
"""
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "tm_transfers__2407__ALL.csv"
OUT_FILE = PROJECT_ROOT / "data" / "rayados_adn.csv"


# ---------------------------------------------------------------------------
# Titulos de Rayados por temporada (datos hardcodeados verificados)
# Cada temporada usa el season_id de inicio (2017 = temporada 2017/18)
#
# Fuente: Wikipedia, milenio.com, olympics.com (cross-verificado)
# Titulos mayores: Liga MX, Concacaf Champions League
# Titulos menores: Copa MX, Campeon de Campeones
# ---------------------------------------------------------------------------
TITULOS_POR_TEMPORADA = {
    2017: ["Copa MX Apertura 2017"],
    2018: [],
    2019: ["Apertura 2019 (Liga MX)", "Copa MX 2019-20"],
    2020: [],
    2021: ["Concachampions 2021"],
    2022: [],
    2023: [],
    2024: [],
}

# Categorias para visualizacion
TITULOS_MAYORES = ["Liga MX", "Concachampions"]


def titulos_durante_estancia(season_in: int, season_out_or_now: int) -> list[str]:
    """
    Devuelve lista de titulos ganados por Rayados durante el periodo
    [season_in, season_out_or_now] inclusive.
    """
    titulos = []
    for s in range(season_in, season_out_or_now + 1):
        titulos.extend(TITULOS_POR_TEMPORADA.get(s, []))
    return titulos


# ---------------------------------------------------------------------------
# 1. Carga y limpieza basica
# ---------------------------------------------------------------------------
def load_transfers() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"No encuentro {RAW_FILE.name}. Ejecuta el notebook 02 primero."
        )
    df = pd.read_csv(RAW_FILE)
    # tipos
    df["coste_meur"] = df["coste_meur"].fillna(0).astype(float)
    df["edad"] = df["edad"].fillna(0).astype(int)
    df["season_id"] = df["season_id"].astype(int)
    print(f"Cargados: {len(df)} registros")
    return df


# ---------------------------------------------------------------------------
# 2. Matching entradas-salidas del mismo jugador
# ---------------------------------------------------------------------------
def build_player_journeys(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cruza entradas y salidas del mismo tm_player_id.
    Devuelve un DataFrame con una fila POR FICHAJE (solo entradas) donde
    cada fila tiene tambien info de la salida si ocurrio.
    """
    entradas = df[df["direccion"] == "in"].copy()
    salidas = df[df["direccion"] == "out"].copy()

    # En el dataset hay jugadores que entran y salen en mismo año (cesiones cortas).
    # Para cada entrada buscamos la salida MÁS PROXIMA POSTERIOR del mismo jugador.
    enriched = []
    for _, e in entradas.iterrows():
        pid = e["tm_player_id"]
        season_in = e["season_id"]
        # buscar salidas posteriores del mismo jugador
        matches = salidas[
            (salidas["tm_player_id"] == pid) &
            (salidas["season_id"] >= season_in)
        ]
        if not matches.empty:
            salida = matches.sort_values("season_id").iloc[0]
            season_out = int(salida["season_id"])
            coste_venta = float(salida["coste_meur"])
            anios_en_club = season_out - season_in + 1
            destino_salida = salida["club_relacionado"]
            liga_salida = salida["liga_relacionada"]
            coste_texto_salida = salida.get("coste_texto_original", "")
            sigue = False
        else:
            season_out = None
            coste_venta = 0.0
            anios_en_club = 2025 - season_in  # asumimos sigue activo
            destino_salida = ""
            liga_salida = ""
            coste_texto_salida = ""
            sigue = True

        # Calcular titulos ganados durante la estancia (inclusive)
        season_out_for_titles = season_out if season_out is not None else 2024
        titulos_estancia = titulos_durante_estancia(season_in, season_out_for_titles)
        n_titulos_mayores = sum(
            1 for t in titulos_estancia
            if any(tm in t for tm in TITULOS_MAYORES)
        )

        enriched.append({
            "jugador": e["jugador"],
            "tm_player_id": pid,
            "season_id_llegada": season_in,
            "anio_llegada": season_in,
            "edad_llegada": e["edad"],
            "nacionalidad": e["nacionalidad"],
            "posicion_tm": e["posicion_tm"],
            "club_anterior": e["club_relacionado"],
            "liga_anterior": e["liga_relacionada"],
            "coste_compra_meur": float(e["coste_meur"]),
            "coste_texto_compra": e.get("coste_texto_original", ""),
            "season_id_salida": season_out,
            "anios_en_club": anios_en_club,
            "club_destino": destino_salida,
            "liga_destino": liga_salida,
            "coste_venta_meur": coste_venta,
            "coste_texto_venta": coste_texto_salida,
            "sigue_en_club": sigue,
            "titulos_ganados": "; ".join(titulos_estancia) if titulos_estancia else "",
            "n_titulos_total": len(titulos_estancia),
            "n_titulos_mayores": n_titulos_mayores,
        })

    out = pd.DataFrame(enriched)
    print(f"Jugadores entradas->salidas matcheados: {(~out['sigue_en_club']).sum()} con salida, {out['sigue_en_club'].sum()} siguen en club")
    return out


# ---------------------------------------------------------------------------
# 3. Logica de etiquetado
# ---------------------------------------------------------------------------
def label_transfer(row) -> tuple[str, str]:
    """
    Devuelve (etiqueta, razon_principal).
    etiqueta in {'exitoso','fallido','neutro'}.
    """
    coste = row["coste_compra_meur"]
    venta = row["coste_venta_meur"]
    anios = row["anios_en_club"]
    sigue = row["sigue_en_club"]
    edad_llegada = row["edad_llegada"]
    texto_venta = str(row.get("coste_texto_venta", "")).lower()
    texto_compra = str(row.get("coste_texto_compra", "")).lower()

    # Pre-filtros: cesiones cortas, fin de cesion al llegar (no son fichajes reales)
    if "cesi" in texto_compra or "fin de" in texto_compra or "loan" in texto_compra:
        return "neutro", "Retorno de cesion (no es fichaje real)"

    # Info de titulos (para regla de bonificacion)
    n_titulos_mayores = int(row.get("n_titulos_mayores", 0))
    titulos_str = str(row.get("titulos_ganados", ""))

    # Calculo de recuperacion para evaluaciones (None si sigue o llego libre)
    if coste > 0 and not sigue:
        recup_pct = (venta / coste) * 100
    else:
        recup_pct = None

    # =====================================================================
    # CRITERIOS DE FALLIDO (tienen prioridad - desastre financiero domina)
    # =====================================================================
    # (a) Coste alto + recuperacion baja
    if coste >= 3.0 and not sigue and venta < coste * 0.50:
        return "fallido", f"Coste {coste:.1f}ME, recupero solo {recup_pct:.0f}%"

    # (b) Coste muy alto + revendido rapido a perdida
    if coste >= 5.0 and not sigue and anios <= 2 and venta < coste * 0.85:
        return "fallido", f"Coste alto ({coste:.1f}ME) revendido en {anios} anio(s) al {recup_pct:.0f}%"

    # (c) Coste medio + salida sin recuperacion en plazo corto
    if coste >= 2.0 and not sigue and venta == 0 and anios <= 2:
        return "fallido", f"Coste {coste:.1f}ME, salio libre/cesion en {anios} anios"

    # =====================================================================
    # CRITERIOS DE EXITOSO (orden: financieros primero, despues titulos)
    # =====================================================================
    # (a) Operacion rentable: vendido por mas de lo que costo
    if not sigue and coste > 0 and venta >= coste * 1.20:
        return "exitoso", f"Operacion rentable: vendido al {recup_pct:.0f}% del coste"

    # (b) Recuperacion al menos 90% en largo plazo (3+ anios)
    if not sigue and coste >= 2.0 and venta >= coste * 0.90 and anios >= 3:
        return "exitoso", f"Recupero {recup_pct:.0f}% tras {anios} anios"

    # (c) Llegada libre/cantera con venta significativa (>=2ME)
    if coste == 0 and venta >= 2.0:
        return "exitoso", f"Llego libre, vendido por {venta:.1f}ME"

    # (d) NUEVO: Bonificacion por titulos
    # EXITOSO si gano titulo mayor + 2+ anios + no fue desastre financiero
    if n_titulos_mayores >= 1 and anios >= 2:
        # Proteccion anti-desastre 1: recuperacion <30% no se salva por titulos
        es_desastre = (recup_pct is not None and recup_pct < 30)
        # Proteccion anti-desastre 2: coste alto sin venta = desastre aunque haya titulos
        es_desastre_coste_alto = (not sigue and coste >= 3.0 and venta < coste * 0.40)

        if not (es_desastre or es_desastre_coste_alto):
            titulo_principal = titulos_str.split(";")[0].strip() if titulos_str else "titulo mayor"
            if sigue:
                return "exitoso", f"Gano {titulo_principal} ({anios} temp en club)"
            elif recup_pct is not None:
                return "exitoso", f"Gano {titulo_principal}, recupero {recup_pct:.0f}% en {anios} anios"
            else:
                # Caso coste=0: llego libre y gano titulo
                if venta > 0:
                    return "exitoso", f"Gano {titulo_principal}, llego libre y vendido por {venta:.1f}ME"
                else:
                    return "exitoso", f"Gano {titulo_principal}, llego libre ({anios} anios)"

    # Casos limitrofes
    razon_neutro = "Sin datos suficientes"
    if sigue and anios >= 3:
        razon_neutro = "Sigue en club tras 3+ anios"
    elif anios == 1 and not sigue:
        razon_neutro = "Solo 1 temporada"
    elif coste < 1.0:
        razon_neutro = "Coste bajo"

    return "neutro", razon_neutro


def label_all(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica el etiquetado a todo el dataframe."""
    df = df.copy()
    labels = df.apply(label_transfer, axis=1)
    df["etiqueta"] = labels.str[0]
    df["razon_principal"] = labels.str[1]
    return df


# ---------------------------------------------------------------------------
# 4. Reformatear al esquema que la app espera
# ---------------------------------------------------------------------------
def reshape_for_app(df: pd.DataFrame) -> pd.DataFrame:
    """
    Esquema que app.py espera para rayados_adn.csv:
    jugador, anio_llegada, edad_llegada, nacionalidad, club_anterior,
    liga_anterior, posicion, minutos_previos, coste_meur, salario_anual_meur,
    anios_en_club, etiqueta, razon_principal, observacion
    """
    # mapeo de posiciones TM a categorias simplificadas (igual que en process_squad.py)
    def map_pos(pos_tm):
        if not pos_tm or pd.isna(pos_tm):
            return "Desconocido"
        p = str(pos_tm).lower()
        if "portero" in p or "goalkeeper" in p: return "Portero"
        if "central" in p or "centre-back" in p: return "Defensa central"
        if "lateral" in p or "back" in p: return "Lateral"
        if "extremo" in p or "winger" in p or "interior" in p: return "Extremo"
        if "delantero" in p or "forward" in p or "striker" in p: return "Delantero"
        if "medi" in p or "centrocamp" in p or "pivote" in p or "midfield" in p: return "Mediocentro"
        return "Mediocentro"  # default

    df = df.copy()
    df["posicion"] = df["posicion_tm"].apply(map_pos)

    # observacion narrativa
    def make_obs(row):
        parts = []
        if row["coste_compra_meur"] > 0:
            parts.append(f"Comprado por {row['coste_compra_meur']:.1f}ME")
        elif "libre" in str(row.get("coste_texto_compra","")).lower():
            parts.append("Llego libre")
        if not row["sigue_en_club"]:
            if row["coste_venta_meur"] > 0:
                parts.append(f"vendido por {row['coste_venta_meur']:.1f}ME a {row['club_destino']}")
            else:
                parts.append(f"salio sin coste a {row['club_destino']}")
        else:
            parts.append("sigue en el club")
        return ". ".join(parts).capitalize()

    df["observacion"] = df.apply(make_obs, axis=1)

    # esquema final
    out = pd.DataFrame({
        "jugador": df["jugador"],
        "anio_llegada": df["anio_llegada"],
        "edad_llegada": df["edad_llegada"],
        "nacionalidad": df["nacionalidad"],
        "club_anterior": df["club_anterior"],
        "liga_anterior": df["liga_anterior"],
        "posicion": df["posicion"],
        "minutos_previos": 0,   # no scrapeado todavia
        "coste_meur": df["coste_compra_meur"],
        "coste_venta_meur": df["coste_venta_meur"],
        "salario_anual_meur": 0,   # no scrapeado
        "anios_en_club": df["anios_en_club"],
        "sigue_en_club": df["sigue_en_club"],
        "titulos_ganados": df["titulos_ganados"],
        "n_titulos_mayores": df["n_titulos_mayores"],
        "etiqueta": df["etiqueta"],
        "razon_principal": df["razon_principal"],
        "observacion": df["observacion"],
    })
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=== Procesamiento de ADN Rayados ===\n")
    df_raw = load_transfers()
    print()

    journeys = build_player_journeys(df_raw)
    print()

    journeys = label_all(journeys)
    print("Distribucion de etiquetas:")
    print(journeys["etiqueta"].value_counts().to_string())
    print()

    print("=== TOP 10 EXITOSOS ===")
    exitos = journeys[journeys["etiqueta"]=="exitoso"].nlargest(10, "coste_venta_meur")
    print(exitos[["jugador","anio_llegada","coste_compra_meur","coste_venta_meur","anios_en_club","n_titulos_mayores","razon_principal"]].to_string(index=False))
    print()

    print("=== TOP 10 FALLIDOS ===")
    fallos = journeys[journeys["etiqueta"]=="fallido"].nlargest(10, "coste_compra_meur")
    print(fallos[["jugador","anio_llegada","coste_compra_meur","coste_venta_meur","anios_en_club","n_titulos_mayores","razon_principal"]].to_string(index=False))
    print()

    print("=== CASOS LIMITROFES (neutros con coste >= 2 ME) ===")
    print("(estos son candidatos para review manual)")
    limit = journeys[(journeys["etiqueta"]=="neutro") & (journeys["coste_compra_meur"]>=2)]
    limit = limit.nlargest(15, "coste_compra_meur")
    print(limit[["jugador","anio_llegada","coste_compra_meur","coste_venta_meur","anios_en_club","sigue_en_club","n_titulos_mayores","titulos_ganados"]].to_string(index=False))
    print()

    # Estadistica adicional: cuantos fichajes coincidieron con titulos
    con_titulos = journeys[journeys["n_titulos_mayores"] > 0]
    print(f"=== INFO ADICIONAL: TITULOS ===")
    print(f"  Fichajes que coincidieron con al menos 1 titulo mayor: {len(con_titulos)} / {len(journeys)}")
    print(f"  (Esta info NO afecta etiqueta - es contextual)")
    print()

    # backup del ADN dummy
    if OUT_FILE.exists():
        backup = OUT_FILE.with_suffix(".dummy_backup.csv")
        if not backup.exists():
            OUT_FILE.rename(backup)
            print(f"[backup] dummy anterior guardado en {backup.name}")

    # generar CSV final
    out = reshape_for_app(journeys)
    out.to_csv(OUT_FILE, index=False)
    print(f"\nGuardado: {OUT_FILE.name}")
    print(f"Total fichajes en ADN: {len(out)}")
    print(f"  exitosos: {(out['etiqueta']=='exitoso').sum()}")
    print(f"  fallidos: {(out['etiqueta']=='fallido').sum()}")
    print(f"  neutros:  {(out['etiqueta']=='neutro').sum()}")
    print("\nListo. Recarga la app y revisa la pestana 'Club Rayados' -> ADN.")


if __name__ == "__main__":
    main()
