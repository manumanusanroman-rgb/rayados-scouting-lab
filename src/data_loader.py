"""
data_loader.py
--------------
Carga centralizada de los datasets del proyecto.

Para reemplazar dummy por datos reales: basta con sustituir los CSV en /data/
manteniendo los nombres de columnas. Las funciones devuelven DataFrames listos.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_teams_benchmark() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "teams_benchmark.csv")


@st.cache_data
def load_players() -> pd.DataFrame:
    """Pool de jugadores scouteables (Liga MX, Argentina, Brasil, Segunda Espanola)."""
    return pd.read_csv(DATA_DIR / "players_scouting.csv")


@st.cache_data
def load_kpi_profiles() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "kpi_profiles.csv")


@st.cache_data
def load_adn() -> pd.DataFrame:
    """Historico de fichajes etiquetados como exitosos o fallidos."""
    return pd.read_csv(DATA_DIR / "rayados_adn.csv")


@st.cache_data
def load_rayados_squad() -> pd.DataFrame:
    """Plantilla actual de Rayados (nombres reales, stats dummy)."""
    return pd.read_csv(DATA_DIR / "rayados_squad.csv")


@st.cache_data
def load_club_info() -> dict:
    """Info economica/administrativa del club como dict para acceso rapido."""
    df = pd.read_csv(DATA_DIR / "club_info.csv")
    return {row["concepto"]: row["valor"] for _, row in df.iterrows()}


def get_profiles_for_position(position: str) -> list[str]:
    df = load_kpi_profiles()
    return sorted(df[df["posicion"] == position]["perfil"].unique().tolist())


def get_kpis_for_profile(position: str, profile: str) -> dict[str, float]:
    df = load_kpi_profiles()
    sub = df[(df["posicion"] == position) & (df["perfil"] == profile)]
    return dict(zip(sub["kpi"], sub["peso"] / 100.0))
