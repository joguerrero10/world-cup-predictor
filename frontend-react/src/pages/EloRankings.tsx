import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { Search, Download } from "lucide-react"
import { fetchEloRankings } from "../api/endpoints"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { TableRowSkeleton } from "../components/ui/LoadingSkeleton"
import type { Data } from "plotly.js"

export function EloRankings() {
  const [search, setSearch] = useState("")
  const [topN, setTopN] = useState(30)
  const [chartView, setChartView] = useState<"bar" | "scatter">("bar")

  const { data: elo, isLoading } = useQuery({
    queryKey: ["elo-rankings"],
    queryFn: fetchEloRankings,
    staleTime: 60_000,
  })

  const filtered = (elo ?? []).filter(t =>
    t.team.toLowerCase().includes(search.toLowerCase())
  ).slice(0, topN)

  const top10 = (elo ?? []).slice(0, 10)
  const maxRating = elo?.[0]?.rating ?? 2000

  const barData: Data[] = [{
    type: "bar",
    x: top10.map(t => t.rating),
    y: top10.map(t => t.team),
    orientation: "h",
    marker: {
      color: top10.map((_, i) =>
        i === 0 ? "#F0B429" : i === 1 ? "#C0C0C0" : i === 2 ? "#CD7F32" : "#00D4FF"
      ),
    },
    text: top10.map(t => t.rating.toFixed(0)),
    textposition: "outside",
    textfont: { color: "#64748B", size: 11 },
    hovertemplate: "%{y}: %{x:.0f} Elo<extra></extra>",
  }]

  const scatterData: Data[] = [{
    type: "scatter",
    mode: "markers+text" as any,
    x: (elo ?? []).map(t => t.attack),
    y: (elo ?? []).map(t => t.defense),
    text: (elo ?? []).map(t => t.team),
    textposition: "top center",
    textfont: { color: "#64748B", size: 9 },
    marker: {
      size: (elo ?? []).map(t => Math.max(6, (t.rating / maxRating) * 18)),
      color: (elo ?? []).map(t => t.rating),
      colorscale: [[0, "#1E2D40"], [0.5, "#00D4FF"], [1, "#F0B429"]],
      showscale: true,
      colorbar: { title: { text: "Elo" }, tickfont: { color: "#64748B" }, outlinewidth: 0 },
    },
    hovertemplate: "<b>%{text}</b><br>Ataque: %{x:.0f}<br>Defensa: %{y:.0f}<extra></extra>",
  }]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <p className="section-label">Clasificación global</p>
            <h2 className="section-title">RANKING ELO MUNDIAL</h2>
          </div>
          <div className="flex gap-2">
            {(["bar", "scatter"] as const).map(v => (
              <button
                key={v}
                onClick={() => setChartView(v)}
                className={`btn-ghost text-xs py-1 ${chartView === v ? "border-cyan/50 text-cyan" : ""}`}
              >
                {v === "bar" ? "Top 10" : "Ataque vs Defensa"}
              </button>
            ))}
          </div>
        </div>
        <PlotlyChart
          data={chartView === "bar" ? barData : scatterData}
          height={340}
          layout={chartView === "bar" ? {
            xaxis: { showgrid: false, zeroline: false, visible: false },
            yaxis: { tickfont: { color: "#E2E8F0", size: 12 }, autorange: "reversed" },
            bargap: 0.3,
            margin: { l: 110, r: 70, t: 10, b: 10 },
          } : {
            xaxis: { title: { text: "Fuerza de ataque", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
            yaxis: { title: { text: "Fuerza de defensa", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
            margin: { l: 60, r: 20, t: 10, b: 50 },
          }}
        />
      </div>

      {/* Table */}
      <div className="card">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 className="section-title text-xl">TABLA COMPLETA</h2>
          <div className="flex items-center gap-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Buscar equipo..."
                className="input-dark pl-8 w-48"
              />
            </div>
            {/* Top N */}
            <select value={topN} onChange={e => setTopN(+e.target.value)} className="select-dark w-24">
              {[20, 30, 50, 100, 999].map(n => (
                <option key={n} value={n}>{n === 999 ? "Todos" : `Top ${n}`}</option>
              ))}
            </select>
            {/* Export */}
            <button
              onClick={() => {
                const csv = ["Rank,Equipo,Elo,Ataque,Defensa", ...(elo ?? []).map(t => `${t.rank},${t.team},${t.rating},${t.attack},${t.defense}`)].join("\n")
                const blob = new Blob([csv], { type: "text/csv" })
                const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "elo_rankings.csv"; a.click()
              }}
              className="btn-ghost p-2"
              title="Exportar CSV"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="table-dark">
            <thead>
              <tr>
                <th className="w-16">Rank</th>
                <th>Equipo</th>
                <th>Rating Elo</th>
                <th>Ataque</th>
                <th>Defensa</th>
                <th>Barra</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => <TableRowSkeleton key={i} cols={6} />)
              ) : (
                filtered.map((team, i) => {
                  const barWidth = (team.rating / maxRating) * 100
                  const isTop3 = team.rank <= 3
                  return (
                    <motion.tr
                      key={team.team}
                      className="border-b border-border/50 hover:bg-white/2 transition-colors"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.02 }}
                    >
                      <td>
                        <span className={`font-display text-xl ${isTop3 ? "text-amber" : "text-muted"}`}>
                          {team.rank === 1 ? "🥇" : team.rank === 2 ? "🥈" : team.rank === 3 ? "🥉" : team.rank}
                        </span>
                      </td>
                      <td className="font-medium text-text">{team.team}</td>
                      <td>
                        <span className={`font-display text-lg ${isTop3 ? "text-amber" : "text-cyan"}`}>
                          {team.rating.toFixed(0)}
                        </span>
                      </td>
                      <td className="text-muted">{team.attack.toFixed(0)}</td>
                      <td className="text-muted">{team.defense.toFixed(0)}</td>
                      <td className="w-32">
                        <div className="h-1.5 bg-border rounded overflow-hidden">
                          <div
                            className={`h-full rounded transition-all ${isTop3 ? "bg-amber" : "bg-cyan"}`}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </td>
                    </motion.tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {!isLoading && <p className="text-xs text-muted mt-3 text-right">{filtered.length} equipos mostrados</p>}
      </div>
    </div>
  )
}
