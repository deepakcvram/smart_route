import math
from utils.hotspot_engine import haversine_meters

# Configurable default risk weights for hotspot categories
DEFAULT_RISK_WEIGHTS = {
    "HIGH": 3.0,
    "MEDIUM": 2.0,
    "LOW": 1.0,
}

# Configurable score categories (thresholds and labels)
DEFAULT_SCORE_CATEGORIES = [
    (80, 100, "LOWER RELATIVE RISK", "#39FF14"),
    (60, 79,  "MODERATE RELATIVE RISK", "#FF8C42"),
    (0,  59,  "HIGHER RELATIVE RISK", "#FF3B3B"),
]


def calculate_route_distance_km(route_coords: list) -> float:
    """
    Calculate the cumulative driving distance along route coordinates in kilometers.
    Uses haversine distance between consecutive GPS points.
    Returns 0.0 if route_coords is empty or invalid.
    """
    if not route_coords or len(route_coords) < 2:
        return 0.0
    try:
        total_m = 0.0
        for i in range(len(route_coords) - 1):
            p1 = route_coords[i]
            p2 = route_coords[i + 1]
            total_m += haversine_meters(p1[0], p1[1], p2[0], p2[1])
        return round(total_m / 1000.0, 1)
    except Exception:
        return 0.0


def calculate_route_safety_score(
    alerts: list,
    route_distance_km: float = None,
    weights: dict = None,
    categories: list = None,
    k: float = 0.08,
) -> dict:
    """
    Calculate a transparent, comparative Route Safety Score (0-100) based on
    hotspots identified along the route, weighted by severity and normalized
    by route exposure (distance in km).

    Formula:
      weighted_risk = sum(count_i * weight_i) for unique hotspots
      exposure_density = weighted_risk / (max(distance_km, 5.0) / 100.0)
      normalized_risk = exposure_density * k
      bounded_risk = 1.0 - exp(-normalized_risk)
      safety_score = round(100.0 * (1.0 - bounded_risk))

    Higher safety_score indicates lower estimated relative accident risk.
    """
    if weights is None:
        weights = DEFAULT_RISK_WEIGHTS
    if categories is None:
        categories = DEFAULT_SCORE_CATEGORIES

    # Deduplicate hotspots by cluster_id so multiple detections of the same cluster are counted once
    unique_hotspots = []
    seen_clusters = set()
    for a in alerts or []:
        cid = a.get("cluster_id")
        if cid is not None:
            if cid in seen_clusters:
                continue
            seen_clusters.add(cid)
        unique_hotspots.append(a)

    high_count = sum(1 for a in unique_hotspots if a.get("risk_level") == "HIGH")
    med_count  = sum(1 for a in unique_hotspots if a.get("risk_level") == "MEDIUM")
    low_count  = sum(1 for a in unique_hotspots if a.get("risk_level") == "LOW")
    total_count = len(unique_hotspots)

    # Use actual distance or a sensible baseline
    if route_distance_km is not None and route_distance_km > 0:
        dist_km = float(route_distance_km)
    else:
        dist_km = 25.0  # fallback assumption for city trip

    # Calculate weighted risk points
    weighted_risk = (
        high_count * weights.get("HIGH", 3.0) +
        med_count  * weights.get("MEDIUM", 2.0) +
        low_count  * weights.get("LOW", 1.0)
    )

    if total_count == 0:
        score = 98
        exposure_density = 0.0
    else:
        # Route exposure: weighted points per 100 km of road
        exposure_density = weighted_risk / (max(dist_km, 5.0) / 100.0)
        norm_risk = exposure_density * k
        bounded_risk = 1.0 - math.exp(-norm_risk)
        score = max(0, min(100, round(100.0 * (1.0 - bounded_risk))))

    # Determine risk category and color
    risk_category = "MODERATE RELATIVE RISK"
    risk_color = "#FF8C42"
    for low_th, high_th, cat_name, col in categories:
        if low_th <= score <= high_th:
            risk_category = cat_name
            risk_color = col
            break

    disclaimer = (
        "Heuristic route risk indicator based on historical hotspot density and severity exposure. "
        "Does not represent guaranteed safety or statistical probability of a collision."
    )

    return {
        "safety_score": score,
        "risk_category": risk_category,
        "risk_color": risk_color,
        "total_hotspots": total_count,
        "high_count": high_count,
        "medium_count": med_count,
        "low_count": low_count,
        "weighted_risk": weighted_risk,
        "route_distance_km": round(dist_km, 1),
        "exposure_density": round(exposure_density, 2),
        "disclaimer": disclaimer,
    }


def get_safety_recommendation(hotspot: dict) -> str:
    """
    Returns an actionable, crisp safety recommendation tailored to the hotspot's
    primary cause, peak hour, and fatality/casualty profile.
    """
    cause = str(hotspot.get("top_cause", "")).lower()
    risk_level = str(hotspot.get("risk_level", "MEDIUM")).upper()
    fatal = hotspot.get("fatal", 0)
    night_pct = hotspot.get("night_pct", 0)

    recommendations = []

    if cause == "overspeeding":
        recommendations.append("Strictly adhere to posted speed limits and avoid sudden overtaking maneuvers.")
    elif cause == "drunk driving":
        recommendations.append("High incidence of impaired driving recorded here; stay alert for erratic vehicle behavior.")
    elif cause == "poor road":
        recommendations.append("Watch for potholes, uneven road surface, and sudden lane narrowing ahead.")
    elif cause == "weather":
        recommendations.append("Hazardous road surface conditions; increase following distance to at least 4 seconds.")
    elif cause == "distraction":
        recommendations.append("High driver inattention corridor; minimize phone/in-cabin distractions and keep full focus.")
    else:
        recommendations.append("Exercise defensive driving and maintain a safe following distance.")

    if fatal > 0 and risk_level == "HIGH":
        recommendations.append("Critical high-severity zone with history of fatal collisions — reduce speed now.")
    elif night_pct > 40:
        recommendations.append("Ensure headlights are on low-beam and watch for unlit two-wheelers or pedestrians.")

    return " ".join(recommendations)
