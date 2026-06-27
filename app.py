"""
Rayados Scouting Lab v2
=======================
Herramienta interactiva de direccion deportiva.
TFM Big Data Deportivo.

5 secciones:
1. Home
2. Club Rayados (presupuesto, plantilla, ADN, decepciones historicas)
3. Diagnostico Competitivo (Benchmark + Diagnostico inteligente fusionados)
4. Scouting Lab (Buscador + Comparador + Riesgo)
5. Propuesta Final (con ventas, fichajes y flujo de dinero)

Para ejecutar:  streamlit run app.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent))

from src import data_loader as dl
from src import scoring as sc
from src import diagnostics as dg
from src import visuals as vz


# ============================================================
# CONFIG + ESTILO
# ============================================================
st.set_page_config(
    page_title="Rayados Scouting Lab",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #003DA5 0%, #002a72 100%);
    }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 0.95rem; padding: 0.35rem 0;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: 0.15rem; }

    .ray-header {
        border-bottom: 3px solid #003DA5;
        padding-bottom: 0.8rem;
        margin-bottom: 1.5rem;
    }
    .ray-header h1 {
        color: #1C1C1C; font-weight: 700; margin: 0; font-size: 1.9rem;
    }
    .ray-header .subtitle {
        color: #6B7280; font-size: 0.95rem; margin-top: 0.25rem;
    }

    div[data-testid="stMetric"] {
        background: #F8FAFC; border: 1px solid #E5E7EB;
        border-left: 4px solid #003DA5;
        padding: 1rem 1.2rem; border-radius: 6px;
    }
    div[data-testid="stMetricLabel"] {
        color: #6B7280; font-size: 0.78rem;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] {
        color: #1C1C1C; font-weight: 700;
    }

    .badge {
        display: inline-block; padding: 2px 10px;
        border-radius: 999px; font-size: 0.75rem; font-weight: 600;
    }
    .badge-critica { background: #FEE2E2; color: #991B1B; }
    .badge-alta { background: #FED7AA; color: #9A3412; }
    .badge-moderada { background: #FEF3C7; color: #92400E; }
    .badge-ok { background: #DCFCE7; color: #166534; }

    .diag-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-left: 5px solid #003DA5;
        border-radius: 6px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .diag-card.critica { border-left-color: #DC2626; }
    .diag-card.alta { border-left-color: #D97706; }
    .diag-card.moderada { border-left-color: #CA8A04; }

    .stButton button {
        background: #003DA5; color: white; border: none;
        border-radius: 4px; font-weight: 500;
    }
    .stButton button:hover { background: #002a72; }

    .stDataFrame { border: 1px solid #E5E7EB; border-radius: 6px; }

    .info-tip {
        background: #EFF6FF; border-left: 3px solid #3E66C2;
        padding: 0.8rem 1rem; border-radius: 4px; font-size: 0.9rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CARGA DE DATOS
# ============================================================
bench = dl.load_teams_benchmark()
players = dl.load_players()
kpi_profiles = dl.load_kpi_profiles()
adn = dl.load_adn()
squad = dl.load_rayados_squad()
club = dl.load_club_info()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### 🔵 Rayados Scouting Lab")
    st.caption("Direccion deportiva · TFM Big Data")
    st.markdown("---")

    seccion = st.radio(
        "Navegacion",
        ["🏠 Home",
         "🏟️ Club Rayados",
         "📊 Diagnostico Competitivo",
         "🔍 Scouting Lab",
         "📋 Propuesta Final"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption("✅ Datos reales · Opta + Transfermarkt")
    st.caption(f"{len(players)} candidatos · 8 ligas")


def header(titulo: str, subtitulo: str = ""):
    st.markdown(
        f'<div class="ray-header"><h1>{titulo}</h1>'
        f'<div class="subtitle">{subtitulo}</div></div>',
        unsafe_allow_html=True,
    )


def badge_html(severidad: str) -> str:
    cls = {"Critica": "badge-critica", "Alta": "badge-alta",
           "Moderada": "badge-moderada"}.get(severidad, "badge-ok")
    return f'<span class="badge {cls}">{severidad}</span>'


# ====================================================================
# 1. HOME
# ====================================================================
if seccion == "🏠 Home":
    header("Rayados Scouting Lab",
           "Diagnostico competitivo y scouting para direccion deportiva")

    _base_fichajes = float(club['presupuesto_fichajes'])
    _cv = float(st.session_state.get("pf_caja_ventas", 0.0))
    _cf = float(st.session_state.get("pf_coste_fichajes", 0.0))
    _caja_fichajes = _base_fichajes + _cv - _cf
    # plantilla proyectada: misma logica que Club Rayados (una sola fuente de verdad)
    _plan_h = st.session_state.get("pf_plan_ventas", {})
    _out_h = [n for n, d in _plan_h.items() if (d.get("vender") or d.get("ceder"))]
    _n_vende = sum(1 for d in _plan_h.values() if d.get("vender"))
    _n_cede = sum(1 for d in _plan_h.values() if d.get("ceder"))
    _in_h = []
    for _l in st.session_state.get("listas", []):
        _prc = list(_l.get("prioridad", []))
        if _prc:
            _in_h.append(_prc[0])
    _vish = set(); _in_h = [n for n in _in_h if not (n in _vish or _vish.add(n))]
    _pn_h = "nombre" if "nombre" in players.columns else "jugador"
    _en_h = players[players[_pn_h].isin(_in_h)]
    _n_fich = int(len(_en_h))
    _qd_h = squad[~squad["jugador"].isin(_out_h)]
    _base_plantilla = int(len(squad))
    _plantilla_res = int(len(_qd_h) + len(_en_h))
    _hay_mov = bool(_out_h or _in_h)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja para fichajes", f"{_caja_fichajes:.1f} M\u20ac",
              (f"{(_cv - _cf):+.1f} vs base" if _hay_mov else None))
    c2.metric("Jugadores plantilla", _plantilla_res,
              (f"{(_n_fich - _n_vende - _n_cede):+d}" if _hay_mov else None))
    c3.metric("Candidatos analizados", len(players))
    c4.metric("Ultimo titulo Liga MX", int(club['ultimo_titulo_liga']))
    if _hay_mov:
        st.caption("Reflejando tu Propuesta Final: " + str(_n_vende) + " ventas, " + str(_n_cede) +
                   " cesiones, " + str(_n_fich) + " fichajes. Cambialo alla y estos numeros se mueven.")
    else:
        st.caption("Aun no defines movimientos. Ve a Propuesta Final (vender / ceder / fichar) y estos numeros reaccionan.")

    st.markdown("### ¿Que problema resuelve esta herramienta?")
    st.markdown(
        "Responde cuantitativamente a la pregunta de presidencia:\n\n"
        "> **¿Como hacemos que Rayados gane en el campo y en las oficinas siendo un club "
        "economicamente viable? Es decir: que necesitamos para competir al nivel del Top 4 de "
        "Liga MX y como financiamos esos refuerzos de forma sostenible.**\n\n"
        "Lo hace combinando tres analisis:\n"
        "1. **Quien somos hoy**: presupuesto, plantilla y ADN de fichajes (que tipo de fichaje funciona aqui).\n"
        "2. **Que nos falta**: brechas medidas vs el Top 4 de Liga MX, traducidas a causas concretas por posicion.\n"
        "3. **A quien fichar (y a quien vender)**: motor de scouting que puntua el **encaje final** con el perfil, "
        "estima **riesgo** y **coste/salario**, separa por **perfiles** e **insignias**, y compara cada candidato "
        "contra el jugador actual de esa posicion."
    )

    st.markdown("### Estructura de la app")
    st.markdown("""
