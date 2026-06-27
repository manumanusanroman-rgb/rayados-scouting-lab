"""
diagnostics.py
--------------
Diagnostico v2: NO solo mide brecha vs campeones,
sino que CRUZA varias metricas para inferir la causa raiz del problema.

Logica clave:
- xG bajo + tiros bajos    -> problema de GENERACION (no llegamos)
- xG bajo + tiros altos    -> problema de CALIDAD DE TIRO (tiramos desde lejos)
- xG normal + goles bajos  -> problema de FINALIZACION (generamos pero fallamos)
- xGA alto + tiros conc alto -> problema de CONTROL (cedemos juego)
- xGA alto + tiros conc bajo -> problema de ZONA (pocos tiros pero peligrosos)

Cada diagnostico se traduce a un perfil de jugador concreto.
"""
import pandas as pd
import numpy as np


def _avg(df: pd.DataFrame, col: str) -> float:
    return float(df[col].mean())


def _delta_pct(rayados_val: float, campeones_val: float, higher_is_better: bool = True) -> float:
    """Diferencia % de Rayados vs media de campeones. Positiva = Rayados peor."""
    if campeones_val == 0:
        return 0.0
    if higher_is_better:
        return (campeones_val - rayados_val) / campeones_val * 100
    return (rayados_val - campeones_val) / campeones_val * 100


