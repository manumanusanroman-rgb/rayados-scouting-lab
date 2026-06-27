# Documentación de fuentes de datos

> **Sección crítica para defensa del TFM**: justificación metodológica de las decisiones de datos.

## Resumen ejecutivo

| Tipo de dato | Fuente elegida | Razón |
|---|---|---|
| Stats agregadas jugadores (4 ligas) | **FBref** vía `fbrefdata` | Única fuente pública gratuita con cobertura completa y métricas avanzadas Opta |
| Valor de mercado plantilla actual | **Transfermarkt** | Estándar de la industria |
| Salarios | **Modelo estimado** + Capology como validación | Liga MX no publica salarios oficialmente |
| Historia y palmarés | **rayados.com** + Wikipedia | Cross-validation |
| ADN histórico (éxito/fallo) | **Transfermarkt** + prensa (manual) | Etiquetado cualitativo requiere criterio humano |

## Por qué FBref y no las otras

### Comparación de fuentes evaluadas

| Fuente | Liga MX | Brasileirão | Primera Arg | Segunda Esp | Métricas avanzadas | Coste |
|---|---|---|---|---|---|---|
| **FBref** | ✅ desde 2017 | ✅ desde 2014 | ✅ desde 2014 | ✅ desde 2017 | xG, xA, npxG, progresivos, presiones | Gratis |
| FotMob | ✅ actual | ✅ actual | ✅ actual | ✅ actual | xG, xA limitados | Gratis (endpoint frágil) |
| SofaScore | ✅ | ✅ | ✅ | ✅ | Limitadas | Gratis (rate limit agresivo) |
| Understat | ❌ | ❌ | ❌ | ❌ | xG completo | Gratis |
| StatsBomb Open | ❌ | ❌ | Solo 2017-18 | ❌ | Event data completo | Gratis |
| StatsBomb (full) | ✅ | ✅ | ✅ | ✅ | Event data + freeze frames | ~$50k+/año |
| Opta directo | ✅ | ✅ | ✅ | ✅ | Todo | Pago |
| Wyscout | ✅ | ✅ | ✅ | ✅ | Event data | Pago |

### Justificación final

FBref es la **única fuente gratuita con cobertura completa de las 4 ligas y métricas avanzadas Opta**. Las alternativas tienen limitaciones inaceptables:

- FotMob/SofaScore: endpoints no oficiales, frágiles, pueden romperse sin aviso.
- Understat: no cubre nuestras ligas.
- StatsBomb Open: no cubre nuestras ligas en datos abiertos.
- Pago: fuera del presupuesto de un TFM.

**Consideración metodológica importante**: FBref muestra datos de Opta. Esto significa que las métricas son consistentes con la mayoría de clubes profesionales que usan Opta como proveedor. Un análisis hecho con FBref es directamente comparable con uno hecho con datos de cliente Opta.

## Pipeline de datos

```
┌─────────────────────────────────────────────────────────────┐
│  PASO 1: SCRAPING (notebooks/01_fbref_scraping.ipynb)       │
│  - 4 ligas, 2 últimas temporadas                            │
│  - Cache local en data/raw/                                 │
│  - Rate limit: 6s entre requests                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PASO 2: TRANSFERMARKT (notebooks/02_transfermarkt.ipynb)   │
│  - Plantilla Rayados con valor de mercado actual            │
│  - Histórico de fichajes del club (ADN)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PASO 3: CLEANING (notebooks/03_data_cleaning.ipynb)        │
│  - Mapeo de columnas FBref → esquema interno                │
│  - Cálculo de métricas derivadas (per 90, percentiles)      │
│  - Output a data/processed/                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PASO 4: VALIDATION (notebooks/04_validation.ipynb)         │
│  - Sanity checks: rangos plausibles                         │
│  - Cross-check contra FotMob (subset)                       │
│  - Detección de outliers y datos faltantes                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
                  data/processed/*.csv
                            ↓
                       app.py lee
```

## Consideraciones éticas y legales

- **FBref**: scraping permitido para uso académico no comercial según sus términos. La librería `fbrefdata` respeta robots.txt y rate limits.
- **Transfermarkt**: scraping en zona gris. Para TFM (uso académico, sin redistribución comercial) es aceptado. **No redistribuir los datos crudos**.
- **rayados.com**: información pública del club.

## Limitaciones reconocidas (documentar en TFM)

1. **No tenemos event data real** para Liga MX. Esto limita análisis tácticos profundos (xG por zona, mapas de presión).
2. **Salarios estimados, no reales**. Liga MX no publica.
3. **Coste de fichajes**: Transfermarkt es estimación, no precio real de operaciones.
4. **xG comparado entre ligas**: el modelo de Opta es el mismo, pero los **rivales son diferentes**. Un delantero brasileño con 0.5 xG/90 enfrenta defensas distintas a uno mexicano. Esto se ajusta con un factor de liga en el scoring.
