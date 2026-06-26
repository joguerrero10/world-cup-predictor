import { motion } from "framer-motion"

interface Props {
  home: string
  away: string
  homeWin: number
  draw: number
  awayWin: number
  homeFlag?: string
  awayFlag?: string
  showLabels?: boolean
}

function pct(v: number) { return `${(v * 100).toFixed(1)}%` }

export function DuelBar({ home, away, homeWin, draw, awayWin, showLabels = true }: Props) {
  return (
    <div className="w-full space-y-4">
      {/* Team names + percentages */}
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-1">
          <span className="font-display text-lg tracking-wider text-text">{home}</span>
          <span className="font-display text-4xl tracking-wider text-cyan">{pct(homeWin)}</span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-xs uppercase tracking-widest text-muted font-display">VS</span>
          <span className="font-display text-2xl tracking-wider text-muted">{pct(draw)}</span>
          <span className="text-xs text-muted">Empate</span>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="font-display text-lg tracking-wider text-text">{away}</span>
          <span className="font-display text-4xl tracking-wider text-amber">{pct(awayWin)}</span>
        </div>
      </div>

      {/* Bar */}
      <div className="relative h-2.5 rounded-full bg-border overflow-hidden">
        <motion.div
          className="absolute inset-y-0 left-0 bg-cyan rounded-l-full"
          initial={{ width: 0 }}
          animate={{ width: pct(homeWin) }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
        <motion.div
          className="absolute inset-y-0 bg-muted"
          style={{ left: pct(homeWin) }}
          initial={{ width: 0 }}
          animate={{ width: pct(draw) }}
          transition={{ duration: 0.8, delay: 0.1, ease: "easeOut" }}
        />
        <motion.div
          className="absolute inset-y-0 right-0 bg-amber rounded-r-full"
          initial={{ width: 0 }}
          animate={{ width: pct(awayWin) }}
          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
        />
      </div>

      {showLabels && (
        <div className="flex justify-between text-xs text-muted uppercase tracking-wider">
          <span>Victoria local</span>
          <span>Empate</span>
          <span>Victoria visitante</span>
        </div>
      )}
    </div>
  )
}

interface ProbBarProps {
  label: string
  value: number
  color?: string
  max?: number
}

export function ProbBar({ label, value, color = "#00D4FF", max = 1 }: ProbBarProps) {
  const pctVal = (value / max) * 100
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted w-32 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pctVal}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <span className="text-xs font-medium text-text w-12 text-right">{pct(value)}</span>
    </div>
  )
}
