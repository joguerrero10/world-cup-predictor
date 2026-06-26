import { TrendingUp } from "lucide-react"
import { Badge } from "../components/ui/Badge"

const MOCK_TRANSFERS = [
  { player: "Kylian Mbappé",      from: "Real Madrid",       to: "Al-Hilal",      fee: "200M", type: "permanent" },
  { player: "Erling Haaland",     from: "Manchester City",   to: "Real Madrid",   fee: "180M", type: "permanent" },
  { player: "Vinicius Jr",        from: "Real Madrid",       to: "Real Madrid",   fee: "—",    type: "renewal" },
  { player: "Jude Bellingham",    from: "Real Madrid",       to: "Barcelona",     fee: "160M", type: "permanent" },
  { player: "Pedri",              from: "Barcelona",         to: "Barcelona",     fee: "—",    type: "renewal" },
]

export function Transfers() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="card flex items-center gap-3">
        <TrendingUp className="w-5 h-5 text-cyan" />
        <div>
          <h2 className="section-title text-xl">MERCADO DE FICHAJES</h2>
          <p className="text-xs text-muted">Transferencias y movimientos de mercado</p>
        </div>
      </div>

      <div className="card border-amber/20 bg-amber/5 text-amber text-sm p-4">
        Los datos de transferencias se cargarán desde la base de datos cuando estén disponibles vía ETL.
        Los movimientos mostrados son de ejemplo ilustrativo.
      </div>

      <div className="card">
        <p className="section-label mb-3">Fichajes recientes</p>
        <table className="table-dark">
          <thead>
            <tr>
              <th>Jugador</th><th>Origen</th><th>Destino</th><th>Tarifa</th><th>Tipo</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_TRANSFERS.map((t, i) => (
              <tr key={i}>
                <td className="font-medium text-text">{t.player}</td>
                <td className="text-muted">{t.from}</td>
                <td className="text-cyan">{t.to}</td>
                <td className="font-mono text-amber">{t.fee}</td>
                <td>
                  <Badge variant={t.type === "permanent" ? "cyan" : t.type === "renewal" ? "green" : "amber"}>
                    {t.type}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
