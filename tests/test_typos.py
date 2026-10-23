from utils.location_service import suggest_typo_corrections, resolve_location

tests = ['banlgore', 'Bangalor', 'Chenai', 'Mumabi', 'Hydrabad', 'Dlehi', 'Coimbatorr', 'bengaluru']
for t in tests:
    r = suggest_typo_corrections(t, limit=1)
    c = resolve_location(t)
    typo_city = r[0]['city'] if r else 'NONE'
    resolve_city = c['city'] if c else 'NONE'
    resolve_type = c.get('match_type') if c else '-'
    print(f"{t:20} -> typo: {typo_city} | resolve: {resolve_city} ({resolve_type})")
