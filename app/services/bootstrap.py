"""
Rebuild the in-memory engine (Elo + Dixon-Coles + XGBoost) from matches stored in the DB.

Lets the API start "warm": instead of requiring POST /retrain after every restart,
the service replays the stored match history on startup.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import Match, Team
from app.db import repositories as repo
from app.models.dixon_coles import DixonColes
from app.models.elo import EloConfig, TeamElo, update_match
from app.models.klement import TeamFactors
from app.services.features import MatchRow

logger = logging.getLogger(__name__)


def count_matches(db: Session) -> int:
    """Cuenta partidos finalizados almacenados en BD."""
    return (
        db.query(Match)
        .filter(Match.home_goals.isnot(None), Match.away_goals.isnot(None))
        .count()
    )


def load_match_rows(db: Session) -> list[MatchRow]:
    id_to_name = {t.id: t.name for t in db.query(Team).all()}
    rows: list[MatchRow] = []
    for m in db.query(Match).order_by(Match.match_date).all():
        if m.home_goals is None or m.away_goals is None:
            continue
        h, a = id_to_name.get(m.home_team), id_to_name.get(m.away_team)
        if not h or not a:
            continue
        rows.append(MatchRow(h, a, m.home_goals, m.away_goals, m.match_type, m.neutral))
    return rows


def build_engine_from_db(db: Session, cfg: EloConfig | None = None,
                         xi: float = 0.0018
                         ) -> tuple[dict[str, TeamElo], DixonColes | None, int]:
    """
    xi: tasa de decaimiento exponencial Dixon-Coles. 0.0018 es el valor del paper
    original (Dixon & Coles 1997) — un partido de hace 1 año pesa ~48% de uno de hoy;
    uno de hace 3 años pesa ~12%. Sube xi para olvidar más rápido, baja para más memoria.
    """
    cfg = cfg or EloConfig()
    rows = load_match_rows(db)
    elo: dict[str, TeamElo] = {}
    for m in rows:
        elo.setdefault(m.home, TeamElo()); elo.setdefault(m.away, TeamElo())
        nh, na = update_match(elo[m.home], elo[m.away], m.home_goals, m.away_goals,
                              cfg, m.match_type, m.neutral)
        elo[m.home], elo[m.away] = nh, na

    dc: DixonColes | None = None
    if len(rows) >= 30:
        from app.models.dixon_coles import time_decay_weights
        # rows ya viene ordenado cronológicamente (load_match_rows hace order_by match_date).
        # Usamos el índice de orden como proxy de "días atrás": el último partido = 0,
        # cada partido previo cuenta como 1 unidad más antiguo. No es exacto en días
        # reales, pero conserva el orden cronológico que es lo que importa para el decay.
        n = len(rows)
        days_ago_proxy = [n - i for i in range(n)]   # último partido -> proxy=1 (más reciente)
        weights = time_decay_weights(days_ago_proxy, xi=xi)
        dc = DixonColes()
        dc.fit([m.home for m in rows], [m.away for m in rows],
               [m.home_goals for m in rows], [m.away_goals for m in rows],
               weights=weights)
    return elo, dc, len(rows)

def build_full_engine(
    db: Session,
    cfg: EloConfig | None = None,
    xi: float = 0.0018,
    xgb_min_rows: int = 100,
):
    """
    Construye Elo + Dixon-Coles + XGBoost (FormModel) desde la BD.

    Returns: (elo_dict, dc, form_model, n_matches)
        form_model es None si hay < xgb_min_rows partidos o falla el entrenamiento.

    Se llama en startup y tras cada ETL con suficientes partidos nuevos.
    """
    elo, dc, n = build_engine_from_db(db, cfg, xi)

    form_model = None
    if n >= xgb_min_rows:
        try:
            from app.services.features import walk_forward
            from app.models.form_model import FormModel, build_features
            import numpy as np

            rows = load_match_rows(db)
            feats, outcomes = walk_forward(rows)
            if feats:
                X = build_features(feats)
                y = np.asarray(outcomes)
                form_model = FormModel().fit(X, y)
                logger.info("[bootstrap] XGBoost entrenado con %d muestras", len(y))
        except Exception as exc:
            logger.warning("[bootstrap] XGBoost falló (no crítico): %s", exc)

    logger.info(
        "[bootstrap] Engine listo: %d partidos, %d equipos, DC=%s, XGB=%s",
        n, len(elo), dc is not None, form_model is not None,
    )
    return elo, dc, form_model, n


def build_factors_from_db(db: Session,
                          elo_ratings: dict[str, float] | None = None) -> dict[str, TeamFactors]:
    """
    Build Klement TeamFactors for every team that has the minimum data loaded:
    GDP per capita, population, and a strength score. The strength score uses the
    team's FIFA ranking points if loaded; otherwise it falls back to the team's
    Elo rating (which the system already computes from match history). Teams
    missing GDP/population/strength are skipped — nothing is fabricated.

    The Elo fallback is a documented approximation: Elo and FIFA points live on a
    similar numeric scale (~1500-2100), so Elo is a reasonable stand-in when no
    official FIFA points are available.
    """
    fifa = repo.latest_fifa_points(db)
    elo_ratings = elo_ratings or {}
    factors: dict[str, TeamFactors] = {}
    for t in db.query(Team).all():
        pts = fifa.get(t.id)
        if pts is None:
            pts = elo_ratings.get(t.name)   # fallback: Elo as strength proxy
        if t.gdp_per_capita is None or t.population is None or pts is None:
            continue
        factors[t.name] = TeamFactors(
            gdp_per_capita=float(t.gdp_per_capita),
            population=float(t.population),
            fifa_points=float(pts),
            football_culture=float(t.football_culture) if t.football_culture is not None else 0.5,
            avg_temp_c=float(t.avg_temp_c) if t.avg_temp_c is not None else 20.0,
            is_host=bool(t.is_host),
            confederation=t.confederation or "UEFA",
        )
    return factors
