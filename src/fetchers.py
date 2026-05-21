from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from .config import (
    ESPN_ASSISTS_URL,
    ESPN_SCORING_URL,
    ESPN_SCOREBOARD_URL,
    ESPN_STANDINGS_URL,
    ESPN_TEAMS_URL,
    ESPN_TEAM_ROSTER_URL,
    ESPN_TEAM_SQUAD_URL,
    FOTMOB_STATS_URL,
    FOTMOB_TEAM_API_URL,
    FOTMOB_TEAM_SQUAD_URL,
    LEAGUE_CONFIGS,
    LEAGUE_SCOREBOARD_DATES,
    FOOTBALL_NEWS_FEEDS,
    FRANCE_NEWS_FEEDS,
    REQUEST_HEADERS,
    STATBUNKER_ALL_TIME_ASSISTS_URL,
    STATBUNKER_ALL_TIME_SCORERS_URL,
    CHAMPIONS_LEAGUE_NEWS_FEEDS,
    UCL_ESPN_ASSISTS_URL,
    UCL_ESPN_SCOREBOARD_URL,
    UCL_ESPN_SCORING_URL,
    UCL_ESPN_STANDINGS_URL,
    UCL_ESPN_TEAMS_URL,
    UCL_ESPN_TEAM_ROSTER_URL,
    UCL_ESPN_TEAM_SQUAD_URL,
    UCL_FOTMOB_STATS_URL,
    UEFA_UCL_ALL_TIME_SCORERS_URL,
    WORLD_CUP_NEWS_FEEDS,
)

ROUND_LABELS = {
    "round-of-32": "16es de finale",
    "round-of-16": "8es de finale",
    "quarterfinals": "Quarts de finale",
    "semifinals": "Demi-finales",
    "3rd-place-match": "Match pour la 3e place",
    "final": "Finale",
}

NEWS_KEYWORDS = (
    "équipe de france",
    "equipe de france",
    "les bleus",
    "bleus",
    "deschamps",
)

WORLD_CUP_KEYWORDS = (
    "world cup 2026",
    "2026 world cup",
    "coupe du monde 2026",
    "fifa 2026",
    "world cup squad",
    "final world cup squad",
    "2026 world cup",
    "canada mexico usa",
    "canada-mexico-usa",
    "états-unis",
    "etats-unis",
)

WORLD_CUP_EXCLUDE_KEYWORDS = (
    "women",
    "women's",
    "féminin",
    "féminine",
    "qualifier",
    "qualifiers",
    "qualification",
)

CHAMPIONS_LEAGUE_KEYWORDS = (
    "champions league",
    "ligue des champions",
    "uefa champions",
    "c1",
)

FOOTBALL_NEWS_KEYWORDS = (
    "football", "foot", "soccer", "fifa", "uefa", "coupe du monde", "world cup",
    "ligue des champions", "champions league", "psg", "paris saint-germain", "arsenal",
    "real madrid", "barcelone", "bayern", "france", "bleus", "mercato", "transfert",
    "match", "buteur", "passeur", "entraîneur", "selection", "sélection",
)

FRENCH_NEWS_SOURCE_NAMES = {
    "france info",
    "rmc sport",
    "l'equipe",
    "l’équipe",
    "goal.com",
    "goal france",
    "eurosport",
    "eurosport france",
    "foot mercato",
    "so foot",
    "maxifoot",
    "livefoot",
    "france football",
    "le phoceen",
    "le phocéen",
}

BLOCKED_NEWS_SOURCE_NAMES = {"espn", "bbc", "bbc sport", "google news"}
BLOCKED_NEWS_DOMAINS = ("espn.com", "bbc.", "bbc.co.uk", "news.google.")

FRENCH_TEAM_NAMES = {
    "Senegal": "Sénégal",
    "Ivory Coast": "Côte d'Ivoire",
    "South Korea": "Corée du Sud",
    "United States": "États-Unis",
    "Bosnia-Herzegovina": "Bosnie-Herzégovine",
    "Czechia": "Tchéquie",
    "Curacao": "Curaçao",
    "Türkiye": "Turquie",
}

COUNTRY_FLAG_SLUGS = {
    "Argentina": "arg",
    "Brazil": "bra",
    "England": "eng",
    "France": "fra",
    "Georgia": "geo",
    "Germany": "ger",
    "Hungary": "hun",
    "Morocco": "mar",
    "Netherlands": "ned",
    "Norway": "nor",
    "Poland": "pol",
    "Portugal": "por",
    "Spain": "esp",
    "Ukraine": "ukr",
}

PLAYER_COUNTRIES = {
    "achraf hakimi": "Morocco",
    "anthony gordon": "England",
    "harry kane": "England",
    "julián álvarez": "Argentina",
    "julian alvarez": "Argentina",
    "khvicha kvaratskhelia": "Georgia",
    "kylian mbappé": "France",
    "kylian mbappe": "France",
    "michael olise": "France",
}

UCL_ALL_TIME_COUNTRIES = {
    "cristiano ronaldo": "Portugal",
    "lionel messi": "Argentina",
    "messi": "Argentina",
    "robert lewandowski": "Poland",
    "lewandowski": "Poland",
    "karim benzema": "France",
    "benzema": "France",
    "raúl gonzález": "Spain",
    "raul gonzalez": "Spain",
    "mbappé": "France",
    "kylian mbappé": "France",
    "kylian mbappe": "France",
    "van nistelrooy": "Netherlands",
    "ruud van nistelrooy": "Netherlands",
    "shevchenko": "Ukraine",
    "andriy shevchenko": "Ukraine",
    "haaland": "Norway",
    "erling haaland": "Norway",
    "müller": "Germany",
    "muller": "Germany",
    "thomas müller": "Germany",
    "thomas muller": "Germany",
}

REQUEST_TIMEOUT_SECONDS = 12

FALLBACK_ALL_TIME_SCORERS = [
    {"rank": 1, "name": "Miroslav Klose", "team": "Germany", "country": "Germany", "photo_url": "", "value": 16, "source": "FIFA / StatBunker"},
    {"rank": 2, "name": "Ronaldo", "team": "Brazil", "country": "Brazil", "photo_url": "", "value": 15, "source": "FIFA / StatBunker"},
    {"rank": 3, "name": "Gerd Muller", "team": "Germany", "country": "Germany", "photo_url": "", "value": 14, "source": "FIFA / StatBunker"},
    {"rank": 4, "name": "Lionel Messi", "team": "Argentina", "country": "Argentina", "photo_url": "", "value": 13, "source": "FIFA / StatBunker"},
    {"rank": 5, "name": "Just Fontaine", "team": "France", "country": "France", "photo_url": "", "value": 13, "source": "FIFA / StatBunker"},
    {"rank": 6, "name": "Kylian Mbappe", "team": "France", "country": "France", "photo_url": "", "value": 12, "source": "FIFA / StatBunker"},
    {"rank": 7, "name": "Pele", "team": "Brazil", "country": "Brazil", "photo_url": "", "value": 12, "source": "FIFA / StatBunker"},
    {"rank": 8, "name": "Sandor Kocsis", "team": "Hungary", "country": "Hungary", "photo_url": "", "value": 11, "source": "FIFA / StatBunker"},
    {"rank": 9, "name": "Jurgen Klinsmann", "team": "Germany", "country": "Germany", "photo_url": "", "value": 11, "source": "FIFA / StatBunker"},
    {"rank": 10, "name": "Thomas Muller", "team": "Germany", "country": "Germany", "photo_url": "", "value": 10, "source": "FIFA / StatBunker"},
]

FALLBACK_UCL_ALL_TIME_SCORERS = [
    {"rank": 1, "name": "Cristiano Ronaldo", "team": "Portugal", "country": "Portugal", "photo_url": "", "value": 141, "source": "UEFA"},
    {"rank": 2, "name": "Lionel Messi", "team": "Argentina", "country": "Argentina", "photo_url": "", "value": 129, "source": "UEFA"},
    {"rank": 3, "name": "Robert Lewandowski", "team": "Poland", "country": "Poland", "photo_url": "", "value": 109, "source": "UEFA"},
    {"rank": 4, "name": "Karim Benzema", "team": "France", "country": "France", "photo_url": "", "value": 90, "source": "UEFA"},
    {"rank": 5, "name": "Raúl González", "team": "Spain", "country": "Spain", "photo_url": "", "value": 71, "source": "UEFA"},
    {"rank": 6, "name": "Kylian Mbappé", "team": "France", "country": "France", "photo_url": "", "value": 70, "source": "UEFA"},
    {"rank": 7, "name": "Ruud van Nistelrooy", "team": "Netherlands", "country": "Netherlands", "photo_url": "", "value": 60, "source": "UEFA"},
    {"rank": 8, "name": "Andriy Shevchenko", "team": "Ukraine", "country": "Ukraine", "photo_url": "", "value": 59, "source": "UEFA"},
    {"rank": 9, "name": "Erling Haaland", "team": "Norway", "country": "Norway", "photo_url": "", "value": 57, "source": "UEFA"},
    {"rank": 9, "name": "Thomas Müller", "team": "Germany", "country": "Germany", "photo_url": "", "value": 57, "source": "UEFA"},
]