def diagnose_v2(bench: pd.DataFrame, club: str = "Rayados") -> list[dict]:
    """
    Diagnostico cruzando metricas. Devuelve lista de diagnosticos con:
    - area: nombre del problema
    - causa_raiz: explicacion de POR QUE (no solo que esta mal)
    - severidad: Moderada / Alta / Critica
    - metricas_evidencia: lista de tuplas (metrica, valor_rayados, valor_campeones, %)
    - posicion_sugerida, perfil_sugerido
    """
    rayados = bench[bench["equipo"] == club]
    campeones = bench[bench["equipo"] != club]
    if rayados.empty or campeones.empty:
        return []

    # Valores promedio
    r_xg = _avg(rayados, "xg_90")
    c_xg = _avg(campeones, "xg_90")
    r_tiros = _avg(rayados, "tiros_90")
    c_tiros = _avg(campeones, "tiros_90")
    r_goles = _avg(rayados, "goles_90")
    c_goles = _avg(campeones, "goles_90")
    r_xa = _avg(rayados, "xa_90")
    c_xa = _avg(campeones, "xa_90")

    r_xga = _avg(rayados, "xga_90")
    c_xga = _avg(campeones, "xga_90")
    r_tcon = _avg(rayados, "tiros_concedidos_90")
    c_tcon = _avg(campeones, "tiros_concedidos_90")
    r_gcon = _avg(rayados, "goles_concedidos_90")
    c_gcon = _avg(campeones, "goles_concedidos_90")

    # Brechas
    d_xg = _delta_pct(r_xg, c_xg, True)
    d_tiros = _delta_pct(r_tiros, c_tiros, True)
    d_goles = _delta_pct(r_goles, c_goles, True)
    d_xa = _delta_pct(r_xa, c_xa, True)
    d_xga = _delta_pct(r_xga, c_xga, False)
    d_tcon = _delta_pct(r_tcon, c_tcon, False)
    d_gcon = _delta_pct(r_gcon, c_gcon, False)

    diagnosticos = []

    # ============================================================
    # OFENSIVO - inferencia cruzada
    # ============================================================
    # CASO 1: Generacion (xG bajo + tiros bajos)
    if d_xg > 8 and d_tiros > 8:
        diagnosticos.append({
            "area": "Generacion ofensiva",
            "causa_raiz": (
                "Rayados genera menos peligro porque **llega menos veces al area rival**. "
                "Tanto el volumen de tiros como el xG estan por debajo del estandar campeon. "
                "Esto NO es un problema de finalizador: es de creacion y llegada. "
                "Necesitamos un perfil que aporte conduccion, asociacion en ultimo tercio y desborde."
            ),
            "severidad": _severity(max(d_xg, d_tiros)),
            "evidencia": [
                ("xG / 90", r_xg, c_xg, d_xg),
                ("Tiros / 90", r_tiros, c_tiros, d_tiros),
            ],
            "posicion_sugerida": "Extremo",
            "perfil_sugerido": "Extremo creativo",
        })

    # CASO 2: Calidad de tiro (xG bajo PERO tiros similares o altos)
    elif d_xg > 10 and d_tiros < 5:
        diagnosticos.append({
            "area": "Calidad de tiro",
            "causa_raiz": (
                "Rayados tira tanto o mas que los campeones, pero su xG es bajo. "
                "Eso significa que **dispara desde malas zonas o sin claridad**. "
                "Necesitamos un delantero que finalice dentro del area, no que llegue de fuera."
            ),
            "severidad": _severity(d_xg),
            "evidencia": [
                ("xG / 90", r_xg, c_xg, d_xg),
                ("Tiros / 90", r_tiros, c_tiros, d_tiros),
            ],
            "posicion_sugerida": "Delantero",
            "perfil_sugerido": "Finalizador de area",
        })

    # CASO 3: Finalizacion (xG OK pero goles bajos)
    if d_xg < 8 and d_goles > 12:
        diagnosticos.append({
            "area": "Finalizacion",
            "causa_raiz": (
                "El equipo **genera ocasiones comparables a los campeones pero no las convierte**. "
                "Diferencia entre xG real y goles marcados indica problema de definicion, no de creacion. "
                "Es un fichaje de finalizador puro, no de creativo."
            ),
            "severidad": _severity(d_goles),
            "evidencia": [
                ("xG / 90", r_xg, c_xg, d_xg),
                ("Goles / 90", r_goles, c_goles, d_goles),
            ],
            "posicion_sugerida": "Delantero",
            "perfil_sugerido": "Finalizador de area",
        })

    # CASO 4: Creatividad (xA bajo)
    if d_xa > 12:
        diagnosticos.append({
            "area": "Creatividad",
            "causa_raiz": (
                "Generamos pocas asistencias esperadas. El equipo **no fabrica ocasiones claras "
                "para terceros desde mediocampo**. Necesitamos un organizador que aporte ultimo pase."
            ),
            "severidad": _severity(d_xa),
            "evidencia": [("xA / 90", r_xa, c_xa, d_xa)],
            "posicion_sugerida": "Mediocentro",
            "perfil_sugerido": "Mediocentro organizador",
        })

    # ============================================================
    # DEFENSIVO - inferencia cruzada
    # ============================================================
    # CASO 5: Control del juego (xGA alto + tiros concedidos alto)
    if d_xga > 8 and d_tcon > 8:
        diagnosticos.append({
            "area": "Control del juego",
            "causa_raiz": (
                "Concedemos mas tiros Y mas xGA que los campeones. "
                "**Es un problema estructural: el rival juega comodo en nuestro campo.** "
                "No basta con un central, necesitamos volumen en el doble pivote para controlar."
            ),
            "severidad": _severity(max(d_xga, d_tcon)),
            "evidencia": [
                ("xGA / 90", r_xga, c_xga, d_xga),
                ("Tiros conc. / 90", r_tcon, c_tcon, d_tcon),
            ],
            "posicion_sugerida": "Mediocentro",
            "perfil_sugerido": "Mediocentro defensivo",
        })

    # CASO 6: Zona / defensa (xGA alto PERO tiros concedidos bajo)
    elif d_xga > 12 and d_tcon < 8:
        diagnosticos.append({
            "area": "Proteccion del area",
            "causa_raiz": (
                "Cedemos pocos tiros pero los que cedemos son **muy peligrosos**. "
                "El xGA por tiro concedido es alto: indica problema de **lectura defensiva en el area**, "
                "no de presion. Necesitamos un central dominante en el uno contra uno."
            ),
            "severidad": _severity(d_xga),
            "evidencia": [
                ("xGA / 90", r_xga, c_xga, d_xga),
                ("Tiros conc. / 90", r_tcon, c_tcon, d_tcon),
            ],
            "posicion_sugerida": "Defensa central",
            "perfil_sugerido": "Central dominante defensivo",
        })


    return diagnosticos


