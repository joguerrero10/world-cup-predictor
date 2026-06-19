"""
World Cup Predictor AI — Frontend rediseñado.
Diseño: azul noche de estadio, tipografía de marcador, barra de duelo como firma.
"""
from __future__ import annotations
import io, os
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="World Cup Predictor AI",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --bg:        #0A0E1A;
  --surface:   #111827;
  --border:    #1E2D40;
  --cyan:      #00D4FF;
  --amber:     #F0B429;
  --text:      #E2E8F0;
  --muted:     #64748B;
  --home-clr:  #00D4FF;
  --away-clr:  #F0B429;
  --draw-clr:  #94A3B8;
  --radius:    12px;
}

/* Base */
html, body, [class*="css"] {
  font-family: 'Inter', sans-serif !important;
  background-color: var(--bg) !important;
  color: var(--text) !important;
}
.stApp { background-color: var(--bg) !important; }
.block-container { padding: 2rem 2rem 4rem !important; max-width: 1200px; }

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── HERO ───────────────────────────────────────────────────────────────────── */
.hero {
  text-align: center;
  padding: 3rem 1rem 2rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2.5rem;
}
.hero-title {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(2.8rem, 6vw, 5rem);
  letter-spacing: 0.08em;
  line-height: 1;
  color: var(--text);
  margin: 0;
}
.hero-title span { color: var(--cyan); }
.hero-sub {
  font-size: 0.9rem;
  color: var(--muted);
  margin-top: 0.5rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

/* ── STATUS PILLS ───────────────────────────────────────────────────────────── */
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin: 1rem 0 2rem;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3rem 0.75rem;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.pill-ok   { background: rgba(0,212,255,0.12); color: var(--cyan);  border: 1px solid rgba(0,212,255,0.3); }
.pill-warn { background: rgba(240,180,41,0.12); color: var(--amber); border: 1px solid rgba(240,180,41,0.3); }
.pill-off  { background: rgba(100,116,139,0.12); color: var(--muted); border: 1px solid rgba(100,116,139,0.3); }

/* ── SECTION HEADERS ─────────────────────────────────────────────────────────── */
.section-label {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 0.7rem;
  letter-spacing: 0.2em;
  color: var(--cyan);
  text-transform: uppercase;
  margin-bottom: 0.3rem;
}
.section-title {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  letter-spacing: 0.05em;
  color: var(--text);
  margin: 0 0 1.5rem;
}

/* ── MATCH CARD ──────────────────────────────────────────────────────────────── */
.match-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.75rem 2rem;
  margin-bottom: 1.5rem;
}

/* ── DUEL BAR (firma del diseño) ─────────────────────────────────────────────── */
.duel-wrapper {
  margin: 1.5rem 0 1rem;
}
.duel-teams {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 0.6rem;
}
.duel-team-home { text-align: left; }
.duel-team-away { text-align: right; }
.duel-name {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(1.2rem, 2.5vw, 1.8rem);
  letter-spacing: 0.05em;
  color: var(--text);
}
.duel-pct-home {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(2rem, 5vw, 3.5rem);
  color: var(--home-clr);
  line-height: 1;
}
.duel-pct-away {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(2rem, 5vw, 3.5rem);
  color: var(--away-clr);
  line-height: 1;
}
.duel-bar-track {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: var(--border);
  overflow: hidden;
  display: flex;
}
.duel-bar-home { height: 100%; background: var(--home-clr); border-radius: 4px 0 0 4px; }
.duel-bar-draw { height: 100%; background: var(--draw-clr); }
.duel-bar-away { height: 100%; background: var(--away-clr); border-radius: 0 4px 4px 0; }
.duel-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 0.4rem;
  font-size: 0.72rem;
  color: var(--muted);
  letter-spacing: 0.05em;
}
.duel-draw-center {
  text-align: center;
  flex: 1;
}
.duel-draw-pct {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.2rem;
  color: var(--draw-clr);
}

