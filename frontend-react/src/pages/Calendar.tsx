import { Calendar as CalIcon } from "lucide-react"
import { Badge } from "../components/ui/Badge"

const UPCOMING = [
  { date: "2026-07-11", home: "Argentina", away: "France",    comp: "FIFA World Cup 2026", round: "Final" },
  { date: "2026-07-07", home: "Brazil",    away: "Germany",   comp: "FIFA World Cup 2026", round: "Semifinal" },
  { date: "2026-07-07", home: "Argentina", away: "Spain",     comp: "FIFA World Cup 2026", round: "Semifinal" },
  { date: "2026-06-30", home: "England",   away: "Italy",     comp: "FIFA World Cup 2026", round: "Cuartos" },
  { date: "2026-06-29", home: "France",    away: "Portugal",  comp: "FIFA World Cup 2026", round: "Cuartos" },
]

export function Calendar() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="card flex items-center gap-3">
        <CalIcon className="w-5 h-5 text-cyan" />
        <div>
          <h2 className="section-title text-xl">CALENDARIO</h2>
          <p className="text-xs text-muted">Próximos partidos y competiciones</p>
        </div>
      </div>

      <div className="card border-amber/20 bg-amber/5 text-amber text-sm p-4">
        El calendario detallado se cargará cuando estén disponibles los datos de fixtures en la base de datos.
        Los partidos mostrados son de ejemplo para el Mundial 2026.
      </div>

      <div className="space-y-3">
        {UPCOMING.map((match, i) => (
          <div key={i} className="card-hover flex items-center gap-4 py-3">
            <div className="w-14 text-center shrink-0">
              <p className="text-xs text-muted">{new Date(match.date).toLocaleDateString("es", { month: "short", day: "numeric" })}</p>
              <p className="text-xs text-cyan">{new Date(match.date).getFullYear()}</p>
            </div>
            <div className="flex-1 flex items-center gap-3">
              <span className="font-medium text-text text-sm">{match.home}</span>
              <span className="font-display text-muted tracking-wider">vs</span>
              <span className="font-medium text-text text-sm">{match.away}</span>
            </div>
            <div className="flex gap-2">
              <Badge variant="cyan">{match.round}</Badge>
              <Badge variant="muted">{match.comp.split(" ").slice(0,2).join(" ")}</Badge>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
