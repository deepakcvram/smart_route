import requests
from config import OPENWEATHER_KEY, GEMINI_KEY

# ── OpenWeatherMap ────────────────────────────────────────────────────────────
def get_live_weather(lat: float, lon: float) -> dict:
    """Returns {description, temp, wind_speed, is_rain, is_fog, is_fallback} for given coords.
    is_fallback=True means the API key is missing/invalid or the request failed;
    the returned values are defaults and do NOT represent actual conditions.
    """
    if not OPENWEATHER_KEY or not OPENWEATHER_KEY.strip():
        return _default_weather(is_fallback=True, reason="no_key")
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat":   lat,
                "lon":   lon,
                "appid": OPENWEATHER_KEY,
                "units": "metric",
            },
            timeout=6,
        )
        d = r.json()
        if d.get("cod") != 200:
            return _default_weather(is_fallback=True, reason=str(d.get("message", "API error")))
        weather_id   = d["weather"][0]["id"]
        description  = d["weather"][0]["description"].title()
        temp         = d["main"]["temp"]
        humidity     = d["main"].get("humidity", None)
        wind_speed   = d["wind"]["speed"] * 3.6  # convert m/s -> km/h
        is_rain      = weather_id < 700
        is_fog       = 700 <= weather_id < 800
        return {
            "description": description,
            "temp":        temp,
            "humidity":    humidity,
            "wind_speed":  wind_speed,
            "is_rain":     is_rain,
            "is_fog":      is_fog,
            "raw":         description.lower(),
            "is_fallback": False,
        }
    except Exception as exc:
        return _default_weather(is_fallback=True, reason=str(exc))


def _default_weather(is_fallback: bool = True, reason: str = "unknown") -> dict:
    return {
        "description": "Clear",
        "temp": 28.0,
        "humidity": None,
        "wind_speed": 5.0,
        "is_rain": False,
        "is_fog": False,
        "raw": "clear",
        "is_fallback": is_fallback,
        "fallback_reason": reason,
    }



# ── Gemini description generator ─────────────────────────────────────────────
def generate_alert_description(hotspot: dict, weather: dict) -> str:
    """
    Use Gemini to generate a crisp, driver-focused alert description.
    Falls back to rule-based description if Gemini key not set or fails.
    """
    if not GEMINI_KEY:
        return _fallback_description(hotspot, weather)

    prompt = f"""
You are a road safety AI assistant. Generate a SHORT, crisp driver alert message (max 3 sentences) 
for a driver approaching an accident hotspot. Use a calm but urgent tone. 
Do NOT use markdown. Write as if speaking directly to the driver.

Hotspot data:
- Total accidents recorded: {hotspot['total_accidents']}
- Fatal accidents: {hotspot['fatal']}
- Total casualties: {hotspot['casualties']}
- Primary cause: {hotspot['top_cause']}
- Peak accident hour: {hotspot['peak_hour']:02d}:00
- Most common weather: {hotspot['top_weather']}
- Night accident percentage: {hotspot['night_pct']}%
- Current weather: {weather['description']}, {weather['temp']:.0f}°C, wind {weather['wind_speed']:.0f} km/h

Generate the alert now:
""".strip()

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=10,
        )
        data = r.json()
        text = (data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", ""))
        if text.strip():
            return text.strip()
    except Exception:
        pass

    return _fallback_description(hotspot, weather)


def _fallback_description(hotspot: dict, weather: dict) -> str:
    """Rule-based fallback when Gemini is unavailable."""
    parts = []

    cause_msg = {
        "weather":       "adverse weather conditions",
        "distraction":   "driver distraction",
        "overspeeding":  "overspeeding",
        "drunk driving": "drunk driving incidents",
        "poor road":     "poor road surface",
    }
    parts.append(
        f"This zone has recorded {hotspot['total_accidents']} accidents "
        f"primarily due to {cause_msg.get(hotspot['top_cause'], 'multiple risk factors')}."
    )

    if hotspot["fatal"] > 0:
        parts.append(f"{hotspot['fatal']} of these were fatal.")

    if weather["is_fog"]:
        parts.append("Foggy conditions right now — severely reduced visibility ahead.")
    elif weather["is_rain"]:
        parts.append("Wet road conditions active — increased braking distance.")
    elif hotspot["top_weather"] == "fog":
        parts.append("This stretch is frequently affected by fog.")

    if hotspot.get("night_pct", 0) > 40:
        parts.append(f"{hotspot.get('night_pct',0)}% of accidents here occur at night.")

    parts.append("Reduce speed and stay alert.")
    return " ".join(parts)
