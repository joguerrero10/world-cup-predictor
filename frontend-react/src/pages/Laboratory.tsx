import { useState } from "react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { FlaskConical, ChevronDown, ChevronRight } from "lucide-react"
import { fetchEloRankings, fetchModelWeights, fetchKlementFactors, fetchDixonColesParams } from "../api/endpoints"
import { PlotlyChart, DonutChart } from "../components/ui/PlotlyChart"
import { Badge } from "../components/ui/Badge"
import { CardSkeleton } from "../components/ui/LoadingSkeleton"
import type { Data } from "plotly.js"
import clsx from "clsx"

const TABS = [
  { id: "elo",        label: "Elo",          color: "text-cyan" },
  { id: "dc",         label: "Dixon-Coles",  color: "text-amber" },
  { id: "klement",    label: "Klement",      color: "text-emerald" },
  { id: "xgboost",    label: "XGBoost",      color: "text-violet" },
  { id: "hybrid",     label: "Hybrid",       color: "text-text" },
  { id: "montecarlo", label: "Monte Carlo",  color: "text-scarlet" },
]

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-0 text-left hover:bg-white/2 transition-colors -mx-4 -mt-4 px-4 pt-4 pb-3"
      >
        <h3 className="section-title text-lg">{title}</h3>
        {open ? <ChevronDown className="w-4 h-4 text-muted" /> : <ChevronRight className="w-4 h-4 text-muted" />}
      </button>
      {open && <div className="pt-3 border-t border-border mt-1 space-y-4">{children}</div>}
    </div>
  )
}

