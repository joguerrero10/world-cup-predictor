"""
FastAPI application — Plataforma de Simulación Futbolística.

API v1 (nueva, multicompetición):
    POST /api/v1/simulation-jobs          — simulación asíncrona
    GET  /api/v1/simulation-jobs/{id}     — estado del job
    GET  /api/v1/simulation-jobs/{id}/result
    GET  /api/v1/predict-match            — predicción 1X2 + marcador
    GET  /api/v1/predict-player           — probabilidades de jugador
    GET  /api/v1/predict-season           — temporada completa
    GET  /api/v1/team-probabilities       — torneo Monte Carlo
    GET  /api/v1/league-table             — tabla de liga simulada
    GET  /api/v1/player-probabilities     — distribución de goles
    GET  /api/v1/discipline-probabilities — tarjetas y disciplina

API legacy (mantenida para compatibilidad hacia atrás):
    GET  /predict-match, /simulate-tournament, /team-probabilities
    GET  /elo-rankings, /model-performance
    POST /retrain, /load-from-db, /train-form-model, /load-factors
    GET  /health
"""
from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.models.elo import EloConfig, TeamElo, win_draw_loss_probs
from app.models.dixon_coles import DixonColes
from app.models.klement import KlementWeights, TeamFactors, klement_score, klement_match_probs
from app.models.hybrid import HybridWeights, blend_smart, form_probs
from app.models.monte_carlo import Group, simulate
from app.db.database import init_db, SessionLocal, engine
from app.db import repositories as repo
from app.services.bootstrap import build_engine_from_db, build_factors_from_db
from app.services.features import MatchRow, walk_forward
from app.models.form_model import FormModel, build_features

import time
from contextlib import asynccontextmanager
from sqlalchemy import text

import asyncio