def fetch_dashboard_data() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: list[str] = []

    standings = _safe_fetch("classements ESPN", fetch_espn_standings, errors)
    scoreboard = _safe_fetch("calendrier ESPN", fetch_espn_scoreboard, errors)
    teams_index = _safe_fetch("équipes ESPN", fetch_espn_teams_index, errors)
    group_matches = build_group_matches(scoreboard, standings)
    knockout = build_knockout(scoreboard)
    today_matches = build_today_matches(scoreboard)
    group_matches_total = _count_group_matches(group_matches)
    knockout_matches_total = _count_knockout_matches(knockout)
    group_matches_remaining = _count_remaining_group_matches(group_matches)
    knockout_matches_remaining = _count_remaining_knockout_matches(knockout)
    competition_stage = calculate_competition_stage(group_matches, knockout)
    france_next_match = calculate_france_next_match(scoreboard)
    teams_details = build_teams_details(standings, group_matches, knockout, today_matches, teams_index)
    teams_details = _safe_fetch(
        "effectifs ESPN",
        lambda: enrich_teams_with_espn_rosters(teams_details),
        errors,
    ) or teams_details
    scorers = _safe_fetch("buteurs ESPN", lambda: fetch_espn_player_table(ESPN_SCORING_URL, 0), errors)
    assists = _safe_fetch("passeurs ESPN", lambda: fetch_espn_player_table(ESPN_ASSISTS_URL, 1), errors)
    world_cup_news = _safe_fetch("actualités Coupe du Monde", fetch_world_cup_news, errors)
    news = _safe_fetch("actualités Équipe de France", fetch_france_news, errors)
    football_news_pool = _safe_fetch("actualités football élargies", fetch_football_news_pool, errors)
    all_time_top_scorers = _safe_fetch("buteurs all-time StatBunker", fetch_all_time_top_scorers, errors)
    all_time_top_assisters: list[dict[str, Any]] = []
    focus_entities = sorted(teams_details.keys())
    focused_team_news = build_focused_news(focus_entities, [*news, *world_cup_news, *football_news_pool])

    if not scorers:
        scorers = _safe_fetch("buteurs FotMob", lambda: fetch_fotmob_player_stats("goals"), errors)
    if not assists:
        assists = _safe_fetch("passeurs FotMob", lambda: fetch_fotmob_player_stats("assists"), errors)

    return {
        "generated_at": generated_at,
        "competition": "Coupe du Monde FIFA 2026",
        "standings": standings,
        "group_matches": group_matches,
        "knockout": knockout,
        "today_matches": today_matches,
        "group_matches_total": group_matches_total,
        "group_matches_remaining": group_matches_remaining,
        "knockout_matches_total": knockout_matches_total,
        "knockout_matches_remaining": knockout_matches_remaining,
        "competition_stage": competition_stage,
        "france_next_match": france_next_match,
        "teams_details": teams_details,
        "top_scorers": scorers,
        "top_assists": assists,
        "all_time_top_scorers": all_time_top_scorers,
        "all_time_top_assisters": all_time_top_assisters,
        "world_cup_news": world_cup_news,
        "france_news": news,
        "general_news": world_cup_news,
        "all_news": _dedupe_news([*world_cup_news, *news, *football_news_pool])[:60],
        "focused_team_news": focused_team_news,
        "news_sources": _news_source_names([*WORLD_CUP_NEWS_FEEDS, *FRANCE_NEWS_FEEDS, *FOOTBALL_NEWS_FEEDS]),
        "sources": [
            {"name": "ESPN - classements", "url": ESPN_STANDINGS_URL},
            {"name": "ESPN - matchs", "url": ESPN_SCOREBOARD_URL},
            {"name": "ESPN - équipes", "url": ESPN_TEAMS_URL},
            {"name": "ESPN - statistiques", "url": ESPN_SCORING_URL},
            {"name": "FotMob - statistiques joueurs", "url": FOTMOB_STATS_URL},
            {"name": "StatBunker - buteurs all-time", "url": STATBUNKER_ALL_TIME_SCORERS_URL},
            {"name": "StatBunker - passeurs all-time", "url": STATBUNKER_ALL_TIME_ASSISTS_URL},
            *[{"name": f"Actu Coupe du Monde - {feed['source']}", "url": feed["url"]} for feed in WORLD_CUP_NEWS_FEEDS],
            *[{"name": f"Actu France - {feed['source']}", "url": feed["url"]} for feed in FRANCE_NEWS_FEEDS],
            *[{"name": f"Actu football - {feed['source']}", "url": feed["url"]} for feed in FOOTBALL_NEWS_FEEDS],
        ],
        "errors": errors,
    }


def fetch_champions_league_data() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: list[str] = []

    standings = _safe_fetch("classement Ligue des Champions ESPN", lambda: fetch_espn_standings_from_url(UCL_ESPN_STANDINGS_URL), errors)
    scoreboard = _safe_fetch("calendrier Ligue des Champions ESPN", lambda: fetch_espn_scoreboard_from_url(UCL_ESPN_SCOREBOARD_URL), errors)
    teams_index = _safe_fetch("clubs Ligue des Champions ESPN", lambda: fetch_espn_teams_index_from_url(UCL_ESPN_TEAMS_URL), errors)
    league_matches = build_champions_league_matches(scoreboard)
    knockout = build_champions_league_knockout(scoreboard)
    today_matches = build_today_matches_from_events(scoreboard)
    psg_next_match = calculate_team_next_match(scoreboard, "Paris Saint-Germain", "PSG")
    teams_details = build_teams_details(standings, league_matches, knockout, today_matches, teams_index)
    teams_details = _safe_fetch(
        "effectifs clubs Ligue des Champions ESPN",
        lambda: enrich_teams_with_espn_rosters(teams_details, UCL_ESPN_TEAM_ROSTER_URL, UCL_ESPN_TEAM_SQUAD_URL),
        errors,
    ) or teams_details
    teams_details = _safe_fetch(
        "effectifs clubs Ligue des Champions FotMob",
        lambda: enrich_teams_with_fotmob_rosters(teams_details, UCL_FOTMOB_STATS_URL),
        errors,
    ) or teams_details
    scorers = _safe_fetch("buteurs Ligue des Champions ESPN", lambda: fetch_espn_player_table(UCL_ESPN_SCORING_URL, 0), errors)
    assists = _safe_fetch("passeurs Ligue des Champions ESPN", lambda: fetch_espn_player_table(UCL_ESPN_ASSISTS_URL, 1), errors)
    news = _safe_fetch("actualités Ligue des Champions", fetch_champions_league_news, errors)
    football_news_pool = _safe_fetch("actualités football élargies", fetch_football_news_pool, errors)
    focused_club_news = build_focused_news(sorted(teams_details.keys()), [*news, *football_news_pool])
    all_time_top_scorers = _safe_fetch(
        "buteurs all-time Ligue des Champions UEFA",
        fetch_champions_league_all_time_top_scorers,
        errors,
    )
    if not scorers:
        scorers = _safe_fetch("buteurs Ligue des Champions FotMob", lambda: fetch_fotmob_player_stats_from_url(UCL_FOTMOB_STATS_URL, "goals"), errors)
    else:
        scorers = _safe_fetch(
            "photos buteurs Ligue des Champions FotMob",
            lambda: enrich_players_with_fotmob_stats(scorers, UCL_FOTMOB_STATS_URL, "goals"),
            errors,
        ) or scorers
    if not assists:
        assists = _safe_fetch("passeurs Ligue des Champions FotMob", lambda: fetch_fotmob_player_stats_from_url(UCL_FOTMOB_STATS_URL, "assists"), errors)
    else:
        assists = _safe_fetch(
            "photos passeurs Ligue des Champions FotMob",
            lambda: enrich_players_with_fotmob_stats(assists, UCL_FOTMOB_STATS_URL, "assists"),
            errors,
        ) or assists
    scorers = enrich_players_with_known_country_flags(scorers)
    assists = enrich_players_with_known_country_flags(assists)

    return {
        "generated_at": generated_at,
        "competition": "Ligue des Champions",
        "standings": standings,
        "group_matches": league_matches,
        "knockout": knockout,
        "today_matches": today_matches,
        "group_matches_total": _count_group_matches(league_matches),
        "group_matches_remaining": _count_remaining_group_matches(league_matches),
        "knockout_matches_total": _count_knockout_matches(knockout),
        "knockout_matches_remaining": _count_remaining_knockout_matches(knockout),
        "competition_stage": "Phase de ligue" if _count_remaining_group_matches(league_matches) else "Phase finale",
        "psg_next_match": psg_next_match,
        "teams_details": teams_details,
        "top_scorers": scorers,
        "top_assists": assists,
        "all_time_top_scorers": all_time_top_scorers,
        "all_time_top_assisters": [],
        "world_cup_news": news,
        "france_news": [],
        "general_news": news,
        "all_news": _dedupe_news([*news, *football_news_pool])[:60],
        "focused_club_news": focused_club_news,
        "news_sources": _news_source_names([*CHAMPIONS_LEAGUE_NEWS_FEEDS, *FOOTBALL_NEWS_FEEDS]),
        "sources": [
            {"name": "ESPN - classement Ligue des Champions", "url": UCL_ESPN_STANDINGS_URL},
            {"name": "ESPN - matchs Ligue des Champions", "url": UCL_ESPN_SCOREBOARD_URL},
            {"name": "ESPN - statistiques Ligue des Champions", "url": UCL_ESPN_SCORING_URL},
            {"name": "FotMob - Ligue des Champions", "url": UCL_FOTMOB_STATS_URL},
            {"name": "UEFA - buteurs all-time Ligue des Champions", "url": UEFA_UCL_ALL_TIME_SCORERS_URL},
            *[{"name": f"Actu Ligue des Champions - {feed['source']}", "url": feed["url"]} for feed in CHAMPIONS_LEAGUE_NEWS_FEEDS],
            *[{"name": f"Actu football - {feed['source']}", "url": feed["url"]} for feed in FOOTBALL_NEWS_FEEDS],
        ],
        "errors": errors,
    }



