import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { TrendingUp, RefreshCw, Database } from "lucide-react"
import { fetchTransfers } from "../api/endpoints"
import { Badge } from "../components/ui/Badge"
import { TableRowSkeleton } from "../components/ui/LoadingSkeleton"
import type { TransferItem } from "../types"
import clsx from "clsx"

const TRANSFER_TYPES = ["Todos", "permanent", "loan", "loan_end", "free"]

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, "cyan" | "green" | "amber" | "muted"> = {
    permanent: "cyan",
    loan:      "amber",
    loan_end:  "green",
    free:      "muted",
  }
  const labels: Record<string, string> = {
    permanent: "Permanente",
    loan:      "Préstamo",
    loan_end:  "Fin préstamo",
    free:      "Free",
  }
  return (
    <Badge variant={map[type] ?? "muted"}>{labels[type] ?? type}</Badge>
  )
}

export function Transfers() {
  const [typeFilter, setTypeFilter] = useState("Todos")
  const [search, setSearch] = useState("")

  const {
    data: transfers = [],
    isLoading,
    isError,
    dataUpdatedAt,
    refetch,
    isFetching,
  } = useQuery<TransferItem[]>({
    queryKey: ["transfers"],
    queryFn: () => fetchTransfers({ limit: 200 }),
    staleTime: 10 * 60_000,
    retry: false,
  })

  const filtered = transfers
    .filter(t => typeFilter === "Todos" || t.transfer_type === typeFilter)
    .filter(t =>
      !search ||
      t.player.toLowerCase().includes(search.toLowerCase()) ||
      (t.from_team ?? "").toLowerCase().includes(search.toLowerCase()) ||
      t.to_team.toLowerCase().includes(search.toLowerCase())
    )

  const updatedAgo = dataUpdatedAt
    ? (() => {
        const diff = Math.floor((Date.now() - dataUpdatedAt) / 60_000)
        if (diff < 1) return "justo ahora"
        if (diff < 60) return `hace ${diff} min`
        return `hace ${Math.floor(diff / 60)}h`
      })()
    : null

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="card">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-5 h-5 text-cyan" />
            <div>
              <h2 className="section-title text-xl">MERCADO DE FICHAJES</h2>
              {updatedAgo && !isLoading && (
                <p className="text-xs text-muted">Actualizado {updatedAgo}</p>
              )}
            </div>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 text-xs text-muted hover:text-text transition-colors"
          >
            <RefreshCw className={clsx("w-3.5 h-3.5", isFetching && "animate-spin")} />
            Actualizar
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Search */}
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar jugador o club..."
            className="input-dark w-full"
          />
          {/* Type filter */}
          <div className="flex gap-1.5 flex-wrap">
            {TRANSFER_TYPES.map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={clsx(
                  "px-3 py-1.5 text-xs rounded-lg border transition-all",
                  typeFilter === t
                    ? "border-cyan/40 bg-cyan/10 text-cyan"
                    : "border-border text-muted hover:text-text"
                )}
              >
                {t === "Todos" ? "Todos" : t === "permanent" ? "Permanente" : t === "loan" ? "Préstamo" : t === "free" ? "Free" : "Fin préstamo"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error */}
      {isError && (
        <div className="card border-scarlet/20 bg-scarlet/5 text-scarlet text-sm p-4">
          Error al cargar fichajes. Verifica que el servicio esté activo.
        </div>
      )}

      {/* Main table */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <p className="section-label">
            {isLoading ? "Cargando fichajes..." : `${filtered.length} transferencias`}
          </p>
          {!isLoading && transfers.length > 0 && (
            <Badge variant="green">{transfers.length} en BD</Badge>
          )}
        </div>

        {isLoading ? (
          <table className="table-dark">
            <thead>
              <tr>
                <th>Jugador</th><th>Origen</th><th>Destino</th><th>Fecha</th><th>Tarifa</th><th>Tipo</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 8 }).map((_, i) => (
                <TableRowSkeleton key={i} cols={6} />
              ))}
            </tbody>
          </table>
        ) : transfers.length === 0 ? (
          <div className="text-center py-16 text-muted">
            <Database className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p className="text-sm font-medium">Sin datos de fichajes disponibles</p>
            <p className="text-xs mt-1">
              El ETL sincroniza transferencias diariamente desde API-Football.
            </p>
            <p className="text-xs mt-0.5 opacity-60">
              Puedes activar la sync manualmente desde el panel de administración.
            </p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-10 text-muted">
            <p className="text-sm">Sin resultados para la búsqueda actual.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-dark">
              <thead>
                <tr>
                  <th>Jugador</th>
                  <th>Origen</th>
                  <th>Destino</th>
                  <th>Fecha</th>
                  <th>Tarifa</th>
                  <th>Tipo</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t, i) => (
                  <motion.tr
                    key={t.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i * 0.02, 0.4) }}
                  >
                    <td className="font-medium text-text">{t.player}</td>
                    <td className="text-muted">{t.from_team ?? "—"}</td>
                    <td className="text-cyan">{t.to_team}</td>
                    <td className="text-muted text-xs">{t.date}</td>
                    <td className="font-mono text-amber">{t.fee_display}</td>
                    <td><TypeBadge type={t.transfer_type} /></td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
