"""
process_medals.py v2 - PERCENTILES + 4 MEDALLAS
================================================
Sistema basado en percentiles de la liga (no umbrales arbitrarios).
Cada dimension da 0-30 pts segun percentil.

Medallas:
  1) TIRADOR LEJANO
  2) CABECEADOR
  3) RECUPERADOR PURO (zona baja + entradas limpias)
  4) PRESIONADOR ALTO (presion en ultimo tercio)

Clasificacion: ORO >= 75, PLATA >= 50, BRONCE >= 30
"""
from pathlib import Path
import pandas as pd
import numpy as np
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
EVENTS_CSV = DATA_DIR / "player_events_stats.csv"
SCOUTING_CSV = DATA_DIR / "players_scouting.csv"
RAYADOS_CSV = DATA_DIR / "rayados_squad.csv"
OUTPUT_CSV = DATA_DIR / "player_medals.csv"


def norm(s):
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def classify(pts):
    if pts >= 75:
        return "ORO"
    if pts >= 50:
        return "PLATA"
    if pts >= 30:
        return "BRONCE"
    return None


def percentile_to_points(value, p70, p85, p95, max_pts=30):
    """
    Convierte un valor a puntos segun donde cae en la distribucion:
      < p70:    0 pts
      p70-p85:  10 pts (top 30%)
      p85-p95:  20 pts (top 15%)
      >= p95:   30 pts (top 5%)
    """
    if p95 <= 0:
        return 0
    if value < p70:
        return 0
    if value < p85:
        return round(max_pts * 0.33)
    if value < p95:
        return round(max_pts * 0.67)
    return max_pts


def compute_percentiles(series, mask=None):
    """Calcula P70, P85, P95 de una serie. Mask opcional filtra (ej: solo con minutos suficientes)."""
    if mask is not None:
        s = series[mask]
    else:
        s = series
    s = s[s > 0]  # excluir ceros (no aplicables)
    if len(s) < 5:
        return 0, 0, 0
    return s.quantile(0.70), s.quantile(0.85), s.quantile(0.95)


