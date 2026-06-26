"""
Endpoints de analítica avanzada — consumidos por el frontend React.

GET  /api/v1/system-stats       — KPIs del sistema
GET  /api/v1/competitions       — lista de competiciones
GET  /api/v1/teams-list         — equipos con datos Elo
GET  /api/v1/model-weights      — pesos del modelo híbrido
GET  /api/v1/klement-factors    — factores socioeconómicos Klement
GET  /api/v1/dixon-coles-params — parámetros Dixon-Coles
GET  /api/v1/score-matrix       — matriz de probabilidades de marcador
GET  /api/v1/ai-analysis        — informe IA automático
POST /api/v1/ai-chat            — chat IA sobre el backend
"""
from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Literal

router = APIRouter(tags=["analytics"])


def _state():
    from app.main import STATE
    return STATE


# ─── System Stats ─────────────────────────────────────────────────────────────

@router.get("/system-stats")
def system_stats():
    S = _state()
    try:
        from app.db.database import SessionLocal
        from app.db.models import Match, Player, SimulationJob
        from sqlalchemy import select, func
        with SessionLocal() as db:
            matches_count  = db.scalar(select(func.count(Match.id))) or 0
            players_count  = db.scalar(select(func.count(Player.id))) or 0
            sims_count     = db.scalar(select(func.count(SimulationJob.id))) or 0
            avg_sim_time   = db.scalar(
                select(func.avg(SimulationJob.duration_seconds))
                .where(SimulationJob.status == "completed")
            )
            last_job = db.scalar(
                select(SimulationJob.completed_at)
                .where(SimulationJob.status == "completed")
                .order_by(SimulationJob.completed_at.desc())
            )
    except Exception:
        matches_count = players_count = sims_count = 0
        avg_sim_time = last_job = None

    # Model accuracy from metrics
    model_acc = None
    try:
        from app.db.database import SessionLocal
        from app.db import repositories as repo
        with SessionLocal() as db:
            metrics = repo.latest_metrics(db)
            if metrics:
                for m in metrics:
                    if m.model == "hybrid" and m.accuracy:
                        model_acc = m.accuracy
                        break
    except Exception:
        pass

    active_model = "hybrid"
    if S.form_model and getattr(S.form_model, "fitted", False):
        active_model = "hybrid(xgb+dc)"
    elif S.dc and S.dc.params:
        active_model = "hybrid(dc+elo)"

    return {
        "teams_loaded":      len(S.elo),
        "players_count":     players_count,
        "matches_count":     matches_count,
        "leagues_count":     6,
        "active_model":      active_model,
        "model_accuracy":    model_acc,
        "dc_ready":          S.dc is not None and S.dc.params is not None,
        "klement_loaded":    len(S.factors),
        "form_model_ready":  S.form_model is not None and getattr(S.form_model, "fitted", False),
        "simulations_count": sims_count,
        "avg_simulation_time": float(avg_sim_time) if avg_sim_time else None,
        "last_updated":      last_job.isoformat() if last_job else None,
    }


# ─── Competitions ─────────────────────────────────────────────────────────────

@router.get("/competitions")
def list_competitions():
    from app.models.competition import COMPETITIONS
    return [
        {
            "id":               c.id,
            "name":             c.name,
            "competition_type": c.competition_type.value,
            "tier":             c.tier.value,
            "country":          c.country,
            "n_teams":          c.n_teams,
            "relegation_spots": c.relegation_spots,
            "ucl_spots":        c.ucl_spots,
        }
        for c in COMPETITIONS.values()
    ]


# ─── Teams list ───────────────────────────────────────────────────────────────

@router.get("/teams-list")
def teams_list():
    S = _state()
    if not S.elo:
        return []
    rows = sorted(S.elo.items(), key=lambda kv: -kv[1].rating)
    return [
        {
            "rank":    i + 1,
            "team":    t,
            "rating":  round(e.rating, 1),
            "attack":  round(e.attack, 1),
            "defense": round(e.defense, 1),
        }
        for i, (t, e) in enumerate(rows)
    ]


# ─── Model weights ────────────────────────────────────────────────────────────

