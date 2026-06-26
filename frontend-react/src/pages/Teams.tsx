import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { Users, Search, Shield, Sword } from "lucide-react"
import { fetchEloRankings } from "../api/endpoints"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import clsx from "clsx"
import type { Data } from "plotly.js"

export function Teams() {
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<"grid" | "list">("grid")

  const { data: elo, isLoading } = useQuery({
    queryKey: ["elo-rankings"],
    queryFn: fetchEloRankings,
    staleTime: 60_000,
  })

  const filtered = (elo ?? []).filter(t =>
    t.team.toLowerCase().includes(search.toLowerCase())
  )

  const selectedTeam = elo?.find(t => t.team === selected)
  const maxRating = elo?.[0]?.rating ?? 2000

  // Radar for selected team
  const radarData: Data[] = selectedTeam ? [{
    type: "scatterpolar",
    r: [
      selectedTeam.rating / maxRating,
      selectedTeam.attack / maxRating,
      1 - (selectedTeam.defense / maxRating),
      0.65, 0.70, 0.60,
      selectedTeam.rating / maxRating,
    ],
    theta: ["Rating", "Ataque", "Defensa", "Forma", "xG", "Histórico", "Rating"],
    fill: "toself",
    name: selectedTeam.team,
    line: { color: "#00D4FF", width: 2 },
    fillcolor: "#00D4FF18",
  } as Data] : []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Controls */}
      <div className="card flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 flex-1">
          <Users className="w-5 h-5 text-cyan shrink-0" />
          <h2 className="section-title text-xl">EQUIPOS</h2>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar equipo..."
            className="input-dark pl-8 w-48"
          />
        </div>
        <div className="flex gap-1">
          {(["grid", "list"] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={clsx("btn-ghost py-1.5 px-3 text-xs", view === v && "border-cyan/50 text-cyan")}
            >
              {v === "grid" ? "⊞ Grid" : "≡ Lista"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Team list */}
        <div className={clsx("lg:col-span-2", view === "list" ? "space-y-1" : "")}>
          {view === "grid" ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {isLoading
                ? Array.from({ length: 16 }).map((_, i) => (
                    <div key={i} className="card animate-pulse h-24" />
                  ))
                : filtered.slice(0, 48).map((team, i) => (
                    <motion.button
                      key={team.team}
                      onClick={() => setSelected(selected === team.team ? null : team.team)}
                      className={clsx(
                        "card text-left p-3 space-y-2 transition-all duration-150 w-full",
                        selected === team.team
                          ? "border-cyan/40 bg-cyan/5"
                          : "hover:border-border hover:bg-white/5"
                      )}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: i * 0.02 }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-cyan/20 to-amber/20 border border-border flex items-center justify-center text-sm font-display text-text">
                          {team.team.slice(0, 2).toUpperCase()}
                        </div>
                        <span className={clsx("font-display text-xs", team.rank <= 3 ? "text-amber" : "text-muted")}>
                          #{team.rank}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-text text-xs leading-tight truncate">{team.team}</p>
                        <p className="font-display text-lg text-cyan">{team.rating.toFixed(0)}</p>
                      </div>
                    </motion.button>
                  ))
              }
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="table-dark">
                <thead>
                  <tr>
                    <th>#</th><th>Equipo</th><th>Elo</th><th>Ataque</th><th>Defensa</th><th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((team) => (
                    <tr key={team.team} className={selected === team.team ? "bg-cyan/5 border-cyan/20" : ""}>
                      <td className={clsx("font-display text-lg", team.rank <= 3 ? "text-amber" : "text-muted")}>
                        {team.rank <= 3 ? ["🥇","🥈","🥉"][team.rank - 1] : team.rank}
                      </td>
                      <td className="font-medium">{team.team}</td>
                      <td className="text-cyan font-mono">{team.rating.toFixed(0)}</td>
                      <td className="text-muted font-mono">{team.attack.toFixed(0)}</td>
                      <td className="text-muted font-mono">{team.defense.toFixed(0)}</td>
                      <td>
                        <button
                          onClick={() => setSelected(selected === team.team ? null : team.team)}
                          className="btn-ghost py-1 px-2 text-xs"
                        >
                          {selected === team.team ? "Cerrar" : "Ver"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Team detail panel */}
        <div className="space-y-4">
          {selectedTeam ? (
            <motion.div
              key={selectedTeam.team}
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-4"
            >
              {/* Team header */}
              <div className="card border-cyan/20">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan/20 to-amber/20 border-2 border-cyan/30 flex items-center justify-center text-2xl font-display text-cyan">
                    {selectedTeam.team.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="font-display text-2xl tracking-wider text-text">{selectedTeam.team}</h3>
                    <Badge variant={selectedTeam.rank <= 5 ? "amber" : "cyan"}>Rank #{selectedTeam.rank}</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="stat-card">
                    <span className="font-display text-2xl text-cyan">{selectedTeam.rating.toFixed(0)}</span>
                    <span className="stat-label">Elo Rating</span>
                  </div>
                  <div className="stat-card">
                    <span className="font-display text-2xl text-text flex items-center justify-center gap-1">
                      <Sword className="w-4 h-4 text-amber" />{selectedTeam.attack.toFixed(0)}
                    </span>
                    <span className="stat-label">Ataque</span>
                  </div>
                  <div className="stat-card">
                    <span className="font-display text-2xl text-text flex items-center justify-center gap-1">
                      <Shield className="w-4 h-4 text-emerald" />{selectedTeam.defense.toFixed(0)}
                    </span>
                    <span className="stat-label">Defensa</span>
                  </div>
                </div>
              </div>

              {/* Radar */}
              <div className="card">
                <p className="section-label mb-2">Perfil de equipo</p>
                <PlotlyChart
                  data={radarData}
                  height={260}
                  layout={{
                    polar: {
                      radialaxis: { visible: true, range: [0, 1], gridcolor: "#1E2D40", tickfont: { color: "#64748B", size: 8 } },
                      angularaxis: { tickfont: { color: "#E2E8F0", size: 10 } },
                      bgcolor: "transparent",
                    },
                    showlegend: false,
                    margin: { l: 30, r: 30, t: 20, b: 20 },
                  }}
                />
              </div>

              {/* Stats */}
              <div className="card space-y-3">
                <p className="section-label">Métricas clave</p>
                {[
                  { label: "Rating Elo",    value: selectedTeam.rating,  max: maxRating, color: "#00D4FF" },
                  { label: "Fuerza ataque", value: selectedTeam.attack,  max: maxRating, color: "#F0B429" },
                  { label: "Fuerza defensa",value: selectedTeam.defense, max: maxRating, color: "#22C55E" },
                ].map(s => (
                  <div key={s.label} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted">{s.label}</span>
                      <span className="font-mono text-text">{s.value.toFixed(0)}</span>
                    </div>
                    <div className="h-1.5 bg-border rounded overflow-hidden">
                      <motion.div
                        className="h-full rounded"
                        style={{ backgroundColor: s.color }}
                        initial={{ width: 0 }}
                        animate={{ width: `${(s.value / s.max) * 100}%` }}
                        transition={{ duration: 0.6 }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="card space-y-2">
                <p className="section-label">Info adicional</p>
                {[
                  { label: "Formación favorita", value: "4-3-3" },
                  { label: "Liga",               value: "Internacional" },
                  { label: "Historial mundial",  value: "Disponible" },
                ].map(r => (
                  <div key={r.label} className="flex justify-between py-1.5 border-b border-border/30 last:border-0 text-sm">
                    <span className="text-muted">{r.label}</span>
                    <span className="text-text">{r.value}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          ) : (
            <div className="card text-center py-12 text-muted">
              <Users className="w-10 h-10 mx-auto mb-3 opacity-20" />
              <p className="text-sm">Selecciona un equipo para ver su perfil</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
