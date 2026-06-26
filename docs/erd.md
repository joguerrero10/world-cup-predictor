# Diagrama Entidad-Relación — World Cup Predictor AI

## ERD Mermaid

```mermaid
erDiagram
    competitions {
        int id PK
        string slug UK
        string name
        string competition_type
        string tier
        string country
        int n_teams
        int relegation_spots
        int ucl_spots
        int uel_spots
        int legs
    }

    seasons {
        int id PK
        int competition_id FK
        int year_start
        int year_end
        string status
        string data_sync_status
    }

    teams {
        int id PK
        string name UK
        string short_name
        string country
        string confederation
        float gdp_per_capita
        bigint population
        float football_culture
        float avg_temp_c
        bool is_host
        string data_source
        datetime last_synced_at
    }

    season_teams {
        int id PK
        int season_id FK
        int team_id FK
        string group_name
        int final_position
        bool is_promoted
        bool is_relegated
    }

    players {
        int id PK
        int team_id FK
        string name
        string position
        date birth_date
        string nationality
        float overall_rating
        float goals_per_90
        float xg_per_90
        float assists_per_90
        float yellow_cards_per_90
        float red_cards_per_90
        int minutes_played
        float market_value_eur
        bool is_injured
        bool is_suspended
        int yellow_cards_season
        string data_source
        datetime last_synced_at
    }

    matches {
        int id PK
        int season_id FK
        date match_date
        int home_team FK
        int away_team FK
        int home_goals
        int away_goals
        int home_goals_ht
        int away_goals_ht
        string match_type
        bool neutral
        int matchday
        string round_name
        string venue
        int attendance
        float home_xg
        float away_xg
    }

    match_events {
        int id PK
        int match_id FK
        int team_id FK
        int player_id FK
        int assist_player_id FK
        int minute
        string event_type
        jsonb extra
    }

    lineups {
        int id PK
        int match_id FK
        int team_id FK
        string formation
        string coach
    }

    lineup_players {
        int id PK
        int lineup_id FK
        int player_id FK
        bool is_starter
        int shirt_number
        string position_played
        int minutes_played
        float rating
    }

    transfers {
        int id PK
        int player_id FK
        int from_team_id FK
        int to_team_id FK
        date transfer_date
        string transfer_type
        float fee_eur
        string data_source
        string data_sync_status
    }

    injuries {
        int id PK
        int player_id FK
        int team_id FK
        date injury_date
        date expected_return
        date actual_return
        string injury_type
        string severity
        float performance_impact
        string data_source
    }

    standings {
        int id PK
        int team_id FK
        string competition_slug
        int season_year
        int position
        int played
        int won
        int drawn
        int lost
        int goals_for
        int goals_against
        int points
        datetime last_updated
    }

    elo_history {
        int id PK
        int team_id FK
        date as_of
        float rating
        float attack
        float defense
    }

    fifa_rankings {
        int id PK
        int team_id FK
        date as_of
        float points
        int rank
    }

    predictions {
        int id PK
        datetime created_at
        int match_id FK
        string model
        float p_home
        float p_draw
        float p_away
        jsonb extra
    }

    simulation_jobs {
        int id PK
        datetime created_at
        datetime started_at
        datetime completed_at
        string status
        string competition_id
        int n_sims
        string model_name
        jsonb config
        jsonb result_json
        string error_message
        float duration_seconds
        string worker_id
    }

    model_metrics {
        int id PK
        datetime evaluated_at
        string model
        string competition_id
        float accuracy
        float brier_score
        float log_loss
        float calibration_err
        float roi
    }

    update_logs {
        int id PK
        datetime started_at
        datetime completed_at
        string competition_slug
        string data_type
        int records_fetched
        int records_inserted
        int records_updated
        int records_skipped
        int errors
        string status
        string error_detail
        float duration_seconds
        jsonb providers_used
    }

    macroeconomic_data {
        int id PK
        int team_id FK
        int year
        float gdp_per_capita
        bigint population
    }

    %% Relaciones
    competitions ||--o{ seasons : "tiene"
    seasons ||--o{ season_teams : "incluye"
    teams ||--o{ season_teams : "participa en"
    teams ||--o{ players : "tiene"
    teams ||--o{ matches : "juega como local"
    teams ||--o{ matches : "juega como visitante"
    seasons ||--o{ matches : "contiene"
    matches ||--o{ match_events : "tiene"
    matches ||--o{ lineups : "tiene"
    lineups ||--o{ lineup_players : "incluye"
    players ||--o{ lineup_players : "aparece en"
    players ||--o{ transfers : "tiene"
    players ||--o{ injuries : "sufre"
    teams ||--o{ transfers : "origen"
    teams ||--o{ transfers : "destino"
    teams ||--o{ standings : "tiene"
    teams ||--o{ elo_history : "tiene"
    teams ||--o{ fifa_rankings : "tiene"
    teams ||--o{ macroeconomic_data : "tiene"
    matches ||--o{ predictions : "tiene"
```

## Descripción de tablas principales

| Tabla | Propósito |
|-------|-----------|
| `competitions` | Catálogo de competiciones (Mundial, UCL, PL, etc.) |
| `seasons` | Temporadas por competición con estado de sincronización |
| `season_teams` | Equipos participantes en cada temporada (club o selección) |
| `teams` | Equipos: tanto clubes como selecciones nacionales |
| `players` | Jugadores con estadísticas completas per-90 |
| `matches` | Partidos con resultados, xG y metadata |
| `match_events` | Goles, tarjetas, sustituciones por partido |
| `lineups` | Alineaciones por partido y equipo |
| `transfers` | Fichajes reales (fee, tipo, fecha) |
| `injuries` | Lesiones con gravedad e impacto en rendimiento |
| `standings` | Clasificaciones de liga actualizadas por ETL |
| `elo_history` | Histórico de ratings Elo por equipo y fecha |
| `predictions` | Predicciones 1X2 guardadas por modelo |
| `simulation_jobs` | Jobs de Monte Carlo asíncronos con estado |
| `model_metrics` | Métricas de evaluación de modelos |
| `update_logs` | Auditoría de ejecuciones del ETL |