def fetch_leagues_data() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors: list[str] = []
    leagues: dict[str, Any] = {}
    football_news_pool = _safe_fetch("actualités football championnats", fetch_football_news_pool, errors)

    for key, config in LEAGUE_CONFIGS.items():
        league = fetch_single_league_data(key, config, football_news_pool, errors, generated_at)
        leagues[key] = league

    big5 = []
    for key, league in leagues.items():
        scorer = (league.get("top_scorers") or [])[:1]
        if scorer:
            big5.append({**scorer[0], "league_key": key, "league": league.get("name", "")})

    return {
        "generated_at": generated_at,
        "competition": "Championnats européens",
        "selected_league": "ligue1",
        "leagues": leagues,
        "big5_top_scorers": big5[:5],
        "all_news": football_news_pool[:80],
        "news_sources": _news_source_names(FOOTBALL_NEWS_FEEDS),
        "sources": [
            {"name": f"ESPN - {config['name']}", "url": _league_standings_url(config)}
            for config in LEAGUE_CONFIGS.values()
        ] + [
            {"name": f"Actu football - {feed['source']}", "url": feed["url"]} for feed in FOOTBALL_NEWS_FEEDS
        ],
        "errors": errors,
    }


def fetch_single_league_data(key: str, config: dict[str, Any], football_news_pool: list[dict[str, Any]], errors: list[str], generated_at: str) -> dict[str, Any]:
    name = config["name"]
    standings_url = _league_standings_url(config)
    scoreboard_url = _league_scoreboard_url(config)
    teams_url = _league_teams_url(config)
    scorers_url = _league_stats_url(config)
    assists_url = _league_assists_url(config)
    fotmob_url = _league_fotmob_stats_url(config)

    standings = _safe_fetch(f"classement {name} ESPN", lambda: fetch_espn_standings_from_url(standings_url), errors)
    scoreboard = _safe_fetch(f"calendrier {name} ESPN", lambda: fetch_espn_scoreboard_from_url(scoreboard_url), errors)
    teams_index = _safe_fetch(f"clubs {name} ESPN", lambda: fetch_espn_teams_index_from_url(teams_url), errors)
    matches = build_league_matches(scoreboard)
    today_matches = build_today_matches_from_events(scoreboard)
    teams_details = build_teams_details(standings, matches, [], today_matches, teams_index)
    if not teams_details:
        teams_details = _default_league_teams(key)
    scorers = _safe_fetch(f"buteurs {name} ESPN", lambda: fetch_espn_player_table(scorers_url, 0), errors)
    assists = _safe_fetch(f"passeurs {name} ESPN", lambda: fetch_espn_player_table(assists_url, 1), errors)
    if not scorers:
        scorers = _safe_fetch(f"buteurs {name} FotMob", lambda: fetch_fotmob_player_stats_from_url(fotmob_url, "goals"), errors)
    else:
        scorers = _safe_fetch(f"photos buteurs {name} FotMob", lambda: enrich_players_with_fotmob_stats(scorers, fotmob_url, "goals"), errors) or scorers
    if not assists:
        assists = _safe_fetch(f"passeurs {name} FotMob", lambda: fetch_fotmob_player_stats_from_url(fotmob_url, "assists"), errors)
    else:
        assists = _safe_fetch(f"photos passeurs {name} FotMob", lambda: enrich_players_with_fotmob_stats(assists, fotmob_url, "assists"), errors) or assists
    focused_club_news = build_focused_news(sorted(teams_details.keys()), football_news_pool, limit=12)
    clubs = sorted(teams_details.keys(), key=str.casefold)
    default_focus = _default_league_focus(key, clubs)
    return {
        "key": key,
        "name": name,
        "country": config.get("country", ""),
        "generated_at": generated_at,
        "standings": standings,
        "group_matches": matches,
        "fixtures": matches,
        "today_matches": today_matches,
        "upcoming_matches": _upcoming_matches(matches, 3),
        "top_scorers": enrich_players_with_known_country_flags(scorers),
        "top_assists": enrich_players_with_known_country_flags(assists),
        "focused_club": default_focus,
        "focused_club_next_match": _next_match_from_groups(matches, default_focus),
        "focused_club_news": focused_club_news,
        "clubs": clubs,
        "teams_details": teams_details,
        "sources": [
            {"name": f"ESPN - classement {name}", "url": standings_url},
            {"name": f"ESPN - matchs {name}", "url": scoreboard_url},
            {"name": f"ESPN - statistiques {name}", "url": scorers_url},
            {"name": f"FotMob - {name}", "url": fotmob_url},
        ],
    }


def build_league_matches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = [_parse_event(event, placeholders=True) for event in events]
    matches.sort(key=lambda match: match.get("date", ""))
    return [{"name": "Saison", "matches": matches}]


def _league_standings_url(config: dict[str, Any]) -> str:
    return f"https://www.espn.com/soccer/standings/_/league/{config['espn_code']}"


def _league_scoreboard_url(config: dict[str, Any]) -> str:
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{config['espn_code']}/scoreboard?dates={LEAGUE_SCOREBOARD_DATES}&limit=300"


def _league_teams_url(config: dict[str, Any]) -> str:
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{config['espn_code']}/teams"


def _league_stats_url(config: dict[str, Any]) -> str:
    return f"https://www.espn.com/soccer/stats/_/league/{config['espn_code']}"


def _league_assists_url(config: dict[str, Any]) -> str:
    return f"https://www.espn.com/soccer/stats/_/league/{config['espn_code']}/view/assists"


def _league_fotmob_stats_url(config: dict[str, Any]) -> str:
    return f"https://www.fotmob.com/leagues/{config['fotmob_id']}/stats/{config['fotmob_slug']}/players"


def _default_league_teams(key: str) -> dict[str, dict[str, Any]]:
    defaults = {
        "ligue1": [("Paris Saint-Germain", "160"), ("Marseille", "176"), ("AS Monaco", "174"), ("Lyon", "167")],
        "laliga": [("Real Madrid", "86"), ("Barcelona", "83"), ("Atlético Madrid", "1068"), ("Villarreal", "102")],
        "bundesliga": [("Bayern Munich", "132"), ("Borussia Dortmund", "124"), ("Bayer Leverkusen", "131")],
        "premierleague": [("Manchester City", "382"), ("Arsenal", "359"), ("Liverpool", "364"), ("Chelsea", "363")],
        "seriea": [("Internazionale", "110"), ("Juventus", "111"), ("Napoli", "114"), ("AC Milan", "103")],
    }
    teams: dict[str, dict[str, Any]] = {}
    for name, espn_id in defaults.get(key, []):
        teams[name] = {
            "key": name,
            "name": name,
            "original_name": name,
            "espn_id": espn_id,
            "flag_url": f"https://a.espncdn.com/i/teamlogos/soccer/500/{espn_id}.png",
            "country_code": "",
            "coach": "",
            "formation": "",
            "starters": [],
            "substitutes": [],
            "squad": [],
            "sources": ["Référentiel clubs"],
        }
    return teams


def _default_league_focus(key: str, clubs: list[str]) -> str:
    preferred = {
        "ligue1": ["Paris Saint-Germain", "PSG", "Marseille"],
        "laliga": ["Real Madrid", "Barcelona"],
        "bundesliga": ["Bayern Munich", "Bayern München"],
        "premierleague": ["Manchester City", "Arsenal"],
        "seriea": ["Internazionale", "Juventus", "AC Milan"],
    }.get(key, [])
    normalized = {_normalize_name(club): club for club in clubs}
    for club in preferred:
        found = normalized.get(_normalize_name(club))
        if found:
            return found
    return clubs[0] if clubs else ""


