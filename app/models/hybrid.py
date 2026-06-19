"""
Hybrid 1X2 model — pesos calibrados con Klement 2.0.

Pesos aprendidos sobre 49.425 partidos reales (backtest walk-forward 70/30):
    XGBoost (forma):  80.9 %
    Dixon-Coles:      19.1 %
    Elo:               0.0 %  ← redundante: XGBoost ya captura elo_diff internamente
    Klement:           0.0 %  ← excluido del backtest por falta de datos históricos
                               pero se mantiene activo cuando hay factores cargados
                               (aporta en contexto de torneo completo).

El blend degrada con elegancia: si XGBoost no está entrenado, usa solo
Dixon-Coles; si Klement tiene factores, se añade con peso fijo 0.15 y
los demás se renormalizan.
"""
from __future__ import annotations
from dataclasses import dataclass

Probs = tuple[float, float, float]   # (home_win, draw, away_win)


@dataclass
class HybridWeights:
    # Pesos base — actualizados con Klement 2.0 (backtest real 49.425 partidos)
    xgboost:     float = 0.809   # mayor peso: captura forma, Elo y patrón de goles
    dixon_coles: float = 0.191   # segundo: modelo probabilístico de marcadores
    elo:         float = 0.000   # redundante con xgboost (elo_diff ya es feature)
    klement:     float = 0.000   # activado dinámicamente si hay factores (ver blend_smart)

    def normalised(self) -> "HybridWeights":
        s = self.xgboost + self.dixon_coles + self.elo + self.klement
        if s == 0:
            raise ValueError("Todos los pesos son cero.")
        return HybridWeights(
            self.xgboost / s, self.dixon_coles / s,
            self.elo / s, self.klement / s
        )


def blend(klement: Probs, elo: Probs, dc: Probs, form: Probs,
          w: HybridWeights) -> Probs:
    """
    Mezcla lineal clásica (para compatibilidad con código existente).
    En producción usa blend_smart().
    """
    w = w.normalised()
    out = tuple(
        w.klement * klement[i] + w.elo * elo[i]
        + w.dixon_coles * dc[i] + w.xgboost * form[i]
        for i in range(3)
    )
    s = sum(out)
    return (out[0]/s, out[1]/s, out[2]/s) if s else (1/3, 1/3, 1/3)


def blend_smart(
    dc:       Probs | None,
    xgb:      Probs | None,
    elo:      Probs | None,
    klement:  Probs | None,
) -> tuple[Probs, str]:
    """
    Blend inteligente con degradación elegante.

    Prioridad de pesos aprendidos:
        XGBoost 80.9%  +  Dixon-Coles 19.1%
        Si XGBoost no disponible → Dixon-Coles 70%  +  Elo 30%
        Klement, si disponible  → añade 15%, renormaliza el resto

    Devuelve (probabilidades, descripción de los modelos usados).
    """
    parts: list[tuple[float, Probs, str]] = []

    if xgb is not None:
        parts.append((0.809, xgb, "xgb"))
        if dc is not None:
            parts.append((0.191, dc, "dc"))
    elif dc is not None:
        parts.append((0.700, dc, "dc"))
        if elo is not None:
            parts.append((0.300, elo, "elo"))
    elif elo is not None:
        parts.append((1.000, elo, "elo"))

    if not parts:
        return (1/3, 1/3, 1/3), "uniform"

    # Añadir Klement con peso fijo 0.15, renormalizar el resto
    if klement is not None:
        kl_w = 0.15
        scale = 1.0 - kl_w
        parts = [(w * scale, p, n) for w, p, n in parts]
        parts.append((kl_w, klement, "klement"))

    total_w = sum(w for w, _, _ in parts)
    out = tuple(
        sum(w * p[i] for w, p, _ in parts) / total_w
        for i in range(3)
    )
    s = sum(out)
    probs = (out[0]/s, out[1]/s, out[2]/s) if s else (1/3, 1/3, 1/3)
    label = "hybrid(" + "+".join(n for _, _, n in parts) + ")"
    return probs, label


def form_probs(home_form: float, away_form: float) -> Probs:
    """1X2 de forma reciente (puntos por partido en [0,3])."""
    h = max(home_form, 0.0) + 0.5
    a = max(away_form, 0.0) + 0.5
    e = h / (h + a)
    p_draw = 0.24
    rest = 1.0 - p_draw
    return rest * e, p_draw, rest * (1.0 - e)