def main():
    print("=" * 70)
    print("MEDALLAS v2 - PERCENTILES + 4 MEDALLAS")
    print("=" * 70)
    if not EVENTS_CSV.exists():
        raise FileNotFoundError(f"Falta {EVENTS_CSV}")
    df = pd.read_csv(EVENTS_CSV)
    print(f"\nCargados {len(df)} jugadores")

    # cargar minutos POR player_id (robusto). El nombre queda solo de respaldo.
    def _norm_id(v):
        s = str(v).strip()
        return s[:-2] if s.endswith(".0") else s
    id_to_min = {}
    name_to_min = {}
    for csv_path in [SCOUTING_CSV, RAYADOS_CSV]:
        if csv_path.exists():
            d = pd.read_csv(csv_path)
            nc = "nombre" if "nombre" in d.columns else "jugador"
            if "minutos" in d.columns:
                for _, r in d.iterrows():
                    if "player_id" in d.columns and pd.notna(r.get("player_id")):
                        id_to_min[_norm_id(r["player_id"])] = r["minutos"]
                    name_to_min[norm(r[nc])] = r["minutos"]
    def _min_lookup(r):
        pid = _norm_id(r.get("player_id", ""))
        if pid in id_to_min:
            return id_to_min[pid]
        return name_to_min.get(norm(r["nombre"]), 0)
    df["minutos"] = df.apply(_min_lookup, axis=1)
    print(f"  {(df['minutos'] > 0).sum()} con minutos asignados (por player_id)")

    # CALCULAR METRICAS DERIVADAS POR 90
    df["recup_total_90"] = np.where(df["minutos"] > 0, df["recuperaciones_total"] / df["minutos"] * 90, 0)
    df["recup_baja_90"] = np.where(df["minutos"] > 0, df["recuperaciones_zona_baja"] / df["minutos"] * 90, 0)
    df["recup_alto_90"] = np.where(df["minutos"] > 0, df["recuperaciones_ultimo_tercio"] / df["minutos"] * 90, 0)
    df["intercept_total_90"] = np.where(df["minutos"] > 0, df["intercepciones_total"] / df["minutos"] * 90, 0)
    df["intercept_baja_90"] = np.where(df["minutos"] > 0, df["intercepciones_zona_baja"] / df["minutos"] * 90, 0)
    df["entradas_ok_90"] = np.where(df["minutos"] > 0, df["entradas_exitosas"] / df["minutos"] * 90, 0)
    df["entradas_alto_90"] = np.where(df["minutos"] > 0, df["entradas_ultimo_tercio"] / df["minutos"] * 90, 0)
    df["conversion_pct"] = np.where(df["tiros"] > 0, df["goles"] / df["tiros"] * 100, 0)
    df["pases_clave_90"] = np.where(df["minutos"] > 0, df["pases_clave"] / df["minutos"] * 90, 0)

    # excluir jugadores con minutos no fiables: totales de eventos incoherentes con
    # sus minutos (recuperaciones por 90 imposibles, >20). Son errores de dato.
    _xg90 = np.where(df["minutos"] > 0, df["xg"] / df["minutos"] * 90, 0)
    _imposible = (df["recup_total_90"] > 20) | (_xg90 > 1.6) | (df["pases_clave_90"] > 8)
    _fiable = ~((df["minutos"] > 0) & _imposible)
    _n_excl = int((~_fiable).sum())
    df = df[_fiable].reset_index(drop=True)
    print(f"  Excluidos por minutos no fiables (recup/90 > 20): {_n_excl}")

    # mask para defensa: requerir min 500 minutos (suficiente para ser representativo)
    has_mins = df["minutos"] >= 500

    # ============================================================
    # PERCENTILES POR DIMENSION
    # ============================================================
    print("\nCalculando percentiles de liga...")

    # TIRADOR LEJANO
    tl_vol_p = compute_percentiles(df["tiros_fuera_area"])
    tl_ac_p = compute_percentiles(df["acierto_tiros_fuera_pct"], df["tiros_fuera_area"] >= 8)
    tl_pt_p = compute_percentiles(df["puerta_tiros_fuera_pct"], df["tiros_fuera_area"] >= 4)
    print(f"  TIRADOR_LEJANO  volumen: P70={tl_vol_p[0]:.1f} P85={tl_vol_p[1]:.1f} P95={tl_vol_p[2]:.1f}")
    print(f"  TIRADOR_LEJANO  acierto: P70={tl_ac_p[0]:.1f} P85={tl_ac_p[1]:.1f} P95={tl_ac_p[2]:.1f}")
    print(f"  TIRADOR_LEJANO  puerta:  P70={tl_pt_p[0]:.1f} P85={tl_pt_p[1]:.1f} P95={tl_pt_p[2]:.1f}")

    # CABECEADOR
    cb_gol_p = compute_percentiles(df["goles_cabeza"])
    cb_aer_p = compute_percentiles(df["pct_aereos_ganados"], df["aereos_total"] >= 30)
    cb_vol_p = compute_percentiles(df["tiros_cabeza"])
    print(f"  CABECEADOR  goles: P70={cb_gol_p[0]:.1f} P85={cb_gol_p[1]:.1f} P95={cb_gol_p[2]:.1f}")
    print(f"  CABECEADOR  %aereos: P70={cb_aer_p[0]:.1f} P85={cb_aer_p[1]:.1f} P95={cb_aer_p[2]:.1f}")
    print(f"  CABECEADOR  volumen: P70={cb_vol_p[0]:.1f} P85={cb_vol_p[1]:.1f} P95={cb_vol_p[2]:.1f}")

    # RECUPERADOR PURO (zona baja)
    rp_vol_p = compute_percentiles(df["recup_baja_90"] + df["intercept_baja_90"], has_mins)
    rp_ef_p = compute_percentiles(df["pct_entradas_exitosas"], (df["entradas_total"] >= 15) & has_mins)
    rp_int_p = compute_percentiles(df["intercept_total_90"], has_mins)
    print(f"  RECUP_PURO  vol_baja: P70={rp_vol_p[0]:.2f} P85={rp_vol_p[1]:.2f} P95={rp_vol_p[2]:.2f}")
    print(f"  RECUP_PURO  ef_entradas: P70={rp_ef_p[0]:.1f} P85={rp_ef_p[1]:.1f} P95={rp_ef_p[2]:.1f}")
    print(f"  RECUP_PURO  intercept: P70={rp_int_p[0]:.2f} P85={rp_int_p[1]:.2f} P95={rp_int_p[2]:.2f}")

    # PRESIONADOR ALTO
    pa_recup_p = compute_percentiles(df["recup_alto_90"], has_mins)
    pa_total_p = compute_percentiles(df["recup_total_90"], has_mins)
    pa_ent_p = compute_percentiles(df["entradas_alto_90"], has_mins)
    print(f"  PRES_ALTO  recup_alto: P70={pa_recup_p[0]:.2f} P85={pa_recup_p[1]:.2f} P95={pa_recup_p[2]:.2f}")
    print(f"  PRES_ALTO  recup_total: P70={pa_total_p[0]:.2f} P85={pa_total_p[1]:.2f} P95={pa_total_p[2]:.2f}")
    print(f"  PRES_ALTO  entradas_alto: P70={pa_ent_p[0]:.2f} P85={pa_ent_p[1]:.2f} P95={pa_ent_p[2]:.2f}")

    # ===== NUEVAS MEDALLAS: PERCENTILES =====
    fin_xg_p = compute_percentiles(df["g_menos_xg"], df["tiros"] >= 20)
    fin_con_p = compute_percentiles(df["conversion_pct"], df["tiros"] >= 20)
    fin_gol_p = compute_percentiles(df["goles"])
    cre_pc_p = compute_percentiles(df["pases_clave"])
    cre_90_p = compute_percentiles(df["pases_clave_90"], has_mins)
    reg_vol_p = compute_percentiles(df["regates_exitosos"])
    reg_ef_p = compute_percentiles(df["pct_regates_exito"], df["regates_intentados"] >= 20)
    reg_ut_p = compute_percentiles(df["regates_ultimo_tercio_ok"])
    mur_aer_p = compute_percentiles(df["aereos_ganados"])
    mur_aerp_p = compute_percentiles(df["pct_aereos_ganados"], df["aereos_total"] >= 30)
    mur_ent_p = compute_percentiles(df["pct_entradas_exitosas"], df["entradas_total"] >= 15)
    has_mins_mot = df["minutos"] >= 900
    mot_rec_p = compute_percentiles(df["recup_total_90"], has_mins_mot)
    mot_ent_p = compute_percentiles(df["entradas_ok_90"], has_mins_mot)
    mot_int_p = compute_percentiles(df["intercept_total_90"], has_mins_mot)
    print("  5 nuevas medallas: percentiles calculados")

    # ============================================================
    # APLICAR MEDALLAS
    # ============================================================
    print("\nAplicando medallas...")
    rows = []
    for _, r in df.iterrows():
        nombre = r["nombre"]
        mins = r["minutos"]

        # ---- TIRADOR LEJANO ----
        tl_v = percentile_to_points(r["tiros_fuera_area"], *tl_vol_p, 40)
        tl_a = percentile_to_points(r["acierto_tiros_fuera_pct"], *tl_ac_p, 30) if r["tiros_fuera_area"] >= 8 else 0
        tl_p = percentile_to_points(r["puerta_tiros_fuera_pct"], *tl_pt_p, 30) if r["tiros_fuera_area"] >= 4 else 0
        tl_total = tl_v + tl_a + tl_p

        # ---- CABECEADOR ----
        cb_g = percentile_to_points(r["goles_cabeza"], *cb_gol_p, 40)
        cb_a = percentile_to_points(r["pct_aereos_ganados"], *cb_aer_p, 30) if r["aereos_total"] >= 30 else 0
        cb_v = percentile_to_points(r["tiros_cabeza"], *cb_vol_p, 30)
        cb_total = cb_g + cb_a + cb_v

        # ---- RECUPERADOR PURO ----
        if mins < 500:
            rp_total = 0
        else:
            rp_v = percentile_to_points(r["recup_baja_90"] + r["intercept_baja_90"], *rp_vol_p, 40)
            rp_e = percentile_to_points(r["pct_entradas_exitosas"], *rp_ef_p, 30) if r["entradas_total"] >= 15 else 0
            rp_i = percentile_to_points(r["intercept_total_90"], *rp_int_p, 30)
            rp_total = rp_v + rp_e + rp_i

        # ---- PRESIONADOR ALTO ----
        if mins < 500:
            pa_total = 0
        else:
            pa_r = percentile_to_points(r["recup_alto_90"], *pa_recup_p, 40)
            pa_t = percentile_to_points(r["recup_total_90"], *pa_total_p, 30)
            pa_e = percentile_to_points(r["entradas_alto_90"], *pa_ent_p, 30)
            pa_total = pa_r + pa_t + pa_e

        # ---- FIN DEFINIDOR ----
        fin_x = percentile_to_points(r["g_menos_xg"], *fin_xg_p, 40) if r["tiros"] >= 20 else 0
        fin_c = percentile_to_points(r["conversion_pct"], *fin_con_p, 30) if r["tiros"] >= 20 else 0
        fin_g = percentile_to_points(r["goles"], *fin_gol_p, 30)
        fin_total = fin_x + fin_c + fin_g

        # ---- CRE CREADOR ----
        cre_v = percentile_to_points(r["pases_clave"], *cre_pc_p, 60)
        cre_r = percentile_to_points(r["pases_clave_90"], *cre_90_p, 40) if mins >= 500 else 0
        cre_total = cre_v + cre_r

        # ---- REG DESEQUILIBRANTE ----
        reg_v = percentile_to_points(r["regates_exitosos"], *reg_vol_p, 40)
        reg_e = percentile_to_points(r["pct_regates_exito"], *reg_ef_p, 30) if r["regates_intentados"] >= 20 else 0
        reg_u = percentile_to_points(r["regates_ultimo_tercio_ok"], *reg_ut_p, 30)
        reg_total = reg_v + reg_e + reg_u

        # ---- MUR MURO ----
        mur_a = percentile_to_points(r["aereos_ganados"], *mur_aer_p, 40)
        mur_ap = percentile_to_points(r["pct_aereos_ganados"], *mur_aerp_p, 30) if r["aereos_total"] >= 30 else 0
        mur_en = percentile_to_points(r["pct_entradas_exitosas"], *mur_ent_p, 30) if r["entradas_total"] >= 15 else 0
        mur_total = mur_a + mur_ap + mur_en

        # ---- MOT MOTOR ----
        if mins < 900:
            mot_total = 0
        else:
            mot_r = percentile_to_points(r["recup_total_90"], *mot_rec_p, 40)
            mot_e = percentile_to_points(r["entradas_ok_90"], *mot_ent_p, 30)
            mot_i = percentile_to_points(r["intercept_total_90"], *mot_int_p, 30)
            mot_total = mot_r + mot_e + mot_i

        rows.append({
            "player_id": r.get("player_id", ""),
            "nombre": nombre,
            "minutos": int(mins) if mins else 0,
            "tirador_lejano_pts": tl_total,
            "tirador_lejano_medalla": classify(tl_total),
            "cabeceador_pts": cb_total,
            "cabeceador_medalla": classify(cb_total),
            "recuperador_puro_pts": rp_total,
            "recuperador_puro_medalla": classify(rp_total),
            "presionador_alto_pts": pa_total,
            "presionador_alto_medalla": classify(pa_total),
            "definidor_pts": fin_total,
            "definidor_medalla": classify(fin_total),
            "creador_pts": cre_total,
            "creador_medalla": classify(cre_total),
            "desequilibrante_pts": reg_total,
            "desequilibrante_medalla": classify(reg_total),
            "muro_pts": mur_total,
            "muro_medalla": classify(mur_total),
            "motor_pts": mot_total,
            "motor_medalla": classify(mot_total),
            "goles": int(r["goles"]),
            "pases_clave": int(r["pases_clave"]),
            "regates_exitosos": int(r["regates_exitosos"]),
            "aereos_ganados": int(r["aereos_ganados"]),
            "tiros_fuera": int(r["tiros_fuera_area"]),
            "goles_fuera": int(r["goles_fuera_area"]),
            "acierto_fuera_pct": r["acierto_tiros_fuera_pct"],
            "goles_cabeza": int(r["goles_cabeza"]),
            "aereos_pct": r["pct_aereos_ganados"],
            "aereos_total": int(r["aereos_total"]),
            "recuperaciones_total": int(r["recuperaciones_total"]),
            "recuperaciones_baja": int(r["recuperaciones_zona_baja"]),
            "recuperaciones_alto": int(r["recuperaciones_ultimo_tercio"]),
        })

    df_med = pd.DataFrame(rows)
    df_med.to_csv(OUTPUT_CSV, index=False)
    print(f"\nGuardado: {OUTPUT_CSV}")
    print(f"Total: {len(df_med)} jugadores")

    # DISTRIBUCION
    print("\n" + "=" * 70)
    print("DISTRIBUCION")
    print("=" * 70)
    for med in ["tirador_lejano_medalla", "cabeceador_medalla", "recuperador_puro_medalla", "presionador_alto_medalla", "definidor_medalla", "creador_medalla", "desequilibrante_medalla", "muro_medalla", "motor_medalla"]:
        nm = med.replace("_medalla", "").upper().replace("_", " ")
        counts = df_med[med].value_counts(dropna=False)
        print(f"\n{nm}:")
        for k, v in counts.items():
            print(f"  {k if k else 'sin medalla'}: {v}")

    # TOPs
    for col, label, extras in [
        ("tirador_lejano_pts", "TIRADOR LEJANO", ["tiros_fuera", "goles_fuera", "acierto_fuera_pct"]),
        ("cabeceador_pts", "CABECEADOR", ["goles_cabeza", "aereos_pct", "aereos_total"]),
        ("recuperador_puro_pts", "RECUPERADOR PURO", ["minutos", "recuperaciones_baja", "recuperaciones_total"]),
        ("presionador_alto_pts", "PRESIONADOR ALTO", ["minutos", "recuperaciones_alto", "recuperaciones_total"]),
        ("definidor_pts", "DEFINIDOR", ["goles", "minutos"]),
        ("creador_pts", "CREADOR", ["pases_clave", "minutos"]),
        ("desequilibrante_pts", "DESEQUILIBRANTE", ["regates_exitosos", "minutos"]),
        ("muro_pts", "MURO", ["aereos_ganados", "aereos_total"]),
        ("motor_pts", "MOTOR", ["minutos", "recuperaciones_total"]),
    ]:
        print("\n" + "=" * 70)
        print(f"TOP 12 - {label}")
        print("=" * 70)
        top = df_med[df_med[col] >= 30].nlargest(12, col)[["nombre"] + extras + [col, col.replace("_pts", "_medalla")]]
        print(top.to_string(index=False))


if __name__ == "__main__":
    main()