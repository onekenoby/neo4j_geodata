# map_utils_pydeck.py
import pydeck as pdk
import pandas as pd
from config import PATH_COLORS

_COLOR_MAP = {
    "red":   [255, 0,   0],
    "blue":  [0,   0, 255],
    "green": [0, 255,   0],
}

def draw_map_pydeck(all_points, paths, visibility_flags):
    """
    Render base points (grey scatter) and minimal path (colored) with PyDeck.
    """
    # DataFrame for all points
    df_all = pd.DataFrame(all_points)

    scatter = pdk.Layer(
        "ScatterplotLayer",
        df_all,
        get_position=["lon","lat"],
        get_fill_color=[180,180,180,120],
        get_radius=2000,
        pickable=False
    )

    # Path layer (single minimal)
    path_layers = []
    if paths and visibility_flags and visibility_flags[0]:
        coords = [[c["lon"], c["lat"]] for c in paths[0]["cities"]]
        df_path = pd.DataFrame({"path": [coords]})
        rgb = _COLOR_MAP.get(PATH_COLORS[0], [0,0,0])
        path_layers.append(
            pdk.Layer(
                "PathLayer",
                df_path,
                get_path="path",
                get_color=rgb + [255],
                get_width=4,
                width_min_pixels=2
            )
        )

    view_state = pdk.ViewState(
        latitude=df_all["lat"].mean(),
        longitude=df_all["lon"].mean(),
        zoom=6
    )

    return pdk.Deck(
        layers=[scatter] + path_layers,
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/light-v9"
    )
