import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.hotspot_engine import load_hotspots
from utils.route_analyzer import geocode, get_road_route, find_hotspots_on_route
from utils.ai_description import get_live_weather, generate_alert_description
from utils.route_safety import (
    calculate_route_distance_km,
    calculate_route_safety_score,
    get_safety_recommendation,
)
import plotly.graph_objects as go

def run_e2e_check():
    print("Loading hotspots...")
    hs = load_hotspots()
    print("Hotspots count:", len(hs))

    c1 = (13.0827, 80.2707)
    c2 = (12.9716, 77.5946)
    print("Fetching road route Chennai -> Bangalore...")
    route = get_road_route(c1, c2)
    print("Route points:", len(route))

    dist_km = calculate_route_distance_km(route)
    print(f"Route Distance: {dist_km} km")

    alerts = find_hotspots_on_route(route, hs, warn_radius_m=1000)
    print(f"Hotspots found on route: {len(alerts)}")

    weather = get_live_weather(route[len(route)//2][0], route[len(route)//2][1])
    print("Live Weather:", weather)

    enriched = []
    for a in alerts:
        desc = generate_alert_description(a, weather)
        rec = get_safety_recommendation(a)
        enriched.append({**a, 'weather': weather, 'ai_desc': desc, 'safety_recommendation': rec})

    safety_info = calculate_route_safety_score(enriched, route_distance_km=dist_km)
    print("\n=== ROUTE RISK SUMMARY DASHBOARD METRICS ===")
    print(f"Safety Score: {safety_info['safety_score']} / 100")
    print(f"Risk Category: {safety_info['risk_category']}")
    print(f"Total Hotspots: {safety_info['total_hotspots']}")
    print(f"High: {safety_info['high_count']}, Medium: {safety_info['medium_count']}, Low: {safety_info['low_count']}")
    print(f"Route Exposure Density: {safety_info['exposure_density']} pts / 100 km")

    if enriched:
        card0 = enriched[0]
        print("\n=== SAMPLE HOTSPOT EXPLANATION CARD ===")
        print(f"Hotspot Cluster ID: #{card0.get('cluster_id')}")
        print(f"Risk Level: {card0.get('risk_level')}")
        print(f"Historical Accidents: {card0.get('total_accidents')}")
        print(f"Fatal Accidents: {card0.get('fatal')}")
        print(f"Casualties: {card0.get('casualties')}")
        print(f"Primary Cause: {card0.get('top_cause')}")
        print(f"Peak Hour: {card0.get('peak_hour'):02d}:00")
        print(f"Night Incidents %: {card0.get('night_pct')}%")
        print(f"Distance from Route: {card0.get('distance_m')} m")
        print(f"Safety Recommendation: {card0.get('safety_recommendation')}")

    # Build Plotly Figure
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["HIGH", "MEDIUM", "LOW"],
        y=[safety_info['high_count'], safety_info['medium_count'], safety_info['low_count']],
        marker=dict(color=["#FF3B3B", "#FF8C42", "#39FF14"]),
    ))
    print("\nPlotly figure created successfully!")
    print("ALL E2E PIPELINE CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_e2e_check()
