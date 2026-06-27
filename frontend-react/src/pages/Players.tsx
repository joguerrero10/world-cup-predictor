import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { User, Search } from "lucide-react"
import { fetchEloRankings, fetchPlayers } from "../api/endpoints"
import { Badge } from "../components/ui/Badge"
import { TableRowSkeleton } from "../components/ui/LoadingSkeleton"
import clsx from "clsx"

const POSITIONS = ["Todos", "GK", "DEF", "MID", "FWD"]


export function Players() {
  const [selectedTeam, setSelectedTeam] = useState("")
  const [search, setSearch] = useState("")
  const [position, setPosition] = useState("Todos")
  const [sortBy, setSortBy] = useState<"goals_per_90" | "xg_per_90" | "assists_per_90">("goals_per_90")

  const { data: elo } = useQuery({ queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000 })
  const teams = elo?.map(t => t.team).sort() ?? []

  const { data: playersData, isLoading, isError } = useQuery({
    queryKey: ["players", selectedTeam],
    queryFn: () => fetchPlayers(selectedTeam, 50),
    enabled: !!selectedTeam,
    retry: false,
    staleTime: 30_000,
  })

  const players = (playersData?.players ?? [])
    .filter(p => position === "Todos" || p.position === position)
    .filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => ((b[sortBy] ?? 0) - (a[sortBy] ?? 0)))

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="card">
        <div className="flex items-center gap-3 mb-5">
          <User className="w-5 h-5 text-cyan" />
          <h2 className="section-title text-xl">JUGADORES</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Team selector */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted">Equipo</label>
            <select value={selectedTeam} onChange={e => setSelectedTeam(e.target.value)} className="select-dark w-full">
              <option value="">Seleccionar equipo...</option>
              {teams.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          {/* Search */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted">Buscar</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Nombre jugador..." className="input-dark pl-8 w-full" />
            </div>
          </div>

          {/* Position filter */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted">Posición</label>
            <div className="flex gap-1">
              {POSITIONS.map(p => (
                <button
                  key={p}
                  onClick={() => setPosition(p)}
                  className={clsx(
                    "flex-1 py-2 text-xs rounded-lg border transition-all",
                    position === p ? "border-cyan/40 bg-cyan/10 text-cyan" : "border-border text-muted hover:text-text"
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Sort */}
          <div className="space-y-1.5">
            <label className="text-xs uppercase tracking-wider text-muted">Ordenar por</label>
            <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)} className="select-dark w-full">
              <option value="goals_per_90">Goles/90</option>
              <option value="xg_per_90">xG/90</option>
              <option value="assists_per_90">Asistencias/90</option>
            </select>
          </div>
        </div>
      </div>

      {/* Status banner */}
      {isError && selectedTeam && (
        <div className="card border-scarlet/20 bg-scarlet/5 text-scarlet text-sm p-4">
          Error cargando jugadores de <strong>{selectedTeam}</strong>. Verifica que el servicio esté activo.
        </div>
      )}
      {!isError && playersData?.data_status !== "available" && selectedTeam && !isLoading && (
        <div className="card border-amber/20 bg-amber/5 text-amber text-sm p-4 space-y-1">
          <p>
            {playersData?.message
              ?? `Sin estadísticas de jugadores para ${selectedTeam}. El ETL sincroniza jugadores semanalmente.`}
          </p>
          {playersData?.last_synced_at && (
            <p className="text-xs opacity-70">
              Última sincronización: {new Date(playersData.last_synced_at).toLocaleString("es-ES")}
            </p>
          )}
        </div>
      )}

      {/* Player cards / table */}
      {!selectedTeam ? (
        <div className="card text-center py-16 text-muted">
          <User className="w-12 h-12 mx-auto mb-3 opacity-20" />
          <p className="text-sm">Selecciona un equipo para ver sus jugadores</p>
        </div>
      ) : (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="section-title text-lg">{selectedTeam} — {players.length} jugadores</h3>
            <Badge variant={playersData?.data_status === "available" ? "green" : "amber"}>
              {playersData?.data_status ?? "cargando"}
            </Badge>
          </div>

          {/* Grid view for players */}
          {players.length > 0 ? (
            <>
              {/* Card grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 mb-6">
                {players.map((player, i) => (
                  <motion.div
                    key={player.name}
                    className="card-hover p-3 text-center space-y-2"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.03 }}
                  >
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan/20 to-amber/20 border border-border flex items-center justify-center mx-auto text-lg font-display text-text">
                      {player.name.slice(0, 2).toUpperCase()}
                    </div>

                    <div>
                      <p className="font-medium text-text text-xs leading-tight">{player.name}</p>
                      <p className="text-xs text-muted">{player.position ?? "—"}</p>
                    </div>

                    <div className="flex gap-1 justify-center flex-wrap">
                      {player.is_injured && <Badge variant="red" size="sm">Lesión</Badge>}
                      {player.is_suspended && <Badge variant="amber" size="sm">Susp.</Badge>}
                      {!player.is_injured && !player.is_suspended && (
                        <Badge variant="green" size="sm">Activo</Badge>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-1 text-center">
                      <div>
                        <p className="font-mono text-xs text-cyan">{player.goals_per_90?.toFixed(2) ?? "—"}</p>
                        <p className="text-[9px] text-muted">G/90</p>
                      </div>
                      <div>
                        <p className="font-mono text-xs text-amber">{player.xg_per_90?.toFixed(2) ?? "—"}</p>
                        <p className="text-[9px] text-muted">xG</p>
                      </div>
                      <div>
                        <p className="font-mono text-xs text-emerald">{player.assists_per_90?.toFixed(2) ?? "—"}</p>
                        <p className="text-[9px] text-muted">A/90</p>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Table view */}
              <div className="overflow-x-auto">
                <table className="table-dark">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Jugador</th>
                      <th>Pos.</th>
                      <th>Goles/90</th>
                      <th>xG/90</th>
                      <th>Asist/90</th>
                      <th>Amarillas/90</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading
                      ? Array.from({ length: 10 }).map((_, i) => <TableRowSkeleton key={i} cols={8} />)
                      : players.map((p, i) => (
                          <tr key={p.name}>
                            <td className="text-muted text-sm">{i + 1}</td>
                            <td className="font-medium">{p.name}</td>
                            <td>
                              <Badge variant={
                                p.position === "FWD" ? "amber" :
                                p.position === "MID" ? "cyan" :
                                p.position === "DEF" ? "green" : "muted"
                              }>{p.position ?? "—"}</Badge>
                            </td>
                            <td className="text-cyan font-mono">{p.goals_per_90?.toFixed(2) ?? "—"}</td>
                            <td className="text-amber font-mono">{p.xg_per_90?.toFixed(2) ?? "—"}</td>
                            <td className="font-mono">{p.assists_per_90?.toFixed(2) ?? "—"}</td>
                            <td className="font-mono">{p.yellow_cards_per_90?.toFixed(2) ?? "—"}</td>
                            <td>
                              <Badge variant={p.is_injured ? "red" : p.is_suspended ? "amber" : "green"}>
                                {p.is_injured ? "Lesión" : p.is_suspended ? "Susp." : "OK"}
                              </Badge>
                            </td>
                          </tr>
                        ))
                    }
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            !isLoading && !isError && (
              <div className="text-center py-12 text-muted">
                <User className="w-10 h-10 mx-auto mb-2 opacity-20" />
                <p className="text-sm">Sin jugadores disponibles para <strong>{selectedTeam}</strong></p>
                <p className="text-xs mt-1">El ETL sincroniza estadísticas de jugadores semanalmente.</p>
                {playersData?.last_synced_at && (
                  <p className="text-xs mt-0.5 opacity-60">
                    Última sync: {new Date(playersData.last_synced_at).toLocaleString("es-ES")}
                  </p>
                )}
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}
