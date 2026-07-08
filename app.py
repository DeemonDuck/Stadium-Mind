"""
app.py

StadiumMind's Streamlit dashboard - the single entry point tying everything
together. Two tabs, sharing one venue graph and one crowd simulator:

  - Organizer Dashboard: live congestion view + "Ask Stadium Brain" chat
  - Fan Assistant: pick start/destination/language, get a routed, phrased answer

Run with: streamlit run app.py
"""

import streamlit as st
from core.venue import build_venue_graph
from core.crowd_sim import CrowdSimulator
from agents.organizer_agent import get_organizer_recommendation
from agents.fan_agent import get_fan_directions

st.set_page_config(page_title="StadiumMind", page_icon="🏟️", layout="wide")

# --- Shared state: one graph + one simulator, used by BOTH tabs ---
# This is intentional - it's what makes the "shared intelligence layer"
# story real instead of just a slide. st.session_state persists these
# across reruns within a single browser session.
if "graph" not in st.session_state:
    st.session_state.graph = build_venue_graph()
if "simulator" not in st.session_state:
    st.session_state.simulator = CrowdSimulator(st.session_state.graph, seed=42)

graph = st.session_state.graph
simulator = st.session_state.simulator

st.title("🏟️ StadiumMind")
st.caption(
    "One shared crowd-intelligence layer powering organizer decisions "
    "and fan navigation. Running in mock mode until a real GROQ_API_KEY is added to .env."
)

tab1, tab2 = st.tabs(["📊 Organizer Dashboard", "🧭 Fan Assistant"])

# ----------------------------------------------------------------------
# TAB 1: Organizer Dashboard
# ----------------------------------------------------------------------
with tab1:
    st.subheader("Live Crowd Status")

    col1, col2 = st.columns([1, 1])

    with col1:
        colA, colB = st.columns(2)
        with colA:
            if st.button("⏱️ Advance Simulation (tick)", use_container_width=True):
                simulator.tick()
        with colB:
            if st.button("🚨 Simulate Incident at Gate_A", use_container_width=True):
                simulator.trigger_incident("Gate_A")

        st.divider()
        congestion = simulator.get_all()
        for node, score in sorted(congestion.items(), key=lambda x: -x[1]):
            label = simulator.get_congestion_label(node)
            st.metric(node, f"{score}/100", label)

    with col2:
        st.subheader("Ask Stadium Brain")
        incident_input = st.text_area(
            "Report an incident (optional)",
            placeholder="e.g. Medical emergency near Gate_A",
        )
        if st.button("Get Recommendation", type="primary"):
            incidents = [incident_input] if incident_input else []
            with st.spinner("Analyzing crowd situation..."):
                recommendation = get_organizer_recommendation(simulator.get_all(), incidents)
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
                directions, path = get_fan_directions(graph, simulator, start, destination, language)
            st.success(directions)
            st.caption(f"Path: {' → '.join(path)}")
