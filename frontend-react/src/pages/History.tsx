import { motion } from "framer-motion"
import { History as HistoryIcon, Trash2, Download } from "lucide-react"
import { useAppStore } from "../store/useAppStore"
import { Badge } from "../components/ui/Badge"

export function History() {
  const { history, clearHistory } = useAppStore()

  function exportJSON() {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: "application/json" })
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "football_ai_history.json"; a.click()
  }

  function exportCSV() {
    const rows = history.map(h => ({
      id: h.id,
      type: h.type,
      label: h.label,
      timestamp: new Date(h.timestamp).toISOString(),
    }))
    const csv = ["id,type,label,timestamp", ...rows.map(r => Object.values(r).join(","))].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "history.csv"; a.click()
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="card flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HistoryIcon className="w-5 h-5 text-cyan" />
          <div>
            <h2 className="section-title text-xl">HISTORIAL</h2>
            <p className="text-xs text-muted">{history.length} entradas guardadas localmente</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={exportJSON} className="btn-ghost flex items-center gap-2 text-xs">
            <Download className="w-3 h-3" /> JSON
          </button>
          <button onClick={exportCSV} className="btn-ghost flex items-center gap-2 text-xs">
            <Download className="w-3 h-3" /> CSV
          </button>
          {history.length > 0 && (
            <button
              onClick={() => { if (confirm("¿Limpiar historial?")) clearHistory() }}
              className="btn-ghost text-xs text-scarlet border-scarlet/20 flex items-center gap-2"
            >
              <Trash2 className="w-3 h-3" /> Limpiar
            </button>
          )}
        </div>
      </div>

      {history.length === 0 ? (
        <div className="card text-center py-20 text-muted">
          <HistoryIcon className="w-12 h-12 mx-auto mb-3 opacity-20" />
          <p className="text-sm">No hay historial todavía</p>
          <p className="text-xs mt-1">Las predicciones y simulaciones se guardarán aquí</p>
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((entry, i) => (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.02 }}
              className="card-hover flex items-center gap-4 py-3"
            >
              <div className="w-8 h-8 rounded-lg bg-surface border border-border flex items-center justify-center text-sm">
                {entry.type === "prediction" ? "⚽" : entry.type === "simulation" ? "🏆" : "🧠"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text truncate">{entry.label}</p>
                <p className="text-xs text-muted">{new Date(entry.timestamp).toLocaleString("es")}</p>
              </div>
              <Badge variant={entry.type === "prediction" ? "cyan" : entry.type === "simulation" ? "amber" : "purple"}>
                {entry.type}
              </Badge>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
