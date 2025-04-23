# app.py

import streamlit as st
import pandas as pd

import neo4j_utils
import map_utils_pydeck
import export_utils
from config import PATH_LABELS

# ─── Streamlit Setup ───────────────────────────────────────────
st.set_page_config(page_title="Country → City Paths", layout="wide")
st.title("🌍 Select Country, Then City – Top-3 Shortest Paths")

# Ensure GDS graph (if you use it)
try:
    neo4j_utils.ensure_gds_graph()
except AttributeError:
    pass

# ─── Load & Cache Points ───────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_all_points():
    return neo4j_utils.get_all_point_coords()

all_points = load_all_points()

# Build country list
countries = sorted({pt["country"] for pt in all_points})

# ─── Sidebar ────────────────────────────────────────────────────
if "show_paths" not in st.session_state:
    st.session_state.show_paths = False

with st.sidebar:
    st.header("Controls")

    # 1) Country selector
    country = st.selectbox("Country", countries, index=0)

    # 2) Filter cities by country for the next two dropdowns
    pts_in_country = [pt for pt in all_points if pt["country"] == country]
    labels = [pt["label"] for pt in pts_in_country]

    # 3) City selectors
    start_label = st.selectbox("Start City", labels, index=0)
    end_label   = st.selectbox("End City",   labels, index=min(1, len(labels)-1))

    # 4) Show Paths button
    if st.button("Show Paths"):
        st.session_state.show_paths = True

    # 5) Path toggles (only after Show Paths)
    if st.session_state.show_paths:
        toggles = [
            st.checkbox(PATH_LABELS[i], True, key=f"tog_{i}")
            for i in range(len(PATH_LABELS))
        ]
    else:
        toggles = [False] * len(PATH_LABELS)

    # 6) Export controls
    export_fmt = st.radio("Export format", ["CSV", "JSON"])
    do_export   = st.button("Download Table")

# ─── Compute Paths ─────────────────────────────────────────────
paths = []
if st.session_state.show_paths:
    # map labels back to ids
    label_to_id = {pt["label"]: pt["id"] for pt in pts_in_country}
    src_id = label_to_id[start_label]
    dst_id = label_to_id[end_label]
    paths = neo4j_utils.get_top_paths(src_id, dst_id, k=3)

# ─── Build Comparison Table ────────────────────────────────────
table_df = pd.DataFrame()
if st.session_state.show_paths and paths:
    # For each path, only include if toggle True
    table_df = pd.DataFrame([
        {
          "Path": PATH_LABELS[i],
          "Stops": len(p["cities"]),
          "Route": " → ".join([
              # convert each city-id back to its label in this country
              next(pt["label"] for pt in pts_in_country if pt["id"] == c["id"])
              for c in p["cities"]
          ]),
          "Total Distance (km)": p["total_distance"]
        }
        for i, p in enumerate(paths) if toggles[i]
    ])

# ─── Export Logic ──────────────────────────────────────────────
if do_export and not table_df.empty:
    if export_fmt == "CSV":
        st.download_button(
            "Download CSV",
            data=export_utils.df_to_csv(table_df),
            file_name="paths.csv",
            mime="text/csv"
        )
    else:
        st.download_button(
            "Download JSON",
            data=export_utils.df_to_json(table_df),
            file_name="paths.json",
            mime="application/json"
        )

# ─── Display Table ─────────────────────────────────────────────
st.subheader("Comparison Table")
if st.session_state.show_paths:
    if not table_df.empty:
        st.dataframe(table_df, use_container_width=True)
    else:
        st.write("No routes selected (toggle on).")
else:
    st.write("Select a country and cities, then click **Show Paths**.")

# ─── Map View (PyDeck) ────────────────────────────────────────
st.subheader("Map View")
deck = map_utils_pydeck.draw_map_pydeck(
    all_points,   # still plot all points
    paths,
    toggles
)
st.pydeck_chart(deck)

# ─── Cleanup ───────────────────────────────────────────────────
# Optional: explicitly close driver
try:
    neo4j_utils.close_driver()
except AttributeError:
    pass
