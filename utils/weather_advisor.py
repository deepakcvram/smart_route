"""
Weather-Based Driving Recommendations module.
Analyzes live weather data against route hotspot history to deliver
targeted driving precautions and contextual safety advisories.
"""

def get_weather_safety_advisory(weather: dict, alerts: list = None) -> dict:
    """
    Generate driving precautions based on current weather conditions and
    corridor hotspot history.

    Returns a structured dictionary:
      - condition_title: str
      - condition_color: str (#39FF14, #FF8C42, #FF3B3B, #00D4FF)
      - condition_icon: str (FontAwesome icon name)
      - warnings: list of str
      - precautions: list of str
      - contextual_alerts: list of str (correlation with hotspot history)
      - is_fallback: bool
      - disclaimer: str
    """
    if not weather:
        weather = {}

    desc = str(weather.get("description", "Clear")).title()
    temp = weather.get("temp", 28.0)
    wind = weather.get("wind_speed", 5.0)
    is_rain = weather.get("is_rain", False)
    is_fog = weather.get("is_fog", False)
    raw = str(weather.get("raw", "")).lower()

    # Detect high winds or storms
    is_storm = "storm" in raw or "thunder" in raw or "cyclone" in raw or "squall" in raw
    is_high_wind = wind >= 35.0 or "wind" in raw
    is_mist_or_haze = "haze" in raw or "mist" in raw or "smoke" in raw

    warnings = []
    precautions = []
    contextual_alerts = []

    # Determine condition category, icon, and color
    if is_storm:
        title = f"Severe Weather Warning: {desc}"
        color = "#FF3B3B"
        icon = "cloud-bolt"
        warnings.append("Active thunderstorm / severe weather detected along the route corridor.")
        warnings.append("High risk of sudden hydroplaning, flash waterlogging, and severe wind gusts.")
        precautions.append("Delay non-essential travel until severe convective storm passes.")
        precautions.append("Reduce speed by at least 30-40% and double your following distance.")
        precautions.append("Avoid sheltering under large trees, billboards, or old overhead structures.")
    elif is_rain:
        title = f"Wet Road Advisory: {desc}"
        color = "#FF8C42"
        icon = "cloud-showers-heavy"
        warnings.append("Wet road surfaces active along corridor — braking distance increases by up to 2x.")
        warnings.append("Reduced tire grip and potential standing water on highway fast lanes.")
        precautions.append("Maintain a minimum 4-second following distance from preceding vehicles.")
        precautions.append("Avoid harsh sudden braking or aggressive steering inputs to prevent skids.")
        precautions.append("Ensure windshield wipers are functional and use low-beam headlights.")
    elif is_fog or is_mist_or_haze:
        title = f"Low Visibility Advisory: {desc}"
        color = "#FF8C42"
        icon = "smog"
        warnings.append("Dense fog or haze is reducing forward sight distance across this stretch.")
        warnings.append("High risk of rear-end collisions and delayed reaction times.")
        precautions.append("Switch to low-beam headlights or front fog lamps; avoid high beams which reflect back.")
        precautions.append("Reduce speed significantly to ensure you can stop within visible road distance.")
        precautions.append("Avoid overtaking maneuvers on two-lane corridors; follow lane edge markings.")
    elif is_high_wind:
        title = f"Crosswind Advisory: High Winds ({wind:.0f} km/h)"
        color = "#FF8C42"
        icon = "wind"
        warnings.append("Elevated crosswinds recorded along corridor.")
        precautions.append("Maintain firm two-handed steering, especially on elevated bridges and open bypasses.")
        precautions.append("Allow extra clearance when passing high-sided trucks, buses, or two-wheelers.")
    else:
        title = f"Normal Road Conditions: {desc}"
        color = "#39FF14"
        icon = "sun"
        warnings.append("No adverse weather phenomena currently identified from route midpoint data.")
        precautions.append("Standard defensive driving practices apply; clear weather does not guarantee absence of hazards.")
        precautions.append("Maintain legal speed limits and be vigilant for sudden pedestrian or vehicular incursions.")

    # Contextual correlation with route hotspot history
    if alerts:
        weather_prone_hotspots = [
            a for a in alerts
            if str(a.get("top_weather", "")).lower() in ["fog", "foggy", "rain", "rainy", "stormy"]
        ]
        if weather_prone_hotspots and (is_rain or is_fog or is_storm):
            contextual_alerts.append(
                f"CORRIDOR RISK MULTIPLIER: {len(weather_prone_hotspots)} accident hotspot(s) along your route "
                f"historically recorded adverse weather incidents. Active {desc.lower()} conditions require heightened caution at these coordinates."
            )

        night_prone_hotspots = [
            a for a in alerts
            if a.get("night_pct", 0) > 40
        ]
        if night_prone_hotspots:
            contextual_alerts.append(
                f"{len(night_prone_hotspots)} hotspot(s) on your route experience over 40% of their collisions at night. "
                "Ensure clean headlamp lenses and watch for unlit commercial vehicles or tractors."
            )

    disclaimer = (
        "Weather observations are retrieved for the geographic midpoint of the route and may vary "
        "across the corridor. Recommendations are advisory heuristics based on standard road safety principles."
    )

    return {
        "condition_title": title,
        "condition_color": color,
        "condition_icon": icon,
        "temp": temp,
        "wind_speed": wind,
        "description": desc,
        "warnings": warnings,
        "precautions": precautions,
        "contextual_alerts": contextual_alerts,
        "disclaimer": disclaimer,
    }
