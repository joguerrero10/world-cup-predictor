import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Brain, Sparkles, RefreshCw, Download } from "lucide-react"
import { fetchEloRankings, fetchAIAnalysis, fetchPrediction } from "../api/endpoints"
import { DuelBar, ProbBar } from "../components/ui/DuelBar"
import { Badge } from "../components/ui/Badge"
import { GaugeChart, DonutChart, PlotlyChart } from "../components/ui/PlotlyChart"
import type { ModelType } from "../types"
import type { Data } from "plotly.js"
import clsx from "clsx"

const MODELS: { value: ModelType; label: string; desc: string }[] = [
  { value: "hybrid",      label: "Hybrid",       desc: "XGBoost 80.9% + DC 19.1%" },
  { value: "elo",         label: "Elo",           desc: "Rating diferencial" },
  { value: "dixon_coles", label: "Dixon-Coles",   desc: "Modelo Poisson bivariado" },
  { value: "klement",     label: "Klement",       desc: "Factores socioeconómicos" },
]

export function AIAnalysis() {
  const [home, setHome] = useState("")
  const [away, setAway] = useState("")
  const [model, setModel] = useState<ModelType>("hybrid")

  const { data: elo } = useQuery({ queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000 })
  const teams = elo?.map(t => t.team).sort() ?? []

  const { mutate: analyze, data: analysis, isPending, error, reset } = useMutation({
    mutationFn: () => fetchAIAnalysis(home, away, model),
  })

  const { mutate: predict, data: prediction } = useMutation({
    mutationFn: () => fetchPrediction(home, away, model, true),
  })

  const homeElo = elo?.find(t => t.team === home)
  const awayElo = elo?.find(t => t.team === away)
  const canAnalyze = home && away && home !== away

  function handleAnalyze() {
    reset()
    analyze()
    predict()
  }

  // Radar data for teams
  const maxRating = elo?.[0]?.rating ?? 2000
  const homeRadar = homeElo ? [
    homeElo.rating / maxRating,
    homeElo.attack / maxRating,
    1 - (homeElo.defense / maxRating),
    0.65, 0.70, 0.60,
  ] : []
  const awayRadar = awayElo ? [
    awayElo.rating / maxRating,
    awayElo.attack / maxRating,
    1 - (awayElo.defense / maxRating),
    0.60, 0.65, 0.55,
  ] : []
  const radarCats = ["Elo", "Ataque", "Defensa", "Forma", "xG", "Histórico"]

  const radarData: Data[] = homeRadar.length && awayRadar.length ? [
    {
      type: "scatterpolar",
      r: [...homeRadar, homeRadar[0]],
      theta: [...radarCats, radarCats[0]],
      fill: "toself",
      name: home,
      line: { color: "#00D4FF", width: 2 },
      fillcolor: "#00D4FF18",
    } as Data,
    {
      type: "scatterpolar",
      r: [...awayRadar, awayRadar[0]],
      theta: [...radarCats, radarCats[0]],
      fill: "toself",
      name: away,
      line: { color: "#F0B429", width: 2 },
      fillcolor: "#F0B42918",
    } as Data,
  ] : []

  // Model contributions donut
  const modelColors = ["#00D4FF", "#F0B429", "#A855F7", "#22C55E"]
  const modelWeights = model === "hybrid"
    ? [{ n: "XGBoost", w: 80.9 }, { n: "Dixon-Coles", w: 19.1 }, { n: "Elo", w: 0 }, { n: "Klement", w: 0 }]
    : model === "elo"
    ? [{ n: "XGBoost", w: 0 }, { n: "Dixon-Coles", w: 0 }, { n: "Elo", w: 100 }, { n: "Klement", w: 0 }]
    : model === "dixon_coles"
    ? [{ n: "XGBoost", w: 0 }, { n: "Dixon-Coles", w: 100 }, { n: "Elo", w: 0 }, { n: "Klement", w: 0 }]
    : [{ n: "XGBoost", w: 0 }, { n: "Dixon-Coles", w: 0 }, { n: "Elo", w: 0 }, { n: "Klement", w: 100 }]

  const activeModels = modelWeights.filter(m => m.w > 0)

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero */}
      <div className="relative overflow-hidden card border-violet/20 p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-violet/5 via-transparent to-cyan/5 pointer-events-none" />
        <div className="relative flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center">
            <Brain className="w-6 h-6 text-violet" />
          </div>
          <div>
            <p className="section-label">Motor probabilístico</p>
            <h2 className="font-display text-2xl tracking-wider text-text">
              ANÁLISIS DE <span className="text-gradient-cyan">INTELIGENCIA ARTIFICIAL</span>
            </h2>
            <p className="text-sm text-muted mt-0.5">
              Informe automatizado con Elo · Dixon-Coles · Klement · XGBoost · Monte Carlo
            </p>
          </div>
        </div>
      </div>

      {/* Config */}
      <div className="card space-y-5">
        <h3 className="section-title text-xl">CONFIGURAR ANÁLISIS</h3>

        {/* Team selectors */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Equipo Local</label>
            <select value={home} onChange={e => setHome(e.target.value)} className="select-dark w-full">
              <option value="">Seleccionar...</option>
              {teams.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">Equipo Visitante</label>
            <select value={away} onChange={e => setAway(e.target.value)} className="select-dark w-full">
              <option value="">Seleccionar...</option>
              {teams.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex flex-col justify-end">
            <button
              onClick={handleAnalyze}
              disabled={!canAnalyze || isPending}
              className={clsx(
                "btn-primary flex items-center justify-center gap-2",
                (!canAnalyze || isPending) && "opacity-50 cursor-not-allowed"
              )}
            >
              {isPending
                ? <><RefreshCw className="w-4 h-4 animate-spin" /> Analizando...</>
                : <><Sparkles className="w-4 h-4" /> GENERAR ANÁLISIS</>
              }
            </button>
          </div>
        </div>

        {/* Model selector */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {MODELS.map(m => (
            <button
              key={m.value}
              onClick={() => setModel(m.value)}
              className={clsx(
                "p-3 rounded-xl border text-left transition-all duration-150",
                model === m.value
                  ? "border-cyan/40 bg-cyan/10"
                  : "border-border hover:border-border hover:bg-white/5"
              )}
            >
              <p className={clsx("font-display text-sm tracking-wider", model === m.value ? "text-cyan" : "text-text")}>
                {m.label}
              </p>
              <p className="text-xs text-muted mt-0.5">{m.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Team comparison cards */}
      {(homeElo || awayElo) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {homeElo && (
            <div className="card border-cyan/20">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center text-xl font-display text-cyan">
                  {home.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="font-display text-xl tracking-wider text-cyan">{home}</h3>
                  <Badge variant="cyan">Elo #{homeElo.rank}</Badge>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="font-display text-2xl text-cyan">{homeElo.rating.toFixed(0)}</p>
                  <p className="text-xs text-muted">Rating</p>
                </div>
                <div>
                  <p className="font-display text-2xl text-text">{homeElo.attack.toFixed(0)}</p>
                  <p className="text-xs text-muted">Ataque</p>
                </div>
                <div>
                  <p className="font-display text-2xl text-text">{homeElo.defense.toFixed(0)}</p>
                  <p className="text-xs text-muted">Defensa</p>
                </div>
              </div>
            </div>
          )}
          {awayElo && (
            <div className="card border-amber/20">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-amber/10 border border-amber/20 flex items-center justify-center text-xl font-display text-amber">
                  {away.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="font-display text-xl tracking-wider text-amber">{away}</h3>
                  <Badge variant="amber">Elo #{awayElo.rank}</Badge>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="font-display text-2xl text-amber">{awayElo.rating.toFixed(0)}</p>
                  <p className="text-xs text-muted">Rating</p>
                </div>
                <div>
                  <p className="font-display text-2xl text-text">{awayElo.attack.toFixed(0)}</p>
                  <p className="text-xs text-muted">Ataque</p>
                </div>
                <div>
                  <p className="font-display text-2xl text-text">{awayElo.defense.toFixed(0)}</p>
                  <p className="text-xs text-muted">Defensa</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-scarlet/30 bg-scarlet/5 text-scarlet text-sm p-4">
          {String(error)}
        </div>
      )}

      {/* Results */}
      <AnimatePresence>
        {(analysis || prediction) && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Main prediction */}
            {prediction && (
              <div className="card">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <p className="section-label">Resultado del modelo {model.toUpperCase()}</p>
                    <h2 className="section-title">{home} vs {away}</h2>
                  </div>
                  <div className="flex gap-2">
                    <Badge variant="cyan">{prediction.source}</Badge>
                    {analysis && (
                      <Badge variant={analysis.confidence === "high" ? "green" : analysis.confidence === "medium" ? "amber" : "red"}>
                        Confianza: {analysis.confidence}
                      </Badge>
                    )}
                  </div>
                </div>
                <DuelBar
                  home={home}
                  away={away}
                  homeWin={prediction.home_win}
                  draw={prediction.draw}
                  awayWin={prediction.away_win}
                />
              </div>
            )}

            {/* Gauges + Radar + Model contributions */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {prediction && (
                <>
                  <div className="card">
                    <p className="section-label mb-1">Local</p>
                    <GaugeChart value={prediction.home_win} label={`${home} gana`} color="#00D4FF" />
                  </div>
                  <div className="card">
                    <p className="section-label mb-1">Empate</p>
                    <GaugeChart value={prediction.draw} label="Empate" color="#64748B" />
                  </div>
                  <div className="card">
                    <p className="section-label mb-1">Visitante</p>
                    <GaugeChart value={prediction.away_win} label={`${away} gana`} color="#F0B429" />
                  </div>
                </>
              )}
            </div>

            {/* Radar + Model weights */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Radar */}
              {radarData.length > 0 && (
                <div className="card">
                  <p className="section-label mb-2">Comparación de atributos</p>
                  <PlotlyChart
                    data={radarData}
                    height={300}
                    layout={{
                      polar: {
                        radialaxis: { visible: true, range: [0, 1], gridcolor: "#1E2D40", tickfont: { color: "#64748B", size: 9 } },
                        angularaxis: { tickfont: { color: "#E2E8F0", size: 10 } },
                        bgcolor: "transparent",
                      },
                      showlegend: true,
                      legend: { font: { color: "#E2E8F0", size: 10 }, x: 0, y: -0.15, orientation: "h" },
                      margin: { l: 40, r: 40, t: 20, b: 40 },
                    }}
                  />
                </div>
              )}

              {/* Model contribution donut */}
              <div className="card">
                <p className="section-label mb-2">Contribución de modelos</p>
                <DonutChart
                  labels={activeModels.map(m => m.n)}
                  values={activeModels.map(m => m.w)}
                  colors={activeModels.map((_, i) => modelColors[i])}
                />
                <div className="grid grid-cols-2 gap-2 mt-3">
                  {modelWeights.map((m, i) => (
                    <div key={m.n} className="flex items-center gap-2 text-xs">
                      <span className="w-2 h-2 rounded-full" style={{ background: modelColors[i] }} />
                      <span className="text-muted">{m.n}</span>
                      <span className={clsx("ml-auto font-medium", m.w > 0 ? "text-text" : "text-muted/40")}>{m.w}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* AI Report */}
            {analysis && (
              <div className="card border-violet/20">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-violet/10 border border-violet/20 flex items-center justify-center">
                    <Brain className="w-4 h-4 text-violet" />
                  </div>
                  <div>
                    <p className="section-label">Informe generado por IA</p>
                    <h3 className="section-title text-lg">{home.toUpperCase()} vs {away.toUpperCase()}</h3>
                  </div>
                </div>

                {/* Report text */}
                <div className="bg-gradient-field rounded-xl p-5 border border-border">
                  <div className="flex items-start gap-3">
                    <Sparkles className="w-5 h-5 text-violet mt-0.5 shrink-0" />
                    <p className="text-sm text-text/90 leading-relaxed whitespace-pre-line">
                      {analysis.report}
                    </p>
                  </div>
                </div>

                {/* Data sources */}
                {analysis.data_sources?.length > 0 && (
                  <div className="flex gap-2 flex-wrap mt-4">
                    <span className="text-xs text-muted">Modelos usados:</span>
                    {analysis.data_sources.map(s => <Badge key={s} variant="muted">{s}</Badge>)}
                  </div>
                )}

                {/* Extra stats if available */}
                {prediction?.most_likely_score && (
                  <div className="mt-4 pt-4 border-t border-border">
                    <p className="text-xs text-muted uppercase tracking-wider mb-3">Marcador más probable</p>
                    <div className="flex items-center justify-center gap-8">
                      <div className="text-center">
                        <p className="font-display text-4xl text-cyan">{prediction.most_likely_score[0]}</p>
                        <p className="text-xs text-muted">{home}</p>
                      </div>
                      <p className="font-display text-2xl text-muted">–</p>
                      <div className="text-center">
                        <p className="font-display text-4xl text-amber">{prediction.most_likely_score[1]}</p>
                        <p className="text-xs text-muted">{away}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 mt-4">
                      {prediction.over_2_5 && <ProbBar label="Over 2.5 goles" value={prediction.over_2_5} color="#A855F7" />}
                      {prediction.btts_yes && <ProbBar label="Ambos anotan" value={prediction.btts_yes} color="#22C55E" />}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Export */}
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  const data = { prediction, analysis, home, away, model, timestamp: new Date().toISOString() }
                  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
                  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `ai_analysis_${home}_vs_${away}.json`; a.click()
                }}
                className="btn-ghost flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Exportar análisis
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!analysis && !prediction && !isPending && (
        <div className="card text-center py-16 text-muted">
          <Brain className="w-12 h-12 mx-auto mb-3 opacity-20" />
          <p className="text-sm">Selecciona dos equipos y genera el análisis IA completo</p>
        </div>
      )}
    </div>
  )
}