/* ── STAT CHIPS ──────────────────────────────────────────────────────────────── */
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.25rem;
}
.chip {
  background: rgba(30,45,64,0.7);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.5rem 0.9rem;
  min-width: 90px;
  text-align: center;
}
.chip-val {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.4rem;
  color: var(--text);
  line-height: 1;
}
.chip-lbl {
  font-size: 0.65rem;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 0.1rem;
}

/* ── RANKING TABLE ───────────────────────────────────────────────────────────── */
.rank-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.rank-row:hover { background: var(--surface); }
.rank-num {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.3rem;
  color: var(--muted);
  width: 2rem;
  text-align: center;
}
.rank-num.top3 { color: var(--amber); }
.rank-team { flex: 1; font-weight: 500; }
.rank-bar-wrap { flex: 2; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.rank-bar-fill { height: 100%; background: var(--cyan); border-radius: 3px; }
.rank-val {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.1rem;
  color: var(--cyan);
  width: 4.5rem;
  text-align: right;
}

/* ── SIMULATION ──────────────────────────────────────────────────────────────── */
.sim-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}
.sim-medal {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.5rem;
  width: 2.5rem;
  text-align: center;
}
.sim-team { flex: 1; font-weight: 500; }
.sim-bar-wrap { flex: 2; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.sim-bar-fill { height: 100%; background: linear-gradient(90deg, var(--cyan), var(--amber)); border-radius: 4px; }
.sim-pct {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1.2rem;
  color: var(--amber);
  width: 4rem;
  text-align: right;
}

/* ── DIVIDER ─────────────────────────────────────────────────────────────────── */
.section-divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 3rem 0 2.5rem;
}