@router.get("/model-weights")
def model_weights():
    S = _state()
    w = S.h_weights
    return {
        "xgboost":      w.xgboost,
        "dixon_coles":  w.dixon_coles,
        "elo":          w.elo,
        "klement":      w.klement,
        "total_matches": 49_425,
        "description":  "Pesos calibrados sobre 49,425 partidos reales (backtest walk-forward 70/30)",
    }


# ─── Klement factors ──────────────────────────────────────────────────────────

@router.get("/klement-factors")
def klement_factors():
    S = _state()
    if not S.factors:
        return []
    from app.models.klement import klement_score
    result = []
    for team, f in S.factors.items():
        score = klement_score(f, S.k_weights)
        result.append({
            "team":            team,
            "gdp_per_capita":  f.gdp_per_capita,
            "population":      f.population,
            "fifa_points":     f.fifa_points,
            "football_culture":f.football_culture,
            "is_host":         f.is_host,
            "confederation":   f.confederation,
            "klement_score":   round(score, 4),
        })
    return sorted(result, key=lambda x: -(x["klement_score"] or 0))


# ─── Dixon-Coles params ───────────────────────────────────────────────────────

@router.get("/dixon-coles-params")
def dixon_coles_params():
    S = _state()
    if S.dc is None or S.dc.params is None:
        return {
            "teams":    [],
            "attack":   {},
            "defense":  {},
            "home_adv": 0.0,
            "rho":      0.0,
            "fitted":   False,
        }
    p = S.dc.params
    return {
        "teams":    p.teams,
        "attack":   {t: round(v, 4) for t, v in p.attack.items()},
        "defense":  {t: round(v, 4) for t, v in p.defense.items()},
        "home_adv": round(p.home_adv, 4),
        "rho":      round(p.rho, 4),
        "fitted":   True,
    }


# ─── Score matrix ─────────────────────────────────────────────────────────────

@router.get("/score-matrix")
def score_matrix(
    home: str = Query(...),
    away: str = Query(...),
    neutral: bool = Query(True),
):
    S = _state()
    if S.dc is None or S.dc.params is None:
        raise HTTPException(409, "Dixon-Coles no entrenado.")
    if home not in S.dc.params.attack or away not in S.dc.params.attack:
        raise HTTPException(404, f"Equipos no encontrados en Dixon-Coles: {home}, {away}")

    mat = S.dc.score_matrix(home, away, neutral)
    import math
    p = S.dc.params
    gamma = 0.0 if neutral else p.home_adv
    home_lambda = math.exp(p.attack[home] - p.defense[away] + gamma)
    away_mu     = math.exp(p.attack[away] - p.defense[home])

    return {
        "home":        home,
        "away":        away,
        "matrix":      mat.tolist(),
        "max_goals":   S.dc.max_goals,
        "home_lambda": round(home_lambda, 3),
        "away_mu":     round(away_mu, 3),
    }


# ─── AI Analysis ─────────────────────────────────────────────────────────────

