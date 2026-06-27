# Glosario de métricas — Rayados Scouting Lab

> Documento de referencia metodológica para el TFM. Cada métrica usada en la herramienta está aquí con su definición, fuente y cómo se calcula. **Defender esto ante el tribunal demuestra rigor.**

---

## ⚠️ Nota importante sobre fuentes

Todas las métricas avanzadas (xG, xA, npxG, progresivos, presiones) provienen de **Opta** y son extraídas de **FBref** mediante la librería `fbrefdata`. Esto garantiza **consistencia metodológica**: todas usan el mismo modelo de cálculo.

**No mezclamos** métricas de fuentes distintas. El xG de FBref/Opta tiene valores diferentes al de StatsBomb (mismo partido puede dar valores ~25% distintos), por lo que mezclar fuentes invalidaría las comparaciones.

---

## 📈 Métricas ofensivas

### `xg_90` — Expected Goals por 90 minutos
**Qué es:** Probabilidad agregada de gol de los tiros tomados, normalizada a 90 minutos.
**Cómo se calcula (Opta):** Cada tiro recibe una probabilidad 0-1 según:
- Distancia y ángulo a portería
- Parte del cuerpo (cabeza, pie fuerte, pie débil)
- Tipo de pase previo (centro, balón filtrado, balón parado)
- Tipo de jugada (posesión establecida, rebote, contra)

Un penalti vale ~0.78 xG según el modelo Opta.
**Interpretación:** Mide la *generación de ocasiones*, no el resultado. Más estable que goles.
**Uso en la app:** Diagnóstico (¿generamos lo mismo que campeones?), scoring de delanteros y extremos.

### `npxg_90` — Non-Penalty xG por 90
**Qué es:** xG excluyendo penaltis.
**Por qué importa:** Para evaluar delanteros sin sesgo del especialista a penaltis.

### `xa_90` — Expected Assists por 90
**Qué es:** xG del tiro que sigue a un pase del jugador, incluso si el receptor falla.
**Diferencia con asistencias:** Una asistencia requiere que el receptor anote. xA mide la *calidad del pase*, independiente de la finalización del compañero.
**Uso en la app:** Diagnóstico de creatividad, scoring de mediocentros organizadores y extremos creativos.

### `goles_90`
**Qué es:** Goles marcados / minutos × 90. Excluye penaltis si se especifica `np_goles_90`.

### `tiros_90` / `tiros_area_90`
**Qué es:** Volumen de tiros total / dentro del área (las áreas del fútbol son donde se concentra el 80% del xG).
**Uso clave:** Cruzado con xG permite distinguir si Rayados "no llega" (pocos tiros) o "llega pero tira mal" (muchos tiros, bajo xG).

### `pases_clave_90` (KP en FBref)
**Qué es:** Pases que llevan directamente a un tiro del receptor.
**Diferencia con xA:** Pases_clave cuenta el evento; xA pondera por calidad del tiro que generó.

### `regates_completados_90`
**Qué es:** Take-ons exitosos. Indicador clave para extremos.

### `carreras_progresivas_90`
**Qué es:** Conducciones de balón que avanzan ≥10 yardas hacia portería rival, o llegan al área.
**Uso:** Perfil "Delantero de ruptura" y "Extremo vertical".

### `centros_completados_pct`
**Qué es:** % de centros completados sobre intentados.

### `conversion_pct`
**Qué es:** Goles / Tiros × 100.
**Cuidado:** Métrica muy ruidosa en muestras pequeñas. Solo usar con +1000 minutos.

---

## 🛡️ Métricas defensivas

### `xga_90` — Expected Goals Against
**Qué es:** Suma del xG de los tiros que el equipo concede.
**Interpretación:** Mide *calidad* de las ocasiones cedidas, no solo cantidad.

### `tiros_concedidos_90`
**Qué es:** Tiros que el rival realiza contra nosotros / 90.
**Cruzado con xGA:** Si tiros concedidos es alto y xGA es alto → cedemos cantidad. Si tiros concedidos es bajo pero xGA es alto → cedemos pocos pero peligrosos (problema de zona).

### `entradas_90`
**Qué es:** Tackles realizados (con o sin recuperar el balón).

### `intercepciones_90`
**Qué es:** Balones cortados sin necesidad de tackle. Indicador de **lectura defensiva** (vs entradas que es reactivo).

### `duelos_ganados_pct` / `duelos_aereos_ganados_pct`
**Qué es:** % de duelos individuales / aéreos ganados sobre disputados.

### `despejes_90`
**Qué es:** Balones alejados de zona de peligro sin control. Métrica de central tradicional.

