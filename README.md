# Rayados Scouting Lab

Herramienta de **scouting y decisión deportiva** para CF Monterrey (Liga MX), desarrollada como Trabajo Fin de Máster en Big Data aplicado al deporte.

La aplicación funciona como un asistente para la dirección deportiva: **diagnostica** las carencias del equipo, **busca** candidatos en un pool de más de 3.000 jugadores, y **valida** que la propuesta de fichajes cumpla el presupuesto y el reglamento de Liga MX — todo de forma interactiva.

---

## Qué hace

La herramienta sigue el flujo real de trabajo de un director deportivo:

1. **Diagnóstico competitivo** — Mide la brecha de Rayados frente al Top 4 de Liga MX, por posición y por lado, y genera un plan de refuerzos priorizado.
2. **Scouting Lab** — Filtra a los candidatos por perfil, insignias, pie y edad; los puntúa por encaje, riesgo y salario estimado; y permite compararlos contra los titulares actuales con radares por posición.
3. **Propuesta Final** — Construye un plan de ventas, cesiones y fichajes, recalcula el presupuesto en vivo y comprueba las reglas de Liga MX en tiempo real.

---

## El enfoque

El proyecto combina dos miradas:

- **Deportiva** — Rendimiento medido por percentiles dentro de cada liga, con un sistema propio de *insignias* (rasgos medibles como Creador, Recuperador, Desequilibrante, etc.).
- **Económica** — Cada fichaje se analiza como un activo financiero: coste, recuperación al vender y años amortizados en el club. El hallazgo central es que los fichajes fallidos cuestan de media el triple que los exitosos, lo que justifica una estrategia de fichar **joven e infravalorado**.

---

## Datos

- **Pool de scouting:** ~3.100 jugadores de 8 ligas del continente americano (MLS, Argentina, Brasil A y B, Ecuador, Chile, Colombia y Liga MX).
- **Estadísticas de jugador:** eventos de Opta.
- **Métricas de equipo:** FBref.
- **Valores de mercado e histórico de fichajes:** Transfermarkt.
- **Preferencia de pie (laterales y extremos):** enriquecida vía FotMob.
- **Salarios:** estimados con un modelo posicional propio, calibrado contra referencias públicas.

> Nota: los salarios son estimaciones de un modelo propio, no cifras oficiales. El squad y el lado de cada jugador son datos reales aportados por la dirección deportiva.

---

## Tecnología

- **Python** + **Streamlit** (interfaz web interactiva)
- **pandas** para el procesamiento de datos
- **Plotly** para las visualizaciones (radares, donuts, diagramas)

---

## Cómo ejecutar

```bash
# 1. Crear y activar el entorno (ejemplo con conda)
conda create -n rayados python=3.11
conda activate rayados

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Lanzar la aplicación
streamlit run app.py
```

La aplicación se abre en `http://localhost:8501`.

---

## Estructura del proyecto

```
rayados_scouting_lab/
├── app.py              # Aplicación principal de Streamlit
├── src/                # Módulos: visuales, diagnósticos, scoring, carga de datos
├── data/               # CSVs de jugadores, squad, ADN del club, benchmarks
└── requirements.txt    # Dependencias
```

---

## Autor

**Manuel Sanromán** — Trabajo Fin de Máster en Big Data Deportivo, 2026.