def _upcoming_matches(groups: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    matches = []
    for group in groups:
        for match in group.get("matches", []):
            if match.get("completed"):
                continue
            try:
                date = datetime.fromisoformat(str(match.get("date", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if date >= now:
                matches.append(match)
    return sorted(matches, key=lambda item: item.get("date", ""))[:limit]


def _next_match_from_groups(groups: list[dict[str, Any]], team: str) -> dict[str, Any] | None:
    if not team:
        return None
    for match in _upcoming_matches(groups, 200):
        if team in {match.get("home_team"), match.get("away_team")}:
            return match
    return None

def fetch_espn_standings() -> list[dict[str, Any]]:
    return fetch_espn_standings_from_url(ESPN_STANDINGS_URL)


def fetch_espn_standings_from_url(url: str) -> list[dict[str, Any]]:
    html = _download(url)
    data = _extract_espn_state(html)
    content = data["page"]["content"]["standings"]
    headers = content.get("subheaders", [[], []])[1]
    stat_keys = [item["type"] for item in headers if isinstance(item, dict)]
    groups = content["groups"]["groups"]

    parsed_groups: list[dict[str, Any]] = []
    for group in groups:
        teams = []
        for entry in group.get("standings", []):
            stats = _stats_map(stat_keys, entry.get("stats", []))
            note = entry.get("note") or {}
            team = entry.get("team", {})
            teams.append(
                {
                    "rank": note.get("rank") or stats.get("rank") or len(teams) + 1,
                    "team": team.get("displayName") or team.get("shortDisplayName", ""),
                    "espn_id": str(team.get("id") or ""),
                    "abbr": team.get("abbrev", ""),
                    "country_code": team.get("abbrev", ""),
                    "flag_url": team.get("logo", ""),
                    "played": stats.get("gamesplayed", "0"),
                    "wins": stats.get("wins", "0"),
                    "draws": stats.get("ties", "0"),
                    "losses": stats.get("losses", "0"),
                    "goals_for": stats.get("pointsfor", "0"),
                    "goals_against": stats.get("pointsagainst", "0"),
                    "goal_diff": stats.get("pointdifferential", "0"),
                    "points": stats.get("points", "0"),
                    "status": note.get("description", ""),
                }
            )
        parsed_groups.append({"name": group.get("name", "Groupe"), "teams": teams})

    return parsed_groups


def fetch_espn_scoreboard() -> list[dict[str, Any]]:
    return fetch_espn_scoreboard_from_url(ESPN_SCOREBOARD_URL)


def fetch_espn_scoreboard_from_url(url: str) -> list[dict[str, Any]]:
    data = _download_json(url)
    return data.get("events", [])


def fetch_espn_teams_index() -> dict[str, dict[str, Any]]:
    return fetch_espn_teams_index_from_url(ESPN_TEAMS_URL)


def fetch_espn_teams_index_from_url(url: str) -> dict[str, dict[str, Any]]:
    data = _download_json(url)
    teams: dict[str, dict[str, Any]] = {}
    for item in data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
        team = item.get("team", item)
        name = team.get("displayName") or team.get("shortDisplayName") or team.get("name", "")
        if not name:
            continue
        teams[name] = {
            "espn_id": str(team.get("id") or ""),
            "name": name,
            "flag_url": team.get("logo") or _logo_from_team(team),
            "country_code": team.get("abbreviation") or team.get("abbrev") or "",
        }
    return teams


def build_group_matches(events: list[dict[str, Any]], standings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    group_by_team = {
        team["team"]: group["name"]
        for group in standings
        for team in group.get("teams", [])
        if team.get("team")
    }
    groups = {group["name"]: [] for group in standings}

    for event in events:
        if event.get("season", {}).get("slug") != "group-stage":
            continue
        match = _parse_event(event)
        group_name = group_by_team.get(match["home_team"]) or group_by_team.get(match["away_team"]) or "Groupe à déterminer"
        groups.setdefault(group_name, []).append(match)

    return [{"name": name, "matches": matches} for name, matches in groups.items()]


def build_champions_league_matches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    knockout_slugs = set(ROUND_LABELS) | {
        "knockout-round-playoffs",
        "knockout-round-playoff",
        "playoffs",
        "playoff",
    }
    for event in events:
        slug = str(event.get("season", {}).get("slug") or "").lower()
        name = str(event.get("season", {}).get("name") or "").lower()
        if slug in knockout_slugs or any(word in name for word in ("round of", "quarter", "semi", "final")):
            continue
        matches.append(_parse_event(event, placeholders=True))
    matches.sort(key=lambda match: match.get("date", ""))
    return [{"name": "Phase de ligue", "matches": matches}]


def build_knockout(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rounds = {slug: {"name": label, "matches": []} for slug, label in ROUND_LABELS.items()}
    for event in events:
        slug = event.get("season", {}).get("slug")
        if slug in rounds:
            rounds[slug]["matches"].append(_parse_event(event, placeholders=True))
    return [rounds[slug] for slug in ROUND_LABELS]


def build_champions_league_knockout(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        "knockout-round-playoffs": "Barrages",
        "knockout-round-playoff": "Barrages",
        "playoffs": "Barrages",
        "playoff": "Barrages",
        **ROUND_LABELS,
    }
    rounds = {label: {"name": label, "matches": []} for label in dict.fromkeys(labels.values())}
    for event in events:
        slug = str(event.get("season", {}).get("slug") or "").lower()
        label = labels.get(slug)
        if not label:
            continue
        rounds[label]["matches"].append(_parse_event(event, placeholders=True))
    return list(rounds.values())


def build_today_matches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return build_today_matches_from_events(events)


def build_today_matches_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    matches = []
    for event in events:
        date_value = event.get("date", "")
        try:
            event_date = datetime.fromisoformat(date_value.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if event_date == today:
            matches.append(_parse_event(event, placeholders=True))
    return matches


def calculate_competition_stage(group_matches: list[dict[str, Any]], knockout: list[dict[str, Any]]) -> str:
    if group_matches and _count_remaining_group_matches(group_matches) > 0:
        return "Phase de groupes"
    for round_data in knockout:
        matches = round_data.get("matches", [])
        if matches and any(not match.get("completed") for match in matches):
            return round_data.get("name", "Phase à élimination directe")
    if knockout and _count_knockout_matches(knockout) > 0:
        return "Compétition terminée"
    return "Phase de groupes"


def calculate_france_next_match(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    candidates = []
    for event in events:
        match = _parse_event(event, placeholders=True)
        if match.get("completed"):
            continue
        teams = {match.get("home_team", "").lower(), match.get("away_team", "").lower()}
        if "france" not in teams:
            continue
        try:
            match_date = datetime.fromisoformat(match.get("date", "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if match_date >= now:
            candidates.append((match_date, match))

    if not candidates:
        return None

    _, match = min(candidates, key=lambda item: item[0])
    opponent = match["away_team"] if match.get("home_team") == "France" else match.get("home_team", "À déterminer")
    opponent_side = "away" if match.get("home_team") == "France" else "home"
    return {
        "date": match.get("date", ""),
        "opponent": opponent,
        "opponent_display": FRENCH_TEAM_NAMES.get(opponent, opponent),
        "france_flag_url": match.get("home_flag_url") if match.get("home_team") == "France" else match.get("away_flag_url", ""),
        "opponent_flag_url": match.get(f"{opponent_side}_flag_url", ""),
        "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""),
    }


def calculate_team_next_match(events: list[dict[str, Any]], *team_names: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    needles = {name.lower() for name in team_names if name}
    candidates = []
    for event in events:
        match = _parse_event(event, placeholders=True)
        if match.get("completed"):
            continue
        home = str(match.get("home_team", ""))
        away = str(match.get("away_team", ""))
        if home.lower() not in needles and away.lower() not in needles:
            continue
        try:
            match_date = datetime.fromisoformat(match.get("date", "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if match_date >= now:
            candidates.append((match_date, match))

    if not candidates:
        return None

    _, match = min(candidates, key=lambda item: item[0])
    is_home = str(match.get("home_team", "")).lower() in needles
    return {
        "date": match.get("date", ""),
        "team": match.get("home_team", "") if is_home else match.get("away_team", ""),
        "opponent": match.get("away_team", "") if is_home else match.get("home_team", ""),
        "team_logo_url": match.get("home_flag_url", "") if is_home else match.get("away_flag_url", ""),
        "opponent_logo_url": match.get("away_flag_url", "") if is_home else match.get("home_flag_url", ""),
        "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""),
    }


def build_teams_details(
    standings: list[dict[str, Any]],
    group_matches: list[dict[str, Any]],
    knockout: list[dict[str, Any]],
    today_matches: list[dict[str, Any]],
    teams_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    teams: dict[str, dict[str, Any]] = {}
    teams_index = teams_index or {}

    def register(name: str, flag_url: str = "", country_code: str = "", espn_id: str = "") -> None:
        if not name or name == "À déterminer":
            return
        indexed = teams_index.get(name, {})
        current = teams.setdefault(
            name,
            {
                "key": name,
                "name": FRENCH_TEAM_NAMES.get(name, name),
                "original_name": name,
                "espn_id": "",
                "flag_url": "",
                "country_code": "",
                "coach": "",
                "formation": "",
                "starters": [],
                "substitutes": [],
                "squad": [],
                "sources": [],
            },
        )
        if (espn_id or indexed.get("espn_id")) and not current["espn_id"]:
            current["espn_id"] = str(espn_id or indexed.get("espn_id", ""))
        if indexed.get("flag_url") and not flag_url:
            flag_url = indexed["flag_url"]
        if indexed.get("country_code") and not country_code:
            country_code = indexed["country_code"]
        if flag_url and not current["flag_url"]:
            current["flag_url"] = flag_url
        if country_code and not current["country_code"]:
            current["country_code"] = country_code
        if (flag_url or country_code) and "ESPN" not in current["sources"]:
            current["sources"].append("ESPN")

    for group in standings:
        for team in group.get("teams", []):
            register(team.get("team", ""), team.get("flag_url", ""), team.get("country_code", ""), team.get("espn_id", ""))

    for group in group_matches:
        for match in group.get("matches", []):
            register(match.get("home_team", ""), match.get("home_flag_url", ""), match.get("home_country_code", ""), match.get("home_espn_id", ""))
            register(match.get("away_team", ""), match.get("away_flag_url", ""), match.get("away_country_code", ""), match.get("away_espn_id", ""))

    for round_data in knockout:
        for match in round_data.get("matches", []):
            register(match.get("home_team", ""), match.get("home_flag_url", ""), match.get("home_country_code", ""), match.get("home_espn_id", ""))
            register(match.get("away_team", ""), match.get("away_flag_url", ""), match.get("away_country_code", ""), match.get("away_espn_id", ""))

    for match in today_matches:
        register(match.get("home_team", ""), match.get("home_flag_url", ""), match.get("home_country_code", ""), match.get("home_espn_id", ""))
        register(match.get("away_team", ""), match.get("away_flag_url", ""), match.get("away_country_code", ""), match.get("away_espn_id", ""))

    for name, team in teams_index.items():
        register(name, team.get("flag_url", ""), team.get("country_code", ""), team.get("espn_id", ""))

    return dict(sorted(teams.items()))


def enrich_teams_with_espn_rosters(
    teams_details: dict[str, dict[str, Any]],
    roster_url_template: str = ESPN_TEAM_ROSTER_URL,
    squad_url_template: str = ESPN_TEAM_SQUAD_URL,
) -> dict[str, dict[str, Any]]:
    enriched = {name: dict(details) for name, details in teams_details.items()}
    for name, details in enriched.items():
        team_id = details.get("espn_id")
        if not team_id:
            continue
        try:
            roster = fetch_espn_team_roster(str(team_id), roster_url_template, squad_url_template)
        except Exception:
            continue
        if not roster:
            continue
        details["squad"] = _clean_roster_players(roster.get("squad", []))
        details["coach"] = roster.get("coach", "")
        if "ESPN roster" not in details["sources"]:
            details["sources"].append("ESPN roster")
    return enriched


def enrich_teams_with_fotmob_rosters(
    teams_details: dict[str, dict[str, Any]],
    stats_url: str,
) -> dict[str, dict[str, Any]]:
    team_index = fetch_fotmob_team_index(stats_url)
    enriched = {name: dict(details) for name, details in teams_details.items()}
    for name, details in enriched.items():
        team_id = _lookup_fotmob_team_id(name, team_index)
        if not team_id:
            continue
        details["fotmob_id"] = str(team_id)
        try:
            fotmob_details = fetch_fotmob_team_details(str(team_id), name)
        except Exception:
            continue
        if fotmob_details.get("squad"):
            details["squad"] = _clean_roster_players(fotmob_details["squad"])
        if fotmob_details.get("coach"):
            details["coach"] = fotmob_details["coach"]
        if fotmob_details.get("formation"):
            details["formation"] = fotmob_details["formation"]
        if fotmob_details.get("flag_url") and not details.get("flag_url"):
            details["flag_url"] = fotmob_details["flag_url"]
        if "FotMob" not in details["sources"] and (
            fotmob_details.get("squad") or fotmob_details.get("coach") or fotmob_details.get("formation")
        ):
            details["sources"].append("FotMob")
    return enriched


def fetch_fotmob_team_index(stats_url: str) -> dict[str, str]:
    rows = fetch_fotmob_player_stats_from_url(stats_url, "goals", limit=None) + fetch_fotmob_player_stats_from_url(
        stats_url,
        "assists",
        limit=None,
    )
    teams: dict[str, str] = {}
    for row in rows:
        team = str(row.get("team") or "")
        team_id = str(row.get("team_id") or "")
        if team and team_id:
            teams[_normalize_name(team)] = team_id
    return teams


def _lookup_fotmob_team_id(name: str, team_index: dict[str, str]) -> str:
    normalized = _normalize_name(name)
    if normalized in team_index:
        return team_index[normalized]
    aliases = {
        "psg": "paris saint germain",
        "paris sg": "paris saint germain",
        "bayern munich": "bayern munchen",
        "bayern münchen": "bayern munchen",
        "inter milan": "inter",
    }
    aliased = aliases.get(normalized)
    if aliased and aliased in team_index:
        return team_index[aliased]
    for indexed_name, team_id in team_index.items():
        if normalized in indexed_name or indexed_name in normalized:
            return team_id
    return ""


def fetch_fotmob_team_details(team_id: str, team_name: str) -> dict[str, Any]:
    data: dict[str, Any] | None = None
    try:
        data = _download_json(FOTMOB_TEAM_API_URL.format(team_id=team_id))
    except Exception:
        data = None
    if not data:
        html = _download(FOTMOB_TEAM_SQUAD_URL.format(team_id=team_id, slug=_slugify(team_name)))
        data = _extract_next_data(html)

    squad: list[dict[str, Any]] = []
    _collect_fotmob_squad_players(data, squad)
    unique: dict[str, dict[str, Any]] = {}
    for player in _clean_roster_players(squad):
        name = player.get("name", "")
        if name and name not in unique:
            unique[name] = player
    return {
        "coach": _find_coach_name(data),
        "formation": _find_formation(data),
        "flag_url": _find_team_logo(data),
        "squad": list(unique.values()),
    }


def fetch_espn_team_roster(
    team_id: str,
    roster_url_template: str = ESPN_TEAM_ROSTER_URL,
    squad_url_template: str = ESPN_TEAM_SQUAD_URL,
) -> dict[str, Any]:
    athletes = []
    coach = ""
    try:
        data = _download_json(roster_url_template.format(team_id=team_id))
        for group in data.get("athletes", []):
            for item in group.get("items", []):
                athlete = item.get("athlete", item)
                player = _parse_espn_roster_player(athlete)
                if player.get("name"):
                    athletes.append(player)
        if not athletes:
            for item in data.get("roster", []):
                player = _parse_espn_roster_player(item.get("athlete", item))
                if player.get("name"):
                    athletes.append(player)
        coach = _extract_coach(data)
    except Exception:
        pass
    if not athletes:
        page_roster = fetch_espn_team_squad_page(team_id, squad_url_template)
        athletes = page_roster.get("squad", [])
        coach = coach or page_roster.get("coach", "")
    return {"squad": athletes, "coach": coach}


def fetch_espn_team_squad_page(team_id: str, squad_url_template: str = ESPN_TEAM_SQUAD_URL) -> dict[str, Any]:
    html = _download(squad_url_template.format(team_id=team_id))
    data = _extract_espn_state(html)
    athletes: list[dict[str, Any]] = []
    _collect_roster_players(data, athletes)
    unique: dict[str, dict[str, Any]] = {}
    for player in athletes:
        name = player.get("name", "")
        if name and name not in unique:
            unique[name] = player
    return {"squad": list(unique.values()), "coach": _extract_coach(data)}


def _parse_espn_roster_player(athlete: dict[str, Any]) -> dict[str, Any]:
    position = athlete.get("position") or {}
    headshot = athlete.get("headshot") or {}
    return {
        "name": athlete.get("displayName") or athlete.get("fullName") or athlete.get("shortName") or "",
        "photo_url": headshot.get("href") if isinstance(headshot, dict) else str(headshot or ""),
        "position": position.get("displayName") or position.get("name") or position.get("abbreviation") or "",
        "number": str(athlete.get("jersey") or athlete.get("jerseyNumber") or ""),
    }


def _athlete_country_flag(athlete: dict[str, Any]) -> str:
    for key in ("country", "citizenship", "nationality"):
        value = athlete.get(key)
        if isinstance(value, dict):
            code = value.get("abbreviation") or value.get("code") or value.get("id")
            if code:
                return _flag_from_code(str(code))
        if isinstance(value, str) and value:
            return _country_flag_url(value)
    return ""


def _flag_from_code(code: str) -> str:
    clean = code.lower()
    if len(clean) in (2, 3):
        return f"https://images.fotmob.com/image_resources/logo/teamlogo/{clean}.png"
    return ""


def _collect_roster_players(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        has_name = node.get("displayName") or node.get("fullName") or node.get("shortName")
        has_player_context = any(key in node for key in ("position", "headshot", "jersey", "jerseyNumber"))
        if has_name and has_player_context:
            player = _parse_espn_roster_player(node)
            if player.get("name"):
                out.append(player)
        for value in node.values():
            _collect_roster_players(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_roster_players(value, out)


def _extract_coach(data: dict[str, Any]) -> str:
    for key in ("coach", "headCoach"):
        coach = data.get(key)
        if isinstance(coach, dict):
            return coach.get("displayName") or coach.get("name") or ""
        if isinstance(coach, str):
            return coach
    for item in data.get("coaches", []):
        coach = item.get("coach", item)
        if isinstance(coach, dict):
            name = coach.get("displayName") or coach.get("name")
            if name:
                return name
    return _find_coach_name(data)


def _find_coach_name(node: Any) -> str:
    if isinstance(node, dict):
        for key in ("coach", "headCoach", "manager"):
            value = node.get(key)
            if isinstance(value, dict):
                name = value.get("displayName") or value.get("name") or value.get("fullName")
                if name:
                    return str(name)
            if isinstance(value, str) and value:
                return value
        for value in node.values():
            name = _find_coach_name(value)
            if name:
                return name
    elif isinstance(node, list):
        for value in node:
            name = _find_coach_name(value)
            if name:
                return name
    return ""


def _find_formation(node: Any) -> str:
    if isinstance(node, dict):
        for key in ("formation", "lineup", "lineupFormation"):
            value = node.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9]-[0-9-]+", value):
                return value
            if isinstance(value, dict):
                formation = _find_formation(value)
                if formation:
                    return formation
        for value in node.values():
            formation = _find_formation(value)
            if formation:
                return formation
    elif isinstance(node, list):
        for value in node:
            formation = _find_formation(value)
            if formation:
                return formation
    return ""


def _find_team_logo(node: Any) -> str:
    if isinstance(node, dict):
        logo = node.get("logo") or node.get("imageUrl") or node.get("iconUrl")
        if isinstance(logo, str) and logo.startswith("http"):
            return logo
        for value in node.values():
            found = _find_team_logo(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_team_logo(value)
            if found:
                return found
    return ""


def _collect_fotmob_squad_players(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        name = node.get("name") or node.get("playerName") or node.get("fullName")
        player_id = _fotmob_player_id(node)
        has_player_context = any(
            key in node
            for key in (
                "position",
                "role",
                "shirtNumber",
                "jerseyNumber",
                "number",
                "imageUrl",
                "playerId",
                "id",
            )
        )
        has_roster_position = any(node.get(key) for key in ("position", "role", "positionLabel", "shirtNumber", "jerseyNumber", "number"))
        if name and player_id and has_player_context and has_roster_position:
            out.append(_parse_fotmob_player(node))
        for value in node.values():
            _collect_fotmob_squad_players(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_fotmob_squad_players(value, out)


def _parse_fotmob_player(row: dict[str, Any]) -> dict[str, Any]:
    player_id = _fotmob_player_id(row)
    position = row.get("position") or row.get("role") or row.get("positionLabel") or ""
    if isinstance(position, dict):
        position = position.get("label") or position.get("name") or position.get("shortName") or ""
    return {
        "name": row.get("name") or row.get("playerName") or row.get("fullName") or "",
        "photo_url": row.get("imageUrl", "") or row.get("photoUrl", "") or _fotmob_player_photo(player_id),
        "position": str(position or ""),
        "number": str(row.get("shirtNumber") or row.get("jerseyNumber") or row.get("number") or ""),
        "country_flag_url": _fotmob_country_flag(row),
    }


def _clean_roster_players(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for player in players:
        name = _clean_text(str(player.get("name") or ""))
        if not name:
            continue
        position = _clean_text(str(player.get("position") or ""))
        number = _clean_text(str(player.get("number") or ""))
        # Les pages FotMob contiennent parfois des tableaux de clubs. Ces lignes
        # ont un nom et une image, mais pas de poste ni numéro de joueur.
        if not position and not number:
            continue
        key = _normalize_name(name)
        if key in seen:
            continue
        seen.add(key)
        clean.append({**player, "name": name, "position": position, "number": number})
    return clean


def _fotmob_player_id(row: dict[str, Any]) -> str:
    value = row.get("playerId") or row.get("player_id") or row.get("id")
    return str(value or "")


def _fotmob_player_photo(player_id: str) -> str:
    return f"https://images.fotmob.com/image_resources/playerimages/{player_id}.png" if player_id else ""


def _fotmob_team_logo(team_id: Any) -> str:
    text = str(team_id or "").strip()
    return f"https://images.fotmob.com/image_resources/logo/teamlogo/{text}.png" if text else ""


def _fotmob_country_flag(row: dict[str, Any]) -> str:
    code = row.get("countryCode") or row.get("ccode") or row.get("cCode") or row.get("country")
    if isinstance(code, dict):
        code = code.get("code") or code.get("ccode") or code.get("name")
    if not code:
        return ""
    text = str(code)
    if len(text) in (2, 3):
        return _flag_from_code(text)
    return _country_flag_url(text)


def fetch_espn_player_table(url: str, table_index: int) -> list[dict[str, Any]]:
    html = _download(url)
    data = _extract_espn_state(html)
    statistics = data["page"]["content"]["statistics"]
    rows = statistics.get("tableRows", [])
    if table_index >= len(rows):
        return []

    players = []
    for row in rows[table_index][:5]:
        if len(row) < 5:
            continue
        athlete = row[1] if isinstance(row[1], dict) else {}
        players.append(
            {
                "rank": row[0],
                "name": _cell_name(row[1]),
                "team": _cell_name(row[2]),
                "country_code": _cell_abbr(row[2]),
                "flag_url": "",
                "photo_url": _athlete_headshot(athlete),
                "country_flag_url": _athlete_country_flag(athlete),
                "all_time_rank": "",
                "played": _cell_value(row[3]),
                "value": _cell_value(row[4]),
            }
        )
    return players


def fetch_fotmob_player_stats(metric: str) -> list[dict[str, Any]]:
    return fetch_fotmob_player_stats_from_url(FOTMOB_STATS_URL, metric)


def fetch_fotmob_player_stats_from_url(url: str, metric: str, limit: int | None = 5) -> list[dict[str, Any]]:
    html = _download(url)
    data = _extract_next_data(html)
    candidates = []
    _collect_player_like_rows(data, candidates)
    key_names = {"goals": {"goals", "Goals"}, "assists": {"assists", "Assists"}}[metric]

    rows = []
    for row in candidates:
        value = _first_present(row, key_names)
        name = row.get("name") or row.get("playerName") or row.get("fullName")
        team = row.get("teamName") or row.get("team") or row.get("squadName") or ""
        player_id = _fotmob_player_id(row)
        team_id = row.get("teamId", "") or row.get("teamID", "") or row.get("team_id", "")
        if name and value is not None and str(value).isdigit():
            rows.append(
                {
                    "name": name,
                    "team": team,
                    "team_id": team_id,
                    "team_logo_url": _fotmob_team_logo(team_id),
                    "country_code": row.get("countryCode", "") or row.get("ccode", "") or row.get("cCode", ""),
                    "flag_url": "",
                    "photo_url": row.get("imageUrl", "") or row.get("photoUrl", "") or _fotmob_player_photo(player_id),
                    "country_flag_url": _fotmob_country_flag(row),
                    "all_time_rank": "",
                    "played": row.get("matches", ""),
                    "value": value,
                }
            )

    rows.sort(key=lambda item: _as_int(item["value"]), reverse=True)
    selected = rows if limit is None else rows[:limit]
    return [{**row, "rank": index + 1} for index, row in enumerate(selected)]


def enrich_players_with_fotmob_stats(players: list[dict[str, Any]], stats_url: str, metric: str) -> list[dict[str, Any]]:
    fotmob_players = fetch_fotmob_player_stats_from_url(stats_url, metric)
    by_name = {_normalize_name(player.get("name", "")): player for player in fotmob_players}
    enriched = []
    for player in players:
        match = by_name.get(_normalize_name(player.get("name", "")), {})
        enriched.append(
            {
                **player,
                "photo_url": match.get("photo_url") or player.get("photo_url", ""),
                "country_flag_url": match.get("country_flag_url") or player.get("country_flag_url", ""),
                "country_code": match.get("country_code") or player.get("country_code", ""),
                "team_id": match.get("team_id") or player.get("team_id", ""),
                "team_logo_url": match.get("team_logo_url") or player.get("team_logo_url", ""),
            }
        )
    return enriched


def enrich_players_with_known_country_flags(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for player in players:
        country = player.get("country") or PLAYER_COUNTRIES.get(_normalize_name(player.get("name", "")), "")
        enriched.append(
            {
                **player,
                "country": country,
                "country_flag_url": player.get("country_flag_url") or _country_flag_url(country),
            }
        )
    return enriched


def fetch_france_news() -> list[dict[str, Any]]:
    return _fetch_news(FRANCE_NEWS_FEEDS, NEWS_KEYWORDS, limit=24)


def fetch_world_cup_news() -> list[dict[str, Any]]:
    return _fetch_news(WORLD_CUP_NEWS_FEEDS, WORLD_CUP_KEYWORDS, WORLD_CUP_EXCLUDE_KEYWORDS, limit=24)


def fetch_champions_league_news() -> list[dict[str, Any]]:
    return _fetch_news(CHAMPIONS_LEAGUE_NEWS_FEEDS, CHAMPIONS_LEAGUE_KEYWORDS, limit=24)


def fetch_football_news_pool() -> list[dict[str, Any]]:
    return _fetch_news(FOOTBALL_NEWS_FEEDS, FOOTBALL_NEWS_KEYWORDS, limit=80)


def fetch_all_time_top_scorers() -> list[dict[str, Any]]:
    try:
        html = _download(STATBUNKER_ALL_TIME_SCORERS_URL)
        players = _parse_statbunker_all_time_table(html, "goals")[:10]
        return _with_country_flags(players or FALLBACK_ALL_TIME_SCORERS)
    except Exception:
        return _with_country_flags(FALLBACK_ALL_TIME_SCORERS)


def fetch_all_time_top_assisters() -> list[dict[str, Any]]:
    try:
        html = _download(STATBUNKER_ALL_TIME_ASSISTS_URL)
        return _with_country_flags(_parse_statbunker_all_time_table(html, "assists")[:10])
    except Exception:
        return []


def fetch_champions_league_all_time_top_scorers() -> list[dict[str, Any]]:
    try:
        html = _download(UEFA_UCL_ALL_TIME_SCORERS_URL)
        lines = [_clean_text(line) for line in BeautifulSoup(html, "html.parser").get_text("\n").splitlines()]
        lines = [line for line in lines if line]
        players: list[dict[str, Any]] = []
        names = (
            ("Cristiano Ronaldo", ("cristiano ronaldo",)),
            ("Lionel Messi", ("messi", "lionel messi")),
            ("Robert Lewandowski", ("lewandowski", "robert lewandowski")),
            ("Karim Benzema", ("benzema", "karim benzema")),
            ("Raúl González", ("raúl gonzález", "raul gonzalez")),
            ("Kylian Mbappé", ("mbappé", "mbappe", "kylian mbappé", "kylian mbappe")),
            ("Ruud van Nistelrooy", ("van nistelrooy", "ruud van nistelrooy")),
            ("Andriy Shevchenko", ("shevchenko", "andriy shevchenko")),
            ("Erling Haaland", ("haaland", "erling haaland")),
            ("Thomas Müller", ("müller", "muller", "thomas müller", "thomas muller")),
        )
        used_indexes: set[int] = set()
        for display_name, aliases in names:
            for index, line in enumerate(lines):
                normalized = _normalize_name(line)
                if index in used_indexes or not any(alias in normalized for alias in aliases):
                    continue
                rank_match = re.match(r"^(\d+)\s+", line)
                if not rank_match:
                    continue
                goals = ""
                for next_line in lines[index + 1 : index + 5]:
                    if re.fullmatch(r"\d+", next_line):
                        goals = next_line
                        break
                if not goals:
                    continue
                country = UCL_ALL_TIME_COUNTRIES.get(_normalize_name(display_name), "")
                players.append(
                    {
                        "rank": int(rank_match.group(1)),
                        "name": display_name,
                        "team": country,
                        "country": country,
                        "photo_url": "",
                        "value": int(goals),
                        "source": "UEFA",
                    }
                )
                used_indexes.add(index)
                break
        players.sort(key=lambda player: int(player.get("rank", 999)))
        return _with_country_flags(players[:10] or FALLBACK_UCL_ALL_TIME_SCORERS)
    except Exception:
        return _with_country_flags(FALLBACK_UCL_ALL_TIME_SCORERS)


def _parse_statbunker_all_time_table(html: str, metric: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [_clean_text(cell.get_text(" ", strip=True)).lower() for cell in rows[0].find_all(["th", "td"])]
        player_index = _find_header_index(headers, ("player", "players", "assist name"))
        value_index = _find_header_index(headers, (metric, "goals" if metric == "goals" else "assists"))
        country_index = _find_header_index(headers, ("club", "team", "country", "nationality"))
        if player_index == -1 or value_index == -1:
            continue

        players = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if max(player_index, value_index) >= len(cells):
                continue
            name = _clean_text(cells[player_index].get_text(" ", strip=True))
            value = _clean_text(cells[value_index].get_text(" ", strip=True))
            if not name or not value or not _as_int(value):
                continue
            country = _clean_text(cells[country_index].get_text(" ", strip=True)) if 0 <= country_index < len(cells) else ""
            players.append(
                {
                    "rank": len(players) + 1,
                    "name": name,
                    "team": country,
                    "country": country,
                    "photo_url": "",
                    "flag_url": _country_flag_url(country),
                    "value": _as_int(value),
                    "source": "StatBunker",
                }
            )
            if len(players) == 10:
                return players
        if players:
            return players
    return []


def _find_header_index(headers: list[str], needles: tuple[str, ...]) -> int:
    for index, header in enumerate(headers):
        if any(needle in header for needle in needles):
            return index
    return -1


def _first_image_src(node: Any) -> str:
    image = node.find("img") if hasattr(node, "find") else None
    if not image:
        return ""
    return str(image.get("src") or image.get("data-src") or "")


def _with_country_flags(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for player in players:
        country = str(player.get("country") or player.get("team") or "")
        enriched.append(
            {
                **player,
                "photo_url": "",
                "flag_url": player.get("flag_url") or _country_flag_url(country),
                "country_code": player.get("country_code") or COUNTRY_FLAG_SLUGS.get(country, ""),
            }
        )
    return enriched


def _country_flag_url(country: str) -> str:
    slug = COUNTRY_FLAG_SLUGS.get(country)
    return f"https://a.espncdn.com/i/teamlogos/countries/500/{slug}.png" if slug else ""


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _fetch_news(
    feeds: list[dict[str, Any]],
    keywords: tuple[str, ...],
    exclude_keywords: tuple[str, ...] = (),
    limit: int = 6,
) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()

    for feed in feeds:
        try:
            xml = _download(feed["url"])
            root = ElementTree.fromstring(xml)
        except Exception:
            continue
        for item in root.findall("./channel/item"):
            title = _xml_text(item, "title")
            summary = _strip_html(_xml_text(item, "description"))
            link = _xml_text(item, "link")
            published = _parse_rss_date(_xml_text(item, "pubDate"))
            haystack = _normalize_news_text(f"{title} {summary} {link}")
            if any(_normalize_news_text(keyword) in haystack for keyword in exclude_keywords):
                continue
            if not feed.get("trusted_section") and not any(_normalize_news_text(keyword) in haystack for keyword in keywords):
                continue
            source = str(feed.get("source") or _article_source(item, feed))
            if not _is_allowed_french_news_source(source, link):
                continue
            key = _news_key(title, link)
            if not title or not link or key in seen:
                continue
            seen.add(key)
            articles.append(
                {
                    "title": title,
                    "source": source,
                    "date": published,
                    "summary": _shorten(summary, 210),
                    "url": link,
                }
            )

    articles = _dedupe_news(articles)
    articles.sort(key=lambda item: item.get("date", ""), reverse=True)
    return articles[:limit]


def build_focused_news(entities: list[str], articles: list[dict[str, Any]], limit: int = 12) -> dict[str, list[dict[str, Any]]]:
    focused: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        aliases = _focus_aliases(entity)
        matches = [article for article in articles if _article_matches_aliases(article, aliases)]
        if matches:
            focused[entity] = _dedupe_news(matches)[:limit]
    return focused


def _article_matches_aliases(article: dict[str, Any], aliases: set[str]) -> bool:
    haystack = _normalize_news_text(f"{article.get('title', '')} {article.get('summary', '')} {article.get('url', '')}")
    return any(alias and alias in haystack for alias in aliases)


def _focus_aliases(entity: str) -> set[str]:
    normalized = _normalize_news_text(entity)
    aliases = {normalized}
    mapping = {
        "paris saint germain": {"psg", "paris sg", "paris saint germain"},
        "france": {"france", "equipe de france", "bleus", "deschamps"},
        "senegal": {"senegal", "sénégal", "lions de la teranga"},
        "brazil": {"brazil", "bresil", "brésil", "seleçao", "selecao"},
        "argentina": {"argentina", "argentine", "albiceleste"},
        "real madrid": {"real madrid", "real"},
        "arsenal": {"arsenal", "gunners"},
        "barcelona": {"barcelona", "barcelone", "barça", "barca"},
        "bayern munich": {"bayern", "bayern munich", "bayern munchen"},
    }
    aliases.update(_normalize_news_text(alias) for alias in mapping.get(normalized, set()))
    return {alias for alias in aliases if alias}


def _dedupe_news(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for article in articles:
        key = _news_key(str(article.get("title", "")), str(article.get("url", "")))
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(article)
    clean.sort(key=lambda item: item.get("date", ""), reverse=True)
    return clean


def _news_key(title: str, link: str) -> str:
    title_key = _normalize_news_text(title)[:90]
    return title_key or link.strip().lower()


def _article_source(item: ElementTree.Element, feed: dict[str, Any]) -> str:
    source = _xml_text(item, "source")
    return source or feed["source"]


def _is_allowed_french_news_source(source: str, link: str) -> bool:
    normalized_source = _normalize_news_text(source)
    normalized_source = normalized_source.replace(" ", " ").strip()
    link_lower = str(link or "").lower()
    if normalized_source in BLOCKED_NEWS_SOURCE_NAMES or any(domain in link_lower for domain in BLOCKED_NEWS_DOMAINS):
        return False
    allowed = {_normalize_news_text(name) for name in FRENCH_NEWS_SOURCE_NAMES}
    return normalized_source in allowed or any(_normalize_news_text(name) in normalized_source for name in FRENCH_NEWS_SOURCE_NAMES)


def _normalize_news_text(value: str) -> str:
    replacements = str.maketrans({"é":"e", "è":"e", "ê":"e", "ë":"e", "à":"a", "â":"a", "ä":"a", "î":"i", "ï":"i", "ô":"o", "ö":"o", "ù":"u", "û":"u", "ü":"u", "ç":"c"})
    text = str(value or "").casefold().translate(replacements)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _news_source_names(feeds: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for feed in feeds:
        source = str(feed.get("source", "")).strip()
        if source and source not in seen:
            seen.add(source)
            names.append(source)
    return names


def _safe_fetch(label: str, fetcher, errors: list[str]):
    print(f"Récupération : {label}...", flush=True)
    try:
        result = fetcher()
        print(f"OK : {label}", flush=True)
        return result
    except Exception as exc:  # noqa: BLE001 - le dashboard doit rester générable.
        errors.append(f"{label}: {type(exc).__name__}")
        print(f"Source indisponible : {label} ({type(exc).__name__})", flush=True)
        return []


def _download(url: str) -> str:
    response = None
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200 and response.text.strip():
            return response.text
    except requests.RequestException:
        pass

    # ESPN renvoie parfois une réponse 202 vide aux clients Python, même avec
    # un User-Agent navigateur. curl récupère la même page publique correctement.
    curl = subprocess.run(
        [
            "curl",
            "-L",
            "-s",
            "--max-time",
            str(REQUEST_TIMEOUT_SECONDS),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if curl.returncode == 0 and curl.stdout.strip():
        return curl.stdout

    if response is not None:
        response.raise_for_status()
    raise ValueError(f"réponse vide pour {url}")


def _download_json(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200 and response.text.strip():
            return response.json()
    except requests.RequestException:
        pass
    return json.loads(_download(url))


def _extract_espn_state(html: str) -> dict[str, Any]:
    marker = "window['__espnfitt__']="
    start = html.find(marker)
    if start == -1:
        raise ValueError("état JSON ESPN introuvable")
    start += len(marker)
    end = html.find(";</script>", start)
    if end == -1:
        raise ValueError("fin de l'état JSON ESPN introuvable")
    return json.loads(html[start:end])


def _extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not match:
        raise ValueError("état JSON FotMob introuvable")
    return json.loads(match.group(1))


def _stats_map(keys: list[str], values: list[Any]) -> dict[str, Any]:
    return {key: values[index] for index, key in enumerate(keys) if index < len(values)}


def _cell_name(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("name") or cell.get("displayName") or "")
    return str(cell)


def _cell_value(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("value", ""))
    return str(cell)


def _cell_abbr(cell: Any) -> str:
    if isinstance(cell, dict):
        return str(cell.get("abbrev") or cell.get("shortDisplayName") or "")
    return ""


def _athlete_headshot(athlete: dict[str, Any]) -> str:
    uid = athlete.get("uid", "")
    athlete_id = athlete.get("id", "")
    if not athlete_id and "~a:" in uid:
        athlete_id = uid.rsplit("~a:", 1)[-1]
    if athlete_id:
        return f"https://a.espncdn.com/i/headshots/soccer/players/full/{athlete_id}.png"
    return ""


def _parse_event(event: dict[str, Any], placeholders: bool = False) -> dict[str, Any]:
    competition = (event.get("competitions") or [{}])[0]
    competitors = competition.get("competitors", [])
    home = _competitor_by_side(competitors, "home")
    away = _competitor_by_side(competitors, "away")
    status = competition.get("status", {}).get("type", {})
    venue = competition.get("venue", {}) or {}

    home_name = _team_name(home)
    away_name = _team_name(away)
    if placeholders:
        home_name = _known_or_tbd(home_name)
        away_name = _known_or_tbd(away_name)

    return {
        "id": event.get("id", ""),
        "date": event.get("date") or competition.get("date", ""),
        "home_team": home_name,
        "away_team": away_name,
        "home_flag_url": _team_logo(home),
        "away_flag_url": _team_logo(away),
        "home_espn_id": _team_id(home),
        "away_espn_id": _team_id(away),
        "home_country_code": _team_code(home),
        "away_country_code": _team_code(away),
        "home_score": _score(home, status),
        "away_score": _score(away, status),
        "status": _status_label(status),
        "status_state": status.get("state", ""),
        "completed": bool(status.get("completed")),
        "venue": venue.get("fullName", ""),
        "city": (venue.get("address") or {}).get("city", ""),
    }


def _competitor_by_side(competitors: list[dict[str, Any]], side: str) -> dict[str, Any]:
    for competitor in competitors:
        if competitor.get("homeAway") == side:
            return competitor
    return {}


def _team_name(competitor: dict[str, Any]) -> str:
    team = competitor.get("team") or {}
    return team.get("displayName") or team.get("shortDisplayName") or "À déterminer"


def _team_logo(competitor: dict[str, Any]) -> str:
    team = competitor.get("team") or {}
    return _logo_from_team(team)


def _logo_from_team(team: dict[str, Any]) -> str:
    logo = team.get("logo")
    if logo:
        return str(logo)
    logos = team.get("logos") or []
    if logos and isinstance(logos[0], dict):
        return str(logos[0].get("href", ""))
    return ""


def _team_id(competitor: dict[str, Any]) -> str:
    team = competitor.get("team") or {}
    return str(team.get("id") or "")


def _team_code(competitor: dict[str, Any]) -> str:
    team = competitor.get("team") or {}
    return str(team.get("abbreviation") or team.get("abbrev") or "")


def _score(competitor: dict[str, Any], status: dict[str, Any]) -> str:
    if status.get("state") == "pre" and not status.get("completed"):
        return ""
    score = competitor.get("score")
    return "" if score is None else str(score)


def _status_label(status: dict[str, Any]) -> str:
    state = status.get("state")
    if status.get("completed"):
        return "Terminé"
    if state == "in":
        return "LIVE"
    return "À venir"


def _known_or_tbd(name: str) -> str:
    lowered = name.lower()
    if any(
        word in lowered
        for word in ("winner", "loser", "tbd", "round of", "quarterfinal", "semifinal", " place", "group ")
    ):
        return "À déterminer"
    return name


def _xml_text(item: ElementTree.Element, tag: str) -> str:
    child = item.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss_date(value: str) -> str:
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0] + "…"


def _collect_player_like_rows(node: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if any(key in node for key in ("playerName", "fullName", "name")) and any(
            key.lower() in {"goals", "assists"} for key in node
        ):
            out.append(node)
        for value in node.values():
            _collect_player_like_rows(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_player_like_rows(value, out)


def _first_present(row: dict[str, Any], keys: set[str]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "münchen": "munchen",
        "é": "e",
        "è": "e",
        "ê": "e",
        "à": "a",
        "ã": "a",
        "ç": "c",
        "í": "i",
        "ï": "i",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    return text


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normalize_name(value)).strip("-") or "team"


def _count_group_matches(groups: list[dict[str, Any]]) -> int:
    return sum(len(group.get("matches", [])) for group in groups)


def _count_remaining_group_matches(groups: list[dict[str, Any]]) -> int:
    return sum(1 for group in groups for match in group.get("matches", []) if not match.get("completed"))


def _count_knockout_matches(rounds: list[dict[str, Any]]) -> int:
    return sum(len(round_data.get("matches", [])) for round_data in rounds)


def _count_remaining_knockout_matches(rounds: list[dict[str, Any]]) -> int:
    return sum(1 for round_data in rounds for match in round_data.get("matches", []) if not match.get("completed"))
