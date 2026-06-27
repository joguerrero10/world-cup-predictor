import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Calendar as CalIcon, RefreshCw, Wifi, WifiOff } from "lucide-react"
import { fetchFixtures } from "../api/endpoints"
import type { FixtureItem } from "../types"

// ─── Competition filter tabs ──────────────────────────────────────────────────

const TABS = [
  { id: "",              label: "Todo",         flag: "🌐" },
  { id: "premier_league", label: "Premier",     flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  { id: "laliga",         label: "LaLiga",      flag: "🇪🇸" },
  { id: "bundesliga",     label: "Bundesliga",  flag: "🇩🇪" },
  { id: "serie_a",        label: "Serie A",     flag: "🇮🇹" },
  { id: "ligue_1",        label: "Ligue 1",     flag: "🇫🇷" },
  { id: "ucl",            label: "Champions",   flag: "⭐" },
  { id: "fifa_wc_2026",   label: "Mundial 2026", flag: "🌍" },
] as const

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: FixtureItem["status"] }) {
  if (status === "LIVE") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 border border-green-500/25">
        <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
        EN VIVO
      </span>
    )
  }
  if (status === "FINISHED") {
    return (
      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white/5 text-white/35">
        FINALIZADO
      </span>
    )
  }
  if (status === "POSTPONED") {
    return (
      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-red-500/10 text-red-400/60">
        APLAZADO
      </span>
    )
  }
  return (
    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400/80">
      PROGRAMADO
    </span>
  )
}

// ─── Single match row ─────────────────────────────────────────────────────────

