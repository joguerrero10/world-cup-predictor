import { client } from "./client"
import type {
  HealthStatus, EloTeam, MatchPrediction, TournamentProbs,
  SimulationJobStatus, SimulationJobResult, LeagueTable,
  SystemStats, ModelWeights, KlementFactor, DixonColesParams,
  AIAnalysisReport, ScoreMatrix, ModelType, Competition, FixtureItem,
  TeamDetail
} from "../types"

// ─── Health ──────────────────────────────────────────────────────────────────

export const fetchHealth = async (): Promise<HealthStatus> => {
  const r = await client.get("/health")
  return r.data
}

// ─── System Stats ─────────────────────────────────────────────────────────────

export const fetchSystemStats = async (): Promise<SystemStats> => {
  const r = await client.get("/api/v1/system-stats")
  return r.data
}

// ─── Competitions ─────────────────────────────────────────────────────────────

export const fetchCompetitions = async (): Promise<Competition[]> => {
  const r = await client.get("/api/v1/competitions")
  return r.data
}

// ─── Elo Rankings ─────────────────────────────────────────────────────────────

export const fetchEloRankings = async (): Promise<EloTeam[]> => {
  const r = await client.get("/elo-rankings")
  return r.data
}

// ─── Prediction ───────────────────────────────────────────────────────────────

export const fetchPrediction = async (
  home: string,
  away: string,
  model: ModelType = "hybrid",
  neutral = true
): Promise<MatchPrediction> => {
  const r = await client.get("/api/v1/predict-match", {
    params: { home, away, model, neutral },
  })
  return r.data
}

// ─── Score Matrix ─────────────────────────────────────────────────────────────

export const fetchScoreMatrix = async (
  home: string,
  away: string,
  neutral = true
): Promise<ScoreMatrix> => {
  const r = await client.get("/api/v1/score-matrix", {
    params: { home, away, neutral },
  })
  return r.data
}

// ─── Team Probabilities (Tournament) ─────────────────────────────────────────

export const fetchTournamentProbs = async (
  competition_id: string,
  n_sims: number
): Promise<TournamentProbs> => {
  const r = await client.get("/api/v1/team-probabilities", {
    params: { competition_id, n_sims },
  })
  return r.data
}

// ─── League Table ─────────────────────────────────────────────────────────────

export const fetchLeagueTable = async (
  competition_id: string,
  n_sims: number = 10_000
): Promise<LeagueTable> => {
  const r = await client.get("/api/v1/league-table", {
    params: { competition_id, n_sims },
  })
  return r.data
}

// ─── Simulation Jobs ──────────────────────────────────────────────────────────

export const createSimulationJob = async (payload: {
  competition_id: string
  n_sims: number
  model?: string
}): Promise<SimulationJobStatus> => {
  const r = await client.post("/api/v1/simulation-jobs", payload)
  return r.data
}

export const fetchSimulationJob = async (id: number): Promise<SimulationJobStatus> => {
  const r = await client.get(`/api/v1/simulation-jobs/${id}`)
  return r.data
}

export const fetchSimulationJobResult = async (id: number): Promise<SimulationJobResult> => {
  const r = await client.get(`/api/v1/simulation-jobs/${id}/result`)
  return r.data
}

export const fetchSimulationJobs = async (limit = 20): Promise<SimulationJobStatus[]> => {
  const r = await client.get("/api/v1/simulation-jobs", { params: { limit } })
  return r.data
}

// ─── Model Data ───────────────────────────────────────────────────────────────

export const fetchModelWeights = async (): Promise<ModelWeights> => {
  const r = await client.get("/api/v1/model-weights")
  return r.data
}

export const fetchKlementFactors = async (): Promise<KlementFactor[]> => {
  const r = await client.get("/api/v1/klement-factors")
  return r.data
}

export const fetchDixonColesParams = async (): Promise<DixonColesParams> => {
  const r = await client.get("/api/v1/dixon-coles-params")
  return r.data
}

// ─── Teams ────────────────────────────────────────────────────────────────────

export const fetchTeamsList = async (): Promise<EloTeam[]> => {
  const r = await client.get("/api/v1/teams-list")
  return r.data
}

// ─── Players ──────────────────────────────────────────────────────────────────

export const fetchPlayers = async (
  team?: string,
  top_n = 100,
): Promise<{
  players: import("../types").PlayerStat[]
  team: string
  data_status: string
  last_synced_at: string | null
  message: string | null
}> => {
  if (!team) return { players: [], team: "", data_status: "pending", last_synced_at: null, message: null }
  const r = await client.get("/api/v1/player-probabilities", { params: { team, top_n } })
  return r.data
}

// ─── AI Analysis ─────────────────────────────────────────────────────────────

export const fetchAIAnalysis = async (
  home: string,
  away: string,
  model: ModelType = "hybrid"
): Promise<AIAnalysisReport> => {
  const r = await client.get("/api/v1/ai-analysis", {
    params: { home, away, model },
  })
  return r.data
}

// ─── AI Chat ──────────────────────────────────────────────────────────────────

export const sendChatMessage = async (
  message: string,
  history: Array<{ role: string; content: string }>
): Promise<{ response: string }> => {
  const r = await client.post("/api/v1/ai-chat", { message, history })
  return r.data
}

// ─── Model Performance ────────────────────────────────────────────────────────

export const fetchModelPerformance = async () => {
  const r = await client.get("/model-performance")
  return r.data
}

// ─── Load from DB ─────────────────────────────────────────────────────────────

// ─── Teams ────────────────────────────────────────────────────────────────────

export const fetchTeams = async (params?: {
  competition?: string
  team_type?: "club" | "national"
  search?: string
  limit?: number
}): Promise<TeamDetail[]> => {
  const r = await client.get("/api/v1/teams", { params })
  return r.data
}

// ─── Transfers ────────────────────────────────────────────────────────────────

export const fetchTransfers = async (params?: {
  team?: string
  transfer_type?: string
  limit?: number
}): Promise<import("../types").TransferItem[]> => {
  const r = await client.get("/api/v1/transfers", { params })
  return r.data
}

// ─── Fixtures / Calendar ──────────────────────────────────────────────────────

export const fetchFixtures = async (params?: {
  competition?: string
  date_from?: string
  date_to?: string
  status?: "FINISHED" | "LIVE" | "SCHEDULED" | "POSTPONED"
  limit?: number
  with_predictions?: boolean
}): Promise<FixtureItem[]> => {
  const r = await client.get("/api/v1/fixtures", { params })
  return r.data
}

// ─── Model Metrics ────────────────────────────────────────────────────────────

export const fetchModelMetrics = async (): Promise<{
  stored: Array<{
    model: string
    accuracy: number | null
    brier_score: number | null
    log_loss: number | null
    evaluated_at: string | null
  }>
  live: Record<string, {
    n_evaluated: number
    brier_score: number | null
    accuracy: number | null
  }>
  note: string
  error?: string
}> => {
  const r = await client.get("/api/v1/model-metrics")
  return r.data
}

// ─── Load from DB ─────────────────────────────────────────────────────────────

export const triggerLoadFromDB = async () => {
  const r = await client.post("/load-from-db")
  return r.data
}

export const triggerLoadFactors = async () => {
  const r = await client.post("/load-factors")
  return r.data
}

export const triggerTrainFormModel = async () => {
  const r = await client.post("/train-form-model")
  return r.data
}
