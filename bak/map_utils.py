# map_utils.py
import folium
from config import PATH_COLORS, PATH_LABELS

def draw_point_map(all_points, paths, visibility_flags):
    """
    all_points:       list of {id,lat,lon}
    paths:            list of path dicts as returned by get_top_paths()
    visibility_flags:list[bool] of length==len(PATH_LABELS)
    """
    # Center on Italy
    avg_lat = sum(p["lat"] for p in all_points) / len(all_points)
    avg_lon = sum(p["lon"] for p in all_points) / len(all_points)
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6, tiles="OpenStreetMap")

    # 1) Plot every point in light grey
    for pt in all_points:
        folium.CircleMarker(
            location=[pt["lat"], pt["lon"]],
            radius=3,
            color="#888",
            fill=True,
            fill_color="#ccc",
            fill_opacity=0.5,
            tooltip=pt["id"]
        ).add_to(m)

    # 2) Overlay selected paths
    for idx, path in enumerate(paths):
        if not visibility_flags[idx]:
            continue
        color  = PATH_COLORS[idx]
        cities = path["cities"]
        edges  = path["edges"]
        total  = path["total_distance"]

        # draw nodes
        for c in cities:
            folium.CircleMarker(
                location=[c["lat"], c["lon"]],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=c["id"]
            ).add_to(m)

        # draw edges
        for e in edges:
            a = next(c for c in cities if c["id"] == e["source"])
            b = next(c for c in cities if c["id"] == e["target"])
            folium.PolyLine(
                locations=[[a["lat"], a["lon"]], [b["lat"], b["lon"]]],
                color=color,
                weight=4,
                tooltip=f"{e['source']} → {e['target']}: {e['distance']} km"
            ).add_to(m)

        # midpoint badge
        mid = cities[len(cities)//2]
        folium.Marker(
            location=[mid["lat"], mid["lon"]],
            icon=folium.DivIcon(html=f"""
              <div style="background:white; padding:4px;
                          border:1px solid {color}; border-radius:4px;
                          color:{color}; font-size:12px">
                {PATH_LABELS[idx]}: <b>{total:.1f} km</b>
              </div>"""
            )
        ).add_to(m)

    # 3) static legend
    legend = "<div style='position: fixed; bottom:50px; left:50px; \
                 background:white; padding:8px; border:1px solid grey; z-index:9999; font-size:12px;'>\
                 <b>Legend</b><br>"
    for i, lbl in enumerate(PATH_LABELS):
        legend += f"<span style='color:{PATH_COLORS[i]};'>&#9632;</span> {lbl}<br>"
    legend += "</div>"
    m.get_root().html.add_child(folium.Element(legend))

    return m
