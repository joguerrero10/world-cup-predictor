import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { BarChart3 } from "lucide-react"
import { fetchLeagueTable, fetchTournamentProbs } from "../api/endpoints"
import { PlotlyChart, DonutChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import { ProbBar } from "../components/ui/DuelBar"
import { CardSkeleton } from "../components/ui/LoadingSkeleton"
import type { Data } from "plotly.js"
import clsx from "clsx"

const TABS = [
  { id: "premier_league", label: "Premier League", emoji: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", type: "league" },
  { id: "laliga",         label: "LaLiga",          emoji: "🇪🇸", type: "league" },
  { id: "bundesliga",     label: "Bundesliga",      emoji: "🇩🇪", type: "league" },
  { id: "serie_a",        label: "Serie A",          emoji: "🇮🇹", type: "league" },
  { id: "ligue_1",        label: "Ligue 1",          emoji: "🇫🇷", type: "league" },
  { id: "ucl",            label: "Champions",        emoji: "⭐", type: "tournament" },
  { id: "fifa_wc_2026",   label: "Mundial 2026",     emoji: "🌍", type: "tournament" },
]

export function Probabilities() {
  const [activeComp, setActiveComp] = useState("premier_league")
  const [nSims, setNSims] = useState(10_000)

  const activeTab = TABS.find(t => t.id === activeComp)!
  const isLeague = activeTab.type === "league"

  const { data: leagueData, isLoading: leagueLoading } = useQuery({
    queryKey: ["league-table", activeComp, nSims],
    queryFn: () => fetchLeagueTable(activeComp, nSims),
    enabled: isLeague,
    staleTime: 30_000,
  })

  const { data: tournData, isLoading: tournLoading } = useQuery({
    queryKey: ["tournament-probs", activeComp, nSims],
    queryFn: () => fetchTournamentProbs(activeComp, nSims),
    enabled: !isLeague,
    staleTime: 30_000,
  })

  const isLoading = leagueLoading || tournLoading

  // League champion probs bar
  const champEntries = leagueData
    ? Object.entries(leagueData.table.reduce((acc, row) => ({ ...acc, [row.team]: row.champion_prob }), {} as Record<string, number>))
        .sort((a, b) => b[1] - a[1]).slice(0, 10)
    : []

  const champBar: Data[] = champEntries.length ? [{
    type: "bar",
    x: champEntries.map(([_, p]) => p * 100),
    y: champEntries.map(([t]) => t),
    orientation: "h",
    marker: { color: champEntries.map((_, i) => i === 0 ? "#F0B429" : "#00D4FF80") },
    text: champEntries.map(([_, p]) => `${(p * 100).toFixed(1)}%`),
    textposition: "outside",
    textfont: { color: "#E2E8F0", size: 10 },
    hovertemplate: "%{y}: %{x:.1f}%<extra></extra>",
  }] : []

  // Tournament champion pie
  const tournChamp = tournData ? Object.entries(tournData.champion).sort((a, b) => b[1] - a[1]).slice(0, 8) : []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Competition tabs */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-cyan" />
          <h2 className="section-title text-xl">PROBABILIDADES</h2>
        </div>
        <div className="flex gap-2 flex-wrap">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveComp(t.id)}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition-all",
                activeComp === t.id ? "border-cyan/40 bg-cyan/10 text-cyan" : "border-border text-muted hover:text-text hover:bg-white/5"
              )}
            >
              <span>{t.emoji}</span>
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <span className="text-xs text-muted self-center">Simulaciones:</span>
          {[1_000, 10_000, 50_000].map(n => (
            <button
              key={n}
              onClick={() => setNSims(n)}
              className={clsx(
                "py-1 px-3 rounded border text-xs font-display tracking-wider transition-all",
                nSims === n ? "border-amber/40 bg-amber/10 text-amber" : "border-border text-muted"
              )}
            >
              {n.toLocaleString()}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CardSkeleton /><CardSkeleton />
        </div>
      )}

      {/* League view */}
      {isLeague && leagueData && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Champion probs */}
            <div className="card">
              <p className="section-label mb-2">Probabilidad de título</p>
              <PlotlyChart
                data={champBar}
                height={300}
                layout={{
                  xaxis: { title: { text: "%", font: { color: "#64748B" } }, showgrid: false },
                  yaxis: { autorange: "reversed", tickfont: { color: "#E2E8F0", size: 10 } },
                  bargap: 0.25, margin: { l: 110, r: 70, t: 8, b: 40 },
                }}
              />
            </div>

            {/* Relegation probs */}
            <div className="card">
              <p className="section-label mb-3">Probabilidad de descenso (Top 5)</p>
              <div className="space-y-3 pt-2">
                {leagueData.table
                  .sort((a, b) => b.relegated_prob - a.relegated_prob)
                  .slice(0, 8)
                  .map(row => (
                    <ProbBar key={row.team} label={row.team} value={row.relegated_prob} color="#EF4444" />
                  ))
                }
              </div>
            </div>
          </div>

          {/* League table */}
          <div className="card overflow-x-auto">
            <p className="section-label mb-3">Tabla simulada ({nSims.toLocaleString()} sims)</p>
            <table className="table-dark">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Equipo</th>
                  <th>PJ</th>
                  <th>Pts</th>
                  <th>GF</th>
                  <th>GC</th>
                  <th>DG</th>
                  <th>P(Campeón)</th>
                  <th>P(Top 4)</th>
                  <th>P(Descenso)</th>
                </tr>
              </thead>
              <tbody>
                {leagueData.table.map((row, i) => {
                  const isChamp = i === 0
                  const isTop4  = i < 4
                  const isRel   = i >= leagueData.table.length - 3
                  return (
                    <tr key={row.team} className={isRel ? "bg-scarlet/5" : isTop4 ? "bg-cyan/5" : ""}>
                      <td>
                        <span className={clsx(
                          "font-display text-lg",
                          isChamp ? "text-amber" : isTop4 ? "text-cyan" : isRel ? "text-scarlet" : "text-muted"
                        )}>
                          {row.position}
                        </span>
                      </td>
                      <td className="font-medium">{row.team}</td>
                      <td className="text-muted">{row.played.toFixed(0)}</td>
                      <td className="font-bold">{row.pts.toFixed(1)}</td>
                      <td className="text-muted">{row.gf.toFixed(1)}</td>
                      <td className="text-muted">{row.ga.toFixed(1)}</td>
                      <td className={row.gd >= 0 ? "text-emerald" : "text-scarlet"}>{row.gd.toFixed(1)}</td>
                      <td className="text-amber">{(row.champion_prob * 100).toFixed(1)}%</td>
                      <td className="text-cyan">{(row.top4_prob * 100).toFixed(1)}%</td>
                      <td className="text-scarlet">{(row.relegated_prob * 100).toFixed(1)}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tournament view */}
      {!isLeague && tournData && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {tournChamp.slice(0, 3).map(([team, prob], i) => (
              <motion.div
                key={team}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.1 }}
                className="card-hover text-center p-4 space-y-2"
              >
                <span className="text-3xl">{["🥇","🥈","🥉"][i]}</span>
                <p className="font-display text-lg tracking-wider">{team}</p>
                <p className="font-display text-3xl text-amber">{(prob * 100).toFixed(1)}%</p>
                <p className="text-xs text-muted">Prob. campeón</p>
              </motion.div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="card">
              <p className="section-label mb-2">Distribución de campeones</p>
              <DonutChart
                labels={tournChamp.map(([t]) => t)}
                values={tournChamp.map(([_, p]) => p)}
                colors={["#F0B429","#00D4FF","#CD7F32","#A855F7","#22C55E","#EF4444","#64748B","#06B6D4"]}
              />
            </div>
            <div className="card">
              <p className="section-label mb-3">Probabilidades completas</p>
              <div className="space-y-2">
                {Object.entries(tournData.champion).sort((a,b)=>b[1]-a[1]).slice(0,10).map(([team, prob]) => (
                  <ProbBar key={team} label={team} value={prob} color="#F0B429" />
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
