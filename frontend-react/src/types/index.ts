// ─── API Types ───────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string
  teams_loaded: number
  matches_in_db: number
  dc_ready: boolean
  xgb_ready: boolean
  form_model_ready?: boolean   // legacy alias
  klement_factors_loaded: number
  engine_warm: boolean
  auto_etl_enabled: boolean
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

/**
 * Respuesta unificada del simulador (SimulationResponse del backend).
 *
 * Para competiciones de grupos/knockout (fifa_wc_2026, ucl):
 *   - finalist y semifinalist están poblados
 *   - top4/top6/relegated son {}
 *   - extra.group_qualified contiene prob. de clasificar de grupo
 *
 * Para ligas domésticas (premier_league, laliga, etc.):
 *   - finalist y semifinalist son {}
 *   - top4, top6, relegated están poblados
 *   - extra.group_qualified es {}
 */
export interface TournamentProbs {
  competition: string
  competition_name: string
  n_sims: number
  teams: string[]
  team_type: "club" | "national"
  elapsed_seconds: number
  sims_per_second: number
  champion: Record<string, number>
  finalist: Record<string, number>
  semifinalist: Record<string, number>
  top4: Record<string, number>
  top6: Record<string, number>
  relegated: Record<string, number>
  extra: {
    group_qualified?:    Record<string, number>
    league_phase_top8?:  Record<string, number>
    playoff_qual?:       Record<string, number>
    round_of_16?:        Record<string, number>
    quarterfinal?:       Record<string, number>
    expected_group_pts?: Record<string, number>
    position_probs?:     Record<string, number[]>
    [key: string]: unknown
  }
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
  overall_rating: number | null
  minutes_played: number | null
  is_injured: boolean
  is_suspended: boolean
  data_status: "available" | "pending" | "unavailable"
}

export interface TeamDetail {
  id: number | null
  name: string
  short_name: string | null
  country: string | null
  team_type: "club" | "national"
  competition_id: string | null
  competition_name: string | null
  logo_url: string | null
  stadium: string | null
  founded_year: number | null
  market_value_eur: number | null
  elo_rating: number | null
  elo_attack: number | null
  elo_defense: number | null
  elo_rank: number | null
}

export interface TransferItem {
  id: number
  player: string
  from_team: string | null
  to_team: string
  date: string
  transfer_type: string
  fee_eur: number | null
  fee_display: string
}

export interface FixtureItem {
  match_id: number
  competition: string
  season: string
  date: string
  matchday: number | null
  round: string | null
  home_team: string
  away_team: string
  venue: string | null
  status: "FINISHED" | "LIVE" | "SCHEDULED" | "POSTPONED"
  p_home: number | null
  p_draw: number | null
  p_away: number | null
  expected_goals_home?: number | null
  expected_goals_away?: number | null
  home_goals: number | null
  away_goals: number | null
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
