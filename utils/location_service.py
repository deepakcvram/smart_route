"""
Location Autocomplete and Typo Correction Service.
Provides high-speed local candidate matching, Nominatim geocoding,
and fuzzy typo correction for Indian and global locations.
"""

import difflib
import requests
import functools

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "SafeRouteAI-LocationService/2.0"})

# Comprehensive database of major Indian cities, state capitals, and transit hubs
INDIAN_CITIES_REGISTRY = {
    "Bengaluru": {"display_name": "Bengaluru (Bangalore), Karnataka, India", "city": "Bengaluru", "state": "Karnataka", "country": "India", "lat": 12.9716, "lon": 77.5946},
    "Bangalore": {"display_name": "Bengaluru (Bangalore), Karnataka, India", "city": "Bengaluru", "state": "Karnataka", "country": "India", "lat": 12.9716, "lon": 77.5946},
    "Mumbai": {"display_name": "Mumbai, Maharashtra, India", "city": "Mumbai", "state": "Maharashtra", "country": "India", "lat": 19.0760, "lon": 72.8777},
    "Bombay": {"display_name": "Mumbai, Maharashtra, India", "city": "Mumbai", "state": "Maharashtra", "country": "India", "lat": 19.0760, "lon": 72.8777},
    "Chennai": {"display_name": "Chennai (Madras), Tamil Nadu, India", "city": "Chennai", "state": "Tamil Nadu", "country": "India", "lat": 13.0827, "lon": 80.2707},
    "Madras": {"display_name": "Chennai (Madras), Tamil Nadu, India", "city": "Chennai", "state": "Tamil Nadu", "country": "India", "lat": 13.0827, "lon": 80.2707},
    "Delhi": {"display_name": "New Delhi, Delhi, India", "city": "Delhi", "state": "Delhi", "country": "India", "lat": 28.6139, "lon": 77.2090},
    "New Delhi": {"display_name": "New Delhi, Delhi, India", "city": "New Delhi", "state": "Delhi", "country": "India", "lat": 28.6139, "lon": 77.2090},
    "Hyderabad": {"display_name": "Hyderabad, Telangana, India", "city": "Hyderabad", "state": "Telangana", "country": "India", "lat": 17.3850, "lon": 78.4867},
    "Pune": {"display_name": "Pune, Maharashtra, India", "city": "Pune", "state": "Maharashtra", "country": "India", "lat": 18.5204, "lon": 73.8567},
    "Kolkata": {"display_name": "Kolkata (Calcutta), West Bengal, India", "city": "Kolkata", "state": "West Bengal", "country": "India", "lat": 22.5726, "lon": 88.3639},
    "Calcutta": {"display_name": "Kolkata (Calcutta), West Bengal, India", "city": "Kolkata", "state": "West Bengal", "country": "India", "lat": 22.5726, "lon": 88.3639},
    "Chandigarh": {"display_name": "Chandigarh, Punjab/Haryana, India", "city": "Chandigarh", "state": "Punjab", "country": "India", "lat": 30.7333, "lon": 76.7794},
    "Ahmedabad": {"display_name": "Ahmedabad, Gujarat, India", "city": "Ahmedabad", "state": "Gujarat", "country": "India", "lat": 23.0225, "lon": 72.5714},
    "Jaipur": {"display_name": "Jaipur, Rajasthan, India", "city": "Jaipur", "state": "Rajasthan", "country": "India", "lat": 26.9124, "lon": 75.7873},
    "Lucknow": {"display_name": "Lucknow, Uttar Pradesh, India", "city": "Lucknow", "state": "Uttar Pradesh", "country": "India", "lat": 26.8467, "lon": 80.9462},
    "Coimbatore": {"display_name": "Coimbatore, Tamil Nadu, India", "city": "Coimbatore", "state": "Tamil Nadu", "country": "India", "lat": 11.0168, "lon": 76.9558},
    "Madurai": {"display_name": "Madurai, Tamil Nadu, India", "city": "Madurai", "state": "Tamil Nadu", "country": "India", "lat": 9.9252, "lon": 78.1198},
    "Kochi": {"display_name": "Kochi (Cochin), Kerala, India", "city": "Kochi", "state": "Kerala", "country": "India", "lat": 9.9312, "lon": 76.2673},
    "Cochin": {"display_name": "Kochi (Cochin), Kerala, India", "city": "Kochi", "state": "Kerala", "country": "India", "lat": 9.9312, "lon": 76.2673},
    "Thiruvananthapuram": {"display_name": "Thiruvananthapuram (Trivandrum), Kerala, India", "city": "Thiruvananthapuram", "state": "Kerala", "country": "India", "lat": 8.5241, "lon": 76.9366},
    "Trivandrum": {"display_name": "Thiruvananthapuram (Trivandrum), Kerala, India", "city": "Thiruvananthapuram", "state": "Kerala", "country": "India", "lat": 8.5241, "lon": 76.9366},
    "Mysuru": {"display_name": "Mysuru (Mysore), Karnataka, India", "city": "Mysuru", "state": "Karnataka", "country": "India", "lat": 12.2958, "lon": 76.6394},
    "Mysore": {"display_name": "Mysuru (Mysore), Karnataka, India", "city": "Mysuru", "state": "Karnataka", "country": "India", "lat": 12.2958, "lon": 76.6394},
    "Visakhapatnam": {"display_name": "Visakhapatnam (Vizag), Andhra Pradesh, India", "city": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India", "lat": 17.6868, "lon": 83.2185},
    "Vizag": {"display_name": "Visakhapatnam (Vizag), Andhra Pradesh, India", "city": "Visakhapatnam", "state": "Andhra Pradesh", "country": "India", "lat": 17.6868, "lon": 83.2185},
    "Vijayawada": {"display_name": "Vijayawada, Andhra Pradesh, India", "city": "Vijayawada", "state": "Andhra Pradesh", "country": "India", "lat": 16.5062, "lon": 80.6480},
    "Nagpur": {"display_name": "Nagpur, Maharashtra, India", "city": "Nagpur", "state": "Maharashtra", "country": "India", "lat": 21.1458, "lon": 79.0882},
    "Indore": {"display_name": "Indore, Madhya Pradesh, India", "city": "Indore", "state": "Madhya Pradesh", "country": "India", "lat": 22.7196, "lon": 75.8577},
    "Bhopal": {"display_name": "Bhopal, Madhya Pradesh, India", "city": "Bhopal", "state": "Madhya Pradesh", "country": "India", "lat": 23.2599, "lon": 77.4126},
    "Patna": {"display_name": "Patna, Bihar, India", "city": "Patna", "state": "Bihar", "country": "India", "lat": 25.5941, "lon": 85.1376},
    "Vadodara": {"display_name": "Vadodara (Baroda), Gujarat, India", "city": "Vadodara", "state": "Gujarat", "country": "India", "lat": 22.3072, "lon": 73.1812},
    "Surat": {"display_name": "Surat, Gujarat, India", "city": "Surat", "state": "Gujarat", "country": "India", "lat": 21.1702, "lon": 72.8311},
    "Varanasi": {"display_name": "Varanasi, Uttar Pradesh, India", "city": "Varanasi", "state": "Uttar Pradesh", "country": "India", "lat": 25.3176, "lon": 82.9739},
    "Agra": {"display_name": "Agra, Uttar Pradesh, India", "city": "Agra", "state": "Uttar Pradesh", "country": "India", "lat": 27.1767, "lon": 78.0081},
    "Amritsar": {"display_name": "Amritsar, Punjab, India", "city": "Amritsar", "state": "Punjab", "country": "India", "lat": 31.6340, "lon": 74.8723},
    "Ludhiana": {"display_name": "Ludhiana, Punjab, India", "city": "Ludhiana", "state": "Punjab", "country": "India", "lat": 30.9010, "lon": 75.8573},
    "Dehradun": {"display_name": "Dehradun, Uttarakhand, India", "city": "Dehradun", "state": "Uttarakhand", "country": "India", "lat": 30.3165, "lon": 78.0322},
    "Shimla": {"display_name": "Shimla, Himachal Pradesh, India", "city": "Shimla", "state": "Himachal Pradesh", "country": "India", "lat": 31.1048, "lon": 77.1734},
    "Salem": {"display_name": "Salem, Tamil Nadu, India", "city": "Salem", "state": "Tamil Nadu", "country": "India", "lat": 11.6643, "lon": 78.1460},
    "Tiruchirappalli": {"display_name": "Tiruchirappalli (Trichy), Tamil Nadu, India", "city": "Tiruchirappalli", "state": "Tamil Nadu", "country": "India", "lat": 10.7905, "lon": 78.7047},
    "Trichy": {"display_name": "Tiruchirappalli (Trichy), Tamil Nadu, India", "city": "Tiruchirappalli", "state": "Tamil Nadu", "country": "India", "lat": 10.7905, "lon": 78.7047},
    "Tirupati": {"display_name": "Tirupati, Andhra Pradesh, India", "city": "Tirupati", "state": "Andhra Pradesh", "country": "India", "lat": 13.6288, "lon": 79.4192},
    "Mangaluru": {"display_name": "Mangaluru (Mangalore), Karnataka, India", "city": "Mangaluru", "state": "Karnataka", "country": "India", "lat": 12.9141, "lon": 74.8560},
    "Mangalore": {"display_name": "Mangaluru (Mangalore), Karnataka, India", "city": "Mangaluru", "state": "Karnataka", "country": "India", "lat": 12.9141, "lon": 74.8560},
    "Puducherry": {"display_name": "Puducherry (Pondicherry), India", "city": "Puducherry", "state": "Puducherry", "country": "India", "lat": 11.9416, "lon": 79.8083},
    "Pondicherry": {"display_name": "Puducherry (Pondicherry), India", "city": "Puducherry", "state": "Puducherry", "country": "India", "lat": 11.9416, "lon": 79.8083},
    "Goa": {"display_name": "Panaji, Goa, India", "city": "Panaji", "state": "Goa", "country": "India", "lat": 15.4909, "lon": 73.8278},
    "Panaji": {"display_name": "Panaji, Goa, India", "city": "Panaji", "state": "Goa", "country": "India", "lat": 15.4909, "lon": 73.8278},
    "Noida": {"display_name": "Noida, Uttar Pradesh, India", "city": "Noida", "state": "Uttar Pradesh", "country": "India", "lat": 28.5355, "lon": 77.3910},
    "Gurugram": {"display_name": "Gurugram (Gurgaon), Haryana, India", "city": "Gurugram", "state": "Haryana", "country": "India", "lat": 28.4595, "lon": 77.0266},
    "Gurgaon": {"display_name": "Gurugram (Gurgaon), Haryana, India", "city": "Gurugram", "state": "Haryana", "country": "India", "lat": 28.4595, "lon": 77.0266},
}

# Cache for Nominatim queries to avoid repeat network traffic
_NOMINATIM_CACHE = {}


def search_location_suggestions(query: str, limit: int = 5) -> list:
    """
    Search suggestions for location input.
    1. Fast prefix/substring match from local registry (0ms).
    2. If fewer than 2 matches and query >= 3 chars, queries Nominatim with caching.
    """
    q = (query or "").strip().lower()
    if not q or len(q) < 2:
        return []

    results = []
    seen = set()

    # 1. Local registry prefix / substring matching
    for key, data in INDIAN_CITIES_REGISTRY.items():
        if key.lower().startswith(q) or q in key.lower():
            name = data["display_name"]
            if name not in seen:
                seen.add(name)
                results.append({**data, "match_type": "autocomplete"})
                if len(results) >= limit:
                    return results

    # 2. Query Nominatim if needed
    if len(results) < limit and len(q) >= 3:
        nominatim_res = _query_nominatim(q, limit=limit - len(results))
        for item in nominatim_res:
            if item["display_name"] not in seen:
                seen.add(item["display_name"])
                results.append(item)

    return results[:limit]


def suggest_typo_corrections(query: str, limit: int = 3) -> list:
    """
    Suggest closest candidate cities when a user enters a misspelled location name.
    Example: 'Mumabi' -> 'Mumbai', 'Chenai' -> 'Chennai', 'Bangalor' -> 'Bengaluru'.
    """
    q = (query or "").strip()
    if not q or len(q) < 3:
        return []

    # Get close matches from known city names
    known_keys = list(INDIAN_CITIES_REGISTRY.keys())
    matches = difflib.get_close_matches(q.title(), known_keys, n=limit, cutoff=0.55)

    corrections = []
    seen = set()
    for m in matches:
        data = INDIAN_CITIES_REGISTRY[m]
        d_name = data["display_name"]
        if d_name not in seen:
            seen.add(d_name)
            corrections.append({**data, "match_type": "typo_correction"})

    return corrections


def resolve_location(query: str) -> dict:
    """
    Reliably resolve a user query into structured location data:
    {display_name, lat, lon, city, state, country, match_type}
    Returns None if location cannot be resolved.
    """
    q = (query or "").strip()
    if not q:
        return None

    # 1. Exact match in registry (case-insensitive)
    for key, data in INDIAN_CITIES_REGISTRY.items():
        if key.lower() == q.lower():
            return {**data, "match_type": "exact"}

    # 2. Prefix / Contains match in registry
    suggestions = search_location_suggestions(q, limit=1)
    if suggestions:
        return suggestions[0]

    # 3. Fuzzy typo correction
    typos = suggest_typo_corrections(q, limit=1)
    if typos:
        return typos[0]

    # 4. Fallback to direct Nominatim query
    nom = _query_nominatim(q, limit=1)
    if nom:
        return nom[0]

    return None


def _query_nominatim(query: str, limit: int = 3) -> list:
    """Helper to query Nominatim OpenStreetMap with in-memory caching."""
    q_norm = query.strip().lower()
    if q_norm in _NOMINATIM_CACHE:
        return _NOMINATIM_CACHE[q_norm]

    try:
        r = _SESSION.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query if "india" in q_norm else f"{query}, India",
                "format": "json",
                "addressdetails": 1,
                "limit": limit,
            },
            timeout=5,
        )
        data = r.json()
        results = []
        for item in data:
            addr = item.get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or query.title()
            state = addr.get("state", "")
            country = addr.get("country", "India")
            disp = item.get("display_name", "")
            if len(disp.split(",")) > 3:
                # Truncate overly long OpenStreetMap administrative descriptions
                disp = ", ".join([p.strip() for p in disp.split(",")[:3]])

            results.append({
                "display_name": disp,
                "city": city,
                "state": state,
                "country": country,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "match_type": "nominatim",
            })
        _NOMINATIM_CACHE[q_norm] = results
        return results
    except Exception:
        return []
