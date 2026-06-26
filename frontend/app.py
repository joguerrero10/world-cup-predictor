"""
World Cup Predictor AI — Plataforma Enterprise Multicompetición.

Secciones:
  🏠 Dashboard          → Resumen del sistema y últimas predicciones
  ⚽ Predicciones        → Predicción 1X2 por competición
  🎲 Simulaciones       → Monte Carlo con progress + resultados
  📊 Clasificaciones    → Standings reales por competición
  📅 Calendario         → Fixtures con predicciones
  🏆 Copa del Mundo     → Simulador Mundial 2026
  🌍 Champions League   → Simulador UCL
  🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League     → Simulador PL
  🇪🇸 La Liga            → Simulador LaLiga
  🇩🇪 Bundesliga         → Simulador Bundesliga
  🇮🇹 Serie A            → Simulador Serie A
  🇫🇷 Ligue 1            → Simulador Ligue 1
  💰 Transferencias     → Fichajes reales
  👤 Jugadores          → Estadísticas de jugadores
  📈 Ranking Elo        → Rankings por competición
  🔬 ML                 → Pipeline Machine Learning
  ⚙️ Sistema            → Monitor y configuración
"""
from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="WCP AI — Plataforma Enterprise",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --bg:       #0A0E1A;
  --surface:  #111827;
  --border:   #1E2D40;
  --cyan:     #00D4FF;
  --amber:    #F0B429;
  --green:    #22C55E;
  --red:      #EF4444;
  --text:     #E2E8F0;
  --muted:    #64748B;
  --radius:   12px;
}
html, body, [class*="css"] {
  font-family: 'Inter', sans-serif !important;
  background-color: var(--bg) !important;
  color: var(--text) !important;
}
.stApp { background-color: var(--bg) !important; }
.block-container { padding: 1.5rem 2rem 4rem !important; max-width: 1400px; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
.stSidebar { background-color: #0D1421 !important; border-right: 1px solid var(--border); }

/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
}
.card-title {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 1.2rem;
  letter-spacing: 0.05em;
  color: var(--cyan);
  margin-bottom: 0.5rem;
}
.metric-big {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 2.5rem;
  color: var(--amber);
  line-height: 1;
}
.metric-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }

