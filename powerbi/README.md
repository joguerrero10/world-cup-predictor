# Power BI — Guía de construcción (World Cup Predictor AI)

No puedo generar un archivo binario `.pbix`. Esto es lo que sí se entrega y que te
permite construir el informe completo: el modelo de datos, las relaciones, las
medidas DAX (`measures.dax`) y el paso a paso de las 7 páginas.

## 1. Conexión a datos

Power BI Desktop → **Obtener datos → PostgreSQL**.
- Servidor: `localhost:5432` (o el host del contenedor `db`)
- Base de datos: `worldcup`
- Modo: **Import** para tableros rápidos, o **DirectQuery** si quieres que las
  predicciones se actualicen en vivo a medida que la API escribe en la BD.

Importa estas tablas: `teams`, `matches`, `predictions`, `elo_history`,
`fifa_rankings`, `tournament_results`, `simulations`, `model_metrics`.

## 2. Relaciones (modelo en estrella)

Crea estas relaciones (todas *muchos a uno* hacia `teams`):

| Desde | Columna | Hacia | Columna |
|---|---|---|---|
| `elo_history` | `team_id` | `teams` | `id` |
| `fifa_rankings` | `team_id` | `teams` | `id` |
| `tournament_results` | `team_id` | `teams` | `id` |
| `predictions` | `match_id` | `matches` | `id` |
| `tournament_results` | `simulation_id` | `simulations` | `id` |
| `matches` | `home_team` | `teams` | `id` (rol activo) |

Para `matches[away_team]` usa una segunda relación inactiva + `USERELATIONSHIP`, o
una tabla `teams` duplicada con rol "Visitante".

## 3. Medidas

Crea una tabla vacía llamada `Measures` y pega cada medida de `measures.dax`.
Están agrupadas por página.

## 4. Las 7 páginas

1. **Próximo partido** — segmentador por `matches`; tarjetas con `Prob Local`,
   `Prob Empate`, `Prob Visitante`; gráfico de barras 1X2; tarjeta `Resultado Más Probable`.
2. **Ranking Elo** — tabla `teams[name]` + `Elo Actual`, `Elo Ofensivo`,
   `Elo Defensivo`, `Ranking Elo`; barras horizontales ordenadas por `Elo Actual`.
3. **Probabilidades de campeón** — barras con `Prob Campeón` por equipo; tarjetas
   con `Prob Finalista` / `Prob Semifinalista` del equipo seleccionado.
4. **Evolución histórica Elo** — líneas: eje X `elo_history[as_of]`, valor
   `Elo en Fecha`, leyenda `teams[name]`; medida `Elo Δ desde Inicio`.
5. **Comparación de modelos** — barras agrupadas con `Prob Local (Elo)`,
   `(Dixon-Coles)`, `(Klement)`, `(Híbrido)` para el partido seleccionado.
6. **Precisión del modelo** — matriz por `model_metrics[model]` con `Accuracy`,
   `Brier Score`, `Log Loss`, `Calibration Error`, `ROI`; tarjeta `Nombre Mejor Modelo`.
7. **Simulación interactiva** — segmentador `simulations[n_sims]`
   (10k / 50k / 100k / 1M) que recalcula las medidas de la Página 3.

## 5. Actualización

- **Import**: programa el refresco, o usa un gateway si la BD es local.
- **DirectQuery**: el tablero refleja en vivo cada `POST /predict-match` y cada
  simulación guardada por la API.

## Nota de honestidad

Las páginas muestran lo que haya en la BD. Si aún no has corrido evaluaciones, la
Página 6 saldrá vacía (no se inventan métricas). Llena `model_metrics` ejecutando
el backtest (`app/models/backtest.py`) sobre datos reales y persistiendo el resultado.
