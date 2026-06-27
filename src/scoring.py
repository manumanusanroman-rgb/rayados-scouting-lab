"""
scoring.py
----------
Logica de puntuacion de jugadores.

Tres scores:
- score_encaje : que tan bien encaja el jugador con el perfil buscado (0-100)
- score_riesgo : riesgo de fichaje basado en edad, minutos, lesiones, cambio de liga
- score_final  : combinacion ponderada (encaje 70% + (100-riesgo) 30%)

Adicional:
- estimate_salary: rango salarial estimado en M€ segun edad, minutos, score y liga.
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Normalizacion
# ---------------------------------------------------------------------------
def minmax_normalize(series: pd.Series) -> pd.Series:
    s = series.astype(float)
    lo, hi = s.min(skipna=True), s.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series([50.0] * len(s), index=s.index)
    return ((s - lo) / (hi - lo) * 100).clip(0, 100)


def normalize_kpis(df: pd.DataFrame, kpis: list[str]) -> pd.DataFrame:
    out = df.copy()
    for k in kpis:
        if k in out.columns:
            out[f"{k}_norm"] = minmax_normalize(out[k])
        else:
            out[f"{k}_norm"] = np.nan
    return out


# ---------------------------------------------------------------------------
# Score de encaje
# ---------------------------------------------------------------------------
def score_profile_fit(df: pd.DataFrame, kpi_weights: dict[str, float]) -> pd.Series:
    weights = {k: w for k, w in kpi_weights.items() if f"{k}_norm" in df.columns}
    total = sum(weights.values())
    if total == 0:
        return pd.Series([np.nan] * len(df), index=df.index)
    weights = {k: w / total for k, w in weights.items()}

    score = pd.Series(0.0, index=df.index)
    for kpi, w in weights.items():
        col = df[f"{kpi}_norm"].fillna(50.0)
        score = score + col * w
    return score.clip(0, 100)


# ---------------------------------------------------------------------------
# Score de riesgo
# ---------------------------------------------------------------------------
def score_risk(df: pd.DataFrame, liga_destino: str = "Liga MX",
               edad_optima: tuple[int, int] = (23, 28)) -> pd.Series:
    n = len(df)
    edad = df["edad"].astype(float)
    minutos = df["minutos"].astype(float)
    lesion = df.get("lesion_dias_ult_temp", pd.Series([0] * n, index=df.index)).astype(float)
    liga = df["liga"].astype(str) if "liga" in df.columns else pd.Series([liga_destino] * n, index=df.index)

    lo, hi = edad_optima
    edad_pen = np.where(edad < lo, (lo - edad) * 6,
                np.where(edad > hi, (edad - hi) * 7, 0))
    edad_pen = np.clip(edad_pen, 0, 35)
    min_pen = np.clip((2000 - minutos) / 2000 * 25, 0, 25)
    les_pen = np.clip(lesion / 90 * 20, 0, 20)
    mismo = (liga == liga_destino).values
    liga_pen = np.where(mismo, 5, 20)

    total = edad_pen + min_pen + les_pen + liga_pen
    return pd.Series(np.clip(total, 0, 100), index=df.index)


# ---------------------------------------------------------------------------
# Score final
# ---------------------------------------------------------------------------
def score_final(score_encaje: pd.Series, score_riesgo: pd.Series,
                w_encaje: float = 0.70, w_riesgo: float = 0.30) -> pd.Series:
    return (score_encaje * w_encaje + (100 - score_riesgo) * w_riesgo).clip(0, 100)


# ---------------------------------------------------------------------------
# Pipeline completo
# ---------------------------------------------------------------------------
def evaluate_players(players_df: pd.DataFrame, kpi_weights: dict[str, float],
                     position: str | None = None) -> pd.DataFrame:
    df = players_df.copy()
    if position is not None:
        df = df[df["posicion"] == position].copy()

    kpis = list(kpi_weights.keys())
    df = normalize_kpis(df, kpis)
    df["score_encaje"] = score_profile_fit(df, kpi_weights).round(1)
    df["score_riesgo"] = score_risk(df).round(1)
    df["score_final"] = score_final(df["score_encaje"], df["score_riesgo"]).round(1)
    return df.sort_values("score_final", ascending=False).reset_index(drop=True)


def evaluate_players_any(players_df: pd.DataFrame) -> pd.DataFrame:
    """Puntua sin perfil objetivo (busqueda por insignias). Encaje = mejor medalla."""
    df = players_df.copy()
    pts_cols = ["tirador_lejano_pts", "cabeceador_pts", "recuperador_puro_pts",
                "presionador_alto_pts", "definidor_pts", "creador_pts",
                "desequilibrante_pts", "muro_pts", "motor_pts"]
    have = [c for c in pts_cols if c in df.columns]
    if have:
        best = df[have].apply(pd.to_numeric, errors="coerce").max(axis=1).fillna(0)
        df["score_encaje"] = best.clip(0, 100).round(1)
    else:
        df["score_encaje"] = 0.0
    df["score_riesgo"] = score_risk(df).round(1)
    df["score_final"] = score_final(df["score_encaje"], df["score_riesgo"]).round(1)
    return df.sort_values("score_final", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Estimacion salarial
# ---------------------------------------------------------------------------
# Multiplicadores por liga de origen (poder adquisitivo / nivel competitivo)
LIGA_SALARY_MULT = {
    "Liga MX": 1.00,
    "Primera Argentina": 0.85,
    "Brasileirao": 1.10,
    "Segunda Espanola": 1.20,
}

def estimate_salary_range(row: pd.Series) -> tuple[float, float]:
    """
    Devuelve (salario_min, salario_max) anual estimado en MEUR.

    Logica:
    - Base = valor_mercado * 0.30 (regla del pulgar: salario anual ~ 25-40% del valor)
    - Multiplicador por liga de origen
    - Bonus por score final (jugadores top piden mas)
    - Banda ±20% para reflejar incertidumbre de negociacion
    """
    valor = float(row.get("valor_mercado_meur", 1.5))
    score = float(row.get("score_final", 50.0))
    liga = str(row.get("liga", "Liga MX"))

    liga_mult = LIGA_SALARY_MULT.get(liga, 1.0)
    score_mult = 0.85 + (score / 100) * 0.45    # entre 0.85 y 1.30
    base = valor * 0.30 * liga_mult * score_mult

    return round(base * 0.8, 2), round(base * 1.2, 2)


def add_salary_estimates(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas salario_min_meur y salario_max_meur."""
    out = df.copy()
    ranges = out.apply(estimate_salary_range, axis=1)
    out["salario_min_meur"] = [r[0] for r in ranges]
    out["salario_max_meur"] = [r[1] for r in ranges]
    return out