/* Match card */
.match-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 0.75rem;
}
.team-name { font-weight: 600; font-size: 1rem; }
.vs { color: var(--muted); font-size: 0.85rem; }
.prob-bar {
  display: flex; border-radius: 4px; overflow: hidden;
  height: 6px; width: 100%;
}
.badge {
  display: inline-block; padding: 2px 8px;
  border-radius: 20px; font-size: 0.7rem; font-weight: 600;
}
.badge-club     { background: #1D4ED8; color: white; }
.badge-national { background: #065F46; color: white; }
.badge-live     { background: #EF4444; color: white; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.5; } }

/* Table */
.df-container { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th { background: var(--surface); color: var(--muted); font-size: 0.75rem;
     text-transform: uppercase; padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); }
td { padding: 0.55rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.875rem; }
tr:hover td { background: rgba(255,255,255,0.02); }

/* Progress bar */
.sim-progress { width: 100%; background: var(--border); border-radius: 4px; height: 8px; }
.sim-fill { background: linear-gradient(90deg, var(--cyan), var(--amber));
            height: 8px; border-radius: 4px; transition: width 0.3s; }

/* Section header */
.section-header {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 1.8rem; letter-spacing: 0.08em;
  color: var(--text); margin-bottom: 0.25rem;
}
.section-sub { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
"""
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        r = requests.get(f"{API_URL}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def api_post(path: str, json: dict | None = None) -> dict | None:
    try:
        r = requests.post(f"{API_URL}{path}", json=json, timeout=120)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _color_prob(p: float) -> str:
    if p >= 0.60: return "#22C55E"
    if p >= 0.40: return "#F0B429"
    return "#EF4444"


COMPETITION_META = {
    "fifa_wc_2026":   {"name": "Copa del Mundo 2026", "icon": "🏆", "type": "national"},
    "ucl":            {"name": "Champions League",     "icon": "🌍", "type": "club"},
    "premier_league": {"name": "Premier League",       "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "type": "club"},
    "laliga":         {"name": "La Liga",               "icon": "🇪🇸", "type": "club"},
    "bundesliga":     {"name": "Bundesliga",            "icon": "🇩🇪", "type": "club"},
    "serie_a":        {"name": "Serie A",               "icon": "🇮🇹", "type": "club"},
    "ligue_1":        {"name": "Ligue 1",               "icon": "🇫🇷", "type": "club"},
}


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚽ WCP AI")
    st.markdown("---")
    section = st.radio(
        "Sección",
        options=[
            "🏠 Dashboard",
            "⚽ Predicciones",
            "🎲 Simulaciones",
            "📊 Clasificaciones",
            "📅 Calendario",
            "🏆 Copa del Mundo",
            "🌍 Champions League",
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
            "🇪🇸 La Liga",
            "🇩🇪 Bundesliga",
            "🇮🇹 Serie A",
            "🇫🇷 Ligue 1",
            "💰 Transferencias",
            "👤 Jugadores",
            "📈 Ranking Elo",
            "🔬 ML Pipeline",
            "⚙️ Sistema",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Estado del sistema
    health = api_get("/api/v1/health") or api_get("/health")
    if health:
        status_color = "#22C55E" if health.get("status") == "ok" else "#EF4444"
        st.markdown(
            f'<span style="color:{status_color}">● API Online</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"🏟️ {health.get('teams_loaded', 0)} equipos cargados")
        models = health.get("models_ready", {})
        for m, ready in models.items():
            icon = "✅" if ready else "⭕"
            st.caption(f"{icon} {m.upper()}")
    else:
        st.error("❌ API Offline")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

if section == "🏠 Dashboard":
    st.markdown('<div class="section-header">WORLD CUP PREDICTOR AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Plataforma enterprise de predicción futbolística</div>', unsafe_allow_html=True)

    health = api_get("/api/v1/health") or api_get("/health") or {}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_teams = health.get("teams_loaded", 0)
        st.markdown(f"""
        <div class="card">
          <div class="metric-label">Equipos Cargados</div>
          <div class="metric-big">{n_teams}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        comps = health.get("competitions_available", [])
        st.markdown(f"""
        <div class="card">
          <div class="metric-label">Competiciones</div>
          <div class="metric-big">{len(comps)}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        dc_ok = health.get("dc_ready", False)
        st.markdown(f"""
        <div class="card">
          <div class="metric-label">Dixon-Coles</div>
          <div class="metric-big" style="color:{'#22C55E' if dc_ok else '#EF4444'}">
            {'✓' if dc_ok else '✗'}
          </div>
        </div>""", unsafe_allow_html=True)
    with col4:
        xgb_ok = health.get("form_model_ready", False)
        st.markdown(f"""
        <div class="card">
          <div class="metric-label">XGBoost</div>
          <div class="metric-big" style="color:{'#22C55E' if xgb_ok else '#EF4444'}">
            {'✓' if xgb_ok else '✗'}
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Competiciones disponibles")
    cols = st.columns(4)
    for i, (slug, meta) in enumerate(COMPETITION_META.items()):
        with cols[i % 4]:
            badge_cls = "badge-national" if meta["type"] == "national" else "badge-club"
            badge_txt = "Selecciones" if meta["type"] == "national" else "Clubes"
            st.markdown(f"""
            <div class="card">
              <div style="font-size:1.5rem">{meta["icon"]}</div>
              <div style="font-weight:600;margin:0.3rem 0">{meta["name"]}</div>
              <span class="badge {badge_cls}">{badge_txt}</span>
            </div>""", unsafe_allow_html=True)


# ── PREDICCIONES ──────────────────────────────────────────────────────────────

elif section == "⚽ Predicciones":
    st.markdown('<div class="section-header">PREDICCIÓN DE PARTIDOS</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 2])
    with col_a:
        competition = st.selectbox(
            "Competición",
            options=list(COMPETITION_META.keys()),
            format_func=lambda k: f"{COMPETITION_META[k]['icon']} {COMPETITION_META[k]['name']}",
        )

    # Cargar equipos de la competición seleccionada
    teams_data = api_get(f"/api/v1/competitions/{competition}/teams")
    if teams_data:
        team_names = [t["name"] for t in teams_data]
        team_type = teams_data[0].get("team_type", "club") if teams_data else "club"
    else:
        # Fallback: mostrar mensaje y cargar desde registry estático
        st.info(f"Cargando equipos de la competición...")
        team_names = []
        team_type = COMPETITION_META[competition]["type"]

    if team_names:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            home = st.selectbox("🏠 Local", team_names, key="pred_home")
        with col2:
            st.markdown("<br><div style='text-align:center;font-size:1.5rem;color:var(--muted)'>VS</div>", unsafe_allow_html=True)
        with col3:
            away_options = [t for t in team_names if t != home]
            away = st.selectbox("✈️ Visitante", away_options, key="pred_away")

        col_m, col_n = st.columns(2)
        with col_m:
            model = st.selectbox("Modelo", ["hybrid", "elo", "dixon_coles"], key="pred_model")
        with col_n:
            neutral = st.checkbox("Sede neutral", value=competition in ["fifa_wc_2026"])

        if st.button("🔮 Predecir", type="primary", use_container_width=True):
            with st.spinner("Calculando predicción..."):
                result = api_get("/predict-match", {
                    "home": home, "away": away,
                    "neutral": neutral, "model": model,
                })

            if result and "home_win" in result:
                ph = result["home_win"]
                pd_ = result["draw"]
                pa = result["away_win"]
                src = result.get("source", "hybrid")

                badge = "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Clubes" if team_type == "club" else "🌍 Selecciones"
                st.markdown(f"**Modelo:** `{src}` &nbsp;|&nbsp; **Tipo:** {badge}")
                st.markdown("---")

                c1, c2, c3 = st.columns(3)
                with c1:
                    color = _color_prob(ph)
                    st.markdown(f"""
                    <div class="card" style="text-align:center;border-color:{color}40">
                      <div style="font-size:0.8rem;color:var(--muted)">Victoria Local</div>
                      <div style="font-size:2.2rem;font-weight:700;color:{color}">{ph:.1%}</div>
                      <div style="font-weight:600">{home}</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    color_d = _color_prob(pd_)
                    st.markdown(f"""
                    <div class="card" style="text-align:center">
                      <div style="font-size:0.8rem;color:var(--muted)">Empate</div>
                      <div style="font-size:2.2rem;font-weight:700;color:var(--muted)">{pd_:.1%}</div>
                      <div style="font-weight:600">Empate</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    color_a = _color_prob(pa)
                    st.markdown(f"""
                    <div class="card" style="text-align:center;border-color:{color_a}40">
                      <div style="font-size:0.8rem;color:var(--muted)">Victoria Visitante</div>
                      <div style="font-size:2.2rem;font-weight:700;color:{color_a}">{pa:.1%}</div>
                      <div style="font-weight:600">{away}</div>
                    </div>""", unsafe_allow_html=True)

                # Barra de probabilidades
                fig = go.Figure(go.Bar(
                    x=[f"{home} ({ph:.1%})", f"Empate ({pd_:.1%})", f"{away} ({pa:.1%})"],
                    y=[ph, pd_, pa],
                    marker_color=["#00D4FF", "#94A3B8", "#F0B429"],
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E2E8F0"), showlegend=False,
                    margin=dict(l=0, r=0, t=20, b=0), height=200,
                )
                st.plotly_chart(fig, use_container_width=True)
            elif result:
                st.error(f"Error: {result.get('detail', result)}")
    else:
        st.warning("No se pudieron cargar los equipos. Verifica que la API esté activa.")


# ── SIMULACIONES ──────────────────────────────────────────────────────────────

elif section == "🎲 Simulaciones":
    st.markdown('<div class="section-header">MOTOR MONTE CARLO</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Simulación masiva con equipos correctos por competición</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        competition = st.selectbox(
            "Competición",
            options=list(COMPETITION_META.keys()),
            format_func=lambda k: f"{COMPETITION_META[k]['icon']} {COMPETITION_META[k]['name']}",
            key="sim_comp",
        )
    with col2:
        n_sims = st.select_slider(
            "Simulaciones",
            options=[1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000],
            value=10_000,
        )
    with col3:
        sim_model = st.selectbox("Modelo", ["hybrid", "elo", "dixon_coles"], key="sim_model")

    # Mostrar qué equipos se van a simular
    meta = COMPETITION_META[competition]
    badge_type = "🌍 Selecciones Nacionales" if meta["type"] == "national" else "🏟️ Clubes"
    st.info(f"{meta['icon']} **{meta['name']}** → {badge_type}")

    if st.button(f"▶ Simular {n_sims:,} veces", type="primary", use_container_width=True):
        progress_bar = st.progress(0, text="Iniciando simulación...")
        status_text = st.empty()
        time_text = st.empty()

        t_start = time.time()
        with st.spinner(""):
            for pct in [10, 30, 60, 90]:
                time.sleep(0.05)
                progress_bar.progress(pct / 100, text=f"Simulando... {pct}%")

            result = api_get(
                "/api/v1/simulate/",
                {"competition": competition, "n_sims": n_sims, "model": sim_model},
            )
            progress_bar.progress(1.0, text="✅ Completado")

        if result and "champion" in result:
            elapsed = result.get("elapsed_seconds", time.time() - t_start)
            sps = result.get("sims_per_second", 0)
            team_type_label = result.get("team_type", "club")

            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Simulaciones", f"{result['n_sims']:,}")
            with col_b:
                st.metric("Tiempo", f"{elapsed:.1f}s")
            with col_c:
                st.metric("Sims/seg", f"{sps:,.0f}")
            with col_d:
                badge = "🌍 Selecc." if team_type_label == "national" else "🏟️ Clubes"
                st.metric("Tipo equipos", badge)

            st.markdown("---")
            st.subheader(f"🏆 Probabilidades de Campeón — {meta['name']}")

            champion = result.get("champion", {})
            if champion:
                df = pd.DataFrame(
                    sorted(champion.items(), key=lambda x: x[1], reverse=True),
                    columns=["Equipo", "P(Campeón)"]
                )
                df["P(Campeón) %"] = (df["P(Campeón)"] * 100).round(2)
                df["Posición"] = range(1, len(df) + 1)

                # Añadir otras columnas si existen
                finalist = result.get("finalist", {})
                semi = result.get("semifinalist", {})
                relegated = result.get("relegated", {})

                if finalist:
                    df["P(Final)"] = df["Equipo"].map(lambda t: f"{finalist.get(t, 0):.1%}")
                if semi:
                    df["P(Semis)"] = df["Equipo"].map(lambda t: f"{semi.get(t, 0):.1%}")
                if relegated:
                    df["P(Relegado)"] = df["Equipo"].map(lambda t: f"{relegated.get(t, 0):.1%}")

                top_n = min(20, len(df))
                df_display = df.head(top_n)[["Posición", "Equipo", "P(Campeón) %"]].copy()
                if "P(Final)" in df.columns:
                    df_display["P(Final)"] = df["P(Final)"].head(top_n).values
                if "P(Semis)" in df.columns:
                    df_display["P(Semis)"] = df["P(Semis)"].head(top_n).values

                # Gráfico
                fig = px.bar(
                    df.head(top_n),
                    x="P(Campeón) %", y="Equipo",
                    orientation="h",
                    color="P(Campeón) %",
                    color_continuous_scale=["#1E3A5F", "#00D4FF"],
                    text="P(Campeón) %",
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#E2E8F0"), showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=0), height=max(300, top_n * 22),
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False,
                )
                fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                st.plotly_chart(fig, use_container_width=True)

                # Tabla
                st.dataframe(df_display, use_container_width=True, hide_index=True)
        elif result:
            st.error(f"Error en simulación: {result.get('detail', result)}")
        else:
            st.error("La API no respondió. Verifica que esté activa.")


# ── CLASIFICACIONES ───────────────────────────────────────────────────────────

elif section == "📊 Clasificaciones":
    st.markdown('<div class="section-header">CLASIFICACIONES</div>', unsafe_allow_html=True)

    league_comps = {k: v for k, v in COMPETITION_META.items() if k != "fifa_wc_2026"}
    competition = st.selectbox(
        "Liga",
        options=list(league_comps.keys()),
        format_func=lambda k: f"{COMPETITION_META[k]['icon']} {COMPETITION_META[k]['name']}",
    )

    standings = api_get(f"/api/v1/standings/{competition}")
    if standings:
        df = pd.DataFrame(standings)
        df = df.rename(columns={
            "position": "Pos", "team": "Equipo", "played": "PJ",
            "won": "G", "drawn": "E", "lost": "P",
            "goals_for": "GF", "goals_against": "GC",
            "goal_diff": "DG", "points": "Pts",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning(
            "Sin datos de clasificación en BD. "
            "Ejecuta el ETL: `POST /api/v1/update-data`"
        )
        # Mostrar simulación como alternativa
        if st.button("🎲 Ver clasificación simulada"):
            with st.spinner("Simulando temporada..."):
                result = api_get(
                    "/api/v1/simulate/",
                    {"competition": competition, "n_sims": 10_000}
                )
            if result and "extra" in result:
                table = result.get("extra", {}).get("expected_table", [])
                if table:
                    st.subheader("Tabla esperada (simulada)")
                    df_sim = pd.DataFrame(table)
                    st.dataframe(df_sim, use_container_width=True, hide_index=True)


# ── CALENDARIO ────────────────────────────────────────────────────────────────

elif section == "📅 Calendario":
    st.markdown('<div class="section-header">CALENDARIO DE PARTIDOS</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        competition = st.selectbox(
            "Competición",
            options=list(COMPETITION_META.keys()),
            format_func=lambda k: f"{COMPETITION_META[k]['icon']} {COMPETITION_META[k]['name']}",
            key="fix_comp",
        )
    with col2:
        upcoming = st.checkbox("Solo próximos partidos", value=True)

    with_pred = st.checkbox("Mostrar predicciones", value=True)

    fixtures = api_get(
        f"/api/v1/fixtures/{competition}",
        {"upcoming_only": upcoming, "with_predictions": with_pred, "limit": 30},
    )

    if fixtures:
        for f in fixtures:
            status_color = "#EF4444" if f["status"] == "played" else "#22C55E"
            pred_str = ""
            if f.get("p_home") is not None:
                pred_str = f'<span style="color:#00D4FF">{f["p_home"]:.0%}</span> / <span style="color:#94A3B8">{f["p_draw"]:.0%}</span> / <span style="color:#F0B429">{f["p_away"]:.0%}</span>'

            result_str = ""
            if f.get("home_goals") is not None:
                result_str = f'<b>{f["home_goals"]} - {f["away_goals"]}</b>'

            st.markdown(f"""
            <div class="match-card">
              <div>
                <div style="font-size:0.7rem;color:var(--muted)">{f["date"]} | {f["competition"]} Jornada {f.get("matchday","?")}</div>
                <div><b>{f["home_team"]}</b> <span class="vs">vs</span> <b>{f["away_team"]}</b></div>
                {f'<div style="font-size:0.8rem;margin-top:4px">{pred_str}</div>' if pred_str else ""}
              </div>
              <div style="text-align:right">
                {result_str if result_str else f'<span style="color:{status_color};font-size:0.75rem">{f["status"]}</span>'}
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info(
            "Sin fixtures en BD. El ETL cargará los partidos reales automáticamente. "
            "Ejecuta: `POST /api/v1/update-data`"
        )


# ── COMPETICIONES ESPECÍFICAS ──────────────────────────────────────────────────

def _render_competition_sim(comp_id: str, comp_name: str, icon: str):
    """Renderiza la vista de simulación para una competición específica."""
    st.markdown(f'<div class="section-header">{icon} {comp_name.upper()}</div>', unsafe_allow_html=True)

    # Equipos de la competición (siempre los correctos)
    teams_data = api_get(f"/api/v1/competitions/{comp_id}/teams")
    if teams_data:
        team_type = teams_data[0].get("team_type", "club")
        teams = [t["name"] for t in teams_data]
        badge = "🌍 Selecciones Nacionales" if team_type == "national" else "🏟️ Clubes"
        st.success(f"{badge} · {len(teams)} equipos")

        # Mostrar teams en grid
        cols = st.columns(min(6, len(teams)))
        for i, t in enumerate(teams[:24]):
            cols[i % len(cols)].markdown(
                f'<div style="font-size:0.75rem;padding:4px 8px;background:var(--surface);'
                f'border:1px solid var(--border);border-radius:6px;margin:2px;text-align:center">{t}</div>',
                unsafe_allow_html=True
            )
        if len(teams) > 24:
            st.caption(f"... y {len(teams) - 24} más")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        n_sims = st.select_slider(
            "Simulaciones",
            options=[1_000, 10_000, 50_000, 100_000, 500_000],
            value=50_000,
            key=f"sim_{comp_id}",
        )
    with col2:
        model = st.selectbox("Modelo", ["hybrid", "elo", "dixon_coles"], key=f"model_{comp_id}")

    if st.button(f"▶ Simular {comp_name}", type="primary", use_container_width=True):
        with st.spinner(f"Simulando {n_sims:,} temporadas de {comp_name}..."):
            result = api_get(
                "/api/v1/simulate/",
                {"competition": comp_id, "n_sims": n_sims, "model": model},
            )

        if result and "champion" in result:
            elapsed = result.get("elapsed_seconds", 0)
            st.metric("⏱ Tiempo", f"{elapsed:.1f}s")

            champion = result.get("champion", {})
            df = pd.DataFrame(
                sorted(champion.items(), key=lambda x: x[1], reverse=True),
                columns=["Equipo", "P(Campeón)"]
            )
            df["Prob %"] = (df["P(Campeón)"] * 100).round(2)
            df["#"] = range(1, len(df) + 1)

            for col_key, label in [("finalist", "Final"), ("top4", "Top4"), ("relegated", "Desc")]:
                data = result.get(col_key, {})
                if data:
                    df[label] = df["Equipo"].map(lambda t: f"{data.get(t, 0):.1%}")

            fig = px.bar(
                df.head(min(20, len(df))),
                x="Prob %", y="Equipo", orientation="h",
                color="Prob %",
                color_continuous_scale=["#1E3A5F", "#00D4FF"],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E2E8F0"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=max(250, min(20, len(df)) * 22),
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            show_cols = ["#", "Equipo", "Prob %"] + [c for c in ["Final", "Top4", "Desc"] if c in df.columns]
            st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.error(f"Error: {result}")


for section_name, comp_id in [
    ("🏆 Copa del Mundo",    "fifa_wc_2026"),
    ("🌍 Champions League",  "ucl"),
    ("🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "premier_league"),
    ("🇪🇸 La Liga",           "laliga"),
    ("🇩🇪 Bundesliga",        "bundesliga"),
    ("🇮🇹 Serie A",           "serie_a"),
    ("🇫🇷 Ligue 1",           "ligue_1"),
]:
    if section == section_name:
        meta = COMPETITION_META[comp_id]
        _render_competition_sim(comp_id, meta["name"], meta["icon"])


# ── TRANSFERENCIAS ────────────────────────────────────────────────────────────

elif section == "💰 Transferencias":
    st.markdown('<div class="section-header">FICHAJES REALES</div>', unsafe_allow_html=True)
    st.caption("Datos reales del ETL (Transfermarkt / API-Football). Sin datos inventados.")

    col1, col2, col3 = st.columns(3)
    with col1:
        player_filter = st.text_input("Buscar jugador")
    with col2:
        type_filter = st.selectbox("Tipo", ["todos", "permanent", "loan", "free"])
    with col3:
        limit = st.slider("Resultados", 10, 100, 30)

    params = {"limit": limit}
    if player_filter:
        params["player"] = player_filter
    if type_filter != "todos":
        params["transfer_type"] = type_filter

    transfers = api_get("/api/v1/transfers/", params)
    if transfers:
        df = pd.DataFrame(transfers)
        df = df[["player", "from_team", "to_team", "date", "transfer_type", "fee_display"]]
        df.columns = ["Jugador", "De", "A", "Fecha", "Tipo", "Valor"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Sin fichajes en BD. El ETL descargará los fichajes reales automáticamente. "
            "Ejecuta: `POST /api/v1/update-data`"
        )


# ── JUGADORES ─────────────────────────────────────────────────────────────────

elif section == "👤 Jugadores":
    st.markdown('<div class="section-header">ESTADÍSTICAS DE JUGADORES</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        team_filter = st.text_input("Equipo")
    with col2:
        pos_filter = st.selectbox("Posición", ["Todas", "GK", "DEF", "MID", "FWD"])
    with col3:
        injured = st.selectbox("Estado", ["Todos", "Disponible", "Lesionado"])
    with col4:
        sort_by = st.selectbox("Ordenar por", ["overall_rating", "goals_per_90", "market_value_eur"])

    params = {"limit": 50, "sort_by": sort_by}
    if team_filter:
        params["team"] = team_filter
    if pos_filter != "Todas":
        params["position"] = pos_filter
    if injured == "Lesionado":
        params["injured"] = "true"
    elif injured == "Disponible":
        params["injured"] = "false"

    players = api_get("/api/v1/players/", params)
    if players:
        df = pd.DataFrame(players)
        cols = ["name", "team", "position", "age", "overall_rating",
                "goals_per_90", "assists_per_90", "xg_per_90",
                "minutes_played", "market_value_eur", "is_injured"]
        cols = [c for c in cols if c in df.columns]
        df_display = df[cols].copy()
        df_display.columns = ["Jugador", "Equipo", "Pos", "Edad", "Rating",
                               "G/90", "A/90", "xG/90", "Min", "Valor €", "Lesión"][:len(cols)]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos de jugadores. Ejecuta el ETL: `POST /api/v1/update-data`")


# ── RANKING ELO ───────────────────────────────────────────────────────────────

elif section == "📈 Ranking Elo":
    st.markdown('<div class="section-header">RANKINGS ELO</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        filter_comp = st.selectbox(
            "Filtrar por competición",
            options=["Todos"] + list(COMPETITION_META.keys()),
            format_func=lambda k: "Todos" if k == "Todos" else f"{COMPETITION_META.get(k, {}).get('icon', '')} {COMPETITION_META.get(k, {}).get('name', k)}",
        )
    with col2:
        limit_elo = st.slider("Top N", 10, 100, 30)

    params = {"limit": limit_elo}
    if filter_comp != "Todos":
        params["competition"] = filter_comp

    rankings = api_get("/api/v1/elo-rankings", params) or api_get("/elo-rankings")

    if rankings:
        df = pd.DataFrame(rankings[:limit_elo])

        fig = go.Figure(go.Bar(
            x=[r["team"] for r in rankings[:20]],
            y=[r["rating"] for r in rankings[:20]],
            marker_color=[
                f"rgba(0, 212, 255, {0.4 + 0.6 * (1 - i/20)})"
                for i in range(min(20, len(rankings)))
            ],
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E2E8F0"),
            margin=dict(l=0, r=0, t=10, b=0), height=300,
            xaxis=dict(tickangle=-45),
        )
        st.plotly_chart(fig, use_container_width=True)

        if filter_comp != "Todos":
            meta = COMPETITION_META[filter_comp]
            badge = "🌍 Selecciones" if meta["type"] == "national" else "🏟️ Clubes"
            st.info(f"Mostrando equipos de {meta['icon']} {meta['name']} · {badge}")

        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("Sin ratings Elo cargados. Ejecuta: `POST /load-from-db`")


# ── ML PIPELINE ───────────────────────────────────────────────────────────────

elif section == "🔬 ML Pipeline":
    st.markdown('<div class="section-header">MACHINE LEARNING PIPELINE</div>', unsafe_allow_html=True)

    st.markdown("""
    ```
    ETL
     ↓
    Feature Engineering (Elo diff, DC λ, xG, forma, Klement)
     ↓
    Entrenamiento XGBoost (walk-forward CV)
     ↓
    Validación (Brier Score, Log Loss, Accuracy)
     ↓
    Calibración Isotónica
     ↓
    Ensemble (Elo + Bayesian Elo + Glicko-2 + DC + XGBoost + xG + Klement)
     ↓
    Inferencia (< 1ms por partido)
     ↓
    Monitoreo (drift, performance)
    ```
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Reentrenar XGBoost", use_container_width=True):
            with st.spinner("Reentrenando..."):
                result = api_post("/train-form-model")
            if result:
                st.success(f"Entrenado con {result.get('trained_on', 0):,} partidos")
            else:
                st.error("Error al entrenar")

    with col2:
        if st.button("📥 Cargar modelos desde BD", use_container_width=True):
            with st.spinner("Cargando..."):
                result = api_post("/load-from-db")
            if result and "teams" in result:
                st.success(f"Cargados: {result['teams']} equipos, {result['matches']} partidos")
            else:
                st.error(f"Error: {result}")

    # Métricas del modelo
    metrics = api_get("/model-performance")
    if metrics:
        st.subheader("Métricas de rendimiento")
        df = pd.DataFrame(metrics)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ── SISTEMA ───────────────────────────────────────────────────────────────────

elif section == "⚙️ Sistema":
    st.markdown('<div class="section-header">MONITOR DEL SISTEMA</div>', unsafe_allow_html=True)

    health = api_get("/api/v1/health") or api_get("/health") or {}

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Estado de la API")
        if health.get("status") == "ok":
            st.success("✅ API Online")
        else:
            st.error("❌ API Offline")

        st.json(health)

    with col2:
        st.subheader("Acciones")
        if st.button("🔄 Actualizar todos los datos", use_container_width=True):
            result = api_post("/api/v1/update-data", {
                "data_types": ["matches", "standings", "players"]
            })
            st.info(f"Iniciado: {result}")

        if st.button("📊 Cargar factores Klement", use_container_width=True):
            result = api_post("/load-factors")
            if result:
                st.success(f"Factores: {result.get('teams_with_factors', 0)} equipos")

        if st.button("🔁 Recalcular Elo desde BD", use_container_width=True):
            result = api_post("/load-from-db")
            if result:
                st.success(f"Recalculado: {result.get('teams', 0)} equipos")

    st.markdown("---")
    st.subheader("Competiciones disponibles")
    comps = api_get("/api/v1/simulate/competitions") or []
    if comps:
        df = pd.DataFrame(comps)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Competiciones: " + ", ".join(COMPETITION_META.keys()))
