import { motion } from "framer-motion"
import { type LucideIcon } from "lucide-react"
import clsx from "clsx"

interface Props {
  label: string
  value: string | number
  icon?: LucideIcon
  trend?: number
  color?: "cyan" | "amber" | "green" | "red" | "purple" | "muted"
  sublabel?: string
  loading?: boolean
  delay?: number
}

const colorMap = {
  cyan:   "text-cyan",
  amber:  "text-amber",
  green:  "text-emerald",
  red:    "text-scarlet",
  purple: "text-violet",
  muted:  "text-muted",
}

const bgMap = {
  cyan:   "bg-cyan/10",
  amber:  "bg-amber/10",
  green:  "bg-emerald/10",
  red:    "bg-scarlet/10",
  purple: "bg-violet/10",
  muted:  "bg-muted/10",
}

export function StatCard({ label, value, icon: Icon, trend, color = "cyan", sublabel, loading, delay = 0 }: Props) {
  if (loading) {
    return (
      <div className="card flex flex-col gap-3">
        <div className="skeleton h-4 w-24 rounded" />
        <div className="skeleton h-8 w-16 rounded" />
        <div className="skeleton h-3 w-20 rounded" />
      </div>
    )
  }

  return (
    <motion.div
      className="card-hover flex flex-col gap-2 cursor-default select-none"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        {Icon && (
          <div className={clsx("w-8 h-8 rounded-lg flex items-center justify-center", bgMap[color])}>
            <Icon className={clsx("w-4 h-4", colorMap[color])} />
          </div>
        )}
      </div>
      <div className={clsx("font-display text-3xl tracking-wider", colorMap[color])}>
        {value}
      </div>
      {(sublabel || trend !== undefined) && (
        <div className="flex items-center gap-2">
          {sublabel && <span className="text-xs text-muted">{sublabel}</span>}
          {trend !== undefined && (
            <span className={clsx("text-xs font-medium", trend >= 0 ? "text-emerald" : "text-scarlet")}>
              {trend >= 0 ? "+" : ""}{trend.toFixed(1)}%
            </span>
          )}
        </div>
      )}
    </motion.div>
  )
}