- **🏟️ Club Rayados** — presupuesto, salarios, plantilla actual, ADN historico y decepciones pasadas.
- **📊 Diagnostico Competitivo** — benchmark vs el Top 4 de Liga MX y diagnostico de causa raiz.
- **🔍 Scouting Lab** — buscador + comparacion contra el jugador actual + score + salario.
- **📋 Propuesta Final** — a quien fichar, a quien vender, flujo de dinero.
""")

    with st.expander("Aviso importante sobre los datos"):
        st.markdown(
            "- La **plantilla de Rayados muestra nombres reales** del primer equipo "
            "(temporada 2025/26).\n"
            "- Las **estadisticas provienen de eventos Opta reales** (5M eventos, 8 ligas). Los **salarios son estimados** con un modelo posicional propio.\n"
            "- Los **jugadores scouteables tienen nombres reales** (Opta + Transfermarkt), con **edad y valor de mercado reales** de TM; donde no hubo match fiable el valor es estimado por liga y posicion.\n"
            "- Cada candidato lleva **insignias** (9 perfiles, oro/plata/bronce) "
            "calculadas a partir de sus eventos Opta."
        )


# ====================================================================
# 2. CLUB RAYADOS
# ====================================================================
elif seccion == "🏟️ Club Rayados":
    header("Club Rayados de Monterrey",
           "Situacion economica, plantilla y ADN historico del club")

    # ---------- PROYECCION (movimientos de Propuesta Final) ----------
    _plan_cr = st.session_state.get("pf_plan_ventas", {})
    _out_cr = [n for n, d in _plan_cr.items() if (d.get("vender") or d.get("ceder"))]
    _in_cr = []
    for _l in st.session_state.get("listas", []):
        _prc = list(_l.get("prioridad", []))
        if _prc:
            _in_cr.append(_prc[0])
    _visc = set(); _in_cr = [n for n in _in_cr if not (n in _visc or _visc.add(n))]
    _pn_cr = "nombre" if "nombre" in players.columns else "jugador"
    _qd_cr = squad[~squad["jugador"].isin(_out_cr)].copy()
    _en_cr = players[players[_pn_cr].isin(_in_cr)].copy()
    if "jugador" not in _en_cr.columns and "nombre" in _en_cr.columns:
        _en_cr["jugador"] = _en_cr["nombre"]
    try:
        squad_proj = pd.concat([_qd_cr, _en_cr], ignore_index=True)
    except Exception:
        squad_proj = squad.copy()
    _hay_mov = bool(_out_cr or _in_cr)
    _usar_proj = st.checkbox(
        "Aplicar movimientos de Propuesta Final (proyeccion: - ventas/cesiones + fichaje #1)",
        value=_hay_mov,
        help="Refleja en numeros y graficas las ventas/cesiones GUARDADAS y el fichaje #1 de cada Lista.")
    squad_view = squad_proj if (_usar_proj and _hay_mov) else squad
    if "salario_meur" in _en_cr.columns and len(_en_cr):
        _fichsal_cr = float(pd.to_numeric(_en_cr["salario_meur"], errors="coerce").fillna(0).sum())
    else:
        _fichsal_cr = 0.0
    _ahorro_cr = float(st.session_state.get("pf_ahorro_salarial", 0.0))
    _caja_cr = float(st.session_state.get("pf_caja_ventas", 0.0))
    _coste_cr = float(st.session_state.get("pf_coste_fichajes", 0.0))
    if _usar_proj and _hay_mov:
        st.caption("Plantilla PROYECTADA: salen " + str(len(_out_cr)) + ", entran " + str(len(_in_cr)) +
                   ". Desmarca el check para ver la actual. (Guarda tus ventas en Propuesta Final para que cuenten.)")

    # ---------- ECONOMIA ----------
    st.markdown("### 💰 Economia del club")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Presupuesto anual", f"{club['presupuesto_anual_total']:.0f} M€")
    if _usar_proj and _hay_mov:
        _masa_proj = club['masa_salarial_actual'] - _ahorro_cr + _fichsal_cr
        c2.metric("Masa salarial (proy.)", f"{_masa_proj:.0f} M€",
                  f"{_masa_proj - club['masa_salarial_actual']:+.1f} M€ vs actual", delta_color="inverse")
        c3.metric("Fichajes (disp.)", f"{club['presupuesto_fichajes'] + _caja_cr - _coste_cr:.1f} M€",
                  f"+{_caja_cr:.1f} ventas / -{_coste_cr:.1f} gasto", delta_color="off")
    else:
        c2.metric("Masa salarial", f"{club['masa_salarial_actual']:.0f} M€",
                  f"{club['masa_salarial_actual']/club['presupuesto_anual_total']*100:.0f}% del presupuesto", delta_color="off")
        c3.metric("Presupuesto fichajes", f"{club['presupuesto_fichajes']:.0f} M€")
    c4.metric("Scouting", f"{club['presupuesto_scouting']:.1f} M€")

    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        st.plotly_chart(vz.donut_budget(club), use_container_width=True)
    with col_b:
        st.plotly_chart(vz.donut_salary_cap(club), use_container_width=True)

    st.markdown("---")

    # ---------- PLANTILLA ----------
    st.markdown("### 👥 Plantilla actual")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jugadores", len(squad_view))
    c2.metric("Edad media", f"{pd.to_numeric(squad_view['edad'], errors='coerce').mean():.1f}")
    _nfm_cr = int((~squad_view['nacionalidad'].astype(str).str.strip().str.lower().isin(['mexico', 'méxico', 'mexicano', 'mexicana'])).sum())
    c3.metric("Extranjeros (NFM)", f"{_nfm_cr}/9")
    c4.metric("Valor plantilla", f"{pd.to_numeric(squad_view['valor_mercado_meur'], errors='coerce').sum():.0f} M€")

    col_a, col_b = st.columns([1.3, 1])
    with col_a:
        st.plotly_chart(vz.scatter_age_value_squad(squad_view), use_container_width=True)
        st.caption("🟢 ≤24 años (revaloriza)  🔵 25-29 años  🟠 30-31 años  🔴 ≥32 años (zona venta)")
    with col_b:
        st.plotly_chart(vz.donut_nationalities(squad_view), use_container_width=True)

    st.plotly_chart(vz.bar_salaries_squad(squad_view), use_container_width=True)

    with st.expander("Ver tabla completa de la plantilla"):
        st.dataframe(
            squad[["jugador", "posicion", "perfil_natural", "edad", "nacionalidad",
                   "minutos", "salario_meur", "valor_mercado_meur", "contrato_hasta"]],
            hide_index=True, use_container_width=True,
        )

    st.markdown("---")

    # ---------- TITULOS ----------
    st.markdown("### 🏆 Palmares")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liga MX", int(club['titulos_liga_mx']))
    c2.metric("Concachampions", int(club['titulos_concachampions']))
    c3.metric("Copa MX", int(club['titulos_copa_mx']))
    c4.metric("Ultimo titulo liga", int(club['ultimo_titulo_liga']))

    st.markdown("---")

    # ---------- ADN ----------
    st.markdown("### 🧬 ADN Rayados — ¿Que tipo de fichaje funciona aqui?")
    st.markdown(
        '<div class="info-tip">Analisis de <b>135 fichajes historicos</b> (2017-2025) etiquetados '
        'automaticamente como <b>exitosos</b>, <b>fallidos</b> o <b>en curso</b>. Criterios: '
        'recuperacion economica + bonificacion por titulos ganados.</div>',
        unsafe_allow_html=True,
    )

    # ---- Veredicto rapido ----
    conclusion = dg.adn_conclusion(adn)
    st.info(f"📌 **Veredicto general:** {conclusion}")

    # ---- Tasa de exito + distribucion de edad ----
    col_a, col_b = st.columns([1, 1.2])
    with col_a:
        st.plotly_chart(vz.donut_adn(adn), use_container_width=True)
    with col_b:
        st.plotly_chart(vz.adn_age_distribution(adn), use_container_width=True)
        st.plotly_chart(vz.adn_cost_distribution(adn), use_container_width=True)

    # ---- Liga de origen: exitos vs fallidos ----
    st.plotly_chart(vz.adn_league_chart(adn), use_container_width=True)

    # ---- Insights narrativos ----
    st.markdown("#### 🔍 Insights detectados automaticamente")
    insights = dg.analyze_adn_patterns(adn)
    if insights:
        for ins in insights:
            st.markdown(f"{ins['icono']} {ins['texto']}")
    else:
        st.caption("No se detectaron patrones claros con los datos actuales.")

    with st.expander("Ver historico completo de fichajes (135 registros)"):
        st.dataframe(
            adn[["jugador","anio_llegada","edad_llegada","nacionalidad","liga_anterior",
                  "coste_meur","coste_venta_meur","anios_en_club","etiqueta",
                  "razon_principal","titulos_ganados"]],
            hide_index=True, use_container_width=True,
        )

    st.markdown("---")

    # ---------- EXITOS (CASOS A REPETIR) ----------
    st.markdown("### 💎 Exitos historicos — los que SI debemos repetir")
    exitos = adn[adn["etiqueta"] == "exitoso"].copy()
    # ordenar por ganancia neta descendente (los que mas dinero generaron)
    exitos["ganancia_neta"] = exitos["coste_venta_meur"] - exitos["coste_meur"]
    exitos = exitos.sort_values("ganancia_neta", ascending=False)
    ganancia_total = exitos["ganancia_neta"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Fichajes exitosos", len(exitos))
    c2.metric("Inversion total", f"{exitos['coste_meur'].sum():.1f} M€")
    c3.metric("Ganancia neta", f"+{ganancia_total:.1f} M€")

    # grafico top ganadores
    st.plotly_chart(vz.adn_money_gained_chart(adn), use_container_width=True)

    # tabla detallada
    st.markdown("#### Detalle de exitos")
    cols_show_ex = ["jugador", "anio_llegada", "edad_llegada", "liga_anterior",
                    "coste_meur", "coste_venta_meur", "anios_en_club",
                    "razon_principal", "observacion"]
    cols_existen_ex = [c for c in cols_show_ex if c in exitos.columns]
    st.dataframe(
        exitos[cols_existen_ex].rename(columns={
            "jugador": "Jugador", "anio_llegada": "Año",
            "edad_llegada": "Edad", "liga_anterior": "Liga origen",
            "coste_meur": "Coste M€", "coste_venta_meur": "Vendido por M€",
            "anios_en_club": "Años", "razon_principal": "Razón",
            "observacion": "Observación",
        }),
        hide_index=True, use_container_width=True,
    )

    st.markdown("---")

    # ---------- DECEPCIONES (RIESGO HISTORICO) ----------
    st.markdown("### ⚠️ Decepciones historicas — los que NO debemos repetir")
    decepciones = adn[adn["etiqueta"] == "fallido"].sort_values("coste_meur", ascending=False)
    perdida_total = (decepciones["coste_meur"] - decepciones.get("coste_venta_meur", 0)).sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Fichajes fallidos", len(decepciones))
    c2.metric("Gasto total", f"{decepciones['coste_meur'].sum():.1f} M€")
    c3.metric("Perdida neta", f"-{perdida_total:.1f} M€")

    # grafico de perdidas individuales
    st.plotly_chart(vz.adn_money_lost_chart(adn), use_container_width=True)

    # tabla detallada
    st.markdown("#### Detalle de decepciones")
    cols_show = ["jugador", "anio_llegada", "edad_llegada", "liga_anterior",
                 "coste_meur", "coste_venta_meur", "anios_en_club",
                 "razon_principal", "observacion"]
    cols_existen = [c for c in cols_show if c in decepciones.columns]
    st.dataframe(
        decepciones[cols_existen].rename(columns={
            "jugador": "Jugador", "anio_llegada": "Año",
            "edad_llegada": "Edad", "liga_anterior": "Liga origen",
            "coste_meur": "Coste M€", "coste_venta_meur": "Vendido por M€",
            "anios_en_club": "Años", "razon_principal": "Razón",
            "observacion": "Observación",
        }),
        hide_index=True, use_container_width=True,
    )


# ====================================================================
# 3. DIAGNOSTICO COMPETITIVO (fusion de benchmark + diagnostico)
# ====================================================================
elif seccion == "📊 Diagnostico Competitivo":
    header("Diagnostico competitivo",
           "Cuanto nos falta vs el Top 4 de Liga MX, y por que")

    # ---------- EXPLICACION ----------
    with st.expander("📖 ¿Como se lee este analisis?  (clic para abrir)", expanded=True):
        st.markdown(
            "**¿Que es una brecha?**  "
            "Es la diferencia porcentual entre el rendimiento promedio de Rayados (Apertura 2024 "
            "+ Clausura 2025) y el promedio del **Top 4 de Liga MX 2025-26** "
            "(los cuatro mejores por puntos), nuestra referencia de nivel campeon.\n\n"
            "**Como leer una brecha (ejemplo):** una brecha del 15% en xG/90 querria decir que el "
            "Top 4 genera, de media, un 15% mas de ocasiones esperadas por partido que Rayados "
            "(es un ejemplo para interpretar la tabla, no un dato medido).\n\n"
            "**¿Por que es un diagnostico y no solo una medicion?**  "
            "El sistema **cruza varias metricas** para inferir la *causa raiz*. "
            "No es lo mismo que falten goles porque no llegamos al area (problema de creacion) "
            "o porque llegamos y fallamos (problema de finalizacion). El diagnostico distingue ambos."
        )

    # ---------- KPIs TOP ----------
    _fb = pd.read_csv(Path(__file__).resolve().parent / "data" / "teams_benchmark_fbref.csv")
    _ray = _fb[_fb["equipo"].astype(str).str.contains("Monterrey", case=False)].iloc[0]
    _top = _fb.sort_values("pts", ascending=False).head(4).mean(numeric_only=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Goles/90", f"{_ray['goles_90']:.2f}", f"{_ray['goles_90']-_top['goles_90']:+.2f}")
    c2.metric("Goles conc./90", f"{_ray['goles_conc_90']:.2f}", f"{_ray['goles_conc_90']-_top['goles_conc_90']:+.2f}", delta_color="inverse")
    c3.metric("Posesion %", f"{_ray['poss']:.1f}", f"{_ray['poss']-_top['poss']:+.1f}")
    c4.metric("Porterias a cero %", f"{_ray['cs_pct']:.1f}", f"{_ray['cs_pct']-_top['cs_pct']:+.1f}")

    st.markdown("---")

    # ---------- RADAR ----------
    st.markdown("### Perfil competitivo")
    rc1, rc2 = st.columns(2)
    with rc1:
        st.plotly_chart(vz.radar_team_vs_champions(bench), use_container_width=True)
    with rc2:
        st.plotly_chart(vz.radar_team_defensivo(bench), use_container_width=True)
    st.caption("Cada eje es el percentil de Rayados entre los 18 equipos de Liga MX 2025-26. Mas lejos del centro = mejor; el gris es la media del top 4.")

    st.markdown("---")

    # ---------- DIAGNOSTICOS CRUZADOS ----------
    st.markdown("### 🔬 Diagnostico de causa raiz")
    diags = dg.diagnose_v2(bench)
    diags = [d for d in diags if "porter" not in str(d.get("area", "")).lower()]  # porteria cubierta: decision deportiva, no es problema
    if not diags:
        st.success("No se detectan brechas estructurales relevantes.")
    else:
        st.markdown(f"Se identifican **{len(diags)} problemas estructurales**. "
                    "Cada uno cruza varias metricas para inferir la causa.")

        for d in diags:
            sev_cls = d["severidad"].lower()
            st.markdown(f'<div class="diag-card {sev_cls}">', unsafe_allow_html=True)

            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(f"#### {d['area']} &nbsp; {badge_html(d['severidad'])}",
                            unsafe_allow_html=True)
                st.markdown(d["causa_raiz"])
                st.markdown(
                    f"**🎯 Recomendacion:** {d['perfil_sugerido']} ({d['posicion_sugerida']})"
                )
            with cols[1]:
                # gauge con la peor brecha del diagnostico
                worst = max(d["evidencia"], key=lambda x: x[3])
                st.plotly_chart(
                    vz.gauge_brecha(worst[3], worst[0]),
                    use_container_width=True,
                    key=f"gauge_{d['area']}",
                )

            st.markdown("**Evidencia:**")
            ev_df = pd.DataFrame(d["evidencia"], columns=["Metrica", "Rayados", "Campeones", "Brecha %"])
            ev_df["Rayados"] = ev_df["Rayados"].round(2)
            ev_df["Campeones"] = ev_df["Campeones"].round(2)
            ev_df["Brecha %"] = ev_df["Brecha %"].round(1)
            st.dataframe(ev_df, hide_index=True, use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)


    # ---------- ANALISIS POR POSICION (de donde salen las necesidades) ----------
    st.markdown("### De donde salen las necesidades")
    st.caption("Comparamos a nuestros titulares (>500 min) contra los jugadores de su MISMA posicion en "
               "Liga MX. Para nivel CAMPEON no basta la mediana (p50): el objetivo es tener a todos en "
               "VERDE. Codigo de color por celda:  rojo = por debajo de p50 (urgente)  |  "
               "amarillo = p50-65 (mejorable, no alcanza para campeon)  |  verde = p65+ (sobresale).")

    _ligamx = players[players["liga"].astype(str) == "Liga MX"].copy()
    _MIN_MIN = 500

    def _pctile(pool_pos, value, col):
        if col not in pool_pos.columns:
            return None
        s = pd.to_numeric(pool_pos[col], errors="coerce").dropna()
        if s.empty or pd.isna(value):
            return None
        return int(round(100.0 * (s <= value).mean()))

    def _fmt_pct(v):
        return ("p" + str(int(round(v)))) if pd.notna(v) else "-"

    def _color_pct(v):
        if pd.isna(v):
            return "color:#9ca3af"
        if v < 50:
            return "background-color:#fca5a5; color:#7f1d1d"
        if v < 65:
            return "background-color:#fde68a; color:#78350f"
        return "background-color:#86efac; color:#065f46"

    _POS_CFG = {
        "Portero": ("Portero - paradas y seguridad",
                    [("paradas_pct", "Paradas %"), ("paradas_90", "Paradas/90"),
                     ("duelos_aereos_ganados_pct", "Aereos %")]),
        "Defensa central": ("Central - solidez (1-3) y salida de balon (4)",
                            [("duelos_aereos_ganados_pct", "Aereos %"), ("intercepciones_90", "Intercep."),
                             ("recuperaciones_90", "Recuper."), ("pases_progresivos_90", "Salida (prog.)")]),
        "Lateral": ("Laterales - defensa y ataque",
                    [("recuperaciones_90", "Recuper."), ("duelos_ganados_pct", "Duelos %"),
                     ("pases_progresivos_90", "Progresion"), ("pases_clave_90", "Pases clave"),
                     ("asistencias_90", "Asist.")]),
        "Mediocentro": ("Mediocampo - recuperacion y salida",
                        [("entradas_90", "Entradas"), ("intercepciones_90", "Intercep."),
                         ("recuperaciones_90", "Recuper."), ("duelos_ganados_pct", "Duelos %"),
                         ("pases_progresivos_90", "Progresion")]),
        "Extremo": ("Extremos - desborde y produccion (vs extremos de Liga MX por perfil)",
                    [("regates_completados_90", "Regates"), ("carreras_progresivas_90", "Conduccion"),
                     ("xa_90", "xA"), ("pases_clave_90", "Pases clave")]),
        "Delantero": ("Delantero centro - gol y finalizacion",
                      [("goles_90", "Goles"), ("xg_90", "xG"), ("tiros_area_90", "Tiros area"),
                       ("g_menos_xg_90", "G-xG")]),
    }

    def _liga_subset(_p):
        _b = _ligamx[pd.to_numeric(_ligamx["minutos"], errors="coerce").fillna(0) >= _MIN_MIN].copy()
        if _p != "Extremo":
            return _b[_b["posicion"].astype(str) == _p].copy()
        _b = _b[_b["posicion"].astype(str).isin(["Delantero", "Mediocentro", "Lateral"])].copy()
        if "desequilibrante_medalla" in _b.columns:
            _md = _b["desequilibrante_medalla"].astype(str).str.upper().isin(["BRONCE", "PLATA", "ORO"])
        else:
            _md = pd.Series(False, index=_b.index)
        _rg = pd.to_numeric(_b["regates_completados_90"], errors="coerce") if "regates_completados_90" in _b.columns else pd.Series(float("nan"), index=_b.index)
        _cr = pd.to_numeric(_b["carreras_progresivas_90"], errors="coerce") if "carreras_progresivas_90" in _b.columns else pd.Series(float("nan"), index=_b.index)
        _rq = _rg.quantile(0.70) if _rg.notna().any() else float("inf")
        _cq = _cr.quantile(0.70) if _cr.notna().any() else float("inf")
        _stt = ((_rg >= _rq) & (_cr >= _cq)).fillna(False)
        return _b[_md | _stt].copy()

    _veredictos = {}
    _SPLIT = {"Lateral", "Extremo"}
    _GRUPOS = []
    for _pos, (_titulo, _mets) in _POS_CFG.items():
        if _pos in _SPLIT and "lado" in squad.columns:
            _GRUPOS.append((_pos, "Derecho", _pos + " derecho", _titulo, _mets))
            _GRUPOS.append((_pos, "Izquierdo", _pos + " izquierdo", _titulo, _mets))
        else:
            _GRUPOS.append((_pos, None, _pos, _titulo, _mets))
    for _pos, _lado_f, _gkey, _titulo, _mets in _GRUPOS:
        _ray_pos = squad[(squad["posicion"].astype(str) == _pos) &
                         (pd.to_numeric(squad["minutos"], errors="coerce").fillna(0) >= _MIN_MIN)].copy()
        if _lado_f is not None and "lado" in _ray_pos.columns:
            _ray_pos = _ray_pos[_ray_pos["lado"].astype(str) == _lado_f]
        _liga_pos = _liga_subset(_pos)
        with st.expander(_gkey + "   (" + str(len(_ray_pos)) + " nuestros vs " +
                         str(len(_liga_pos)) + " en Liga MX)", expanded=True):
            if _ray_pos.empty or _liga_pos.empty:
                st.info("Sin datos suficientes para comparar en esta posicion (minutos < " + str(_MIN_MIN) + ").")
                continue
            _rows = []
            for _, _pl in _ray_pos.iterrows():
                _nm = str(_pl.get("jugador") or _pl.get("nombre") or "?")
                _row = {"Jugador": _nm, "Min.": int(pd.to_numeric(_pl.get("minutos"), errors="coerce") or 0)}
                _pcts = []
                for _col, _lbl in _mets:
                    _v = pd.to_numeric(pd.Series([_pl.get(_col)]), errors="coerce").iloc[0]
                    _p = _pctile(_liga_pos, _v, _col)
                    _row[_lbl] = float(_p) if _p is not None else float("nan")
                    if _p is not None:
                        _pcts.append(_p)
                _avg = (sum(_pcts) / len(_pcts)) if _pcts else None
                _row["Media"] = float(_avg) if _avg is not None else float("nan")
                _rows.append((_row, _avg if _avg is not None else 999))
            _rows.sort(key=lambda x: x[1])
            _pctcols = [_lbl for _, _lbl in _mets] + ["Media"]
            _tab = pd.DataFrame([r for r, _ in _rows])
            _sty = _tab.style.format(_fmt_pct, subset=_pctcols)
            _sty = (_sty.map(_color_pct, subset=_pctcols) if hasattr(_sty, "map")
                    else _sty.applymap(_color_pct, subset=_pctcols))
            st.dataframe(_sty, hide_index=True, use_container_width=True)

            _valid = [s for _, s in _rows if s < 999]
            _team_avg = (sum(_valid) / len(_valid)) if _valid else None
            if _team_avg is None:
                st.info("Sin percentiles calculables.")
            else:
                _ta = int(round(_team_avg))
                if _team_avg < 50:
                    _niv = "Necesidad ALTA"
                    st.error("Veredicto: titulares por DEBAJO de la mediana de Liga MX (media p" + str(_ta) +
                             "). " + _niv + " - refuerzo urgente.")
                elif _team_avg < 65:
                    _niv = "Necesidad MEDIA"
                    st.warning("Veredicto: en la media de Liga MX, pero por DEBAJO del nivel campeon p65+ "
                               "(media p" + str(_ta) + "). " + _niv + " - hay que subir el techo.")
                else:
                    _niv = "Cubierto (nivel campeon)"
                    st.success("Veredicto: a nivel campeon, p65+ (media p" + str(_ta) + "). " + _niv + ".")
                _veredictos[_gkey] = (_niv, _ta)
                if _pos == "Defensa central":
                    st.caption("La ultima columna (Salida) mide la **salida de balon** via pases progresivos: "
                               "el central moderno construye, no solo despeja. (El % de pases no venia en los "
                               "datos de plantilla, por eso se omite.)")

    st.markdown("---")

    # ---------- PLAN DE REFUERZOS PRIORITARIO ----------
    st.markdown("### Plan de refuerzos prioritario")
    st.caption("Justificado por el analisis de arriba: el orden sigue las brechas medidas vs Liga MX.")

    def _verd(pos):
        v = _veredictos.get(pos)
        return ("  -  " + v[0] + " (media p" + str(v[1]) + ")") if v else ""

    _cv_diag = float(st.session_state.get("pf_caja_ventas", 0.0))
    _PLAN_POS = [
        ("Mediocentro", "Mediocentro (organizador / box-to-box)"),
        ("Lateral izquierdo", "Lateral izquierdo"),
        ("Lateral derecho", "Lateral derecho"),
        ("Defensa central", "Defensa central con salida de balon"),
        ("Extremo izquierdo", "Extremo izquierdo"),
        ("Extremo derecho", "Extremo derecho"),
    ]
    _neces = []
    for _k, _lbl in _PLAN_POS:
        _v = _veredictos.get(_k)
        if _v and "Cubierto" not in _v[0]:
            _neces.append((_v[1], _lbl, _v[0]))
    _neces.sort(key=lambda x: x[0])
    _lineas = []
    for _i, (_p, _lbl, _niv) in enumerate(_neces, 1):
        _lineas.append(str(_i) + ". **" + _lbl + "**  -  " + _niv + " (media p" + str(_p) + ")")
    _idx_del = len(_neces) + 1
    _del = (str(_idx_del) + ". **Delantero** - solo si el dinero de ventas lo permite"
            + ("  (hoy por ventas: **%.1f M\u20ac**)" % _cv_diag if _cv_diag > 0
               else "  (marca ventas en Propuesta Final para liberar caja)."))
    _lineas.append(_del)
    st.markdown("\n".join(_lineas))
    _cub = [_lbl for _k, _lbl in _PLAN_POS if _veredictos.get(_k) and "Cubierto" in _veredictos[_k][0]]
    if _cub:
        st.caption("Ya a nivel campeon (sin refuerzo prioritario): " + ", ".join(_cub) + ".")
    st.info("Porteria: **cubierta esta temporada** (regreso de Andrada + Mele/Cardenas). "
            "Por eso no aparece como necesidad arriba.")


# ====================================================================
# 4. SCOUTING LAB (Buscador + Comparador + Riesgo + Salario)
# ====================================================================
elif seccion == "🔍 Scouting Lab":
    header("Scouting Lab",
           "Busca candidatos, comparalos con el jugador actual y estima salario")

    # --- elegir posicion y perfil ---
    col_a, col_b, col_c = st.columns(3)
    _pos_opts = ["Cualquiera"] + sorted(players["posicion"].unique()) + ["Extremo (perfil)"]
    posicion = col_a.selectbox("Posicion a reforzar", _pos_opts, index=1)
    _es_extremo = (posicion == "Extremo (perfil)")
    if posicion == "Cualquiera" or _es_extremo:
        perfiles_pos = ["Cualquiera"]
    else:
        perfiles_pos = ["Cualquiera"] + dl.get_profiles_for_position(posicion)
    perfil = col_b.selectbox("Perfil buscado", perfiles_pos,
                             index=(0 if (posicion == "Cualquiera" or _es_extremo) else 1))
    ligas_sel = col_c.multiselect("Ligas a explorar", sorted(players["liga"].unique()),
                                    default=sorted(players["liga"].unique()))

    kpi_weights = {} if perfil == "Cualquiera" else dl.get_kpis_for_profile(posicion, perfil)
    if perfil != "Cualquiera" and not kpi_weights:
        st.warning("Sin KPIs para este perfil.")
        st.stop()

    # filtros adicionales
    col_d, col_e, col_f = st.columns(3)
    edad_rng = col_d.slider("Edad", 16, 38, (20, 30))
    min_min = col_e.slider("Minutos minimos", 0, 3000, 1000, step=100)
    riesgo_max = col_f.slider("Riesgo maximo aceptable", 0, 100, 60)
    pie_sel = st.selectbox("Pie habil", ["Cualquiera", "Derecho", "Izquierdo", "Ambidiestro"],
                           help="Filtra por pierna habil. Ojo: muchos jugadores del pool no tienen el dato y quedan fuera si filtras.")

    presup_max = st.slider(
        f"Presupuesto maximo de fichaje (de {club['presupuesto_fichajes']:.0f} M€ disponibles)",
        0.0, 20.0, 8.0, step=0.5,
    )

    encaje_min = st.slider("Encaje minimo con el perfil (0 = sin filtro)", 0, 100, 0,
        help="Subelo para ver solo jugadores que encajan con el perfil elegido. Asi el perfil si cambia la lista.")
    # --- filtro por insignia ---
    col_g, col_h = st.columns(2)
    insignia_sel = col_g.selectbox("Filtrar por insignia",
        ["Cualquiera", "Tirador lejano", "Cabeceador", "Recuperador puro", "Presionador alto",
         "Definidor", "Creador", "Desequilibrante", "Muro", "Motor", "Progresor", "Paradón", "Diamante"])
    nivel_sel = col_h.selectbox("Nivel minimo de la insignia",
        ["Todas", "BRONCE", "PLATA", "ORO"])
    _OPC_INS = ["Cualquiera", "Tirador lejano", "Cabeceador", "Recuperador puro", "Presionador alto",
                "Definidor", "Creador", "Desequilibrante", "Muro", "Motor", "Progresor", "Paradón", "Diamante"]
    _ci2, _cn2, _ci3, _cn3 = st.columns(4)
    insignia_sel2 = _ci2.selectbox("Insignia 2 (opcional)", _OPC_INS, key="ins2")
    nivel_sel2    = _cn2.selectbox("Nivel 2", ["Todas", "BRONCE", "PLATA", "ORO"], key="niv2")
    insignia_sel3 = _ci3.selectbox("Insignia 3 (opcional)", _OPC_INS, key="ins3")
    nivel_sel3    = _cn3.selectbox("Nivel 3", ["Todas", "BRONCE", "PLATA", "ORO"], key="niv3")
    INSIGNIA_COL = {
        "Tirador lejano": "tirador_lejano_medalla",
        "Cabeceador": "cabeceador_medalla",
        "Recuperador puro": "recuperador_puro_medalla",
        "Presionador alto": "presionador_alto_medalla",
        "Definidor": "definidor_medalla",
        "Creador": "creador_medalla",
        "Desequilibrante": "desequilibrante_medalla",
        "Muro": "muro_medalla",
        "Motor": "motor_medalla",
        "Progresor": "progresor_medalla",
        "Paradón": "paradon_medalla",
        "Diamante": "diamante_medalla",
    }
    NIVEL_ORDEN = {"BRONCE": 1, "PLATA": 2, "ORO": 3}

    sub = players[
        (players["liga"].isin(ligas_sel))
        & (players["edad"].between(*edad_rng))
        & (players["minutos"] >= min_min)
        & (players["valor_mercado_meur"] <= presup_max)
    ].copy()
    if pie_sel != "Cualquiera" and "pie" in sub.columns:
        sub = sub[sub["pie"] == pie_sel]
    if _es_extremo:
        _base = sub["posicion"].isin(["Delantero", "Mediocentro", "Lateral"])
        if "desequilibrante_medalla" in sub.columns:
            _med = sub["desequilibrante_medalla"].astype(str).str.upper().isin(["BRONCE", "PLATA", "ORO"])
        else:
            _med = pd.Series(False, index=sub.index)
        _reg = pd.to_numeric(sub["regates_completados_90"], errors="coerce") if "regates_completados_90" in sub.columns else pd.Series(float("nan"), index=sub.index)
        _car = pd.to_numeric(sub["carreras_progresivas_90"], errors="coerce") if "carreras_progresivas_90" in sub.columns else pd.Series(float("nan"), index=sub.index)
        _rq = _reg[_base].quantile(0.70) if (_base.any() and _reg[_base].notna().any()) else float("inf")
        _cq = _car[_base].quantile(0.70) if (_base.any() and _car[_base].notna().any()) else float("inf")
        _stat = ((_reg >= _rq) & (_car >= _cq)).fillna(False)
        sub = sub[_base & (_med | _stat)]
        st.caption("'Extremo (perfil)' = jugadores de banda detectados por perfil "
                   "(medalla Desequilibrante o top 30% en regates + carreras progresivas), "
                   "porque el pool no etiqueta 'Extremo' como posicion.")
    elif posicion != "Cualquiera":
        sub = sub[sub["posicion"] == posicion]

    # aplicar filtro de insignia
    if insignia_sel != "Cualquiera":
        col_med = INSIGNIA_COL[insignia_sel]
        if col_med in sub.columns:
            if nivel_sel == "Todas":
                sub = sub[sub[col_med].isin(["BRONCE", "PLATA", "ORO"])]
            else:
                min_niv = NIVEL_ORDEN[nivel_sel]
                sub = sub[sub[col_med].map(lambda m: NIVEL_ORDEN.get(m, 0)) >= min_niv]
    # filtros de insignia 2 y 3 (combinadas con Y)
    for _ins, _niv in [(insignia_sel2, nivel_sel2), (insignia_sel3, nivel_sel3)]:
        if _ins == "Cualquiera":
            continue
        _cm = INSIGNIA_COL.get(_ins)
        if _cm and _cm in sub.columns:
            if _niv == "Todas":
                sub = sub[sub[_cm].isin(["BRONCE", "PLATA", "ORO"])]
            else:
                _mn = NIVEL_ORDEN[_niv]
                sub = sub[sub[_cm].map(lambda m: NIVEL_ORDEN.get(m, 0)) >= _mn]

    if sub.empty:
        st.warning("Sin candidatos con esos filtros. Relaja los rangos.")
        st.stop()

    if perfil == "Cualquiera":
        evaluated = sc.evaluate_players_any(sub)
    else:
        evaluated = sc.evaluate_players(sub, kpi_weights, position=None)
    evaluated = evaluated[evaluated["score_riesgo"] <= riesgo_max]
    evaluated = evaluated[evaluated["score_encaje"] >= encaje_min]
    evaluated = sc.add_salary_estimates(evaluated)

    st.markdown(f"### 🎯 {len(evaluated)} candidatos para *{perfil}*")

    with st.expander("Que significan Encaje, Riesgo y Final?"):
        st.markdown(
            "- **Encaje (0-100)**: que tan bien encaja el jugador con lo que Rayados "
            "necesita en esa posicion y perfil. Mas alto = mejor ajuste.\n"
            "- **Riesgo (0-100)**: que tan arriesgado es el fichaje (edad alta, pocos "
            "minutos, lesiones, salto grande de liga). Mas bajo = mas seguro.\n"
            "- **Final (0-100)**: nota global que premia el encaje y penaliza el riesgo. "
            "Es el numero con el que se ordena el ranking."
        )

    # ---------- TABLA RANKING (AgGrid) ----------
    _disp = evaluated.copy()
    _disp["salario_esperado_meur"] = ((pd.to_numeric(_disp["salario_min_meur"], errors="coerce")
                                       + pd.to_numeric(_disp["salario_max_meur"], errors="coerce")) / 2).round(2)
    cols_show = ["nombre", "edad", "nacionalidad", "liga", "club", "pie", "minutos",
                 "perfil_natural", "medallas", "valor_mercado_meur",
                 "salario_esperado_meur", "score_final"]
    _ren = {"nombre": "Jugador", "edad": "Edad", "nacionalidad": "Nac.", "liga": "Liga", "club": "Club",
            "minutos": "Min.", "pie": "Pie", "perfil_natural": "Perfil", "medallas": "Insignias",
            "valor_mercado_meur": "Valor M\u20ac", "salario_esperado_meur": "Salario esp.", "score_final": "Final"}
    _tab = _disp[[x for x in cols_show if x in _disp.columns]].rename(columns=_ren)

    _AGGRID_OK = True
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
    except Exception:
        _AGGRID_OK = False

    if _AGGRID_OK and not _tab.empty:
        st.caption("Clic en un encabezado ordena por esa columna. Manten Shift y clic en otra para "
                   "encadenar el desempate (ej: Club y luego Salario). Cada columna trae su filtro. "
                   "Marca casillas a la izquierda para elegir jugadores.")
        _gb = GridOptionsBuilder.from_dataframe(_tab)
        _gb.configure_default_column(sortable=True, filter=True, resizable=True, floatingFilter=True)
        _gb.configure_selection("multiple", use_checkbox=True, header_checkbox=True)
        _gb.configure_grid_options(multiSortKey="shift")
        for _nc in ["Valor M\u20ac", "Salario esp.", "Final", "Edad", "Min."]:
            if _nc in _tab.columns:
                _gb.configure_column(_nc, type=["numericColumn"])
        _grid = AgGrid(_tab, gridOptions=_gb.build(),
                       update_mode=GridUpdateMode.SELECTION_CHANGED,
                       data_return_mode=DataReturnMode.AS_INPUT,
                       fit_columns_on_grid_load=False, allow_unsafe_jscode=True,
                       height=460, theme="streamlit", key="aggrid_ranking")
        _sel = _grid.get("selected_rows", None)
        if isinstance(_sel, pd.DataFrame):
            _sel_names = _sel["Jugador"].astype(str).tolist() if ("Jugador" in _sel.columns and not _sel.empty) else []
        elif isinstance(_sel, list):
            _sel_names = [str(r.get("Jugador")) for r in _sel if isinstance(r, dict) and r.get("Jugador")]
        else:
            _sel_names = []
        st.session_state["_aggrid_sel_names"] = _sel_names
        if _sel_names:
            st.success("Seleccionados (" + str(len(_sel_names)) + "): " + ", ".join(_sel_names))
        else:
            st.caption("Sin seleccion todavia.")
    else:
        if not _AGGRID_OK:
            st.warning("AgGrid no esta disponible (pip install streamlit-aggrid). Muestro la tabla normal.")
        st.dataframe(_tab.astype(str), use_container_width=True, hide_index=True)
        st.session_state["_aggrid_sel_names"] = []

    # ---------- GUARDAR BUSQUEDA / LISTAS ----------
    if "listas" not in st.session_state:
        st.session_state["listas"] = []
    if "_lst_seq" not in st.session_state:
        st.session_state["_lst_seq"] = 0

    try:
        _ins_pairs = [(insignia_sel, nivel_sel), (insignia_sel2, nivel_sel2), (insignia_sel3, nivel_sel3)]
        _ins_txt = ", ".join(str(_i) + ">=" + str(_n) for _i, _n in _ins_pairs if str(_i) != "Cualquiera")
        _filtro_label = ("Pos: " + str(posicion) + " | Edad " + str(edad_rng[0]) + "-" + str(edad_rng[1]) +
                         " | Perfil: " + str(perfil))
        if _ins_txt:
            _filtro_label += " | Insignias: " + _ins_txt
    except Exception:
        _filtro_label = "(filtros actuales)"

    _sel_names = st.session_state.get("_aggrid_sel_names", [])

    st.markdown("#### Listas de scouting")
    st.caption("Guarda este set de filtros como una Lista, y mete a ella los jugadores que marcaste "
               "con las casillas de la tabla. En Propuesta Final eliges tu top-3 de cada Lista.")

    g1, g2 = st.columns([3, 2])
    _new_name = g1.text_input("Nombre de la busqueda", key="lst_new_name",
                              placeholder="Ej: Mediocentro defensivo")
    if g2.button("Guardar busqueda como Lista", key="lst_save"):
        if not _new_name.strip():
            st.warning("Ponle un nombre a la busqueda.")
        else:
            st.session_state["_lst_seq"] += 1
            st.session_state["listas"].append({
                "id": "L" + str(st.session_state["_lst_seq"]),
                "nombre": _new_name.strip(),
                "filtros": _filtro_label,
                "jugadores": [],
                "prioridad": [],
            })
            st.success("Lista '" + _new_name.strip() + "' creada con estos filtros.")
            try:
                st.rerun()
            except Exception:
                st.rerun()

    if st.session_state["listas"]:
        _lnames = [l["nombre"] for l in st.session_state["listas"]]
        a1, a2 = st.columns([3, 2])
        _active = a1.selectbox("Lista activa (a donde se anaden)", _lnames, key="lst_active")
        _btn_txt = "Anadir seleccionados (" + str(len(_sel_names)) + ")"
        if a2.button(_btn_txt, key="lst_add_sel"):
            if not _sel_names:
                st.warning("No marcaste jugadores en la tabla de arriba (casillas de la izquierda).")
            else:
                _lst = next((l for l in st.session_state["listas"] if l["nombre"] == _active), None)
                if _lst is not None:
                    _have = {j["nombre"] for j in _lst["jugadores"]}
                    _added = 0
                    for nm in _sel_names:
                        if nm in _have:
                            continue
                        _r = evaluated[evaluated["nombre"].astype(str) == nm]
                        if _r.empty:
                            continue
                        _r = _r.iloc[0]
                        _lst["jugadores"].append({
                            "nombre": nm,
                            "posicion": str(_r.get("posicion", "")),
                            "club": str(_r.get("club", "")),
                            "liga": str(_r.get("liga", "")),
                            "edad": int(pd.to_numeric(_r.get("edad"), errors="coerce") or 0),
                            "pie": str(_r.get("pie", "s/d")),
                            "nacionalidad": str(_r.get("nacionalidad", "")),
                            "valor_mercado_meur": float(pd.to_numeric(_r.get("valor_mercado_meur"), errors="coerce") or 0),
                            "score_final": float(pd.to_numeric(_r.get("score_final"), errors="coerce") or 0),
                        })
                        _added += 1
                    st.success("Anadidos " + str(_added) + " a '" + _active + "'. Total: " + str(len(_lst["jugadores"])) + ".")
        st.caption("Tus listas: " + ", ".join(l["nombre"] + " (" + str(len(l["jugadores"])) + ")" for l in st.session_state["listas"]))
    else:
        st.info("Aun no tienes listas. Guarda tu primera busqueda arriba.")

    # ---------- MAPAS ----------
    if len(evaluated) >= 3:
        col1, col2 = st.columns(2)
        with col1:
            st.empty()
        with col2:
            st.empty()

    st.markdown("---")

    # ---------- COMPARADOR POR POSICION vs JUGADOR ACTUAL ----------
    st.markdown("### Comparar candidato con jugador actual de Rayados")

    BUCKET = {
        "Delantero": "DELANTERO", "Extremo": "DELANTERO",
        "Mediocentro": "MEDIO", "Lateral": "LATERAL",
        "Defensa central": "DEFENSA",
    }
    EJES_POS = {
        "DELANTERO": [("goles_90", "Goles/90"), ("xg_90", "xG/90"),
                      ("g_menos_xg_90", "G-xG/90"), ("tiros_90", "Tiros/90"),
                      ("tiros_area_90", "Tiros area/90"), ("xa_90", "xA/90"),
                      ("pases_clave_90", "Pases clave/90"),
                      ("regates_completados_90", "Regates/90"),
                      ("recuperaciones_90", "Recuperac./90")],
        "MEDIO": [("pases_clave_90", "Pases clave/90"), ("xa_90", "xA/90"),
                  ("asistencias_90", "Asist./90"), ("xg_90", "xG/90"),
                  ("regates_completados_90", "Regates/90"),
                  ("recuperaciones_90", "Recuperac./90"),
                  ("intercepciones_90", "Intercep./90"),
                  ("duelos_ganados_pct", "Duelos %")],
        "LATERAL": [("xa_90", "xA/90"), ("pases_clave_90", "Pases clave/90"),
                    ("asistencias_90", "Asist./90"),
                    ("regates_completados_90", "Regates/90"),
                    ("entradas_90", "Entradas/90"),
                    ("intercepciones_90", "Intercep./90"),
                    ("recuperaciones_90", "Recuperac./90"),
                    ("duelos_ganados_pct", "Duelos %")],
        "Extremo": [("regates_completados_90", "Regates/90"),
                    ("carreras_progresivas_90", "Conduccion/90"),
                    ("xa_90", "xA/90"),
                    ("asistencias_90", "Asist./90"),
                    ("pases_clave_90", "Pases clave/90"),
                    ("centros_completados_pct", "Centros %")],
        "DEFENSA": [("despejes_90", "Despejes/90"),
                    ("duelos_aereos_ganados_pct", "Duelos aereos %"),
                    ("intercepciones_90", "Intercep./90"),
                    ("entradas_90", "Entradas/90"),
                    ("recuperaciones_90", "Recuperac./90"),
                    ("duelos_ganados_pct", "Duelos %")],
    }

    # fix_radar_extremo_match
    posicion = "Extremo" if str(posicion) == "Extremo (perfil)" else posicion
    rayados_pos = squad[squad["posicion"] == posicion]
    bucket = BUCKET.get(posicion)
    if posicion == "Portero":
        st.info("El radar por posicion es para jugadores de campo. Los porteros se "
                "valoran por % de paradas y paradas/90 en la ficha de plantilla.")
    elif rayados_pos.empty:
        st.warning("No hay jugadores de '" + str(posicion) + "' en la plantilla actual.")
    elif bucket is None:
        st.warning("Selecciona una posicion concreta para ver el radar por posicion.")
    else:
        col_x, col_y = st.columns(2)
        actual = col_x.selectbox("Jugador actual Rayados", rayados_pos["jugador"].tolist())
        candidato = col_y.selectbox("Candidato externo", evaluated["nombre"].tolist())
        cur = squad[squad["jugador"] == actual].iloc[0]
        cand = evaluated[evaluated["nombre"] == candidato].iloc[0]
        ejes = EJES_POS[bucket]
        st.plotly_chart(
            vz.radar_player_position(cur, cand, players, squad, ejes,
                                     name_cur=actual, name_cand=candidato),
            use_container_width=True, key="radar_pos")
        st.caption("Cada eje es el percentil del jugador DENTRO de su propia liga. "
                   "La forma revela el tipo de jugador.")
        st.markdown("#### Encaje por perfil de la posicion (0-100, lado a lado)")
        fit = vz.profile_fit_table(cur, cand, players, squad, posicion,
                                   name_cur=actual, name_cand=candidato)
        st.dataframe(fit.astype(str), hide_index=True, use_container_width=True)
        st.markdown("#### Datos numericos")
        compare_show = pd.DataFrame({
            "Aspecto": ["Edad", "Minutos", "Liga", "Valor mercado (M EUR)",
                        "Salario actual / estimado (M EUR)"],
            actual: [int(cur["edad"]), int(cur["minutos"]), "Liga MX",
                     cur["valor_mercado_meur"], cur["salario_meur"]],
            candidato: [int(cand["edad"]), int(cand["minutos"]), cand["liga"],
                        cand["valor_mercado_meur"],
                        str(cand["salario_min_meur"]) + " - " + str(cand["salario_max_meur"])],
        }).astype(str)
        st.dataframe(compare_show, hide_index=True, use_container_width=True)
        diff_salario_med = ((cand["salario_min_meur"] + cand["salario_max_meur"]) / 2) - cur["salario_meur"]
        if cand["score_final"] >= 75:
            verdict = "Mejora deportiva clara."
        elif cand["score_final"] >= 65:
            verdict = "Mejora moderada, evaluar coste."
        else:
            verdict = "No supera al titular actual en el perfil objetivo."
        st.markdown(
            "**Veredicto:** " + verdict + "  \n"
            "Diferencia salarial estimada: **" + format(diff_salario_med, "+.2f") + " M EUR/ano** "
            "(media del rango candidato vs salario actual).")

    # ---------- ENCAJE FINAL / PRECIO ----------
    st.markdown("---")
    st.markdown("#### Encaje Final / Precio")
    st.caption("Cada candidato segun su Encaje Final (nota global) y su precio de mercado. "
               "Alto encaje y bajo precio = mejor relacion.")
    if len(evaluated) >= 3:
        st.plotly_chart(vz.scatter_value_score(evaluated), use_container_width=True,
                        key="scatter_encaje_precio")
    else:
        st.info("Se necesitan al menos 3 candidatos para el mapa Encaje Final / Precio.")

# ====================================================================
# 5. PROPUESTA FINAL
# ====================================================================
elif seccion == "📋 Propuesta Final":
    header("Propuesta final de mercado",
           "A quien fichar, a quien vender y como cuadrar el presupuesto")

    diags = dg.diagnose_v2(bench)
    summary = dg.executive_summary(diags)

    # ---------- RESUMEN ----------
    st.markdown("### 📌 Resumen ejecutivo")
    # fix_resumen_propuesta
    st.info(
        "**Estrategia de mercado:** liberar masa salarial y caja vendiendo a los jugadores caros, mayores o sin minutos, y reinvertir esa caja en fichajes jovenes e infravalorados con potencial de revalorizacion. El objetivo: subir el nivel competitivo respetando presupuesto y reglas de Liga MX."
    )

    # fix_quitar_stop_propuesta (antes: if not diags: st.stop() -> ocultaba toda la Propuesta)

    # ---------- PLAN DE VENTAS (INTERACTIVO) ----------
    st.markdown("### Plan de ventas y cesiones (interactivo)")
    st.caption("Marca 'Vender' para traspasar (entra valor a la caja + libera 100% del salario) o 'Ceder' "
               "para prestar (no entra valor, pero el club destino cubre un % del salario, ajustable en la "
               "columna). La caja y el salario liberado se recalculan solos.")
    _pl = squad[["jugador", "posicion", "edad", "nacionalidad",
                 "valor_mercado_meur", "salario_meur"]].copy()
    _pl = _pl.rename(columns={
        "jugador": "Jugador", "posicion": "Pos.", "edad": "Edad", "nacionalidad": "Nac.",
        "valor_mercado_meur": "Valor M\u20ac", "salario_meur": "Salario M\u20ac"})
    _saved = st.session_state.get("pf_plan_ventas", None)
    def _dflt_v(n):
        if _saved is None: return n in ["L. Ocampos", "G. Berterame"]
        return bool(_saved.get(n, {}).get("vender", False))
    def _dflt_c(n):
        if _saved is None: return False
        return bool(_saved.get(n, {}).get("ceder", False))
    def _dflt_p(n):
        if _saved is None: return 50
        return int(_saved.get(n, {}).get("pct", 50))
    _pl.insert(0, "Vender", _pl["Jugador"].map(_dflt_v))
    _pl.insert(1, "Ceder", _pl["Jugador"].map(_dflt_c))
    _pl.insert(2, "% paga destino", _pl["Jugador"].map(_dflt_p))
    _ed = st.data_editor(
        _pl, hide_index=True, use_container_width=True, key="editor_ventas",
        column_config={
            "Vender": st.column_config.CheckboxColumn("Vender", default=False),
            "Ceder": st.column_config.CheckboxColumn("Ceder", default=False),
            "% paga destino": st.column_config.NumberColumn(
                "% paga destino", min_value=0, max_value=100, step=5, default=50,
                help="Solo aplica si marcas Ceder: que % del salario cubre el club que lo recibe."),
        },
        disabled=["Jugador", "Pos.", "Edad", "Nac.", "Valor M\u20ac", "Salario M\u20ac"])

    _bs1, _bs2 = st.columns([1, 2])
    if _bs1.button("💾 Guardar decision de ventas/cesiones"):
        _plan = {}
        for _, _r in _ed.iterrows():
            _plan[_r["Jugador"]] = {"vender": bool(_r["Vender"]),
                                    "ceder": bool(_r["Ceder"]),
                                    "pct": int(_r["% paga destino"])}
        st.session_state["pf_plan_ventas"] = _plan
        st.success("Decision guardada: se mantiene aunque cambies de seccion.")
    if "pf_plan_ventas" in st.session_state:
        _ng = sum(1 for v in st.session_state["pf_plan_ventas"].values()
                  if v.get("vender") or v.get("ceder"))
        _bs2.caption("✅ Decision de ventas guardada (" + str(_ng) + " jugadores).")
    else:
        _bs2.caption("Sin guardar. Pulsa Guardar para que no se reinicie al cambiar de seccion.")
    _sel_vender = _ed["Vender"].astype(bool)
    _sel_ceder = _ed["Ceder"].astype(bool) & (~_sel_vender)
    _vend = _ed[_sel_vender]
    _ced = _ed[_sel_ceder]

    candidatos_venta = squad[squad["jugador"].isin(_vend["Jugador"])]
    caja_ventas = float(_vend["Valor M\u20ac"].sum())
    ahorro_venta = float(_vend["Salario M\u20ac"].sum())
    _pct = pd.to_numeric(_ced["% paga destino"], errors="coerce").fillna(0) / 100.0
    ahorro_cesion = float((pd.to_numeric(_ced["Salario M\u20ac"], errors="coerce").fillna(0) * _pct).sum())
    ahorro_salarial = ahorro_venta + ahorro_cesion
    presup_total = float(club["presupuesto_fichajes"]) + caja_ventas
    st.session_state["pf_caja_ventas"] = float(caja_ventas)
    st.session_state["pf_ahorro_salarial"] = float(ahorro_salarial)
    st.session_state["pf_n_vende"] = int(len(_vend))
    st.session_state["pf_n_cede"] = int(len(_ced))
    st.session_state["pf_n_fichajes"] = 0
    st.session_state["pf_coste_fichajes"] = 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja por ventas", f"{caja_ventas:.1f} M\u20ac")
    c2.metric("Salario liberado / ano", f"{ahorro_salarial:.1f} M\u20ac")
    c3.metric("  -> por cesiones", f"{ahorro_cesion:.1f} M\u20ac")
    c4.metric("Presupuesto total", f"{presup_total:.1f} M\u20ac", f"+{caja_ventas:.1f} vs base")
    if len(_vend):
        st.success("Vendiendo: " + ", ".join(_vend["Jugador"].tolist()))
    if len(_ced):
        st.info("Cediendo: " + ", ".join(_ced["Jugador"].tolist()) +
                "  (libera " + f"{ahorro_cesion:.2f}" + " M\u20ac de salario)")
    if not len(_vend) and not len(_ced):
        st.info("Aun no marcaste ventas ni cesiones. Marca 'Vender' o 'Ceder' arriba.")
    st.markdown("---")

    # ---------- PROPUESTA: LISTAS Y TOP-3 ----------
    st.markdown("### Propuesta final por Listas")
    st.caption("Cada Lista = una necesidad. Elige hasta 3 candidatos en orden de prioridad. "
               "Se ficha el #1; el #2 y #3 son alternativas (plan B) si no llega el primero. "
               "El coste y el conteo cuentan SOLO el #1 de cada Lista.")
    if "listas" not in st.session_state:
        st.session_state["listas"] = []

    _presup_total = club["presupuesto_fichajes"] + caja_ventas
    st.markdown("**Caja disponible: " + str(round(_presup_total, 1)) + " M\u20ac**")

    if not st.session_state["listas"]:
        st.warning("No has creado ninguna Lista todavia. Ve a Scouting Lab, guarda una busqueda y anade jugadores.")
    else:
        _propuesta_global = []
        for _lst in st.session_state["listas"]:
            with st.expander(_lst["nombre"] + "  (" + str(len(_lst["jugadores"])) + " candidatos)", expanded=True):
                # fix_borrar_listas (borrar individual)
                _cdel1, _cdel2 = st.columns([4, 1])
                if _cdel2.button("Borrar", key="del_lst_" + str(_lst.get("id", _lst["nombre"]))):
                    st.session_state["listas"] = [
                        _x for _x in st.session_state["listas"]
                        if _x.get("id", _x["nombre"]) != _lst.get("id", _lst["nombre"])
                    ]
                    st.rerun()
                st.caption("Filtros: " + str(_lst.get("filtros", "-")))
                # fix_comparar_seleccionados
                if st.button("Comparar seleccionados", key="cmp_lst_" + str(_lst.get("id", _lst["nombre"]))):
                    _nombres_sel = [str(_j.get("nombre", "")) for _j in _lst.get("jugadores", [])]
                    if len(_nombres_sel) < 2:
                        st.info("Necesitas al menos 2 jugadores en la Lista para comparar.")
                    else:
                        _cmp = players[players["nombre"].astype(str).isin(_nombres_sel)].copy()
                        if _cmp.empty:
                            st.warning("No encontre a estos jugadores en el pool.")
                        else:
                            _cols_cmp = [c for c in ["nombre", "club", "liga", "perfil_natural",
                                         "edad", "pie", "minutos", "valor_mercado_meur",
                                         "salario_meur", "medallas"] if c in _cmp.columns]
                            _tab = _cmp[_cols_cmp].rename(columns={
                                "perfil_natural": "perfil", "valor_mercado_meur": "valor M\u20ac",
                                "salario_meur": "salario M\u20ac", "medallas": "insignias"})
                            st.dataframe(_tab.set_index("nombre"), use_container_width=True)
                            st.caption("Comparativa de los " + str(len(_tab)) + " seleccionados de esta Lista.")
                _js = _lst["jugadores"]
                if not _js:
                    st.info("Esta Lista no tiene jugadores aun. Anadelos desde Scouting Lab.")
                    continue
                _df = pd.DataFrame(_js)
                _cols = [x for x in ["nombre", "club", "liga", "edad", "pie", "nacionalidad",
                                     "valor_mercado_meur", "score_final"] if x in _df.columns]
                _ren = {"nombre": "Jugador", "club": "Club", "liga": "Liga", "edad": "Edad", "pie": "Pie",
                        "nacionalidad": "Nac.", "valor_mercado_meur": "Valor M\u20ac", "score_final": "Final"}
                st.dataframe(_df[_cols].rename(columns=_ren).astype(str), hide_index=True, use_container_width=True)

                _names = [j["nombre"] for j in _js]
                st.markdown("**Tu top-3 (orden de prioridad):**")
                p1, p2, p3 = st.columns(3)
                _sp = _lst.get("prioridad", [])
                _o1 = ["(vacio)"] + _names
                _k1 = "pri1_" + _lst["id"]
                if _k1 not in st.session_state and len(_sp) > 0 and _sp[0] in _o1:
                    st.session_state[_k1] = _sp[0]
                _c1 = p1.selectbox("#1", _o1, key=_k1)
                _o2 = ["(vacio)"] + [n for n in _names if n != _c1]
                _k2 = "pri2_" + _lst["id"]
                if _k2 not in st.session_state and len(_sp) > 1 and _sp[1] in _o2:
                    st.session_state[_k2] = _sp[1]
                _c2 = p2.selectbox("#2", _o2, key=_k2)
                _o3 = ["(vacio)"] + [n for n in _names if n not in (_c1, _c2)]
                _k3 = "pri3_" + _lst["id"]
                if _k3 not in st.session_state and len(_sp) > 2 and _sp[2] in _o3:
                    st.session_state[_k3] = _sp[2]
                _c3 = p3.selectbox("#3", _o3, key=_k3)
                _pri = [x for x in [_c1, _c2, _c3] if x != "(vacio)"]
                _lst["prioridad"] = _pri
                if _pri:
                    if len(_pri) > 1:
                        st.success("Ficha el #1: " + _pri[0] +
                                   "   ·   alternativas (plan B) si no llega: " + "  >  ".join(_pri[1:]))
                    else:
                        st.success("Ficha el #1: " + _pri[0])
                    _row = next((j for j in _js if j["nombre"] == _pri[0]), None)
                    if _row:
                        _propuesta_global.append((_pri[0], float(_row.get("valor_mercado_meur", 0) or 0)))

        st.markdown("---")
        st.markdown("### Resumen economico de la propuesta")
        if _propuesta_global:
            _dedup = {}
            for nm, v in _propuesta_global:
                _dedup[nm] = max(_dedup.get(nm, 0.0), v)
            _coste = sum(_dedup.values())
            _bal = _presup_total - _coste
            st.session_state["pf_n_fichajes"] = int(len(_dedup))
            st.session_state["pf_coste_fichajes"] = float(_coste)
            m1, m2, m3 = st.columns(3)
            m1.metric("Caja disponible", str(round(_presup_total, 1)) + " M\u20ac")
            m2.metric("Coste de la propuesta", str(round(_coste, 1)) + " M\u20ac")
            m3.metric("Balance", ("+" if _bal >= 0 else "") + str(round(_bal, 1)) + " M\u20ac")
            st.caption("Elegidos: " + ", ".join(_dedup.keys()))
            if _bal < 0:
                st.warning("Te pasas por " + str(round(abs(_bal), 1)) + " M\u20ac. Baja un candidato o vende/cede a alguien.")
            else:
                st.success("Propuesta viable. Margen: " + str(round(_bal, 1)) + " M\u20ac.")
        else:
            st.info("Elige al menos un #1 en alguna Lista para ver el balance.")

    # === VALIDADOR_INOUT (auto) ===
    st.markdown("---")
    st.markdown("### 🔎 Validacion de plantilla (reglas Liga MX 2026-27)")
    import unicodedata as _ud
    def _nz(s):
        return pd.to_numeric(s, errors="coerce")
    def _norm(x):
        x = str(x).strip().lower()
        return "".join(c for c in _ud.normalize("NFD", x) if _ud.category(c) != "Mn")

    _out_names = list(_vend["Jugador"]) + list(_ced["Jugador"])
    _in_names = []
    for _l in st.session_state.get("listas", []):
        _pr = list(_l.get("prioridad", []))
        if _pr:
            _in_names.append(_pr[0])
    _seen = set(); _in_names = [n for n in _in_names if not (n in _seen or _seen.add(n))]

    _pname = "nombre" if "nombre" in players.columns else ("jugador" if "jugador" in players.columns else players.columns[0])
    _entran = players[players[_pname].isin(_in_names)].copy()
    _salen = squad[squad["jugador"].isin(_out_names)].copy()
    _quedan = squad[~squad["jugador"].isin(_out_names)].copy()

    def _sal(df):
        if "salario_meur" in df.columns and _nz(df["salario_meur"]).fillna(0).abs().sum() > 0:
            return _nz(df["salario_meur"])
        lo = _nz(df["salario_min_meur"]) if "salario_min_meur" in df.columns else None
        hi = _nz(df["salario_max_meur"]) if "salario_max_meur" in df.columns else None
        if lo is not None and hi is not None:
            return (lo + hi) / 2.0
        return pd.Series([float("nan")] * len(df), index=df.index)

    _pos_fin = list(_quedan["posicion"]) + (list(_entran["posicion"]) if "posicion" in _entran.columns else [])
    _edad_all = list(_nz(_quedan["edad"])) + (list(_nz(_entran["edad"])) if "edad" in _entran.columns else [])
    _nac_fin = list(_quedan["nacionalidad"]) + (list(_entran["nacionalidad"]) if "nacionalidad" in _entran.columns else [])
    _es = pd.Series([e for e in _edad_all if pd.notna(e)])

    _total = len(_pos_fin)
    _porteros = sum(1 for p in _pos_fin if _norm(p) == "portero")
    _nfm = sum(1 for n in _nac_fin if _norm(n) not in ("mexico", "mexicano", "mexicana"))
    _sub23 = int((_es <= 23).sum()) if len(_es) else 0
    _may30 = int((_es >= 30).sum()) if len(_es) else 0
    _edadm = round(float(_es.mean()), 1) if len(_es) else 0.0

    _reglas = [
        ("Plantilla total", _total, "<= 25", _total <= 25),
        ("Porteros", _porteros, "= 3", _porteros == 3),
        ("NFM / extranjeros", _nfm, "<= 9", _nfm <= 9),
        ("Sub-23 (edad<=23)", _sub23, ">= 4", _sub23 >= 4),
        ("Edad media", _edadm, "~ 26.5", abs(_edadm - 26.5) <= 1.5),
    ]
    if all(r[3] for r in _reglas) and _total > 0:
        st.success("PROPUESTA VALIDA: la plantilla resultante cumple las reglas comprobables de Liga MX.")
    else:
        st.error("PROPUESTA NO VALIDA todavia: ajusta lo que salga en rojo (vende/cede o ficha distinto).")

    _vdf = pd.DataFrame(
        [{"Regla": r[0], "Actual": r[1], "Limite": r[2], "Cumple": ("OK" if r[3] else "NO")} for r in _reglas])
    def _color_reglas(_row):
        _ok = (_row["Cumple"] == "OK")
        _bg = ("background-color: #DCFCE7; color: #166534; font-weight: 600" if _ok
               else "background-color: #FEE2E2; color: #991B1B; font-weight: 600")
        return [_bg] * len(_row)
    st.dataframe(_vdf.style.apply(_color_reglas, axis=1), hide_index=True, use_container_width=True)

    # fix_validacion_plantilla (extremo cuenta dentro de delantero; ideal delantero=6)
    _ideal = {"portero": 3, "defensa central": 4, "lateral": 4, "mediocentro": 6, "delantero": 6}
    _cnt = {}
    for _p in _pos_fin:
        _k = _norm(_p)
        if _k == "extremo":
            _k = "delantero"
        _cnt[_k] = _cnt.get(_k, 0) + 1
    st.markdown("**Distribucion por posicion (resultante vs ideal):**")
    _ddf = pd.DataFrame(
        [{"Posicion": k.title(), "Actual": _cnt.get(k, 0), "Ideal": v,
          "Estado": ("OK" if _cnt.get(k, 0) == v else "ajustar")} for k, v in _ideal.items()])
    def _color_dist(_row):
        _diff = abs(_row["Actual"] - _row["Ideal"])
        if _diff == 0:
            _bg = "background-color: #DCFCE7; color: #166534; font-weight: 600"
        elif _diff == 1:
            _bg = "background-color: #FEF3C7; color: #92400E"
        else:
            _bg = "background-color: #FEE2E2; color: #991B1B; font-weight: 600"
        return [_bg] * len(_row)
    st.dataframe(_ddf.style.apply(_color_dist, axis=1), hide_index=True, use_container_width=True)
    st.caption("Pendiente de dato: 'cantera Rayados >= 6' (no hay marca de canterano) y reglas de "
               "alineacion (7 NFM / 4 FM en cancha, minutos de menores). Si un fichaje del pool no "
               "trae posicion 'Extremo', esa fila es orientativa.")

    st.markdown("### Comparativa IN / OUT")
    def _resumen(df):
        if df is None or len(df) == 0:
            return {"n": 0, "edad": None, "sal": None, "val": None, "nombres": []}
        ed = _nz(df["edad"]) if "edad" in df.columns else pd.Series(dtype=float)
        va = _nz(df["valor_mercado_meur"]) if "valor_mercado_meur" in df.columns else pd.Series(dtype=float)
        sa = _sal(df)
        nc = "jugador" if "jugador" in df.columns else ("nombre" if "nombre" in df.columns else None)
        return {"n": len(df),
                "edad": round(float(ed.mean()), 1) if ed.notna().any() else None,
                "sal": round(float(sa.mean()), 2) if sa.notna().any() else None,
                "val": round(float(va.mean()), 1) if va.notna().any() else None,
                "nombres": (list(df[nc]) if nc else [])}
    _o = _resumen(_salen); _i = _resumen(_entran)
    def _d(a, b):
        if a is None or b is None: return "-"
        x = round(b - a, 2); return ("+" if x >= 0 else "") + str(x)
    st.dataframe(pd.DataFrame([
        {"Metrica": "Jugadores", "Salen (OUT)": _o["n"], "Entran (IN)": _i["n"], "Dif (IN-OUT)": _i["n"] - _o["n"]},
        {"Metrica": "Edad media", "Salen (OUT)": _o["edad"], "Entran (IN)": _i["edad"], "Dif (IN-OUT)": _d(_o["edad"], _i["edad"])},
        {"Metrica": "Salario medio (M\u20ac)", "Salen (OUT)": _o["sal"], "Entran (IN)": _i["sal"], "Dif (IN-OUT)": _d(_o["sal"], _i["sal"])},
        {"Metrica": "Valor mercado medio (M\u20ac)", "Salen (OUT)": _o["val"], "Entran (IN)": _i["val"], "Dif (IN-OUT)": _d(_o["val"], _i["val"])},
    ]), hide_index=True, use_container_width=True)
    st.markdown("**Salen:** " + (", ".join(map(str, _o["nombres"])) if _o["nombres"] else "(nadie aun)"))
    st.markdown("**Entran:** " + (", ".join(map(str, _i["nombres"])) if _i["nombres"] else "(nadie aun)"))
    # === FIN VALIDADOR_INOUT ===

