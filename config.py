import os

def _load_env_file():
    """Load key-value pairs from .env if present without external dependencies."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

# API Keys (loaded from environment variables, .env file, or direct configuration)
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY", "").strip()
NEWSAPI_KEY     = os.environ.get("NEWSAPI_KEY", "").strip()
GEMINI_KEY      = os.environ.get("GEMINI_KEY", "").strip()

CITIES = [
    "Chennai", "Mumbai", "Delhi", "Bangalore",
    "Hyderabad", "Pune", "Kolkata", "Chandigarh"
]

CITY_COORDS = {
    "Chennai":    (13.0827, 80.2707),
    "Mumbai":     (19.0760, 72.8777),
    "Delhi":      (28.6139, 77.2090),
    "Bangalore":  (12.9716, 77.5946),
    "Hyderabad":  (17.3850, 78.4867),
    "Pune":       (18.5204, 73.8567),
    "Kolkata":    (22.5726, 88.3639),
    "Chandigarh": (30.7333, 76.7794),
}

NEWS_FETCH_DAYS   = 30    # look back window for news
RETRAIN_HOUR      = 2     # 2 AM daily auto-retrain
WARN_RADIUS_M     = 500   # hotspot alert radius in metres — only truly on-route hotspots
HOTSPOT_PATH      = "sample_data/hotspots.pkl"
MODEL_PATH        = "sample_data/risk_model.pkl"
RETRAIN_LOG_PATH  = "sample_data/retrain_log.json"
NEWS_CACHE_PATH   = "sample_data/news_cache.json"
