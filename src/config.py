from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
OUTPUT_HTML = BASE_DIR / "index.html"
CACHE_FILE = DATA_DIR / "worldcup_dashboard.json"
CHAMPIONS_LEAGUE_CACHE_FILE = DATA_DIR / "champions_league_dashboard.json"
LEAGUES_CACHE_FILE = DATA_DIR / "leagues_dashboard.json"

ESPN_STANDINGS_URL = "https://www.espn.com/soccer/standings/_/league/fifa.world/fifa-world"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719&limit=200"
ESPN_SCORING_URL = "https://www.espn.com/soccer/stats/_/league/FIFA.WORLD/season/2026"
ESPN_ASSISTS_URL = "https://www.espn.com/soccer/stats/_/league/FIFA.WORLD/season/2026/view/assists"
ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams"
ESPN_TEAM_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/teams/{team_id}/roster"
ESPN_TEAM_SQUAD_URL = "https://www.espn.com/soccer/team/squad/_/id/{team_id}"
FOTMOB_STATS_URL = "https://www.fotmob.com/leagues/77/stats/World-Cup/players"
STATBUNKER_ALL_TIME_SCORERS_URL = "https://www.statbunker.com/alltimestats/AllTimeLeadingScorers?comp_code=WC"
STATBUNKER_ALL_TIME_ASSISTS_URL = "https://www.statbunker.com/alltimestats/AllTimeCompetitionMostAssists?comp_code=WC"

UCL_ESPN_STANDINGS_URL = "https://www.espn.com/soccer/standings/_/league/uefa.champions"
UCL_ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=20250701-20260630&limit=300"
UCL_ESPN_SCORING_URL = "https://www.espn.com/soccer/stats/_/league/UEFA.CHAMPIONS"
UCL_ESPN_ASSISTS_URL = "https://www.espn.com/soccer/stats/_/league/UEFA.CHAMPIONS/view/assists"
UCL_ESPN_TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/teams"
UCL_ESPN_TEAM_ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/teams/{team_id}/roster"
UCL_ESPN_TEAM_SQUAD_URL = "https://www.espn.com/soccer/team/squad/_/id/{team_id}"
UCL_FOTMOB_STATS_URL = "https://www.fotmob.com/leagues/42/stats/Champions-League/players"
UEFA_UCL_ALL_TIME_SCORERS_URL = "https://www.uefa.com/uefachampionsleague/history/rankings/players/goals_scored/"
FOTMOB_TEAM_API_URL = "https://www.fotmob.com/api/teams?id={team_id}"
FOTMOB_TEAM_SQUAD_URL = "https://www.fotmob.com/teams/{team_id}/squad/{slug}"

LEAGUE_CONFIGS = {
    "ligue1": {
        "name": "Ligue 1",
        "country": "France",
        "espn_code": "fra.1",
        "fotmob_id": "53",
        "fotmob_slug": "Ligue-1",
    },
    "laliga": {
        "name": "Liga",
        "country": "Espagne",
        "espn_code": "esp.1",
        "fotmob_id": "87",
        "fotmob_slug": "LaLiga",
    },
    "bundesliga": {
        "name": "Bundesliga",
        "country": "Allemagne",
        "espn_code": "ger.1",
        "fotmob_id": "54",
        "fotmob_slug": "Bundesliga",
    },
    "premierleague": {
        "name": "Premier League",
        "country": "Angleterre",
        "espn_code": "eng.1",
        "fotmob_id": "47",
        "fotmob_slug": "Premier-League",
    },
    "seriea": {
        "name": "Serie A",
        "country": "Italie",
        "espn_code": "ita.1",
        "fotmob_id": "55",
        "fotmob_slug": "Serie-A",
    },
}

LEAGUE_SCOREBOARD_DATES = "20250801-20260630"

FRANCE_NEWS_FEEDS = [
    {
        "source": "France Info",
        "url": "https://www.francetvinfo.fr/sports/foot/equipe-de-france.rss",
        "trusted_section": True,
    },
    {
        "source": "RMC Sport",
        "url": "https://rmcsport.bfmtv.com/rss/football/",
        "trusted_section": False,
    },
]

WORLD_CUP_NEWS_FEEDS = [
    {
        "source": "France Info",
        "url": "https://www.francetvinfo.fr/sports/foot/coupe-du-monde.rss",
        "trusted_section": True,
    },
    {
        "source": "RMC Sport",
        "url": "https://rmcsport.bfmtv.com/rss/football/",
        "trusted_section": False,
    },
]

CHAMPIONS_LEAGUE_NEWS_FEEDS = [
    {
        "source": "RMC Sport",
        "url": "https://rmcsport.bfmtv.com/rss/football/",
        "trusted_section": False,
    },
]


EXTRA_FOOTBALL_NEWS_FEEDS = [
    {"source": "L'Équipe", "url": "https://www.lequipe.fr/rss/actu_rss_Football.xml", "trusted_section": False},
    {"source": "Goal.com", "url": "https://www.goal.com/feeds/fr/news?fmt=rss", "trusted_section": False},
    {"source": "Eurosport", "url": "https://www.eurosport.fr/rss.xml", "trusted_section": False},
    {"source": "Foot Mercato", "url": "https://www.footmercato.net/rss.xml", "trusted_section": False},
    {"source": "SO FOOT", "url": "https://www.sofoot.com/rss", "trusted_section": False},
    {"source": "Maxifoot", "url": "https://www.maxifoot.fr/rss.xml", "trusted_section": False},
    {"source": "LiveFoot", "url": "https://www.livefoot.fr/rss.xml", "trusted_section": False},
    {"source": "France Football", "url": "https://www.francefootball.fr/rss/actu_rss.xml", "trusted_section": False},
    {"source": "Le Phocéen", "url": "https://www.lephoceen.fr/rss", "trusted_section": False},
]


# Flux élargis utilisés pour enrichir les actualités et filtrer par équipe suivie.
FOOTBALL_NEWS_FEEDS = [
    *FRANCE_NEWS_FEEDS,
    *WORLD_CUP_NEWS_FEEDS,
    *CHAMPIONS_LEAGUE_NEWS_FEEDS,
    *EXTRA_FOOTBALL_NEWS_FEEDS,
]

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.6",
}
