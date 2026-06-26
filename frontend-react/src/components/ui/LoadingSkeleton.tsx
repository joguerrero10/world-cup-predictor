import clsx from "clsx"

interface SkeletonProps { className?: string }

export function Skeleton({ className }: SkeletonProps) {
  return <div className={clsx("skeleton", className)} />
}

export function CardSkeleton() {
  return (
    <div className="card flex flex-col gap-3 animate-pulse">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-3 w-40" />
    </div>
  )
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="border-b border-border/50">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="py-3 px-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  )
}

export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div className="card animate-pulse flex flex-col gap-2" style={{ height }}>
      <Skeleton className="h-4 w-32" />
      <div className="flex-1 flex items-end gap-2 p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex-1 bg-border/50 rounded" style={{ height: `${30 + Math.random() * 60}%` }} />
        ))}
      </div>
    </div>
  )
}
