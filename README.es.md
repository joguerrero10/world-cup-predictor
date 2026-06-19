# World Cup Predictor AI

Predicción probabilística de partidos de fútbol y torneos completos, combinando una
puntuación socioeconómica **inspirada en Klement**, ratings **Elo**, el modelo de
marcadores **Dixon–Coles** y la forma reciente, con simulación de torneos por
**Monte Carlo**.

> **Estado (seamos honestos):** núcleo de ML + API + capa de base de datos +
> modelo xgboost + frontend Streamlit + ETL + CI + **arranque en caliente desde BD**
> + **calibración de probabilidades** + **backtest walk-forward** + **paquete Power BI
> (modelo de datos + DAX)** implementados y probados (**48 aserciones** pasan en 3 suites).
> Lo que queda son datos reales y despliegue, listados en "Aún no construido".

---

## Qué está realmente construido y verificado

Al ejecutar `python -m tests.verify` se comprueban propiedades matemáticas reales (20 aserciones, todas pasan):

| Módulo | Archivo | Comportamiento verificado |
|---|---|---|
| Elo | `app/models/elo.py` | Expectativa en campo neutral/igualdad = 0.5; ventaja de localía > 0.5; **el rating global es de suma cero**; el ganador gana puntos; el 1X2 suma 1 |
| Dixon–Coles | `app/models/dixon_coles.py` | Ajuste por MLE; la matriz de marcadores y el 1X2 se normalizan a 1; recupera al equipo más fuerte; parámetro de localía positivo; corrección τ para marcadores bajos |
| Klement (aprox.) | `app/models/klement.py` | Factores socioeconómicos más fuertes → puntuación más alta |
| Híbrido | `app/models/hybrid.py` | Mezcla configurable 30/40/20/10; suma 1; se degrada con elegancia cuando a un submodelo le faltan datos |
| Monte Carlo | `app/models/monte_carlo.py` | Las probabilidades de campeón suman 1; el equipo más fuerte gana con mayor probabilidad; todas las probabilidades en [0,1] |
| Métricas + **Klement 2.0** | `app/models/metrics.py` | Brier / log-loss / accuracy / ECE / ROI; el optimizador **aprende los pesos** y da más peso al submodelo informativo |
| API | `app/main.py` | Los 6 endpoints; `/retrain` ajusta Elo + Dixon–Coles de extremo a extremo; persiste predicciones en BD |
| Base de datos | `app/db/database.py`, `repositories.py` | 10 tablas ORM; JSON portable (JSONB↔SQLite); upsert idempotente; roundtrip verificado |
| Modelo de forma | `app/models/form_model.py` | Clasificador **XGBoost** 1X2; supera al baseline uniforme en log-loss; 3 clases que suman 1 |

Segunda suite: `python -m tests.verify_stage2` (BD en SQLite + modelo XGBoost).

**Etapa 3** (`python -m tests.verify_stage3`, 14 aserciones):

| Módulo | Archivo | Comportamiento verificado |
|---|---|---|
| Features walk-forward | `app/services/features.py` | Una fila por partido; el primer partido tiene `elo_diff` = 0 (sin fuga de datos) |
| Calibración | `app/models/calibration.py` | Isotónica reduce el error de calibración (0.204 → 0.001); Platt suma 1 |
| Backtest | `app/models/backtest.py` | Walk-forward: accuracy 0.58 > 1/3; log-loss bajo el baseline; ROI cuando hay cuotas |
| Arranque desde BD | `app/services/bootstrap.py` | `/load-from-db` reconstruye Elo + Dixon–Coles; `/train-form-model` entrena XGBoost del historial |
| Power BI | `powerbi/measures.dax`, `powerbi/README.md` | Modelo de datos + todas las medidas DAX de las 7 páginas |

## Metodología y fuentes (verificadas)

- **Dixon, M.J. & Coles, S.G. (1997)**, *Modelling Association Football Scores and
  Inefficiencies in the Football Betting Market*, JRSS Series C 46(2), 265–280 —
  base de la Poisson bivariada + corrección τ.
- Fórmula de los **World Football Elo Ratings** (esperado = 1/(1+10^(−dr/400)), +100 de
  ventaja de localía, K-factor, índice de diferencia de goles) —
  https://en.wikipedia.org/wiki/World_Football_Elo_Ratings
