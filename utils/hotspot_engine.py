import pandas as pd
import numpy as np
import joblib
import os
from sklearn.cluster import DBSCAN
from math import radians, sin, cos, sqrt, atan2

DS1_PATH  = "Dataset1 Folder/indian_roads_dataset.csv"
DS2_PATH  = "Dataset2 Folder/accident_prediction_india.csv"
HOTSPOT_PATH = "sample_data/hotspots.pkl"

# ── severity mapping ──────────────────────────────────────────────────────────
SEV_MAP = {
    # DS1
    "fatal": 3, "major": 2, "minor": 1,
    # DS2
    "Fatal": 3, "Serious": 2, "Minor": 1,
}

CAUSE_MSG = {
    "weather":       "Adverse weather conditions (fog/rain) reported at this stretch.",
    "distraction":   "High driver distraction incidents recorded here.",
    "overspeeding":  "Overspeeding is the primary cause of accidents at this location.",
    "drunk driving": "Drunk driving incidents frequently reported at this spot.",
    "poor road":     "Poor road surface conditions contribute to accidents here.",
}

LOCATION_MSG = {
    "Curve":         "Sharp curve ahead — reduced sight distance.",
    "Intersection":  "Busy intersection with high vehicle conflict.",
    "Bridge":        "Bridge section — narrow lanes and sudden drops.",
    "Straight Road": "High-speed straight stretch with frequent overtaking.",
}

WEATHER_MSG = {
    "fog": "Dense fog — severely reduced visibility.",
    "Foggy": "Dense fog — severely reduced visibility.",
    "Hazy": "Hazy conditions — reduced visibility ahead.",
    "rain": "Wet road surface — increased skid risk.",
    "Rainy": "Wet road surface — increased skid risk.",
    "Stormy": "Storm conditions — extreme caution required.",
}

VEHICLE_MSG = {
    "Two-Wheeler": "High two-wheeler accident zone — watch for bikes.",
    "Truck":       "Heavy vehicle conflict zone — maintain safe distance.",
    "Pedestrian":  "High pedestrian activity — slow down.",
    "Bus":         "Frequent bus-related accidents — watch for sudden stops.",
    "Auto-Rickshaw": "High auto-rickshaw conflict — narrow lane risk.",
}


def haversine_meters(lat1, lon1, lat2, lon2) -> float:
    """Distance in metres between two GPS points."""
    R = 6_371_000
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _load_ds1() -> pd.DataFrame:
    df = pd.read_csv(DS1_PATH)
    df = df.rename(columns={
        "accident_severity": "severity_raw",
        "road_type":         "road_type",
        "weather":           "weather",
        "cause":             "cause",
        "casualties":        "casualties",
        "vehicles_involved": "vehicles_involved",
        "hour":              "hour",
        "day_of_week":       "day_of_week",
        "risk_score":        "risk_score",
        "traffic_density":   "traffic_density",
        "visibility":        "visibility",
        "is_peak_hour":      "is_peak_hour",
    })
    df["severity"] = df["severity_raw"].map(SEV_MAP).fillna(1)
    df["source"]   = "ds1"
    df["alcohol"]  = 0
    df["location_type"] = "Straight Road"
    df["vehicle_type"]  = "Car"
    return df[[
        "latitude","longitude","severity","severity_raw","weather","road_type",
        "cause","casualties","vehicles_involved","hour","day_of_week",
        "risk_score","traffic_density","visibility","is_peak_hour",
        "alcohol","location_type","vehicle_type","source"
    ]]


