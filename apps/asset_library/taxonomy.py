from __future__ import annotations

# Initial production taxonomy for a Vietnamese-first soccer media system.
# IDs are stable configuration identifiers, not display names.

MARKETS = [
    {"market_code": "VN", "name": "Vietnam", "language_code": "vi", "priority": 10},
]

CATEGORIES = [
    {"category_code": "SOCCER", "market_code": "VN", "name": "Soccer", "parent_category_code": None, "priority": 10},
    {"category_code": "SOCCER_EUROPE", "market_code": "VN", "name": "European Football", "parent_category_code": "SOCCER", "priority": 20},
    {"category_code": "SOCCER_INTERNATIONAL", "market_code": "VN", "name": "International Football", "parent_category_code": "SOCCER", "priority": 20},
    {"category_code": "SOCCER_VIETNAM", "market_code": "VN", "name": "Vietnamese Football", "parent_category_code": "SOCCER", "priority": 5},
]

# tier: 1 = global/most important, 2 = major continental/international, 3 = major domestic/other priority.
# priority is an internal retrieval/coverage priority, not a quality ranking.
COMPETITIONS = [
    {"code": "FIFA_WORLD_CUP", "category": "SOCCER_INTERNATIONAL", "name": "FIFA World Cup", "scope": "global", "region": "global", "tier": 1, "priority": 10},
    {"code": "FIFA_CLUB_WC", "category": "SOCCER_INTERNATIONAL", "name": "FIFA Club World Cup", "scope": "global", "region": "global", "tier": 1, "priority": 20},
    {"code": "UEFA_EURO", "category": "SOCCER_INTERNATIONAL", "name": "UEFA European Championship", "scope": "continental", "region": "Europe", "tier": 1, "priority": 30},
    {"code": "COPA_AMERICA", "category": "SOCCER_INTERNATIONAL", "name": "Copa América", "scope": "continental", "region": "South America", "tier": 1, "priority": 40},
    {"code": "AFC_ASIAN_CUP", "category": "SOCCER_INTERNATIONAL", "name": "AFC Asian Cup", "scope": "continental", "region": "Asia", "tier": 1, "priority": 50},
    {"code": "AFCON", "category": "SOCCER_INTERNATIONAL", "name": "Africa Cup of Nations", "scope": "continental", "region": "Africa", "tier": 2, "priority": 60},
    {"code": "CONCACAF_GOLD_CUP", "category": "SOCCER_INTERNATIONAL", "name": "CONCACAF Gold Cup", "scope": "continental", "region": "North America", "tier": 2, "priority": 70},
    {"code": "OFC_NATIONS_CUP", "category": "SOCCER_INTERNATIONAL", "name": "OFC Nations Cup", "scope": "continental", "region": "Oceania", "tier": 3, "priority": 80},
    {"code": "UEFA_NATIONS_LEAGUE", "category": "SOCCER_INTERNATIONAL", "name": "UEFA Nations League", "scope": "continental", "region": "Europe", "tier": 2, "priority": 90},
    {"code": "UEFA_CHAMPIONS_LEAGUE", "category": "SOCCER_EUROPE", "name": "UEFA Champions League", "scope": "continental", "region": "Europe", "tier": 1, "priority": 10},
    {"code": "UEFA_EUROPA_LEAGUE", "category": "SOCCER_EUROPE", "name": "UEFA Europa League", "scope": "continental", "region": "Europe", "tier": 2, "priority": 20},
    {"code": "UEFA_CONFERENCE_LEAGUE", "category": "SOCCER_EUROPE", "name": "UEFA Conference League", "scope": "continental", "region": "Europe", "tier": 3, "priority": 30},
    {"code": "PREMIER_LEAGUE", "category": "SOCCER_EUROPE", "name": "Premier League", "scope": "domestic", "region": "England", "tier": 1, "priority": 10},
    {"code": "LA_LIGA", "category": "SOCCER_EUROPE", "name": "La Liga", "scope": "domestic", "region": "Spain", "tier": 1, "priority": 20},
    {"code": "SERIE_A", "category": "SOCCER_EUROPE", "name": "Serie A", "scope": "domestic", "region": "Italy", "tier": 1, "priority": 30},
    {"code": "BUNDESLIGA", "category": "SOCCER_EUROPE", "name": "Bundesliga", "scope": "domestic", "region": "Germany", "tier": 1, "priority": 40},
    {"code": "LIGUE_1", "category": "SOCCER_EUROPE", "name": "Ligue 1", "scope": "domestic", "region": "France", "tier": 1, "priority": 50},
    {"code": "UEFA_WOMENS_EURO", "category": "SOCCER_INTERNATIONAL", "name": "UEFA Women's Championship", "scope": "continental", "region": "Europe", "tier": 2, "priority": 100},
    {"code": "VIETNAM_NATIONAL_TEAM", "category": "SOCCER_VIETNAM", "name": "Vietnam Men's National Team", "scope": "national", "region": "Vietnam", "tier": 1, "priority": 10},
    {"code": "VIETNAM_U23", "category": "SOCCER_VIETNAM", "name": "Vietnam U23 / Youth National Teams", "scope": "national", "region": "Vietnam", "tier": 1, "priority": 20},
    {"code": "V_LEAGUE_1", "category": "SOCCER_VIETNAM", "name": "V.League 1", "scope": "domestic", "region": "Vietnam", "tier": 1, "priority": 30},
    {"code": "V_LEAGUE_2", "category": "SOCCER_VIETNAM", "name": "V.League 2", "scope": "domestic", "region": "Vietnam", "tier": 2, "priority": 60},
    {"code": "VIETNAM_NATIONAL_CUP", "category": "SOCCER_VIETNAM", "name": "Vietnam National Cup", "scope": "domestic", "region": "Vietnam", "tier": 2, "priority": 50},
    {"code": "ASEAN_CHAMPIONSHIP", "category": "SOCCER_VIETNAM", "name": "ASEAN Championship / AFF Championship", "scope": "regional", "region": "Southeast Asia", "tier": 1, "priority": 40},
    {"code": "SEA_GAMES_FOOTBALL", "category": "SOCCER_VIETNAM", "name": "SEA Games Football", "scope": "regional", "region": "Southeast Asia", "tier": 2, "priority": 45},
]

PURPOSES = [
    "establishing_visual",
    "player_focus",
    "team_identity",
    "competition_identity",
    "match_context",
    "tactical_context",
    "data_visual",
    "broll",
    "thumbnail",
    "transition",
    "background",
    "map_or_location",
    "quote_or_statement",
]

SUBJECT_TYPES = [
    "player",
    "team",
    "national_team",
    "competition",
    "stadium",
    "manager",
    "official",
    "match",
    "tactical_diagram",
    "generic_soccer",
]
