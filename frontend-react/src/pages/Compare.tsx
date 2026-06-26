import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery, useMutation } from "@tanstack/react-query"
import { GitCompare, RefreshCw } from "lucide-react"
import { fetchEloRankings, fetchPrediction } from "../api/endpoints"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { DuelBar } from "../components/ui/DuelBar"
import { Badge } from "../components/ui/Badge"
import type { Data } from "plotly.js"
import clsx from "clsx"

export function Compare() {
  const [teamA, setTeamA] = useState("")
  const [teamB, setTeamB] = useState("")

  const { data: elo } = useQuery({ queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000 })
  const teams = elo?.map(t => t.team).sort() ?? []

  const { mutate: compare, data: prediction, isPending } = useMutation({
    mutationFn: () => fetchPrediction(teamA, teamB, "hybrid", true),
  })

  const eloA = elo?.find(t => t.team === teamA)
  const eloB = elo?.find(t => t.team === teamB)
  const maxRating = elo?.[0]?.rating ?? 2000

  const canCompare = teamA && teamB && teamA !== teamB

  // Radar comparison
  const radarCats = ["Rating", "Ataque", "Defensa", "Forma", "xG", "Histórico"]
  const radarA = eloA ? [eloA.rating / maxRating, eloA.attack / maxRating, 1 - eloA.defense / maxRating, 0.65, 0.70, 0.60] : []
  const radarB = eloB ? [eloB.rating / maxRating, eloB.attack / maxRating, 1 - eloB.defense / maxRating, 0.60, 0.65, 0.55] : []

  const radarData: Data[] = (radarA.length && radarB.length) ? [
    {
      type: "scatterpolar",
      r: [...radarA, radarA[0]],
      theta: [...radarCats, radarCats[0]],
      fill: "toself", name: teamA,
      line: { color: "#00D4FF", width: 2 }, fillcolor: "#00D4FF18",
    } as Data,
    {
      type: "scatterpolar",
      r: [...radarB, radarB[0]],
      theta: [...radarCats, radarCats[0]],
      fill: "toself", name: teamB,
      line: { color: "#F0B429", width: 2 }, fillcolor: "#F0B42918",
    } as Data,
  ] : []

  // Bar comparison
  const barLabels = ["Elo Rating", "Ataque", "Defensa"]
  const barA = eloA ? [eloA.rating, eloA.attack, eloA.defense] : [0, 0, 0]
  const barB = eloB ? [eloB.rating, eloB.attack, eloB.defense] : [0, 0, 0]

  const barData: Data[] = [
    { type: "bar", name: teamA || "Equipo A", x: barLabels, y: barA, marker: { color: "#00D4FF" }, hovertemplate: "%{x}: %{y:.0f}<extra></extra>" } as Data,
    { type: "bar", name: teamB || "Equipo B", x: barLabels, y: barB, marker: { color: "#F0B429" }, hovertemplate: "%{x}: %{y:.0f}<extra></extra>" } as Data,
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <GitCompare className="w-5 h-5 text-cyan" />
          <h2 className="section-title text-xl">COMPARADOR DE EQUIPOS</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-end">
          <div className="md:col-span-2 space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-cyan font-medium">Equipo A</label>
            <select value={teamA} onChange={e => setTeamA(e.target.value)} className="select-dark w-full border-cyan/30">
              <option value="">Seleccionar...</option>
              {teams.filter(t => t !== teamB).map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          <div className="flex justify-center">
            <span className="font-display text-2xl tracking-widest text-muted">VS</span>
          </div>

          <div className="md:col-span-2 space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-amber font-medium">Equipo B</label>
            <select value={teamB} onChange={e => setTeamB(e.target.value)} className="select-dark w-full border-amber/30">
              <option value="">Seleccionar...</option>
              {teams.filter(t => t !== teamA).map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <button
          onClick={() => compare()}
          disabled={!canCompare || isPending}
          className={clsx("btn-primary mt-4 flex items-center gap-2", (!canCompare || isPending) && "opacity-50 cursor-not-allowed")}
        >
          {isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <GitCompare className="w-4 h-4" />}
          {isPending ? "Comparando..." : "COMPARAR"}
        </button>
      </div>

      {/* Side by side stats */}
      {(eloA || eloB) && (
        <div className="grid grid-cols-2 gap-4">
          {/* Team A */}
          <div className="card border-cyan/20 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center font-display text-cyan text-lg">
                {(teamA || "A").slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h3 className="font-display text-xl tracking-wider text-cyan">{teamA || "Equipo A"}</h3>
                {eloA && <Badge variant="cyan">Rank #{eloA.rank}</Badge>}
              </div>
            </div>
            {eloA && (
              <div className="grid grid-cols-3 gap-2 text-center">
                <div><p className="font-display text-2xl text-cyan">{eloA.rating.toFixed(0)}</p><p className="text-xs text-muted">Elo</p></div>
                <div><p className="font-display text-2xl text-text">{eloA.attack.toFixed(0)}</p><p className="text-xs text-muted">Ataque</p></div>
                <div><p className="font-display text-2xl text-text">{eloA.defense.toFixed(0)}</p><p className="text-xs text-muted">Defensa</p></div>
              </div>
            )}
          </div>

          {/* Team B */}
          <div className="card border-amber/20 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-amber/10 border border-amber/20 flex items-center justify-center font-display text-amber text-lg">
                {(teamB || "B").slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h3 className="font-display text-xl tracking-wider text-amber">{teamB || "Equipo B"}</h3>
                {eloB && <Badge variant="amber">Rank #{eloB.rank}</Badge>}
              </div>
            </div>
            {eloB && (
              <div className="grid grid-cols-3 gap-2 text-center">
                <div><p className="font-display text-2xl text-amber">{eloB.rating.toFixed(0)}</p><p className="text-xs text-muted">Elo</p></div>
                <div><p className="font-display text-2xl text-text">{eloB.attack.toFixed(0)}</p><p className="text-xs text-muted">Ataque</p></div>
                <div><p className="font-display text-2xl text-text">{eloB.defense.toFixed(0)}</p><p className="text-xs text-muted">Defensa</p></div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Charts */}
      {(eloA && eloB) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Radar */}
          <div className="card">
            <p className="section-label mb-2">Radar comparativo</p>
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
                legend: { orientation: "h", x: 0, y: -0.15, font: { color: "#E2E8F0", size: 10 } },
                margin: { l: 40, r: 40, t: 20, b: 40 },
              }}
            />
          </div>

          {/* Bar comparison */}
          <div className="card">
            <p className="section-label mb-2">Comparación de métricas</p>
            <PlotlyChart
              data={barData}
              height={300}
              layout={{
                barmode: "group",
                bargap: 0.2,
                bargroupgap: 0.1,
                legend: { font: { color: "#E2E8F0", size: 10 } },
                yaxis: { gridcolor: "#1E2D40" },
                margin: { l: 40, r: 20, t: 10, b: 40 },
              }}
            />
          </div>
        </div>
      )}

      {/* Prediction result */}
      {prediction && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="card"
        >
          <div className="flex items-center justify-between mb-6">
            <div>
              <p className="section-label">Predicción de enfrentamiento</p>
              <h3 className="section-title">{teamA} vs {teamB}</h3>
            </div>
            <Badge variant="cyan">{prediction.source}</Badge>
          </div>
          <DuelBar home={teamA} away={teamB} homeWin={prediction.home_win} draw={prediction.draw} awayWin={prediction.away_win} />

          {prediction.most_likely_score && (
            <div className="mt-4 pt-4 border-t border-border flex items-center justify-center gap-8">
              <div className="text-center">
                <p className="font-display text-4xl text-cyan">{prediction.most_likely_score[0]}</p>
                <p className="text-xs text-muted">{teamA}</p>
              </div>
              <p className="font-display text-2xl text-muted">–</p>
              <div className="text-center">
                <p className="font-display text-4xl text-amber">{prediction.most_likely_score[1]}</p>
                <p className="text-xs text-muted">{teamB}</p>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Advantage analysis */}
      {eloA && eloB && (
        <div className="card">
          <p className="section-label mb-3">Análisis de ventajas</p>
          <div className="space-y-3">
            {[
              { label: "Rating Elo",  a: eloA.rating,  b: eloB.rating,  max: maxRating },
              { label: "Ataque",      a: eloA.attack,  b: eloB.attack,  max: maxRating },
              { label: "Defensa",     a: eloA.defense, b: eloB.defense, max: maxRating },
            ].map(stat => {
              const aWins = stat.a >= stat.b
              return (
                <div key={stat.label} className="space-y-1">
                  <div className="flex justify-between text-xs text-muted">
                    <span className={clsx("font-medium", aWins ? "text-cyan" : "text-muted")}>{stat.a.toFixed(0)} {aWins && "✓"}</span>
                    <span>{stat.label}</span>
                    <span className={clsx("font-medium", !aWins ? "text-amber" : "text-muted")}>{!aWins && "✓"} {stat.b.toFixed(0)}</span>
                  </div>
                  <div className="flex h-2 rounded overflow-hidden bg-border">
                    <div className="bg-cyan" style={{ width: `${(stat.a / (stat.a + stat.b)) * 100}%` }} />
                    <div className="bg-amber" style={{ width: `${(stat.b / (stat.a + stat.b)) * 100}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
