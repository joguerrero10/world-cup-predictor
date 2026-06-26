// ─── API Types ───────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string
  teams_loaded: number
  dc_ready: boolean
  form_model_ready: boolean
  klement_factors_loaded: number
}

export interface EloTeam {
  rank: number
  team: string
  rating: number
  attack: number
  defense: number
}

export interface MatchPrediction {
  home: string
  away: string
  home_win: number
  draw: number
  away_win: number
  source: string
  most_likely_score: [number, number] | null
  over_2_5: number | null
  under_2_5: number | null
  btts_yes: number | null
  btts_no: number | null
}

export interface TournamentProbs {
  competition_id: string
  n_sims: number
  champion: Record<string, number>
  finalist: Record<string, number>
  semifinalist: Record<string, number>
  group_qualified: Record<string, number>
}

export interface SimulationJobStatus {
  id: number
  status: "queued" | "running" | "completed" | "failed"
  competition_id: string
  n_sims: number
  model_name: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  error_message: string | null
}

export interface SimulationJobResult extends SimulationJobStatus {
  result: TournamentProbs | null
}

export interface LeagueTableEntry {
  position: number
  team: string
  played: number
  pts: number
  gf: number
  ga: number
  gd: number
  champion_prob: number
  top4_prob: number
  relegated_prob: number
}

export interface LeagueTable {
  competition_id: string
  n_sims: number
  table: LeagueTableEntry[]
  position_distribution: Record<string, number[]>
}

export interface Competition {
  id: string
  name: string
  competition_type: "league" | "knockout" | "group_knockout"
  tier: "domestic_top" | "continental" | "international" | "domestic_2"
  country: string
  n_teams: number
  relegation_spots: number
  ucl_spots: number
}

export interface PlayerStat {
  name: string
  position: string | null
  goals_per_90: number | null
  xg_per_90: number | null
  assists_per_90: number | null
  yellow_cards_per_90: number | null
  is_injured: boolean
  is_suspended: boolean
  data_status: "available" | "pending" | "unavailable"
}

export interface SystemStats {
  teams_loaded: number
  players_count: number
  matches_count: number
  leagues_count: number
  active_model: string
  model_accuracy: number | null
  dc_ready: boolean
  klement_loaded: number
  form_model_ready: boolean
  simulations_count: number
  avg_simulation_time: number | null
  last_updated: string | null
}

export interface ModelWeights {
  xgboost: number
  dixon_coles: number
  elo: number
  klement: number
  total_matches: number
  description: string
}

export interface KlementFactor {
  team: string
  gdp_per_capita: number | null
  population: number | null
  fifa_points: number | null
  football_culture: number | null
  is_host: boolean
  confederation: string | null
  klement_score: number | null
}

export interface DixonColesParams {
  teams: string[]
  attack: Record<string, number>
  defense: Record<string, number>
  home_adv: number
  rho: number
  fitted: boolean
}

export interface AIAnalysisReport {
  home: string
  away: string
  model: string
  home_win: number
  draw: number
  away_win: number
  most_likely_score: [number, number] | null
  report: string
  model_contributions: ModelWeights
  data_sources: string[]
  confidence: "high" | "medium" | "low"
  model_accuracy?: number | null
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

export interface ScoreMatrix {
  home: string
  away: string
  matrix: number[][]
  max_goals: number
  home_lambda: number
  away_mu: number
}

// ─── UI State Types ───────────────────────────────────────────────────────────

export type Page =
  | "dashboard"
  | "prediction"
  | "simulator"
  | "probabilities"
  | "elo"
  | "models"
  | "ai-analysis"
  | "players"
  | "teams"
  | "calendar"
  | "transfers"
  | "statistics"
  | "ai-chat"
  | "laboratory"
  | "settings"
  | "compare"
  | "history"

export type Theme = "dark" | "light"
export type Language = "es" | "en" | "pt"
export type ModelType = "hybrid" | "elo" | "dixon_coles" | "klement"

export interface AppSettings {
  theme: Theme
  language: Language
  default_sims: number
  default_model: ModelType
  animations: boolean
}

export interface HistoryEntry {
  id: string
  type: "prediction" | "simulation" | "analysis"
  timestamp: Date
  data: MatchPrediction | TournamentProbs | AIAnalysisReport
  label: string
}
