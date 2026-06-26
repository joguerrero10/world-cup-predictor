import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { BarChart2 } from "lucide-react"
import { fetchEloRankings, fetchModelPerformance } from "../api/endpoints"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import { CardSkeleton } from "../components/ui/LoadingSkeleton"
import type { Data } from "plotly.js"

export function Statistics() {
  const [selectedTeam, setSelectedTeam] = useState("")

  const { data: elo } = useQuery({ queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000 })
  const { data: metrics, isLoading } = useQuery({ queryKey: ["model-performance"], queryFn: fetchModelPerformance, staleTime: 60_000, retry: 1 })

  const teams = elo?.map(t => t.team).sort() ?? []
  const team = elo?.find(t => t.team === selectedTeam)

  // Elo distribution histogram
  const eloValues = (elo ?? []).map(t => t.rating)
  const histData: Data[] = eloValues.length ? [{
    type: "histogram",
    x: eloValues,
    nbinsx: 20,
    marker: { color: "#00D4FF50", line: { color: "#00D4FF", width: 1 } },
    hovertemplate: "Rango %{x}: %{y} equipos<extra></extra>",
  } as any as Data] : []

  // Attack vs Defense scatter all teams
  const scatterAll: Data[] = elo ? [{
    type: "scatter",
    mode: "markers",
    x: elo.map(t => t.attack),
    y: elo.map(t => t.defense),
    text: elo.map(t => t.team),
    marker: {
      size: 7,
      color: elo.map(t => t.rating),
      colorscale: [[0, "#1E2D40"], [0.5, "#00D4FF"], [1, "#F0B429"]],
      showscale: false,
    },
    hovertemplate: "<b>%{text}</b><br>Ataque: %{x:.0f}<br>Defensa: %{y:.0f}<extra></extra>",
  } as Data] : []

  // Model metrics
  const metricsRows = Array.isArray(metrics) ? metrics : []

  // xG mock distribution (team-specific)
  const xgDist = team ? Array.from({ length: 8 }, (_, k) => {
    const lambda = 1.2 + (team.attack - 1500) / 1000
    const factorial = (n: number): number => n <= 0 ? 1 : n * factorial(n - 1)
    return { k, p: Math.exp(-lambda) * Math.pow(lambda, k) / factorial(k) }
  }) : []
  const xgChartData: Data[] = xgDist.length ? [{
    type: "bar",
    x: xgDist.map(d => `${d.k} goles`),
    y: xgDist.map(d => d.p),
    marker: { color: "#00D4FF60", line: { color: "#00D4FF", width: 1 } },
    hovertemplate: "%{x}: %{y:.4f}<extra></extra>",
  }] : []

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="card flex items-center gap-3">
        <BarChart2 className="w-5 h-5 text-cyan" />
        <h2 className="section-title text-xl">ESTADÍSTICAS</h2>
      </div>

      {/* Distribution charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <p className="section-label mb-2">Distribución de ratings Elo</p>
          <PlotlyChart
            data={histData}
            height={240}
            layout={{
              xaxis: { title: { text: "Rating Elo", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
              yaxis: { title: { text: "N equipos", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
              margin: { l: 50, r: 20, t: 10, b: 50 },
            }}
          />
        </div>
        <div className="card">
          <p className="section-label mb-2">Ataque vs Defensa (todos los equipos)</p>
          <PlotlyChart
            data={scatterAll}
            height={240}
            layout={{
              xaxis: { title: { text: "Ataque", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
              yaxis: { title: { text: "Defensa", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
              margin: { l: 50, r: 20, t: 10, b: 50 },
            }}
          />
        </div>
      </div>

      {/* Team xG */}
      <div className="card">
        <div className="flex items-center gap-4 mb-4 flex-wrap">
          <p className="section-label">Distribución xG por equipo</p>
          <select value={selectedTeam} onChange={e => setSelectedTeam(e.target.value)} className="select-dark w-48">
            <option value="">Seleccionar equipo...</option>
            {teams.map(t => <option key={t}>{t}</option>)}
          </select>
        </div>
        {selectedTeam && team ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted mb-2">Distribución de goles esperados (Poisson)</p>
              <PlotlyChart data={xgChartData} height={220}
                layout={{ bargap: 0.2, margin: { l: 40, r: 20, t: 8, b: 50 } }}
              />
            </div>
            <div className="space-y-3">
              <p className="text-xs text-muted uppercase tracking-wider">Métricas clave</p>
              {[
                { label: "Elo Rating",      val: team.rating.toFixed(0),   color: "text-cyan" },
                { label: "Fuerza ataque",   val: team.attack.toFixed(0),   color: "text-amber" },
                { label: "Fuerza defensa",  val: team.defense.toFixed(0),  color: "text-emerald" },
                { label: "xG estimado/90",  val: (1.2 + (team.attack - 1500)/1000).toFixed(2), color: "text-text" },
                { label: "xGA estimado/90", val: (1.1 + (team.defense - 1500)/1000).toFixed(2), color: "text-text" },
              ].map(s => (
                <div key={s.label} className="flex justify-between py-2 border-b border-border/30 last:border-0">
                  <span className="text-sm text-muted">{s.label}</span>
                  <span className={`text-sm font-mono font-medium ${s.color}`}>{s.val}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-muted text-sm">
            Selecciona un equipo para ver su distribución xG
          </div>
        )}
      </div>

      {/* Model metrics */}
      <div className="card">
        <p className="section-label mb-3">Métricas de rendimiento de modelos</p>
        {isLoading ? <CardSkeleton /> : metricsRows.length > 0 ? (
          <table className="table-dark">
            <thead>
              <tr>
                <th>Modelo</th><th>Accuracy</th><th>Brier</th><th>Log Loss</th><th>Calibración</th><th>ROI</th>
              </tr>
            </thead>
            <tbody>
              {metricsRows.map((m: any) => (
                <tr key={m.model}>
                  <td><Badge variant="cyan">{m.model}</Badge></td>
                  <td className="text-emerald font-mono">{m.accuracy != null ? `${(m.accuracy*100).toFixed(1)}%` : "—"}</td>
                  <td className="font-mono text-muted">{m.brier_score?.toFixed(4) ?? "—"}</td>
                  <td className="font-mono text-muted">{m.log_loss?.toFixed(4) ?? "—"}</td>
                  <td className="font-mono text-muted">{m.calibration_err?.toFixed(4) ?? "—"}</td>
                  <td className={m.roi >= 0 ? "text-emerald font-mono" : "text-scarlet font-mono"}>{m.roi != null ? `${(m.roi*100).toFixed(1)}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-center py-8 text-muted text-sm">
            <p>No hay métricas disponibles todavía.</p>
            <p className="text-xs mt-1">Las métricas se generan después de ejecutar una evaluación sobre datos reales.</p>
          </div>
        )}
      </div>

      {/* Global stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total equipos",  value: (elo ?? []).length.toString(),                         color: "text-cyan" },
          { label: "Rating promedio", value: elo ? (elo.reduce((a,t) => a+t.rating,0)/elo.length).toFixed(0) : "—", color: "text-amber" },
          { label: "Rating máximo",  value: elo?.[0]?.rating.toFixed(0) ?? "—",                   color: "text-emerald" },
          { label: "Rating mínimo",  value: elo ? elo[elo.length-1]?.rating.toFixed(0) : "—",    color: "text-scarlet" },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <span className={`stat-value ${s.color}`}>{s.value}</span>
            <span className="stat-label">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