def _load_ds2() -> pd.DataFrame:
    df = pd.read_csv(DS2_PATH)
    df = df.rename(columns={
        "Accident Severity":        "severity_raw",
        "Weather Conditions":       "weather",
        "Road Type":                "road_type",
        "Number of Casualties":     "casualties",
        "Number of Fatalities":     "fatalities",
        "Number of Vehicles Involved": "vehicles_involved",
        "Time of Day":              "time_raw",
        "Day of Week":              "day_of_week",
        "Accident Location Details":"location_type",
        "Vehicle Type Involved":    "vehicle_type",
        "Alcohol Involvement":      "alcohol_raw",
        "Speed Limit (km/h)":       "speed_limit",
        "Lighting Conditions":      "lighting",
        "Road Condition":           "road_condition",
    })
    df["severity"]  = df["severity_raw"].map(SEV_MAP).fillna(1)
    df["hour"]      = pd.to_datetime(df["time_raw"], format="%H:%M", errors="coerce").dt.hour.fillna(12).astype(int)
    df["alcohol"]   = (df["alcohol_raw"] == "Yes").astype(int)
    df["cause"]     = df.apply(_infer_cause, axis=1)
    df["risk_score"] = df["severity"] / 3.0
    df["traffic_density"] = "medium"
    df["visibility"]      = df["lighting"].map(
        {"Dark": "low", "Dusk": "low", "Dawn": "medium", "Daylight": "high"}
    ).fillna("medium")
    df["is_peak_hour"] = df["hour"].apply(lambda h: 1 if h in range(7,10) or h in range(17,20) else 0)
    # DS2 has no GPS — will be enriched via city centroid later
    df["latitude"]  = np.nan
    df["longitude"] = np.nan
    df["source"]    = "ds2"
    return df[[
        "latitude","longitude","severity","severity_raw","weather","road_type",
        "cause","casualties","vehicles_involved","hour","day_of_week",
        "risk_score","traffic_density","visibility","is_peak_hour",
        "alcohol","location_type","vehicle_type","source"
    ]]


def _infer_cause(row) -> str:
    if row.get("alcohol_raw") == "Yes":
        return "drunk driving"
    rc = str(row.get("road_condition","")).lower()
    if rc in ("damaged","under construction"):
        return "poor road"
    wc = str(row.get("weather","")).lower()
    if wc in ("foggy","rainy","hazy","stormy"):
        return "weather"
    lt = str(row.get("location_type","")).lower()
    if lt in ("curve","bridge"):
        return "poor road"
    return "distraction"


def build_hotspots(eps_meters=800, min_samples=3) -> pd.DataFrame:
    """
    Cluster DS1 accidents with DBSCAN.
    Each cluster = one hotspot with aggregated stats + why description.
    Returns DataFrame of hotspot centroids.
    """
    df = _load_ds1()
    ds2 = _load_ds2()

    # DBSCAN in radians (haversine metric)
    coords = df[["latitude","longitude"]].values
    eps_rad = eps_meters / 6_371_000  # metres → radians
    labels  = DBSCAN(
        eps=eps_rad, min_samples=min_samples, metric="haversine"
    ).fit_predict(np.radians(coords))

    df["cluster"] = labels
    clustered = df[df["cluster"] >= 0].copy()

    hotspots = []
    for cid, grp in clustered.groupby("cluster"):
        center_lat = grp["latitude"].mean()
        center_lon = grp["longitude"].mean()
        n          = len(grp)
        fatal      = (grp["severity"] == 3).sum()
        serious    = (grp["severity"] == 2).sum()
        top_cause  = grp["cause"].mode()[0] if not grp["cause"].mode().empty else "unknown"
        top_weather= grp["weather"].mode()[0] if not grp["weather"].mode().empty else "clear"
        peak_hour  = int(grp["hour"].mode()[0]) if not grp["hour"].mode().empty else 12
        top_day    = grp["day_of_week"].mode()[0] if not grp["day_of_week"].mode().empty else "Monday"
        avg_risk   = grp["risk_score"].mean()
        tot_cas    = int(grp["casualties"].sum())
        top_vis    = grp["visibility"].mode()[0] if not grp["visibility"].mode().empty else "high"
        night_pct  = int((grp["hour"].apply(lambda h: h < 6 or h > 20).sum() / n) * 100)

        why = _build_why(top_cause, top_weather, peak_hour, top_day,
                         fatal, n, top_vis, night_pct)

        hotspots.append({
            "cluster_id":   cid,
            "latitude":     round(center_lat, 6),
            "longitude":    round(center_lon, 6),
            "total_accidents": n,
            "fatal":        int(fatal),
            "serious":      int(serious),
            "casualties":   tot_cas,
            "avg_risk":     round(avg_risk, 3),
            "top_cause":    top_cause,
            "top_weather":  top_weather,
            "peak_hour":    peak_hour,
            "top_day":      top_day,
            "night_pct":    night_pct,
            "why":          why,
            "risk_level":   "HIGH" if avg_risk >= 0.6 else ("MEDIUM" if avg_risk >= 0.35 else "LOW"),
        })

    hotspot_df = pd.DataFrame(hotspots)
    os.makedirs("sample_data", exist_ok=True)
    joblib.dump(hotspot_df, HOTSPOT_PATH)
    return hotspot_df


