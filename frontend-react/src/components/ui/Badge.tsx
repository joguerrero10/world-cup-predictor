import clsx from "clsx"

type Variant = "cyan" | "amber" | "green" | "red" | "purple" | "muted" | "outline"

interface Props {
  children: React.ReactNode
  variant?: Variant
  size?: "sm" | "md"
  className?: string
}

const variants: Record<Variant, string> = {
  cyan:    "bg-cyan/10 text-cyan border-cyan/20",
  amber:   "bg-amber/10 text-amber border-amber/20",
  green:   "bg-emerald/10 text-emerald border-emerald/20",
  red:     "bg-scarlet/10 text-scarlet border-scarlet/20",
  purple:  "bg-violet/10 text-violet border-violet/20",
  muted:   "bg-muted/10 text-muted border-muted/20",
  outline: "bg-transparent text-text border-border",
}

export function Badge({ children, variant = "muted", size = "sm", className }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  )
}

export function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge variant={ok ? "green" : "muted"}>
      <span className={clsx("w-1.5 h-1.5 rounded-full", ok ? "bg-emerald animate-pulse" : "bg-muted")} />
      {label}
    </Badge>
  )
}
