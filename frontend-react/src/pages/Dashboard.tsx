import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import {
  Users, Trophy, Activity,
  TrendingUp, Clock, Zap, CheckCircle, AlertCircle, BarChart3
} from "lucide-react"
import { StatCard } from "../components/ui/StatCard"
import { Badge, StatusBadge } from "../components/ui/Badge"
import { CardSkeleton } from "../components/ui/LoadingSkeleton"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { fetchHealth, fetchSystemStats, fetchEloRankings, fetchModelMetrics } from "../api/endpoints"
import type { Data } from "plotly.js"

export function Dashboard() {
  const { data: health, isLoading: hLoading } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: stats, isLoading: sLoading } = useQuery({
    queryKey: ["system-stats"],
    queryFn: fetchSystemStats,
    refetchInterval: 30_000,
    retry: 1,
  })

  const { data: elo } = useQuery({
    queryKey: ["elo-rankings"],
    queryFn: fetchEloRankings,
    staleTime: 60_000,
  })

  const { data: metrics } = useQuery({
    queryKey: ["model-metrics"],
    queryFn: fetchModelMetrics,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const loading = hLoading || sLoading
  const top10 = elo?.slice(0, 10) ?? []

  // Chart: top 10 elo bar
  const eloChartData: Data[] = top10.length > 0 ? [{
    type: "bar",
    x: top10.map(t => t.rating),
    y: top10.map(t => t.team),
    orientation: "h",
    marker: {
      color: top10.map((_, i) => i === 0 ? "#F0B429" : i === 1 ? "#E2E8F0" : i === 2 ? "#CD7F32" : "#00D4FF"),
    },
    text: top10.map(t => t.rating.toFixed(0)),
    textposition: "outside",
    textfont: { color: "#64748B", size: 11 },
    hovertemplate: "%{y}: %{x:.0f}<extra></extra>",
  }] : []

  // Model status pie
  const modelData: Data[] = health ? [{
    type: "pie",
    hole: 0.65,
    labels: ["XGBoost", "Dixon-Coles", "Elo", "Klement"],
    values: [
      health.form_model_ready ? 80.9 : 0,
      health.dc_ready ? 19.1 : 30,
      health.teams_loaded > 0 ? 30 : 0,
      health.klement_factors_loaded > 0 ? 15 : 0,
    ],
    marker: { colors: ["#00D4FF", "#F0B429", "#A855F7", "#22C55E"] },
    textinfo: "label+percent",
    textfont: { color: "#E2E8F0", size: 10 },
    hovertemplate: "%{label}: %{percent}<extra></extra>",
  }] : []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Welcome banner */}
      <motion.div
        className="relative overflow-hidden card border-cyan/20 p-6"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-cyan/5 via-transparent to-amber/5 pointer-events-none" />
        <div className="relative flex flex-col md:flex-row md:items-center gap-4">
          <div className="flex-1">
            <p className="section-label mb-1">Football AI Analytics</p>
            <h2 className="font-display text-3xl md:text-4xl tracking-wider text-text">
              PLATAFORMA DE <span className="text-gradient-cyan">ANÁLISIS IA</span>
            </h2>
            <p className="text-sm text-muted mt-1">
              Elo · Dixon-Coles · Klement · XGBoost · Monte Carlo · Simulación masiva
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge ok={!!health?.teams_loaded} label={`${health?.teams_loaded ?? 0} equipos`} />
            <StatusBadge ok={!!health?.dc_ready} label="Dixon-Coles" />
            <StatusBadge ok={!!health?.form_model_ready} label="XGBoost" />
            <StatusBadge ok={(health?.klement_factors_loaded ?? 0) > 0} label="Klement" />
          </div>
        </div>
      </motion.div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              label="Equipos cargados"
              value={stats?.teams_loaded ?? health?.teams_loaded ?? "—"}
              icon={Users}
              color="cyan"
              delay={0}
            />
            <StatCard
              label="Jugadores"
              value={stats?.players_count ?? "—"}
              icon={Users}
              color="amber"
              delay={0.05}
            />
            <StatCard
              label="Partidos"
              value={stats?.matches_count?.toLocaleString() ?? "—"}
              icon={Activity}
              color="green"
              delay={0.1}
            />
            <StatCard
              label="Ligas"
              value={stats?.leagues_count ?? "6"}
              icon={Trophy}
              color="purple"
              delay={0.15}
            />
            <StatCard
              label="Modelo activo"
              value={stats?.active_model?.toUpperCase() ?? "HYBRID"}
              icon={BarChart3}
              color="cyan"
              delay={0.2}
            />
            <StatCard
              label="Precisión"
              value={stats?.model_accuracy != null ? `${(stats.model_accuracy * 100).toFixed(1)}%` : "—"}
              icon={TrendingUp}
              color="amber"
              sublabel="histórica"
              delay={0.25}
            />
            <StatCard
              label="Simulaciones"
              value={stats?.simulations_count?.toLocaleString() ?? "—"}
              icon={Zap}
              color="green"
              delay={0.3}
            />
            <StatCard
              label="T. simulación"
              value={stats?.avg_simulation_time != null ? `${stats.avg_simulation_time.toFixed(1)}s` : "—"}
              icon={Clock}
              color="red"
              sublabel="promedio"
              delay={0.35}
            />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top 10 Elo */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="section-label">Clasificación</p>
              <h3 className="section-title text-xl">TOP 10 RANKING ELO</h3>
            </div>
            <Badge variant="cyan">Elo Rating</Badge>
          </div>
          {top10.length > 0 ? (
            <PlotlyChart
              data={eloChartData}
              height={280}
              layout={{
                xaxis: { showgrid: false, zeroline: false, visible: false },
                yaxis: { tickfont: { color: "#E2E8F0", size: 11 }, autorange: "reversed" },
                bargap: 0.3,
                margin: { l: 100, r: 60, t: 8, b: 8 },
              }}
            />
          ) : (
            <div className="h-[280px] flex items-center justify-center text-muted text-sm">
              Sin datos de ranking. Carga los partidos primero.
            </div>
          )}
        </div>

        {/* Model weights pie */}
        <div className="card">
          <div className="mb-4">
            <p className="section-label">Modelo Híbrido</p>
            <h3 className="section-title text-xl">PESOS DE MODELOS</h3>
          </div>
          {health ? (
            <PlotlyChart
              data={modelData}
              height={220}
              layout={{
                showlegend: true,
                legend: { orientation: "h", x: 0, y: -0.1, font: { color: "#E2E8F0", size: 10 } },
                margin: { l: 20, r: 20, t: 10, b: 40 },
                annotations: [{
                  text: "Hybrid",
                  x: 0.5, y: 0.5,
                  font: { size: 14, color: "#E2E8F0", family: "Bebas Neue" },
                  showarrow: false,
                }],
              }}
            />
          ) : (
            <CardSkeleton />
          )}
        </div>
      </div>

      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* API Status */}
        <div className="card space-y-4">
          <div>
            <p className="section-label">Sistema</p>
            <h3 className="section-title text-xl">ESTADO DE LA API</h3>
          </div>
          <div className="space-y-3">
            {[
              { label: "API FastAPI", ok: health?.status === "ok", detail: health?.status ?? "—" },
              { label: "Dixon-Coles", ok: health?.dc_ready ?? false, detail: health?.dc_ready ? "Entrenado" : "Sin entrenar" },
              { label: "XGBoost Form Model", ok: health?.form_model_ready ?? false, detail: health?.form_model_ready ? "Listo" : "Sin entrenar" },
              { label: "Klement Factors", ok: (health?.klement_factors_loaded ?? 0) > 0, detail: `${health?.klement_factors_loaded ?? 0} equipos` },
              { label: "Equipos en memoria", ok: (health?.teams_loaded ?? 0) > 0, detail: `${health?.teams_loaded ?? 0} equipos` },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <div className="flex items-center gap-2">
                  {item.ok
                    ? <CheckCircle className="w-4 h-4 text-emerald" />
                    : <AlertCircle className="w-4 h-4 text-muted" />
                  }
                  <span className="text-sm text-text">{item.label}</span>
                </div>
                <Badge variant={item.ok ? "green" : "muted"}>{item.detail}</Badge>
              </div>
            ))}
          </div>
        </div>

        {/* Competitions */}
        <div className="card space-y-4">
          <div>
            <p className="section-label">Competiciones</p>
            <h3 className="section-title text-xl">LIGAS SOPORTADAS</h3>
          </div>
          <div className="space-y-2">
            {[
              { name: "FIFA World Cup 2026",    id: "fifa_wc_2026",   type: "🌍", tier: "Internacional" },
              { name: "UEFA Champions League",  id: "ucl",            type: "⭐", tier: "Continental" },
              { name: "Premier League",         id: "premier_league", type: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", tier: "Inglaterra" },
              { name: "LaLiga",                 id: "laliga",         type: "🇪🇸", tier: "España" },
              { name: "Bundesliga",             id: "bundesliga",     type: "🇩🇪", tier: "Alemania" },
              { name: "Serie A",                id: "serie_a",        type: "🇮🇹", tier: "Italia" },
              { name: "Ligue 1",                id: "ligue_1",        type: "🇫🇷", tier: "Francia" },
            ].map((comp) => (
              <div key={comp.id} className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-base">{comp.type}</span>
                  <span className="text-sm text-text">{comp.name}</span>
                </div>
                <Badge variant="muted">{comp.tier}</Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Model metrics card */}
      {(metrics?.stored.length || Object.keys(metrics?.live ?? {}).length) ? (
        <div className="card space-y-3">
          <div>
            <p className="section-label">Evaluación</p>
            <h3 className="section-title text-xl">MÉTRICAS DEL MODELO</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Live metrics */}
            {Object.entries(metrics?.live ?? {}).length > 0 && (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wider text-muted">En tiempo real</p>
                {Object.entries(metrics!.live).map(([model, m]) => (
                  <div key={model} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <span className="text-sm font-mono text-cyan uppercase">{model}</span>
                    <div className="flex gap-3 text-xs text-muted">
                      {m.accuracy != null && (
                        <span>
                          Acc <span className="text-text font-mono">{(m.accuracy * 100).toFixed(1)}%</span>
                        </span>
                      )}
                      {m.brier_score != null && (
                        <span>
                          Brier <span className="text-text font-mono">{m.brier_score.toFixed(3)}</span>
                        </span>
                      )}
                      <span className="text-border">n={m.n_evaluated}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* Stored metrics */}
            {metrics?.stored.length ? (
              <div className="space-y-2">
                <p className="text-xs uppercase tracking-wider text-muted">Guardadas en BD</p>
                {metrics.stored.slice(0, 5).map((m, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                    <span className="text-sm font-mono text-amber uppercase">{m.model}</span>
                    <div className="flex gap-3 text-xs text-muted">
                      {m.accuracy != null && (
                        <span>
                          Acc <span className="text-text font-mono">{(m.accuracy * 100).toFixed(1)}%</span>
                        </span>
                      )}
                      {m.brier_score != null && (
                        <span>
                          Brier <span className="text-text font-mono">{m.brier_score.toFixed(3)}</span>
                        </span>
                      )}
                      {m.evaluated_at && (
                        <span className="text-border">{new Date(m.evaluated_at).toLocaleDateString("es-ES")}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          {metrics?.note && (
            <p className="text-xs text-muted/60 italic">{metrics.note}</p>
          )}
        </div>
      ) : null}

      {/* Last updated */}
      <div className="text-center text-xs text-muted/50">
        Football AI Analytics · Elo · Dixon-Coles · Klement · XGBoost · Monte Carlo
        {stats?.last_updated && <span> · Actualizado: {new Date(stats.last_updated).toLocaleString("es")}</span>}
      </div>
    </div>
  )
}