def _build_why(cause, weather, peak_hour, top_day,
               fatal, total, visibility, night_pct) -> str:
    parts = []

    # cause
    parts.append(CAUSE_MSG.get(cause, "Multiple risk factors recorded here."))

    # weather
    if weather in WEATHER_MSG:
        parts.append(WEATHER_MSG[weather])

    # time
    if night_pct > 40:
        parts.append(f"{night_pct}% of accidents occur at night — poor visibility zone.")
    else:
        parts.append(f"Peak accident time: {peak_hour:02d}:00–{(peak_hour+2)%24:02d}:00 hrs.")

    # fatality
    fatal_pct = int((fatal / total) * 100) if total > 0 else 0
    if fatal_pct >= 30:
        parts.append(f"{fatal_pct}% of incidents here were fatal.")

    return " ".join(parts)


def load_hotspots() -> pd.DataFrame:
    if os.path.exists(HOTSPOT_PATH):
        return joblib.load(HOTSPOT_PATH)
    return build_hotspots()


def get_nearby_hotspots(lat: float, lon: float,
                         hotspots: pd.DataFrame,
                         radius_m: float = 500) -> pd.DataFrame:
    """Return hotspots within radius_m metres of current position."""
    if hotspots.empty:
        return hotspots
    hotspots = hotspots.copy()
    hotspots["distance_m"] = hotspots.apply(
        lambda r: haversine_meters(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    nearby = hotspots[hotspots["distance_m"] <= radius_m].sort_values("distance_m")
    return nearby


_DS1_CACHED = None


def get_historical_accident_points(route_coords=None, max_points=2500):
    """
    Returns a list of [latitude, longitude, weight] for HeatMap rendering.
    Filters invalid coordinates. If route_coords is provided, extracts
    historical points within the route's bounding box (+ margin) for a
    route-focused heatmap; otherwise returns representative regional points.
    """
    global _DS1_CACHED
    if _DS1_CACHED is None:
        try:
            _DS1_CACHED = _load_ds1()
        except Exception:
            return []

    df = _DS1_CACHED.dropna(subset=["latitude", "longitude"])
    if df.empty:
        return []

    if route_coords and len(route_coords) > 1:
        lats = [c[0] for c in route_coords]
        lons = [c[1] for c in route_coords]
        margin = 0.18  # roughly ~20km corridor margin
        min_lat, max_lat = min(lats) - margin, max(lats) + margin
        min_lon, max_lon = min(lons) - margin, max(lons) + margin

        filtered = df[
            (df["latitude"] >= min_lat) & (df["latitude"] <= max_lat) &
            (df["longitude"] >= min_lon) & (df["longitude"] <= max_lon)
        ]
        if not filtered.empty:
            df = filtered

    if len(df) > max_points:
        df = df.sample(n=max_points, random_state=42)

    # Weight by severity (1=minor, 2=major, 3=fatal)
    heat_data = [
        [float(r["latitude"]), float(r["longitude"]), float(r.get("severity", 1)) / 3.0]
        for _, r in df.iterrows()
    ]
    return heat_data

