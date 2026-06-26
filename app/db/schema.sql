-- Football Simulation Platform — PostgreSQL schema v2
-- Generado desde app/db/models.py (SQLAlchemy 2.0)
-- Ejecutar contra una DB vacía; en producción usar: alembic upgrade head

-- ── Competiciones y temporadas ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS competitions (
    id                  SERIAL PRIMARY KEY,
    slug                TEXT NOT NULL UNIQUE,        -- "premier_league"
    name                TEXT NOT NULL,
    competition_type    TEXT NOT NULL,               -- league|knockout|group_knockout
    tier                TEXT NOT NULL,               -- domestic_top|continental|international
    country             TEXT,
    n_teams             INTEGER NOT NULL,
    relegation_spots    INTEGER DEFAULT 0,
    ucl_spots           INTEGER DEFAULT 0,
    uel_spots           INTEGER DEFAULT 0,
    legs                INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS seasons (
    id                  SERIAL PRIMARY KEY,
    competition_id      INTEGER REFERENCES competitions(id),
    year_start          INTEGER NOT NULL,
    year_end            INTEGER NOT NULL,
    status              TEXT DEFAULT 'upcoming',      -- upcoming|active|completed
    data_sync_status    TEXT DEFAULT 'pending',       -- pending|synced|stale
    UNIQUE(competition_id, year_start)
);

CREATE TABLE IF NOT EXISTS season_teams (
    id                  SERIAL PRIMARY KEY,
    season_id           INTEGER REFERENCES seasons(id),
    team_id             INTEGER REFERENCES teams(id),
    group_name          TEXT,
    final_position      INTEGER,
    is_promoted         BOOLEAN DEFAULT FALSE,
    is_relegated        BOOLEAN DEFAULT FALSE,
    UNIQUE(season_id, team_id)
);

-- ── Equipos ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS teams (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    short_name          VARCHAR(10),
    country             TEXT,
    confederation       TEXT,
    gdp_per_capita      DOUBLE PRECISION,
    population          BIGINT,
    football_culture    DOUBLE PRECISION,            -- 0..1
    avg_temp_c          DOUBLE PRECISION,
    is_host             BOOLEAN DEFAULT FALSE,
    data_source         TEXT,
    last_synced_at      TIMESTAMP
);

-- ── Jugadores (ampliado) ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS players (
    id                      SERIAL PRIMARY KEY,
    team_id                 INTEGER REFERENCES teams(id),
    name                    TEXT NOT NULL,
    position                TEXT,                    -- GK|DEF|MID|FWD
    birth_date              DATE,
    nationality             TEXT,
    overall_rating          DOUBLE PRECISION,        -- 0-100
    goals_per_90            DOUBLE PRECISION,
    xg_per_90               DOUBLE PRECISION,
    assists_per_90          DOUBLE PRECISION,
    yellow_cards_per_90     DOUBLE PRECISION,
    red_cards_per_90        DOUBLE PRECISION,
    minutes_played          INTEGER,
    market_value_eur        DOUBLE PRECISION,
    is_injured              BOOLEAN DEFAULT FALSE,
    is_suspended            BOOLEAN DEFAULT FALSE,
    yellow_cards_season     INTEGER DEFAULT 0,
    data_source             TEXT,
    last_synced_at          TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);

-- ── Traspasos ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS transfers (
    id                  SERIAL PRIMARY KEY,
    player_id           INTEGER REFERENCES players(id),
    from_team_id        INTEGER REFERENCES teams(id),
    to_team_id          INTEGER REFERENCES teams(id),
    transfer_date       DATE NOT NULL,
    transfer_type       TEXT NOT NULL,               -- permanent|loan|free|end_loan
    fee_eur             DOUBLE PRECISION,
    data_source         TEXT,
    data_sync_status    TEXT DEFAULT 'pending'
);

-- ── Partidos (ampliado) ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS matches (
    id              SERIAL PRIMARY KEY,
    season_id       INTEGER REFERENCES seasons(id),
    match_date      DATE NOT NULL,
    home_team       INTEGER REFERENCES teams(id),
    away_team       INTEGER REFERENCES teams(id),
    home_goals      INTEGER,
    away_goals      INTEGER,
    home_goals_ht   INTEGER,
    away_goals_ht   INTEGER,
    match_type      TEXT DEFAULT 'friendly',
    neutral         BOOLEAN DEFAULT FALSE,
    matchday        INTEGER,
    round_name      TEXT,
    venue           TEXT,
    attendance      INTEGER,
    home_xg         DOUBLE PRECISION,
    away_xg         DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season_id);

-- ── Eventos de partido ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS match_events (
    id                  SERIAL PRIMARY KEY,
    match_id            INTEGER REFERENCES matches(id),
    team_id             INTEGER REFERENCES teams(id),
    player_id           INTEGER REFERENCES players(id),
    assist_player_id    INTEGER REFERENCES players(id),
    minute              INTEGER,
    event_type          TEXT NOT NULL,               -- goal|yellow_card|red_card|sub|penalty_goal|own_goal
    extra               JSONB
);
CREATE INDEX IF NOT EXISTS idx_events_match ON match_events(match_id);
CREATE INDEX IF NOT EXISTS idx_events_player ON match_events(player_id);

-- ── Alineaciones ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lineups (
    id          SERIAL PRIMARY KEY,
    match_id    INTEGER REFERENCES matches(id),
    team_id     INTEGER REFERENCES teams(id),
    formation   TEXT,
    coach       TEXT
);

CREATE TABLE IF NOT EXISTS lineup_players (
    id                  SERIAL PRIMARY KEY,
    lineup_id           INTEGER REFERENCES lineups(id),
    player_id           INTEGER REFERENCES players(id),
    is_starter          BOOLEAN DEFAULT TRUE,
    shirt_number        INTEGER,
    position_played     TEXT,
    minutes_played      INTEGER,
    rating              DOUBLE PRECISION
);

-- ── Lesiones ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS injuries (
    id                  SERIAL PRIMARY KEY,
    player_id           INTEGER REFERENCES players(id),
    team_id             INTEGER REFERENCES teams(id),
    injury_date         DATE NOT NULL,
    expected_return     DATE,
    actual_return       DATE,
    injury_type         TEXT,
    severity            TEXT DEFAULT 'moderate',     -- minor|moderate|severe
    performance_impact  DOUBLE PRECISION DEFAULT 0.0,
    data_source         TEXT,
    data_sync_status    TEXT DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_injuries_player ON injuries(player_id);

-- ── Trabajos de simulación asíncronos ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS simulation_jobs (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMP DEFAULT now(),
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    status              TEXT DEFAULT 'queued',       -- queued|running|completed|failed
    competition_id      TEXT NOT NULL,
    n_sims              INTEGER NOT NULL,
    model_name          TEXT DEFAULT 'hybrid',
    config              JSONB,
    result_json         JSONB,
    error_message       TEXT,
    duration_seconds    DOUBLE PRECISION,
    worker_id           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sim_jobs_status ON simulation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_sim_jobs_created ON simulation_jobs(created_at);

-- ── Tablas existentes (compatibilidad) ────────────────────────────────────

CREATE TABLE IF NOT EXISTS elo_history (
    id          SERIAL PRIMARY KEY,
    team_id     INTEGER REFERENCES teams(id),
    as_of       DATE NOT NULL,
    rating      DOUBLE PRECISION,
    attack      DOUBLE PRECISION,
    defense     DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_elo_team_date ON elo_history(team_id, as_of);

CREATE TABLE IF NOT EXISTS fifa_rankings (
    id          SERIAL PRIMARY KEY,
    team_id     INTEGER REFERENCES teams(id),
    as_of       DATE NOT NULL,
    points      DOUBLE PRECISION,
    rank        INTEGER
);

CREATE TABLE IF NOT EXISTS macroeconomic_data (
    id              SERIAL PRIMARY KEY,
    team_id         INTEGER REFERENCES teams(id),
    year            INTEGER,
    gdp_per_capita  DOUBLE PRECISION,
    population      BIGINT
);

CREATE TABLE IF NOT EXISTS simulations (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT now(),
    n_sims      INTEGER,
    config      JSONB
);

CREATE TABLE IF NOT EXISTS predictions (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT now(),
    match_id    INTEGER REFERENCES matches(id),
    model       TEXT,
    p_home      DOUBLE PRECISION,
    p_draw      DOUBLE PRECISION,
    p_away      DOUBLE PRECISION,
    extra       JSONB
);
CREATE INDEX IF NOT EXISTS idx_pred_match ON predictions(match_id);

CREATE TABLE IF NOT EXISTS tournament_results (
    id              SERIAL PRIMARY KEY,
    simulation_id   INTEGER REFERENCES simulations(id),
    team_id         INTEGER REFERENCES teams(id),
    p_champion      DOUBLE PRECISION,
    p_finalist      DOUBLE PRECISION,
    p_semifinalist  DOUBLE PRECISION,
    p_group_qualify DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id              SERIAL PRIMARY KEY,
    evaluated_at    TIMESTAMP DEFAULT now(),
    model           TEXT,
    competition_id  TEXT,
    accuracy        DOUBLE PRECISION,
    brier_score     DOUBLE PRECISION,
    log_loss        DOUBLE PRECISION,
    calibration_err DOUBLE PRECISION,
    roi             DOUBLE PRECISION
);
