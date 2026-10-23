import numpy as np
import requests
from math import radians

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "RoadRiskNavigator/2.0"})


def _haversine_vectorized(rlat, rlon, hs_lats, hs_lons):
    """Vectorized haversine — compares ONE route point vs ALL hotspots at once."""
    R   = 6_371_000
    rl  = np.radians(rlat)
    rlo = np.radians(rlon)
    hl  = np.radians(hs_lats)
    hlo = np.radians(hs_lons)
    dlat = hl - rl
    dlon = hlo - rlo
    a = np.sin(dlat / 2) ** 2 + np.cos(rl) * np.cos(hl) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def geocode(place: str):
    """Nominatim geocode — returns (lat, lon) or None."""
    try:
        r = _SESSION.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": place + ", India", "format": "json", "limit": 1},
            timeout=6,
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def get_road_route(start: tuple, end: tuple) -> list:
    """OSRM real road route — returns list of (lat, lon)."""
    url = (f"http://router.project-osrm.org/route/v1/driving/"
           f"{start[1]},{start[0]};{end[1]},{end[0]}"
           f"?overview=full&geometries=geojson")
    try:
        r = _SESSION.get(url, timeout=8)
        data = r.json()
        if data.get("code") == "Ok":
            coords = data["routes"][0]["geometry"]["coordinates"]
            return [(c[1], c[0]) for c in coords]
    except Exception:
        pass
    lats = np.linspace(start[0], end[0], 40)
    lons = np.linspace(start[1], end[1], 40)
    return list(zip(lats, lons))


def find_hotspots_on_route(route_coords: list,
                            hotspots,
                            warn_radius_m: float = 500) -> list:
    """
    For each hotspot, find the CLOSEST point on the route.
    Only alert if that minimum distance <= warn_radius_m.
    This ensures hotspots off the road are never shown.
    """
    hs_lats = hotspots["latitude"].values
    hs_lons = hotspots["longitude"].values
    r_lats  = np.array([c[0] for c in route_coords])
    r_lons  = np.array([c[1] for c in route_coords])

    alerts = []

    for hi in range(len(hotspots)):
        # distance from this hotspot to EVERY route point
        dists = _haversine_vectorized(
            hs_lats[hi], hs_lons[hi], r_lats, r_lons
        )
        min_dist = dists.min()
        if min_dist > warn_radius_m:
            continue   # hotspot not close enough to route — skip

        closest_route_idx = int(dists.argmin())
        hs = hotspots.iloc[hi]
        alerts.append({
            "cluster_id":      int(hs["cluster_id"]),
            "hotspot_lat":     float(hs["latitude"]),
            "hotspot_lon":     float(hs["longitude"]),
            "distance_m":      int(min_dist),
            "total_accidents": int(hs["total_accidents"]),
            "fatal":           int(hs["fatal"]),
            "casualties":      int(hs["casualties"]),
            "avg_risk":        float(hs["avg_risk"]),
            "risk_level":      hs["risk_level"],
            "top_cause":       hs["top_cause"],
            "top_weather":     hs["top_weather"],
            "peak_hour":       int(hs["peak_hour"]),
            "night_pct":       int(hs.get("night_pct", 0)),
            "top_day":         str(hs.get("top_day", "Monday")),
            "why":             hs["why"],
            "route_idx":       closest_route_idx,
        })

    alerts.sort(key=lambda x: x["route_idx"])
    return alerts
