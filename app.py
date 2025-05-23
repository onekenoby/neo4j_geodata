# app.py

import streamlit as st
import pandas as pd
import pydeck as pdk

from neo4j_utils import driver, ensure_gds_graph, get_minimal_path_dijkstra
import export_utils

# ────────────────── Streamlit Setup ─────────────────────────────
st.set_page_config(page_title="Country → City Minimal Path", layout="wide")
st.title("🌍 Country → City – True Minimal Path")

# 1) Project GDS graph once
try:
    ensure_gds_graph()
except Exception:
    pass

# ─── Inline loader for all points (including country) ────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_points():
    q = """
    MATCH (op:OperationPoint)
    OPTIONAL MATCH (op)-[r:NAMED]->(pn:OperationPointName)
    RETURN
      op.id      AS id,
      coalesce(pn.name, op.id) AS label,
      r.country  AS country,
      op.geolocation.latitude  AS lat,
      op.geolocation.longitude AS lon
    ORDER BY country, label
    """
    pts = []
    with driver.session() as ses:
        for rec in ses.run(q):
            pts.append({
                "id":      rec["id"],
                "label":   rec["label"],
                "country": rec["country"] or "Unknown",
                "lat":     rec["lat"],
                "lon":     rec["lon"]
            })
    return pts

# ─── Inline loader for all network edges ────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_edges():
    q = """
    MATCH (a:OperationPoint)-[r:SECTION]-(b:OperationPoint)
    RETURN
      a.geolocation.longitude AS lon1,
      a.geolocation.latitude  AS lat1,
      b.geolocation.longitude AS lon2,
      b.geolocation.latitude  AS lat2
    """
    edges = []
    with driver.session() as ses:
        for rec in ses.run(q):
            edges.append({
                "lon1": rec["lon1"],
                "lat1": rec["lat1"],
                "lon2": rec["lon2"],
                "lat2": rec["lat2"]
            })
    return pd.DataFrame(edges)

# Load data
all_points = load_points()
all_edges  = load_edges()

if not all_points:
    st.error("No OperationPoint data found. Please load your CSV & project GDS.")
    st.stop()

# ─── Sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    
    # Country selector
    countries = sorted({pt["country"] for pt in all_points})
    country = st.selectbox("Country", countries)
    
    # Filter points by country
    pts = [pt for pt in all_points if pt["country"] == country]
    labels = [pt["label"] for pt in pts]
    
    # Search + select Start City
    start_search = st.text_input("🔍 Search Start City")
    start_opts = [lbl for lbl in labels if start_search.lower() in lbl.lower()]
    start_label = st.selectbox("Start City", start_opts or ["–"])
    
    # Search + select End City
    end_search = st.text_input("🔍 Search End City")
    end_opts = [lbl for lbl in labels if end_search.lower() in lbl.lower()]
    end_label = st.selectbox("End City", end_opts or ["–"])
    
    # Show Minimal Path button
    show_btn = st.button("▶ Show Minimal Path")
    
    # Export controls
    export_fmt = st.radio("Export format", ["CSV", "JSON"])
    download   = st.button("Download Table")

# ─── Compute minimal path on demand ─────────────────────────────
paths = []
if show_btn:
    if start_label not in labels or end_label not in labels:
        st.warning("Please select valid start and end cities.")
    elif start_label == end_label:
        st.warning("Start and end must differ.")
    else:
        src_id = next(pt["id"] for pt in pts if pt["label"] == start_label)
        dst_id = next(pt["id"] for pt in pts if pt["label"] == end_label)
        paths = get_minimal_path_dijkstra(src_id, dst_id)
        if not paths:
            st.error("No path found between those cities.")

# ─── Build route details DataFrame ──────────────────────────────
table_df = pd.DataFrame()
if paths:
    p = paths[0]
    table_df = pd.DataFrame([{
        "Stops": len(p["cities"]),
        "Route": " → ".join(c["label"] for c in p["cities"]),
        "Total Distance (km)": p["total_distance"]
    }])

# ─── Export logic ────────────────────────────────────────────────
if download:
    if table_df.empty:
        st.warning("No route to download. Run 'Show Minimal Path' first.")
    else:
        if export_fmt == "CSV":
            st.download_button(
                "Download CSV",
                data=export_utils.df_to_csv(table_df),
                file_name="minimal_path.csv",
                mime="text/csv"
            )
        else:
            st.download_button(
                "Download JSON",
                data=export_utils.df_to_json(table_df),
                file_name="minimal_path.json",
                mime="application/json"
            )

# ─── Display route table ────────────────────────────────────────
st.subheader("Route Details")
if show_btn and paths:
    st.dataframe(table_df, use_container_width=True)
elif show_btn:
    st.write("")  
else:
    st.info("Select a country & cities, then click ▶ Show Minimal Path.")

# ─── Map rendering (PyDeck) ────────────────────────────────────
st.subheader("Map View")

# 1) Base network edges in light grey, thicker lines
edge_layer = pdk.Layer(
    "LineLayer",
    all_edges,
    get_source_position=["lon1", "lat1"],
    get_target_position=["lon2", "lat2"],
    get_color=[150, 150, 150, 120],
    get_width=5,            # increased line thickness
    width_min_pixels=2,
    width_max_pixels=20,
    pickable=False
)

# 2) Path layer: red for minimal route
path_layers = []
if paths:
    coords = [[c["lon"], c["lat"]] for c in paths[0]["cities"]]
    df_path = pd.DataFrame({"path": [coords]})
    path_layers.append(
        pdk.Layer(
            "PathLayer",
            df_path,
            get_path="path",
            get_color=[255, 0, 0, 200],  # bright red
            get_width=5,
            width_min_pixels=2
        )
    )

# 3) View state centered on Italy
df_pts = pd.DataFrame(all_points)
view_state = pdk.ViewState(
    latitude=df_pts["lat"].mean(),
    longitude=df_pts["lon"].mean(),
    zoom=6
)

# 4) Build deck with double vertical size
deck = pdk.Deck(
    layers=[edge_layer] + path_layers,
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/streets-v11",
    height=800
)

st.pydeck_chart(deck, use_container_width=True)
