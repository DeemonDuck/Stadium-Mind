"""
app.py

StadiumMind's Streamlit dashboard - the single entry point tying everything
together. Two tabs, sharing one venue graph, one crowd simulator, and one
cached layout, used by BOTH tabs:

  - Organizer Dashboard: live visual congestion map + predictive trend
    metrics + structured incident log + "Ask Stadium Brain"
  - Fan Assistant: pick start/destination/language, see the chosen route
    highlighted on the same map, with an explanation of why it was chosen

AUTO-TICK NOTE: the live congestion panel runs inside an st.fragment, which
lets it auto-refresh on a timer WITHOUT rerunning the whole page - so the
incident report form below it never gets wiped out mid-typing.

Run with: streamlit run app.py
"""

import streamlit as st
from core.venue import build_venue_graph
from core.crowd_sim import CrowdSimulator
from core.incidents import Incident, sort_by_urgency
from core.graph_layout import compute_layout
from core.visualization import build_congestion_figure
from agents.organizer_agent import get_organizer_recommendation
from agents.fan_agent import get_fan_directions

st.set_page_config(page_title="StadiumMind", page_icon="🏟️", layout="wide")

# --- Shared state: one graph + one simulator + one cached layout + one
# incident log, used by BOTH tabs. This is intentional - it's what makes
# the "shared intelligence layer" story real instead of just a slide.
# st.session_state persists these across reruns within a single session.
if "graph" not in st.session_state:
    st.session_state.graph = build_venue_graph()
if "simulator" not in st.session_state:
    st.session_state.simulator = CrowdSimulator(st.session_state.graph, seed=42)
if "incidents" not in st.session_state:
    st.session_state.incidents = []
if "positions" not in st.session_state:
    # Computed once and reused - keeps the map visually stable instead of
    # re-laying-out (and jumping around) on every rerun.
    st.session_state.positions = compute_layout(st.session_state.graph)

graph = st.session_state.graph
simulator = st.session_state.simulator
positions = st.session_state.positions

st.title("🏟️ StadiumMind")
st.caption(
    "One shared crowd-intelligence layer powering organizer decisions "
    "and fan navigation. Running in mock mode until a real GROQ_API_KEY is added to .env."
)

tab1, tab2 = st.tabs(["📊 Organizer Dashboard", "🧭 Fan Assistant"])


# ----------------------------------------------------------------------
# TAB 1: Organizer Dashboard
# ----------------------------------------------------------------------
@st.fragment(run_every="3s")
def render_live_panel():
    """
    The auto-refreshing part of the dashboard: the map + trend metrics.
    Isolated in its own fragment so its timer-driven reruns never touch
    the incident form or anything else on the page - only this function's
    output refreshes automatically.
    """
    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1, 1])
    with ctrl1:
        st.checkbox("🔄 Auto-tick every 3s (for a live demo)", key="auto_tick")
    with ctrl2:
        if st.button("⏱️ Tick once", width="stretch"):
            simulator.tick()
    with ctrl3:
        if st.button("🚨 Spike Gate_A", width="stretch"):
            simulator.trigger_incident("Gate_A")

    if st.session_state.get("auto_tick"):
        simulator.tick()

    congestion = simulator.get_all()
    trends = {
        node: {
            "trend_pct": simulator.get_trend(node),
            "eta_ticks": simulator.estimate_ticks_to_critical(node),
        }
        for node in congestion
    }
    # Stash the latest snapshot so the (non-fragment) "Ask Stadium Brain"
    # button below can read current data without needing its own fragment.
    st.session_state["latest_congestion"] = congestion
    st.session_state["latest_trends"] = trends

    fig = build_congestion_figure(graph, simulator, positions)
    st.plotly_chart(fig, width="stretch", key="organizer_map")
    st.caption("🟢 Low &nbsp;&nbsp; 🟡 Moderate &nbsp;&nbsp; 🟠 High &nbsp;&nbsp; 🔴 Critical", unsafe_allow_html=True)

    st.markdown("**Top congestion hotspots**")
    top_nodes = sorted(congestion.items(), key=lambda x: -x[1])[:4]
    cols = st.columns(len(top_nodes))
    for col, (node, score) in zip(cols, top_nodes):
        trend_pct = trends[node]["trend_pct"]
        eta = trends[node]["eta_ticks"]
        with col:
            st.metric(node, f"{score}/100", delta=f"{trend_pct}%", delta_color="inverse")
            if eta == 0:
                st.caption("⚠️ Already critical")
            elif eta is not None:
                st.caption(f"~{eta} updates to critical")


with tab1:
    render_live_panel()

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Report an Incident")
        with st.form("incident_form", clear_on_submit=True):
            desc = st.text_input("Description", placeholder="e.g. Medical emergency")
            loc = st.selectbox("Location", sorted(graph.nodes))
            severity = st.selectbox("Severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], index=1)
            submitted = st.form_submit_button("Log Incident")
            if submitted and desc:
                st.session_state.incidents.append(Incident(desc, loc, severity))

        if st.session_state.incidents:
            st.caption("Active incidents (most urgent first):")
            for inc in sort_by_urgency(st.session_state.incidents):
                st.text(str(inc))
            if st.button("Clear all incidents"):
                st.session_state.incidents = []

    with col2:
        st.subheader("Ask Stadium Brain")
        if st.button("Get Recommendation", type="primary"):
            congestion_snapshot = st.session_state.get("latest_congestion", simulator.get_all())
            trends = st.session_state.get("latest_trends", {})
            with st.spinner("Analyzing crowd situation..."):
                recommendation = get_organizer_recommendation(
                    graph, congestion_snapshot, st.session_state.incidents, trends
                )
            st.info(recommendation)

# ----------------------------------------------------------------------
# TAB 2: Fan Assistant
# ----------------------------------------------------------------------
with tab2:
    st.subheader("Where do you want to go?")

    all_nodes = sorted(graph.nodes)
    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.selectbox("Your current location", all_nodes, index=all_nodes.index("Gate_A"))
    with col2:
        destination = st.selectbox(
            "Destination", all_nodes, index=all_nodes.index("Restroom_2")
        )
    with col3:
        language = st.selectbox("Preferred language", ["English", "Hindi", "Spanish", "French"])

    if st.button("Get Directions", type="primary"):
        if start == destination:
            st.warning("You're already there!")
        else:
            with st.spinner("Finding the best route..."):
                directions, path, explanation = get_fan_directions(
                    graph, simulator, start, destination, language
                )
            st.success(directions)
            st.caption(f"Why this route: {explanation}")

            fig = build_congestion_figure(graph, simulator, positions, highlight_path=path)
            st.plotly_chart(fig, width="stretch", key="fan_map")
            st.caption("🟢 Low &nbsp;&nbsp; 🟡 Moderate &nbsp;&nbsp; 🟠 High &nbsp;&nbsp; 🔴 Critical &nbsp;&nbsp; 🔵 Chosen route", unsafe_allow_html=True)
