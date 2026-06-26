import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useQuery, useMutation } from "@tanstack/react-query"
import { Crosshair, Download, RefreshCw, ChevronDown } from "lucide-react"
import { fetchEloRankings, fetchPrediction, fetchAIAnalysis } from "../api/endpoints"
import { DuelBar, ProbBar } from "../components/ui/DuelBar"
import { Badge } from "../components/ui/Badge"
import { PlotlyChart, GaugeChart, DonutChart } from "../components/ui/PlotlyChart"
import type { ModelType } from "../types"
import type { Data } from "plotly.js"
import clsx from "clsx"

function pct(v: number) { return `${(v * 100).toFixed(1)}%` }

const MODELS: { value: ModelType; label: string }[] = [
  { value: "hybrid",      label: "Hybrid (recomendado)" },
  { value: "elo",         label: "Elo" },
  { value: "dixon_coles", label: "Dixon-Coles" },
  { value: "klement",     label: "Klement" },
]

const GOAL_PROBS = (lambda: number) => {
  const factorial = (n: number): number => n <= 1 ? 1 : n * factorial(n - 1)
  return Array.from({ length: 6 }, (_, k) => ({
    k,
    p: Math.exp(-lambda) * Math.pow(lambda, k) / factorial(k),
  }))
}

export function MatchPrediction() {
  const [home, setHome] = useState("")
  const [away, setAway] = useState("")
  const [model, setModel] = useState<ModelType>("hybrid")
  const [neutral, setNeutral] = useState(true)
  const [showAnalysis, setShowAnalysis] = useState(false)

  const { data: elo } = useQuery({ queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000 })
  const teams = elo?.map(t => t.team).sort() ?? []

  const { mutate: predict, data: result, isPending, error } = useMutation({
    mutationFn: () => fetchPrediction(home, away, model, neutral),
  })

  const { mutate: fetchAnalysis, data: analysis, isPending: aLoading } = useMutation({
    mutationFn: () => fetchAIAnalysis(home, away, model),
  })

  const canPredict = home && away && home !== away

  const homeElo = elo?.find(t => t.team === home)
  const awayElo = elo?.find(t => t.team === away)

  // Score matrix data (Poisson approximation if lambda available)
  const homeLambda = result?.btts_yes != null ? 1.3 : 1.2
  const awayMu = result?.btts_yes != null ? 1.1 : 1.0
  const homeGoalProbs = GOAL_PROBS(homeLambda)
  const awayGoalProbs = GOAL_PROBS(awayMu)

  const scoreMatrixData: Data[] = result ? [{
    type: "heatmap",
    z: Array.from({ length: 6 }, (_, i) =>
      Array.from({ length: 6 }, (_, j) => homeGoalProbs[i].p * awayGoalProbs[j].p)
    ),
    x: ["0", "1", "2", "3", "4", "5+"],
    y: ["0", "1", "2", "3", "4", "5+"],
    colorscale: [[0, "#0A0E1A"], [0.3, "#1E2D40"], [0.7, "#00D4FF60"], [1, "#00D4FF"]],
    showscale: false,
    hovertemplate: "%{y}-%{x}: %{z:.3f}<extra></extra>",
  } as Data] : []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Input panel */}
      <div className="card space-y-5">
        <div className="flex items-center gap-2">
          <Crosshair className="w-5 h-5 text-cyan" />
          <h2 className="section-title text-xl">CONFIGURAR PREDICCIÓN</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Home */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Equipo Local</label>
            <select
              value={home}
              onChange={e => setHome(e.target.value)}
              className="select-dark w-full"
            >
              <option value="">Seleccionar...</option>
              {teams.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Away */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Equipo Visitante</label>
            <select
              value={away}
              onChange={e => setAway(e.target.value)}
              className="select-dark w-full"
            >
              <option value="">Seleccionar...</option>
              {teams.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Model */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Modelo</label>
            <select
              value={model}
              onChange={e => setModel(e.target.value as ModelType)}
              className="select-dark w-full"
            >
              {MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>

          {/* Options */}
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Opciones</label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-text">
                <input
                  type="checkbox"
                  checked={neutral}
                  onChange={e => setNeutral(e.target.checked)}
                  className="w-4 h-4 accent-cyan rounded"
                />
                Campo neutral
              </label>
            </div>
            <button
              onClick={() => predict()}
              disabled={!canPredict || isPending}
              className={clsx(
                "btn-primary w-full flex items-center justify-center gap-2",
                (!canPredict || isPending) && "opacity-50 cursor-not-allowed"
              )}
            >
              {isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Crosshair className="w-4 h-4" />}
              {isPending ? "Calculando..." : "PREDECIR"}
            </button>
          </div>
        </div>

        {/* Team info row */}
        {(homeElo || awayElo) && (
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border">
            {homeElo && (
              <div className="flex items-center gap-4">
                <div className="team-badge text-xl">{home.slice(0, 2)}</div>
                <div>
                  <p className="font-semibold text-text">{home}</p>
                  <div className="flex gap-2 mt-1">
                    <Badge variant="cyan">Elo: {homeElo.rating.toFixed(0)}</Badge>
                    <Badge variant="muted">Atk: {homeElo.attack.toFixed(0)}</Badge>
                    <Badge variant="muted">Def: {homeElo.defense.toFixed(0)}</Badge>
                  </div>
                </div>
              </div>
            )}
            {awayElo && (
              <div className="flex items-center gap-4 justify-end">
                <div className="text-right">
                  <p className="font-semibold text-text">{away}</p>
                  <div className="flex gap-2 mt-1 justify-end">
                    <Badge variant="amber">Elo: {awayElo.rating.toFixed(0)}</Badge>
                    <Badge variant="muted">Atk: {awayElo.attack.toFixed(0)}</Badge>
                    <Badge variant="muted">Def: {awayElo.defense.toFixed(0)}</Badge>
                  </div>
                </div>
                <div className="team-badge text-xl">{away.slice(0, 2)}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="card border-scarlet/30 bg-scarlet/5 text-scarlet text-sm p-4">
          {String(error)}
        </div>
      )}

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            {/* Duel Card */}
            <div className="card">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <p className="section-label">Resultado del modelo</p>
                  <h2 className="section-title">{result.home} vs {result.away}</h2>
                </div>
                <Badge variant="cyan">{result.source.toUpperCase()}</Badge>
              </div>
              <DuelBar
                home={result.home}
                away={result.away}
                homeWin={result.home_win}
                draw={result.draw}
                awayWin={result.away_win}
              />
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Gauge charts */}
              <div className="card">
                <p className="section-label mb-2">Probabilidades gauge</p>
                <GaugeChart value={result.home_win} label={`${result.home} gana`} color="#00D4FF" />
              </div>
              <div className="card">
                <GaugeChart value={result.draw} label="Empate" color="#64748B" />
              </div>
              <div className="card">
                <GaugeChart value={result.away_win} label={`${result.away} gana`} color="#F0B429" />
              </div>
            </div>

            {/* Extra stats + score matrix */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Score & extras */}
              <div className="card space-y-4">
                <p className="section-label">Resultado esperado</p>
                {result.most_likely_score && (
                  <div className="flex items-center justify-center gap-6 py-4 bg-gradient-field rounded-xl">
                    <div className="text-center">
                      <p className="font-display text-5xl tracking-wider text-cyan">{result.most_likely_score[0]}</p>
                      <p className="text-xs text-muted uppercase">{result.home}</p>
                    </div>
                    <p className="font-display text-3xl text-muted">–</p>
                    <div className="text-center">
                      <p className="font-display text-5xl tracking-wider text-amber">{result.most_likely_score[1]}</p>
                      <p className="text-xs text-muted uppercase">{result.away}</p>
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  {result.over_2_5 != null && <ProbBar label="Más de 2.5 goles" value={result.over_2_5} color="#00D4FF" />}
                  {result.under_2_5 != null && <ProbBar label="Menos de 2.5 goles" value={result.under_2_5} color="#64748B" />}
                  {result.btts_yes != null && <ProbBar label="Ambos anotan" value={result.btts_yes} color="#22C55E" />}
                  {result.btts_no != null && <ProbBar label="Al menos uno no anota" value={result.btts_no} color="#EF4444" />}
                </div>
              </div>

              {/* Score matrix heatmap */}
              <div className="card">
                <p className="section-label mb-2">Distribución de marcadores</p>
                <p className="text-xs text-muted mb-3">Filas = goles {result.home} · Columnas = goles {result.away}</p>
                <PlotlyChart
                  data={scoreMatrixData}
                  height={260}
                  layout={{
                    xaxis: { title: { text: result.away, font: { color: "#64748B" } }, tickfont: { color: "#64748B" } },
                    yaxis: { title: { text: result.home, font: { color: "#64748B" } }, tickfont: { color: "#64748B" } },
                    margin: { l: 50, r: 20, t: 10, b: 50 },
                  }}
                />
              </div>
            </div>

            {/* Goal distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="card">
                <p className="section-label mb-2">Distribución Poisson — {result.home}</p>
                <PlotlyChart
                  height={200}
                  data={[{
                    type: "bar",
                    x: homeGoalProbs.map(g => `${g.k}${g.k === 5 ? "+" : ""} goles`),
                    y: homeGoalProbs.map(g => g.p),
                    marker: { color: homeGoalProbs.map((_, i) => i <= 2 ? "#00D4FF" : "#1E2D40") },
                    hovertemplate: "%{x}: %{y:.3f}<extra></extra>",
                  } as Data]}
                  layout={{ bargap: 0.2, margin: { l: 40, r: 20, t: 10, b: 50 } }}
                />
              </div>
              <div className="card">
                <p className="section-label mb-2">Distribución Poisson — {result.away}</p>
                <PlotlyChart
                  height={200}
                  data={[{
                    type: "bar",
                    x: awayGoalProbs.map(g => `${g.k}${g.k === 5 ? "+" : ""} goles`),
                    y: awayGoalProbs.map(g => g.p),
                    marker: { color: awayGoalProbs.map((_, i) => i <= 2 ? "#F0B429" : "#1E2D40") },
                    hovertemplate: "%{x}: %{y:.3f}<extra></extra>",
                  } as Data]}
                  layout={{ bargap: 0.2, margin: { l: 40, r: 20, t: 10, b: 50 } }}
                />
              </div>
            </div>

            {/* Pie chart */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="card">
                <p className="section-label mb-2">Probabilidades 1X2</p>
                <DonutChart
                  labels={[`${result.home} gana`, "Empate", `${result.away} gana`]}
                  values={[result.home_win, result.draw, result.away_win]}
                  colors={["#00D4FF", "#64748B", "#F0B429"]}
                />
              </div>
              {/* Discipline */}
              <div className="card space-y-3">
                <p className="section-label">Análisis de probabilidades</p>
                <div className="space-y-3 pt-2">
                  <ProbBar label={`${result.home} gana`} value={result.home_win} color="#00D4FF" />
                  <ProbBar label="Empate" value={result.draw} color="#64748B" />
                  <ProbBar label={`${result.away} gana`} value={result.away_win} color="#F0B429" />
                  {result.over_2_5 && <ProbBar label="Over 2.5 goles" value={result.over_2_5} color="#A855F7" />}
                  {result.btts_yes && <ProbBar label="Ambos anotan" value={result.btts_yes} color="#22C55E" />}
                </div>
              </div>
            </div>

            {/* AI Analysis toggle */}
            <div className="card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="section-label">Análisis IA</p>
                  <h3 className="section-title text-lg">INFORME AUTOMÁTICO</h3>
                </div>
                <button
                  onClick={() => {
                    setShowAnalysis(!showAnalysis)
                    if (!showAnalysis && !analysis) fetchAnalysis()
                  }}
                  className="btn-ghost flex items-center gap-2"
                >
                  <ChevronDown className={clsx("w-4 h-4 transition-transform", showAnalysis && "rotate-180")} />
                  {showAnalysis ? "Ocultar" : "Generar análisis"}
                </button>
              </div>

              <AnimatePresence>
                {showAnalysis && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-4 pt-4 border-t border-border">
                      {aLoading ? (
                        <div className="space-y-2">
                          <div className="skeleton h-4 w-full rounded" />
                          <div className="skeleton h-4 w-3/4 rounded" />
                          <div className="skeleton h-4 w-5/6 rounded" />
                        </div>
                      ) : analysis ? (
                        <div className="space-y-3">
                          <div className="flex gap-2 flex-wrap">
                            <Badge variant="cyan">Precisión histórica: {analysis.model_accuracy != null ? pct(analysis.model_accuracy) : "—"}</Badge>
                            <Badge variant={analysis.confidence === "high" ? "green" : analysis.confidence === "medium" ? "amber" : "red"}>
                              Confianza: {analysis.confidence}
                            </Badge>
                          </div>
                          <div className="bg-gradient-field rounded-xl p-4 text-sm text-text/90 leading-relaxed border border-border">
                            {analysis.report}
                          </div>
                          {analysis.data_sources?.length > 0 && (
                            <div className="flex gap-2 flex-wrap">
                              <span className="text-xs text-muted">Fuentes:</span>
                              {analysis.data_sources.map(s => <Badge key={s} variant="muted">{s}</Badge>)}
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-muted">No se pudo generar el análisis.</p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Export */}
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  const data = JSON.stringify(result, null, 2)
                  const blob = new Blob([data], { type: "application/json" })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement("a")
                  a.href = url
                  a.download = `${home}_vs_${away}.json`
                  a.click()
                }}
                className="btn-ghost flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Exportar JSON
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
