import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

from utils.hotspot_engine import load_hotspots, build_hotspots, _load_ds1, get_historical_accident_points
from utils.risk_model import train_model, load_or_train
from utils.route_analyzer import geocode, get_road_route, find_hotspots_on_route
from utils.ai_description import get_live_weather, generate_alert_description
from utils.auto_retrain import start_scheduler, get_retrain_log
from utils.ui_components import GLOBAL_CSS
from utils.route_safety import (
    calculate_route_distance_km,
    calculate_route_safety_score,
    get_safety_recommendation,
)
from utils.report_generator import generate_csv_report, generate_pdf_report
from utils.weather_advisor import get_weather_safety_advisory
from utils.location_service import search_location_suggestions, suggest_typo_corrections, resolve_location
from config import WARN_RADIUS_M

st.set_page_config(
    page_title="SafeRoute — Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── init ──────────────────────────────────────────────────────────────────────
start_scheduler()

if "hotspots" not in st.session_state:
    with st.spinner("Indexing hotspot database..."):
        st.session_state["hotspots"] = load_hotspots()
if "clf" not in st.session_state:
    with st.spinner("Loading risk model..."):
        df = _load_ds1()
        st.session_state["clf"]      = load_or_train(df)
        st.session_state["train_df"] = df
if "satellite" not in st.session_state:
    st.session_state["satellite"] = False
if "_from_val" not in st.session_state:
    st.session_state["_from_val"] = ""
if "_to_val" not in st.session_state:
    st.session_state["_to_val"] = ""

hotspots = st.session_state["hotspots"]
high_hs  = len(hotspots[hotspots["risk_level"] == "HIGH"])
med_hs   = len(hotspots[hotspots["risk_level"] == "MEDIUM"])

# ── TOP NAV ───────────────────────────────────────────────────────────────────
components.html(f"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Space+Mono&display=swap" rel="stylesheet">
<div style="
  background:linear-gradient(180deg,#06060E 0%,rgba(6,6,14,.95) 100%);
  border-bottom:1px solid rgba(0,212,255,.12);
  padding:0 28px;height:62px;
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;
  backdrop-filter:blur(12px);
">
  <div style="display:flex;align-items:center;gap:14px">
    <div style="width:36px;height:36px;border-radius:50%;
      background:rgba(0,212,255,.1);border:1px solid rgba(0,212,255,.3);
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 0 16px rgba(0,212,255,.2)">
      <i class="fa-solid fa-shield-halved" style="color:#00D4FF;font-size:.9rem"></i>
    </div>
    <div style="font-family:'Orbitron',monospace;font-size:1rem;font-weight:700;
                letter-spacing:2px;color:#F0F0F0">
      SAFE<span style="color:#00D4FF">ROUTE</span>
    </div>
    <div style="background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.2);
      border-radius:4px;padding:2px 8px;
      font-family:'Space Mono',monospace;font-size:.58rem;
      letter-spacing:1.5px;color:#00D4FF;">AI NAVIGATOR</div>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <div style="display:inline-flex;align-items:center;gap:8px;
      background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.25);
      border-radius:8px;padding:6px 14px">
      <i class="fa-solid fa-database" style="color:#00D4FF;font-size:.72rem"></i>
      <div>
        <div style="font-family:'Orbitron',monospace;font-size:.78rem;font-weight:700;color:#00D4FF">{len(hotspots)}</div>
        <div style="font-family:'Space Mono',monospace;font-size:.58rem;color:rgba(0,212,255,.7)">HOTSPOTS</div>
      </div>
    </div>
    <div style="display:inline-flex;align-items:center;gap:8px;
      background:rgba(255,59,59,.08);border:1px solid rgba(255,59,59,.25);
      border-radius:8px;padding:6px 14px">
      <i class="fa-solid fa-circle-exclamation" style="color:#FF3B3B;font-size:.72rem"></i>
      <div>
        <div style="font-family:'Orbitron',monospace;font-size:.78rem;font-weight:700;color:#FF3B3B">{high_hs}</div>
        <div style="font-family:'Space Mono',monospace;font-size:.58rem;color:rgba(255,59,59,.7)">HIGH RISK</div>
      </div>
    </div>
    <div style="display:inline-flex;align-items:center;gap:8px;
      background:rgba(255,140,66,.08);border:1px solid rgba(255,140,66,.25);
      border-radius:8px;padding:6px 14px">
      <i class="fa-solid fa-city" style="color:#FF8C42;font-size:.72rem"></i>
      <div>
        <div style="font-family:'Orbitron',monospace;font-size:.78rem;font-weight:700;color:#FF8C42">8</div>
        <div style="font-family:'Space Mono',monospace;font-size:.58rem;color:rgba(255,140,66,.7)">CITIES</div>
      </div>
    </div>
  </div>
</div>
""", height=70)

# ── ROUTE INPUT ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="
  background:linear-gradient(180deg,#0D0D16,#0A0A0F);
  padding:28px 28px 20px;
  border-bottom:1px solid rgba(0,212,255,.08);
">
  <div style="font-family:'Space Mono',monospace;font-size:.6rem;
              letter-spacing:2.5px;color:#8A8A9A;margin-bottom:14px">
    <i class="fa-solid fa-route" style="color:#00D4FF;margin-right:6px"></i>
    ROUTE CONFIGURATION
  </div>
""", unsafe_allow_html=True)

ci1, ci2, ci3, ci4 = st.columns([5, 5, 2, 1])
with ci1:
    from_txt = st.text_input("from", placeholder="FROM — origin city or address",
                              label_visibility="collapsed", key="from_inp",
                              value=st.session_state["_from_val"])
    # Typo / autocomplete suggestion for Origin
    if from_txt.strip() and len(from_txt.strip()) >= 3:
        from_typos = suggest_typo_corrections(from_txt.strip(), limit=1)
        if from_typos and from_typos[0]["city"].lower() != from_txt.strip().lower():
            st.markdown(f"""
            <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#00D4FF;margin-top:4px">
              💡 Did you mean: <b>{from_typos[0]['display_name']}</b>?
            </div>""", unsafe_allow_html=True)
with ci2:
    to_txt = st.text_input("to", placeholder="TO — destination city or address",
                            label_visibility="collapsed", key="to_inp",
                            value=st.session_state["_to_val"])
    # Typo / autocomplete suggestion for Destination
    if to_txt.strip() and len(to_txt.strip()) >= 3:
        to_typos = suggest_typo_corrections(to_txt.strip(), limit=1)
        if to_typos and to_typos[0]["city"].lower() != to_txt.strip().lower():
            st.markdown(f"""
            <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#00D4FF;margin-top:4px">
              💡 Did you mean: <b>{to_typos[0]['display_name']}</b>?
            </div>""", unsafe_allow_html=True)
with ci3:
    scan_route = st.button("SCAN ROUTE", use_container_width=True, type="primary")
with ci4:
    if st.button("SAT" if not st.session_state["satellite"] else "MAP",
                 use_container_width=True, key="sat_btn"):
        st.session_state["satellite"] = not st.session_state["satellite"]
        st.rerun()

# city quick-select pills
st.markdown("""
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;padding-bottom:4px">
  <span style="font-family:'Space Mono',monospace;font-size:.58rem;
               letter-spacing:1.5px;color:#8A8A9A;align-self:center">QUICK SELECT:</span>
""", unsafe_allow_html=True)

cities = ["Chennai","Mumbai","Delhi","Bangalore","Hyderabad","Pune","Kolkata","Chandigarh"]
pill_cols = st.columns(len(cities))
for i, city in enumerate(cities):
    with pill_cols[i]:
        if st.button(city, key=f"city_{i}", use_container_width=True):
            st.session_state["_from_val"] = city
            st.rerun()

st.markdown('</div></div>', unsafe_allow_html=True)

# ── ROUTE LOGIC ───────────────────────────────────────────────────────────────
if scan_route:
    if not from_txt.strip() or not to_txt.strip():
        st.warning("Enter both From and To locations.")
    else:
        steps = [
            "Resolving locations and correcting typos...",
            "Fetching road segments from OSRM...",
            "Scanning 1,126 accident hotspots...",
            "Fetching live weather data...",
            "Generating AI safety briefs...",
            "Route analysis complete.",
        ]
        prog = st.progress(0)
        status_box = st.empty()

        status_box.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.15);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#00D4FF;letter-spacing:.5px">
          <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>
          {steps[0]}
        </div>""", unsafe_allow_html=True)

        start_res = resolve_location(from_txt.strip())
        prog.progress(15)
        end_res   = resolve_location(to_txt.strip())
        prog.progress(30)

        if not start_res:
            typos = suggest_typo_corrections(from_txt.strip())
            hint = f" Did you mean: **{typos[0]['display_name']}**?" if typos else " Please check spelling or select from quick list."
            st.error(f"Location not found for origin: '{from_txt}'.{hint}")
            prog.empty(); status_box.empty(); st.stop()
        if not end_res:
            typos = suggest_typo_corrections(to_txt.strip())
            hint = f" Did you mean: **{typos[0]['display_name']}**?" if typos else " Please check spelling or select from quick list."
            st.error(f"Location not found for destination: '{to_txt}'.{hint}")
            prog.empty(); status_box.empty(); st.stop()

        start_c   = (start_res["lat"], start_res["lon"])
        end_c     = (end_res["lat"], end_res["lon"])
        start_lbl = start_res["display_name"]
        end_lbl   = end_res["display_name"]

        status_box.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.15);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#00D4FF;letter-spacing:.5px">
          <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>
          {steps[1]}
        </div>""", unsafe_allow_html=True)

        route = get_road_route(start_c, end_c)
        prog.progress(55)

        status_box.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.15);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#00D4FF;letter-spacing:.5px">
          <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>
          {steps[2]}
        </div>""", unsafe_allow_html=True)

        alerts = find_hotspots_on_route(route, hotspots, WARN_RADIUS_M)
        prog.progress(70)

        status_box.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.15);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#00D4FF;letter-spacing:.5px">
          <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>
          {steps[3]}
        </div>""", unsafe_allow_html=True)

        mid_pt  = route[len(route) // 2]
        weather = get_live_weather(mid_pt[0], mid_pt[1])
        prog.progress(85)

        status_box.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.15);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#00D4FF;letter-spacing:.5px">
          <i class="fa-solid fa-circle-notch fa-spin" style="margin-right:8px"></i>
          {steps[4]}
        </div>""", unsafe_allow_html=True)

        enriched = []
        for a in alerts:
            desc = generate_alert_description(a, weather)
            rec  = get_safety_recommendation(a)
            enriched.append({**a, "weather": weather, "ai_desc": desc, "safety_recommendation": rec})
        prog.progress(100)

        route_dist_km = calculate_route_distance_km(route)

        status_box.markdown(f"""
        <div style="background:rgba(57,255,20,.05);border:1px solid rgba(57,255,20,.2);
                    border-radius:10px;padding:12px 18px;
                    font-family:'Space Mono',monospace;font-size:.75rem;
                    color:#39FF14;letter-spacing:.5px">
          <i class="fa-solid fa-circle-check" style="margin-right:8px"></i>
          {steps[5]}
        </div>""", unsafe_allow_html=True)

        st.session_state.update({
            "route": route, "alerts": enriched,
            "route_distance_km": route_dist_km,
            "start": start_c, "end": end_c,
            "start_label": start_lbl,
            "end_label":   end_lbl,
            "weather":     weather,
            "_from_val":   "",
            "_to_val":     "",
        })

        import time; time.sleep(0.6)
        prog.empty(); status_box.empty()
        st.rerun()

# ── ROUTE RISK SUMMARY DASHBOARD (FEATURE 2 & 3) ──────────────────────────────
if "alerts" in st.session_state:
    alerts = st.session_state["alerts"]
    route_dist_km = st.session_state.get("route_distance_km")
    if route_dist_km is None and "route" in st.session_state:
        route_dist_km = calculate_route_distance_km(st.session_state["route"])
        st.session_state["route_distance_km"] = route_dist_km
    if route_dist_km is None:
        route_dist_km = 0.0

    safety_info = calculate_route_safety_score(alerts, route_distance_km=route_dist_km)
    score       = safety_info["safety_score"]
    risk_cat    = safety_info["risk_category"]
    risk_col    = safety_info["risk_color"]
    high_n      = safety_info["high_count"]
    med_n       = safety_info["medium_count"]
    low_n       = safety_info["low_count"]
    total_hs    = safety_info["total_hotspots"]
    w           = st.session_state.get("weather", {})
    s_lbl       = st.session_state.get("start_label", "Origin")
    e_lbl       = st.session_state.get("end_label", "Destination")

    # Adverse factor indicators
    fatal_zones = sum(1 for a in alerts if a.get("fatal", 0) > 0)
    weather_hazard_zones = sum(
        1 for a in alerts if str(a.get("top_weather", "")).lower() in ["fog", "foggy", "rain", "rainy", "stormy"]
    )

    # Dashboard Header
    st.markdown(f"""
    <div style="background:linear-gradient(180deg,#0D0D18 0%,#090910 100%);
                padding:20px 28px 16px;border-bottom:1px solid rgba(0,212,255,.12)">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
        <div>
          <div style="font-family:'Space Mono',monospace;font-size:.62rem;letter-spacing:2px;
                      color:#00D4FF;margin-bottom:4px">
            <i class="fa-solid fa-gauge-high" style="margin-right:6px"></i>
            ROUTE RISK SUMMARY DASHBOARD
          </div>
          <div style="font-family:'Orbitron',monospace;font-size:1.2rem;font-weight:700;color:#F0F0F0">
            {s_lbl.upper()} <span style="color:#00D4FF">➔</span> {e_lbl.upper()}
          </div>
        </div>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <div style="font-family:'Space Mono',monospace;font-size:.68rem;color:#8A8A9A;
                      background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
                      border-radius:20px;padding:6px 14px">
            <i class="fa-solid fa-road" style="color:#00D4FF;margin-right:6px"></i>
            {route_dist_km:.1f} KM CORRIDOR
          </div>
          <div style="font-family:'Orbitron',monospace;font-size:.68rem;font-weight:700;
                      color:{risk_col};background:{risk_col}15;border:1px solid {risk_col}45;
                      border-radius:20px;padding:6px 14px;letter-spacing:1px">
            <i class="fa-solid fa-shield-halved" style="margin-right:6px"></i>
            {risk_cat}
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Main Dashboard Body: Score Card (Left) & Risk Distribution Chart (Right)
    dash_col1, dash_col2 = st.columns([5, 5])

    with dash_col1:
        st.markdown(f"""
        <div style="margin:16px 0 16px 28px;background:rgba(255,255,255,.03);
                    border:1px solid rgba(255,255,255,.08);border-left:5px solid {risk_col};
                    border-radius:14px;padding:22px 24px;box-shadow:0 0 25px {risk_col}15">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div style="font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:2px;
                          color:#8A8A9A;margin-bottom:6px">
                ESTIMATED ROUTE SAFETY SCORE
              </div>
              <div style="display:flex;align-items:baseline;gap:6px">
                <span style="font-family:'Orbitron',monospace;font-size:3.2rem;font-weight:900;
                             color:{risk_col};line-height:1;text-shadow:0 0 24px {risk_col}55">
                  {score}
                </span>
                <span style="font-family:'Space Mono',monospace;font-size:1.1rem;color:#8A8A9A;font-weight:700">
                  / 100
                </span>
              </div>
            </div>
            <div style="text-align:right">
              <span style="display:inline-block;background:{risk_col}18;color:{risk_col};
                           border:1px solid {risk_col}40;border-radius:8px;padding:5px 12px;
                           font-family:'Orbitron',monospace;font-size:.7rem;font-weight:700;
                           letter-spacing:1px">
                {risk_cat}
              </span>
              <div style="font-family:'Space Mono',monospace;font-size:.6rem;color:#8A8A9A;margin-top:6px">
                {total_hs} Hotspots on Route
              </div>
            </div>
          </div>

          <!-- Progress bar visualization -->
          <div style="background:rgba(255,255,255,.06);height:8px;border-radius:4px;
                      margin:16px 0 12px;overflow:hidden">
            <div style="background:linear-gradient(90deg,#FF3B3B 0%,#FF8C42 60%,#39FF14 100%);
                        width:{max(5, score)}%;height:100%;border-radius:4px;
                        box-shadow:0 0 12px {risk_col}80"></div>
          </div>

          <div style="display:flex;justify-content:space-between;font-family:'Space Mono',monospace;
                      font-size:.6rem;color:#8A8A9A;margin-bottom:14px">
            <span>HIGH RISK (0-59)</span>
            <span>MODERATE (60-79)</span>
            <span>LOWER RISK (80-100)</span>
          </div>

          <div style="border-top:1px solid rgba(255,255,255,.06);padding-top:12px;
                      font-family:'Rajdhani',sans-serif;font-size:.82rem;color:#8A8A9A;line-height:1.4">
            <i class="fa-solid fa-circle-info" style="color:#00D4FF;margin-right:6px"></i>
            <strong>Heuristic Exposure Index:</strong> {safety_info['exposure_density']:.2f} weighted risk pts / 100 km.
            <div style="font-size:.75rem;color:#666677;margin-top:3px;font-style:italic">
              *Heuristic route risk indicator based on historical hotspot density and severity exposure.
              Does not represent guaranteed safety or statistical collision probability.
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with dash_col2:
        # Plotly Risk Distribution Chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["HIGH RISK", "MEDIUM RISK", "LOW RISK"],
            y=[high_n, med_n, low_n],
            marker=dict(
                color=["#FF3B3B", "#FF8C42", "#39FF14"],
                line=dict(color=["rgba(255,59,59,0.8)", "rgba(255,140,66,0.8)", "rgba(57,255,20,0.8)"], width=1.5),
            ),
            text=[f"{high_n}", f"{med_n}", f"{low_n}"],
            textposition="auto",
            textfont=dict(family="Space Mono, monospace", size=12, color="#FFFFFF"),
        ))
        fig.update_layout(
            title=dict(
                text="HOTSPOT RISK CLASSIFICATION BREAKDOWN",
                font=dict(family="Orbitron, monospace", size=11, color="#00D4FF"),
                x=0.02,
                y=0.95,
            ),
            height=215,
            margin=dict(l=15, r=28, t=35, b=25),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,0.02)",
            font=dict(color="#F0F0F0", family="Rajdhani, sans-serif"),
            xaxis=dict(
                showgrid=False,
                tickfont=dict(family="Space Mono, monospace", size=10, color="#8A8A9A"),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(255,255,255,0.06)",
                title=dict(
                    text="Hotspots",
                    font=dict(family="Space Mono, monospace", size=10, color="#8A8A9A"),
                ),
                tickfont=dict(family="Space Mono, monospace", size=10, color="#8A8A9A"),
                zeroline=False,
                dtick=max(1, max(high_n, med_n, low_n, 1)),
            ),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Metric Cards Grid (6 indicators)
    st.markdown('<div style="padding:0 28px 16px">', unsafe_allow_html=True)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.18);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:#00D4FF">
            {route_dist_km:.1f} <span style="font-size:.7rem">KM</span>
          </div>
          <div style="font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            ROUTE DISTANCE
          </div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:#F0F0F0">
            {total_hs}
          </div>
          <div style="font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            TOTAL HOTSPOTS
          </div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div style="background:rgba(255,59,59,.06);border:1px solid rgba(255,59,59,.2);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:#FF3B3B">
            {high_n}
          </div>
          <div style="font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            HIGH RISK ZONES
          </div>
        </div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div style="background:rgba(255,140,66,.06);border:1px solid rgba(255,140,66,.2);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:#FF8C42">
            {med_n}
          </div>
          <div style="font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            MEDIUM RISK ZONES
          </div>
        </div>""", unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div style="background:rgba(57,255,20,.05);border:1px solid rgba(57,255,20,.18);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:#39FF14">
            {low_n}
          </div>
          <div style="font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            LOW RISK ZONES
          </div>
        </div>""", unsafe_allow_html=True)
    with m6:
        _w_is_fallback = w.get("is_fallback", True)
        _w_color = "#8A8A9A" if _w_is_fallback else "#00D4FF"
        _w_temp = w.get("temp", 28)
        _w_temp_str = f"{_w_temp:.0f}°C"
        _w_humidity = w.get("humidity")
        _w_sub = "NO API KEY — DEFAULTS SHOWN" if _w_is_fallback else "ROUTE MIDPOINT WEATHER"
        _w_desc = w.get("description", "Clear")
        _w_wind = w.get("wind_speed", 5.0)

        if _w_is_fallback:
            _w_extra = '<div style="font-size:.65rem;color:#FF8C42;margin-top:2px">Set API key in config.py</div>'
        elif _w_humidity is not None:
            _w_extra = f'<div style="font-size:.65rem;color:#8A8A9A;margin-top:2px">Humidity: {_w_humidity}% • Wind: {_w_wind:.0f} km/h</div>'
        else:
            _w_extra = ''

        st.markdown(f"""
        <div style="background:rgba(0,212,255,.05);border:1px solid rgba(0,212,255,.18);
                    border-radius:10px;padding:12px 14px;text-align:center">
          <div style="font-family:'Orbitron',monospace;font-size:.9rem;font-weight:700;color:{_w_color};line-height:1.3">
            {_w_desc}<br><span style="font-size:.75rem">{_w_temp_str}</span>
          </div>
          {_w_extra}
          <div style="font-family:'Space Mono',monospace;font-size:.52rem;letter-spacing:1px;color:#8A8A9A;margin-top:2px">
            {_w_sub}
          </div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── MAP ───────────────────────────────────────────────────────────────────────
def _add_tiles(m, satellite):
    if satellite:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery", name="Satellite", max_zoom=19,
        ).add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            attr="Esri Labels", name="Labels", overlay=True, opacity=0.9,
        ).add_to(m)
    else:
        folium.TileLayer(tiles="CartoDB positron", name="Street").add_to(m)


