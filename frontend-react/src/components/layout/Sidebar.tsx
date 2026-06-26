import { motion, AnimatePresence } from "framer-motion"
import clsx from "clsx"
import {
  LayoutDashboard, Crosshair, Trophy, BarChart3, Globe2,
  FlaskConical, Brain, User, Users, Calendar, TrendingUp,
  BarChart2, Settings, ChevronLeft, ChevronRight,
  GitCompare, History, MessageSquare, Menu
} from "lucide-react"
import type { Page } from "../../types"
import { useAppStore } from "../../store/useAppStore"

interface NavItem {
  id: Page
  label: string
  icon: React.ElementType
  group?: string
}

const NAV: NavItem[] = [
  // Main
  { id: "dashboard",    label: "Dashboard",       icon: LayoutDashboard, group: "PRINCIPAL" },
  { id: "prediction",   label: "Predicción",       icon: Crosshair },
  { id: "simulator",    label: "Simular Torneo",   icon: Trophy },
  { id: "probabilities",label: "Probabilidades",   icon: BarChart3 },
  { id: "elo",          label: "Ranking Elo",       icon: Globe2 },
  // Analysis
  { id: "ai-analysis",  label: "Análisis IA",      icon: Brain, group: "ANÁLISIS" },
  { id: "ai-chat",      label: "IA Chat",           icon: MessageSquare },
  { id: "models",       label: "Modelos",           icon: FlaskConical },
  { id: "laboratory",   label: "Laboratorio",       icon: FlaskConical },
  // Data
  { id: "players",      label: "Jugadores",         icon: User, group: "DATOS" },
  { id: "teams",        label: "Equipos",           icon: Users },
  { id: "compare",      label: "Comparador",        icon: GitCompare },
  { id: "statistics",   label: "Estadísticas",      icon: BarChart2 },
  { id: "transfers",    label: "Fichajes",           icon: TrendingUp },
  { id: "calendar",     label: "Calendario",        icon: Calendar },
  // Config
  { id: "history",      label: "Historial",         icon: History, group: "SISTEMA" },
  { id: "settings",     label: "Configuración",     icon: Settings },
]

export function Sidebar() {
  const { currentPage, sidebarOpen, setPage, toggleSidebar } = useAppStore()

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            className="fixed inset-0 bg-black/60 z-30 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={toggleSidebar}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex flex-col bg-surface border-r border-border",
          "transition-all duration-300 ease-in-out"
        )}
        animate={{ width: sidebarOpen ? 220 : 60 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 border-b border-border min-h-[60px]">
          <div className="w-8 h-8 rounded-lg bg-cyan/10 border border-cyan/20 flex items-center justify-center shrink-0">
            <span className="text-base">⚽</span>
          </div>
          <AnimatePresence>
            {sidebarOpen && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <p className="font-display text-sm tracking-widest text-text whitespace-nowrap">FOOTBALL AI</p>
                <p className="text-xs text-muted whitespace-nowrap">Analytics Platform</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV.map((item, i) => {
            const isActive = currentPage === item.id
            const Icon = item.icon
            const showGroup = item.group && sidebarOpen

            return (
              <div key={item.id}>
                {showGroup && (
                  <p className="text-[10px] uppercase tracking-widest text-muted/50 font-semibold px-2 pt-4 pb-1">
                    {item.group}
                  </p>
                )}
                <motion.button
                  onClick={() => setPage(item.id)}
                  className={clsx(
                    "w-full flex items-center gap-3 px-2 py-2.5 rounded-lg transition-all duration-150",
                    "text-sm font-medium cursor-pointer",
                    isActive
                      ? "bg-cyan/10 text-cyan border border-cyan/20"
                      : "text-muted hover:text-text hover:bg-white/5"
                  )}
                  whileHover={{ x: 2 }}
                  whileTap={{ scale: 0.97 }}
                  title={!sidebarOpen ? item.label : undefined}
                >
                  <Icon className={clsx("w-4 h-4 shrink-0", isActive ? "text-cyan" : "")} />
                  <AnimatePresence>
                    {sidebarOpen && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="whitespace-nowrap overflow-hidden"
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active"
                      className="ml-auto w-1 h-4 rounded-full bg-cyan"
                    />
                  )}
                </motion.button>
              </div>
            )
          })}
        </nav>

        {/* Collapse toggle */}
        <div className="border-t border-border p-2">
          <button
            onClick={toggleSidebar}
            className="w-full flex items-center justify-center p-2 rounded-lg text-muted hover:text-text hover:bg-white/5 transition-colors"
          >
            {sidebarOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </motion.aside>
    </>
  )
}
