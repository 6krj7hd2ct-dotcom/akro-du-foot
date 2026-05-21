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
        dataset["top_scorers"] = enrich_players_with_known_country_flags(dataset.get("top_scorers", []))
        dataset["top_assists"] = enrich_players_with_known_country_flags(dataset.get("top_assists", []))
        dataset["all_time_top_assisters"] = []

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
        "today_matches",
    ):
        if key in {"general_news", "all_news", "focused_team_news", "focused_club_news", "news_sources"}:
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