function FixtureRow({ f }: { f: FixtureItem }) {
  const isLive     = f.status === "LIVE"
  const isFinished = f.status === "FINISHED"
  const homeWins   = isFinished && f.home_goals !== null && f.away_goals !== null && f.home_goals > f.away_goals
  const awayWins   = isFinished && f.home_goals !== null && f.away_goals !== null && f.away_goals > f.home_goals

  return (
    <div
      className={`
        flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors
        ${isLive
          ? "bg-green-500/5 border-green-500/20 hover:border-green-500/35"
          : "bg-white/[0.03] border-white/[0.06] hover:border-white/10"}
      `}
    >
      {/* Competition + round */}
      <div className="w-28 shrink-0 hidden sm:block">
        <p className="text-[10px] text-white/30 truncate leading-tight">{f.competition}</p>
        {f.round && <p className="text-[9px] text-white/20 truncate mt-0.5">{f.round}</p>}
      </div>

      {/* Teams + score */}
      <div className="flex-1 flex items-center justify-center gap-2 min-w-0">
        <span
          className={`text-sm font-medium text-right truncate flex-1 ${
            homeWins ? "text-white" : "text-white/65"
          }`}
        >
          {f.home_team}
        </span>

        <div className="shrink-0 w-16 text-center">
          {isFinished ? (
            <span className="text-base font-bold text-white tabular-nums">
              {f.home_goals} – {f.away_goals}
            </span>
          ) : (
            <span className={`text-sm font-medium ${isLive ? "text-green-400 animate-pulse" : "text-white/25"}`}>
              vs
            </span>
          )}
        </div>

        <span
          className={`text-sm font-medium text-left truncate flex-1 ${
            awayWins ? "text-white" : "text-white/65"
          }`}
        >
          {f.away_team}
        </span>
      </div>

      {/* Status + odds */}
      <div className="w-28 shrink-0 flex flex-col items-end gap-1">
        <StatusBadge status={f.status} />
        {f.p_home !== null && f.p_draw !== null && f.p_away !== null && !isFinished && (
          <div className="flex gap-1 text-[9px] text-white/22 tabular-nums">
            <span>{Math.round(f.p_home * 100)}%</span>
            <span className="text-white/15">·</span>
            <span>{Math.round(f.p_draw * 100)}%</span>
            <span className="text-white/15">·</span>
            <span>{Math.round(f.p_away * 100)}%</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Skeleton loader ──────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {[1, 2, 3].map(i => (
        <div key={i}>
          <div className="h-4 bg-white/5 rounded w-28 mb-3" />
          <div className="space-y-2">
            {[1, 2, 3].map(j => (
              <div key={j} className="h-14 bg-white/5 rounded-xl" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function Calendar() {
  const [fixtures, setFixtures]   = useState<FixtureItem[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState<string | null>(null)
  const [competition, setComp]    = useState("")
  const [lastUpdated, setUpdated] = useState<Date | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setLoading(true)
    try {
      const data = await fetchFixtures({
        competition: competition || undefined,
        with_predictions: true,
      })
      setFixtures(data)
      setUpdated(new Date())
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error de red")
    } finally {
      setLoading(false)
    }
  }, [competition])

  // Initial load + auto-refresh
  useEffect(() => {
    load(true)

    // Clear any previous timer
    if (timerRef.current) clearInterval(timerRef.current)

    // Refresh every 60s when there are live matches, every 5 min otherwise
    const delay = fixtures.some(f => f.status === "LIVE") ? 60_000 : 300_000
    timerRef.current = setInterval(() => load(false), delay)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competition])

  const hasLive = fixtures.some(f => f.status === "LIVE")
  const today   = new Date().toISOString().slice(0, 10)

  // Group by date
  const grouped = fixtures.reduce<Record<string, FixtureItem[]>>((acc, f) => {
    ;(acc[f.date] ??= []).push(f)
    return acc
  }, {})
  const dates = Object.keys(grouped).sort()

  const formatDate = (d: string): string => {
    if (d === today) return "Hoy"
    const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)
    if (d === tomorrow) return "Mañana"
    const dt = new Date(d + "T12:00:00")
    return dt.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" })
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CalIcon className="w-5 h-5 text-cyan" />
          <div>
            <h2 className="section-title text-xl">CALENDARIO</h2>
            <p className="text-xs text-muted">Partidos en tiempo real y próximas jornadas</p>
          </div>
          {hasLive && (
            <span className="flex items-center gap-1.5 text-xs text-green-400 ml-2">
              <Wifi className="w-3 h-3" />
              En directo
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-[10px] text-white/25 hidden sm:block">
              {lastUpdated.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <button
            onClick={() => load(true)}
            disabled={loading}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/8 transition-colors disabled:opacity-50"
            title="Actualizar"
          >
            <RefreshCw className={`w-4 h-4 text-white/40 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Competition tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setComp(tab.id)}
            className={`
              shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium transition-colors
              ${competition === tab.id
                ? "bg-cyan/15 text-cyan border border-cyan/25"
                : "bg-white/5 text-white/45 hover:text-white/65 hover:bg-white/8 border border-transparent"}
            `}
          >
            <span>{tab.flag}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Loading skeleton */}
      {loading && fixtures.length === 0 && <Skeleton />}

      {/* Error state */}
      {error && !loading && (
        <div className="card text-center py-10 space-y-2">
          <WifiOff className="w-8 h-8 text-white/15 mx-auto" />
          <p className="text-sm text-white/30">{error}</p>
          <p className="text-xs text-white/20">
            Los fixtures se mostrarán cuando el ETL sincronice datos
          </p>
          <button
            onClick={() => load(true)}
            className="mt-2 text-xs text-cyan/60 hover:text-cyan transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && fixtures.length === 0 && (
        <div className="card text-center py-10 space-y-2">
          <CalIcon className="w-8 h-8 text-white/15 mx-auto" />
          <p className="text-sm text-white/30">Sin partidos en este período</p>
          <p className="text-xs text-white/20">
            Ejecuta el ETL para cargar fixtures: <code className="text-cyan/50">POST /update-data</code>
          </p>
        </div>
      )}

      {/* Fixtures grouped by date */}
      <AnimatePresence>
        {dates.map(d => (
          <motion.section
            key={d}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-2"
          >
            <h3
              className={`text-xs font-semibold capitalize tracking-wide ${
                d === today ? "text-cyan" : "text-white/40"
              }`}
            >
              {formatDate(d)}
              <span className="ml-2 font-normal text-white/20">({grouped[d].length})</span>
            </h3>

            <div className="space-y-1.5">
              {grouped[d].map(f => (
                <FixtureRow key={f.match_id} f={f} />
              ))}
            </div>
          </motion.section>
        ))}
      </AnimatePresence>

      {/* Live refresh indicator */}
      {hasLive && (
        <div className="text-center">
          <span className="text-[10px] text-green-400/50">
            Actualizando cada 60 segundos
          </span>
        </div>
      )}
    </div>
  )
}
