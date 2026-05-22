from __future__ import annotations

import json
from typing import Any

from src.config import CACHE_FILE, CHAMPIONS_LEAGUE_CACHE_FILE, DATA_DIR, LEAGUES_CACHE_FILE, MERCATO_LIVE_CACHE_FILE, OUTPUT_HTML
from src.fetchers import enrich_players_with_known_country_flags, fetch_champions_league_data, fetch_dashboard_data, fetch_leagues_data, fetch_mercato_live
from src.render import render_html


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    previous_worldcup = _read_cache(CACHE_FILE)
    previous_champions = _read_cache(CHAMPIONS_LEAGUE_CACHE_FILE)
    previous_leagues = _read_cache(LEAGUES_CACHE_FILE)
    worldcup_data = _preserve_news_cache(_merge_refresh(previous_worldcup, fetch_dashboard_data()), previous_worldcup)
    champions_league_data = _preserve_news_cache(_merge_refresh(previous_champions, fetch_champions_league_data()), previous_champions)
    leagues_data = _preserve_leagues_news_cache(_merge_leagues_refresh(previous_leagues, fetch_leagues_data()), previous_leagues)
    previous_mercato = _read_cache(MERCATO_LIVE_CACHE_FILE) or {}
    mercato_items = fetch_mercato_live()
    mercato_data = {"items": mercato_items or previous_mercato.get("items", []), "source": "Mercato Live", "url": "https://www.mercatolive.fr/"}
    _filter_news_sources(worldcup_data, {"rmc sport", "l equipe", "l'equipe", "l’équipe"})
    _filter_news_sources(champions_league_data, {"rmc sport", "l equipe", "l'equipe", "l’équipe"})
    _filter_leagues_news_sources(leagues_data, {"rmc sport", "l equipe", "l'equipe", "l’équipe"})
    for dataset in (worldcup_data, champions_league_data):
        _sanitize_dataset(dataset)
        dataset["top_scorers"] = enrich_players_with_known_country_flags(dataset.get("top_scorers", []))
        dataset["top_assists"] = enrich_players_with_known_country_flags(dataset.get("top_assists", []))
        dataset["all_time_top_assisters"] = []
        dataset["players_index"] = _build_players_index(dataset)

    CACHE_FILE.write_text(json.dumps(worldcup_data, ensure_ascii=False, indent=2), encoding="utf-8")
    CHAMPIONS_LEAGUE_CACHE_FILE.write_text(
        json.dumps(champions_league_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LEAGUES_CACHE_FILE.write_text(json.dumps(leagues_data, ensure_ascii=False, indent=2), encoding="utf-8")
    MERCATO_LIVE_CACHE_FILE.write_text(json.dumps(mercato_data, ensure_ascii=False, indent=2), encoding="utf-8")
    render_html(
        {
            "mercato_live": mercato_data,
            "worldcup": worldcup_data,
            "champions_league": champions_league_data,
            "leagues": leagues_data,
        },
        OUTPUT_HTML,
    )
    print(f"Dashboard généré : {OUTPUT_HTML}")


def _preserve_news_cache(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return current
    for section in ("world_cup_news", "france_news", "general_news", "all_news"):
        if not current.get(section) and previous.get(section):
            current[section] = previous[section]
    for section in ("focused_team_news", "focused_club_news"):
        if not current.get(section) and previous.get(section):
            current[section] = previous[section]
    return current


def _preserve_leagues_news_cache(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return current
    if not current.get("all_news") and previous.get("all_news"):
        current["all_news"] = previous["all_news"]
    current_leagues = current.get("leagues") or {}
    previous_leagues = previous.get("leagues") or {}
    for key, league in current_leagues.items():
        previous_league = previous_leagues.get(key, {})
        if not league.get("focused_club_news") and previous_league.get("focused_club_news"):
            league["focused_club_news"] = previous_league["focused_club_news"]
        if not league.get("all_news") and previous_league.get("all_news"):
            league["all_news"] = previous_league["all_news"]
    return current


def _filter_news_sources(dataset: dict[str, Any], allowed_sources: set[str]) -> None:
    for section in ("world_cup_news", "france_news", "general_news", "all_news"):
        articles = dataset.get(section)
        if isinstance(articles, list):
            dataset[section] = [article for article in articles if _news_source_allowed(article, allowed_sources)]
    for section in ("focused_team_news", "focused_club_news"):
        focused = dataset.get(section)
        if isinstance(focused, dict):
            dataset[section] = {key: [article for article in value if _news_source_allowed(article, allowed_sources)] for key, value in focused.items()}


def _filter_leagues_news_sources(dataset: dict[str, Any], allowed_sources: set[str]) -> None:
    articles = dataset.get("all_news")
    if isinstance(articles, list):
        dataset["all_news"] = [article for article in articles if _news_source_allowed(article, allowed_sources)]
    for league in (dataset.get("leagues") or {}).values():
        _filter_news_sources(league, allowed_sources)


def _news_source_allowed(article: dict[str, Any], allowed_sources: set[str]) -> bool:
    source = str(article.get("source_name") or article.get("source") or "").casefold()
    normalized = source.replace("é", "e").replace("è", "e").replace("ê", "e").replace("’", "'")
    return any(allowed in normalized for allowed in allowed_sources)


def _sanitize_dataset(dataset: dict[str, Any]) -> None:
    for details in (dataset.get("teams_details") or {}).values():
        for section in ("squad", "starters", "substitutes"):
            details[section] = _clean_roster(details.get(section, []) or [])
    blocked_sources = {"espn", "bbc", "bbc sport", "google news"}
    for section in ("world_cup_news", "france_news", "general_news", "all_news"):
        articles = dataset.get(section)
        if isinstance(articles, list):
            dataset[section] = [article for article in articles if str(article.get("source", "")).casefold() not in blocked_sources]
    sources = dataset.get("sources")
    if isinstance(sources, list):
        dataset["sources"] = [
            source for source in sources
            if not str(source.get("name", "")).casefold().startswith(("actu coupe du monde - espn", "actu coupe du monde - bbc", "actu ligue des champions - espn", "actu ligue des champions - bbc"))
        ]


def _clean_roster(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for player in players:
        name = " ".join(str(player.get("name") or "").split())
        position = " ".join(str(player.get("position") or "").split())
        number = " ".join(str(player.get("number") or player.get("jersey") or player.get("jerseyNumber") or "").split())
        if not name or (not position and not number):
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append({**player, "name": name, "position": position, "number": number})
    return clean


def _build_players_index(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    generated_at = dataset.get("generated_at", "")
    players: dict[str, dict[str, Any]] = {}

    def add_player(
        name: str,
        *,
        club_current: str = "",
        country: str = "",
        position: str = "",
        number: str = "",
        photo_url: str = "",
        associated_team: str = "",
        source: str = "",
    ) -> None:
        clean_name = " ".join(str(name or "").split())
        if not clean_name:
            return
        key = clean_name.casefold()
        current = players.setdefault(
            key,
            {
                "name": clean_name,
                "club_current": "",
                "country": "",
                "position": "",
                "number": "",
                "photo_url": "",
                "associated_team": "",
                "updated_at": generated_at,
                "source": "",
            },
        )
        for field, value in {
            "club_current": club_current,
            "country": country,
            "position": position,
            "number": number,
            "photo_url": photo_url,
            "associated_team": associated_team,
            "source": source,
        }.items():
            if value and not current.get(field):
                current[field] = str(value)
        if generated_at:
            current["updated_at"] = generated_at

    for player in dataset.get("top_scorers", []) + dataset.get("top_assists", []):
        add_player(
            player.get("name", ""),
            club_current=player.get("team", ""),
            country=player.get("country", ""),
            photo_url=player.get("photo_url", ""),
            associated_team=player.get("team", ""),
            source=player.get("source") or "FotMob/ESPN stats",
        )

    for team_name, details in dataset.get("teams_details", {}).items():
        sources = details.get("sources") or []
        source = ", ".join(sources) if isinstance(sources, list) else str(sources or "")
        for section in ("squad", "starters", "substitutes"):
            for player in details.get(section, []) or []:
                add_player(
                    player.get("name", ""),
                    club_current=team_name,
                    country=details.get("name", team_name),
                    position=player.get("position", ""),
                    number=player.get("number") or player.get("jersey") or player.get("jerseyNumber") or "",
                    photo_url=player.get("photo_url", ""),
                    associated_team=team_name,
                    source=source or "ESPN/FotMob roster",
                )

    return sorted(players.values(), key=lambda item: item.get("name", "").casefold())


def _merge_leagues_refresh(previous_data: dict[str, Any] | None, refreshed_data: dict[str, Any]) -> dict[str, Any]:
    if not previous_data:
        return refreshed_data
    data = dict(refreshed_data)
    leagues = dict(previous_data.get("leagues", {}))
    for key, league in (refreshed_data.get("leagues") or {}).items():
        previous_league = leagues.get(key, {})
        if not league.get("standings") and previous_league.get("standings"):
            merged = dict(previous_league)
            for field in ("top_scorers", "top_assists", "focused_club_news", "teams_details", "generated_at", "sources"):
                if league.get(field):
                    merged[field] = _merge_team_footmercato_cache(previous_league.get(field), league[field]) if field == "teams_details" else league[field]
            leagues[key] = merged
        else:
            leagues[key] = league
    data["leagues"] = leagues
    if not data.get("big5_top_scorers"):
        data["big5_top_scorers"] = previous_data.get("big5_top_scorers", [])
    return data



def _merge_team_footmercato_cache(previous: Any, current: Any) -> Any:
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return current
    merged = dict(current)
    for team, previous_details in previous.items():
        if not isinstance(previous_details, dict):
            continue
        current_details = dict(merged.get(team, {}))
        for field in (
            "coach_info",
            "coach_name",
            "coach_age",
            "coach_country",
            "coach_country_flag",
            "coach_matches",
            "coach_wins",
            "coach_draws",
            "coach_losses",
            "coach_win_percent",
            "coach_draw_percent",
            "coach_loss_percent",
            "honors",
            "palmares",
            "footmercato_url",
            "source",
            "last_updated",
        ):
            if not current_details.get(field) and previous_details.get(field):
                current_details[field] = previous_details[field]
        if current_details:
            merged[team] = current_details
    return merged


def _read_cache(path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _merge_refresh(previous_data: dict[str, Any] | None, refreshed_data: dict[str, Any]) -> dict[str, Any]:
    if not (_is_failed_refresh(refreshed_data) and previous_data and _has_core_data(previous_data)):
        return refreshed_data

    data = dict(previous_data)
    for key in (
        "all_time_top_scorers",
        "all_time_top_assisters",
        "world_cup_news",
        "france_news",
        "general_news",
        "all_news",
        "focused_team_news",
        "focused_club_news",
        "news_sources",
        "top_scorers",
        "top_assists",
        "teams_details",
        "players_index",
        "today_matches",
        "sources",
    ):
        if key in {"general_news", "all_news", "focused_team_news", "focused_club_news", "news_sources", "sources"}:
            data[key] = refreshed_data.get(key, [] if key != "focused_team_news" and key != "focused_club_news" else {})
        elif refreshed_data.get(key):
            data[key] = _merge_team_footmercato_cache(previous_data.get(key), refreshed_data[key]) if key == "teams_details" else refreshed_data[key]
    data["errors"] = [
        "Mise à jour impossible pour le moment : conservation du dernier cache valide.",
        *refreshed_data.get("errors", []),
    ]
    return data


def _is_failed_refresh(data: dict[str, Any]) -> bool:
    return bool(data.get("errors")) and not _has_core_data(data)


def _has_core_data(data: dict[str, Any]) -> bool:
    standings = data.get("standings", [])
    group_matches = data.get("group_matches", [])
    knockout = data.get("knockout", [])
    has_standings = any(group.get("teams") for group in standings)
    has_group_matches = any(group.get("matches") for group in group_matches)
    has_knockout_matches = any(round_data.get("matches") for round_data in knockout)
    return has_standings or has_group_matches or has_knockout_matches


if __name__ == "__main__":
    main()