@router.get("/ai-analysis")
def ai_analysis(
    home: str = Query(...),
    away: str = Query(...),
    model: Literal["hybrid", "elo", "dixon_coles", "klement"] = "hybrid",
):
    """Genera un informe de análisis IA completo automáticamente."""
    S = _state()

    if home not in S.elo and home not in S.factors:
        raise HTTPException(404, f"Equipo no encontrado: {home}")
    if away not in S.elo and away not in S.factors:
        raise HTTPException(404, f"Equipo no encontrado: {away}")

    # Get prediction
    from app.models.elo import win_draw_loss_probs, TeamElo
    from app.models.klement import klement_score, klement_match_probs
    from app.models.hybrid import blend_smart

    h_elo = S.elo.get(home, TeamElo())
    a_elo = S.elo.get(away, TeamElo())

    def elo_p():
        return win_draw_loss_probs(h_elo.rating, a_elo.rating, S.elo_cfg, True)

    def dc_p():
        if S.dc and S.dc.params and home in S.dc.params.attack and away in S.dc.params.attack:
            p = S.dc.match_probabilities(home, away, True)
            return p["home_win"], p["draw"], p["away_win"]
        return None

    def klement_p():
        if home in S.factors and away in S.factors:
            sh = klement_score(S.factors[home], S.k_weights)
            sa = klement_score(S.factors[away], S.k_weights)
            return klement_match_probs(sh, sa)
        return None

    def xgb_p():
        if S.form_model and getattr(S.form_model, "fitted", False):
            feats = {
                "elo_diff":     h_elo.rating - a_elo.rating,
                "attack_diff":  h_elo.attack - a_elo.attack,
                "defense_diff": h_elo.defense - a_elo.defense,
                "form_diff":    S.form.get(home, 1.5) - S.form.get(away, 1.5),
                "fifa_diff":    0.0,
                "neutral":      1.0,
            }
            return S.form_model.predict_one(feats)
        return None

    blend = blend_smart(dc=dc_p(), xgb=xgb_p(), elo=elo_p(), klement=klement_p())
    if blend is None:
        probs = elo_p()
        src = "elo"
    else:
        probs, src = blend

    home_win, draw, away_win = float(probs[0]), float(probs[1]), float(probs[2])

    # DC extras
    most_likely = None
    dc_info = dc_p()
    if S.dc and S.dc.params and home in S.dc.params.attack and away in S.dc.params.attack:
        dc_full = S.dc.match_probabilities(home, away, True)
        most_likely = dc_full.get("most_likely_score")

    # Determine confidence
    elo_diff = abs(h_elo.rating - a_elo.rating)
    confidence = "high" if elo_diff > 200 else "medium" if elo_diff > 100 else "low"

    # Data sources used
    data_sources = ["Elo"]
    if dc_p() is not None:    data_sources.append("Dixon-Coles")
    if klement_p() is not None: data_sources.append("Klement")
    if xgb_p() is not None:   data_sources.append("XGBoost")

    # Generate automatic report
    report = _generate_report(
        home=home, away=away,
        home_win=home_win, draw=draw, away_win=away_win,
        h_elo=h_elo, a_elo=a_elo,
        most_likely=most_likely,
        src=src, data_sources=data_sources,
        dc_probs=dc_p(), klement_probs=klement_p(),
        S=S,
    )

    return {
        "home":       home,
        "away":       away,
        "model":      model,
        "home_win":   round(home_win, 4),
        "draw":       round(draw, 4),
        "away_win":   round(away_win, 4),
        "most_likely_score": most_likely,
        "report":     report,
        "model_contributions": {
            "xgboost":     S.h_weights.xgboost,
            "dixon_coles": S.h_weights.dixon_coles,
            "elo":         S.h_weights.elo,
            "klement":     S.h_weights.klement,
            "total_matches": 49_425,
            "description": "",
        },
        "data_sources": data_sources,
        "confidence":   confidence,
        "model_accuracy": None,
    }


