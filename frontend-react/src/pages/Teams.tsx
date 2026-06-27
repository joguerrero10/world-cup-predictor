import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { Users, Search, Shield, Sword, Building2, Calendar, TrendingUp } from "lucide-react"
import { fetchTeams } from "../api/endpoints"
import { PlotlyChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import clsx from "clsx"
import type { TeamDetail } from "../types"
import type { Data } from "plotly.js"

// ─── Competition tabs ─────────────────────────────────────────────────────────

const TABS = [
  { id: "",              label: "Todos",        flag: "🌐", type: undefined },
  { id: "fifa_wc_2026",  label: "Mundial 2026", flag: "🌍", type: "national" as const },
  { id: "ucl",           label: "Champions",    flag: "⭐", type: "club" as const },
  { id: "premier_league", label: "Premier",     flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", type: "club" as const },
  { id: "laliga",        label: "LaLiga",       flag: "🇪🇸", type: "club" as const },
  { id: "bundesliga",    label: "Bundesliga",   flag: "🇩🇪", type: "club" as const },
  { id: "serie_a",       label: "Serie A",      flag: "🇮🇹", type: "club" as const },
  { id: "ligue_1",       label: "Ligue 1",      flag: "🇫🇷", type: "club" as const },
]

// ─── Team logo with initial fallback ─────────────────────────────────────────

function TeamLogo({
  name,
  logo_url,
  size = 36,
  className = "",
}: {
  name: string
  logo_url: string | null
  size?: number
  className?: string
}) {
  const [imgError, setImgError] = useState(false)
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map(w => w[0] ?? "")
    .join("")
    .toUpperCase()

  if (logo_url && !imgError) {
    return (
      <img
        src={logo_url}
        alt={name}
        width={size}
        height={size}
        className={clsx("object-contain", className)}
        onError={() => setImgError(true)}
        loading="lazy"
      />
    )
  }

  return (
    <div
      style={{ width: size, height: size, fontSize: size * 0.3 }}
      className={clsx(
        "rounded-full bg-gradient-to-br from-cyan/20 to-amber/20 border border-border flex items-center justify-center font-display text-text select-none",
        className
      )}
    >
      {initials || "?"}
    </div>
  )
}

// ─── Team card (grid) ─────────────────────────────────────────────────────────

function TeamCard({
  team,
  selected,
  onClick,
  rank,
  index,
}: {
  team: TeamDetail
  selected: boolean
  onClick: () => void
  rank: number
  index: number
}) {
  return (
    <motion.button
      onClick={onClick}
      className={clsx(
        "card text-left p-3 space-y-2 transition-all duration-150 w-full",
        selected ? "border-cyan/40 bg-cyan/5" : "hover:border-border hover:bg-white/5"
      )}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: index * 0.015 }}
    >
      <div className="flex items-center justify-between">
        <TeamLogo name={team.name} logo_url={team.logo_url} size={36} />
        <span className={clsx("font-display text-xs", rank <= 3 ? "text-amber" : "text-muted")}>
          #{rank}
        </span>
      </div>
      <div>
        <p className="font-medium text-text text-xs leading-tight truncate">{team.name}</p>
        <p className="font-display text-lg text-cyan">
          {team.elo_rating?.toFixed(0) ?? "—"}
        </p>
        <p className="text-[10px] text-muted truncate">
          {team.team_type === "national" ? "🌍 Selección" : "🏟️ Club"}{team.country ? ` · ${team.country}` : ""}
        </p>
      </div>
    </motion.button>
  )
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function TeamDetail({ team, maxRating }: { team: TeamDetail; maxRating: number }) {
  const radarData: Data[] = [{
    type: "scatterpolar",
    r: [
      (team.elo_rating ?? 1500) / maxRating,
      (team.elo_attack ?? 1500) / maxRating,
      1 - (team.elo_defense ?? 1500) / maxRating,
      0.65, 0.70, 0.60,
      (team.elo_rating ?? 1500) / maxRating,
    ],
    theta: ["Rating", "Ataque", "Defensa", "Forma", "xG", "Histórico", "Rating"],
    fill: "toself",
    name: team.name,
    line: { color: "#00D4FF", width: 2 },
    fillcolor: "#00D4FF18",
  } as Data]

  const mv = team.market_value_eur
  const mvLabel = mv
    ? mv >= 1e9
      ? `€${(mv / 1e9).toFixed(1)}B`
      : `€${(mv / 1e6).toFixed(0)}M`
    : null

  return (
    <motion.div
      key={team.name}
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="card border-cyan/20">
        <div className="flex items-center gap-3 mb-4">
          <TeamLogo name={team.name} logo_url={team.logo_url} size={56} />
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-xl tracking-wider text-text truncate">{team.name}</h3>
            <div className="flex flex-wrap gap-1 mt-1">
              {team.elo_rank && (
                <Badge variant={team.elo_rank <= 5 ? "amber" : "cyan"}>
                  #{team.elo_rank}
                </Badge>
              )}
              <Badge variant="muted">
                {team.team_type === "national" ? "Selección" : "Club"}
              </Badge>
              {team.competition_name && (
                <Badge variant="muted">{team.competition_name}</Badge>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="stat-card">
            <span className="font-display text-2xl text-cyan">
              {team.elo_rating?.toFixed(0) ?? "—"}
            </span>
            <span className="stat-label">Elo Rating</span>
          </div>
          <div className="stat-card">
            <span className="font-display text-2xl text-text flex items-center justify-center gap-1">
              <Sword className="w-4 h-4 text-amber" />
              {team.elo_attack?.toFixed(0) ?? "—"}
            </span>
            <span className="stat-label">Ataque</span>
          </div>
          <div className="stat-card">
            <span className="font-display text-2xl text-text flex items-center justify-center gap-1">
              <Shield className="w-4 h-4 text-emerald" />
              {team.elo_defense?.toFixed(0) ?? "—"}
            </span>
            <span className="stat-label">Defensa</span>
          </div>
        </div>
      </div>

      {/* Radar */}
      {team.elo_rating && (
        <div className="card">
          <p className="section-label mb-2">Perfil de equipo</p>
          <PlotlyChart
            data={radarData}
            height={240}
            layout={{
              polar: {
                radialaxis: {
                  visible: true, range: [0, 1],
                  gridcolor: "#1E2D40", tickfont: { color: "#64748B", size: 8 },
                },
                angularaxis: { tickfont: { color: "#E2E8F0", size: 10 } },
                bgcolor: "transparent",
              },
              showlegend: false,
              margin: { l: 30, r: 30, t: 20, b: 20 },
            }}
          />
        </div>
      )}

      {/* Metrics */}
      {team.elo_rating && (
        <div className="card space-y-3">
          <p className="section-label">Métricas clave</p>
          {[
            { label: "Rating Elo",     value: team.elo_rating  ?? 0, color: "#00D4FF" },
            { label: "Fuerza ataque",  value: team.elo_attack  ?? 0, color: "#F0B429" },
            { label: "Fuerza defensa", value: team.elo_defense ?? 0, color: "#22C55E" },
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
                  animate={{ width: `${(s.value / maxRating) * 100}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info */}
      <div className="card space-y-2">
        <p className="section-label">Información</p>
        {[
          team.country        && { icon: <span>🌐</span>,         label: "País",          value: team.country },
          team.stadium        && { icon: <Building2 className="w-3.5 h-3.5 text-muted" />, label: "Estadio", value: team.stadium },
          team.founded_year   && { icon: <Calendar className="w-3.5 h-3.5 text-muted" />,  label: "Fundado", value: String(team.founded_year) },
          mvLabel             && { icon: <TrendingUp className="w-3.5 h-3.5 text-muted" />, label: "Valor de mercado", value: mvLabel },
          { icon: <span>🏆</span>, label: "Competición", value: team.competition_name ?? "—" },
        ]
          .filter(Boolean)
          .map((row: any) => (
            <div
              key={row.label}
              className="flex justify-between py-1.5 border-b border-border/30 last:border-0 text-sm"
            >
              <span className="text-muted flex items-center gap-1.5">
                {row.icon} {row.label}
              </span>
              <span className="text-text text-right max-w-[55%] truncate">{row.value}</span>
            </div>
          ))}
      </div>
    </motion.div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function Teams() {
  const [search, setSearch]     = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView]         = useState<"grid" | "list">("grid")
  const [activeTab, setTab]     = useState("")

  const activeComp = TABS.find(t => t.id === activeTab)

  const { data: teams = [], isLoading } = useQuery({
    queryKey: ["teams", activeTab],
    queryFn: () =>
      fetchTeams({
        competition: activeTab || undefined,
        limit: 200,
      }),
    staleTime: 5 * 60_000,
  })

  const filtered = teams.filter(t =>
    t.name.toLowerCase().includes(search.toLowerCase())
  )

  const selectedTeam = teams.find(t => t.name === selected)
  const maxRating = Math.max(...teams.map(t => t.elo_rating ?? 1500), 1500)

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header + controls */}
      <div className="card flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Users className="w-5 h-5 text-cyan shrink-0" />
          <h2 className="section-title text-xl">EQUIPOS</h2>
          {!isLoading && (
            <span className="text-xs text-muted ml-1">({filtered.length})</span>
          )}
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

      {/* Competition tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => { setTab(tab.id); setSelected(null) }}
            className={clsx(
              "shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full font-medium transition-colors",
              activeTab === tab.id
                ? "bg-cyan/15 text-cyan border border-cyan/25"
                : "bg-white/5 text-white/45 hover:text-white/65 hover:bg-white/8 border border-transparent"
            )}
          >
            <span>{tab.flag}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Team list */}
        <div className="lg:col-span-2">
          {view === "grid" ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {isLoading
                ? Array.from({ length: 16 }).map((_, i) => (
                    <div key={i} className="card animate-pulse h-28" />
                  ))
                : filtered.slice(0, 96).map((team, i) => (
                    <TeamCard
                      key={team.name}
                      team={team}
                      rank={team.elo_rank ?? i + 1}
                      index={i}
                      selected={selected === team.name}
                      onClick={() => setSelected(selected === team.name ? null : team.name)}
                    />
                  ))
              }
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="table-dark">
                <thead>
                  <tr>
                    <th>#</th>
                    <th></th>
                    <th>Equipo</th>
                    <th>Tipo</th>
                    <th>Elo</th>
                    <th>Ataque</th>
                    <th>Defensa</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((team, i) => (
                    <tr
                      key={team.name}
                      className={selected === team.name ? "bg-cyan/5 border-cyan/20" : ""}
                    >
                      <td className={clsx("font-display text-lg", (team.elo_rank ?? 99) <= 3 ? "text-amber" : "text-muted")}>
                        {(team.elo_rank ?? 0) <= 3
                          ? ["🥇", "🥈", "🥉"][(team.elo_rank ?? 1) - 1]
                          : team.elo_rank ?? i + 1}
                      </td>
                      <td className="w-10">
                        <TeamLogo name={team.name} logo_url={team.logo_url} size={28} />
                      </td>
                      <td className="font-medium">{team.name}</td>
                      <td>
                        <span className="text-xs text-muted">
                          {team.team_type === "national" ? "🌍 Selecc." : "🏟️ Club"}
                        </span>
                      </td>
                      <td className="text-cyan font-mono">
                        {team.elo_rating?.toFixed(0) ?? "—"}
                      </td>
                      <td className="text-muted font-mono">
                        {team.elo_attack?.toFixed(0) ?? "—"}
                      </td>
                      <td className="text-muted font-mono">
                        {team.elo_defense?.toFixed(0) ?? "—"}
                      </td>
                      <td>
                        <button
                          onClick={() => setSelected(selected === team.name ? null : team.name)}
                          className="btn-ghost py-1 px-2 text-xs"
                        >
                          {selected === team.name ? "Cerrar" : "Ver"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div className="space-y-4">
          <AnimatePresence mode="wait">
            {selectedTeam ? (
              <TeamDetail
                key={selectedTeam.name}
                team={selectedTeam}
                maxRating={maxRating}
              />
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="card text-center py-12 text-muted"
              >
                <Users className="w-10 h-10 mx-auto mb-3 opacity-20" />
                <p className="text-sm">Selecciona un equipo para ver su perfil</p>
                {activeComp && activeComp.id && (
                  <p className="text-xs text-muted/60 mt-1">{activeComp.label}</p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