### `recuperaciones_90`
**Qué es:** Recuperaciones de posesión por cualquier vía. Más amplia que entradas + intercepciones.

### `presiones_90` (Opta)
**Qué es:** Acciones de presión sobre el rival con balón (a menos de 2m).
**Subtipos relevantes:** `presiones_campo_rival_90` para delanteros presionantes.

### `ppda` — Passes Per Defensive Action
**Qué es:** Pases del rival permitidos entre cada acción defensiva nuestra.
**Interpretación:** Bajo = presión alta. Equipos campeones suelen estar entre 7-9.

---

## 🥅 Métricas de portero

### `paradas_pct`
**Qué es:** Paradas / tiros a puerta recibidos × 100.

### `psxg` — Post-Shot xG
**Qué es:** xG calculado **después del tiro**, con información de dónde fue dirigido el balón.
**Por qué importa:** Mide *qué tan parable* fue el tiro (no qué tan peligrosa fue la ocasión).

### `goles_evitados_psxg`
**Qué es:** PSxG - Goles encajados.
**Interpretación:** Positivo = portero salva más de lo esperado (bueno). Negativo = encaja goles que un portero estándar pararía.
**Uso clave:** Diagnóstico de portería del equipo en la herramienta.

### `salidas_90`
**Qué es:** Salidas del área para despejar balones aéreos.

---

## 🔗 Métricas de pase y construcción

### `pases_progresivos_90`
**Qué es:** Pases que avanzan el balón ≥10 yardas hacia portería rival. Excluye saques de banda y pases hacia atrás.

### `pases_completados_pct`
**Qué es:** % de pases completados sobre intentados. Indicador básico de control.

### `pases_largos_completados_pct`
**Qué es:** Subconjunto: solo pases > 30 yardas. Clave para centrales con salida de balón y porteros con juego de pies.

---

## ⚡ Métricas físicas (Opta)

### `velocidad_max`
**Qué es:** Velocidad máxima registrada en km/h durante el partido.
**Disponibilidad:** Solo en datos Opta premium. Para FBref público puede no estar.

### `distancia_recorrida_90`
**Qué es:** Km recorridos por 90 minutos.

---

## 💰 Métricas económicas

### `valor_mercado_meur` — Valor de mercado
**Fuente:** Transfermarkt.
**Cómo se calcula:** Estimación de Transfermarkt basada en mercado, edad, rendimiento, contrato. **No es precio real**, es valoración del mercado por la comunidad y editores.

### `salario_estimado_meur`
**Fuente:** Modelo propio basado en datos parciales de Capology + valor de mercado.
**Fórmula:**
```
salario_anual ≈ valor_mercado × 0.30 × multiplicador_liga × multiplicador_score
```
**Validación:** Para jugadores con dato real en Capology (caso Sergio Canales que jugó en La Liga), se verifica que el modelo no se desvíe >25%.
**Limitación reconocida:** Liga MX no publica salarios. Este modelo es **una estimación**, no un dato real. Documentado así en la app.

---

## 📊 Métricas derivadas (calculadas por la herramienta)

### `score_encaje` (0-100)
**Cálculo:** Promedio ponderado de KPIs normalizados min-max al pool de jugadores de la misma posición.
**Pesos:** Definidos en `data/kpi_profiles.csv` por perfil. Suman 100% por perfil.

### `score_riesgo` (0-100)
**Componentes:**
- Edad fuera de rango óptimo 23-28: penalización lineal
- Minutos < 2000 en última temporada: penalización por falta de rodaje
- Días de lesión última temporada: penalización proporcional
- Liga distinta a Liga MX: penalización por adaptación

### `score_final` (0-100)
```
score_final = score_encaje × 0.70 + (100 − score_riesgo) × 0.30
```

### `percentil_posicional`
**Qué es:** Para cada KPI, percentil del jugador respecto a su posición en su liga.
**Uso en la app:** Pizza chart y beeswarm.

---

## 🔗 Cobertura por liga (FBref)

| Liga | Stats agregadas | Event data público |
|---|---|---|
| Liga MX | ✅ desde 2017-18 | ❌ |
| Brasileirão | ✅ desde 2014-15 | ❌ |
| Primera Argentina | ✅ desde 2014-15 | ❌ |
| Segunda España (LaLiga 2) | ✅ desde 2017-18 | ❌ |

**Limitaciones reconocidas:**
- Algunas métricas avanzadas (xG, presiones) **solo están disponibles desde 2017-18** en FBref para Liga MX.
- En partidos antiguos puede no haber datos físicos (velocidad, distancia).
- FBref puede tener **delay de 24-48h** respecto a la jornada actual.