/* ── BUTTONS ─────────────────────────────────────────────────────────────────── */
.stButton > button {
  background: var(--cyan) !important;
  color: #0A0E1A !important;
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: 1rem !important;
  letter-spacing: 0.1em !important;
  border: none !important;
  border-radius: 8px !important;
  padding: 0.6rem 1.5rem !important;
  transition: opacity 0.15s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* ── SELECTBOX / INPUTS ──────────────────────────────────────────────────────── */
[data-baseweb="select"] > div {
  background: var(--surface) !important;
  border-color: var(--border) !important;
  border-radius: 8px !important;
}
label { color: var(--muted) !important; font-size: 0.75rem !important;
        letter-spacing: 0.08em !important; text-transform: uppercase !important; }

/* ── DOWNLOAD BUTTONS ────────────────────────────────────────────────────────── */
.stDownloadButton > button {
  background: transparent !important;
  color: var(--cyan) !important;
  border: 1px solid var(--border) !important;
  font-size: 0.8rem !important;
  padding: 0.4rem 1rem !important;
  letter-spacing: 0.05em !important;
}
.stDownloadButton > button:hover { border-color: var(--cyan) !important; }

/* ── ALERTS ──────────────────────────────────────────────────────────────────── */
.stAlert { border-radius: 8px !important; }

/* ── RESPONSIVE ──────────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .duel-pct-home, .duel-pct-away { font-size: 2.2rem; }
  .chip-row { gap: 0.4rem; }
  .rank-bar-wrap { display: none; }
  .sim-bar-wrap { display: none; }
}
"""

st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail
        super().__init__(f"{status}: {detail}")

def _detail(r):
    try: return r.json().get("detail", r.text)
    except: return r.text

def api_get(path, **params):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=60)
    if not r.ok: raise ApiError(r.status_code, _detail(r))
    return r.json()

def _to_pdf(df: pd.DataFrame, title: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    data = [list(df.columns)] + df.astype(str).values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#111827")),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.white),
        ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#1E2D40")),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 9),
    ]))
    doc.build([Paragraph(title, styles["Title"]), Spacer(1, 12), table])
    return buf.getvalue()

def pct(v: float) -> str: return f"{v*100:.1f}%"


# ── Data fetch ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def get_health():
    try: return api_get("/health")
    except: return {}

@st.cache_data(ttl=30)
def get_elo():
    try: return api_get("/elo-rankings")
    except: return []

health  = get_health()
elo_rows = get_elo()
teams   = sorted(r["team"] for r in elo_rows) if elo_rows else []
n_teams = health.get("teams_loaded", 0)
dc_ok   = health.get("dc_ready", False)
kl_ok   = health.get("klement_factors_loaded", 0) > 0
xg_ok   = health.get("form_model_ready", False)


# ── HERO ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <p class="hero-title">WORLD CUP<span> PREDICTOR</span></p>
  <p class="hero-sub">Motor probabilístico · Elo · Dixon-Coles · Klement · Monte Carlo</p>
</div>
""", unsafe_allow_html=True)

# Status pills
pills_html = '<div class="pill-row">'
pills_html += f'<span class="pill {"pill-ok" if n_teams>0 else "pill-off"}">⚡ {n_teams} equipos</span>'
pills_html += f'<span class="pill {"pill-ok" if dc_ok else "pill-off"}">Dixon-Coles {"✓" if dc_ok else "—"}</span>'
pills_html += f'<span class="pill {"pill-ok" if kl_ok else "pill-warn"}">Klement {"✓" if kl_ok else "sin factores"}</span>'
pills_html += f'<span class="pill {"pill-ok" if xg_ok else "pill-warn"}">XGBoost {"✓" if xg_ok else "sin entrenar"}</span>'
pills_html += '</div>'
st.markdown(pills_html, unsafe_allow_html=True)


# ── SECCIÓN 1: PREDICCIÓN DE PARTIDO ──────────────────────────────────────────
st.markdown('<p class="section-label">Análisis</p><h2 class="section-title">PREDICCIÓN DE PARTIDO</h2>', unsafe_allow_html=True)

if not teams:
    st.warning("Sin datos. Carga results.csv y llama a /load-from-db para empezar.")
else:
    modelos = ["hybrid", "elo", "dixon_coles"] + (["klement"] if kl_ok else [])

    col1, col2, col3, col4 = st.columns([3, 3, 2, 1])
    home    = col1.selectbox("Local", teams, index=teams.index("Brazil") if "Brazil" in teams else 0)
    away    = col2.selectbox("Visitante", teams, index=teams.index("Argentina") if "Argentina" in teams else min(1, len(teams)-1))
    model   = col3.selectbox("Modelo", modelos)
    neutral = col4.checkbox("Neutral", value=True)

    predict_btn = st.button("PREDECIR PARTIDO", type="primary")

    if predict_btn:
        try:
            res = api_get("/predict-match", home=home, away=away,
                          model=model, neutral=neutral)
        except ApiError as e:
            st.error(f"{e.detail}")
            res = None

        if res:
            ph, pd_, pa = res["home_win"], res["draw"], res["away_win"]

            # Duel bar HTML (firma del diseño)
            duel_html = f"""
<div class="match-card">
  <div class="duel-wrapper">
    <div class="duel-teams">
      <div class="duel-team-home">
        <div class="duel-name">{home}</div>
        <div class="duel-pct-home">{pct(ph)}</div>
      </div>
      <div style="text-align:center">
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1rem;
                    color:var(--muted);letter-spacing:.15em">VS</div>
        <div class="duel-draw-pct">{pct(pd_)}</div>
        <div style="font-size:.65rem;color:var(--muted);
                    text-transform:uppercase;letter-spacing:.1em">Empate</div>
      </div>
      <div class="duel-team-away">
        <div class="duel-name" style="text-align:right">{away}</div>
        <div class="duel-pct-away" style="text-align:right">{pct(pa)}</div>
      </div>
    </div>
    <div class="duel-bar-track">
      <div class="duel-bar-home" style="width:{ph*100:.1f}%"></div>
      <div class="duel-bar-draw" style="width:{pd_*100:.1f}%"></div>
      <div class="duel-bar-away" style="width:{pa*100:.1f}%"></div>
    </div>
    <div class="duel-labels">
      <span>Victoria local</span>
      <span>Empate</span>
      <span>Victoria visitante</span>
    </div>
  </div>
</div>"""
            st.markdown(duel_html, unsafe_allow_html=True)

            # Chips adicionales
            winner = home if ph > pa and ph > pd_ else (away if pa > ph and pa > pd_ else "Empate")
            winner_clr = "var(--home-clr)" if winner == home else ("var(--away-clr)" if winner == away else "var(--draw-clr)")
            chips_html = f"""
<div class="chip-row">
  <div class="chip">
    <div class="chip-val" style="color:{winner_clr}">{winner}</div>
    <div class="chip-lbl">Resultado más probable</div>
  </div>
  <div class="chip">
    <div class="chip-val">{res.get("source","hybrid").split("(")[0].upper()}</div>
    <div class="chip-lbl">Modelo</div>
  </div>
  <div class="chip">
    <div class="chip-val" style="color:var(--home-clr)">{pct(ph)}</div>
    <div class="chip-lbl">P(local)</div>
  </div>
  <div class="chip">
    <div class="chip-val" style="color:var(--draw-clr)">{pct(pd_)}</div>
    <div class="chip-lbl">P(empate)</div>
  </div>
  <div class="chip">
    <div class="chip-val" style="color:var(--away-clr)">{pct(pa)}</div>
    <div class="chip-lbl">P(visitante)</div>
  </div>
</div>"""
            st.markdown(chips_html, unsafe_allow_html=True)

            # Exports
            df_exp = pd.DataFrame({
                "Resultado": [f"{home} gana", "Empate", f"{away} gana"],
                "Probabilidad": [ph, pd_, pa],
                "Modelo": [res.get("source")] * 3,
            })
            st.write("")
            c_xl, c_pdf, _ = st.columns([1, 1, 4])
            buf = io.BytesIO()
            df_exp.to_excel(buf, index=False, engine="openpyxl")
            c_xl.download_button("↓ Excel", buf.getvalue(),
                                  file_name=f"{home}_vs_{away}.xlsx",
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            c_pdf.download_button("↓ PDF", _to_pdf(df_exp, f"{home} vs {away}"),
                                   file_name=f"{home}_vs_{away}.pdf",
                                   mime="application/pdf")


# ── SECCIÓN 2: RANKING ELO ─────────────────────────────────────────────────────
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown('<p class="section-label">Clasificación</p><h2 class="section-title">RANKING ELO MUNDIAL</h2>', unsafe_allow_html=True)

if elo_rows:
    top_n = st.slider("Equipos a mostrar", 10, min(50, len(elo_rows)), 20, step=5)
    df_elo = pd.DataFrame(elo_rows).head(top_n)
    max_r  = df_elo["rating"].max()

    rows_html = ""
    for _, row in df_elo.iterrows():
        rk = int(row["rank"])
        top_cls = "top3" if rk <= 3 else ""
        bar_w = row["rating"] / max_r * 100
        medal = "🥇" if rk == 1 else ("🥈" if rk == 2 else ("🥉" if rk == 3 else ""))
        rows_html += f"""
<div class="rank-row">
  <div class="rank-num {top_cls}">{medal or rk}</div>
  <div class="rank-team">{row['team']}</div>
  <div class="rank-bar-wrap"><div class="rank-bar-fill" style="width:{bar_w:.1f}%"></div></div>
  <div class="rank-val">{row['rating']:.0f}</div>
</div>"""

    st.markdown(rows_html, unsafe_allow_html=True)

    # Compact chart for top 10
    st.write("")
    fig = go.Figure(go.Bar(
        x=df_elo["rating"].head(10),
        y=df_elo["team"].head(10),
        orientation="h",
        marker=dict(
            color=df_elo["rating"].head(10),
            colorscale=[[0,"#1E2D40"],[0.5,"#00D4FF"],[1,"#F0B429"]],
            showscale=False,
        ),
        text=[f"{v:.0f}" for v in df_elo["rating"].head(10)],
        textposition="outside",
        textfont=dict(color="#E2E8F0", size=11),
    ))
    fig.update_layout(
        paper_bgcolor="#0A0E1A", plot_bgcolor="#0A0E1A",
        height=360, margin=dict(l=0, r=60, t=8, b=8),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(tickfont=dict(color="#E2E8F0", size=12), autorange="reversed"),
        bargap=0.3,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Carga el historial de partidos para ver el ranking.")


# ── SECCIÓN 3: SIMULACIÓN ──────────────────────────────────────────────────────
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown('<p class="section-label">Monte Carlo</p><h2 class="section-title">SIMULACIÓN DE TORNEO</h2>', unsafe_allow_html=True)

if not teams:
    st.info("Sin equipos cargados.")
else:
    sim_col1, sim_col2 = st.columns([2, 1])
    n_sims = sim_col1.select_slider(
        "Simulaciones",
        options=[10_000, 50_000, 100_000, 1_000_000],
        value=10_000,
        format_func=lambda x: f"{x:,}",
    )
    sim_col2.write("")
    run_sim = sim_col2.button("SIMULAR TORNEO", type="primary")

    if run_sim:
        try:
            with st.spinner("Calculando probabilidades…"):
                res = api_get("/team-probabilities", n_sims=n_sims)
        except ApiError as e:
            st.error(f"{e.detail}")
            res = None

        if res:
            champ = sorted(res["champion"].items(), key=lambda kv: -kv[1])
            max_p = champ[0][1] if champ else 1

            # Top 3 heroes
            h1, h2, h3 = st.columns(3)
            for col, (team, prob), medal in zip(
                [h1, h2, h3], champ[:3], ["🥇","🥈","🥉"]
            ):
                col.markdown(f"""
<div style="background:var(--surface);border:1px solid var(--border);
            border-radius:var(--radius);padding:1.25rem;text-align:center">
  <div style="font-size:2rem">{medal}</div>
  <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;
              margin:.3rem 0">{team}</div>
  <div style="font-family:'Bebas Neue',sans-serif;font-size:2.5rem;
              color:var(--amber)">{pct(prob)}</div>
  <div style="font-size:.65rem;color:var(--muted);text-transform:uppercase;
              letter-spacing:.1em">Prob. campeón</div>
</div>""", unsafe_allow_html=True)

            st.write("")

            # Rest of top 15
            rest_html = ""
            for i, (team, prob) in enumerate(champ[3:15], start=4):
                bar_w = prob / max_p * 100
                rest_html += f"""
<div class="sim-card">
  <div class="sim-medal" style="color:var(--muted);font-size:1rem">{i}</div>
  <div class="sim-team">{team}</div>
  <div class="sim-bar-wrap"><div class="sim-bar-fill" style="width:{bar_w:.1f}%"></div></div>
  <div class="sim-pct">{pct(prob)}</div>
</div>"""
            if rest_html:
                st.markdown(rest_html, unsafe_allow_html=True)

            # Export
            df_sim = pd.DataFrame(champ, columns=["Equipo", "P(campeón)"])
            buf = io.BytesIO()
            df_sim.to_excel(buf, index=False, engine="openpyxl")
            st.write("")
            st.download_button("↓ Exportar resultados Excel", buf.getvalue(),
                                file_name=f"simulacion_{n_sims}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:3rem 0 1rem;
            color:var(--muted);font-size:.75rem;letter-spacing:.08em">
  WORLD CUP PREDICTOR AI &nbsp;·&nbsp;
  Elo &nbsp;·&nbsp; Dixon-Coles &nbsp;·&nbsp; Klement &nbsp;·&nbsp; Monte Carlo
</div>
""", unsafe_allow_html=True)