def _severity(brecha_pct: float) -> str:
    if brecha_pct >= 20: return "Critica"
    if brecha_pct >= 12: return "Alta"
    return "Moderada"


def executive_summary(diags: list[dict]) -> str:
    if not diags:
        return "No se detectan brechas estructurales relevantes vs el estandar campeon."
    top = diags[:3]
    lines = []
    for d in top:
        lines.append(
            f"- **{d['area']}** ({d['severidad']}): {d['causa_raiz'].split('.')[0]}. "
            f"Recomendacion: {d['perfil_sugerido']} ({d['posicion_sugerida']})."
        )
    return "Diagnostico ejecutivo:\n\n" + "\n".join(lines)


# =============================================================================
# ANALISIS DE PATRONES EN EL ADN
# =============================================================================
def analyze_adn_patterns(adn) -> list[dict]:
    """
    Genera insights narrativos comparando exitosos vs fallidos.

    Devuelve lista de dicts: {tipo, icono, texto}
        tipo: 'verde' (insight positivo) / 'rojo' (alerta) / 'azul' (info)
    """
    import pandas as pd
    insights = []

    ex = adn[adn["etiqueta"] == "exitoso"].copy()
    fa = adn[adn["etiqueta"] == "fallido"].copy()

    if ex.empty and fa.empty:
        return [{"tipo": "azul", "icono": "ℹ️",
                  "texto": "Aun no hay suficientes fichajes evaluados."}]

    # ------------------------------------------------------------------
    # INSIGHT 1: edad media (si la diferencia es significativa)
    # ------------------------------------------------------------------
    if len(ex) >= 3 and len(fa) >= 3:
        e_age = ex["edad_llegada"].mean()
        f_age = fa["edad_llegada"].mean()
        diff = f_age - e_age
        if diff >= 2:
            insights.append({
                "tipo": "verde", "icono": "✅",
                "texto": (f"Los exitosos llegan **{diff:.1f} años mas jovenes** "
                          f"({e_age:.1f} vs {f_age:.1f}). Apostar por jovenes ha rendido mejor.")
            })
        elif diff <= -2:
            insights.append({
                "tipo": "azul", "icono": "ℹ️",
                "texto": f"Curiosamente, los exitosos llegan **mas mayores** "
                          f"({e_age:.1f} años) que los fallidos ({f_age:.1f})."
            })

    # ------------------------------------------------------------------
    # INSIGHT 2: liga origen donde MAS funciona
    # ------------------------------------------------------------------
    if len(ex) >= 3:
        liga_exito = ex["liga_anterior"].value_counts().head(3)
        if not liga_exito.empty:
            top_liga = liga_exito.index[0]
            n = liga_exito.iloc[0]
            if isinstance(top_liga, str) and top_liga and top_liga != "Sin dato":
                insights.append({
                    "tipo": "verde", "icono": "🟢",
                    "texto": (f"Liga origen mas frecuente en exitosos: **{top_liga}** "
                              f"({n} fichajes). Es un mercado a seguir explotando.")
                })

    # ------------------------------------------------------------------
    # INSIGHT 3: liga origen donde MAS fallan (la trampa)
    # ------------------------------------------------------------------
    if len(fa) >= 3:
        # ligas con tasa de fallo alta (al menos 2 fichajes y >50% fallan)
        all_eval = pd.concat([ex.assign(et="e"), fa.assign(et="f")])
        ligas_eval = all_eval.groupby("liga_anterior")["et"].agg(["count",
                        lambda s: (s == "f").sum()]).rename(columns={"<lambda_0>": "n_fall"})
        ligas_eval = ligas_eval[ligas_eval["count"] >= 2]
        ligas_eval["pct_fallo"] = ligas_eval["n_fall"] / ligas_eval["count"] * 100
        ligas_eval = ligas_eval[ligas_eval["pct_fallo"] >= 50].sort_values("n_fall", ascending=False)
        if not ligas_eval.empty:
            liga_trampa = ligas_eval.index[0]
            n_fall = int(ligas_eval.iloc[0]["n_fall"])
            n_total = int(ligas_eval.iloc[0]["count"])
            if isinstance(liga_trampa, str) and liga_trampa and liga_trampa != "Sin dato":
                insights.append({
                    "tipo": "rojo", "icono": "🚫",
                    "texto": (f"**Cuidado con {liga_trampa}**: {n_fall} de {n_total} fichajes "
                              f"de esa liga fueron fallidos ({n_fall/n_total*100:.0f}%).")
                })

    # ------------------------------------------------------------------
    # INSIGHT 4: coste medio (si los caros fracasan)
    # ------------------------------------------------------------------
    ex_caros = ex[ex["coste_meur"] > 0]
    fa_caros = fa[fa["coste_meur"] > 0]
    if len(ex_caros) >= 2 and len(fa_caros) >= 3:
        e_coste = ex_caros["coste_meur"].mean()
        f_coste = fa_caros["coste_meur"].mean()
        if f_coste >= e_coste + 1.5:
            insights.append({
                "tipo": "rojo", "icono": "💸",
                "texto": (f"Los **fallidos costaron mas** en promedio ({f_coste:.1f} M€) "
                          f"que los exitosos ({e_coste:.1f} M€). El gasto alto no garantiza acierto.")
            })

    # ------------------------------------------------------------------
    # INSIGHT 5: dinero total perdido en fallidos
    # ------------------------------------------------------------------
    if not fa.empty:
        perdida_total = (fa["coste_meur"] - fa.get("coste_venta_meur", 0)).sum()
        if perdida_total > 0:
            insights.append({
                "tipo": "rojo", "icono": "📉",
                "texto": (f"Perdida economica acumulada en fallidos: "
                          f"**{perdida_total:.1f} M€** (solo en transferencias, sin contar salarios).")
            })

    # ------------------------------------------------------------------
    # INSIGHT 6: cantera/libres como ROI alto
    # ------------------------------------------------------------------
    libres_ex = ex[ex["coste_meur"] == 0]
    if len(libres_ex) >= 2:
        venta_libres = libres_ex.get("coste_venta_meur", pd.Series([0])).sum()
        insights.append({
            "tipo": "verde", "icono": "💎",
            "texto": (f"**{len(libres_ex)} fichajes libres/cantera** generaron "
                      f"**{venta_libres:.1f} M€ en ventas**. ROI infinito.")
        })

    return insights


def adn_conclusion(adn) -> str:
    """Conclusion ejecutiva narrativa del ADN (1-2 lineas)."""
    ex = adn[adn["etiqueta"] == "exitoso"]
    fa = adn[adn["etiqueta"] == "fallido"]
    if ex.empty and fa.empty:
        return "Sin datos suficientes para conclusion."

    tasa = len(ex) / (len(ex) + len(fa)) * 100 if (len(ex) + len(fa)) > 0 else 0

    if tasa >= 60:
        veredicto = "Politica de fichajes **positiva en balance**, aunque con casos puntuales caros que perjudican el ROI global."
    elif tasa >= 40:
        veredicto = "Balance de fichajes **mixto**. Hay aciertos claros y errores caros que conviene evitar replicar."
    else:
        veredicto = "Balance de fichajes **preocupante**: dominan los fallos. Revisar criterios de scouting es prioritario."
    return veredicto
