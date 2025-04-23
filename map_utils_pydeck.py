# map_utils_pydeck.py
import pydeck as pdk
import pandas as pd
from config import PATH_COLORS, PATH_LABELS

_COLOR_MAP = {
    "red":   [255, 0,   0],
    "blue":  [0,   0, 255],
    "green": [0, 255,   0],
}

def draw_map_pydeck(all_points, paths, visibility_flags):
    """
    all_points:       list of {"id","label","lat","lon"}
    paths:            list of path dicts (cities use .id for lookups)
    visibility_flags: list of bools
    """
    df_all = pd.DataFrame(all_points)

    # Scatter layer: grey points, tooltip shows label
    scatter = pdk.Layer(
        "ScatterplotLayer",
        df_all,
        pickable=True,
        get_position=["lon", "lat"],
        get_fill_color=[200, 200, 200, 80],
        get_radius=5000,
        tooltip=True,
    )

    # Path layers
    path_layers = []
    for i, path in enumerate(paths):
        if not visibility_flags[i]:
            continue
        coords = [[c["lon"], c["lat"]] for c in path["cities"]]
        df_path = pd.DataFrame({"path": [coords]})
        rgb = _COLOR_MAP[PATH_COLORS[i]]
        layer = pdk.Layer(
            "PathLayer",
            df_path,
            get_path="path",
            get_width=5,
            get_color=rgb + [200],
            width_min_pixels=2,
        )
        path_layers.append(layer)

    # Center on Italy
    view_state = pdk.ViewState(
        latitude=df_all["lat"].mean(),
        longitude=df_all["lon"].mean(),
        zoom=6,
        pitch=0,
    )

    return pdk.Deck(
        layers=[scatter] + path_layers,
        initial_view_state=view_state,
        tooltip={"text": "{label}"},  # show label on hover
        map_style="mapbox://styles/mapbox/light-v9",
    )