def _generate_report(
    home, away, home_win, draw, away_win,
    h_elo, a_elo, most_likely, src, data_sources, dc_probs, klement_probs, S
) -> str:
    from app.models.klement import klement_score

    winner = home if home_win > away_win and home_win > draw else (away if away_win > home_win and away_win > draw else "ninguno")
    winner_pct = max(home_win, away_win, draw) * 100
    elo_diff = h_elo.rating - a_elo.rating

    lines = []

    # Opening
    if winner == home:
        lines.append(f"{home} parte como favorito con un {home_win*100:.1f}% de probabilidad de victoria según el modelo {src.upper()}.")
    elif winner == away:
        lines.append(f"{away} llega como favorito con un {away_win*100:.1f}% de probabilidad de ganar según el modelo {src.upper()}.")
    else:
        lines.append(f"El enfrentamiento entre {home} y {away} se presenta muy igualado. El empate alcanza un {draw*100:.1f}% de probabilidad.")

    # Elo comparison
    if elo_diff > 50:
        lines.append(f"El modelo Elo favorece a {home} por {abs(elo_diff):.0f} puntos de rating ({h_elo.rating:.0f} vs {a_elo.rating:.0f}).")
    elif elo_diff < -50:
        lines.append(f"El modelo Elo favorece a {away} por {abs(elo_diff):.0f} puntos de rating ({a_elo.rating:.0f} vs {h_elo.rating:.0f}).")
    else:
        lines.append(f"Los ratings Elo son muy similares ({h_elo.rating:.0f} vs {a_elo.rating:.0f}), lo que refuerza la incertidumbre del resultado.")

    # Dixon-Coles
    if dc_probs is not None and S.dc and S.dc.params:
        try:
            import math
            p = S.dc.params
            home_lambda = math.exp(p.attack[home] - p.defense[away])
            away_mu     = math.exp(p.attack[away] - p.defense[home])
            total_goals  = home_lambda + away_mu
            lines.append(f"Dixon-Coles proyecta un promedio de {total_goals:.1f} goles totales (λ={home_lambda:.2f} para {home}, μ={away_mu:.2f} para {away}).")
        except Exception:
            pass

    # Klement
    if klement_probs and home in S.factors and away in S.factors:
        sh = klement_score(S.factors[home], S.k_weights)
        sa = klement_score(S.factors[away], S.k_weights)
        kl_diff = (sh - sa) * 100
        if abs(kl_diff) > 2:
            better = home if kl_diff > 0 else away
            lines.append(f"El factor socioeconómico Klement incrementa en {abs(kl_diff):.1f}% la probabilidad de {better} por su ventaja en PIB, cultura futbolística y ranking FIFA.")

    # Most likely score
    if most_likely:
        lines.append(f"El marcador más probable según Dixon-Coles es {home} {most_likely[0]}–{most_likely[1]} {away}.")

    # Attack comparison
    atk_diff = h_elo.attack - a_elo.attack
    def_diff  = h_elo.defense - a_elo.defense
    if abs(atk_diff) > 30:
        better_atk = home if atk_diff > 0 else away
        lines.append(f"{better_atk} muestra una superioridad ofensiva notable (diferencia de {abs(atk_diff):.0f} puntos en el índice de ataque).")
    if abs(def_diff) > 30:
        better_def = home if def_diff < 0 else away
        lines.append(f"{better_def} presenta una defensa más sólida según el índice defensivo Elo.")

    # Conclusion
    lines.append(f"El modelo híbrido ({src}) combina {', '.join(data_sources)} para obtener la predicción más robusta disponible con los datos actuales.")

    return "\n\n".join(lines)


# ─── AI Chat ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@router.post("/ai-chat")
def ai_chat(req: ChatRequest):
    """Chat IA que consulta el estado del backend y genera respuestas analíticas."""
    S = _state()
    msg_lower = req.message.lower()

    # Build context
    elo_sorted = sorted(S.elo.items(), key=lambda kv: -kv[1].rating)
    top5 = [t for t, _ in elo_sorted[:5]]
    bottom5 = [t for t, _ in elo_sorted[-5:]] if len(elo_sorted) >= 5 else []

    response = _answer_chat(msg_lower, req.message, S, elo_sorted, top5, bottom5)
    return {"response": response}