def _build_map():
    sat = st.session_state.get("satellite", False)

    if "route" not in st.session_state:
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=5, tiles=None)
        _add_tiles(m, sat)
        reg_points = get_historical_accident_points(route_coords=None, max_points=1500)
        if reg_points:
            HeatMap(
                reg_points,
                name="Accident Density Heatmap",
                min_opacity=0.25,
                radius=14,
                blur=18,
                show=True,
            ).add_to(m)
        folium.LayerControl(position="topright", collapsed=False).add_to(m)
        return m

    route  = st.session_state["route"]
    alerts = st.session_state["alerts"]
    start  = st.session_state["start"]
    end    = st.session_state["end"]
    s_lbl  = st.session_state["start_label"]
    e_lbl  = st.session_state["end_label"]

    mid = route[len(route) // 2]
    m   = folium.Map(location=mid, zoom_start=12, tiles=None, prefer_canvas=True)
    _add_tiles(m, sat)

    # Feature 6: Heatmap layer of historical accident concentrations near corridor
    heat_data = get_historical_accident_points(route_coords=route, max_points=2500)
    if heat_data:
        HeatMap(
            heat_data,
            name="Corridor Accident Heatmap",
            min_opacity=0.3,
            radius=16,
            blur=18,
            max_zoom=13,
            overlay=True,
            control=True,
            show=True,
        ).add_to(m)

    # Route glow — 3 layers
    folium.PolyLine(route, color="#00D4FF", weight=14, opacity=0.08).add_to(m)
    folium.PolyLine(route, color="#00AADD", weight=7,  opacity=0.5).add_to(m)
    folium.PolyLine(route, color="#00D4FF", weight=2,  opacity=0.95).add_to(m)

    # Risky segment overlays
    step = max(1, len(route) // 60)
    for a in alerts:
        clr = "#FF3B3B" if a["risk_level"] == "HIGH" else "#FF8C42"
        idx = a["route_idx"]
        seg = route[max(0, idx - step * 3): idx + step * 3 + 1]
        if len(seg) > 1:
            folium.PolyLine(seg, color=clr, weight=9, opacity=0.9).add_to(m)

    # Start
    folium.Marker(start, tooltip=f"START: {s_lbl}",
                  icon=folium.Icon(color="green", icon="circle", prefix="fa")).add_to(m)
    # End
    folium.Marker(end, tooltip=f"DESTINATION: {e_lbl}",
                  icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

    # Pulsing hotspot markers via CSS injection
    for i, a in enumerate(alerts):
        is_h  = a["risk_level"] == "HIGH"
        is_l  = a["risk_level"] == "LOW"
        clr   = "#FF3B3B" if is_h else ("#39FF14" if is_l else "#FF8C42")
        label = f"{a['risk_level']} RISK"
        w_d   = a.get("weather", {})
        night = a.get("night_pct", 0)

        popup = folium.Popup(f"""
        <div style='font-family:system-ui;padding:14px;min-width:245px;
                    background:#0D0D16;color:#F0F0F0;border-radius:10px;
                    border:1px solid {clr}44'>
          <div style='color:{clr};font-weight:800;font-size:.9rem;
                      letter-spacing:.5px;margin-bottom:10px;
                      padding-bottom:8px;border-bottom:1px solid {clr}33'>
            HOTSPOT {i+1} — {label}
          </div>
          <table style='width:100%;font-size:.78rem;border-collapse:collapse'>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Cluster ID</td>
                <td style='text-align:right;font-weight:700;color:#00D4FF'>#{a.get('cluster_id', 'N/A')}</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Total Accidents</td>
                <td style='text-align:right;font-weight:700;color:#F0F0F0'>{a.get('total_accidents', 'N/A')}</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Fatal</td>
                <td style='text-align:right;font-weight:700;color:#FF3B3B'>{a.get('fatal', 0)}</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Casualties</td>
                <td style='text-align:right;font-weight:700;color:#FF8C42'>{a.get('casualties', 0)}</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Primary Cause</td>
                <td style='text-align:right;font-weight:600;color:#F0F0F0'>{str(a.get('top_cause', '')).title()}</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Peak Hour</td>
                <td style='text-align:right;font-weight:600;color:#F0F0F0'>{a.get('peak_hour', 12):02d}:00</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Night Accidents</td>
                <td style='text-align:right;font-weight:600;color:#F0F0F0'>{night}%</td></tr>
            <tr><td style='color:#8A8A9A;padding:3px 0'>Weather Now</td>
                <td style='text-align:right;font-weight:600;color:#00D4FF'>{w_d.get('description','—')} {w_d.get('temp',0):.0f}°C</td></tr>
          </table>
          <div style='margin-top:10px;background:rgba(0,212,255,.08);border-radius:7px;
                      padding:9px 11px;font-size:.77rem;color:#A0A0C0;line-height:1.6;
                      border-left:3px solid #00D4FF'>
            {a.get('ai_desc', '')}
          </div>
          <div style='margin-top:8px;font-size:.7rem;color:#8A8A9A;text-align:center'>
            📍 Details in Hotspot Card #{i+1} below
          </div>
        </div>""", max_width=320)

        # Pulsing outer ring (CSS animation via DivIcon)
        folium.Marker(
            [a["hotspot_lat"], a["hotspot_lon"]],
            icon=folium.DivIcon(html=f"""
            <div style="position:relative;width:40px;height:40px;
                        margin-left:-20px;margin-top:-20px">
              <div style="position:absolute;width:40px;height:40px;border-radius:50%;
                   border:2px solid {clr};opacity:.6;
                   animation:pulse-ring 2s ease-out infinite"></div>
              <div style="position:absolute;width:26px;height:26px;top:7px;left:7px;
                   border-radius:50%;border:2px solid {clr};opacity:.4;
                   animation:pulse-ring 2s ease-out infinite;animation-delay:.4s"></div>
            </div>
            <style>
            @keyframes pulse-ring {{
              0%   {{transform:scale(1);opacity:.8}}
              70%  {{transform:scale(2.2);opacity:0}}
              100% {{transform:scale(1);opacity:0}}
            }}
            </style>""", icon_size=(40, 40), icon_anchor=(20, 20))
        ).add_to(m)

        # Solid core dot with popup
        folium.CircleMarker(
            [a["hotspot_lat"], a["hotspot_lon"]],
            radius=8, color="#fff", fill=True,
            fill_color=clr, fill_opacity=1.0, weight=2,
            popup=popup,
            tooltip=f"HOTSPOT {i+1} — {a['total_accidents']} accidents | Click for details",
        ).add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)
    return m


st.markdown('<div style="padding:0">', unsafe_allow_html=True)
st_folium(_build_map(), height=520, width=None, returned_objects=[],
          key=f"map_{st.session_state['satellite']}")
st.markdown("""
<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 28px 12px;font-family:'Space Mono',monospace;font-size:.62rem;color:#8A8A9A">
  <span><i class="fa-solid fa-layer-group" style="color:#00D4FF;margin-right:5px"></i>MAP CONTROLS: Toggle Street/Satellite layers & Accident Density HeatMap in top-right.</span>
  <span><i class="fa-solid fa-fire" style="color:#FF3B3B;margin-right:5px"></i>Heatmap visualizes historical collision density from Dataset 1.</span>
</div>
</div>""", unsafe_allow_html=True)

# ── FEATURE 1: HOTSPOT EXPLANATION CARDS ──────────────────────────────────────
if "alerts" in st.session_state:
    alerts = st.session_state["alerts"]

    if not alerts:
        st.markdown("""
        <div style="margin:24px 28px;padding:36px;text-align:center;
                    background:rgba(57,255,20,.04);
                    border:1px solid rgba(57,255,20,.15);border-radius:16px">
          <i class="fa-solid fa-shield-halved" style="font-size:2.5rem;
             color:#39FF14;text-shadow:0 0 20px rgba(57,255,20,.5);
             display:block;margin-bottom:14px"></i>
          <div style="font-family:'Orbitron',monospace;font-size:.9rem;
                      font-weight:700;color:#39FF14;letter-spacing:1px;
                      margin-bottom:8px">ALL CLEAR — NO HOTSPOTS DETECTED</div>
          <div style="font-family:'Rajdhani',sans-serif;font-size:.95rem;
                      color:#8A8A9A;font-weight:500">
            No historical accident hotspots detected within 500m of your route.
            Standard defensive driving caution is still recommended.
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="padding:24px 28px 8px">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
            <div style="font-family:'Space Mono',monospace;font-size:.65rem;
                        letter-spacing:2px;color:#00D4FF">
              <i class="fa-solid fa-id-card-clip" style="color:#00D4FF;margin-right:8px"></i>
              HOTSPOT EXPLANATION CARDS — COMPREHENSIVE RISK PROFILES
            </div>
            <div style="font-family:'Space Mono',monospace;font-size:.6rem;color:#8A8A9A">
              Showing detailed intelligence for detected corridor hotspots
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        # Hotspot Card Selector / Filter
        st.markdown('<div style="padding:0 28px 10px">', unsafe_allow_html=True)
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            card_options = ["Show All Hotspots"] + [
                f"Hotspot #{idx+1} — {al['risk_level']} Risk (Cluster #{al.get('cluster_id', 'N/A')})"
                for idx, al in enumerate(alerts)
            ]
            selected_card_filter = st.selectbox(
                "Filter / Inspect Hotspot Card:",
                options=card_options,
                index=0,
                key="hotspot_card_filter",
                help="Select a specific hotspot card to focus on, or show all detected hotspots."
            )
        with col_f2:
            displayed_count = 1 if selected_card_filter != "Show All Hotspots" else len(alerts)
            st.markdown(f"""
            <div style="padding-top:28px;font-family:'Space Mono',monospace;font-size:.7rem;color:#8A8A9A">
              Displaying <span style="color:#00D4FF;font-weight:700">{displayed_count}</span> of {len(alerts)} cards
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        for i, a in enumerate(alerts):
            if selected_card_filter != "Show All Hotspots":
                expected_prefix = f"Hotspot #{i+1} —"
                if not selected_card_filter.startswith(expected_prefix):
                    continue
            is_high   = a["risk_level"] == "HIGH"
            is_low    = a["risk_level"] == "LOW"
            clr       = "#FF3B3B" if is_high else ("#39FF14" if is_low else "#FF8C42")
            bw        = "8px" if is_high else ("4px" if is_low else "6px")
            glow      = "rgba(255,59,59,.2)" if is_high else ("rgba(57,255,20,.15)" if is_low else "rgba(255,140,66,.18)")
            badge_bg  = f"{clr}18"
            badge_bd  = f"{clr}40"
            dm        = a.get("distance_m", 0)
            dist      = f"{dm} metres from route" if dm < 1000 else f"{dm/1000:.2f} km from route"
            w_card    = a.get("weather", {})
            w_is_fb   = w_card.get("is_fallback", True)
            w_lbl     = "Placeholder" if w_is_fb else "Live"
            w_col     = "#8A8A9A" if w_is_fb else "#00D4FF"
            w_txt_col = "#8A8A9A" if w_is_fb else "#F0F0F0"
            w_desc_val= w_card.get("description", "Clear")
            w_temp_val= f"{w_card.get('temp', 28):.0f}°C"
            w_wind_val= f"{w_card.get('wind_speed', 5):.0f} km/h"
            w_hum     = w_card.get("humidity")
            w_hum_row = f'<tr><td style="color:#8A8A9A;padding:4px 0">Humidity:</td><td style="text-align:right;font-weight:700;color:#F0F0F0">{w_hum}%</td></tr>' if w_hum is not None and not w_is_fb else ''
            
            if w_is_fb:
                w_surf_text = "Unknown"
                w_surf_col = "#8A8A9A"
            elif w_card.get("is_rain"):
                w_surf_text = "Wet / Skid Risk"
                w_surf_col = "#FF3B3B"
            elif w_card.get("is_fog"):
                w_surf_text = "Fog / Low Visibility"
                w_surf_col = "#FF3B3B"
            else:
                w_surf_text = "Dry / Normal"
                w_surf_col = "#39FF14"

            w_notice_html = '<div style="font-family:Rajdhani,sans-serif;font-size:.78rem;color:#FF8C42;padding:6px 0 8px;border-bottom:1px solid rgba(255,255,255,.06);margin-bottom:8px"><i class="fa-solid fa-triangle-exclamation" style="margin-right:6px"></i>Live weather data unavailable. Add your OpenWeatherMap API key to config.py. The values below are placeholder defaults only.</div>' if w_is_fb else ''
            w_env_title = "WEATHER UNAVAILABLE — API KEY NOT SET" if w_is_fb else "CURRENT ENVIRONMENTAL CONDITIONS"
            w_title_col = "#8A8A9A" if w_is_fb else "#39FF14"

            fatal_val = a.get("fatal")
            fatal_str = f"{fatal_val} Fatalities" if fatal_val is not None else "Not available"
            cas_val   = a.get("casualties")
            cas_str   = f"{cas_val} Casualties" if cas_val is not None else "Not available"
            night_val = a.get("night_pct")
            night_str = f"{night_val}% Night Incidents" if night_val is not None else "Not available"
            peak_h    = a.get("peak_hour", 12)
            peak_str  = f"{peak_h:02d}:00 – {(peak_h+2)%24:02d}:00 hrs"
            cause_str = str(a.get("top_cause", "Not available")).title()
            tot_acc   = a.get("total_accidents", "Not available")
            rec_text  = a.get("safety_recommendation") or get_safety_recommendation(a)

            st.markdown(f"""
            <div id="hotspot-card-{i+1}" style="
              margin:0 28px 18px;
              background:rgba(255,255,255,.03);
              border:1px solid rgba(255,255,255,.08);
              border-left:{bw} solid {clr};
              border-radius:14px;padding:22px 24px;
              box-shadow:0 6px 28px {glow};
              transition:transform .25s,box-shadow .25s;
              animation:fadeSlideUp .4s ease {i*0.06}s both;
            ">
              <!-- Card Top Header -->
              <div style="display:flex;justify-content:space-between;align-items:center;
                          flex-wrap:wrap;gap:10px;margin-bottom:18px;padding-bottom:12px;
                          border-bottom:1px solid rgba(255,255,255,.06)">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                  <div style="background:{badge_bg};border:1px solid {badge_bd};
                              border-radius:6px;padding:5px 14px;
                              font-family:'Orbitron',monospace;font-size:.78rem;
                              font-weight:700;color:{clr};letter-spacing:1px">
                    <i class="fa-solid fa-{'triangle-exclamation' if is_high else 'circle-exclamation'}"
                       style="margin-right:6px"></i>
                    HOTSPOT #{i+1} — {a['risk_level']} RISK
                  </div>
                  <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#8A8A9A;
                              background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
                              border-radius:6px;padding:4px 10px">
                    <i class="fa-solid fa-bullseye" style="color:#00D4FF;margin-right:5px"></i>
                    CLUSTER ID: #{a.get('cluster_id', 'N/A')}
                  </div>
                </div>
                <div style="font-family:'Space Mono',monospace;font-size:.65rem;
                            color:#8A8A9A;background:rgba(0,212,255,.06);
                            border:1px solid rgba(0,212,255,.2);border-radius:6px;
                            padding:4px 12px">
                  <i class="fa-solid fa-arrows-to-dot" style="margin-right:6px;color:#00D4FF"></i>
                  {dist}
                </div>
              </div>

              <!-- Two Distinct Panels: Historical Accident Stats vs Current Context -->
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:16px">
                
                <!-- Panel 1: Historical Accident Intelligence -->
                <div style="background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.06);
                            border-radius:10px;padding:14px 16px">
                  <div style="font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:1.5px;
                              color:#00D4FF;margin-bottom:10px">
                    <i class="fa-solid fa-chart-line" style="margin-right:6px"></i>
                    HISTORICAL ACCIDENT DATA (DBSCAN CLUSTER)
                  </div>
                  <table style="width:100%;font-size:.82rem;font-family:'Rajdhani',sans-serif;border-collapse:collapse">
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Historical Accidents:</td>
                      <td style="text-align:right;font-weight:700;color:#F0F0F0">{tot_acc}</td>
                    </tr>
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Fatal Accidents:</td>
                      <td style="text-align:right;font-weight:700;color:{'#FF3B3B' if a.get('fatal',0)>0 else '#F0F0F0'}">{fatal_str}</td>
                    </tr>
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Total Casualties:</td>
                      <td style="text-align:right;font-weight:700;color:{'#FF8C42' if a.get('casualties',0)>0 else '#F0F0F0'}">{cas_str}</td>
                    </tr>
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Primary Recorded Cause:</td>
                      <td style="text-align:right;font-weight:700;color:#00D4FF">{cause_str}</td>
                    </tr>
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Peak Accident Period:</td>
                      <td style="text-align:right;font-weight:700;color:#F0F0F0">{peak_str}</td>
                    </tr>
                    <tr>
                      <td style="color:#8A8A9A;padding:4px 0">Night Incidents:</td>
                      <td style="text-align:right;font-weight:700;color:{'#FF8C42' if a.get('night_pct',0)>40 else '#F0F0F0'}">{night_str}</td>
                    </tr>
                  </table>
                </div>

                <!-- Panel 2: Current Environmental & Live Context -->
                <div style="background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.06);
                            border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;justify-content:space-between">
                  <div>
                    <div style="font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:1.5px;
                                color:{w_title_col};margin-bottom:10px">
                      <i class="fa-solid fa-cloud-sun" style="margin-right:6px"></i>
                      {w_env_title}
                    </div>
                    {w_notice_html}
                    <table style="width:100%;font-size:.82rem;font-family:'Rajdhani',sans-serif;border-collapse:collapse">
                      <tr>
                        <td style="color:#8A8A9A;padding:4px 0">{w_lbl} Weather:</td>
                        <td style="text-align:right;font-weight:700;color:{w_col}">{w_desc_val}</td>
                      </tr>
                      <tr>
                        <td style="color:#8A8A9A;padding:4px 0">Temperature:</td>
                        <td style="text-align:right;font-weight:700;color:{w_txt_col}">{w_temp_val}</td>
                      </tr>
                      <tr>
                        <td style="color:#8A8A9A;padding:4px 0">Wind Speed:</td>
                        <td style="text-align:right;font-weight:700;color:{w_txt_col}">{w_wind_val}</td>
                      </tr>
                      {w_hum_row}
                      <tr>
                        <td style="color:#8A8A9A;padding:4px 0">Road Surface Risk:</td>
                        <td style="text-align:right;font-weight:700;color:{w_surf_col}">{w_surf_text}</td>
                      </tr>
                    </table>
                  </div>

                  <!-- AI Context Brief -->
                  <div style="margin-top:12px;background:rgba(0,212,255,.05);border-left:3px solid #00D4FF;
                              border-radius:6px;padding:8px 12px;font-family:'Rajdhani',sans-serif;
                              font-size:.88rem;color:#A0A0C0;font-style:italic;line-height:1.4">
                    <i class="fa-solid fa-robot" style="color:#00D4FF;margin-right:5px"></i>
                    {a.get('ai_desc', '')}
                  </div>
                </div>

              </div>

              <!-- Bottom Actionable Safety Recommendation -->
              <div style="
                background:rgba(57,255,20,.05);
                border:1px solid rgba(57,255,20,.2);
                border-left:4px solid #39FF14;
                border-radius:10px;padding:12px 16px;
                display:flex;align-items:flex-start;gap:12px
              ">
                <i class="fa-solid fa-shield-halved" style="color:#39FF14;font-size:1.1rem;margin-top:2px"></i>
                <div>
                  <div style="font-family:'Space Mono',monospace;font-size:.62rem;
                              letter-spacing:1.5px;color:#39FF14;margin-bottom:3px">
                    SAFETY RECOMMENDATION
                  </div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:.95rem;
                              font-weight:600;color:#F0F0F0;line-height:1.5">
                    {rec_text}
                  </div>
                </div>
              </div>

            </div>
            """, unsafe_allow_html=True)

    # ── FEATURE 5: WEATHER-BASED DRIVING RECOMMENDATIONS ──────────────────────
    st.markdown('<div style="padding:16px 28px 8px">', unsafe_allow_html=True)
    w_is_fallback = w.get("is_fallback", True)
    w_advisory = get_weather_safety_advisory(w, alerts)

    adv_title = w_advisory.get("condition_title", "Weather Advisory")
    adv_color = w_advisory.get("condition_color", "#39FF14")
    adv_icon  = w_advisory.get("condition_icon", "cloud")
    desc      = w_advisory.get("description", "Clear")
    temp      = w_advisory.get("temp", 28.0)
    wind      = w_advisory.get("wind_speed", 5.0)
    humidity  = w.get("humidity")

    # Show notice when weather data is unavailable
    if w_is_fallback:
        st.markdown("""
        <div style="background:rgba(255,140,66,.08);border:1px solid rgba(255,140,66,.3);
                    border-left:4px solid #FF8C42;border-radius:10px;padding:12px 16px;margin-bottom:12px">
          <span style="font-family:'Space Mono',monospace;font-size:.65rem;color:#FF8C42;font-weight:700">
            <i class="fa-solid fa-cloud-slash" style="margin-right:8px"></i>
            WEATHER DATA UNAVAILABLE — ADD OPENWEATHERMAP API KEY TO config.py
          </span><br>
          <span style="font-family:'Rajdhani',sans-serif;font-size:.82rem;color:#C0A080">
            The recommendations below are based on generic good-weather defaults.
            They do not reflect actual conditions along your route.
          </span>
        </div>
        """, unsafe_allow_html=True)

    ctx_html = ""
    for ca in w_advisory.get("contextual_alerts", []):
        ctx_html += f"""
        <div style="background:rgba(255,59,59,.1);border:1px solid rgba(255,59,59,.3);
                    border-left:4px solid #FF3B3B;border-radius:8px;padding:10px 14px;
                    margin-bottom:12px;font-family:'Rajdhani',sans-serif;font-size:.9rem;
                    color:#FFA0A0;font-weight:600">
          <i class="fa-solid fa-triangle-exclamation" style="color:#FF3B3B;margin-right:8px"></i>
          {ca}
        </div>
        """

    precautions_html = "".join([
        f"<li style='margin-bottom:6px;color:#F0F0F0'>{p}</li>"
        for p in w_advisory.get("precautions", [])
    ])
    warnings_html = "".join([
        f"<li style='margin-bottom:6px;color:#FFB080'>{warn}</li>"
        for warn in w_advisory.get("warnings", [])
    ])

    humidity_str = f" &bull; HUMIDITY {humidity}%" if humidity is not None and not w_is_fallback else ""

    st.markdown(f"""
    <div style="
      background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
      border-left:6px solid {adv_color};border-radius:14px;padding:22px 24px;
      margin-bottom:20px;box-shadow:0 6px 28px rgba(0,0,0,.35)
    ">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:16px">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="background:{adv_color}18;border:1px solid {adv_color}40;
                      border-radius:8px;padding:8px 12px;font-size:1.3rem;color:{adv_color}">
            <i class="fa-solid fa-{adv_icon}"></i>
          </div>
          <div>
            <div style="font-family:'Orbitron',monospace;font-size:.85rem;font-weight:700;color:{adv_color};letter-spacing:1px">
              {adv_title.upper()}
            </div>
            <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#8A8A9A">
              {'DEFAULTS — NOT LIVE DATA' if w_is_fallback else f'ROUTE MIDPOINT CONDITIONS: {desc.upper()} &bull; {temp:.0f}&deg;C &bull; WIND {wind:.0f} KM/H{humidity_str}'}
            </div>
          </div>
        </div>
        <div style="font-family:'Space Mono',monospace;font-size:.62rem;color:#8A8A9A;
                    background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
                    border-radius:6px;padding:4px 10px">
          ROAD SURFACE: {'UNKNOWN — NO LIVE DATA' if w_is_fallback else ('WET / LOW TRACTION' if w.get('is_rain') else ('LOW VISIBILITY' if w.get('is_fog') else 'DRY / STANDARD'))}
        </div>
      </div>

      {ctx_html}

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px">
        <div style="background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:14px 16px">
          <div style="font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:1.5px;color:#FF8C42;margin-bottom:8px">
            <i class="fa-solid fa-triangle-exclamation" style="margin-right:6px"></i>ACTIVE WEATHER HAZARDS
          </div>
          <ul style="margin:0;padding-left:18px;font-family:'Rajdhani',sans-serif;font-size:.88rem;line-height:1.5">
            {warnings_html}
          </ul>
        </div>
        <div style="background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:14px 16px">
          <div style="font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:1.5px;color:#39FF14;margin-bottom:8px">
            <i class="fa-solid fa-shield-halved" style="margin-right:6px"></i>ACTIONABLE DRIVING PRECAUTIONS
          </div>
          <ul style="margin:0;padding-left:18px;font-family:'Rajdhani',sans-serif;font-size:.88rem;line-height:1.5">
            {precautions_html}
          </ul>
        </div>
      </div>

      <div style="margin-top:12px;font-family:'Rajdhani',sans-serif;font-size:.78rem;color:#6A6A7A;font-style:italic">
        <i class="fa-solid fa-circle-info" style="margin-right:5px"></i>
        {w_advisory.get('disclaimer')}
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── FEATURE 4: DOWNLOADABLE ROUTE SAFETY REPORT ───────────────────────────
    st.markdown('<div style="padding:4px 28px 24px">', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:12px">
      <div style="font-family:'Space Mono',monospace;font-size:.65rem;letter-spacing:2px;color:#00D4FF">
        <i class="fa-solid fa-file-arrow-down" style="color:#00D4FF;margin-right:8px"></i>
        DOWNLOADABLE ROUTE SAFETY REPORT & EXPORTS
      </div>
      <div style="font-family:'Space Mono',monospace;font-size:.6rem;color:#8A8A9A">
        Export comprehensive route safety profile for offline planning and audit
      </div>
    </div>
    """, unsafe_allow_html=True)

    route_sum = {
        "start_label": s_lbl,
        "end_label": e_lbl,
        "route_distance_km": route_dist_km,
        "safety_score": score,
        "risk_category": risk_cat,
        "total_hotspots": len(alerts),
        "high_count": high_n,
        "medium_count": med_n,
        "low_count": low_n,
    }

    rep_col1, rep_col2 = st.columns(2)
    clean_origin = "".join(c for c in str(s_lbl) if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    clean_dest   = "".join(c for c in str(e_lbl) if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    if not clean_origin: clean_origin = "Origin"
    if not clean_dest:   clean_dest   = "Destination"

    with rep_col1:
        try:
            pdf_bytes = generate_pdf_report(route_sum, alerts, w)
            pdf_filename = f"SafeRoute_Report_{clean_origin}_to_{clean_dest}.pdf"
            st.download_button(
                label="📄 Download PDF Safety Report",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                help="Download a formatted multi-page PDF safety report with route KPIs, weather, and detailed hotspot records.",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generating PDF report: {e}")

    with rep_col2:
        try:
            csv_str = generate_csv_report(route_sum, alerts, w)
            csv_filename = f"SafeRoute_Data_{clean_origin}_to_{clean_dest}.csv"
            st.download_button(
                label="📊 Download CSV Data Export",
                data=csv_str,
                file_name=csv_filename,
                mime="text/csv",
                help="Export tabular hotspot data and route metadata as CSV for spreadsheet analysis.",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generating CSV report: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# ── TERMINAL RETRAIN LOG ──────────────────────────────────────────────────────
st.markdown('<div style="padding:8px 28px 24px">', unsafe_allow_html=True)
logs = get_retrain_log()
with st.expander("SYSTEM LOG — AUTO-RETRAIN HISTORY"):
    log_lines = ""
    if logs:
        for l in reversed(logs[-8:]):
            ts  = l['timestamp'][:16].replace('T', ' ')
            st_ = l['status'].upper()
            col = "#39FF14" if st_ == "SUCCESS" else ("#FF8C42" if st_ == "SKIPPED" else "#FF3B3B")
            log_lines += f"""
            <div style="padding:5px 0;border-bottom:1px solid rgba(255,255,255,.04)">
              <span style="color:#555">[{ts}]</span>
              <span style="color:{col};margin-left:10px">{st_}</span>
              <span style="color:#8A8A9A;margin-left:10px">+{l['new_records']} records</span>
              <span style="color:#00D4FF;margin-left:10px">acc: {l['accuracy']}%</span>
              <span style="color:#555;margin-left:10px">// {l['note']}</span>
            </div>"""
    else:
        log_lines = '<div style="color:#555">No retrain events yet. Runs daily at 02:00.</div>'

    st.markdown(f"""
    <div style="
      background:#060608;border:1px solid rgba(57,255,20,.12);
      border-radius:12px;padding:18px 20px;
      font-family:'Space Mono',monospace;font-size:.72rem;
      line-height:1.8;max-height:240px;overflow-y:auto;
    ">
      <div style="color:#39FF14;margin-bottom:10px;font-size:.65rem;letter-spacing:1.5px">
        SAFEROUTE SYSTEM LOG v2.0 — AUTO-RETRAIN DAEMON
      </div>
      {log_lines}
    </div>""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ── REPORT FORM ───────────────────────────────────────────────────────────────
st.markdown('<div style="padding:0 28px 28px">', unsafe_allow_html=True)
with st.expander("REPORT NEW ACCIDENT — TRIGGERS MODEL RETRAIN"):
    with st.form("report_form"):
        c1, c2, c3 = st.columns(3)
        r_lat   = c1.number_input("Latitude",  value=13.0827, format="%.6f")
        r_lon   = c2.number_input("Longitude", value=80.2707, format="%.6f")
        r_sev   = c3.selectbox("Severity", ["minor", "major", "fatal"])
        c4, c5  = st.columns(2)
        r_weath = c4.selectbox("Weather", ["clear", "fog", "rain"])
        r_cause = c5.selectbox("Cause", ["weather","distraction",
                                          "overspeeding","drunk driving","poor road"])
        r_road  = st.selectbox("Road Type", ["urban","highway","rural"])
        submit  = st.form_submit_button("SUBMIT AND RETRAIN MODEL", type="primary")

    if submit:
        sev_num = {"minor": 1, "major": 2, "fatal": 3}[r_sev]
        new_row = {
            "latitude": r_lat, "longitude": r_lon,
            "severity": sev_num, "severity_raw": r_sev,
            "weather": r_weath, "road_type": r_road, "cause": r_cause,
            "casualties": 1 if sev_num >= 2 else 0, "vehicles_involved": 2,
            "hour": datetime.now().hour,
            "day_of_week": datetime.now().strftime("%A"),
            "risk_score": round(sev_num / 3.0, 3),
            "traffic_density": "medium", "visibility": "medium",
            "is_peak_hour": 0, "alcohol": 0,
            "location_type": "Straight Road", "vehicle_type": "Car",
            "source": "reported",
        }
        base    = st.session_state.get("train_df", _load_ds1())
        updated = pd.concat([base, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state["train_df"] = updated
        with st.spinner("Retraining model and rebuilding hotspots..."):
            clf, acc = train_model(updated)
            st.session_state["clf"] = clf
            new_hs = build_hotspots()
            st.session_state["hotspots"] = new_hs
        st.success(f"Accident reported. Model accuracy: {acc*100:.1f}% | Hotspots: {len(new_hs)}")

st.markdown('</div>', unsafe_allow_html=True)
