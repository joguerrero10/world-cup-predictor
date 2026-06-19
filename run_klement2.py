from app.models.backtest import backtest_form_model
from app.models.metrics import optimise_weights
from app.services.bootstrap import load_match_rows
from app.services.features import walk_forward
from app.models.form_model import build_features
from app.models.elo import EloConfig, TeamElo, win_draw_loss_probs
from app.models.dixon_coles import DixonColes
from app.db.database import SessionLocal
import numpy as np

print("Cargando partidos desde la BD...")
with SessionLocal() as db:
    rows = load_match_rows(db)
print(f"  {len(rows)} partidos cargados")

# Generar features walk-forward (sin fuga de datos)
print("Calculando features walk-forward...")
feats, outcomes = walk_forward(rows)
X = build_features(feats)
y = np.asarray(outcomes)

# Backtest walk-forward: entrena en 70%, evalúa en 30%
print("Corriendo backtest walk-forward (puede tardar ~2 min)...")
res = backtest_form_model(rows, train_frac=0.7, n_estimators=300)
print("\n=== MÉTRICAS DEL BACKTEST ===")
for k, v in res.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

# Generar predicciones de cada sub-modelo para optimizar pesos
print("\nGenerando predicciones por sub-modelo...")
split = int(0.7 * len(y))
X_test, y_test = X[split:], y[split:]

# Elo predictions
elo_state = {}
cfg = EloConfig()
for m in rows:
    elo_state.setdefault(m.home, TeamElo())
    elo_state.setdefault(m.away, TeamElo())
elo_probs = np.array([
    win_draw_loss_probs(
        elo_state.get(rows[split+i].home, TeamElo()).rating,
        elo_state.get(rows[split+i].away, TeamElo()).rating,
        cfg, neutral=rows[split+i].neutral
    ) for i in range(len(y_test))
])

# Dixon-Coles predictions
print("Ajustando Dixon-Coles en datos de entrenamiento...")
dc = DixonColes()
dc.fit(
    [m.home for m in rows[:split]],
    [m.away for m in rows[:split]],
    [m.home_goals for m in rows[:split]],
    [m.away_goals for m in rows[:split]],
)
dc_probs = []
for m in rows[split:]:
    try:
        p = dc.match_probabilities(m.home, m.away, m.neutral)
        dc_probs.append([p["home_win"], p["draw"], p["away_win"]])
    except Exception:
        dc_probs.append([1/3, 1/3, 1/3])
dc_probs = np.array(dc_probs)

# XGBoost form model predictions
from app.models.form_model import FormModel
print("Entrenando XGBoost en datos de entrenamiento...")
xgb = FormModel(n_estimators=300).fit(X[:split], y[:split])
xgb_probs = xgb.predict_proba(X_test)

# Optimizar pesos (Klement 2.0)
print("\nOptimizando pesos del modelo híbrido (Klement 2.0)...")
sub_models = {"elo": elo_probs, "dixon_coles": dc_probs, "xgboost": xgb_probs}
best_weights = optimise_weights(sub_models, y_test, objective="log_loss")

print("\n=== PESOS ÓPTIMOS (Klement 2.0) ===")
for model, w in sorted(best_weights.items(), key=lambda x: -x[1]):
    print(f"  {model}: {w*100:.1f}%")

print("\n=== PESOS ACTUALES DEL SISTEMA ===")
print("  elo: 40.0%  dixon_coles: 20.0%  klement: 30.0%  form: 10.0%")
print("\nPara aplicar los pesos óptimos, actualiza HybridWeights en app/main.py")
print("o llama a POST /retrain con los nuevos pesos.")
