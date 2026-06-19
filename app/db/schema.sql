-- World Cup Predictor AI — PostgreSQL schema
-- Run against an empty database; mirrors app/db/models.py (SQLAlchemy).

CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    confederation   TEXT,
    gdp_per_capita  DOUBLE PRECISION,
    population      BIGINT,
    football_culture DOUBLE PRECISION,   -- 0..1
    avg_temp_c      DOUBLE PRECISION,
    is_host         BOOLEAN DEFAULT FALSE
);

CREATE TABLE matches (
    id          SERIAL PRIMARY KEY,
    match_date  DATE NOT NULL,
    home_team   INTEGER REFERENCES teams(id),
    away_team   INTEGER REFERENCES teams(id),
    home_goals  INTEGER,
    away_goals  INTEGER,
    match_type  TEXT DEFAULT 'friendly',  -- friendly|qualifier|continental|world_cup_group|world_cup_knockout
    neutral     BOOLEAN DEFAULT FALSE
);

CREATE TABLE players (
    id        SERIAL PRIMARY KEY,
    team_id   INTEGER REFERENCES teams(id),
    name      TEXT NOT NULL,
    position  TEXT
);

CREATE TABLE elo_history (
    id        SERIAL PRIMARY KEY,
    team_id   INTEGER REFERENCES teams(id),
    as_of     DATE NOT NULL,
    rating    DOUBLE PRECISION,
    attack    DOUBLE PRECISION,
    defense   DOUBLE PRECISION
);

CREATE TABLE fifa_rankings (
    id        SERIAL PRIMARY KEY,
    team_id   INTEGER REFERENCES teams(id),
    as_of     DATE NOT NULL,
    points    DOUBLE PRECISION,
    rank      INTEGER
);

CREATE TABLE macroeconomic_data (
    id              SERIAL PRIMARY KEY,
    team_id         INTEGER REFERENCES teams(id),
    year            INTEGER,
    gdp_per_capita  DOUBLE PRECISION,
    population      BIGINT
);

CREATE TABLE simulations (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT now(),
    n_sims      INTEGER,
    config      JSONB
);

CREATE TABLE predictions (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT now(),
    match_id    INTEGER REFERENCES matches(id),
    model       TEXT,                      -- elo|dixon_coles|klement|hybrid
    p_home      DOUBLE PRECISION,
    p_draw      DOUBLE PRECISION,
    p_away      DOUBLE PRECISION,
    extra       JSONB
);

CREATE TABLE tournament_results (
    id              SERIAL PRIMARY KEY,
    simulation_id   INTEGER REFERENCES simulations(id),
    team_id         INTEGER REFERENCES teams(id),
    p_champion      DOUBLE PRECISION,
    p_finalist      DOUBLE PRECISION,
    p_semifinalist  DOUBLE PRECISION,
    p_group_qualify DOUBLE PRECISION
);

CREATE TABLE model_metrics (
    id              SERIAL PRIMARY KEY,
    evaluated_at    TIMESTAMP DEFAULT now(),
    model           TEXT,
    accuracy        DOUBLE PRECISION,
    brier_score     DOUBLE PRECISION,
    log_loss        DOUBLE PRECISION,
    calibration_err DOUBLE PRECISION,
    roi             DOUBLE PRECISION
);

CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_elo_team_date ON elo_history(team_id, as_of);
CREATE INDEX idx_pred_match ON predictions(match_id);