async def _warm_start():
    """Reconstruye Elo + Dixon-Coles + factores Klement en segundo plano.
    La API responde /health de inmediato; los modelos quedan listos en ~60s."""
    await asyncio.sleep(3)
    try:
        t0 = time.time()
        with SessionLocal() as db:
            elo, dc, n = build_engine_from_db(db)
            elo_ratings = {name: e.rating for name, e in elo.items()}
            factors = build_factors_from_db(db, elo_ratings)
        if n > 0:
            STATE.elo, STATE.dc = elo, dc
        if factors:
            STATE.factors = factors
        print(f"[warm-start] {n} partidos, {len(elo)} equipos, "
              f"{len(factors)} factores Klement — {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        print(f"[warm-start] error: {e}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Espera a que Postgres acepte conexiones (reintentos)
    last_err = None
    for _ in range(20):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            init_db()
            last_err = None
            break
        except Exception as e:
            last_err = e
            time.sleep(2)
    if last_err is not None:
        print(f"[startup] DB no disponible tras reintentos: {last_err}", flush=True)

    # Lanza el warm-start en background: la API ya responde /health
    asyncio.create_task(_warm_start())
    yield


app = FastAPI(
    title="Football Simulation Platform",
    version="1.0.0",
    description="Plataforma de simulación y predicción de fútbol: Copa del Mundo, ligas europeas, Champions League.",
    lifespan=lifespan,
)

# Registrar la API v1
from app.api.v1.router import v1_router
app.include_router(v1_router)


def _persist_prediction(model: str, p: tuple[float, float, float], extra: dict | None = None) -> None:
    """Best-effort persistence; never breaks the request if the DB is unavailable."""
    try:
        with SessionLocal() as db:
            repo.save_prediction(db, model, p[0], p[1], p[2], extra=extra)
            db.commit()
    except Exception:
        pass


class _State:
    """In-memory state. Replace with DB repositories in production."""
    def __init__(self):
        self.elo: dict[str, TeamElo] = {}
        self.elo_cfg = EloConfig()
        self.dc: DixonColes | None = None
        self.factors: dict[str, TeamFactors] = {}
        self.k_weights = KlementWeights()
        self.h_weights = HybridWeights()
        self.form: dict[str, float] = {}
        self.form_model: FormModel | None = None

STATE = _State()


class PredictResponse(BaseModel):
    home: str
    away: str
    home_win: float
    draw: float
    away_win: float
    source: str


@app.get("/predict-match", response_model=PredictResponse)
def predict_match(
    home: str = Query(...),
    away: str = Query(...),
    neutral: bool = True,
    model: Literal["hybrid", "elo", "dixon_coles", "klement"] = "hybrid",
):
    try:
        return _predict_match_impl(home, away, neutral, model)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[predict-match ERROR] {e}\n{traceback.format_exc()}", flush=True)
        raise HTTPException(500, f"Error interno: {type(e).__name__}: {e}")


def _predict_match_impl(home: str, away: str, neutral: bool, model: str) -> PredictResponse:
    for t in (home, away):
        if t not in STATE.elo and t not in STATE.factors:
            raise HTTPException(404, f"Equipo desconocido: {t}. Carga datos primero.")

    def elo_p():
        h = STATE.elo.get(home, TeamElo()); a = STATE.elo.get(away, TeamElo())
        return win_draw_loss_probs(h.rating, a.rating, STATE.elo_cfg, neutral)

    def dc_p():
        if STATE.dc is None or STATE.dc.params is None:
            return None
        if home not in STATE.dc.params.attack or away not in STATE.dc.params.attack:
            return None
        p = STATE.dc.match_probabilities(home, away, neutral)
        return p["home_win"], p["draw"], p["away_win"]

    def klement_p():
        if home not in STATE.factors or away not in STATE.factors:
            return None
        sh = klement_score(STATE.factors[home], STATE.k_weights)
        sa = klement_score(STATE.factors[away], STATE.k_weights)
        return klement_match_probs(sh, sa)

    def xgb_p():
        if STATE.form_model is None or not STATE.form_model.fitted:
            return None
        h_elo = STATE.elo.get(home, TeamElo())
        a_elo = STATE.elo.get(away, TeamElo())
        feats = {
            "elo_diff":     h_elo.rating  - a_elo.rating,
            "attack_diff":  h_elo.attack  - a_elo.attack,
            "defense_diff": h_elo.defense - a_elo.defense,
            "form_diff":    STATE.form.get(home, 1.5) - STATE.form.get(away, 1.5),
            "fifa_diff":    0.0,
            "neutral":      1.0 if neutral else 0.0,
        }
        return STATE.form_model.predict_one(feats)

    if model == "elo":
        p = elo_p()
        src = "elo"
    elif model == "dixon_coles":
        p = dc_p()
        if p is None:
            raise HTTPException(409, "Dixon-Coles no entrenado. Llama a POST /retrain.")
        src = "dixon_coles"
    elif model == "klement":
        p = klement_p()
        if p is None:
            raise HTTPException(409, "Factores Klement no cargados para estos equipos.")
        src = "klement"
    else:
        # Hybrid con pesos aprendidos (Klement 2.0)
        blend_result = blend_smart(
            dc=dc_p(),
            xgb=xgb_p(),
            elo=elo_p() if home in STATE.elo and away in STATE.elo else None,
            klement=klement_p(),
        )
        if blend_result is None:
            p = elo_p()
            src = "elo_fallback"
        else:
            p, src = blend_result

    # Guardar que p es una tupla válida de 3 floats
    if p is None or len(p) != 3:
        raise HTTPException(409, "Sin datos suficientes para predecir. Carga partidos primero.")

    _persist_prediction(src, p, extra={"home": home, "away": away, "neutral": neutral})
    return PredictResponse(home=home, away=away, home_win=float(p[0]), draw=float(p[1]),
                           away_win=float(p[2]), source=src)


@app.get("/elo-rankings")
def elo_rankings():
    rows = sorted(STATE.elo.items(), key=lambda kv: kv[1].rating, reverse=True)
    return [{"rank": i + 1, "team": t, "rating": round(e.rating, 1),
             "attack": round(e.attack, 1), "defense": round(e.defense, 1)}
            for i, (t, e) in enumerate(rows)]


@app.get("/team-probabilities")
def team_probabilities(
    n_sims: int = Query(10_000, ge=1000, le=1_000_000),
):
    if not STATE.elo:
        raise HTTPException(409, "No teams/ratings loaded. Call POST /retrain.")
    # Demo grouping: chunk loaded teams into groups of 4. Replace with real draw.
    rows = sorted(
    STATE.elo.items(),
    key=lambda kv: kv[1].rating,
    reverse=True
)
    teams = [t for t,_ in rows[:48]]
    groups = [Group(str(i // 4 + 1), teams[i:i + 4])
              for i in range(0, len(teams) - len(teams) % 4, 4)]
    if not groups:
        raise HTTPException(409, "Need at least 4 teams to form a group.")

    prob_matrix = {}

    for home in teams:
        for away in teams:
            if home == away:
                continue

            hh = STATE.elo[home]
            aa = STATE.elo[away]

            prob_matrix[(home, away)] = win_draw_loss_probs(
                hh.rating,
                aa.rating,
                STATE.elo_cfg,
                True
            )
    def model(h, a, neutral):
        return prob_matrix[(h, a)]

    res = simulate(groups, model, n_sims=n_sims)
    return {"n_sims": res.n_sims, "champion": res.champion,
            "finalist": res.finalist, "semifinalist": res.semifinalist,
            "group_qualified": res.group_qualified}


@app.get("/simulate-tournament")
def simulate_tournament(n_sims: int = Query(10_000, ge=1000, le=1_000_000)):
    return team_probabilities(n_sims)


@app.get("/model-performance")
def model_performance():
    """Return stored evaluation metrics. Empty list (not fabricated) until an
    evaluation has been run on real held-out data and persisted to model_metrics."""
    try:
        with SessionLocal() as db:
            rows = repo.latest_metrics(db)
            return [{"model": r.model, "accuracy": r.accuracy,
                     "brier_score": r.brier_score, "log_loss": r.log_loss,
                     "calibration_err": r.calibration_err, "roi": r.roi,
                     "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None}
                    for r in rows]
    except Exception as e:
        raise HTTPException(500, f"DB error: {e}")


class RetrainRequest(BaseModel):
    # Minimal payload: historical matches to (re)fit Elo + Dixon-Coles.
    home_teams: list[str]
    away_teams: list[str]
    home_goals: list[int]
    away_goals: list[int]


@app.post("/retrain")
def retrain(req: RetrainRequest):
    if not (len(req.home_teams) == len(req.away_teams)
            == len(req.home_goals) == len(req.away_goals)):
        raise HTTPException(400, "All input lists must be the same length.")
    # Fit Dixon-Coles
    dc = DixonColes()
    dc.fit(req.home_teams, req.away_teams, req.home_goals, req.away_goals)
    STATE.dc = dc
    # Rebuild Elo by replaying matches in order
    from app.models.elo import update_match
    STATE.elo = {}
    for h, a, hg, ag in zip(req.home_teams, req.away_teams, req.home_goals, req.away_goals):
        STATE.elo.setdefault(h, TeamElo()); STATE.elo.setdefault(a, TeamElo())
        nh, na = update_match(STATE.elo[h], STATE.elo[a], hg, ag, STATE.elo_cfg,
                              "world_cup_group", neutral=True)
        STATE.elo[h], STATE.elo[a] = nh, na
    return {"status": "ok", "teams": len(STATE.elo),
            "matches": len(req.home_teams),
            "dc_home_adv": round(dc.params.home_adv, 4)}


@app.post("/load-from-db")
def load_from_db():
    """Rebuild Elo + Dixon-Coles from matches stored in the database."""
    with SessionLocal() as db:
        elo, dc, n = build_engine_from_db(db)
    if n == 0:
        raise HTTPException(409, "No matches in DB. Run the ETL or POST /retrain.")
    STATE.elo, STATE.dc = elo, dc
    return {"status": "ok", "matches": n, "teams": len(elo),
            "dixon_coles_fitted": dc is not None}


@app.post("/train-form-model")
def train_form_model(train_frac: float = Query(1.0, gt=0.0, le=1.0)):
    """Train the XGBoost form model from stored match history (walk-forward features)."""
    with SessionLocal() as db:
        from app.services.bootstrap import load_match_rows
        rows = load_match_rows(db)
    if len(rows) < 100:
        raise HTTPException(409, f"Need >=100 matches to train; have {len(rows)}.")
    feats, outcomes = walk_forward(rows)
    import numpy as np
    X, y = build_features(feats), np.asarray(outcomes)
    split = int(train_frac * len(y))
    model = FormModel().fit(X[:split], y[:split])
    STATE.form_model = model
    return {"status": "ok", "trained_on": split, "total_matches": len(rows)}


@app.post("/load-factors")
def load_factors():
    """Build Klement socio-economic factors from the DB (teams + FIFA points).

    Run the ETL `python -m etl.load_factors --csv factors.csv` first to populate
    the data. Teams without GDP/population/FIFA points are skipped (not faked)."""
    with SessionLocal() as db:
        elo_ratings = {name: e.rating for name, e in STATE.elo.items()}
        factors = build_factors_from_db(db, elo_ratings)
    if not factors:
        raise HTTPException(409, "No socio-economic factors in DB. Run "
                                 "`python -m etl.load_factors --csv factors.csv` first "
                                 "(necesitas al menos PIB y población por país).")
    STATE.factors = factors
    return {"status": "ok", "teams_with_factors": len(factors),
            "sample": sorted(factors.keys())[:10]}


@app.get("/health")
def health():
    return {"status": "ok", "teams_loaded": len(STATE.elo),
            "dc_ready": STATE.dc is not None and STATE.dc.params is not None,
            "form_model_ready": STATE.form_model is not None,
            "klement_factors_loaded": len(STATE.factors)}
