from __future__ import annotations

import json
from typing import Any

from src.config import CACHE_FILE, CHAMPIONS_LEAGUE_CACHE_FILE, DATA_DIR, OUTPUT_HTML
from src.fetchers import enrich_players_with_known_country_flags, fetch_champions_league_data, fetch_dashboard_data
from src.render import render_html


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    worldcup_data = _merge_refresh(_read_cache(CACHE_FILE), fetch_dashboard_data())
    champions_league_data = _merge_refresh(_read_cache(CHAMPIONS_LEAGUE_CACHE_FILE), fetch_champions_league_data())
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
    render_html(
        {
            "worldcup": worldcup_data,
            "champions_league": champions_league_data,
        },
        OUTPUT_HTML,
    )
    print(f"Dashboard généré : {OUTPUT_HTML}")


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
            data[key] = refreshed_data[key]
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
