import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Trophy, Play, RefreshCw, Download } from "lucide-react"
import { createSimulationJob, fetchSimulationJob, fetchSimulationJobResult } from "../api/endpoints"
import { PlotlyChart, DonutChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import type { SimulationJobStatus, TournamentProbs } from "../types"
import type { Data } from "plotly.js"
import clsx from "clsx"

// ─── Configuración de competiciones ──────────────────────────────────────────

const COMPETITIONS = [
  { id: "fifa_wc_2026",   name: "FIFA World Cup 2026",  emoji: "🌍", type: "knockout" as const },
  { id: "ucl",            name: "Champions League",     emoji: "⭐", type: "knockout" as const },
  { id: "premier_league", name: "Premier League",       emoji: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", type: "league"   as const },
  { id: "laliga",         name: "LaLiga",               emoji: "🇪🇸", type: "league"   as const },
  { id: "bundesliga",     name: "Bundesliga",           emoji: "🇩🇪", type: "league"   as const },
  { id: "serie_a",        name: "Serie A",              emoji: "🇮🇹", type: "league"   as const },
  { id: "ligue_1",        name: "Ligue 1",              emoji: "🇫🇷", type: "league"   as const },
]

const LEAGUE_IDS = new Set(["premier_league", "laliga", "bundesliga", "serie_a", "ligue_1"])

const SIM_OPTIONS = [
  { label: "1K",   value: 1_000 },
  { label: "10K",  value: 10_000 },
  { label: "100K", value: 100_000 },
  { label: "500K", value: 500_000 },
  { label: "1M",   value: 1_000_000 },
]

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(v: number | undefined) {
  return `${((v ?? 0) * 100).toFixed(1)}%`
}

/** Devuelve los datos de "fase previa" según el tipo de competición. */
function getEarlyRoundData(result: TournamentProbs, competitionId: string): Record<string, number> {
  if (LEAGUE_IDS.has(competitionId)) return {}
  return result.extra?.group_qualified ?? result.extra?.league_phase_top8 ?? {}
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function TournamentSimulator() {
  const [competition, setCompetition] = useState("fifa_wc_2026")
  const [nSims, setNSims]             = useState(10_000)
  const [jobId, setJobId]             = useState<number | null>(null)
  const [job, setJob]                 = useState<SimulationJobStatus | null>(null)
  const [result, setResult]           = useState<TournamentProbs | null>(null)
  const [elapsed, setElapsed]         = useState(0)

  const isLeague   = LEAGUE_IDS.has(competition)
  const compConfig = COMPETITIONS.find(c => c.id === competition)!

  // Reset result cuando cambia la competición
  useEffect(() => {
    setResult(null)
    setJob(null)
    setJobId(null)
  }, [competition])

  // Poll job status
  useQuery({
    queryKey: ["sim-job", jobId],
    queryFn: async () => {
      if (!jobId) return null
      const j = await fetchSimulationJob(jobId)
      setJob(j)
      if (j.status === "completed") {
        const r = await fetchSimulationJobResult(jobId)
        if (r.result) setResult(r.result as TournamentProbs)
      }
      return j
    },
    enabled: !!jobId && job?.status !== "completed" && job?.status !== "failed",
    refetchInterval: 1000,
  })

  // Cronómetro visual mientras corre
  useEffect(() => {
    if (job?.status !== "running") { setElapsed(0); return }
    const timer = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(timer)
  }, [job?.status])

  const { mutate: startSim, isPending } = useMutation({
    mutationFn: () => createSimulationJob({ competition_id: competition, n_sims: nSims }),
    onSuccess: (j) => { setJobId(j.id); setJob(j); setResult(null) },
  })

  const isRunning = job?.status === "running" || job?.status === "queued"

  // Ordenar equipos por probabilidad de campeón
  const champion = result?.champion
    ? Object.entries(result.champion).sort((a, b) => b[1] - a[1])
    : []
  const top10Champ = champion.slice(0, 10)

  // Datos del gráfico de barras
  const champBarData: Data[] = top10Champ.length > 0 ? [{
    type: "bar",
    x: top10Champ.map(([_, p]) => p * 100),
    y: top10Champ.map(([t]) => t),
    orientation: "h",
    marker: {
      color: top10Champ.map((_, i) =>
        i === 0 ? "#F0B429" : i === 1 ? "#E2E8F0" : i === 2 ? "#CD7F32" : "#00D4FF80"
      ),
    },
    text: top10Champ.map(([_, p]) => `${(p * 100).toFixed(1)}%`),
    textposition: "outside",
    textfont: { color: "#E2E8F0", size: 11 },
    hovertemplate: "%{y}: %{x:.1f}%<extra></extra>",
  }] : []

  // CSV export — columnas según tipo de competición
  function exportCsv() {
    if (!result) return
    const headers = isLeague
      ? "Equipo,Campeón,Top4,Top6,Descenso"
      : "Equipo,Campeón,Finalista,Semifinal,Grupos"
    const rows = champion.map(([t, p]) => {
      if (isLeague) {
        return `${t},${p},${result.top4[t] ?? 0},${result.top6[t] ?? 0},${result.relegated[t] ?? 0}`
      }
      const early = getEarlyRoundData(result, competition)
      return `${t},${p},${result.finalist[t] ?? 0},${result.semifinalist[t] ?? 0},${early[t] ?? 0}`
    })
    const csv = [headers, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `sim_${competition}_${nSims}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  function exportJson() {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = `sim_${competition}_${nSims}.json`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Panel de configuración ── */}
      <div className="card space-y-5">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-amber" />
          <h2 className="section-title text-xl">CONFIGURAR SIMULACIÓN</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Selector de competición */}
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wider text-muted font-medium">
              Competición
            </label>
            <div className="grid grid-cols-1 gap-2">
              {COMPETITIONS.map(c => (
                <button
                  key={c.id}
                  onClick={() => setCompetition(c.id)}
                  className={clsx(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg border text-sm transition-all duration-150",
                    competition === c.id
                      ? "border-cyan/40 bg-cyan/10 text-cyan"
                      : "border-border bg-transparent text-muted hover:border-border hover:text-text hover:bg-white/5"
                  )}
                >
                  <span className="text-base">{c.emoji}</span>
                  <span className="flex-1 text-left">{c.name}</span>
                  <span className={clsx(
                    "text-xs px-1.5 py-0.5 rounded",
                    c.type === "league"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-violet-500/10 text-violet-400"
                  )}>
                    {c.type === "league" ? "Liga" : "Copa"}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Sims + botón */}
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs uppercase tracking-wider text-muted font-medium">
                Número de simulaciones
              </label>
              <div className="grid grid-cols-3 gap-2">
                {SIM_OPTIONS.map(s => (
                  <button
                    key={s.value}
                    onClick={() => setNSims(s.value)}
                    className={clsx(
                      "py-2 px-3 rounded-lg border text-sm font-display tracking-wider transition-all",
                      nSims === s.value
                        ? "border-amber/40 bg-amber/10 text-amber"
                        : "border-border text-muted hover:text-text hover:bg-white/5"
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted">{nSims.toLocaleString()} simulaciones Monte Carlo</p>
            </div>

            {/* ETA */}
            <div className="bg-gradient-field rounded-xl p-4 space-y-1 border border-border">
              <p className="text-xs text-muted uppercase tracking-wider">Tiempo estimado</p>
              <p className="font-display text-2xl text-cyan tracking-wider">
                {nSims <= 10_000 ? "~2s" : nSims <= 100_000 ? "~5s" : nSims <= 500_000 ? "~20s" : "~60s"}
              </p>
              <p className="text-xs text-muted">Motor Monte Carlo vectorizado</p>
            </div>

            <button
              onClick={() => startSim()}
              disabled={isPending || isRunning}
              className={clsx(
                "btn-primary w-full flex items-center justify-center gap-2",
                (isPending || isRunning) && "opacity-60 cursor-not-allowed"
              )}
            >
              {isRunning
                ? <RefreshCw className="w-4 h-4 animate-spin" />
                : <Play className="w-4 h-4" />}
              {isRunning ? "Simulando..." : "INICIAR SIMULACIÓN"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Progreso del job ── */}
      <AnimatePresence>
        {job && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="card space-y-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="section-label">Job #{job.id}</p>
                <h3 className="section-title text-xl">
                  {compConfig.emoji} {compConfig.name} — {nSims.toLocaleString()} sims
                </h3>
              </div>
              <Badge
                variant={
                  job.status === "completed" ? "green" :
                  job.status === "running"   ? "cyan"  :
                  job.status === "failed"    ? "red"   : "amber"
                }
              >
                {job.status.toUpperCase()}
              </Badge>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="stat-card">
                <span className="stat-value text-cyan">
                  {isRunning ? elapsed : (job.duration_seconds?.toFixed(1) ?? "—")}s
                </span>
                <span className="stat-label">{isRunning ? "Transcurrido" : "Duración"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-value text-amber">{nSims.toLocaleString()}</span>
                <span className="stat-label">Simulaciones</span>
              </div>
              <div className="stat-card">
                <span className="stat-value text-text">{compConfig.emoji}</span>
                <span className="stat-label">{compConfig.name}</span>
              </div>
              <div className="stat-card">
                <span className="stat-value text-text">{job.model_name?.toUpperCase()}</span>
                <span className="stat-label">Modelo</span>
              </div>
            </div>

            {isRunning && (
              <div className="space-y-1">
                <div className="progress-bar">
                  <motion.div
                    className="progress-fill bg-gradient-to-r from-cyan to-amber"
                    animate={{ width: ["0%", "90%"] }}
                    transition={{ duration: 3, ease: "easeInOut" }}
                  />
                </div>
                <p className="text-xs text-muted text-center">
                  Procesando {nSims.toLocaleString()} torneos...
                </p>
              </div>
            )}

            {job.status === "failed" && (
              <div className="bg-scarlet/10 border border-scarlet/20 rounded-lg p-3 text-sm text-scarlet">
                {job.error_message ?? "Simulación fallida"}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Resultados ── */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Meta info */}
            <div className="flex items-center gap-4 text-xs text-muted">
              <span>{result.n_sims.toLocaleString()} simulaciones</span>
              <span>·</span>
              <span>{result.elapsed_seconds?.toFixed(1)}s</span>
              <span>·</span>
              <span>{result.sims_per_second?.toLocaleString()} sims/s</span>
              <span>·</span>
              <span className={clsx(
                "px-2 py-0.5 rounded text-xs",
                result.team_type === "national"
                  ? "bg-violet-500/10 text-violet-400"
                  : "bg-emerald-500/10 text-emerald-400"
              )}>
                {result.team_type === "national" ? "Selecciones" : "Clubes"}
              </span>
            </div>

            {/* Podio: Top 3 */}
            {champion.length >= 3 && (
              <div>
                <p className="section-label mb-3">Campeones más probables</p>
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { data: champion[0], medal: "🥇", delay: 0 },
                    { data: champion[1], medal: "🥈", delay: 0.1 },
                    { data: champion[2], medal: "🥉", delay: 0.2 },
                  ].map(({ data: [team, prob], medal, delay }) => (
                    <motion.div
                      key={team}
                      className="card-hover text-center p-4 space-y-2"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay }}
                    >
                      <span className="text-3xl">{medal}</span>
                      <p className="font-display text-lg tracking-wider text-text">{team}</p>
                      <p className="font-display text-3xl tracking-wider text-amber">{pct(prob)}</p>
                      <p className="text-xs text-muted">Prob. campeón</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            {/* Gráficos */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="card">
                <p className="section-label mb-2">Top 10 — Probabilidad de campeón</p>
                <PlotlyChart
                  data={champBarData}
                  height={320}
                  layout={{
                    xaxis: { title: { text: "%", font: { color: "#64748B" } }, showgrid: false },
                    yaxis: { autorange: "reversed", tickfont: { color: "#E2E8F0", size: 11 } },
                    bargap: 0.25,
                    margin: { l: 100, r: 70, t: 10, b: 40 },
                  }}
                />
              </div>
              <div className="card">
                <p className="section-label mb-2">Distribución de campeones (Top 5)</p>
                <DonutChart
                  labels={champion.slice(0, 5).map(([t]) => t)}
                  values={champion.slice(0, 5).map(([_, p]) => p)}
                  colors={["#F0B429", "#00D4FF", "#CD7F32", "#A855F7", "#22C55E"]}
                />
              </div>
            </div>

            {/* Tabla de probabilidades */}
            <div className="card">
              <p className="section-label mb-3">Tabla completa de probabilidades</p>
              <div className="overflow-x-auto">
                <table className="table-dark">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Equipo</th>
                      <th>Campeón</th>
                      {isLeague ? (
                        <>
                          <th>Top 4</th>
                          <th>Top 6</th>
                          <th className="text-scarlet/80">Descenso</th>
                        </>
                      ) : (
                        <>
                          <th>Finalista</th>
                          <th>Semifinal</th>
                          <th>{competition === "ucl" ? "Fase grupos" : "Clasificó grupos"}</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {champion.map(([team, prob], i) => {
                      const earlyRound = getEarlyRoundData(result, competition)
                      return (
                        <tr key={team} className={i < 3 ? "text-amber" : ""}>
                          <td className="font-display text-lg w-8">
                            {i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : i + 1}
                          </td>
                          <td className="font-medium">{team}</td>
                          <td>
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-border rounded overflow-hidden">
                                <div
                                  className="h-full bg-amber rounded"
                                  style={{ width: pct(prob) }}
                                />
                              </div>
                              <span className="text-xs text-amber">{pct(prob)}</span>
                            </div>
                          </td>
                          {isLeague ? (
                            <>
                              <td className="text-cyan">{pct(result.top4[team])}</td>
                              <td className="text-muted">{pct(result.top6[team])}</td>
                              <td className="text-scarlet">{pct(result.relegated[team])}</td>
                            </>
                          ) : (
                            <>
                              <td className="text-cyan">{pct(result.finalist[team])}</td>
                              <td className="text-muted">{pct(result.semifinalist[team])}</td>
                              <td className="text-muted">{pct(earlyRound[team])}</td>
                            </>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Exportar */}
            <div className="flex gap-2 justify-end">
              <button onClick={exportCsv} className="btn-ghost flex items-center gap-2">
                <Download className="w-4 h-4" />
                Exportar CSV
              </button>
              <button onClick={exportJson} className="btn-ghost flex items-center gap-2">
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