- **Modelo Klement**: según lo publicado, el modelo de Joachim Klement utiliza el PIB
  per cápita, la población, la temperatura, los puntos del ranking FIFA y la ventaja
  de localía, derivado de Hoffmann, Ging & Ramasamy (2002, Universidad de Nottingham).
  **Sus coeficientes exactos son propietarios**, por lo que `klement.py` es una
  *aproximación* transparente que usa las mismas variables — **no** reproduce sus
  cifras. Fuentes: cobertura de ESPN, SBS y Fortune (2022) sobre los pronósticos de Klement.

## Inicio rápido

```bash
# 1. Local (sin Docker) — ejecuta el núcleo verificado + la API
pip install -r requirements.txt
python -m tests.verify                 # 20 comprobaciones, todas deberían PASAR
uvicorn app.main:app --reload          # http://localhost:8000/docs

# 2. Stack completo con Postgres
cp .env.example .env                    # define una POSTGRES_PASSWORD real
docker compose up --build               # api:8000, streamlit:8501, db:5432
```

### Ejemplo: entrenar y luego predecir

```bash
# POST /retrain con resultados históricos (equipos local/visitante + goles)
curl -X POST localhost:8000/retrain -H 'content-type: application/json' \
  -d '{"home_teams":["Brazil","France"],"away_teams":["Ghana","Japan"],
       "home_goals":[2,1],"away_goals":[0,1]}'

curl 'localhost:8000/predict-match?home=Brazil&away=Ghana&model=hybrid'
curl 'localhost:8000/elo-rankings'
curl 'localhost:8000/team-probabilities?n_sims=50000'
```

## Endpoints

| Método | Ruta | Notas |
|---|---|---|
| GET  | `/predict-match` | 1X2 para un emparejamiento; `model=hybrid\|elo\|dixon_coles\|klement` |
| GET  | `/simulate-tournament` | Probabilidades de campeón/finalista/semifinalista por Monte Carlo |
| GET  | `/team-probabilities` | mismo motor, agregados por equipo |
| GET  | `/elo-rankings` | Elo global + ofensivo/defensivo |
| GET  | `/model-performance` | métricas de evaluación almacenadas (409 hasta que ejecutes una evaluación) |
| POST | `/retrain` | reajusta Elo + Dixon–Coles a partir del historial proporcionado |

Los endpoints devuelven **HTTP 409** cuando un modelo no está entrenado, en lugar de inventar resultados.

## Klement 2.0 (pesos basados en datos)

`metrics.optimise_weights(sub_model_probs, outcomes, objective)` reemplaza el reparto
fijo 30/40/20/10 aprendiendo los pesos que minimizan el log-loss o el Brier sobre datos
históricos. **Debes proporcionar un dataset real de 1998–2022** (partidos + las
predicciones fuera de muestra de cada submodelo); la función no inventa nada.

## Integración con Power BI

No puedo generar un archivo binario `.pbix`. El enfoque previsto:
1. Exponer las tablas `predictions`, `elo_history`, `tournament_results` y
   `model_metrics` (esquema en `app/db/schema.sql`) — conectar Power BI directamente a Postgres.
2. Construir las 7 páginas del informe sobre ese modelo. Ejemplos de medidas DAX a crear:
   - `Champion % = AVERAGE(tournament_results[p_champion])`
   - `Brier (latest) = CALCULATE(MIN(model_metrics[brier_score]), ...)`
   - `Elo Δ = SELECTEDVALUE(elo_history[rating]) - CALCULATE(MIN(elo_history[rating]), ...)`
   Puedo generar el conjunto completo de DAX y la construcción página por página si lo pides.

## Ejecutar frontend y ETL

```bash
# Frontend (con la API corriendo en :8000)
streamlit run frontend/app.py            # http://localhost:8501

# Cargar resultados históricos reales (formato CSV público estándar)
python -m etl.load_results --csv ruta/a/results.csv
```

## Aún no construido (próximas etapas)

- Persistir snapshots de Elo y resultados de simulación en la BD tras cada `/retrain` y simulación (las funciones de repositorio ya existen)
- Endpoint que persista las métricas del backtest en `model_metrics` para alimentar la Página 6 de Power BI
- Conseguir y cargar datos socioeconómicos reales (PIB/población/FIFA) — el cargador ya existe (`etl/load_factors.py` + `/load-factors`); falta el dataset real
- Backtest ROI 1998–2022 con cuotas históricas reales
- Despliegue: imagen publicada, gateway de Power BI, y autenticación de la API

## Advertencia

Incluso un modelo bien calibrado predice un único torneo con alta incertidumbre — el
propio Klement advierte que sus pronósticos no deben usarse para apuestas. Trata las
probabilidades de campeón como distribuciones sobre muchas simulaciones, no como certezas.