def _answer_chat(msg_lower: str, original_msg: str, S, elo_sorted, top5, bottom5) -> str:
    from app.models.elo import win_draw_loss_probs

    # Champions / winner questions
    if any(k in msg_lower for k in ["ganará", "campeón", "champion", "winner", "ganar"]):
        if top5:
            lines = [f"Según el modelo Elo actual, los equipos con mayor probabilidad de campeonar son:"]
            for i, team in enumerate(top5[:5], 1):
                e = S.elo[team]
                lines.append(f"  {i}. {team} — Elo: {e.rating:.0f}")
            lines.append(f"\nEl favorito absoluto es {top5[0]} con {S.elo[top5[0]].rating:.0f} puntos Elo.")
            if S.dc and S.dc.params:
                lines.append("Para una estimación más precisa, ejecuta la simulación de torneo con Monte Carlo.")
            return "\n".join(lines)

    # Relegation / descent
    if any(k in msg_lower for k in ["descenso", "relegated", "bajar", "últimos", "descend"]):
        if bottom5:
            lines = [f"Los equipos con menor rating Elo y mayor riesgo de descenso son:"]
            for i, team in enumerate(bottom5[:5], 1):
                e = S.elo[team]
                lines.append(f"  {i}. {team} — Elo: {e.rating:.0f}")
            return "\n".join(lines)

    # Best defense
    if any(k in msg_lower for k in ["mejor defensa", "defense", "defensiva", "sólida"]):
        def_sorted = sorted(S.elo.items(), key=lambda kv: kv[1].defense)[:5]
        if def_sorted:
            lines = ["Los equipos con mejor índice defensivo (menor es mejor):"]
            for i, (t, e) in enumerate(def_sorted, 1):
                lines.append(f"  {i}. {t} — Índice defensa: {e.defense:.0f}")
            return "\n".join(lines)

    # Best attack
    if any(k in msg_lower for k in ["mejor ataque", "attack", "ofensiva", "goles"]):
        atk_sorted = sorted(S.elo.items(), key=lambda kv: -kv[1].attack)[:5]
        if atk_sorted:
            lines = ["Los equipos con mayor índice ofensivo:"]
            for i, (t, e) in enumerate(atk_sorted, 1):
                lines.append(f"  {i}. {t} — Índice ataque: {e.attack:.0f}")
            return "\n".join(lines)

    # How many teams
    if any(k in msg_lower for k in ["cuántos equipos", "how many teams", "equipos cargados"]):
        return f"Actualmente hay {len(S.elo)} equipos cargados en el sistema. El modelo Elo tiene datos para todos ellos."

    # Explain hybrid model
    if any(k in msg_lower for k in ["híbrido", "hybrid", "cómo funciona", "modelo"]):
        return (
            "El modelo híbrido combina 4 modelos matemáticos:\n\n"
            "• XGBoost (80.9%): modelo de machine learning entrenado sobre 49,425 partidos históricos. "
            "Usa diferencias de Elo, ataque, defensa y forma reciente como features.\n\n"
            "• Dixon-Coles (19.1%): modelo probabilístico bivariado que estima la distribución conjunta "
            "de goles usando Poisson con corrección tau en marcadores bajos.\n\n"
            "• Elo (0% directo): incluido implícitamente como feature de XGBoost. Calcula la probabilidad "
            "usando el rating diferencial histórico.\n\n"
            "• Klement (variable): cuando los factores socioeconómicos están cargados, agrega un 15% de peso "
            "basado en PIB, población, cultura futbolística y ranking FIFA.\n\n"
            "Si XGBoost no está entrenado, el fallback es Dixon-Coles 70% + Elo 30%."
        )

    # Elo vs Dixon-Coles
    if any(k in msg_lower for k in ["diferencia", "elo vs", "dixon"]):
        return (
            "Diferencia entre Elo y Dixon-Coles:\n\n"
            "• Elo: sistema de rating por par de equipos. Calcula la probabilidad de victoria usando la diferencia "
            "de ratings. Es simple, rápido e interpretable, pero no modela directamente la distribución de goles.\n\n"
            "• Dixon-Coles: modelo estadístico que estima la distribución conjunta de goles (X, Y) usando "
            "dos Poisson independientes (λ para local, μ para visitante) más una corrección para marcadores "
            "bajos (0-0, 0-1, 1-0, 1-1). Permite obtener el marcador más probable y las probabilidades "
            "over/under, BTTS, etc.\n\n"
            "En la plataforma, el modelo híbrido combina ambos para obtener la mejor estimación."
        )

    # Default: general context
    n_teams = len(S.elo)
    dc_status = "entrenado ✓" if (S.dc and S.dc.params) else "no entrenado"
    xgb_status = "listo ✓" if (S.form_model and getattr(S.form_model, "fitted", False)) else "no entrenado"
    kl_status = f"{len(S.factors)} equipos" if S.factors else "no cargado"

    return (
        f"Estoy conectado al motor de análisis Football AI. Estado actual:\n\n"
        f"• {n_teams} equipos con ratings Elo\n"
        f"• Dixon-Coles: {dc_status}\n"
        f"• XGBoost: {xgb_status}\n"
        f"• Klement: {kl_status}\n\n"
        f"Puedo responder preguntas sobre predicciones, equipos, modelos y estadísticas. "
        f"¿Qué quieres saber? Por ejemplo: '¿Quién ganará el Mundial?', '¿Cuál tiene mejor defensa?', "
        f"'¿Cómo funciona el modelo híbrido?'"
    )