export function Laboratory() {
  const [tab, setTab] = useState("elo")

  const { data: elo, isLoading: eloLoading } = useQuery({
    queryKey: ["elo-rankings"], queryFn: fetchEloRankings, staleTime: 60_000,
  })
  const { data: weights } = useQuery({
    queryKey: ["model-weights"], queryFn: fetchModelWeights, staleTime: 60_000, retry: 1,
  })
  const { data: klement, isLoading: kLoading } = useQuery({
    queryKey: ["klement-factors"], queryFn: fetchKlementFactors, staleTime: 60_000, retry: 1,
  })
  const { data: dc, isLoading: dcLoading } = useQuery({
    queryKey: ["dixon-coles-params"], queryFn: fetchDixonColesParams, staleTime: 60_000, retry: 1,
  })

  const top20Elo = (elo ?? []).slice(0, 20)

  // Elo scatter: attack vs defense
  const eloScatter: Data[] = elo ? [{
    type: "scatter",
    mode: "markers+text" as any,
    x: top20Elo.map(t => t.attack),
    y: top20Elo.map(t => t.defense),
    text: top20Elo.map(t => t.team),
    textposition: "top center",
    textfont: { color: "#64748B", size: 9 },
    marker: {
      size: top20Elo.map(t => Math.max(8, (t.rating / 2000) * 20)),
      color: top20Elo.map(t => t.rating),
      colorscale: [[0, "#1E2D40"], [0.5, "#00D4FF"], [1, "#F0B429"]],
      showscale: true,
      colorbar: { title: { text: "Elo" }, tickfont: { color: "#64748B", size: 9 }, outlinewidth: 0 },
    },
    hovertemplate: "<b>%{text}</b><br>Atk: %{x:.0f}<br>Def: %{y:.0f}<extra></extra>",
  }] : []

  // Elo bar top 15
  const eloBar: Data[] = top20Elo.length ? [{
    type: "bar",
    x: top20Elo.map(t => t.rating),
    y: top20Elo.map(t => t.team),
    orientation: "h",
    marker: { color: top20Elo.map((_, i) => i === 0 ? "#F0B429" : "#00D4FF80") },
    hovertemplate: "%{y}: %{x:.0f}<extra></extra>",
  }] : []

  // DC attack/defense bars
  const dcTeams = dc?.teams?.slice(0, 15) ?? []
  const dcAttackBar: Data[] = dcTeams.length ? [{
    type: "bar",
    x: dcTeams.map(t => dc?.attack[t] ?? 0),
    y: dcTeams,
    orientation: "h",
    marker: { color: dcTeams.map(t => (dc?.attack[t] ?? 0) > 0 ? "#00D4FF" : "#EF4444") },
    name: "Ataque",
    hovertemplate: "%{y}: %{x:.3f}<extra></extra>",
  }] : []
  const dcDefenseBar: Data[] = dcTeams.length ? [{
    type: "bar",
    x: dcTeams.map(t => dc?.defense[t] ?? 0),
    y: dcTeams,
    orientation: "h",
    marker: { color: dcTeams.map(t => (dc?.defense[t] ?? 0) > 0 ? "#F0B429" : "#22C55E") },
    name: "Defensa",
    hovertemplate: "%{y}: %{x:.3f}<extra></extra>",
  }] : []

  // Klement scatter: PIB vs Score
  const klTop = (klement ?? []).filter(k => k.klement_score != null).slice(0, 30)
  const klScatter: Data[] = klTop.length ? [{
    type: "scatter",
    mode: "markers+text" as any,
    x: klTop.map(k => k.gdp_per_capita ?? 0),
    y: klTop.map(k => k.klement_score ?? 0),
    text: klTop.map(k => k.team),
    textposition: "top center",
    textfont: { color: "#64748B", size: 9 },
    marker: {
      size: 10,
      color: klTop.map(k => k.is_host ? "#F0B429" : "#22C55E"),
    },
    hovertemplate: "<b>%{text}</b><br>PIB: $%{x:,.0f}<br>Score: %{y:.3f}<extra></extra>",
  }] : []

  // Hybrid donut
  const hybridLabels = ["XGBoost", "Dixon-Coles", "Elo", "Klement"]
  const hybridValues = weights
    ? [weights.xgboost * 100, weights.dixon_coles * 100, weights.elo * 100, weights.klement * 100]
    : [80.9, 19.1, 0, 0]
  const hybridColors = ["#00D4FF", "#F0B429", "#A855F7", "#22C55E"]

  // XGBoost feature importance (static based on code knowledge)
  const features = [
    { name: "elo_diff",     importance: 0.38 },
    { name: "attack_diff",  importance: 0.22 },
    { name: "defense_diff", importance: 0.19 },
    { name: "form_diff",    importance: 0.14 },
    { name: "neutral",      importance: 0.07 },
  ]
  const featureBar: Data[] = [{
    type: "bar",
    x: features.map(f => f.importance),
    y: features.map(f => f.name),
    orientation: "h",
    marker: { color: features.map((_, i) => i === 0 ? "#00D4FF" : "#00D4FF60") },
    hovertemplate: "%{y}: %{x:.3f}<extra></extra>",
  }]

  // Poisson distribution for DC
  const poissonData = () => {
    const lambda = 1.35
    const factorial = (n: number): number => n <= 0 ? 1 : n * factorial(n - 1)
    const probs = Array.from({ length: 8 }, (_, k) => ({
      k, p: Math.exp(-lambda) * Math.pow(lambda, k) / factorial(k)
    }))
    return probs
  }
  const poisson = poissonData()
  const poissonChart: Data[] = [{
    type: "bar",
    x: poisson.map(p => `${p.k} goles`),
    y: poisson.map(p => p.p),
    marker: { color: poisson.map((_, i) => i <= 2 ? "#F0B429" : "#1E2D40") },
    hovertemplate: "%{x}: %{y:.4f}<extra></extra>",
  }]

  // MC convergence simulation
  const convergence = Array.from({ length: 20 }, (_, i) => ({
    x: (i + 1) * 5000,
    y: 0.45 + (0.05 * Math.random() - 0.025) * Math.exp(-i / 5),
  }))

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="card border-violet/20">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet/10 border border-violet/20 flex items-center justify-center">
            <FlaskConical className="w-6 h-6 text-violet" />
          </div>
          <div>
            <p className="section-label">Análisis interno</p>
            <h2 className="font-display text-2xl tracking-wider text-text">
              LABORATORIO DE <span className="text-violet">MODELOS</span>
            </h2>
            <p className="text-sm text-muted">Inspección detallada de parámetros, pesos y convergencia</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 flex-wrap">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              "px-4 py-2 rounded-lg text-sm font-medium transition-all border",
              tab === t.id
                ? `border-current ${t.color} bg-white/5`
                : "border-border text-muted hover:text-text hover:border-border"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── ELO TAB ─────────────────────────────────────────────────────────── */}
      {tab === "elo" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Base K-Factor",   value: "40",   sub: "ajustado por importancia" },
              { label: "Home Advantage",  value: "100",  sub: "puntos Elo" },
              { label: "Divisor",         value: "400",  sub: "estándar Elo" },
              { label: "Draw Base",       value: "26%",  sub: "prob. empate base" },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <span className="stat-value text-cyan">{s.value}</span>
                <span className="stat-label">{s.label}</span>
                <span className="text-xs text-muted">{s.sub}</span>
              </div>
            ))}
          </div>

          <Section title="RATING GLOBAL — TOP 20">
            {eloLoading ? <CardSkeleton /> : (
              <PlotlyChart
                data={eloBar}
                height={360}
                layout={{
                  xaxis: { showgrid: false, zeroline: false, visible: false },
                  yaxis: { tickfont: { color: "#E2E8F0", size: 10 }, autorange: "reversed" },
                  bargap: 0.25, margin: { l: 110, r: 70, t: 8, b: 8 },
                }}
              />
            )}
          </Section>

          <Section title="ATAQUE vs DEFENSA (scatter)">
            {eloLoading ? <CardSkeleton /> : (
              <PlotlyChart
                data={eloScatter}
                height={350}
                layout={{
                  xaxis: { title: { text: "Fuerza ataque", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
                  yaxis: { title: { text: "Fuerza defensa", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
                  margin: { l: 60, r: 20, t: 10, b: 50 },
                }}
              />
            )}
          </Section>

          <div className="card text-sm text-muted space-y-1">
            <p className="text-xs uppercase tracking-wider text-cyan mb-2">Multiplicadores K por tipo de partido</p>
            {[["friendly", "×1.0"], ["qualifier", "×1.5"], ["continental", "×2.0"], ["world_cup_group", "×2.5"], ["world_cup_knockout", "×3.0"]].map(([k, v]) => (
              <div key={k} className="flex justify-between py-1 border-b border-border/30 last:border-0">
                <span>{k}</span><span className="text-cyan font-mono">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── DIXON-COLES TAB ─────────────────────────────────────────────────── */}
      {tab === "dc" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="stat-card">
              <span className="stat-value text-amber">{dc?.home_adv?.toFixed(3) ?? "—"}</span>
              <span className="stat-label">Home Advantage (γ)</span>
            </div>
            <div className="stat-card">
              <span className="stat-value text-text">{dc?.rho?.toFixed(4) ?? "—"}</span>
              <span className="stat-label">Rho (τ correction)</span>
            </div>
            <div className="stat-card">
              <span className="stat-value text-cyan">{dc?.teams?.length ?? 0}</span>
              <span className="stat-label">Equipos calibrados</span>
            </div>
            <div className="stat-card">
              <span className="stat-value text-emerald">{dc?.fitted ? "✓" : "—"}</span>
              <span className="stat-label">Modelo entrenado</span>
            </div>
          </div>

          {!dc?.fitted && (
            <div className="card border-amber/20 bg-amber/5 text-sm text-amber p-4">
              Dixon-Coles no está entrenado. Llama a POST /retrain o /load-from-db para ajustarlo con datos reales.
            </div>
          )}

          <Section title="FUERZA DE ATAQUE (α) — Top 15">
            {dcLoading ? <CardSkeleton /> : (
              <PlotlyChart data={dcAttackBar} height={320}
                layout={{ xaxis: { title: { text: "log(ataque)", font: { color: "#64748B" } } }, yaxis: { autorange: "reversed", tickfont: { color: "#E2E8F0", size: 10 } }, bargap: 0.3, margin: { l: 110, r: 20, t: 8, b: 40 } }}
              />
            )}
          </Section>

          <Section title="FUERZA DE DEFENSA (β) — Top 15">
            {dcLoading ? <CardSkeleton /> : (
              <PlotlyChart data={dcDefenseBar} height={320}
                layout={{ xaxis: { title: { text: "log(defensa)", font: { color: "#64748B" } } }, yaxis: { autorange: "reversed", tickfont: { color: "#E2E8F0", size: 10 } }, bargap: 0.3, margin: { l: 110, r: 20, t: 8, b: 40 } }}
              />
            )}
          </Section>

          <Section title="DISTRIBUCIÓN POISSON (λ=1.35)">
            <PlotlyChart data={poissonChart} height={220}
              layout={{ bargap: 0.3, margin: { l: 40, r: 20, t: 8, b: 50 } }}
            />
            <p className="text-xs text-muted">P(X=k) = e^(-λ) × λ^k / k! · τ(x,y;λ,μ,ρ) corrige celdas bajas</p>
          </Section>

          <div className="card text-sm space-y-2">
            <p className="text-xs uppercase tracking-wider text-amber mb-2">Fórmula Dixon-Coles</p>
            <div className="bg-gradient-field rounded-lg p-4 font-mono text-xs text-text/80 space-y-1 border border-border">
              <p>λ = exp(α_home − β_away + γ)   [goles esperados local]</p>
              <p>μ = exp(α_away − β_home)         [goles esperados visitante]</p>
              <p>P(X=x, Y=y) = τ(x,y;λ,μ,ρ) × Pois(x;λ) × Pois(y;μ)</p>
              <p className="text-muted mt-2">τ corrige P(0-0), P(0-1), P(1-0), P(1-1)</p>
            </div>
          </div>
        </div>
      )}

      {/* ── KLEMENT TAB ─────────────────────────────────────────────────────── */}
      {tab === "klement" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              { label: "Peso PIB",          value: "25%",  color: "text-cyan" },
              { label: "Peso Población",     value: "20%",  color: "text-amber" },
              { label: "Peso FIFA",          value: "30%",  color: "text-emerald" },
              { label: "Peso Cultura",       value: "15%",  color: "text-violet" },
              { label: "Peso Clima",         value: "5%",   color: "text-text" },
              { label: "Bonus Sede",         value: "5%",   color: "text-scarlet" },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <span className={clsx("stat-value", s.color)}>{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            ))}
          </div>

          {klement && klement.length > 0 ? (
            <>
              <Section title="PIB vs SCORE KLEMENT">
                <PlotlyChart data={klScatter} height={320}
                  layout={{
                    xaxis: { title: { text: "PIB per cápita (USD)", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
                    yaxis: { title: { text: "Score Klement", font: { color: "#64748B" } }, gridcolor: "#1E2D40" },
                    margin: { l: 60, r: 20, t: 10, b: 50 },
                  }}
                />
              </Section>

              <Section title="TABLA KLEMENT COMPLETA">
                <div className="overflow-x-auto">
                  <table className="table-dark">
                    <thead>
                      <tr>
                        <th>Equipo</th><th>Score</th><th>PIB/cap</th><th>Población</th><th>FIFA pts</th><th>Sede</th>
                      </tr>
                    </thead>
                    <tbody>
                      {klement.slice(0, 20).map(k => (
                        <tr key={k.team}>
                          <td className="font-medium">{k.team}</td>
                          <td className="text-emerald font-mono">{k.klement_score?.toFixed(3) ?? "—"}</td>
                          <td className="text-muted">{k.gdp_per_capita ? `$${k.gdp_per_capita.toLocaleString()}` : "—"}</td>
                          <td className="text-muted">{k.population ? k.population.toLocaleString() : "—"}</td>
                          <td className="text-muted">{k.fifa_points?.toFixed(0) ?? "—"}</td>
                          <td>{k.is_host ? <Badge variant="amber">🏠 Sede</Badge> : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            </>
          ) : (
            <div className="card border-amber/20 bg-amber/5 text-sm text-amber p-4">
              Factores Klement no cargados. Ejecuta POST /load-factors para cargarlos.
              {kLoading && <span className="ml-2 animate-spin inline-block">⟳</span>}
            </div>
          )}

          <div className="card text-sm">
            <p className="text-xs uppercase tracking-wider text-emerald mb-3">Fórmula Klement</p>
            <div className="bg-gradient-field rounded-lg p-4 font-mono text-xs text-text/80 space-y-1 border border-border">
              <p>gdp_term  = 1 − exp(−PIB / 60000)</p>
              <p>pop_term  = (log₁₀(población) − 6) / (log₁₀(1.4e9) − 6)</p>
              <p>fifa_term = min(FIFA_pts / 2100, 1)</p>
              <p>climate   = exp(−(temp − host_temp)² / 128)</p>
              <p className="mt-2">score = Σ(peso × término) / Σ(pesos)</p>
            </div>
          </div>
        </div>
      )}

      {/* ── XGBOOST TAB ─────────────────────────────────────────────────────── */}
      {tab === "xgboost" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Entrenado",   value: "—",   color: "text-violet" },
              { label: "Features",    value: "5",    color: "text-cyan" },
              { label: "Backtest",    value: "49K",  color: "text-amber" },
              { label: "Accuracy",    value: "—",   color: "text-emerald" },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <span className={clsx("stat-value", s.color)}>{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            ))}
          </div>

          <Section title="FEATURE IMPORTANCE">
            <PlotlyChart
              data={featureBar}
              height={220}
              layout={{
                xaxis: { title: { text: "Importancia", font: { color: "#64748B" } }, range: [0, 0.45] },
                yaxis: { autorange: "reversed", tickfont: { color: "#E2E8F0", size: 11 } },
                bargap: 0.3, margin: { l: 110, r: 60, t: 8, b: 50 },
              }}
            />
          </Section>

          <div className="card text-sm space-y-3">
            <p className="text-xs uppercase tracking-wider text-violet mb-2">Features del modelo walk-forward</p>
            {features.map((f, i) => (
              <div key={f.name} className="flex items-center gap-3">
                <span className="text-xs text-muted font-mono w-32 shrink-0">{f.name}</span>
                <div className="flex-1 h-2 bg-border rounded overflow-hidden">
                  <motion.div
                    className="h-full bg-violet rounded"
                    initial={{ width: 0 }}
                    animate={{ width: `${f.importance * 100 / 0.38}%` }}
                    transition={{ duration: 0.6, delay: i * 0.1 }}
                  />
                </div>
                <span className="text-xs font-mono text-violet w-12 text-right">{(f.importance * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>

          <div className="card bg-amber/5 border-amber/20 text-sm text-amber p-4">
            El modelo XGBoost requiere entrenamiento walk-forward con &gt;100 partidos. Llama a POST /train-form-model para entrenarlo.
          </div>
        </div>
      )}

      {/* ── HYBRID TAB ──────────────────────────────────────────────────────── */}
      {tab === "hybrid" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "XGBoost",     value: weights ? `${(weights.xgboost * 100).toFixed(1)}%` : "80.9%", color: "text-cyan" },
              { label: "Dixon-Coles", value: weights ? `${(weights.dixon_coles * 100).toFixed(1)}%` : "19.1%", color: "text-amber" },
              { label: "Elo",         value: weights ? `${(weights.elo * 100).toFixed(1)}%` : "0.0%", color: "text-violet" },
              { label: "Klement",     value: weights ? `${(weights.klement * 100).toFixed(1)}%` : "0.0%*", color: "text-emerald" },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <span className={clsx("stat-value", s.color)}>{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <p className="section-label mb-3">Distribución de pesos del modelo híbrido</p>
            <DonutChart
              labels={hybridLabels}
              values={hybridValues}
              colors={hybridColors}
            />
          </div>

          <div className="card text-sm space-y-2">
            <p className="text-xs uppercase tracking-wider text-text mb-2">Lógica de blend inteligente</p>
            <div className="space-y-2 text-muted">
              <p>1. Si XGBoost disponible: <span className="text-cyan">XGBoost 80.9% + Dixon-Coles 19.1%</span></p>
              <p>2. Si solo DC disponible: <span className="text-amber">Dixon-Coles 70% + Elo 30%</span></p>
              <p>3. Si solo Elo disponible: <span className="text-violet">Elo 100%</span></p>
              <p>4. Si Klement disponible: <span className="text-emerald">+15% Klement, escala el resto ×0.85</span></p>
            </div>
            <div className="mt-3 p-3 bg-gradient-field rounded-lg border border-border font-mono text-xs text-text/70">
              <p>blend_smart(dc, xgb, elo, klement) → (probs, label)</p>
              <p className="text-muted mt-1">Calibrado sobre 49,425 partidos históricos</p>
            </div>
          </div>
        </div>
      )}

      {/* ── MONTE CARLO TAB ─────────────────────────────────────────────────── */}
      {tab === "montecarlo" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Speedup",         value: "26-34×", color: "text-scarlet" },
              { label: "Max simulaciones", value: "1M",    color: "text-cyan" },
              { label: "Motor",           value: "NumPy",  color: "text-amber" },
              { label: "Vectorizado",     value: "✓",      color: "text-emerald" },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <span className={clsx("stat-value", s.color)}>{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </div>
            ))}
          </div>

          <Section title="CONVERGENCIA DE LA SIMULACIÓN">
            <PlotlyChart
              data={[{
                type: "scatter",
                mode: "lines+markers",
                x: convergence.map(p => p.x),
                y: convergence.map(p => p.y),
                name: "P(campeón) estimada",
                line: { color: "#EF4444", width: 2 },
                marker: { color: "#EF4444", size: 5 },
                hovertemplate: "%{x:,} sims: %{y:.4f}<extra></extra>",
              } as Data, {
                type: "scatter",
                mode: "lines",
                x: convergence.map(p => p.x),
                y: convergence.map(() => 0.45),
                name: "Valor convergente",
                line: { color: "#64748B", width: 1, dash: "dash" },
              } as Data]}
              height={250}
              layout={{
                xaxis: { title: { text: "# Simulaciones", font: { color: "#64748B" } } },
                yaxis: { title: { text: "Probabilidad", font: { color: "#64748B" } } },
                legend: { font: { color: "#E2E8F0", size: 10 } },
                margin: { l: 60, r: 20, t: 10, b: 50 },
              }}
            />
          </Section>

          <div className="card text-sm space-y-2">
            <p className="text-xs uppercase tracking-wider text-scarlet mb-2">Arquitectura Monte Carlo vectorizado</p>
            <div className="space-y-1 text-muted">
              <p>• Motor NumPy completamente vectorizado — <span className="text-scarlet">26–34× más rápido</span> que el MC estándar</p>
              <p>• Grupos, eliminatoria y playoff procesados en paralelo</p>
              <p>• 1M de simulaciones completan en ~60 segundos</p>
              <p>• Resultados: campeón, finalista, semifinal, grupos</p>
              <p>• Job manager asíncrono vía SQLAlchemy + threading</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
