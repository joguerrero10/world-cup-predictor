# World Cup Predictor AI

Probabilistic prediction for football matches and full tournaments, combining a
**Klement-inspired** socio-economic score, **Elo** ratings, the **Dixon–Coles**
scoreline model, and recent form, with **Monte Carlo** tournament simulation.

> **Status (be honest with yourself):** this repository is a *verified, runnable
> core*, not the finished platform described in the original brief. The ML engine
> and API are implemented and tested. Streamlit UI, Power BI assets, CI/CD, and the
> full DB data layer are scaffolded / documented and listed under "Not yet built".

---

## What is actually built and verified

Running `python -m tests.verify` checks real mathematical properties (20 assertions, all passing):

| Module | File | Verified behaviour |
|---|---|---|
| Elo | `app/models/elo.py` | Equal/neutral expectation = 0.5; home advantage > 0.5; **global rating is zero-sum**; winner gains; 1X2 sums to 1 |
| Dixon–Coles | `app/models/dixon_coles.py` | MLE fit; score matrix and 1X2 normalise to 1; recovers stronger team; positive home-advantage param; τ low-score correction |
| Klement (approx.) | `app/models/klement.py` | Stronger socio-economic factors → higher score |
| Hybrid | `app/models/hybrid.py` | Configurable 30/40/20/10 blend; sums to 1; degrades gracefully when a sub-model lacks data |
| Monte Carlo | `app/models/monte_carlo.py` | Champion probabilities sum to 1; strongest team most likely to win; all probs in [0,1] |
| Metrics + **Klement 2.0** | `app/models/metrics.py` | Brier / log-loss / accuracy / ECE / ROI; optimiser **learns weights** and up-weights the informative sub-model |
| API | `app/main.py` | All 6 endpoints; `/retrain` fits Elo + Dixon–Coles end-to-end |

## Methodology and sources (verified)

- **Dixon, M.J. & Coles, S.G. (1997)**, *Modelling Association Football Scores and
  Inefficiencies in the Football Betting Market*, JRSS Series C 46(2), 265–280 —
  basis of the bivariate-Poisson + τ correction.
- **World Football Elo Ratings** formula (expected = 1/(1+10^(−dr/400)), +100 home
  advantage, K-factor, goal-difference index) — https://en.wikipedia.org/wiki/World_Football_Elo_Ratings
- **Klement model**: Joachim Klement's published model reportedly uses GDP per
  capita, population, temperature, FIFA ranking points and host advantage, derived
  from Hoffmann, Ging & Ramasamy (2002, University of Nottingham). **His exact
  coefficients are proprietary**, so `klement.py` is a transparent *approximation*
  using the same inputs — it does **not** reproduce his numbers.
  Sources: ESPN, SBS, Fortune (2022) coverage of Klement's forecasts.

## Quick start

```bash
# 1. Local (no Docker) — run the verified core + API
pip install -r requirements.txt
python -m tests.verify                 # 20 checks, should all PASS
uvicorn app.main:app --reload          # http://localhost:8000/docs

# 2. Full stack with Postgres
cp .env.example .env                    # set a real POSTGRES_PASSWORD
docker compose up --build               # api:8000, streamlit:8501, db:5432
```

### Example: train, then predict

```bash
# POST /retrain with historical results (home/away teams + goals)
curl -X POST localhost:8000/retrain -H 'content-type: application/json' \
  -d '{"home_teams":["Brazil","France"],"away_teams":["Ghana","Japan"],
       "home_goals":[2,1],"away_goals":[0,1]}'

curl 'localhost:8000/predict-match?home=Brazil&away=Ghana&model=hybrid'
curl 'localhost:8000/elo-rankings'
curl 'localhost:8000/team-probabilities?n_sims=50000'
```

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET  | `/predict-match` | 1X2 for a pair; `model=hybrid\|elo\|dixon_coles\|klement` |
| GET  | `/simulate-tournament` | Monte Carlo champion/finalist/semifinalist probs |
| GET  | `/team-probabilities` | same engine, per-team aggregates |
| GET  | `/elo-rankings` | global + attack/defence Elo |
| GET  | `/model-performance` | stored eval metrics (409 until you run an evaluation) |
| POST | `/retrain` | refit Elo + Dixon–Coles from supplied history |

Endpoints return **HTTP 409** when a model is untrained rather than inventing output.

## Klement 2.0 (data-driven weights)

`metrics.optimise_weights(sub_model_probs, outcomes, objective)` replaces the fixed
30/40/20/10 split by learning weights that minimise log-loss or Brier on historical
data. **You must supply a real 1998–2022 dataset** (matches + each sub-model's
out-of-sample predictions); the function fabricates nothing.

## Power BI integration

I cannot author a binary `.pbix` file. The intended approach:
1. Expose the `predictions`, `elo_history`, `tournament_results`, `model_metrics`
   tables (schema in `app/db/schema.sql`) — connect Power BI directly to Postgres.
2. Build the 7 report pages on that model. Example DAX measures to create:
   - `Champion % = AVERAGE(tournament_results[p_champion])`
   - `Brier (latest) = CALCULATE(MIN(model_metrics[brier_score]), ...)`
   - `Elo Δ = SELECTEDVALUE(elo_history[rating]) - CALCULATE(MIN(elo_history[rating]), ...)`
   I can generate the full DAX set and step-by-step page build on request.

## Not yet built (next stages)

- `frontend/app.py` Streamlit UI (selector, Plotly charts, Excel/PDF export, dark theme)
- Full DB repositories wiring `app/main.py` `STATE` to Postgres
- ETL scripts to ingest real match/FIFA/macroeconomic data
- `.github/workflows/ci.yml` (lint + pytest)
- `players`, `fifa_rankings`, `macroeconomic_data`, `simulations`, `tournament_results` ORM classes (DDL exists in `schema.sql`)
- xgboost-based form model (dependency included; model not yet implemented)

## Caveat

Even a well-calibrated model predicts a single tournament with high uncertainty —
Klement himself warns his forecasts should not be used for betting. Treat champion
probabilities as distributions over many simulations, not certainties.
