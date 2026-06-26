import { motion } from "framer-motion"
import { Menu, RefreshCw, Bell, Wifi, WifiOff } from "lucide-react"
import { useAppStore } from "../../store/useAppStore"
import { useQuery } from "@tanstack/react-query"
import { fetchHealth } from "../../api/endpoints"
import clsx from "clsx"

const PAGE_TITLES: Record<string, string> = {
  dashboard:     "Dashboard",
  prediction:    "Predicción de Partido",
  simulator:     "Simulador de Torneo",
  probabilities: "Probabilidades",
  elo:           "Ranking Elo",
  models:        "Modelos",
  "ai-analysis": "Análisis IA",
  players:       "Jugadores",
  teams:         "Equipos",
  calendar:      "Calendario",
  transfers:     "Mercado de Fichajes",
  statistics:    "Estadísticas",
  "ai-chat":     "IA — Chat",
  laboratory:    "Laboratorio de Modelos",
  settings:      "Configuración",
  compare:       "Comparador",
  history:       "Historial",
}

export function Header() {
  const { currentPage, toggleSidebar } = useAppStore()
  const { data: health, isError, refetch, isFetching } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    staleTime: 20_000,
  })

  const online = !isError && health?.status === "ok"

  return (
    <motion.header
      className="fixed top-0 right-0 left-0 z-30 flex items-center h-[60px] px-4 gap-4
                 bg-surface/80 backdrop-blur-md border-b border-border"
      style={{ paddingLeft: "calc(var(--sidebar-width, 60px) + 1rem)" }}
      initial={{ y: -60 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Mobile menu */}
      <button
        onClick={toggleSidebar}
        className="lg:hidden p-1.5 rounded-lg hover:bg-white/5 text-muted hover:text-text transition-colors"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Page title */}
      <div className="flex-1 min-w-0">
        <motion.h1
          key={currentPage}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="font-display text-xl tracking-wider text-text truncate"
        >
          {PAGE_TITLES[currentPage] ?? currentPage}
        </motion.h1>
      </div>

      {/* Status */}
      <div className="flex items-center gap-3">
        {health && (
          <div className="hidden md:flex items-center gap-2 text-xs text-muted">
            <span className={clsx("w-1.5 h-1.5 rounded-full", online ? "bg-emerald animate-pulse" : "bg-scarlet")}>
            </span>
            <span>{health.teams_loaded} equipos</span>
            {health.dc_ready && <span className="text-cyan/60">· DC ✓</span>}
          </div>
        )}

        <button
          onClick={() => refetch()}
          className={clsx(
            "p-1.5 rounded-lg hover:bg-white/5 text-muted hover:text-text transition-colors",
            isFetching && "animate-spin"
          )}
          title="Actualizar"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        <div
          className={clsx(
            "p-1.5 rounded-lg",
            online ? "text-emerald" : "text-muted"
          )}
          title={online ? "API conectada" : "API desconectada"}
        >
          {online ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
        </div>
      </div>
    </motion.header>
  )
}
