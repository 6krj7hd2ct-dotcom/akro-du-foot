from __future__ import annotations

import json
import re
import unicodedata
import base64
import hashlib
import hmac
import os
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

try:
    from flask import Flask, Response, jsonify, request, send_file
except ImportError:
    Flask = None
    Response = None
    jsonify = None
    request = None
    send_file = None

from src.config import BASE_DIR, CACHE_FILE, CHAMPIONS_LEAGUE_CACHE_FILE, HALL_OF_FAME_CACHE_FILE, LEAGUES_CACHE_FILE, MERCATO_LIVE_CACHE_FILE, NEWS_CACHE_FILE, OUTPUT_HTML
from src.fetchers import fetch_all_news, fetch_champions_league_news, fetch_france_header_news, fetch_league_news, fetch_world_cup_news, filter_news_articles, rank_articles, dedupe_articles

COMMUNITY_FILE = BASE_DIR / "data" / "community.json"
WATCH_ROOM = "worldcup-watch-party"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
COACH_REFUSAL = "Je suis Coach, je réponds uniquement aux questions liées au football."
COACH_UNAVAILABLE = "Coach indisponible : clé OpenAI absente ou invalide."
COACH_DISCLAIMER = "Analyse fictive pour le jeu entre amis. Aucun conseil de pari réel."
COACH_FACTS_LAST_VERIFIED = "2026-05-24"
COACH_VERIFICATION_SOURCES = ("Wikipedia", "FotMob", "Transfermarkt", "SofaScore", "ESPN", "API Football")
API_FOOTBALL_BASE_URL = os.environ.get("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").rstrip("/")
COACH_API_FOOTBALL_CACHE_TTL = max(3600, int(os.environ.get("AKRO_COACH_API_FOOTBALL_CACHE_TTL", "604800")))
COACH_API_FOOTBALL_TIMEOUT = max(4, int(os.environ.get("AKRO_COACH_API_FOOTBALL_TIMEOUT", "12")))

COMMUNITY_LEVELS = [
    ("Débutant", "Bronze", "🥉"),
    ("Supporter", "Bronze", "🥉"),
    ("Observateur", "Bronze", "🥉"),
    ("Analyste", "Argent", "🥈"),
    ("Tacticien", "Argent", "🥈"),
    ("Visionnaire", "Argent", "🥈"),
    ("Expert", "Or", "🥇"),
    ("Prodige", "Or", "🥇"),
    ("Maestro", "Or", "🥇"),
    ("Elite", "Diamant", "💎"),
    ("Stratège", "Diamant", "💎"),
    ("Architecte", "Diamant", "💎"),
    ("Capitaine", "Étoile", "⭐"),
    ("Sélectionneur", "Étoile", "⭐"),
    ("Champion", "Trophée", "🏆"),
    ("Grand Champion", "Trophée", "🏆"),
    ("Icône", "Couronne", "👑"),
    ("Légende", "Couronne", "👑"),
    ("Immortel", "Galaxie", "✦"),
    ("Hall of Fame", "Galaxie", "✦"),
]

SUPABASE_TIMEOUT = 8
SYNC_STALL_SECONDS = max(60, int(os.environ.get("AKRO_SYNC_STALL_MINUTES", "5")) * 60)
SUPABASE_FOOTBALL_CACHE_TTL = max(30, int(os.environ.get("AKRO_SUPABASE_FOOTBALL_CACHE_TTL", "300")))
SUPABASE_FAILURE_TTL = max(30, int(os.environ.get("AKRO_SUPABASE_FAILURE_TTL", "120")))
SUPABASE_PROFILE_COLUMNS = "id,pseudo,avatar_url,favorite_club,favorite_club_logo,favorite_nation,favorite_nation_flag,created_at,updated_at"
SUPABASE_PROFILE_STATS_COLUMNS = "id,profile_id,total_predictions,correct_scores,correct_results,total_points,rank,updated_at"
SUPABASE_PREDICTION_COLUMNS = "id,profile_id,match_id,home_team,away_team,predicted_home_score,predicted_away_score,actual_home_score,actual_away_score,status,points,created_at"
SUPABASE_PROFILE_BADGE_COLUMNS = "id,profile_id,badge_key,badge_name,unlocked_at"
SUPABASE_COACH_COLUMNS = "id,session_id,role,content,detected_entity,detected_intent,created_at"
BUILD_VERSION_TOKEN = "__AKRO_BUILD_VERSION__"
NO_STORE_CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"
LIVE_SCORE_REFRESH_INTERVAL = 60
LIVE_SCORE_REFRESH_LOCK = threading.Lock()
LIVE_SCORE_LAST_REFRESH_AT = 0.0
LIVE_SCORE_REFRESHING = False
LIVE_SCORE_LAST_ERROR = ""
MATCH_ARTICLE_GENERATION_INTERVAL = 300
MATCH_ARTICLE_GENERATION_DELAY_SECONDS = 15 * 60
MATCH_ARTICLE_GENERATION_LOCK = threading.Lock()
MATCH_ARTICLE_GENERATION_LAST_RUN = 0.0
MATCH_ARTICLE_GENERATION_RUNNING = False
HALL_OF_FAME_REFRESH_LOCK = threading.Lock()
HALL_OF_FAME_REFRESH_LAST_RUN = 0.0
HALL_OF_FAME_REFRESH_RUNNING = False
HALL_OF_FAME_TIMEZONE = ZoneInfo(os.environ.get("AKRO_HALL_OF_FAME_TIMEZONE", "Europe/Paris"))
FOOTBALL_SUPABASE_CACHE_LOCK = threading.Lock()
FOOTBALL_SUPABASE_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}
SUPABASE_FAILED_PATHS: dict[str, float] = {}
WIKIPEDIA_VERIFICATION_CACHE: dict[str, tuple[float, list[str]]] = {}
WIKIPEDIA_VERIFICATION_CACHE_TTL = max(300, int(os.environ.get("AKRO_WIKIPEDIA_CACHE_TTL", "21600")))

app = Flask(__name__) if Flask else None


if app:
    @app.get("/")
    def index():
        return _runtime_file_response(OUTPUT_HTML, "text/html; charset=utf-8", replace_build_version=True, no_store=True)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/watch-party")
    def watch_party():
        return watch_party_html()

    @app.get("/admin/sync")
    def admin_sync_page_route():
        return Response(admin_sync_html(), mimetype="text/html")

    @app.get("/manifest.json")
    def manifest_file():
        return _runtime_file_response(BASE_DIR / "manifest.json", "application/manifest+json", no_store=True)

    @app.get("/service-worker.js")
    def service_worker_file():
        return _runtime_file_response(BASE_DIR / "service-worker.js", "application/javascript; charset=utf-8", no_store=True)

    @app.get("/icons/<path:filename>")
    def icon_file(filename: str):
        return send_file(BASE_DIR / "icons" / filename)

    @app.get("/avatars/<path:filename>")
    def avatar_file(filename: str):
        return send_file(BASE_DIR / "public" / "avatars" / filename)


def _background_updates_enabled() -> bool:
    # Render must open the web port immediately. Background scraping is disabled
    # there unless explicitly re-enabled after the service is healthy.
    if os.environ.get("RENDER") and os.environ.get("AKRO_ALLOW_RENDER_BACKGROUND_UPDATES", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    return os.environ.get("AKRO_BACKGROUND_UPDATES", "").strip().lower() in {"1", "true", "yes", "on"}


def _run_dashboard_update_loop() -> None:
    interval = max(300, int(os.environ.get("AKRO_UPDATE_INTERVAL_SECONDS", "3600")))
    while True:
        time.sleep(interval)
        subprocess.run(
            [os.environ.get("PYTHON_BIN", sys.executable), str(BASE_DIR / "update_dashboard.py")],
            cwd=BASE_DIR,
            check=False,
        )


if app and _background_updates_enabled():
    threading.Thread(target=_run_dashboard_update_loop, daemon=True).start()


def _build_version() -> str:
    explicit = os.environ.get("AKRO_BUILD_VERSION", "").strip()
    if explicit:
        return explicit
    render_commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if render_commit:
        return render_commit[:12]
    try:
        return str(int(OUTPUT_HTML.stat().st_mtime))
    except OSError:
        return str(int(time.time()))


def _replace_build_version(raw: bytes, content_type: str, enabled: bool = False) -> bytes:
    if not enabled:
        return raw
    if "text/html" not in content_type:
        return raw
    text = raw.decode("utf-8")
    return text.replace(BUILD_VERSION_TOKEN, _build_version()).encode("utf-8")


def _apply_cache_headers_to_flask_response(response: Any, no_store: bool = False) -> Any:
    if no_store:
        response.headers["Cache-Control"] = NO_STORE_CACHE_CONTROL
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-Akro-Build"] = _build_version()
    return response


def _runtime_file_response(path: Path, content_type: str, replace_build_version: bool = False, no_store: bool = False) -> Any:
    raw = path.read_bytes()
    raw = _replace_build_version(raw, content_type, replace_build_version)
    response = Response(raw, content_type=content_type)
    response.headers["Content-Length"] = str(len(raw))
    response.headers["X-Akro-Served-File"] = path.name
    return _apply_cache_headers_to_flask_response(response, no_store=no_store)


def news_payload(filter_key: str = "all") -> dict[str, Any]:
    data = _read_json(NEWS_CACHE_FILE, {})
    articles = data.get("all_articles") or data.get("articles") or []
    filtered = filter_news_articles(rank_articles(dedupe_articles(articles)), filter_key)[:50]
    return {
        "generated_at": data.get("generated_at", ""),
        "filter": filter_key or "all",
        "articles": filtered,
        "count": len(filtered),
        "sources": data.get("sources", []),
        "errors": data.get("errors", []),
    }


def refresh_global_news_payload(filter_key: str = "all") -> dict[str, Any]:
    previous = _read_json(NEWS_CACHE_FILE, {})
    data = fetch_all_news(filter_key=filter_key or "all", previous=previous.get("all_articles") or previous.get("articles") or [])
    NEWS_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return news_payload(filter_key)


def hall_of_fame_payload() -> dict[str, Any]:
    _schedule_hall_of_fame_refresh()
    cache = _read_json(HALL_OF_FAME_CACHE_FILE, {})
    if not isinstance(cache, dict) or not isinstance(cache.get("lists"), dict) or not cache.get("lists"):
        _refresh_hall_of_fame_cache()
        cache = _read_json(HALL_OF_FAME_CACHE_FILE, {})
    lists = cache.get("lists") if isinstance(cache, dict) else {}
    sources = cache.get("sources") if isinstance(cache, dict) else []
    return {
        "generated_at": cache.get("generated_at", "") if isinstance(cache, dict) else "",
        "checked_at": cache.get("checked_at", "") if isinstance(cache, dict) else "",
        "status": cache.get("status", "fallback") if isinstance(cache, dict) else "fallback",
        "lists": lists if isinstance(lists, dict) else {},
        "sources": sources if isinstance(sources, list) else [],
    }


def _hall_of_fame_refresh_enabled() -> bool:
    return os.environ.get("AKRO_DISABLE_HALL_OF_FAME_REFRESH", "").strip().lower() not in {"1", "true", "yes", "on"}


def _seconds_until_next_hall_of_fame_refresh(now: datetime | None = None) -> float:
    now = now.astimezone(HALL_OF_FAME_TIMEZONE) if now else datetime.now(HALL_OF_FAME_TIMEZONE)
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return max(0.0, (target - now).total_seconds())


def _schedule_hall_of_fame_refresh(force: bool = False) -> None:
    global HALL_OF_FAME_REFRESH_LAST_RUN, HALL_OF_FAME_REFRESH_RUNNING
    if not _hall_of_fame_refresh_enabled():
        return
    now = time.time()
    with HALL_OF_FAME_REFRESH_LOCK:
        if HALL_OF_FAME_REFRESH_RUNNING:
            return
        next_delay = _seconds_until_next_hall_of_fame_refresh()
        should_run = force or (next_delay > 23 * 3600 and now - HALL_OF_FAME_REFRESH_LAST_RUN > 12 * 3600)
        if not should_run:
            return
        HALL_OF_FAME_REFRESH_RUNNING = True
        HALL_OF_FAME_REFRESH_LAST_RUN = now
    threading.Thread(target=_refresh_hall_of_fame_cache, daemon=True).start()


def _valid_hall_of_fame_list(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    players = value.get("players")
    if not isinstance(players, list) or not players:
        return False
    return all(isinstance(item, dict) and item.get("name") and item.get("value") not in {None, ""} for item in players[:3])


def _refresh_hall_of_fame_cache() -> None:
    global HALL_OF_FAME_REFRESH_RUNNING
    try:
        previous = _read_json(HALL_OF_FAME_CACHE_FILE, {})
        curated = _read_json(BASE_DIR / "data" / "hall_of_fame_updates.json", {})
        reliable_lists = {}
        source_lists = curated.get("lists") if isinstance(curated, dict) else {}
        if isinstance(source_lists, dict):
            reliable_lists = {key: value for key, value in source_lists.items() if _valid_hall_of_fame_list(value)}
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "updated" if reliable_lists else "fallback",
            "lists": reliable_lists or (previous.get("lists") if isinstance(previous, dict) and isinstance(previous.get("lists"), dict) else {}),
            "sources": curated.get("sources", []) if isinstance(curated, dict) and isinstance(curated.get("sources"), list) else (previous.get("sources", []) if isinstance(previous, dict) and isinstance(previous.get("sources"), list) else []),
        }
        HALL_OF_FAME_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        HALL_OF_FAME_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as error:
        print(f"[hall-of-fame] vérification ignorée: {error}", flush=True)
    finally:
        HALL_OF_FAME_REFRESH_RUNNING = False


def _run_hall_of_fame_daily_loop() -> None:
    while True:
        time.sleep(max(60.0, _seconds_until_next_hall_of_fame_refresh()))
        _schedule_hall_of_fame_refresh(force=True)


if app and _hall_of_fame_refresh_enabled():
    threading.Thread(target=_run_hall_of_fame_daily_loop, daemon=True).start()


MATCH_ARTICLES_MIN_DATE = date(2026, 4, 28)


def match_articles_payload(limit: int = 12, focus: str = "") -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 12), 12))
    focus_teams = _match_article_focus_teams(focus)
    articles = _dedupe_match_articles([
        article
        for article in [*_match_articles_rows(200, max_limit=200), *_static_match_articles_rows()]
        if _is_official_match_article_competition(article.get("competition")) or _match_article_matches_focus(article, focus_teams)
    ])[:safe_limit]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "articles": articles,
        "count": len(articles),
    }


def match_article_detail_html(slug: str) -> tuple[str, int]:
    slug = _clean(slug, 160)
    articles = _match_articles_rows(12, slug=slug, apply_filters=False)
    article = articles[0] if articles else None
    if not article:
        article = next((item for item in _static_match_articles_rows() if item.get("slug") == slug), None)
    if not article:
        return _match_article_page_html({
            "title": "Résumé introuvable",
            "summary": "Ce résumé de match n'est pas disponible.",
            "content": "Le résumé demandé n'existe pas ou n'est pas encore publié.",
            "competition": "Akro du Foot",
            "date": "",
            "score": "",
            "home_team": "",
            "away_team": "",
        }), 404
    return _match_article_page_html(article), 200


def _static_match_articles_rows() -> list[dict[str, Any]]:
    return [{
        "id": "static-paris-back-2-back",
        "match_id": "champions-final-2025-2026-psg-arsenal",
        "match_api_id": "champions-final-2025-2026-psg-arsenal",
        "slug": "paris-back-2-back",
        "title": "Paris Back 2 Back",
        "summary": "Paris Saint-Germain remporte la Champions League 2025-2026 face à Arsenal, finaliste, après un 1-1 intense et une séance de tirs au but gagnée 4-3.",
        "content": "Paris Saint-Germain conserve sa couronne européenne au terme d'une finale tendue face à Arsenal. Après un score de 1-1, Paris s'impose 4-3 aux tirs au but et remporte la Champions League 2025-2026.\n\nArsenal termine finaliste après une campagne solide, mais Paris a mieux tenu le moment décisif. Cette victoire confirme la place du PSG au sommet de l'Europe.",
        "competition": "Champions League",
        "status": "published",
        "date": "2026-05-30T16:00:00Z",
        "published_at": "2026-05-30T19:30:00Z",
        "created_at": "2026-05-30T19:30:00Z",
        "home_team": "Paris Saint-Germain",
        "away_team": "Arsenal",
        "home_logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
        "away_logo_url": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
        "teams": "Paris Saint-Germain vs Arsenal",
        "score": "1 - 1 · TAB 4-3",
        "winner": "Paris Saint-Germain",
    }]


def _dedupe_match_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for article in sorted(articles or [], key=lambda item: str(item.get("published_at") or item.get("date") or item.get("created_at") or ""), reverse=True):
        key = str(article.get("match_id") or article.get("slug") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(article)
    return output


def _match_articles_rows(limit: int = 12, slug: str = "", max_limit: int = 12, official_only: bool = False, apply_filters: bool = True) -> list[dict[str, Any]]:
    if not _supabase_service_enabled():
        return []
    safe_limit = max(1, min(int(limit or 12), max(1, int(max_limit or 12))))
    slug_filter = f"&slug=eq.{quote(slug, safe='')}" if slug else ""
    articles = _supabase_service_request(
        "GET",
        "match_articles?"
        "select=id,match_id,match_api_id,slug,title,summary,content,competition,status,published_at,created_at"
        f"&status=eq.published{slug_filter}&order=published_at.desc&limit={safe_limit}",
    )
    if not isinstance(articles, list) or not articles:
        return []

    deduped = []
    seen = set()
    for article in articles:
        if not isinstance(article, dict):
            continue
        key = str(article.get("match_id") or article.get("slug") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(article)
    if not deduped:
        return []

    match_ids = [str(article.get("match_id") or "") for article in deduped if article.get("match_id")]
    matches = _supabase_service_request(
        "GET",
        f"matches?select=id,api_id,competition_id,match_date,home_team_id,away_team_id,home_score,away_score,status&limit={max(1, len(match_ids))}&id=in.({','.join(quote(item, safe='') for item in match_ids)})",
    ) if match_ids else []
    match_by_id = {str(row.get("id")): row for row in (matches or []) if isinstance(row, dict)}
    competition_ids = sorted({
        str(match.get("competition_id") or "")
        for match in match_by_id.values()
        if match.get("competition_id")
    })
    competitions = _supabase_service_request(
        "GET",
        f"competitions?select=id,name&limit={max(1, len(competition_ids))}&id=in.({','.join(quote(item, safe='') for item in competition_ids)})",
    ) if competition_ids else []
    competition_by_id = {str(row.get("id")): str(row.get("name") or "") for row in (competitions or []) if isinstance(row, dict)}
    team_ids = sorted({
        str(match.get(field) or "")
        for match in match_by_id.values()
        for field in ("home_team_id", "away_team_id")
        if match.get(field)
    })
    teams = _supabase_service_request(
        "GET",
        f"teams?select=id,name,logo_url,raw_data&limit={max(1, len(team_ids))}&id=in.({','.join(quote(item, safe='') for item in team_ids)})",
    ) if team_ids else []
    team_by_id = {str(row.get("id")): row for row in (teams or []) if isinstance(row, dict)}

    output = []
    for article in deduped:
        match = match_by_id.get(str(article.get("match_id") or ""), {})
        competition = competition_by_id.get(str(match.get("competition_id") or ""), "") or str(article.get("competition") or "")
        article_date = match.get("match_date") or article.get("published_at") or article.get("created_at") or ""
        if apply_filters and not _match_article_is_recent_enough(article_date):
            continue
        if official_only and not _is_official_match_article_competition(competition):
            continue
        home_row = team_by_id.get(str(match.get("home_team_id") or ""), {})
        away_row = team_by_id.get(str(match.get("away_team_id") or ""), {})
        home = str(home_row.get("name") or "") if isinstance(home_row, dict) else ""
        away = str(away_row.get("name") or "") if isinstance(away_row, dict) else ""
        home_score = match.get("home_score")
        away_score = match.get("away_score")
        score = f"{home_score} - {away_score}" if home_score is not None and away_score is not None else ""
        output.append({
            **article,
            "competition": competition or article.get("competition") or "",
            "date": article_date,
            "home_team": home,
            "away_team": away,
            "home_logo_url": _match_article_team_logo_url(home_row),
            "away_logo_url": _match_article_team_logo_url(away_row),
            "teams": " vs ".join(team for team in (home, away) if team),
            "score": score,
        })
    return output


def _match_article_team_logo_url(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
    raw_team = raw_data.get("team") if isinstance(raw_data.get("team"), dict) else {}
    return str(row.get("logo_url") or raw_team.get("logo") or raw_data.get("logo_url") or raw_data.get("logo") or "")


def _match_article_is_recent_enough(value: Any) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return parsed >= MATCH_ARTICLES_MIN_DATE


def _is_official_match_article_competition(value: Any) -> bool:
    normalized = _normalize_football_text(str(value or ""))
    return (
        "coupe du monde" in normalized
        or "world cup" in normalized
        or normalized == "euro"
        or "euro " in f"{normalized} "
        or "european championship" in normalized
        or "champions league" in normalized
        or "ligue des champions" in normalized
    )


def _match_article_focus_teams(value: str) -> list[str]:
    teams = []
    for item in str(value or "").split("|"):
        normalized = _normalize_football_text(item)
        if normalized and normalized not in teams:
            teams.append(normalized)
    return teams


def _match_article_matches_focus(article: dict[str, Any], focus_teams: list[str]) -> bool:
    if not focus_teams:
        return False
    home = _normalize_football_text(article.get("home_team") or "")
    away = _normalize_football_text(article.get("away_team") or "")
    return any(team and team in {home, away} for team in focus_teams)


def _match_article_page_html(article: dict[str, Any]) -> str:
    title = _html_escape(article.get("title") or "Résumé de match")
    summary = _html_escape(article.get("summary") or "")
    content = _html_escape(article.get("content") or "").replace("\n", "<br>")
    competition = _html_escape(article.get("competition") or "Compétition")
    date = _html_escape(_format_article_date(article.get("date")) or "")
    teams = _html_escape(article.get("teams") or "")
    score = _html_escape(article.get("score") or "")
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Akro du Foot</title>
  <style>
    body {{ margin: 0; min-height: 100vh; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #f4f8ff; background: radial-gradient(circle at top left, rgba(31,111,235,.25), transparent 34rem), linear-gradient(135deg, #07111f, #10243b); }}
    main {{ width: min(920px, calc(100% - 28px)); margin: 0 auto; padding: 42px 0; }}
    a {{ color: #f5c96b; font-weight: 900; text-decoration: none; }}
    article {{ border: 1px solid rgba(255,255,255,.14); border-radius: 22px; padding: clamp(20px, 4vw, 38px); background: rgba(255,255,255,.06); box-shadow: 0 24px 70px rgba(0,0,0,.28); }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; color: #b9c9dc; font-weight: 850; }}
    .pill {{ border: 1px solid rgba(245,201,107,.28); border-radius: 999px; padding: 6px 10px; color: #ffe1a0; background: rgba(245,201,107,.10); }}
    h1 {{ margin: 0 0 14px; font-size: clamp(30px, 6vw, 56px); line-height: .96; }}
    .summary {{ color: #d8e5f4; font-size: 18px; line-height: 1.55; font-weight: 750; }}
    .content {{ margin-top: 24px; color: #c9d7e7; line-height: 1.65; font-size: 16px; }}
  </style>
</head>
<body>
  <main>
    <p><a href="/">← Retour à Akro du Foot</a></p>
    <article>
      <div class="meta"><span class="pill">{competition}</span><span>{date}</span><span>{teams}</span><span>{score}</span></div>
      <h1>{title}</h1>
      <p class="summary">{summary}</p>
      <div class="content">{content}</div>
    </article>
  </main>
</body>
</html>"""


def match_articles_archive_html() -> str:
    articles = _dedupe_match_articles([
        *_match_articles_rows(120, max_limit=120, official_only=True),
        *_static_match_articles_rows(),
    ])[:60]
    cards = "".join(_match_article_archive_card(article) for article in articles)
    if not cards:
        cards = '<div class="empty">Aucun résumé disponible pour le moment.</div>'
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Archives des résumés · Akro du Foot</title>
  <style>
    body {{ margin: 0; min-height: 100vh; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #f4f8ff; background: radial-gradient(circle at top left, rgba(31,111,235,.25), transparent 34rem), linear-gradient(135deg, #07111f, #10243b); }}
    main {{ width: min(1180px, calc(100% - 28px)); margin: 0 auto; padding: 42px 0; }}
    a {{ color: inherit; text-decoration: none; }}
    .back {{ color: #f5c96b; font-weight: 900; }}
    h1 {{ margin: 16px 0 8px; font-size: clamp(34px, 6vw, 64px); line-height: .95; }}
    .intro {{ color: #b9c9dc; font-weight: 750; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 24px; }}
    .card {{ position: relative; display: grid; gap: 10px; min-height: 176px; padding: 15px; border-radius: 16px; border: 1px solid rgba(245,201,107,.24); background: linear-gradient(145deg, rgba(7,17,31,.95), rgba(25,43,62,.88)); box-shadow: 0 18px 44px rgba(0,0,0,.20); overflow: hidden; }}
    .card::before {{ content: ""; position: absolute; inset: 0; background: radial-gradient(circle at right top, rgba(245,201,107,.15), transparent 36%), radial-gradient(circle at left bottom, rgba(99,232,255,.10), transparent 34%); pointer-events: none; }}
    .card > * {{ position: relative; z-index: 1; }}
    .top, .line {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; min-width: 0; }}
    .competition {{ color: #ffe1a0; font-size: 11px; font-weight: 950; letter-spacing: .04em; text-transform: uppercase; }}
    .date {{ color: #b9c9dc; font-size: 12px; font-weight: 850; }}
    .teams {{ color: #fff; font-size: 17px; font-weight: 950; line-height: 1.15; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .team-line {{ min-width: 0; display: inline-flex; align-items: center; gap: 7px; overflow: hidden; vertical-align: middle; }}
    .team-line span {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .team-logo {{ width: 22px; height: 22px; flex: 0 0 22px; border-radius: 50%; object-fit: contain; object-position: center; padding: 2px; background: rgba(255,255,255,.92); border: 1px solid rgba(255,255,255,.16); }}
    .vs {{ color: #9fb0c2; font-size: 12px; font-weight: 950; text-transform: uppercase; }}
    .score {{ border-radius: 999px; padding: 5px 9px; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); font-size: 12px; font-weight: 950; white-space: nowrap; }}
    .title {{ color: #f4f8ff; font-size: 15px; line-height: 1.35; font-weight: 900; }}
    .read {{ align-self: end; color: #f5c96b; font-size: 13px; font-weight: 950; }}
    .empty {{ grid-column: 1 / -1; padding: 18px; border-radius: 16px; color: #b9c9dc; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12); }}
  </style>
</head>
<body>
  <main>
    <a class="back" href="/">← Retour à Akro du Foot</a>
    <h1>Archives des résumés</h1>
    <p class="intro">Tous les résumés de matchs publiés automatiquement, du plus récent au plus ancien.</p>
    <section class="grid">{cards}</section>
  </main>
</body>
</html>"""


def _match_article_archive_card(article: dict[str, Any]) -> str:
    href = f"/actus/resume/{quote(str(article.get('slug') or ''), safe='')}"
    competition = _html_escape(article.get("competition") or "Compétition")
    date = _html_escape(_format_article_date(article.get("date")) or "")
    teams = _match_article_teams_html(article)
    score = _html_escape(article.get("score") or "")
    title = _html_escape(article.get("title") or article.get("summary") or "Résumé de match")
    return f"""<a class="card" href="{href}">
      <div class="top"><span class="competition">{competition}</span><span class="date">{date}</span></div>
      <div class="line"><span class="teams">{teams}</span><span class="score">{score}</span></div>
      <div class="title">{title}</div>
      <span class="read">Lire le résumé</span>
    </a>"""


def _match_article_teams_html(article: dict[str, Any]) -> str:
    home = article.get("home_team") or ""
    away = article.get("away_team") or ""
    if not home and not away:
        return _html_escape(article.get("teams") or "Match")
    return (
        f"{_match_article_team_line_html(home, article.get('home_logo_url') or '')} "
        f"<span class=\"vs\">vs</span> "
        f"{_match_article_team_line_html(away, article.get('away_logo_url') or '')}"
    )


def _match_article_team_line_html(name: Any, logo_url: Any) -> str:
    logo = f'<img class="team-logo" src="{_html_escape(logo_url)}" alt="" loading="lazy">' if logo_url else ""
    return f'<span class="team-line">{logo}<span>{_html_escape(name)}</span></span>'


def _html_escape(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def refresh_news_payload(competition: str, focus: str, league: str = "") -> dict[str, Any]:
    key = str(competition or "").casefold()
    live: list[dict[str, Any]] = []
    if "league" in key and "champ" not in key:
        root = _read_json(LEAGUES_CACHE_FILE, {})
        data = (root.get("leagues") or {}).get(league, {}) if league else root
        live = fetch_league_news(league) if league else []
        cached = data.get("all_news") or root.get("all_news") or []
    elif "champ" in key:
        data = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
        live = fetch_champions_league_news()
        cached = data.get("general_news") or data.get("all_news") or data.get("world_cup_news") or []
    else:
        data = _read_json(CACHE_FILE, {})
        live = fetch_world_cup_news()
        france_live = fetch_france_header_news()
        cached = data.get("general_news") or data.get("all_news") or data.get("world_cup_news") or []
        france_cached = data.get("france_header_news") or []
        articles = _dedupe_articles(live or cached)[:6]
        france_header_news = _dedupe_articles(france_live or france_cached)[:10]
        return {"general": articles, "focused": {}, "all": articles, "france_header_news": france_header_news}
    articles = _dedupe_articles(live or cached)[:6]
    return {"general": articles, "focused": {}, "all": articles}


def _article_matches_focus(article: dict[str, Any], focus: str) -> bool:
    if not focus:
        return False
    haystack = _normalize_football_text(f"{article.get('title', '')} {article.get('summary', '')} {article.get('url', '')}")
    aliases = _focus_aliases_for_news(focus)
    return any(alias and alias in haystack for alias in aliases)


def _focus_aliases_for_news(focus: str) -> set[str]:
    normalized = _normalize_football_text(focus)
    mapping = {
        "paris saint germain": {"psg", "paris sg", "paris saint germain"},
        "manchester city": {"man city", "manchester city", "city"},
        "marseille": {"om", "olympique de marseille", "marseille"},
        "france": {"france", "equipe de france", "bleus"},
        "england": {"angleterre", "england", "three lions"},
        "angleterre": {"angleterre", "england", "three lions"},
        "senegal": {"senegal", "sénégal", "lions de la teranga"},
        "brazil": {"brazil", "bresil", "brésil", "selecao"},
    }
    return {normalized, *{_normalize_football_text(alias) for alias in mapping.get(normalized, set())}}


def _dedupe_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for article in articles or []:
        if not _is_allowed_cached_news(article):
            continue
        key = _normalize_football_text(article.get("title") or article.get("url") or "")[:90]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(article)
    return sorted(out, key=_cached_news_sort_key, reverse=True)


def _balanced_articles(articles: list[dict[str, Any]], limit: int, max_per_source: int = 2) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for article in sorted(articles or [], key=_cached_news_sort_key, reverse=True):
        source = _normalize_football_text(article.get("source_name") or article.get("source") or "source")
        if counts.get(source, 0) >= max_per_source:
            continue
        selected.append(article)
        counts[source] = counts.get(source, 0) + 1
        if len(selected) >= limit:
            return selected
    for article in sorted(articles or [], key=_cached_news_sort_key, reverse=True):
        if article not in selected:
            selected.append(article)
            if len(selected) >= limit:
                break
    return selected


def _cached_news_sort_key(article: dict[str, Any]) -> tuple[int, str]:
    source = _normalize_football_text(article.get("source_name") or article.get("source") or "")
    priority = ["fifa", "l equipe", "eurosport", "eurosport france"]
    score = 40
    for index, name in enumerate(priority):
        if _normalize_football_text(name) in source:
            score = 100 - index
            break
    return (score, str(article.get("published_at") or article.get("date") or ""))


def _is_allowed_cached_news(article: dict[str, Any]) -> bool:
    source = _normalize_football_text(article.get("source_name") or article.get("source", ""))
    link = str(article.get("url", "")).lower()
    hostname = urlparse(link).netloc.replace("www.", "")
    blocked_sources = {"espn", "bbc", "bbc sport", "google news"}
    blocked_domains = ("espn.com", "bbc.", "bbc.co.uk", "news.google.")
    allowed_sources = {"fifa", "l equipe", "l equipe", "eurosport", "eurosport france"}
    allowed_domains = ("fifa.com", "lequipe.fr", "eurosport.fr")
    if source in blocked_sources or any(domain in link for domain in blocked_domains):
        return False
    source_allowed = source in allowed_sources or any(allowed in source for allowed in allowed_sources)
    domain_allowed = any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains)
    return source_allowed and domain_allowed


def community_payload() -> dict[str, Any]:
    _schedule_match_article_generation()
    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    leagues_dashboard = _read_json(LEAGUES_CACHE_FILE, {})
    community = _read_community()
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard, leagues_dashboard)
    supabase = _read_supabase_community(matches)
    source_predictions = supabase.get("predictions") if supabase.get("available") else community.get("predictions", [])
    predictions = _predictions_with_points(source_predictions or [], matches)
    if supabase.get("available"):
        changed_profiles = _sync_supabase_prediction_points(predictions, matches)
        for profile_id, pseudo in changed_profiles:
            _sync_supabase_user_totals(profile_id, pseudo, matches)
    profiles = _community_profiles(predictions, matches, supabase.get("badges", {}))
    if supabase.get("available"):
        _enrich_profiles_with_supabase_users(profiles, supabase.get("users", []))
    leaderboard = _leaderboard(predictions, matches, supabase.get("badges", {}), supabase.get("users", []) if supabase.get("available") else None)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "messages": community.get("messages", [])[-100:],
        "predictions": predictions,
        "leaderboard": leaderboard,
        "profiles": profiles,
        "matches": list(matches.values()),
        "live_refreshing": LIVE_SCORE_REFRESHING,
        "live_refresh_error": LIVE_SCORE_LAST_ERROR,
        "storage": "supabase" if supabase.get("available") else "json",
    }


def _live_score_refresh_enabled() -> bool:
    return os.environ.get("AKRO_DISABLE_LIVE_SCORE_REFRESH", "").strip().lower() not in {"1", "true", "yes", "on"}


def _schedule_live_score_refresh(force: bool = False) -> None:
    global LIVE_SCORE_LAST_REFRESH_AT, LIVE_SCORE_REFRESHING
    if not _live_score_refresh_enabled():
        return
    now = time.time()
    with LIVE_SCORE_REFRESH_LOCK:
        if LIVE_SCORE_REFRESHING:
            return
        if not force and now - LIVE_SCORE_LAST_REFRESH_AT < LIVE_SCORE_REFRESH_INTERVAL:
            return
        LIVE_SCORE_REFRESHING = True
        LIVE_SCORE_LAST_REFRESH_AT = now
    threading.Thread(target=_refresh_live_score_caches, daemon=True).start()


def _schedule_match_article_generation(force: bool = False) -> None:
    global MATCH_ARTICLE_GENERATION_LAST_RUN, MATCH_ARTICLE_GENERATION_RUNNING
    if not _supabase_service_enabled():
        return
    now = time.time()
    with MATCH_ARTICLE_GENERATION_LOCK:
        if MATCH_ARTICLE_GENERATION_RUNNING:
            return
        if not force and now - MATCH_ARTICLE_GENERATION_LAST_RUN < MATCH_ARTICLE_GENERATION_INTERVAL:
            return
        MATCH_ARTICLE_GENERATION_LAST_RUN = now
        MATCH_ARTICLE_GENERATION_RUNNING = True
    threading.Thread(target=_generate_match_articles, daemon=True).start()


def _generate_match_articles() -> None:
    global MATCH_ARTICLE_GENERATION_RUNNING
    try:
        created = _generate_match_articles_once()
        if created:
            print(f"[match-articles] articles générés: {created}", flush=True)
    except Exception as error:
        print(f"[match-articles] génération ignorée: {error}", flush=True)
    finally:
        MATCH_ARTICLE_GENERATION_RUNNING = False


def _refresh_live_score_caches() -> None:
    global LIVE_SCORE_REFRESHING, LIVE_SCORE_LAST_ERROR
    env = dict(os.environ)
    env["AKRO_RENDER_HTML_DURING_UPDATE"] = "0"
    try:
        result = subprocess.run(
            [env.get("PYTHON_BIN", sys.executable), str(BASE_DIR / "update_dashboard.py")],
            cwd=BASE_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        LIVE_SCORE_LAST_ERROR = "" if result.returncode == 0 else (result.stderr or result.stdout or "refresh failed")[-240:]
    except Exception as error:
        LIVE_SCORE_LAST_ERROR = str(error)
    finally:
        LIVE_SCORE_REFRESHING = False


if app:
    @app.get("/api/community")
    def get_community():
        _schedule_live_score_refresh()
        return jsonify(community_payload())

    @app.get("/api/supabase-public-config")
    def supabase_public_config():
        url, key = _supabase_config()
        return jsonify({"url": url, "anon_key": key, "configured": bool(url and key)})

    @app.post("/api/profile-password/hash")
    def profile_password_hash():
        payload = request.get_json(silent=True) or {}
        body, status = make_profile_password_hash(payload)
        return jsonify(body), status

    @app.get("/api/community/profile")
    def get_community_profile():
        pseudo = _clean(request.args.get("pseudo", ""), 32)
        profile = community_payload().get("profiles", {}).get(pseudo)
        if not profile:
            return jsonify({"error": "Profil introuvable."}), 404
        return jsonify(profile)

    @app.get("/api/livekit-token")
    def livekit_token():
        pseudo = _clean(request.args.get("pseudo", ""), 32) or "Invite"
        role = "admin" if request.args.get("role") == "admin" and _is_admin_key(request.args.get("admin_key", "")) else "viewer"
        body, status = make_livekit_token(pseudo, role)
        return jsonify(body), status

    @app.get("/api/watch-chat")
    def watch_chat():
        return jsonify({"messages": _watch_messages()[-120:]})

    @app.get("/api/refresh-news")
    def refresh_news():
        competition = request.args.get("competition", "")
        focus = request.args.get("focus", "")
        return jsonify(refresh_news_payload(competition, focus, request.args.get("league", "")))

    @app.get("/api/news")
    def global_news():
        return jsonify(news_payload(request.args.get("filter", "all")))

    @app.get("/api/news/refresh")
    def refresh_global_news():
        return jsonify(refresh_global_news_payload(request.args.get("filter", "all")))

    @app.get("/api/hall-of-fame")
    def hall_of_fame():
        return jsonify(hall_of_fame_payload())

    @app.get("/api/match-articles")
    def match_articles():
        return jsonify(match_articles_payload(focus=request.args.get("focus", "")))

    @app.get("/actus/resume/<slug>")
    def match_article_detail(slug: str):
        html, status = match_article_detail_html(slug)
        return Response(html, status=status, content_type="text/html; charset=utf-8")

    @app.get("/actus/resumes")
    def match_articles_archive():
        return Response(match_articles_archive_html(), content_type="text/html; charset=utf-8")

    @app.get("/api/mercato-live")
    def mercato_live():
        return jsonify(_read_json(MERCATO_LIVE_CACHE_FILE, {"items": [], "source": "Mercato Live", "url": "https://www.mercatolive.fr/"}))

    @app.get("/api/leagues-dashboard")
    def leagues_dashboard_cache():
        payload = _read_json(LEAGUES_CACHE_FILE, {"leagues": {}, "big5_top_scorers": [], "errors": []})
        leagues = payload.get("leagues") or {}
        rendered = {
            key: {
                "scorers": len(value.get("top_scorers") or []),
                "assists": len(value.get("top_assists") or []),
                "standings": sum(len(group.get("teams") or group.get("standings") or []) for group in value.get("standings") or []),
                "matches": sum(len(group.get("matches") or []) for group in value.get("group_matches") or []),
            }
            for key, value in leagues.items()
        }
        print(f"[championnats] cache utilisé: leagues={len(leagues)} big5={len(payload.get('big5_top_scorers') or [])} rendered={rendered}", flush=True)
        return jsonify(payload)

    @app.get("/api/football-supabase")
    def football_supabase_data():
        return jsonify(_football_supabase_payload())

    @app.post("/api/football-chatbot")
    def football_chatbot():
        payload = request.get_json(silent=True) or {}
        body, status = football_chatbot_response(payload)
        return jsonify(body), status

    @app.post("/api/coach-prediction")
    def coach_prediction():
        payload = request.get_json(silent=True) or {}
        body, status = coach_prediction_response(payload)
        return jsonify(body), status

    @app.post("/api/search/coach")
    def search_coach():
        payload = request.get_json(silent=True) or {}
        body, status = search_coach_response(payload)
        return jsonify(body), status

    @app.get("/api/coach/messages")
    def coach_messages():
        session_id = _clean(request.args.get("session_id", ""), 120)
        raw_limit = _clean(request.args.get("limit", "12"), 8)
        try:
            limit = min(30, max(1, int(raw_limit or "12")))
        except ValueError:
            limit = 12
        return jsonify({"messages": _coach_messages_from_supabase(session_id, limit) if session_id else []})

    @app.get("/api/admin/sync/logs")
    def admin_sync_logs_route():
        body, status = admin_sync_logs_response()
        return jsonify(body), status

    @app.post("/api/admin/sync/run")
    def admin_sync_run_route():
        payload = request.get_json(silent=True) or {}
        body, status = admin_sync_run_response(payload)
        return jsonify(body), status

    @app.post("/api/admin/sync/cancel")
    def admin_sync_cancel_route():
        payload = request.get_json(silent=True) or {}
        body, status = admin_sync_cancel_response(payload)
        return jsonify(body), status


def football_chatbot_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    question = _clean(payload.get("message", ""), 500)
    history = _chat_history(payload.get("history", []))
    session_id = _clean(payload.get("session_id", ""), 120)
    client_context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    merged_history = history[-20:]
    if session_id:
        merged_history = _chat_history(_coach_messages_from_supabase(session_id, 20) + merged_history)[-20:]
    context_state = _detect_conversation_context(merged_history, question, client_context)
    resolved_question = _resolve_followup_question(question, context_state)
    if not question:
        return {"error": "Question vide."}, 400
    if session_id:
        _save_coach_message_supabase(session_id, "user", question, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
    if not _looks_like_football_question(resolved_question, merged_history):
        return {"answer": COACH_REFUSAL}, 200

    verified_fact = _verified_coach_fact_answer(resolved_question, merged_history)
    if verified_fact:
        answer = _format_coach_answer(verified_fact["answer"])
        verification = verified_fact["verification"]
        if session_id:
            _save_coach_message_supabase(session_id, "assistant", answer, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
        return {
            "answer": answer,
            "detected_context": context_state,
            "resolved_question": resolved_question,
            "verification": verification,
        }, 200

    verification = _coach_verification_context(resolved_question, merged_history)
    local_answer = _local_coach_answer(resolved_question, merged_history)
    if local_answer:
        answer = _format_coach_answer(local_answer)
        verification = _local_coach_verification(verification)
        if session_id:
            _save_coach_message_supabase(session_id, "assistant", answer, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
        return {
            "answer": answer,
            "detected_context": context_state,
            "resolved_question": resolved_question,
            "verification": verification,
        }, 200

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"error": COACH_UNAVAILABLE}, 503

    context = _coach_context_summary()
    coach_data_context = _coach_relevant_supabase_context(resolved_question)
    history_text = _format_chat_history(merged_history)
    try:
        import requests

        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("OPENAI_CHATBOT_MODEL", "gpt-4.1-mini"),
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es Coach, assistant football expert intégré à Akro du Foot. "
                            "Tu réponds en français comme un consultant football moderne : naturel, passionné, clair, précis. "
                            "Tu dois comprendre les relances courtes grâce au contexte précédent (ex: 'nombre de but', 'et en ligue des champions ?'). "
                            "Tes réponses doivent être très lisibles sur mobile : paragraphes courts, sauts de ligne utiles, jamais de gros bloc compact. "
                            "Sépare les idées après les points importants, avec des paragraphes courts de 2 à 3 phrases maximum. "
                            "Si la réponse dépasse quelques lignes, structure-la avec Résumé, Analyse et Conclusion. "
                            "capable d'expliquer simplement l'histoire du foot, les règles, la tactique, les statistiques, le mercato, "
                            "les joueurs actuels et anciens, les clubs, les sélections, le PSG, l'Équipe de France, la Coupe du Monde "
                            "et la Ligue des Champions. Tu peux analyser des matchs et proposer des lectures tactiques utiles. "
                            f"Si la question sort vraiment du football, réponds exactement : {COACH_REFUSAL} "
                            "Avant de répondre sur un joueur, vérifie dans les données locales son club actuel, sa sélection, son effectif et ses statistiques. "
                            "Les données locales Akro du Foot priment sur tes connaissances générales quand elles sont présentes. "
                            "Si l'utilisateur te corrige (ex: 'non il joue au Real Madrid', 'tu te trompes', 'vérifie'), reconnais la correction, vérifie les données locales, puis reprends-toi clairement. "
                            "Quand l'utilisateur dit que ta réponse précédente est fausse, relis l'historique fourni, identifie précisément l'affirmation contestée, reconnais l'erreur et corrige sans te défendre. "
                            "Pour les records, meilleurs buteurs, statistiques joueurs, transferts, classements et compétitions en cours, utilise d'abord le bloc Vérification fourni. "
                            "Si ce bloc indique une vérification limitée, dis-le clairement et évite les certitudes absolues. "
                            "Quand le bloc Données football pertinentes contient des éléments locaux, cite-les brièvement dans une section Données utilisées avant ton analyse. "
                            "Si une donnée manque dans Supabase ou dans le site, dis-le proprement et n'invente jamais un score, un classement, un effectif ou une statistique. "
                            "Ne répète jamais une donnée historique sensible sans préciser si elle vient d'une source vérifiée récemment. "
                            "Pour l'actualité, ne jamais inventer : si aucune donnée récente n'est présente dans le site, réponds exactement : "
                            "Je n'ai pas encore cette information dans les données du site. "
                            "Si une information sportive générale est stable et historique, tu peux répondre avec tes connaissances. "
                            "Ne donne jamais de conseil de pari réel : les pronostics sont uniquement fictifs, entre amis, sans argent."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Contexte détecté: {json.dumps(context_state, ensure_ascii=False)}\n"
                            f"Historique récent:\n{history_text}\n\n"
                            f"Vérification football récente:\n{verification.get('context', '')}\n\n"
                            f"Données football pertinentes ({coach_data_context['source']}):\n{coach_data_context['context'] or 'Aucune donnée Supabase pertinente trouvée pour cette question.'}\n\n"
                            f"Données Akro du Foot disponibles:\n{context}\n\n"
                            f"Question utilisateur résolue:\n{resolved_question}"
                        ),
                    },
                ],
                "temperature": 0.35,
                "max_output_tokens": 700,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            return {"error": COACH_UNAVAILABLE}, 503
        data = response.json()
        answer = _format_coach_answer(_openai_response_text(data))
        if session_id and answer:
            _save_coach_message_supabase(session_id, "assistant", answer, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
        return {
            "answer": answer or COACH_UNAVAILABLE,
            "detected_context": context_state,
            "resolved_question": resolved_question,
            "context_source": coach_data_context["source"],
            "verification": _public_coach_verification(verification),
        }, 200
    except Exception:
        return {"error": COACH_UNAVAILABLE}, 503


def search_coach_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    query = _clean(payload.get("query", ""), 500)
    entity_type = _clean(payload.get("entity_type", ""), 60)
    normalized_query = _normalize_football_text(query)
    if not query or not normalized_query:
        return {"error": "Question vide."}, 400

    if not _looks_like_football_question(query, []):
        return {"answer": COACH_REFUSAL, "source": "refusal", "cached": False}, 200

    live_sensitive = _coach_needs_recent_verification(normalized_query)
    cached = None if live_sensitive else _search_ai_answer_get(normalized_query)
    if cached:
        _search_ai_answer_increment_usage(cached.get("id"))
        return {
            "answer": str(cached.get("answer", "")),
            "source": "supabase",
            "cached": True,
            "normalized_query": normalized_query,
            "entity_type": cached.get("entity_type") or entity_type,
        }, 200

    verified_fact = _verified_coach_fact_answer(query, [])
    if verified_fact:
        answer = _format_coach_answer(verified_fact["answer"])
        if not live_sensitive:
            _search_ai_answer_upsert(query, normalized_query, answer, entity_type)
        return {
            "answer": answer,
            "source": "verified",
            "cached": False,
            "normalized_query": normalized_query,
            "entity_type": entity_type,
            "verification": verified_fact["verification"],
        }, 200

    verification = _coach_verification_context(query, [])
    local_answer = _local_coach_answer(query, [])
    if local_answer:
        answer = _format_coach_answer(local_answer)
        if not live_sensitive:
            _search_ai_answer_upsert(query, normalized_query, answer, entity_type)
        return {
            "answer": answer,
            "source": "local",
            "cached": False,
            "normalized_query": normalized_query,
            "entity_type": entity_type,
            "verification": _local_coach_verification(verification),
        }, 200

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"error": COACH_UNAVAILABLE}, 503

    coach_data_context = _coach_relevant_supabase_context(query)
    try:
        import requests

        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("OPENAI_CHATBOT_MODEL", "gpt-4.1-mini"),
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Tu es Coach Akro du Foot. Réponds en français, court, clair, utile. "
                            "Donne une fiche claire avec résumé, club ou sélection si pertinent, statistiques disponibles, infos importantes. "
                            "Reste 100% football et n'invente pas d'actualité si elle n'est pas dans les données. "
                            "Pour les records, meilleurs buteurs, statistiques, classements et transferts, appuie-toi d'abord sur le bloc Vérification. "
                            "Quand des données locales sont fournies, structure si utile avec Résumé, Données utilisées, Analyse et Conclusion. "
                            "Si la vérification est limitée, signale-le et évite les affirmations catégoriques."
                        ),
                    },
                    {"role": "user", "content": f"Vérification:\n{verification.get('context', '')}\n\nDonnées football pertinentes ({coach_data_context['source']}):\n{coach_data_context['context'] or 'Aucune donnée Supabase pertinente.'}\n\nQuestion:\n{query}"},
                ],
                "temperature": 0.25,
                "max_output_tokens": 700,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            print(f"[search-coach] OpenAI error status={response.status_code}")
            return {"error": COACH_UNAVAILABLE}, 503
        data = response.json()
        answer = _format_coach_answer(_openai_response_text(data)) or COACH_UNAVAILABLE
        if not live_sensitive:
            _search_ai_answer_upsert(query, normalized_query, answer, entity_type)
        return {
            "answer": answer,
            "source": "openai",
            "context_source": coach_data_context["source"],
            "cached": False,
            "normalized_query": normalized_query,
            "entity_type": entity_type,
            "verification": _public_coach_verification(verification),
        }, 200
    except Exception as exc:
        print(f"[search-coach] OpenAI request error: {exc}")
        return {"error": COACH_UNAVAILABLE}, 503


def coach_prediction_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    match_id = _clean(payload.get("match_id", ""), 180)
    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    leagues_dashboard = _read_json(LEAGUES_CACHE_FILE, {})
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard, leagues_dashboard)
    match = matches.get(match_id)
    if not match:
        return _unavailable_prediction("Match introuvable dans les données du site."), 200

    home = str(match.get("home_team") or "")
    away = str(match.get("away_team") or "")
    if not home or not away or "déterminer" in home.casefold() or "déterminer" in away.casefold():
        return _unavailable_prediction("Les équipes ne sont pas encore connues pour ce match."), 200
    if match.get("completed"):
        return {
            "predicted_winner": "Match terminé",
            "predicted_score": _real_score_label(match),
            "confidence": "",
            "reason": "Ce match est déjà terminé : Coach lit le score final plutôt qu'une prédiction après coup.",
            "disclaimer": COACH_DISCLAIMER,
        }, 200

    data_pool = [worldcup_dashboard, champions_dashboard, leagues_dashboard]
    home_data_strength, home_reasons = _team_strength(home, data_pool)
    away_data_strength, away_reasons = _team_strength(away, data_pool)
    home_strength = _baseline_team_strength(home) + home_data_strength + 1.5
    away_strength = _baseline_team_strength(away) + away_data_strength
    diff = home_strength - away_strength

    if abs(diff) < 2.5:
        predicted_winner = "Match équilibré"
        confidence = 54
        predicted_score = "1 - 1"
        reason = _balanced_reason(home, away)
    else:
        winner = home if diff > 0 else away
        predicted_winner = f"{winner} favori"
        confidence = min(73, max(56, int(54 + abs(diff) * 0.85)))
        predicted_score = _probable_score(diff)
        if diff < 0:
            predicted_score = " - ".join(reversed(predicted_score.split(" - ")))
        reasons = home_reasons if diff > 0 else away_reasons
        reason = reasons[0] if reasons else _reputation_reason(winner, home, away, match.get("competition", ""))

    return {
        "predicted_winner": predicted_winner,
        "predicted_score": predicted_score,
        "confidence": confidence,
        "reason": reason,
        "disclaimer": COACH_DISCLAIMER,
    }, 200


def _unavailable_prediction(reason: str) -> dict[str, Any]:
    return {
        "predicted_winner": "Analyse impossible",
        "predicted_score": "",
        "confidence": "",
        "reason": reason,
        "disclaimer": COACH_DISCLAIMER,
    }


def _baseline_team_strength(team_name: str) -> float:
    key = _team_key(team_name)
    ratings = {
        "realmadrid": 92, "parissaintgermain": 89, "psg": 89, "manchestercity": 90, "bayernmunich": 90,
        "bayernmunchen": 90, "barcelona": 88, "fcbarcelona": 88, "arsenal": 87, "liverpool": 88,
        "inter": 86, "internazionale": 86, "juventus": 83, "chelsea": 84, "atleticomadrid": 84,
        "borussiadortmund": 82, "benfica": 79, "napoli": 81, "marseille": 76, "asmonaco": 76,
        "france": 91, "brazil": 91, "bresil": 91, "argentina": 90, "argentine": 90, "england": 88,
        "angleterre": 88, "spain": 88, "espagne": 88, "germany": 87, "allemagne": 87, "portugal": 87,
        "netherlands": 85, "paysbas": 85, "belgium": 83, "belgique": 83, "uruguay": 82, "croatia": 82,
        "croatie": 82, "mexico": 78, "mexique": 78, "senegal": 78, "maroc": 80, "morocco": 80,
        "switzerland": 80, "suisse": 80, "japan": 78, "japon": 78, "usa": 77, "unitedstates": 77,
        "canada": 75, "southafrica": 70, "afriquedusud": 70, "qatar": 70, "saudiarabia": 71,
        "tunisia": 72, "tunisie": 72, "egypt": 74, "egypte": 74, "australia": 74, "australie": 74,
        "turkiye": 76, "turkey": 76, "czechia": 75, "republiquetcheque": 75, "bosniaherzegovina": 73,
        "bosnieherzegovine": 73, "haiti": 68, "scotland": 75, "ecosse": 75, "paraguay": 75,
        "colombia": 80, "colombie": 80, "ghana": 74, "ecuador": 77, "equateur": 77,
    }
    return float(ratings.get(key, 74))


def _probable_score(diff: float) -> str:
    margin = abs(diff)
    if margin >= 14:
        return "2 - 0"
    if margin >= 8:
        return "2 - 1"
    return "1 - 0"


def _balanced_reason(home: str, away: str) -> str:
    return f"{home} et {away} semblent proches sur le papier : match serré, où le rythme, les transitions et l'efficacité dans les deux surfaces peuvent tout changer."


def _reputation_reason(winner: str, home: str, away: str, competition: str) -> str:
    if competition == "Ligue des Champions":
        return f"{winner} a un léger avantage sur la réputation européenne, la densité d'effectif et l'expérience des grands rendez-vous."
    return f"{winner} part avec un avantage lié au niveau global estimé, à l'expérience internationale et au potentiel offensif."


def _real_score_label(match: dict[str, Any]) -> str:
    home_score = match.get("home_score", "")
    away_score = match.get("away_score", "")
    return f"{home_score} - {away_score}" if home_score != "" and away_score != "" else "Score final non disponible"


def _coach_context_summary() -> str:
    worldcup = _read_json(CACHE_FILE, {})
    champions = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    leagues = _read_json(LEAGUES_CACHE_FILE, {})
    community = _read_community()
    chunks = [
        _competition_summary("Coupe du Monde", worldcup),
        _competition_summary("Ligue des Champions", champions),
        _leagues_context_summary(leagues),
    ]
    chunks.append(_player_index_summary(worldcup, champions))
    leaderboard = _leaderboard(_predictions_with_points(community.get("predictions", []), _all_dashboard_matches(worldcup, champions, leagues)))[:5]
    if leaderboard:
        chunks.append("Classement pronostics: " + "; ".join(f"{row['pseudo']} {row['points']} pts" for row in leaderboard))
    else:
        chunks.append("Classement pronostics: aucune donnée publiée.")
    return "\n".join(chunk for chunk in chunks if chunk).strip()[:6000]


def _verified_coach_fact_answer(question: str, history: list[dict[str, str]]) -> dict[str, Any] | None:
    normalized = _normalize_football_text(question)
    recent = _recent_history_text(history)
    combined = f"{recent} {normalized}"
    asks_france_top_scorer = (
        ("france" in combined or "equipe de france" in combined)
        and any(term in combined for term in {"meilleur buteur", "buteur historique", "record de buts", "plus de buts"})
        and any(term in combined for term in {"selection", "equipe", "historique", "france", "bleus", "buteur"})
    )
    correcting_top_scorer = _is_correction_message(normalized) and any(
        term in recent for term in {"thierry henry", "olivier giroud", "mbappe", "meilleur buteur", "buteur historique"}
    )
    if not (asks_france_top_scorer or correcting_top_scorer):
        return None

    prefix = "Tu as raison, je corrige mon erreur." if _is_correction_message(normalized) else "Résumé :"
    answer = (
        f"{prefix} Le meilleur buteur historique de l'équipe de France est Olivier Giroud avec 57 buts. "
        "Kylian Mbappé est juste derrière avec 56 buts, devant Thierry Henry qui est à 51.\n\n"
        "Analyse : l'ancienne réponse avec Thierry Henry était dépassée. Henry a longtemps été la référence, "
        "mais Giroud l'a dépassé, et Mbappé est désormais au contact.\n\n"
        f"Vérification : donnée prioritaire Coach vérifiée le {COACH_FACTS_LAST_VERIFIED}. "
        "À recontrôler après chaque rassemblement international."
    )
    verification = {
        "status": "verified",
        "label": "Vérifié",
        "confidence": 96,
        "checked_at": COACH_FACTS_LAST_VERIFIED,
        "sources": ["Wikipedia", "référence football historique Akro"],
        "freshness": "record sensible, à revérifier après chaque match international",
        "context": (
            "Fait vérifié prioritaire: meilleur buteur historique de l'équipe de France = Olivier Giroud 57 buts; "
            "Kylian Mbappé 56; Thierry Henry 51. Dernière vérification: "
            f"{COACH_FACTS_LAST_VERIFIED}."
        ),
    }
    return {"answer": answer, "verification": verification}


def _coach_needs_recent_verification(normalized_question: str) -> bool:
    sensitive_terms = {
        "record", "records", "meilleur", "meilleurs", "buteur", "buteurs", "historique",
        "stat", "stats", "statistique", "statistiques", "classement", "transfert",
        "mercato", "actuel", "actuelle", "aujourd hui", "cette saison", "buts", "passes",
        "selection", "sélection", "competition", "compétition",
    }
    return any(term in normalized_question for term in sensitive_terms)


def _coach_verification_context(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    normalized = _normalize_football_text(question)
    freshness = _dashboard_freshness_summary()
    if not _coach_needs_recent_verification(normalized):
        return {
            "status": "not_required",
            "label": "Contexte",
            "confidence": 72,
            "checked_at": datetime.now(timezone.utc).date().isoformat(),
            "sources": ["Données locales Akro"],
            "freshness": freshness,
            "context": f"Vérification live non nécessaire pour cette question. Fraîcheur locale: {freshness}.",
        }

    snippets = _wikipedia_verification_snippets(question)
    api_football_note = _api_football_availability_note()
    if snippets:
        return {
            "status": "verified",
            "label": "Vérifié",
            "confidence": 86,
            "checked_at": datetime.now(timezone.utc).date().isoformat(),
            "sources": ["Wikipedia", *([api_football_note] if api_football_note.startswith("API Football") else [])],
            "freshness": freshness,
            "context": (
                f"Sources prioritaires prévues: {', '.join(COACH_VERIFICATION_SOURCES)}. "
                "Sources consultées pour cette réponse: Wikipedia. "
                f"{api_football_note} "
                f"Fraîcheur locale: {freshness}. "
                "Extraits de vérification:\n- " + "\n- ".join(snippets[:4])
            ),
        }
    return {
        "status": "limited",
        "label": "À vérifier",
        "confidence": 48,
        "checked_at": datetime.now(timezone.utc).date().isoformat(),
        "sources": ["Données locales Akro"],
        "freshness": freshness,
        "context": (
            "Vérification externe non disponible depuis le serveur pour cette requête. "
            f"Sources prioritaires prévues: {', '.join(COACH_VERIFICATION_SOURCES)}. "
            f"{api_football_note} "
            f"Fraîcheur locale: {freshness}. "
            "Le Coach doit éviter les certitudes sur records, transferts, classements et statistiques récentes."
        ),
    }


def _wikipedia_verification_snippets(question: str) -> list[str]:
    try:
        import requests

        search_query = _wikipedia_query_for_question(question)
        cache_key = _normalize_football_text(search_query)
        cached = WIKIPEDIA_VERIFICATION_CACHE.get(cache_key)
        if cached and time.time() - cached[0] <= WIKIPEDIA_VERIFICATION_CACHE_TTL:
            print("[coach] cache Wikipedia utilisé", flush=True)
            return cached[1]
        snippets: list[str] = []
        for language in ("fr", "en"):
            print(f"[coach] fallback vérification Wikipedia appelé: {language}", flush=True)
            response = requests.get(
                f"https://{language}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": search_query,
                    "srlimit": 3,
                    "format": "json",
                    "utf8": 1,
                },
                headers={"User-Agent": "AkroDuFootCoach/1.0"},
                timeout=4,
            )
            if response.status_code >= 400:
                continue
            for item in response.json().get("query", {}).get("search", [])[:3]:
                title = re.sub(r"\s+", " ", str(item.get("title", "")).strip())
                snippet = re.sub("<[^>]+>", "", str(item.get("snippet", "")))
                snippet = re.sub(r"\s+", " ", snippet).strip()
                if title and snippet:
                    snippets.append(f"{title}: {snippet}")
            if snippets:
                break
        snippets = snippets[:4]
        WIKIPEDIA_VERIFICATION_CACHE[cache_key] = (time.time(), snippets)
        return snippets
    except Exception:
        return []


def _wikipedia_query_for_question(question: str) -> str:
    normalized = _normalize_football_text(question)
    if "france" in normalized and any(term in normalized for term in {"buteur", "meilleur buteur", "buts"}):
        return "France national football team top scorers Olivier Giroud Kylian Mbappe Thierry Henry"
    if "mbappe" in normalized:
        return "Kylian Mbappe football statistics"
    if "giroud" in normalized:
        return "Olivier Giroud France top scorer"
    return f"{question} football"


def _api_football_availability_note() -> str:
    return "API Football disponible." if os.environ.get("API_FOOTBALL_KEY", "").strip() else "API Football non configurée."


def _dashboard_freshness_summary() -> str:
    items = []
    for label, path in (
        ("Coupe du Monde", CACHE_FILE),
        ("Ligue des Champions", CHAMPIONS_LEAGUE_CACHE_FILE),
        ("Championnats", LEAGUES_CACHE_FILE),
        ("Mercato", MERCATO_LIVE_CACHE_FILE),
        ("News", NEWS_CACHE_FILE),
    ):
        generated_at = (_read_json(path, {}) or {}).get("generated_at")
        items.append(f"{label}: {_freshness_label(generated_at)}")
    return "; ".join(items)


def _freshness_label(value: Any) -> str:
    if not value:
        return "date inconnue"
    raw = str(value)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        age_hours = max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600)
        if age_hours < 6:
            return f"{raw} (récent)"
        if age_hours < 48:
            return f"{raw} ({int(age_hours)}h)"
        return f"{raw} (ancien, à vérifier)"
    except ValueError:
        return raw


def _local_coach_verification(base: dict[str, Any]) -> dict[str, Any]:
    if base.get("status") == "verified":
        return _public_coach_verification(base)
    return _public_coach_verification({
        **base,
        "status": "local",
        "label": "Local",
        "confidence": min(int(base.get("confidence") or 64), 64),
        "sources": ["Données locales Akro"],
    })


def _public_coach_verification(verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(verification.get("status", "")),
        "label": str(verification.get("label", "")),
        "confidence": int(verification.get("confidence") or 0),
        "checked_at": str(verification.get("checked_at", "")),
        "sources": [str(item) for item in verification.get("sources", []) if item],
        "freshness": str(verification.get("freshness", "")),
    }


def _leagues_context_summary(data: dict[str, Any]) -> str:
    leagues = (data or {}).get("leagues", {})
    if not leagues:
        return "Championnats: données non disponibles."
    lines = ["Championnats européens:"]
    for key, league in list(leagues.items())[:5]:
        matches = list(_dashboard_matches(league).values())
        upcoming = sorted([match for match in matches if not match.get("completed")], key=lambda item: str(item.get("date", "")))[:3]
        lines.append(f"{league.get('name', key)} prochains matchs: " + (_format_match_list(upcoming) if upcoming else "aucun match publié."))
        lines.append(f"{league.get('name', key)} classement: " + _standings_summary(league.get("standings", [])[:1]))
    return "\n".join(lines)


def _competition_summary(name: str, data: dict[str, Any]) -> str:
    if not data:
        return f"{name}: données non disponibles."
    lines = [
        f"{name}: {data.get('competition', name)}",
        f"Dernière mise à jour: {data.get('generated_at', 'non disponible')}",
        f"Phase: {data.get('competition_stage', 'non disponible')}",
    ]
    matches = list(_dashboard_matches(data).values())
    today = [match for match in matches if _is_today_iso(match.get("date", ""))]
    upcoming = sorted([match for match in matches if not match.get("completed")], key=lambda item: str(item.get("date", "")))[:5]
    lines.append("Matchs du jour: " + (_format_match_list(today[:5]) if today else "aucun match aujourd'hui."))
    lines.append("Prochains matchs: " + (_format_match_list(upcoming) if upcoming else "aucun match à venir publié."))
    lines.append("Classements: " + _standings_summary(data.get("standings", [])[:2]))
    lines.append("Buteurs: " + _players_summary(data.get("top_scorers", [])[:5], "buts"))
    lines.append("Passeurs: " + _players_summary(data.get("top_assists", [])[:5], "passes"))
    news = (data.get("world_cup_news") or data.get("news") or [])[:3]
    if data.get("france_news"):
        news += data.get("france_news", [])[:2]
    lines.append("Actualités: " + _news_summary(news[:3]))
    return "\n".join(lines)


def _format_match_list(matches: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{match.get('home_team', 'À déterminer')} vs {match.get('away_team', 'À déterminer')} ({match.get('date', 'date inconnue')}, {match.get('status', 'statut inconnu')})"
        for match in matches
    )


def _standings_summary(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return "non publiés."
    parts: list[str] = []
    for group in groups:
        teams = group.get("teams") or group.get("standings") or []
        team_bits = []
        for team in teams[:4]:
            name = team.get("team") or team.get("name") or team.get("team_name") or "Équipe"
            pts = team.get("points", team.get("pts", "?"))
            team_bits.append(f"{name} {pts} pts")
        if team_bits:
            parts.append(f"{group.get('name', 'Groupe')}: " + ", ".join(team_bits))
    return "; ".join(parts) if parts else "non publiés."


def _players_summary(players: list[dict[str, Any]], label: str) -> str:
    if not players:
        return "non publiés."
    return "; ".join(f"{player.get('name', 'Joueur')} {player.get('value', 0)} {label}" for player in players)


def _news_summary(news: list[dict[str, Any]]) -> str:
    if not news:
        return "aucune actualité disponible."
    return "; ".join(f"{item.get('source', 'Source')} - {item.get('title', 'Sans titre')}" for item in news[:3])


def _is_today_iso(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.astimezone().date() == datetime.now().astimezone().date()


def _team_strength(team_name: str, dashboards: list[dict[str, Any]]) -> tuple[float, list[str]]:
    key = _team_key(team_name)
    score = 0.0
    reasons: list[str] = []
    for data in dashboards:
        for group in data.get("standings", []):
            teams = group.get("teams") or group.get("standings") or []
            for row in teams:
                name = row.get("team") or row.get("name") or row.get("team_name") or ""
                if _team_key(name) == key:
                    points = _number(row.get("points", row.get("pts")))
                    goal_diff = _number(row.get("goal_difference", row.get("gd", row.get("diff"))))
                    score += points * 0.7 + goal_diff * 0.2
                    reasons.append(f"{team_name} ressort mieux dans le classement disponible ({points:g} pts, différence {goal_diff:g}).")
        for player in (data.get("top_scorers", []) + data.get("top_assists", [])):
            player_team = player.get("team") or player.get("country") or ""
            if _team_key(player_team) == key:
                value = _number(player.get("value"))
                score += 1.0 + min(value, 10) * 0.15
                reasons.append(f"{team_name} a un joueur en vue dans les statistiques offensives publiées.")
        details = data.get("teams_details", {}).get(team_name, {})
        # Les fiches effectif ne sont plus affichées : on ne s'en sert pas comme argument visible.
    return score, reasons


def _team_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def _chat_history(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value[-20:]:
        if not isinstance(item, dict):
            continue
        role = _clean(item.get("role", ""), 16)
        content = _clean(item.get("content", ""), 500)
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def _format_chat_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "Aucun historique récent."
    return "\n".join(f"{item['role']}: {item['content']}" for item in history[-20:])


def _detect_conversation_context(history: list[dict[str, str]], question: str, client_context: dict[str, Any]) -> dict[str, str]:
    history_text = _normalize_football_text(" ".join(item.get("content", "") for item in history[-10:]))
    text = _normalize_football_text(history_text + " " + question)
    qn = _normalize_football_text(question)
    entity = str(client_context.get("lastEntity", "") or "")
    entity_type = str(client_context.get("lastEntityType", "") or "")
    competition = str(client_context.get("lastCompetition", "") or "")
    season = str(client_context.get("lastSeason", "") or "")
    intent = str(client_context.get("lastIntent", "") or "")
    comparison_entity = str(client_context.get("lastComparisonEntity", "") or "")

    players = {"mbappe": "Kylian Mbappé", "kylian mbappe": "Kylian Mbappé", "messi": "Lionel Messi", "ronaldo": "Cristiano Ronaldo", "cristiano ronaldo": "Cristiano Ronaldo", "haaland": "Erling Haaland", "erling haaland": "Erling Haaland", "neymar": "Neymar", "benzema": "Karim Benzema"}
    clubs = {"psg": "PSG", "paris saint germain": "PSG", "om": "OM", "marseille": "OM", "real madrid": "Real Madrid", "barca": "Barcelona", "barcelona": "Barcelona", "manchester city": "Manchester City"}
    competitions = {"ligue des champions": "Ligue des Champions", "champions league": "Ligue des Champions", "coupe du monde": "Coupe du Monde", "euro": "Euro", "ligue 1": "Ligue 1", "ballon d or": "Ballon d'Or"}

    current_player = ""
    for key, value in players.items():
        if _normalized_contains(qn, key):
            current_player = value
        elif not entity and _normalized_contains(history_text, key):
            entity, entity_type = value, "player"

    if current_player:
        if any(term in qn for term in {"compare", "compar", "versus", "vs", "avec"}) and entity and current_player != entity:
            comparison_entity = current_player
            intent = "compare"
        else:
            entity, entity_type = current_player, "player"

    for key, value in clubs.items():
        if _normalized_contains(qn, key) or (not entity and _normalized_contains(text, key)):
            entity, entity_type = value, "club"
    for key, value in competitions.items():
        if _normalized_contains(qn, key) or (not competition and _normalized_contains(text, key)):
            competition = value

    if any(term in qn for term in {"nombre de but", "but", "buts"}):
        intent = "goals"
    elif any(term in qn for term in {"passe", "passes", "assist"}):
        intent = "assists"
    elif any(term in qn for term in {"compare", "compar"}):
        intent = "compare"
    elif any(term in qn for term in {"club", "son club", "ou joue"}):
        intent = "club"
    elif any(term in qn for term in {"selection", "sélection", "nation", "sa selection"}):
        intent = "national_team"
    elif "stats" in qn or "stat" in qn:
        intent = "stats"

    if "cette saison" in qn:
        season = "cette saison"
    elif any(year in question for year in {"2024", "2025", "2026"}):
        for year in ("2026", "2025", "2024"):
            if year in question:
                season = year
                break

    return {
        "lastEntity": entity,
        "lastEntityType": entity_type,
        "lastCompetition": competition,
        "lastSeason": season,
        "lastIntent": intent,
        "lastComparisonEntity": comparison_entity,
    }


def _resolve_followup_question(question: str, context_state: dict[str, str]) -> str:
    qn = _normalize_football_text(question)
    ambiguous = len(qn.split()) <= 5 or any(term in qn for term in {"et en", "cette saison", "son club", "sa selection", "sa sélection", "nombre de but", "compare avec", "et lui", "ses buts", "sa stat"})
    if not ambiguous:
        return question
    parts = []
    if context_state.get("lastEntity"):
        parts.append(f"sujet={context_state['lastEntity']}")
    if context_state.get("lastComparisonEntity"):
        parts.append(f"comparaison={context_state['lastComparisonEntity']}")
    if context_state.get("lastCompetition"):
        parts.append(f"compétition={context_state['lastCompetition']}")
    if context_state.get("lastSeason"):
        parts.append(f"saison={context_state['lastSeason']}")
    if context_state.get("lastIntent"):
        parts.append(f"intention={context_state['lastIntent']}")
    if not parts:
        return question
    return f"{question} (contexte conversationnel: {', '.join(parts)})"


def _normalized_contains(text: str, phrase: str) -> bool:
    normalized_phrase = _normalize_football_text(phrase)
    if not normalized_phrase:
        return False
    return re.search(rf"(^|\s){re.escape(normalized_phrase)}($|\s)", text) is not None


def _is_correction_message(normalized_text: str) -> bool:
    correction_terms = {
        "tu te trompes", "c est faux", "ce nest pas vrai", "ce n est pas vrai", "non", "pas vrai",
        "verifie", "verifie ca", "corrige", "correction", "il joue au", "elle joue au",
        "il joue a", "elle joue a", "joue pour", "il est au", "elle est au", "il est a",
        "elle est a", "il a signe", "elle a signe", "il a rejoint", "elle a rejoint",
    }
    return any(term in normalized_text for term in correction_terms)


def _local_coach_answer(question: str, history: list[dict[str, str]]) -> str:
    normalized = _normalize_football_text(question)
    recent = _recent_history_text(history)
    if any(term in normalized for term in {"compare", "comparaison", "versus", "vs", "plus fort", "meilleur"}) and len(_coach_detect_player_names(question)) >= 2:
        stats_context = _coach_player_stats_context(question)
        if stats_context:
            age = _coach_detect_age(question)
            age_text = f" à âge équivalent ({age} ans)" if age else ""
            return (
                f"Résumé : je peux comparer ces joueurs{age_text} avec les données disponibles dans Akro/Supabase.\n\n"
                f"Données utilisées :\n{stats_context}\n\n"
                "Analyse : les chiffres ci-dessus donnent la base objective. Pour départager proprement, il faut ensuite pondérer le contexte : rôle exact, championnat, niveau de l’équipe, compétition européenne, sélection et titres disponibles dans la période.\n\n"
                "Conclusion : si une ligne indique que la statistique détaillée est absente, je ne l’invente pas. Elle pourra être enrichie via API-Football puis conservée en base pour les prochaines questions."
            )
    supabase_answer = _supabase_local_answer(normalized)
    if supabase_answer:
        return supabase_answer
    if _is_correction_message(normalized):
        if "mbappe" in recent or "mbappe" in normalized:
            player = _find_player_fact("mbappe")
            club = player.get("club_current") if player else "Real Madrid"
            return (
                f"Résumé : tu as raison, Mbappé joue au {club or 'Real Madrid'}."
                "\n\nAnalyse : je corrige mon erreur précédente, il a quitté le PSG et évolue désormais au Real Madrid."
                "\n\nConclusion : merci pour la correction, je m'aligne sur cette information."
            )
        return (
            "Résumé : tu as raison de me reprendre."
            "\n\nAnalyse : je dois vérifier cette information, mes données locales ne sont peut-être pas à jour."
        )

    if any(term in normalized for term in {"qui entraine", "entraineur", "coach", "selectionneur"}):
        team = _find_team_fact(normalized)
        if team:
            coach = team.get("coach")
            name = team.get("name") or team.get("original_name") or "cette équipe"
            source = ", ".join(team.get("sources", [])) if isinstance(team.get("sources"), list) else str(team.get("sources", ""))
            if coach:
                return f"Résumé : {name} est entraîné par {coach}.\n\nSource locale : {source or 'données Akro du Foot'}."
        return "Je dois vérifier cette information, mes données locales ne sont peut-être pas à jour."

    player = _find_player_fact(normalized)
    asks_goals = any(term in normalized for term in {"nombre de but", "combien de but", "combien de buts", "buts", "but"})
    if player and asks_goals:
        name = player.get("name") or "ce joueur"
        source = player.get("source") or "données locales Akro du Foot"
        goals = player.get("goals") or player.get("goals_total") or player.get("season_goals")
        if goals not in (None, ""):
            return (
                f"Résumé : pour {name}, tu veux sûrement parler de son nombre de buts. Il a marqué {goals} buts selon les données locales."
                f"\n\nSource locale : {source}."
            )
        return (
            f"Résumé : pour {name}, tu veux sûrement parler de son nombre de buts. Je n'ai pas le total exact dans les données locales actuelles."
            "\n\nAnalyse : je peux quand même te situer le contexte avec les infos disponibles : club, sélection et compétition si elle est mentionnée. Pour un total exact, il faut préciser la saison ou la compétition, ou lancer une recherche plus précise."
        )
    if player and any(term in normalized for term in {"selection", "sa selection", "nation", "pays"}):
        country = player.get("country")
        source = player.get("source") or "données locales Akro du Foot"
        if country:
            return f"Résumé : {player.get('name')} représente {country} en sélection.\n\nSource locale : {source}."
        return f"Résumé : je n'ai pas la sélection exacte de {player.get('name') or 'ce joueur'} dans les données locales actuelles."
    if player and any(term in normalized for term in {"stats", "statistique", "statistiques"}):
        bits = []
        if player.get("club_current"):
            bits.append(f"club actuel : {player['club_current']}")
        if player.get("country"):
            bits.append(f"sélection : {player['country']}")
        if player.get("position"):
            bits.append(f"poste : {player['position']}")
        source = player.get("source") or "données locales Akro du Foot"
        detail = "; ".join(bits) if bits else "les statistiques détaillées ne sont pas disponibles localement."
        return f"Résumé : {player.get('name') or 'ce joueur'} - {detail}.\n\nAnalyse : les totaux exacts de buts/passes peuvent dépendre de la saison et de la compétition demandées.\n\nSource locale : {source}."
    if "intention compare" in normalized or "comparaison" in normalized or any(term in normalized for term in {"compare avec", "comparer avec"}):
        comparison = ""
        match = re.search(r"comparaison ([a-z0-9 ]+?)(?: competition| saison| intention|$)", normalized)
        if match:
            comparison = match.group(1).strip()
        if player:
            other = f" avec {comparison.title()}" if comparison else " avec l'autre joueur mentionné"
            return (
                f"Résumé : je peux comparer {player.get('name')}{other}, mais les données locales ne contiennent pas assez de statistiques exactes pour une comparaison chiffrée complète."
                "\n\nAnalyse : je peux comparer le profil, le poste, le club, la sélection et les compétitions si tu veux une lecture qualitative."
            )
    if player and any(term in normalized for term in {"ou joue", "club", "joue", "evolue", "mbappe", "pele"}):
        club = player.get("club_current") or player.get("associated_team")
        country = player.get("country")
        source = player.get("source") or "données locales Akro du Foot"
        if club:
            if club == "retraité":
                return (
                    f"Résumé : {player.get('name')} ne joue plus, il est retraité."
                    f"\n\nAnalyse : il reste associé au {country or 'football brésilien'} dans les données football historiques."
                    f"\n\nSource locale : {source}."
                )
            details = f"{player.get('name')} évolue actuellement à {club}"
            if country:
                details += f" et représente {country}"
            return f"Résumé : {details}.\n\nSource locale : {source}."
        return "Je dois vérifier cette information, mes données locales ne sont peut-être pas à jour."
    return ""


def _find_team_fact(normalized_question: str) -> dict[str, Any] | None:
    dashboards = (_read_json(CACHE_FILE, {}), _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {}))
    aliases = {
        "psg": {"psg", "paris saint germain", "paris sg"},
        "real madrid": {"real madrid"},
        "france": {"france", "equipe de france"},
    }
    targets = []
    for canonical, values in aliases.items():
        if any(alias in normalized_question for alias in values):
            targets.append(canonical)
    for data in dashboards:
        for name, details in data.get("teams_details", {}).items():
            name_key = _normalize_football_text(name)
            detail_name_key = _normalize_football_text(details.get("name", ""))
            if any(target in {name_key, detail_name_key} or target in name_key for target in targets):
                return details
    return None


def _recent_history_text(history: list[dict[str, str]]) -> str:
    return _normalize_football_text(" ".join(item.get("content", "") for item in history[-6:]))


def _find_player_fact(normalized_question: str) -> dict[str, Any] | None:
    dashboards = (_read_json(CACHE_FILE, {}), _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {}))
    aliases = {
        "mbappe": "kylian mbappe",
        "kylian mbappe": "kylian mbappe",
        "haaland": "erling haaland",
        "erling haaland": "erling haaland",
        "messi": "lionel messi",
        "lionel messi": "lionel messi",
        "cristiano ronaldo": "cristiano ronaldo",
        "ronaldo": "cristiano ronaldo",
        "pele": "pele",
    }
    target = ""
    for alias, canonical in aliases.items():
        if alias in normalized_question:
            target = canonical
            break
    for data in dashboards:
        for player in data.get("players_index", []):
            name_key = _normalize_football_text(player.get("name", ""))
            if target and target in name_key:
                return player
            if name_key and name_key in normalized_question:
                return player
    if "mbappe" in normalized_question:
        return {
            "name": "Kylian Mbappé",
            "club_current": "Real Madrid",
            "country": "France",
            "position": "Attaquant",
            "source": "référence locale Akro du Foot",
        }
    if "pele" in normalized_question:
        return {"name": "Pelé", "club_current": "retraité", "country": "Brésil", "source": "connaissance football historique"}
    if "haaland" in normalized_question:
        return {"name": "Erling Haaland", "club_current": "Manchester City", "country": "Norvège", "position": "Avant-centre", "source": "référence locale Akro du Foot"}
    if "messi" in normalized_question:
        return {"name": "Lionel Messi", "club_current": "Inter Miami", "country": "Argentine", "position": "Attaquant", "source": "référence locale Akro du Foot"}
    if "ronaldo" in normalized_question:
        return {"name": "Cristiano Ronaldo", "club_current": "Al-Nassr", "country": "Portugal", "position": "Attaquant", "source": "référence locale Akro du Foot"}
    return None


def _player_index_summary(worldcup: dict[str, Any], champions: dict[str, Any]) -> str:
    players = _merge_player_indexes(worldcup.get("players_index", []), champions.get("players_index", []))
    if not players:
        return "Index joueurs: aucune donnée locale disponible."
    priority_names = {"kylian mbappe", "kylian mbappé", "harry kane", "michael olise", "achraf hakimi", "lionel messi"}
    priority = [player for player in players if _normalize_football_text(player.get("name", "")) in {_normalize_football_text(name) for name in priority_names}]
    sample = priority or players[:12]
    rows = []
    for player in sample[:18]:
        bits = [str(player.get("name", ""))]
        if player.get("club_current"):
            bits.append(f"club actuel: {player['club_current']}")
        if player.get("country"):
            bits.append(f"pays/sélection: {player['country']}")
        if player.get("position"):
            bits.append(f"poste: {player['position']}")
        if player.get("source"):
            bits.append(f"source: {player['source']}")
        rows.append(" | ".join(bits))
    return "Index joueurs local: " + "; ".join(rows)


def _merge_player_indexes(*indexes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for index in indexes:
        for player in index or []:
            key = _normalize_football_text(player.get("name", ""))
            if not key:
                continue
            current = merged.setdefault(key, dict(player))
            for field, value in player.items():
                if value and not current.get(field):
                    current[field] = value
    return sorted(merged.values(), key=lambda item: str(item.get("name", "")).casefold())


def _format_coach_answer(text: str) -> str:
    original = str(text or "").strip()
    if not original:
        return ""
    if "\n" in original:
        return original
    clean = " ".join(original.split())
    labels = ("Résumé :", "Analyse :", "Conclusion :", "Source locale :")
    for label in labels:
        clean = clean.replace(f" {label}", f"\n\n{label}")
    if len(clean) < 260:
        return clean
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    paragraphs: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        current.append(sentence)
        if len(" ".join(current)) >= 180:
            paragraphs.append(" ".join(current).strip())
            current = []
    if current:
        paragraphs.append(" ".join(current).strip())
    return "\n\n".join(paragraphs)


def _openai_response_text(data: dict[str, Any]) -> str:
    text = data.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts: list[str] = []
    for item in data.get("output", []) if isinstance(data.get("output"), list) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                value = content.get("text")
                if isinstance(value, str):
                    parts.append(value)
    return "\n".join(part.strip() for part in parts if part.strip()).strip()


def _looks_like_football_question(question: str, history: list[dict[str, str]] | None = None) -> bool:
    text = _normalize_football_text(question)
    if not text:
        return False
    if _is_correction_message(text):
        return True
    keywords = {
        "football", "foot", "soccer", "fifa", "uefa", "ballon", "ballon d'or", "but", "buts",
        "match", "matches", "joueur", "joueurs", "club", "clubs", "selection", "selectionneur",
        "equipe", "equipes", "coach", "entraineur", "manager", "gardien", "defenseur", "milieu",
        "attaquant", "ailier", "avant centre", "capitaine", "stade", "carton", "penalty", "penalties",
        "hors jeu", "var", "arbitre", "classement", "calendrier", "resultat", "score", "finale",
        "demi finale", "quart", "huitieme", "seizieme", "mercato", "transfert", "tactique",
        "formation", "possession", "pressing", "contre attaque", "xg", "statistique", "palmares",
        "coupe du monde", "mondial", "ligue des champions", "champions league", "euro", "can",
        "copa america", "ligue 1", "premier league", "liga", "serie a", "bundesliga", "mls",
        "pronostic", "favori", "nul", "victoire", "defaite", "joue", "jouer", "club actuel",
        "effectif", "composition", "compo", "selection", "selection nationale", "transfert", "verifie",
        "corrige", "erreur", "tu te trompes", "pas vrai", "actualite", "actu", "rumeur",
    }
    names = {
        "pele", "maradona", "zidane", "messi", "cristiano ronaldo", "ronaldo", "ronaldinho",
        "mbappe", "kylian mbappe", "haaland", "neymar", "benzema", "griezmann", "platini",
        "henry", "thierry henry", "deschamps", "didier deschamps", "luis enrique", "ancelotti",
        "guardiola", "mourinho", "klopp", "xavi", "iniesta", "modric", "kroos", "bellingham",
        "vinicius", "yamal", "dembele", "olise", "kane", "salah", "lewandowski", "buffon",
        "casillas", "beckenbauer", "cruyff", "eusebio", "klose", "platini",
        "psg", "paris saint germain", "paris saintgermain", "real madrid", "barca", "barcelone",
        "fc barcelona", "bayern", "bayern munich", "arsenal", "chelsea", "liverpool", "manchester city",
        "manchester united", "juventus", "milan", "inter", "internazionale", "dortmund", "atletico",
        "france", "bresil", "argentine", "allemagne", "espagne", "portugal", "angleterre", "italie",
        "senegal", "maroc", "mexico", "mexique",
    }
    if any(term in text for term in keywords | names):
        return True
    if _known_football_entity_in_question(text):
        return True
    if history and any(_looks_like_football_question(item.get("content", ""), []) for item in history[-4:]):
        return _is_correction_message(text) or any(word in text for word in {"non", "si", "faux", "verifie", "corrige"})
    return False


def _known_football_entity_in_question(normalized_question: str) -> bool:
    if len(normalized_question) < 3:
        return False
    for data in (_read_json(CACHE_FILE, {}), _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})):
        for name in _football_entities_from_dashboard(data):
            normalized = _normalize_football_text(name)
            if len(normalized) >= 4 and normalized in normalized_question:
                return True
    return False


def _football_entities_from_dashboard(data: dict[str, Any]) -> set[str]:
    entities: set[str] = set()
    for match in _dashboard_matches(data).values():
        entities.add(str(match.get("home_team", "")))
        entities.add(str(match.get("away_team", "")))
    for group in data.get("standings", []):
        for row in group.get("teams", []) or group.get("standings", []) or []:
            entities.add(str(row.get("team") or row.get("name") or row.get("team_name") or ""))
    for player in data.get("top_scorers", []) + data.get("top_assists", []) + data.get("all_time_top_scorers", []) + data.get("players_index", []):
        entities.add(str(player.get("name", "")))
        entities.add(str(player.get("team", "")))
        entities.add(str(player.get("club_current", "")))
        entities.add(str(player.get("country", "")))
    for team_name, details in data.get("teams_details", {}).items():
        entities.add(str(team_name))
        entities.add(str(details.get("name", "")))
        entities.add(str(details.get("coach", "")))
        for player in details.get("squad", []) + details.get("starters", []) + details.get("substitutes", []):
            entities.add(str(player.get("name", "")))
    return {entity for entity in entities if entity and entity != "À déterminer"}


def _normalize_football_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    ascii_text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join("".join(ch if ch.isalnum() else " " for ch in ascii_text).split())


def save_message(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    pseudo = _clean(payload.get("pseudo", ""), 32)
    text = _clean(payload.get("message", ""), 500)
    color = _clean_color(payload.get("color", ""))
    if not pseudo or not text:
        return {"error": "Pseudo et message obligatoires."}, 400

    community = _read_community()
    community.setdefault("messages", []).append(
        {
            "pseudo": pseudo,
            "message": text,
            "color": color,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    community["messages"] = community["messages"][-200:]
    _write_community(community)
    return {"ok": True}, 200


if app:
    @app.post("/api/messages")
    def add_message():
        payload = request.get_json(silent=True) or {}
        body, status = save_message(payload)
        return jsonify(body), status

    @app.post("/api/watch-chat")
    def add_watch_chat():
        payload = request.get_json(silent=True) or {}
        body, status = save_watch_message(payload)
        return jsonify(body), status


def save_prediction(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    pseudo = _clean(payload.get("pseudo", ""), 32)
    match_id = _clean(payload.get("match_id", ""), 180)
    home_score = _to_score(payload.get("home_score"))
    away_score = _to_score(payload.get("away_score"))
    if not pseudo:
        return {"error": "Choisis un pseudo pour participer au classement"}, 400

    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    leagues_dashboard = _read_json(LEAGUES_CACHE_FILE, {})
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard, leagues_dashboard)
    match = matches.get(match_id)

    if not match or home_score is None or away_score is None:
        return {"error": "Pronostic invalide."}, 400
    if _is_locked(match):
        return {"error": "Pronostic verrouillé : le match a commencé."}, 423

    if _save_prediction_supabase(pseudo, match_id, home_score, away_score, matches):
        return {"ok": True, "storage": "supabase"}, 200

    community = _read_community()
    predictions = [
        prediction
        for prediction in community.get("predictions", [])
        if not (prediction.get("pseudo") == pseudo and prediction.get("match_id") == match_id)
    ]
    predictions.append(
        {
            "pseudo": pseudo,
            "match_id": match_id,
            "home_score": home_score,
            "away_score": away_score,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    community["predictions"] = predictions
    _write_community(community)
    return {"ok": True, "storage": "json"}, 200


if app:
    @app.post("/api/predictions")
    def add_prediction():
        payload = request.get_json(silent=True) or {}
        body, status = save_prediction(payload)
        return jsonify(body), status


class CommunityHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_file(OUTPUT_HTML, "text/html; charset=utf-8", replace_build_version=True, no_store=True)
        elif path == "/watch-party":
            self._send_html(watch_party_html())
        elif path == "/admin/sync":
            self._send_html(admin_sync_html(), no_store=True)
        elif path == "/manifest.json":
            self._send_file(BASE_DIR / "manifest.json", "application/manifest+json", no_store=True)
        elif path == "/service-worker.js":
            self._send_file(BASE_DIR / "service-worker.js", "application/javascript; charset=utf-8", no_store=True)
        elif path.startswith("/icons/"):
            self._send_file(BASE_DIR / path.lstrip("/"), _icon_content_type(path))
        elif path.startswith("/avatars/"):
            self._send_file(BASE_DIR / "public" / path.lstrip("/"), _icon_content_type(path))
        elif path == "/healthz":
            self._send_json({"status": "ok"})
        elif path == "/api/community":
            _schedule_live_score_refresh()
            self._send_json(community_payload())
        elif path == "/api/supabase-public-config":
            url, key = _supabase_config()
            self._send_json({"url": url, "anon_key": key, "configured": bool(url and key)})
        elif path == "/api/community/profile":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            pseudo = _clean(_url_decode(query.get("pseudo", "")), 32)
            profile = community_payload().get("profiles", {}).get(pseudo)
            self._send_json(profile or {"error": "Profil introuvable."}, 200 if profile else 404)
        elif path == "/api/livekit-token":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            pseudo = _clean(_url_decode(query.get("pseudo", "")), 32) or "Invite"
            role = "admin" if query.get("role") == "admin" and _is_admin_key(_url_decode(query.get("admin_key", ""))) else "viewer"
            body, status = make_livekit_token(pseudo, role)
            self._send_json(body, status)
        elif path == "/api/watch-chat":
            self._send_json({"messages": _watch_messages()[-120:]})
        elif path == "/api/refresh-news":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            self._send_json(refresh_news_payload(_url_decode(query.get("competition", "")), _url_decode(query.get("focus", "")), _url_decode(query.get("league", ""))))
        elif path == "/api/news":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            self._send_json(news_payload(_url_decode(query.get("filter", "all"))))
        elif path == "/api/news/refresh":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            self._send_json(refresh_global_news_payload(_url_decode(query.get("filter", "all"))))
        elif path == "/api/hall-of-fame":
            self._send_json(hall_of_fame_payload())
        elif path == "/api/match-articles":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            self._send_json(match_articles_payload(focus=_url_decode(query.get("focus", ""))))
        elif path == "/actus/resumes":
            self._send_html(match_articles_archive_html(), no_store=True)
        elif path.startswith("/actus/resume/"):
            html, status = match_article_detail_html(_url_decode(path.rsplit("/", 1)[-1]))
            self._send_html(html, status=status, no_store=True)
        elif path == "/api/mercato-live":
            self._send_json(_read_json(MERCATO_LIVE_CACHE_FILE, {"items": [], "source": "Mercato Live", "url": "https://www.mercatolive.fr/"}))
        elif path == "/api/leagues-dashboard":
            payload = _read_json(LEAGUES_CACHE_FILE, {"leagues": {}, "big5_top_scorers": [], "errors": []})
            leagues = payload.get("leagues") or {}
            rendered = {
                key: {
                    "scorers": len(value.get("top_scorers") or []),
                    "assists": len(value.get("top_assists") or []),
                    "standings": sum(len(group.get("teams") or group.get("standings") or []) for group in value.get("standings") or []),
                    "matches": sum(len(group.get("matches") or []) for group in value.get("group_matches") or []),
                }
                for key, value in leagues.items()
            }
            print(f"[championnats] cache utilisé: leagues={len(leagues)} big5={len(payload.get('big5_top_scorers') or [])} rendered={rendered}", flush=True)
            self._send_json(payload)
        elif path == "/api/football-supabase":
            self._send_json(_football_supabase_payload())
        elif path == "/api/coach/messages":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            session_id = _clean(_url_decode(query.get("session_id", "")), 120)
            raw_limit = _clean(_url_decode(query.get("limit", "12")), 8)
            try:
                limit = min(30, max(1, int(raw_limit or "12")))
            except ValueError:
                limit = 12
            self._send_json({"messages": _coach_messages_from_supabase(session_id, limit) if session_id else []})
        elif path == "/api/admin/sync/logs":
            body, status = admin_sync_logs_response()
            self._send_json(body, status)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_payload()
        if path == "/api/messages":
            body, status = save_message(payload)
            self._send_json(body, status)
        elif path == "/api/watch-chat":
            body, status = save_watch_message(payload)
            self._send_json(body, status)
        elif path == "/api/predictions":
            body, status = save_prediction(payload)
            self._send_json(body, status)
        elif path == "/api/football-chatbot":
            body, status = football_chatbot_response(payload)
            self._send_json(body, status)
        elif path == "/api/coach-prediction":
            body, status = coach_prediction_response(payload)
            self._send_json(body, status)
        elif path == "/api/search/coach":
            body, status = search_coach_response(payload)
            self._send_json(body, status)
        elif path == "/api/admin/sync/run":
            body, status = admin_sync_run_response(payload)
            self._send_json(body, status)
        elif path == "/api/admin/sync/cancel":
            body, status = admin_sync_cancel_response(payload)
            self._send_json(body, status)
        elif path == "/api/profile-password/hash":
            body, status = make_profile_password_hash(payload)
            self._send_json(body, status)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_payload(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return {}

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_no_store_headers(self) -> None:
        self.send_header("Cache-Control", NO_STORE_CACHE_CONTROL)
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def _send_html(self, html: str, status: int = 200, no_store: bool = False) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Akro-Build", _build_version())
        self.send_header("X-Akro-Served-File", "inline-html")
        if no_store:
            self._send_no_store_headers()
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str, replace_build_version: bool = False, no_store: bool = False) -> None:
        if not path.exists():
            self.send_error(404)
            return
        raw = path.read_bytes()
        raw = _replace_build_version(raw, content_type, replace_build_version)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Akro-Build", _build_version())
        self.send_header("X-Akro-Served-File", path.name)
        if no_store:
            self._send_no_store_headers()
        self.end_headers()
        self.wfile.write(raw)


def _supabase_config() -> tuple[str, str]:
    return os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_ANON_KEY", "").strip()


def _supabase_service_config() -> tuple[str, str]:
    return os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _supabase_service_enabled() -> bool:
    url, key = _supabase_service_config()
    return bool(url and key)


def _supabase_service_headers(prefer: str = "return=representation") -> dict[str, str]:
    _, key = _supabase_service_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _supabase_service_request(method: str, path: str, **kwargs: Any) -> Any:
    if not _supabase_service_enabled():
        return None
    cache_key = f"{method.upper()} {path}"
    if SUPABASE_FAILED_PATHS.get(cache_key, 0) > time.time():
        return None
    try:
        import requests

        url, _ = _supabase_service_config()
        extra_headers = kwargs.pop("extra_headers", {}) or {}
        headers = _supabase_service_headers(kwargs.pop("prefer", "return=representation"))
        headers.update(extra_headers)
        response = requests.request(
            method,
            f"{url}/rest/v1/{path.lstrip('/')}",
            headers=headers,
            timeout=SUPABASE_TIMEOUT,
            **kwargs,
        )
        if response.status_code >= 400:
            SUPABASE_FAILED_PATHS[cache_key] = time.time() + SUPABASE_FAILURE_TTL
            print(f"[supabase-service] fallback activé {method} {path} status={response.status_code} body={response.text[:220]}", flush=True)
            return None
        if not response.content:
            return []
        return response.json()
    except Exception as exc:
        SUPABASE_FAILED_PATHS[cache_key] = time.time() + SUPABASE_FAILURE_TTL
        print(f"[supabase-service] fallback activé {method} {path}: {exc}", flush=True)
        return None


def _supabase_service_paginated(path: str, page_size: int = 1000, max_rows: int = 50000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for start in range(0, max_rows, page_size):
        end = start + page_size - 1
        page = _supabase_service_request("GET", path, extra_headers={"Range": f"{start}-{end}"})
        if page is None:
            return rows
        if not isinstance(page, list) or not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
    return rows


def _api_football_enabled() -> bool:
    return bool(os.environ.get("API_FOOTBALL_KEY", "").strip())


def _api_football_cache_key(endpoint: str, params: dict[str, Any]) -> str:
    normalized = json.dumps({"endpoint": endpoint.strip("/"), "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _api_football_get(endpoint: str, params: dict[str, Any], *, cache_ttl: int | None = None) -> list[dict[str, Any]]:
    if not _api_football_enabled():
        print(f"[coach-api-football] API_FOOTBALL_KEY absente endpoint={endpoint}", flush=True)
        return []
    endpoint = endpoint.strip("/")
    clean_params = {key: str(value) for key, value in params.items() if value not in (None, "")}
    safe_url = f"{API_FOOTBALL_BASE_URL}/{endpoint}"
    api_key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    print(
        f"[coach-api-football] request_prepare url={safe_url} params={clean_params} "
        f"key_configured={bool(api_key)} key_len={len(api_key)}",
        flush=True,
    )
    cache_key = _api_football_cache_key(endpoint, clean_params)
    cached = _supabase_service_request(
        "GET",
        f"coach_api_cache?select=response,updated_at&cache_key=eq.{quote(cache_key, safe='')}&limit=1",
    )
    if isinstance(cached, list) and cached:
        updated_at = str(cached[0].get("updated_at") or cached[0].get("created_at") or "")
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            max_age = cache_ttl or COACH_API_FOOTBALL_CACHE_TTL
            if (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() <= max_age:
                response = cached[0].get("response")
                if isinstance(response, dict):
                    rows = response.get("response")
                    print(
                        f"[coach-api-football] cache_hit endpoint={endpoint} params={clean_params} "
                        f"rows={len(rows) if isinstance(rows, list) else 0}",
                        flush=True,
                    )
                    return rows if isinstance(rows, list) else []
        except ValueError:
            pass
    try:
        import requests

        print(f"[coach-api-football] http_start url={safe_url} params={clean_params}", flush=True)
        response = requests.get(
            safe_url,
            params=clean_params,
            headers={"x-apisports-key": os.environ.get("API_FOOTBALL_KEY", "").strip()},
            timeout=COACH_API_FOOTBALL_TIMEOUT,
        )
        print(f"[coach-api-football] http_done status={response.status_code} url={safe_url} params={clean_params}", flush=True)
        if response.status_code >= 400:
            print(f"[coach-api-football] http_error status={response.status_code} endpoint={endpoint} body={response.text[:220]}", flush=True)
            return []
        payload = response.json()
        if isinstance(payload, dict) and payload.get("errors"):
            print(f"[coach-api-football] errors endpoint={endpoint} params={clean_params} errors={str(payload.get('errors'))[:220]}", flush=True)
        _supabase_service_request(
            "POST",
            "coach_api_cache?on_conflict=cache_key",
            json={
                "cache_key": cache_key,
                "endpoint": endpoint,
                "params": clean_params,
                "response": payload,
                "source": "api-football",
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
        rows = payload.get("response") if isinstance(payload, dict) else []
        print(f"[coach-api-football] fetched endpoint={endpoint} params={clean_params} rows={len(rows) if isinstance(rows, list) else 0}", flush=True)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        print(f"[coach-api-football] erreur endpoint={endpoint}: {exc}", flush=True)
        return []


def _generate_match_articles_once() -> int:
    cutoff = datetime.fromtimestamp(time.time() - MATCH_ARTICLE_GENERATION_DELAY_SECONDS, timezone.utc).isoformat()
    matches = _supabase_service_request(
        "GET",
        "matches?"
        "select=id,api_id,competition_id,season,round,status,match_date,venue_name,home_team_id,away_team_id,home_score,away_score,raw_data,updated_at"
        f"&status=in.(FT,AET,PEN)&updated_at=lte.{quote(cutoff, safe='')}&order=updated_at.asc&limit=20",
    )
    if not isinstance(matches, list) or not matches:
        return 0

    match_ids = [str(match.get("id") or "") for match in matches if match.get("id")]
    if not match_ids:
        return 0

    existing = _supabase_service_request(
        "GET",
        f"match_articles?select=match_id&match_id=in.({','.join(quote(item, safe='') for item in match_ids)})",
    )
    if existing is None:
        return 0
    existing_ids = {str(row.get("match_id") or "") for row in existing if isinstance(row, dict)}
    candidates = [match for match in matches if str(match.get("id") or "") not in existing_ids]
    if not candidates:
        return 0

    team_ids = sorted({
        str(match.get(field) or "")
        for match in candidates
        for field in ("home_team_id", "away_team_id")
        if match.get(field)
    })
    competition_ids = sorted({str(match.get("competition_id") or "") for match in candidates if match.get("competition_id")})
    teams = _supabase_service_request(
        "GET",
        f"teams?select=id,name&limit=2000&id=in.({','.join(quote(item, safe='') for item in team_ids)})",
    ) if team_ids else []
    competitions = _supabase_service_request(
        "GET",
        f"competitions?select=id,name&limit=300&id=in.({','.join(quote(item, safe='') for item in competition_ids)})",
    ) if competition_ids else []
    team_by_id = {str(row.get("id")): str(row.get("name") or "") for row in (teams or []) if isinstance(row, dict)}
    competition_by_id = {str(row.get("id")): str(row.get("name") or "") for row in (competitions or []) if isinstance(row, dict)}

    created = 0
    for match in candidates:
        article = _match_article_payload(match, team_by_id, competition_by_id)
        if not article:
            continue
        saved = _supabase_service_request(
            "POST",
            "match_articles",
            json=article,
            prefer="return=minimal",
        )
        if saved is not None:
            created += 1
    return created


def _match_article_payload(match: dict[str, Any], team_by_id: dict[str, str], competition_by_id: dict[str, str]) -> dict[str, Any] | None:
    match_id = str(match.get("id") or "")
    home = team_by_id.get(str(match.get("home_team_id") or "")) or "Équipe domicile"
    away = team_by_id.get(str(match.get("away_team_id") or "")) or "Équipe extérieure"
    home_score = _to_score(match.get("home_score"))
    away_score = _to_score(match.get("away_score"))
    if not match_id or home_score is None or away_score is None:
        return None
    competition = competition_by_id.get(str(match.get("competition_id") or "")) or "Compétition"
    score = f"{home_score}-{away_score}"
    penalties = _match_article_penalty_score(match)
    score_title = f"{score} ({penalties} TAB)" if penalties else score
    title = f"{home} {score_title} {away} : résumé automatique du match"
    if penalties:
        summary = f"{home} et {away} se sont quittés sur un score de {score} avant une séance de tirs au but conclue à {penalties}."
    elif home_score == away_score:
        summary = f"{home} et {away} se sont neutralisés sur le score de {score}."
    else:
        winner = home if home_score > away_score else away
        summary = f"{winner} s'est imposé face à {away if winner == home else home} sur le score de {score}."
    moments = _match_article_moments(match)
    content = _match_article_content(match, title, summary, competition, home, away, score_title, moments)
    return {
        "match_id": match_id,
        "match_api_id": str(match.get("api_id") or ""),
        "slug": _match_article_slug(match, home, away),
        "title": title,
        "summary": summary,
        "content": content,
        "competition": competition,
        "status": "published",
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def _match_article_slug(match: dict[str, Any], home: str, away: str) -> str:
    date_value = str(match.get("match_date") or "")[:10]
    base = _normalize_football_text(f"{date_value} {home} {away} {match.get('api_id') or match.get('id')}")
    slug = "-".join(base.split())
    return slug[:140] or f"match-{str(match.get('id') or '')[:8]}"


def _match_article_penalty_score(match: dict[str, Any]) -> str:
    raw_data = match.get("raw_data") if isinstance(match.get("raw_data"), dict) else {}
    score = raw_data.get("score") if isinstance(raw_data.get("score"), dict) else {}
    penalty = score.get("penalty") if isinstance(score.get("penalty"), dict) else {}
    home = _to_score(penalty.get("home"))
    away = _to_score(penalty.get("away"))
    return f"{home}-{away}" if home is not None and away is not None else ""


def _match_article_moments(match: dict[str, Any]) -> list[str]:
    raw_data = match.get("raw_data") if isinstance(match.get("raw_data"), dict) else {}
    events = raw_data.get("events") if isinstance(raw_data.get("events"), list) else []
    moments = []
    for event in events[:8]:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or event.get("detail") or "").strip()
        player = event.get("player") if isinstance(event.get("player"), dict) else {}
        team = event.get("team") if isinstance(event.get("team"), dict) else {}
        minute = event.get("time") if isinstance(event.get("time"), dict) else {}
        label = " ".join(str(part or "").strip() for part in [minute.get("elapsed"), event_type, player.get("name"), team.get("name")] if part)
        if label:
            moments.append(label)
    return moments


def _match_article_content(match: dict[str, Any], title: str, summary: str, competition: str, home: str, away: str, score: str, moments: list[str]) -> str:
    date_label = _format_article_date(match.get("match_date"))
    lines = [
        title,
        "",
        summary,
        "",
        "Moments clés",
    ]
    lines.extend([f"- {moment}" for moment in moments] or ["- Les événements détaillés seront ajoutés dès disponibilité dans les données match."])
    lines.extend([
        "",
        "Fiche match",
        f"- Compétition : {competition}",
        f"- Date : {date_label or 'Date non disponible'}",
        f"- Affiche : {home} vs {away}",
        f"- Score : {score}",
        f"- Statut : {match.get('status') or 'Terminé'}",
    ])
    if match.get("venue_name"):
        lines.append(f"- Stade : {match.get('venue_name')}")
    return "\n".join(lines)


def _format_article_date(value: Any) -> str:
    try:
        date = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return ""
    return date.strftime("%d/%m/%Y %Hh%M")


def _football_supabase_payload() -> dict[str, Any]:
    if not _supabase_service_enabled():
        return {"configured": False, "teams": [], "countries": [], "competitions": [], "matches": [], "source": "fallback"}
    with FOOTBALL_SUPABASE_CACHE_LOCK:
        cached_payload = FOOTBALL_SUPABASE_CACHE.get("payload")
        if cached_payload and FOOTBALL_SUPABASE_CACHE.get("expires_at", 0) > time.time():
            return cached_payload

    countries = _supabase_service_request("GET", "countries?select=id,api_id,name,code,flag_url&order=name.asc&limit=300") or []
    competitions = _supabase_service_request("GET", "competitions?select=id,api_id,country_id,name,type,logo_url,season,updated_at&is_active=eq.true&order=name.asc&limit=300") or []
    teams = _supabase_service_request("GET", "teams?select=id,api_id,country_id,name,short_name,code,type,logo_url,venue_name,raw_data,updated_at&is_active=eq.true&order=updated_at.desc&limit=2000") or []
    players = _supabase_service_request("GET", "players?select=id,api_id,name,firstname,lastname,birth_date,nationality,position,photo_url,raw_data,updated_at&is_active=eq.true&order=updated_at.desc&limit=5000") or []
    coaches = _supabase_service_request("GET", "coaches?select=id,api_id,name,firstname,lastname,birth_date,nationality,photo_url,raw_data,updated_at&is_active=eq.true&order=updated_at.desc&limit=1000") or []
    team_players = _supabase_service_paginated(
        "team_players?select=team_id,player_id,season,shirt_number,position,updated_at,players(id,api_id,name,firstname,lastname,birth_date,nationality,position,photo_url,raw_data)&is_active=eq.true&order=updated_at.desc",
        page_size=1000,
        max_rows=50000,
    )
    if not team_players:
        team_players = _supabase_service_paginated(
            "team_players?select=team_id,player_id,season,shirt_number,position,updated_at&is_active=eq.true&order=updated_at.desc",
            page_size=1000,
            max_rows=50000,
        )
    team_coaches = _supabase_service_request("GET", "team_coaches?select=team_id,coach_id,season,role,updated_at&is_active=eq.true&order=updated_at.desc&limit=1000") or []
    matches = _supabase_service_request("GET", "matches?select=id,api_id,competition_id,season,round,status,match_date,venue_name,home_team_id,away_team_id,home_score,away_score,raw_data,updated_at&order=match_date.desc&limit=500") or []

    country_by_id = {str(row.get("id")): row for row in countries if row.get("id")}
    team_by_id = {str(row.get("id")): row for row in teams if row.get("id")}
    player_by_id = {str(row.get("id")): row for row in players if row.get("id")}
    coach_by_id = {str(row.get("id")): row for row in coaches if row.get("id")}
    competition_by_id = {str(row.get("id")): row for row in competitions if row.get("id")}
    missing_link_player_ids = sorted({
        str(link.get("player_id") or "")
        for link in team_players
        if link.get("player_id") and str(link.get("player_id")) not in player_by_id and not isinstance(link.get("players"), dict)
    })
    for index in range(0, len(missing_link_player_ids), 80):
        chunk = missing_link_player_ids[index:index + 80]
        scoped_players = _supabase_service_request(
            "GET",
            f"players?select=id,api_id,name,firstname,lastname,birth_date,nationality,position,photo_url,raw_data,updated_at&id=in.({','.join(quote(item, safe='') for item in chunk)})",
        ) or []
        for player in scoped_players:
            if player.get("id"):
                player_by_id[str(player["id"])] = player
                players.append(player)

    players_by_team: dict[str, list[dict[str, Any]]] = {}
    linked_relations = 0
    resolved_players = 0
    for link in team_players:
        team_id = str(link.get("team_id") or "")
        embedded_player = link.get("players") if isinstance(link.get("players"), dict) else None
        player = embedded_player or player_by_id.get(str(link.get("player_id") or ""))
        if not team_id or not player:
            continue
        linked_relations += 1
        resolved_players += 1
        raw_player = player.get("raw_data") if isinstance(player.get("raw_data"), dict) else {}
        raw_nested_player = raw_player.get("player") if isinstance(raw_player.get("player"), dict) else {}
        age = raw_player.get("age") or raw_nested_player.get("age")
        players_by_team.setdefault(team_id, []).append({
            "name": player.get("name") or "",
            "firstname": player.get("firstname") or "",
            "lastname": player.get("lastname") or "",
            "position": link.get("position") or player.get("position") or "",
            "shirt_number": link.get("shirt_number"),
            "number": link.get("shirt_number"),
            "birth_date": player.get("birth_date") or "",
            "age": age or "",
            "nationality": player.get("nationality") or "",
            "photo_url": player.get("photo_url") or "",
            "season": link.get("season") or "",
        })

    coaches_by_team: dict[str, list[dict[str, Any]]] = {}
    for link in team_coaches:
        team_id = str(link.get("team_id") or "")
        coach = coach_by_id.get(str(link.get("coach_id") or ""))
        if not team_id or not coach:
            continue
        coaches_by_team.setdefault(team_id, []).append({
            "name": coach.get("name") or "",
            "role": link.get("role") or "coach",
            "photo_url": coach.get("photo_url") or "",
            "nationality": coach.get("nationality") or "",
            "season": link.get("season") or "",
        })

    public_matches = []
    competition_for_team: dict[str, str] = {}
    def _team_logo_url(row: dict[str, Any] | None) -> str:
        if not row:
            return ""
        raw_data = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
        raw_team = raw_data.get("team") if isinstance(raw_data.get("team"), dict) else {}
        return (
            row.get("logo_url")
            or row.get("logo")
            or row.get("crest")
            or raw_team.get("logo")
            or raw_data.get("logo_url")
            or raw_data.get("logo")
            or raw_data.get("crest")
            or ""
        )

    for match in matches:
        home = team_by_id.get(str(match.get("home_team_id") or ""))
        away = team_by_id.get(str(match.get("away_team_id") or ""))
        competition = competition_by_id.get(str(match.get("competition_id") or ""))
        competition_name = competition.get("name") if competition else ""
        raw_match = match.get("raw_data") if isinstance(match.get("raw_data"), dict) else {}
        raw_score = raw_match.get("score") if isinstance(raw_match.get("score"), dict) else {}
        raw_penalty = raw_score.get("penalty") if isinstance(raw_score.get("penalty"), dict) else {}
        if home and competition_name:
            competition_for_team.setdefault(str(home.get("id")), str(competition_name))
        if away and competition_name:
            competition_for_team.setdefault(str(away.get("id")), str(competition_name))
        public_match = {
            "id": match.get("api_id") or match.get("id") or "",
            "competition": competition_name or "Compétition",
            "season": match.get("season") or "",
            "phase": match.get("round") or "",
            "raw_data": raw_match,
            "date": match.get("match_date") or "",
            "status": match.get("status") or "",
            "venue": match.get("venue_name") or "",
            "home_team": home.get("name") if home else "Équipe à compléter",
            "away_team": away.get("name") if away else "Équipe à compléter",
            "home_flag_url": _team_logo_url(home),
            "away_flag_url": _team_logo_url(away),
            "home_score": "" if match.get("home_score") is None else str(match.get("home_score")),
            "away_score": "" if match.get("away_score") is None else str(match.get("away_score")),
            "home_penalty_score": "" if raw_penalty.get("home") is None else str(raw_penalty.get("home")),
            "away_penalty_score": "" if raw_penalty.get("away") is None else str(raw_penalty.get("away")),
            "completed": str(match.get("status") or "").lower() in {"ft", "aet", "pen", "terminé", "match finished"},
        }
        public_matches.append(public_match)

    public_teams = []
    player_team_names: dict[str, list[str]] = {}
    debug_roster_rows = []
    for row in teams:
        country = country_by_id.get(str(row.get("country_id") or ""))
        team_id = str(row.get("id") or "")
        squad = players_by_team.get(team_id, [])
        if _normalize_football_text(row.get("name") or "") in {"paris saint germain", "psg", "france"}:
            debug_roster_rows.append({
                "name": row.get("name") or "",
                "team_id": team_id,
                "api_id": row.get("api_id") or "",
                "squad": len(squad),
                "positions": sorted({str(player.get("position") or "") for player in squad if player.get("position")}),
            })
        for player in squad:
            if player.get("name"):
                player_team_names.setdefault(player["name"], []).append(row.get("name") or "")
        coaches_list = coaches_by_team.get(team_id, [])
        public_teams.append({
            "id": team_id,
            "api_id": row.get("api_id") or "",
            "name": row.get("name") or "",
            "short_name": row.get("short_name") or "",
            "code": row.get("code") or "",
            "type": row.get("type") or "club",
            "logo_url": _team_logo_url(row),
            "venue_name": row.get("venue_name") or "",
            "country": country.get("name") if country else "",
            "country_code": country.get("code") if country else "",
            "country_flag_url": country.get("flag_url") if country else "",
            "competition": competition_for_team.get(team_id, ""),
            "coach": coaches_list[0]["name"] if coaches_list else "",
            "coaches": coaches_list,
            "squad": squad,
            "updated_at": row.get("updated_at") or "",
        })
    public_players = [{
        "name": row.get("name") or "",
        "firstname": row.get("firstname") or "",
        "lastname": row.get("lastname") or "",
        "birth_date": row.get("birth_date") or "",
        "nationality": row.get("nationality") or "",
        "position": row.get("position") or "",
        "photo_url": row.get("photo_url") or "",
        "teams": player_team_names.get(row.get("name") or "", [])[:3],
        "updated_at": row.get("updated_at") or "",
    } for row in players if row.get("name")]
    public_coaches = [{
        "name": row.get("name") or "",
        "nationality": row.get("nationality") or "",
        "photo_url": row.get("photo_url") or "",
        "updated_at": row.get("updated_at") or "",
    } for row in coaches if row.get("name")]

    payload = {
        "configured": True,
        "source": "supabase",
        "countries": countries,
        "competitions": competitions,
        "teams": public_teams,
        "players": public_players,
        "coaches": public_coaches,
        "matches": public_matches,
        "counts": {
            "countries": len(countries),
            "competitions": len(competitions),
            "teams": len(public_teams),
            "players": len(players),
            "coaches": len(coaches),
            "team_players": len(team_players),
            "team_coaches": len(team_coaches),
            "team_players_resolved": resolved_players,
            "matches": len(public_matches),
        },
    }
    with FOOTBALL_SUPABASE_CACHE_LOCK:
        FOOTBALL_SUPABASE_CACHE["payload"] = payload
        FOOTBALL_SUPABASE_CACHE["expires_at"] = time.time() + SUPABASE_FOOTBALL_CACHE_TTL
    print(f"[football-supabase] source=supabase counts={payload['counts']} linked_relations={linked_relations} resolved_players={resolved_players} roster_debug={debug_roster_rows}", flush=True)
    return payload


def _coach_supabase_context(question: str) -> str:
    if not question or not _supabase_service_enabled():
        return ""
    normalized = _normalize_football_text(question)
    context = _coach_local_football_context(normalized)
    if context:
        return context
    payload = _football_supabase_payload()
    snippets = []
    for team in payload.get("teams", [])[:120]:
      haystack = _normalize_football_text(f"{team.get('name', '')} {team.get('short_name', '')} {team.get('code', '')} {team.get('country', '')}")
      if normalized and any(word in haystack for word in normalized.split() if len(word) > 2):
          parts = [team.get("name") or "Équipe"]
          if team.get("country"):
              parts.append(f"pays: {team['country']}")
          if team.get("competition"):
              parts.append(f"compétition: {team['competition']}")
          if team.get("coach"):
              parts.append(f"coach: {team['coach']}")
          squad = team.get("squad") or []
          if squad:
              parts.append("joueurs: " + ", ".join(player.get("name", "") for player in squad[:8] if player.get("name")))
          snippets.append("- " + " · ".join(parts))
    if not snippets:
        for player in payload.get("players", [])[:200]:
            haystack = _normalize_football_text(f"{player.get('name', '')} {player.get('position', '')} {' '.join(player.get('teams') or [])}")
            if normalized and any(word in haystack for word in normalized.split() if len(word) > 2):
                parts = [player.get("name") or "Joueur"]
                if player.get("position"):
                    parts.append(f"poste: {player['position']}")
                if player.get("teams"):
                    parts.append("club/équipe: " + ", ".join(player.get("teams")[:3]))
                snippets.append("- " + " · ".join(parts))
                if len(snippets) >= 8:
                    break
    if not snippets:
        for coach in payload.get("coaches", [])[:120]:
            haystack = _normalize_football_text(f"{coach.get('name', '')} {coach.get('nationality', '')}")
            if normalized and any(word in haystack for word in normalized.split() if len(word) > 2):
                parts = [coach.get("name") or "Coach"]
                if coach.get("nationality"):
                    parts.append(f"nationalité: {coach['nationality']}")
                snippets.append("- " + " · ".join(parts))
                if len(snippets) >= 8:
                    break
    if not snippets:
        for competition in payload.get("competitions", [])[:80]:
            haystack = _normalize_football_text(f"{competition.get('name', '')} {competition.get('season', '')}")
            if normalized and any(word in haystack for word in normalized.split() if len(word) > 2):
                snippets.append(f"- Compétition: {competition.get('name')} · saison {competition.get('season') or 'non précisée'}")
    if not snippets:
        for match in payload.get("matches", [])[:80]:
            haystack = _normalize_football_text(f"{match.get('home_team', '')} {match.get('away_team', '')} {match.get('competition', '')}")
            if normalized and any(word in haystack for word in normalized.split() if len(word) > 2):
                snippets.append(f"- Match: {match.get('home_team')} vs {match.get('away_team')} · {match.get('competition')} · {match.get('status')}")
    return "\n".join(snippets[:8])


def _coach_query_terms(normalized_question: str) -> list[str]:
    stopwords = {
        "avec", "dans", "pour", "quoi", "quel", "quelle", "quels", "quelles", "donne", "explique",
        "analyse", "compare", "contre", "classement", "match", "matches", "joueur", "joueurs",
        "coach", "entraineur", "entraîneur", "equipe", "équipe", "club", "clubs", "saison",
        "competition", "compétition", "forme", "recent", "récente", "dernier", "derniers",
        "pronostic", "favori", "palmares", "palmarès", "bracket", "phase", "finale",
    }
    return [word for word in normalized_question.split() if len(word) > 2 and word not in stopwords]


COACH_PLAYER_ALIASES = {
    "messi": "Lionel Messi",
    "lionel messi": "Lionel Messi",
    "ronaldo": "Cristiano Ronaldo",
    "cristiano ronaldo": "Cristiano Ronaldo",
    "cr7": "Cristiano Ronaldo",
    "mbappe": "Kylian Mbappé",
    "mbappee": "Kylian Mbappé",
    "kylian mbappe": "Kylian Mbappé",
    "haaland": "Erling Haaland",
    "erling haaland": "Erling Haaland",
    "neymar": "Neymar",
    "zidane": "Zinedine Zidane",
    "platini": "Michel Platini",
}

COACH_PLAYER_BIRTH_DATES = {
    "Lionel Messi": "1987-06-24",
    "Cristiano Ronaldo": "1985-02-05",
    "Kylian Mbappé": "1998-12-20",
    "Erling Haaland": "2000-07-21",
    "Neymar": "1992-02-05",
    "Zinedine Zidane": "1972-06-23",
    "Michel Platini": "1955-06-21",
}


def _coach_detect_player_names(question: str) -> list[str]:
    normalized = _normalize_football_text(question)
    names: list[str] = []
    for alias, name in COACH_PLAYER_ALIASES.items():
        if alias in normalized and name not in names:
            names.append(name)
    if len(names) >= 2:
        return names[:4]
    payload = _football_supabase_payload()
    terms = _coach_query_terms(normalized)
    for player in _coach_pick_relevant_rows(payload.get("players", []), terms, ["name", "firstname", "lastname"], 4):
        name = str(player.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names[:4]


def _coach_detect_age(question: str) -> int | None:
    normalized = _normalize_football_text(question)
    match = re.search(r"\b(?:a|à|age|ans)\s*(\d{2})\b", normalized)
    if not match:
        match = re.search(r"\b(\d{2})\s*ans\b", normalized)
    if not match:
        return None
    age = int(match.group(1))
    return age if 15 <= age <= 45 else None


def _coach_player_birth_year(player_name: str, payload: dict[str, Any]) -> int | None:
    for player in payload.get("players", []):
        if _normalize_football_text(player.get("name", "")) == _normalize_football_text(player_name):
            birth = str(player.get("birth_date") or "")[:10]
            if re.match(r"^\d{4}-", birth):
                return int(birth[:4])
    birth = COACH_PLAYER_BIRTH_DATES.get(player_name)
    return int(birth[:4]) if birth else None


def _coach_seasons_for_age(player_name: str, age: int, payload: dict[str, Any]) -> list[str]:
    birth_year = _coach_player_birth_year(player_name, payload)
    if not birth_year:
        return []
    pivot = birth_year + age
    return [str(pivot - 1), str(pivot), str(pivot + 1)]


def _coach_find_player_row(player_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    wanted = _normalize_football_text(player_name)
    for player in payload.get("players", []):
        if _normalize_football_text(player.get("name", "")) == wanted:
            return player
    candidates = _coach_pick_relevant_rows(payload.get("players", []), _coach_query_terms(wanted), ["name", "firstname", "lastname"], 1)
    return candidates[0] if candidates else None


def _coach_player_stats_rows(player_name: str, seasons: list[str]) -> list[dict[str, Any]]:
    if not _supabase_service_enabled() or not seasons:
        return []
    season_filter = ",".join(quote(season, safe="") for season in seasons)
    rows = _supabase_service_request(
        "GET",
        "coach_player_season_stats?"
        "select=player_name,player_api_id,team_name,league_name,season,appearances,lineups,minutes,goals,assists,yellow_cards,red_cards,rating,updated_at"
        f"&player_name=ilike.{quote(f'*{player_name}*', safe='')}&season=in.({season_filter})&order=season.asc",
    )
    return rows if isinstance(rows, list) else []


def _coach_stat_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _coach_player_api_search_terms(player_name: str) -> list[str]:
    normalized = _normalize_football_text(player_name)
    aliases = {
        "lionel messi": ["messi", "lionel messi"],
        "cristiano ronaldo": ["cristiano ronaldo", "cristiano", "ronaldo"],
        "kylian mbappe": ["kylian mbappe", "mbappe"],
        "erling haaland": ["erling haaland", "haaland"],
        "neymar": ["neymar"],
    }
    terms = aliases.get(normalized, [])
    if not terms:
        parts = normalized.split()
        terms = [normalized]
        if parts:
            terms.append(parts[-1])
    out: list[str] = []
    for term in terms:
        clean = _normalize_football_text(term)
        if len(clean) >= 4 and clean not in out:
            out.append(clean)
    return out


def _coach_api_player_matches(api_name: str, requested_name: str) -> bool:
    requested_terms = _coach_query_terms(_normalize_football_text(requested_name))
    if _coach_match_score(_normalize_football_text(api_name), requested_terms) > 0:
        return True
    api_norm = _normalize_football_text(api_name)
    return any(term and term in api_norm for term in _coach_player_api_search_terms(requested_name))


def _coach_api_player_stats(player_name: str, seasons: list[str]) -> list[dict[str, Any]]:
    print(
        f"[coach-enrich] player_start player={player_name} seasons={seasons} "
        f"api_enabled={_api_football_enabled()} supabase_service={_supabase_service_enabled()}",
        flush=True,
    )
    if not _api_football_enabled() or not seasons:
        print(f"[coach-enrich] player_skip player={player_name} reason=api_disabled_or_no_seasons", flush=True)
        return []
    collected: list[dict[str, Any]] = []
    search_terms = _coach_player_api_search_terms(player_name)
    print(f"[coach-enrich] search_terms player={player_name} terms={search_terms}", flush=True)
    for season in seasons[:4]:
        rows: list[dict[str, Any]] = []
        seen_api_players: set[str] = set()
        print(f"[coach-enrich] season_start player={player_name} season={season}", flush=True)
        for search_term in search_terms:
            api_rows = _api_football_get("players", {"search": search_term, "season": season})
            print(
                f"[coach-enrich] api_rows player={player_name} season={season} "
                f"search={search_term} count={len(api_rows)}",
                flush=True,
            )
            for item in api_rows:
                player = item.get("player") if isinstance(item, dict) else {}
                api_id = str(player.get("id") or "") if isinstance(player, dict) else ""
                dedupe_key = api_id or json.dumps(player, sort_keys=True, ensure_ascii=False)
                if dedupe_key in seen_api_players:
                    continue
                seen_api_players.add(dedupe_key)
                rows.append(item)
        print(f"[coach-enrich] candidates player={player_name} season={season} count={len(rows)}", flush=True)
        season_mapped = 0
        for item in rows[:8]:
            player = item.get("player") if isinstance(item, dict) else {}
            if not isinstance(player, dict):
                continue
            api_name = str(player.get("name") or "").strip()
            matches_player = bool(api_name and _coach_api_player_matches(api_name, player_name))
            print(
                f"[coach-enrich] candidate_match player={player_name} season={season} "
                f"api_name={api_name or '-'} api_id={player.get('id') or '-'} matched={matches_player}",
                flush=True,
            )
            if not matches_player:
                continue
            for stat in item.get("statistics") or []:
                if not isinstance(stat, dict):
                    continue
                games = stat.get("games") if isinstance(stat.get("games"), dict) else {}
                goals = stat.get("goals") if isinstance(stat.get("goals"), dict) else {}
                cards = stat.get("cards") if isinstance(stat.get("cards"), dict) else {}
                team = stat.get("team") if isinstance(stat.get("team"), dict) else {}
                league = stat.get("league") if isinstance(stat.get("league"), dict) else {}
                row = {
                    "api_id": f"{player.get('id')}:{team.get('id') or ''}:{league.get('id') or ''}:{season}",
                    "player_api_id": str(player.get("id") or ""),
                    "player_name": player_name,
                    "team_api_id": str(team.get("id") or ""),
                    "team_name": str(team.get("name") or ""),
                    "league_api_id": str(league.get("id") or ""),
                    "league_name": str(league.get("name") or ""),
                    "season": str(season),
                    "appearances": _coach_stat_int(games.get("appearences") or games.get("appearances")),
                    "lineups": _coach_stat_int(games.get("lineups")),
                    "minutes": _coach_stat_int(games.get("minutes")),
                    "goals": _coach_stat_int(goals.get("total")),
                    "assists": _coach_stat_int(goals.get("assists")),
                    "yellow_cards": _coach_stat_int(cards.get("yellow")),
                    "red_cards": _coach_stat_int(cards.get("red")),
                    "rating": None,
                    "raw_data": {"player": player, "statistics": stat, "api_player_name": api_name},
                    "source": "api-football",
                }
                try:
                    row["rating"] = float(games.get("rating")) if games.get("rating") not in (None, "") else None
                except (TypeError, ValueError):
                    row["rating"] = None
                collected.append(row)
                season_mapped += 1
        print(f"[coach-enrich] season_mapped player={player_name} season={season} rows={season_mapped}", flush=True)
    if collected and _supabase_service_enabled():
        print(f"[coach-enrich] upsert_start player={player_name} rows={len(collected[:80])}", flush=True)
        saved = _supabase_service_request(
            "POST",
            "coach_player_season_stats?on_conflict=api_id",
            json=collected[:80],
            prefer="resolution=merge-duplicates,return=minimal",
        )
        if saved is None:
            print(f"[coach-api-football] upsert coach_player_season_stats failed player={player_name} rows={len(collected[:80])}", flush=True)
        else:
            print(f"[coach-api-football] upsert coach_player_season_stats ok player={player_name} rows={len(collected[:80])}", flush=True)
    elif collected:
        print(f"[coach-enrich] upsert_skip player={player_name} reason=supabase_service_disabled rows={len(collected)}", flush=True)
    else:
        print(f"[coach-enrich] no_rows_mapped player={player_name}", flush=True)
    return collected


def _coach_player_stats_context(question: str) -> str:
    player_names = _coach_detect_player_names(question)
    if not player_names:
        return ""
    payload = _football_supabase_payload()
    age = _coach_detect_age(question)
    print(f"[coach-enrich] context_start question={question[:160]!r} players={player_names} age={age}", flush=True)
    lines = []
    for name in player_names:
        seasons = _coach_seasons_for_age(name, age, payload) if age else []
        print(f"[coach-enrich] player_context player={name} seasons={seasons}", flush=True)
        if not seasons:
            seasons = [str(datetime.now(timezone.utc).year - 1), str(datetime.now(timezone.utc).year)]
            print(f"[coach-enrich] player_context fallback_seasons player={name} seasons={seasons}", flush=True)
        rows = _coach_player_stats_rows(name, seasons)
        print(f"[coach-enrich] supabase_rows player={name} seasons={seasons} count={len(rows)}", flush=True)
        if not rows:
            rows = _coach_api_player_stats(name, seasons)
            print(f"[coach-enrich] enriched_rows player={name} seasons={seasons} count={len(rows)}", flush=True)
        if not rows:
            row = _coach_find_player_row(name, payload) or {}
            base = [f"- {name}: statistiques détaillées absentes dans Supabase"]
            if row.get("birth_date"):
                base.append(f"naissance {row['birth_date']}")
            if row.get("nationality"):
                base.append(f"nationalité {row['nationality']}")
            if row.get("teams"):
                base.append("équipes liées " + ", ".join(row.get("teams")[:3]))
            lines.append(" · ".join(base))
            continue
        totals = {
            "matches": sum(_coach_stat_int(row.get("appearances")) for row in rows),
            "minutes": sum(_coach_stat_int(row.get("minutes")) for row in rows),
            "goals": sum(_coach_stat_int(row.get("goals")) for row in rows),
            "assists": sum(_coach_stat_int(row.get("assists")) for row in rows),
        }
        competitions = sorted({str(row.get("league_name") or "") for row in rows if row.get("league_name")})[:5]
        teams = sorted({str(row.get("team_name") or "") for row in rows if row.get("team_name")})[:5]
        age_label = f" autour de ses {age} ans" if age else ""
        lines.append(
            f"- {name}{age_label}: {totals['matches']} matchs, {totals['minutes']} minutes, "
            f"{totals['goals']} buts, {totals['assists']} passes décisives. "
            f"Saisons: {', '.join(sorted({str(row.get('season')) for row in rows if row.get('season')}))}. "
            f"Clubs: {', '.join(teams) or 'non précisés'}. Compétitions: {', '.join(competitions) or 'non précisées'}."
        )
    if not lines:
        return ""
    intro = "Statistiques joueur récupérées depuis Supabase"
    if _api_football_enabled():
        intro += " puis enrichies à la demande via API-Football si nécessaire"
    return intro + ":\n" + "\n".join(lines)


def _coach_match_score(haystack: str, terms: list[str]) -> int:
    if not haystack or not terms:
        return 0
    return sum(2 if re.search(rf"(^|\s){re.escape(term)}($|\s)", haystack) else 1 for term in terms if term in haystack)


def _coach_pick_relevant_rows(rows: list[dict[str, Any]], terms: list[str], fields: list[str], limit: int = 5) -> list[dict[str, Any]]:
    ranked = []
    for row in rows:
        haystack = _normalize_football_text(" ".join(str(row.get(field, "")) for field in fields))
        score = _coach_match_score(haystack, terms)
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in ranked[:limit]]


def _coach_team_recent_matches(team_name: str, matches: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    key = _normalize_football_text(team_name)
    team_matches = [
        match for match in matches
        if key and key in {
            _normalize_football_text(match.get("home_team", "")),
            _normalize_football_text(match.get("away_team", "")),
        }
    ]
    return sorted(team_matches, key=lambda item: str(item.get("date") or ""), reverse=True)[:limit]


def _coach_match_line(match: dict[str, Any]) -> str:
    home = match.get("home_team") or "Équipe A"
    away = match.get("away_team") or "Équipe B"
    score = _real_score_label(match) if match.get("home_score") != "" and match.get("away_score") != "" else "score non disponible"
    status = match.get("status") or "statut non disponible"
    competition = match.get("competition") or "compétition non précisée"
    date = match.get("date") or "date non disponible"
    return f"{home} vs {away} · {competition} · {date} · {status} · {score}"


def _coach_team_context(team: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    parts = [f"- Équipe: {team.get('name') or 'Équipe'}"]
    if team.get("type"):
        parts.append(f"type: {team['type']}")
    if team.get("country"):
        parts.append(f"pays: {team['country']}")
    if team.get("competition"):
        parts.append(f"compétition liée: {team['competition']}")
    if team.get("coach"):
        parts.append(f"coach: {team['coach']}")
    squad = team.get("squad") or []
    if squad:
        by_position: dict[str, list[str]] = {}
        for player in squad:
            position = str(player.get("position") or "poste non précisé")
            name = str(player.get("name") or "").strip()
            if name:
                by_position.setdefault(position, []).append(name)
        sample = []
        for position, names in list(by_position.items())[:4]:
            sample.append(f"{position}: {', '.join(names[:5])}")
        parts.append(f"effectif synchronisé: {len(squad)} joueurs")
        if sample:
            parts.append("joueurs par poste: " + " | ".join(sample))
    recent = _coach_team_recent_matches(team.get("name") or "", matches, 4)
    if recent:
        parts.append("matchs récents/prochains: " + "; ".join(_coach_match_line(match) for match in recent))
    return " · ".join(parts)


def _coach_player_context(player: dict[str, Any]) -> str:
    parts = [f"- Joueur: {player.get('name') or 'Joueur'}"]
    if player.get("position"):
        parts.append(f"poste: {player['position']}")
    if player.get("nationality"):
        parts.append(f"nationalité: {player['nationality']}")
    if player.get("teams"):
        parts.append("équipes liées: " + ", ".join(player.get("teams")[:3]))
    if player.get("birth_date"):
        parts.append(f"naissance: {player['birth_date']}")
    if player.get("updated_at"):
        parts.append(f"maj: {player['updated_at']}")
    return " · ".join(parts)


def _coach_competition_context(competition: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    name = competition.get("name") or "Compétition"
    season = competition.get("season") or "saison non précisée"
    comp_key = _normalize_football_text(name)
    comp_matches = [match for match in matches if comp_key and comp_key in _normalize_football_text(match.get("competition", ""))]
    completed = [match for match in comp_matches if match.get("completed")]
    upcoming = [match for match in comp_matches if not match.get("completed")]
    lines = [f"- Compétition: {name} · saison {season} · matchs Supabase: {len(comp_matches)}"]
    if completed:
        lines.append("derniers résultats: " + "; ".join(_coach_match_line(match) for match in completed[:4]))
    if upcoming:
        lines.append("prochains matchs: " + "; ".join(_coach_match_line(match) for match in upcoming[:4]))
    return "\n".join(lines)


def _coach_standings_context(normalized_question: str) -> str:
    leagues = _read_json(LEAGUES_CACHE_FILE, {}).get("leagues", {})
    aliases = {
        "ligue 1": "ligue1",
        "liga": "laliga",
        "premier league": "premierleague",
        "serie a": "seriea",
        "bundesliga": "bundesliga",
    }
    selected_keys = []
    for label, key in aliases.items():
        if label in normalized_question:
            selected_keys.append(key)
    if not selected_keys and any(term in normalized_question for term in {"classement", "championnat", "championnats"}):
        selected_keys = list(leagues.keys())[:5]
    lines = []
    for key in selected_keys:
        league = leagues.get(key) or {}
        groups = league.get("standings", [])
        if groups:
            lines.append(f"- Classement {league.get('name', key)}: {_standings_summary(groups[:1])}")
    return "\n".join(lines)


def _coach_local_football_context(normalized_question: str) -> str:
    payload = _football_supabase_payload()
    terms = _coach_query_terms(normalized_question)
    if not terms and not any(term in normalized_question for term in {"classement", "champions league", "ligue des champions", "coupe du monde", "euro"}):
        return ""
    teams = _coach_pick_relevant_rows(payload.get("teams", []), terms, ["name", "short_name", "code", "country", "competition"], 4)
    players = _coach_pick_relevant_rows(payload.get("players", []), terms, ["name", "firstname", "lastname", "nationality", "position"], 5)
    coaches = _coach_pick_relevant_rows(payload.get("coaches", []), terms, ["name", "nationality"], 3)
    competitions = _coach_pick_relevant_rows(payload.get("competitions", []), terms, ["name", "type", "season"], 3)
    matches = _coach_pick_relevant_rows(payload.get("matches", []), terms, ["home_team", "away_team", "competition", "phase", "season", "status"], 6)
    all_matches = payload.get("matches", [])
    sections: list[str] = []
    if teams:
        sections.append("Équipes trouvées:\n" + "\n".join(_coach_team_context(team, all_matches) for team in teams))
    if players:
        sections.append("Joueurs trouvés:\n" + "\n".join(_coach_player_context(player) for player in players))
    if coaches:
        sections.append("Coachs trouvés:\n" + "\n".join(
            "- Coach: " + " · ".join(
                part for part in [
                    coach.get("name") or "Coach",
                    f"nationalité: {coach['nationality']}" if coach.get("nationality") else "",
                    f"maj: {coach['updated_at']}" if coach.get("updated_at") else "",
                ] if part
            )
            for coach in coaches
        ))
    if matches:
        sections.append("Matchs trouvés:\n" + "\n".join(f"- {_coach_match_line(match)}" for match in matches))
    if competitions:
        sections.append("Compétitions trouvées:\n" + "\n".join(_coach_competition_context(comp, all_matches) for comp in competitions))
    standings = _coach_standings_context(normalized_question)
    if standings:
        sections.append("Classements locaux:\n" + standings)
    if not sections:
        return ""
    counts = payload.get("counts") or {}
    header = (
        "Recherche locale Akro/Supabase utilisée. "
        f"Base disponible: {counts.get('teams', 0)} équipes, {counts.get('players', 0)} joueurs, "
        f"{counts.get('coaches', 0)} coachs, {counts.get('matches', 0)} matchs."
    )
    return (header + "\n" + "\n\n".join(sections))[:7000]


def _supabase_local_answer(normalized_question: str) -> str:
    if not normalized_question or not _supabase_service_enabled():
        return ""
    if not any(term in normalized_question for term in {"coach", "entraineur", "entraîneur", "selectionneur", "sélectionneur", "effectif", "joueur", "joueurs", "match", "calendrier", "club", "equipe", "équipe", "classement", "compare", "comparaison", "forme", "resultat", "résultat", "pronostic"}):
        return ""
    payload = _football_supabase_payload()
    words = _coach_query_terms(normalized_question)
    teams = _coach_pick_relevant_rows(payload.get("teams", []), words, ["name", "short_name", "code", "country", "competition"], 3)
    players = _coach_pick_relevant_rows(payload.get("players", []), words, ["name", "firstname", "lastname", "nationality", "position"], 2)
    matches = _coach_pick_relevant_rows(payload.get("matches", []), words, ["home_team", "away_team", "competition", "phase", "season", "status"], 5)
    if any(term in normalized_question for term in {"classement", "tableau", "leader"}):
        standings = _coach_standings_context(normalized_question)
        if standings:
            return f"Résumé : voici le classement disponible dans les données locales.\n\nDonnées utilisées :\n{standings}\n\nConclusion : je m’appuie uniquement sur le classement publié dans Akro/Supabase."
    if len(teams) >= 2 and any(term in normalized_question for term in {"compare", "comparaison", "versus", "vs", "contre"}):
        first, second = teams[0], teams[1]
        first_matches = _coach_team_recent_matches(first.get("name") or "", payload.get("matches", []), 3)
        second_matches = _coach_team_recent_matches(second.get("name") or "", payload.get("matches", []), 3)
        first_squad = len(first.get("squad") or [])
        second_squad = len(second.get("squad") or [])
        return (
            f"Résumé : comparaison locale entre {first.get('name')} et {second.get('name')}.\n\n"
            f"Données utilisées : {first.get('name')} ({first_squad} joueurs liés, coach {first.get('coach') or 'non renseigné'}); "
            f"{second.get('name')} ({second_squad} joueurs liés, coach {second.get('coach') or 'non renseigné'}).\n\n"
            f"Analyse : derniers matchs {first.get('name')} : {'; '.join(_coach_match_line(match) for match in first_matches) or 'non disponibles'}. "
            f"Derniers matchs {second.get('name')} : {'; '.join(_coach_match_line(match) for match in second_matches) or 'non disponibles'}.\n\n"
            "Conclusion : je peux comparer la dynamique, mais je reste prudent si les statistiques détaillées attaque/défense ne sont pas encore synchronisées."
        )
    team = teams[0] if teams else None
    if not team and not players and not matches:
        return ""
    if players and any(term in normalized_question for term in {"joueur", "poste", "selection", "sélection", "nation", "club", "stats", "statistiques"}):
        player = players[0]
        details = []
        if player.get("position"):
            details.append(f"poste : {player['position']}")
        if player.get("nationality"):
            details.append(f"nationalité : {player['nationality']}")
        if player.get("teams"):
            details.append("équipe(s) liée(s) : " + ", ".join(player.get("teams")[:3]))
        if player.get("birth_date"):
            details.append(f"naissance : {player['birth_date']}")
        return (
            f"Résumé : {player.get('name') or 'ce joueur'} est présent dans les données locales.\n\n"
            f"Données utilisées : {'; '.join(details) if details else 'fiche joueur partielle, statistiques détaillées absentes'}.\n\n"
            "Conclusion : je n’invente pas de total de buts ou de passes si la statistique n’est pas synchronisée."
        )
    name = team.get("name") or "cette équipe"
    if any(term in normalized_question for term in {"coach", "entraineur", "entraîneur", "selectionneur", "sélectionneur"}):
        coach = team.get("coach")
        if coach:
            return f"Résumé : {name} est entraîné par {coach}.\n\nDonnées utilisées : fiche équipe Supabase/API-Football synchronisée.\n\nConclusion : si le staff change, il faudra attendre la prochaine synchronisation pour l’actualiser."
    if any(term in normalized_question for term in {"effectif", "joueur", "joueurs"}):
        squad = team.get("squad") or []
        if squad:
            by_position: dict[str, list[str]] = {}
            for player in squad:
                if player.get("name"):
                    by_position.setdefault(str(player.get("position") or "poste non précisé"), []).append(player["name"])
            position_lines = "; ".join(f"{position}: {', '.join(names[:5])}" for position, names in list(by_position.items())[:5])
            return f"Résumé : l’effectif synchronisé de {name} contient {len(squad)} joueurs.\n\nDonnées utilisées : {position_lines or ', '.join(player.get('name', '') for player in squad[:12] if player.get('name'))}.\n\nConclusion : je peux détailler un poste précis si tu veux."
    if any(term in normalized_question for term in {"match", "calendrier", "resultat", "résultat", "forme", "pronostic"}):
        matches = [
            match for match in payload.get("matches", [])
            if name in {match.get("home_team"), match.get("away_team")}
        ][:5]
        if matches:
            lines = "; ".join(_coach_match_line(match) for match in matches)
            caution = "\n\nConclusion : pour un pronostic, je peux donner une lecture sportive prudente, jamais un conseil de pari réel." if "pronostic" in normalized_question else "\n\nConclusion : la forme récente dépend des matchs actuellement synchronisés."
            return f"Résumé : voici les matchs synchronisés pour {name}.\n\nDonnées utilisées : {lines}.{caution}"
    if team:
        squad_count = len(team.get("squad") or [])
        coach = team.get("coach") or "coach non renseigné"
        recent = _coach_team_recent_matches(name, payload.get("matches", []), 3)
        recent_line = "; ".join(_coach_match_line(match) for match in recent) if recent else "aucun match synchronisé récent/prochain"
        return (
            f"Résumé : {name} est présent dans les données locales Akro/Supabase.\n\n"
            f"Données utilisées : {team.get('type') or 'équipe'} · {team.get('country') or 'pays non renseigné'} · {squad_count} joueurs liés · {coach}. "
            f"Matchs : {recent_line}.\n\n"
            "Conclusion : je peux approfondir l’effectif, le coach, la forme ou comparer cette équipe avec une autre."
        )
    return ""


def _sync_admin_authorized(payload: dict[str, Any]) -> bool:
    admin_key = os.environ.get("WATCH_PARTY_ADMIN_KEY", "").strip()
    if not admin_key:
        return True
    return hmac.compare_digest(str(payload.get("admin_key", "")), admin_key)


def _sync_log_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "job_name": row.get("job_name"),
        "status": row.get("status"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
        "message": row.get("message") or "",
        "processed_counts": row.get("processed_counts") or {},
        "error_detail": row.get("error_detail") or "",
    }


def _parse_supabase_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _sync_last_heartbeat(row: dict[str, Any]) -> datetime | None:
    counts = row.get("processed_counts") if isinstance(row.get("processed_counts"), dict) else {}
    return (
        _parse_supabase_datetime(counts.get("heartbeat_at") if isinstance(counts, dict) else None)
        or _parse_supabase_datetime(row.get("updated_at"))
        or _parse_supabase_datetime(row.get("started_at"))
    )


def _mark_stalled_syncs() -> list[dict[str, Any]]:
    if not _supabase_service_enabled():
        return []
    try:
        import requests

        url, _ = _supabase_service_config()
        headers = _supabase_service_headers("return=representation")
        query = "sync_logs?select=id,job_name,status,started_at,updated_at,message,processed_counts,error_detail&job_name=eq.sync-football-data&status=eq.running&order=started_at.desc"
        running_response = requests.get(f"{url}/rest/v1/{query}", headers=headers, timeout=SUPABASE_TIMEOUT)
        if running_response.status_code >= 400:
            print(f"[admin-sync] lecture running impossible: {running_response.text[:220]}", flush=True)
            return []
        running = running_response.json() if running_response.content else []
        if not isinstance(running, list) or not running:
            return []

        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        stalled: list[dict[str, Any]] = []
        for row in running:
            if not isinstance(row, dict):
                continue
            heartbeat = _sync_last_heartbeat(row)
            if not heartbeat:
                continue
            age = (now_dt - heartbeat).total_seconds()
            if age < SYNC_STALL_SECONDS:
                continue
            counts = row.get("processed_counts") if isinstance(row.get("processed_counts"), dict) else {}
            last_checkpoint = (
                counts.get("current_step")
                or counts.get("last_checkpoint")
                or counts.get("heartbeat_checkpoint")
                or "étape inconnue"
            )
            stalled_counts = {
                **counts,
                "sync_timeout": True,
                "sync_timed_out": True,
                "timeout_at": now,
                "stalled_after_seconds": int(age),
                "last_heartbeat_at": heartbeat.isoformat(),
                "last_checkpoint": last_checkpoint,
            }
            payload = {
                "status": "timeout",
                "finished_at": now,
                "message": f"Synchronisation bloquée à l'étape : {last_checkpoint}",
                "error_detail": f"Aucun heartbeat ni compteur mis à jour récemment. Dernière étape connue : {last_checkpoint}. Le job a été libéré automatiquement.",
                "processed_counts": stalled_counts,
            }
            log_id = quote(str(row.get("id") or ""))
            update_response = requests.patch(
                f"{url}/rest/v1/sync_logs?id=eq.{log_id}",
                headers=headers,
                json=payload,
                timeout=SUPABASE_TIMEOUT,
            )
            if update_response.status_code >= 400:
                fallback_payload = {
                    "status": "error",
                    "finished_at": now,
                    "message": f"Synchronisation expirée à l'étape : {last_checkpoint}",
                    "error_detail": f"Timeout automatique à l'étape {last_checkpoint}. Applique football_core.sql pour autoriser le statut timeout.",
                    "processed_counts": {**stalled_counts, "timeout_fallback_status": "error"},
                }
                update_response = requests.patch(
                    f"{url}/rest/v1/sync_logs?id=eq.{log_id}",
                    headers=headers,
                    json=fallback_payload,
                    timeout=SUPABASE_TIMEOUT,
                )
            if update_response.status_code < 400:
                updated = update_response.json() if update_response.content else []
                if isinstance(updated, list) and updated:
                    stalled.extend(updated)
                else:
                    stalled.append({**row, **payload})
            else:
                print(f"[admin-sync] timeout update impossible: {update_response.text[:220]}", flush=True)
        return stalled
    except Exception as exc:
        print(f"[admin-sync] détection stalled impossible: {exc}", flush=True)
        return []


def admin_sync_logs_response() -> tuple[dict[str, Any], int]:
    if not _supabase_service_enabled():
        return {"configured": False, "logs": [], "message": "SUPABASE_SERVICE_ROLE_KEY manquante côté serveur."}, 200
    stalled_rows = _mark_stalled_syncs()
    rows = _supabase_service_request(
        "GET",
        "sync_logs?select=id,job_name,status,started_at,updated_at,finished_at,message,processed_counts,error_detail&job_name=eq.sync-football-data&order=started_at.desc&limit=20",
    )
    running_rows = _supabase_service_request(
        "GET",
        "sync_logs?select=id,status,started_at,updated_at,message&job_name=eq.sync-football-data&status=eq.running&order=started_at.desc&limit=1",
    )
    success_rows = _supabase_service_request(
        "GET",
        "sync_logs?select=id,job_name,status,started_at,updated_at,finished_at,message,processed_counts,error_detail&job_name=eq.sync-football-data&status=eq.success&order=finished_at.desc&limit=1",
    )
    if rows is None:
        return {"configured": True, "logs": [], "message": "Impossible de lire sync_logs. Vérifie que supabase/football_core.sql est appliqué."}, 200
    logs = [_sync_log_public(row) for row in rows]
    latest = logs[0] if logs else None
    latest_success = _sync_log_public(success_rows[0]) if isinstance(success_rows, list) and success_rows else next((log for log in logs if log.get("status") == "success"), None)
    has_running = isinstance(running_rows, list) and bool(running_rows)
    stale = True
    freshness_log = latest_success or latest
    if freshness_log and freshness_log.get("finished_at"):
        try:
            finished = datetime.fromisoformat(str(freshness_log["finished_at"]).replace("Z", "+00:00"))
            stale = (datetime.now(timezone.utc) - finished).total_seconds() > 36 * 3600
        except ValueError:
            stale = True
    return {"configured": True, "logs": logs, "latest": latest, "latest_success": latest_success, "has_running": has_running, "stale": stale, "stalled_marked": len(stalled_rows)}, 200


def admin_sync_run_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not _sync_admin_authorized(payload):
        return {"error": "Clé admin invalide."}, 403
    if not _supabase_service_enabled():
        return {"error": "SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant côté serveur."}, 500
    _mark_stalled_syncs()
    running = _supabase_service_request(
        "GET",
        "sync_logs?select=id,status,started_at,updated_at,message&job_name=eq.sync-football-data&status=eq.running&order=started_at.desc&limit=1",
    )
    if isinstance(running, list) and running:
        return {"error": "Une synchronisation est déjà en cours. Arrête-la ou attends sa fin avant de relancer.", "running": _sync_log_public(running[0])}, 409
    try:
        import requests

        url, key = _supabase_service_config()
        response = requests.post(
            f"{url}/functions/v1/sync-football-data",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"source": "admin-sync", "manual": True},
            timeout=60,
        )
        data = response.json() if response.content else {}
        if response.ok:
            with FOOTBALL_SUPABASE_CACHE_LOCK:
                FOOTBALL_SUPABASE_CACHE.clear()
        return {"ok": response.ok, "result": data}, response.status_code if response.status_code < 500 else 502
    except Exception as exc:
        return {"error": f"Impossible d'appeler sync-football-data : {exc}"}, 502


def admin_sync_cancel_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not _sync_admin_authorized(payload):
        return {"error": "Clé admin invalide."}, 403
    if not _supabase_service_enabled():
        return {"error": "SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant côté serveur."}, 500
    try:
        import requests

        url, _ = _supabase_service_config()
        headers = _supabase_service_headers("return=representation")
        query = "sync_logs?select=id,status,started_at,message,processed_counts&job_name=eq.sync-football-data&status=eq.running&order=started_at.desc"
        running_response = requests.get(f"{url}/rest/v1/{query}", headers=headers, timeout=SUPABASE_TIMEOUT)
        if running_response.status_code >= 400:
            return {"error": f"Impossible de lire la sync en cours : {running_response.text[:220]}"}, 500
        running = running_response.json() if running_response.content else []
        if not isinstance(running, list) or not running:
            return {"ok": False, "message": "Aucune synchronisation en cours."}, 404

        now = datetime.now(timezone.utc).isoformat()
        running_ids = [str(row.get("id") or "") for row in running if row.get("id")]
        merged_counts = {
            "cancelled_by_admin": True,
            "cancelled_jobs": len(running_ids),
            "cancelled_at": now,
        }
        cancel_payload = {
            "status": "cancelled",
            "cancel_requested": False,
            "cancelled_at": now,
            "finished_at": now,
            "message": "Synchronisation annulée par admin",
            "error_detail": "Ancienne synchronisation bloquée annulée. Les données déjà importées sont conservées.",
            "processed_counts": merged_counts,
        }
        update_response = requests.patch(
            f"{url}/rest/v1/sync_logs?job_name=eq.sync-football-data&status=eq.running",
            headers=headers,
            json=cancel_payload,
            timeout=SUPABASE_TIMEOUT,
        )
        if update_response.status_code < 400:
            updated = update_response.json() if update_response.content else []
            return {"ok": True, "message": "Synchronisation annulée", "cancelled": len(updated) or len(running_ids), "logs": [_sync_log_public(row) for row in updated] if updated else []}, 200

        fallback_payload = {
            "status": "error",
            "finished_at": now,
            "message": "Synchronisation annulée",
            "error_detail": "Annulation forcée. Applique football_core.sql pour activer le statut cancelled et l'arrêt propre par cancel_requested.",
            "processed_counts": {
                "cancelled_by_admin": True,
                "cancelled_jobs": len(running_ids),
                "cancel_fallback_status": "error",
                "cancelled_at": now,
            },
        }
        fallback_response = requests.patch(
            f"{url}/rest/v1/sync_logs?job_name=eq.sync-football-data&status=eq.running",
            headers=headers,
            json=fallback_payload,
            timeout=SUPABASE_TIMEOUT,
        )
        if fallback_response.status_code < 400:
            updated = fallback_response.json() if fallback_response.content else []
            return {"ok": True, "message": "Synchronisation annulée. Applique football_core.sql pour afficher le statut cancelled.", "cancelled": len(updated) or len(running_ids), "logs": [_sync_log_public(row) for row in updated] if updated else []}, 200
        return {"error": f"Impossible d'annuler la synchronisation : {update_response.text[:180]} / fallback: {fallback_response.text[:180]}"}, 500
    except Exception as exc:
        return {"error": f"Impossible d'annuler la synchronisation : {exc}"}, 502


def _coach_relevant_supabase_context(question: str) -> dict[str, str]:
    player_stats_context = _coach_player_stats_context(question)
    if player_stats_context:
        return {"source": "Supabase/API-Football player statistics", "context": player_stats_context}
    profile_context = _coach_entity_profile_context(question)
    if profile_context:
        return {"source": "Supabase entity_profiles", "context": profile_context}
    simple_context = _coach_entity_profile_text_context(question)
    if simple_context:
        return {"source": "Supabase entity_profiles texte", "context": simple_context}
    football_context = _coach_supabase_context(question)
    if football_context:
        return {"source": "Supabase football_core", "context": football_context}
    return {"source": "cache/fallback", "context": ""}


def _coach_entity_profile_context(question: str) -> str:
    if not question or not _supabase_service_enabled():
        return ""
    try:
        import requests

        url, key = _supabase_service_config()
        response = requests.post(
            f"{url}/functions/v1/search-entity-profiles",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"question": question, "match_count": 6},
            timeout=8,
        )
        if response.status_code >= 400:
            return ""
        data = response.json()
        rows = data.get("results") or []
        snippets = []
        for row in rows[:6]:
            summary = _clean(str(row.get("summary") or ""), 260)
            entity_type = _clean(str(row.get("entity_type") or ""), 40)
            similarity = row.get("similarity")
            score = f" · confiance {float(similarity):.2f}" if isinstance(similarity, (int, float)) else ""
            if summary:
                snippets.append(f"- {entity_type}: {summary}{score}")
        return "\n".join(snippets)
    except Exception as exc:
        print(f"[entity-profiles] fallback texte activé: {exc}", flush=True)
        return ""


def _coach_entity_profile_text_context(question: str) -> str:
    if not question or not _supabase_service_enabled():
        return ""
    words = [word for word in _normalize_football_text(question).split() if len(word) > 2]
    if not words:
        return ""
    rows = _supabase_service_request(
        "GET",
        "entity_profiles?select=entity_type,summary,searchable_text,updated_at&order=updated_at.desc&limit=120",
    ) or []
    snippets = []
    for row in rows:
        text = _normalize_football_text(f"{row.get('summary', '')} {row.get('searchable_text', '')}")
        if not text or not any(word in text for word in words):
            continue
        summary = _clean(str(row.get("summary") or row.get("searchable_text") or ""), 280)
        entity_type = _clean(str(row.get("entity_type") or "entité"), 40)
        if summary:
            snippets.append(f"- {entity_type}: {summary}")
        if len(snippets) >= 6:
            break
    return "\n".join(snippets)


def admin_sync_html() -> str:
    admin_required = bool(os.environ.get("WATCH_PARTY_ADMIN_KEY", "").strip())
    admin_input = '<input id="adminKey" type="password" placeholder="Clé admin">' if admin_required else ""
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Sync Football - Akro du Foot</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --panel:#101d2f; --gold:#f5c96b; --muted:#9fb0c6; --ok:#32d3a2; --err:#ff7373; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top, #163052, var(--bg)); color:#edf6ff; }}
    main {{ width:min(1280px, calc(100% - 32px)); margin:0 auto 0 max(16px, calc((100vw - 1280px) / 2)); padding:32px 0; display:grid; gap:18px; }}
    .hero, .card {{ border:1px solid rgba(255,255,255,.12); border-radius:18px; background:rgba(16,29,47,.82); box-shadow:0 18px 46px rgba(0,0,0,.26); }}
    .hero {{ padding:22px; }}
    h1 {{ margin:0 0 8px; font-size:clamp(28px,5vw,46px); }}
    h2 {{ margin:0 0 12px; font-size:18px; }}
    p {{ color:var(--muted); line-height:1.55; }}
    .grid {{ display:grid; grid-template-columns:minmax(260px,.8fr) minmax(320px,1.2fr); gap:12px; align-items:start; }}
    .card {{ padding:14px; }}
    .status {{ display:inline-flex; align-items:center; gap:8px; padding:7px 10px; border-radius:999px; font-weight:900; background:rgba(255,255,255,.08); }}
    .success {{ color:var(--ok); }} .error, .timeout, .stalled {{ color:var(--err); }} .running {{ color:var(--gold); }} .cancelled {{ color:var(--muted); }}
    button {{ border:0; border-radius:999px; padding:11px 16px; font-weight:950; color:#07111f; background:linear-gradient(180deg,#ffe1a0,#d5a63a); cursor:pointer; }}
    button:disabled {{ opacity:.58; cursor:wait; }}
    .stop-button {{ display:none; color:#fff; background:linear-gradient(180deg,#ff8b8b,#b92f43); box-shadow:0 10px 26px rgba(255,75,95,.22); }}
    .stop-button.is-visible {{ display:inline-flex; }}
    input {{ min-width:220px; border:1px solid rgba(255,255,255,.16); border-radius:12px; padding:11px 12px; background:rgba(255,255,255,.08); color:#fff; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }}
    .history-table-wrap {{ width:100%; overflow-x:hidden; }}
    table {{ width:100%; table-layout:fixed; border-collapse:collapse; }}
    th, td {{ padding:10px 7px; border-bottom:1px solid rgba(255,255,255,.08); text-align:left; vertical-align:top; }}
    th:nth-child(1), td:nth-child(1) {{ width:10%; }}
    th:nth-child(2), td:nth-child(2) {{ width:11%; }}
    th:nth-child(3), td:nth-child(3) {{ width:25%; }}
    th:nth-child(4), td:nth-child(4) {{ width:54%; }}
    th {{ color:var(--gold); font-size:12px; text-transform:uppercase; }}
    td .status {{ max-width:100%; justify-content:center; white-space:normal; text-align:center; line-height:1.15; padding:6px 8px; }}
    code {{ color:#ffe1a0; white-space:pre-wrap; overflow-wrap:anywhere; word-break:break-word; }}
    .counts-cell {{ display:grid; gap:8px; min-width:0; }}
    .counts-list {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:4px 10px; min-width:0; }}
    .counts-json {{ display:block; max-width:100%; padding:8px; border-radius:10px; background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.08); line-height:1.45; }}
    .history-date, .history-message {{ display:grid; gap:3px; min-width:0; }}
    .history-date strong, .history-message strong {{ color:#edf6ff; font-size:13px; line-height:1.2; overflow-wrap:anywhere; }}
    .history-date span, .history-message span {{ color:var(--muted); font-size:12px; line-height:1.2; overflow-wrap:anywhere; }}
    .muted {{ color:var(--muted); }}
    @media (max-width:800px) {{
      main {{ width:min(980px, calc(100% - 24px)); margin:0 auto; padding:22px 0; }}
      .grid {{ grid-template-columns:1fr; }}
      .history-table-wrap {{ overflow-x:visible; }}
      table, thead, tbody, tr, th, td {{ display:block; width:100%; }}
      thead {{ display:none; }}
      tr {{ margin:0 0 12px; padding:10px 12px; border:1px solid rgba(255,255,255,.1); border-radius:14px; background:rgba(255,255,255,.035); }}
      td {{ padding:7px 0; border-bottom:0; font-size:12px; }}
      td::before {{ display:block; margin-bottom:4px; color:var(--gold); font-size:10px; font-weight:950; letter-spacing:.04em; text-transform:uppercase; }}
      td:nth-child(1)::before {{ content:"Date"; }}
      td:nth-child(2)::before {{ content:"Statut"; }}
      td:nth-child(3)::before {{ content:"Message"; }}
      td:nth-child(4)::before {{ content:"Compteurs"; }}
      .counts-list {{ grid-template-columns:1fr; gap:5px; }}
      .counts-json {{ max-height:220px; overflow:auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Synchronisation football</h1>
      <p>Cette page déclenche uniquement la Edge Function serveur <code>sync-football-data</code>. Les clés Supabase et API football restent côté serveur.</p>
      <div class="actions">
        {admin_input}
        <button id="run">Mettre à jour maintenant</button>
        <button id="stop" class="stop-button">Arrêter la synchronisation</button>
        <span id="state" class="status running">Chargement des logs...</span>
      </div>
    </section>
    <section class="grid">
      <article class="card"><h2>Dernière synchronisation</h2><div id="latest" class="muted">Chargement...</div></article>
      <article class="card"><h2>Données</h2><div id="freshness" class="muted">Chargement...</div></article>
    </section>
    <section class="card">
      <h2>Historique</h2>
      <div class="history-table-wrap"><table><thead><tr><th>Date</th><th>Statut</th><th>Message</th><th>Compteurs</th></tr></thead><tbody id="logs"></tbody></table></div>
    </section>
  </main>
  <script>
    const state = document.getElementById('state');
    const latest = document.getElementById('latest');
    const freshness = document.getElementById('freshness');
    const logsBody = document.getElementById('logs');
    const button = document.getElementById('run');
    const stopButton = document.getElementById('stop');
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#39;'}}[c]));
    const fmt = value => value ? new Date(value).toLocaleString('fr-FR') : 'Non disponible';
    const statusLabel = status => ({{
      running: 'Synchronisation en cours',
      success: 'Synchronisation terminée',
      error: 'Erreur',
      cancelled: 'Synchronisation annulée',
      timeout: 'Synchronisation bloquée',
      stalled: 'Synchronisation expirée'
    }}[String(status || '')] || String(status || 'Aucune synchronisation'));
    function dateCell(value) {{
      if (!value) return '<div class="history-date"><strong>Non disponible</strong><span></span></div>';
      const date = new Date(value);
      return `<div class="history-date"><strong>${{escapeHtml(date.toLocaleDateString('fr-FR'))}}</strong><span>${{escapeHtml(date.toLocaleTimeString('fr-FR', {{hour:'2-digit', minute:'2-digit'}}))}}</span></div>`;
    }}
    function messageCell(value) {{
      const text = String(value || '').trim();
      if (!text) return '<div class="history-message"><strong>Synchronisation</strong><span>football</span></div>';
      const parts = text.split(/\\s+/);
      const first = parts.slice(0, 1).join(' ') || 'Synchronisation';
      const second = parts.slice(1).join(' ') || 'football';
      return `<div class="history-message"><strong>${{escapeHtml(first)}}</strong><span>${{escapeHtml(second)}}</span></div>`;
    }}
    function countsHtml(counts) {{
      const c = counts || {{}};
      const items = [
        ['équipes validées', c.roster_validated_teams_total || 0],
        ['nations validées', c.roster_validated_nations_total || 0],
        ['effectifs complets', c.roster_complete_total || 0],
        ['mises à jour effectifs', c.roster_updated_teams || c.player_teams_visited || c.coach_teams_visited || 0],
        ['équipes déjà à jour', c.roster_already_ok || c.roster_teams_skipped_complete || 0],
        ['nations traitées', c.roster_nations_processed || 0],
        ['clubs traités', c.roster_clubs_processed || 0],
        ['nations sans squad', c.roster_nations_without_squad || 0],
        ['joueurs trouvés', c.players_found || 0],
        ['relations candidates', c.team_player_relation_candidates || 0],
        ['relations upsertées', c.team_players_upserted || 0],
        ['joueurs non résolus', c.team_player_missing_player_ids || 0],
        ['joueurs total', c.players_total || c.players || 0],
        ['relations total', c.team_players || 0],
        ['erreurs API', c.api_errors || 0],
      ];
      return `<div class="counts-cell"><div class="counts-list">${{items.map(([label, value]) => `<span><strong>${{escapeHtml(label)}}:</strong> ${{escapeHtml(value)}}</span>`).join('')}}</div><code class="counts-json">${{escapeHtml(JSON.stringify(c, null, 2))}}</code></div>`;
    }}
    function renderLog(log) {{
      return `<tr><td>${{dateCell(log.started_at)}}</td><td><span class="status ${{escapeHtml(log.status)}}">${{escapeHtml(statusLabel(log.status))}}</span></td><td>${{messageCell(log.message || log.error_detail || '')}}</td><td>${{countsHtml(log.processed_counts)}}</td></tr>`;
    }}
    async function loadLogs() {{
      const res = await fetch('/api/admin/sync/logs', {{cache:'no-store'}});
      const data = await res.json();
      if (!data.configured) {{
        state.textContent = 'Configuration Supabase service manquante';
        latest.textContent = data.message || 'Non configuré';
        logsBody.innerHTML = '';
        return;
      }}
      const last = data.latest;
      const running = Boolean(data.has_running);
      state.textContent = last ? statusLabel(last.status) : 'Aucune synchronisation';
      state.className = `status ${{running ? 'running' : (last?.status || 'running')}}`;
      button.disabled = running;
      stopButton.classList.toggle('is-visible', running);
      stopButton.disabled = false;
      latest.innerHTML = last ? `<strong>${{escapeHtml(statusLabel(last.status))}}</strong><br>${{escapeHtml(fmt(last.finished_at || last.started_at))}}<br><span class="muted">${{escapeHtml(last.message || '')}}</span>` : 'Aucun log.';
      freshness.textContent = data.stale ? 'Données absentes ou anciennes : relance recommandée.' : 'Données synchronisées récemment.';
      logsBody.innerHTML = (data.logs || []).map(renderLog).join('') || '<tr><td colspan="4" class="muted">Aucune synchronisation enregistrée.</td></tr>';
    }}
    button.addEventListener('click', async () => {{
      button.disabled = true;
      state.textContent = 'Synchronisation en cours...';
      state.className = 'status running';
      try {{
        const res = await fetch('/api/admin/sync/run', {{
          method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body: JSON.stringify({{admin_key: document.getElementById('adminKey')?.value || ''}})
        }});
        const data = await res.json();
        state.textContent = data.ok ? 'Synchronisation terminée' : (data.error || data.result?.error || 'Erreur de synchronisation');
      }} catch (error) {{
        state.textContent = 'Erreur réseau pendant la synchronisation';
      }} finally {{
        button.disabled = false;
        await loadLogs();
      }}
    }});
    stopButton.addEventListener('click', async () => {{
      stopButton.disabled = true;
      state.textContent = 'Annulation demandée...';
      state.className = 'status running';
      try {{
        const res = await fetch('/api/admin/sync/cancel', {{
          method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body: JSON.stringify({{admin_key: document.getElementById('adminKey')?.value || ''}})
        }});
        const data = await res.json();
        state.textContent = data.ok ? 'Synchronisation annulée' : (data.error || data.message || 'Annulation impossible');
      }} catch (error) {{
        state.textContent = 'Erreur réseau pendant la demande d’annulation';
      }} finally {{
        await loadLogs();
      }}
    }});
    loadLogs();
    setInterval(loadLogs, 10000);
  </script>
</body>
</html>"""


def make_profile_password_hash(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    pseudo = _clean(str(payload.get("pseudo", "")), 48)
    password = str(payload.get("password", ""))
    if len(password) < 6 or len(password) > 72:
        return {"error": "Mot de passe invalide."}, 400
    normalized = unicodedata.normalize("NFKC", pseudo).strip().casefold()
    salt = os.urandom(16)
    material = f"{normalized}:{password}".encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", material, salt, 210_000)
    return {
        "password_hash": "pbkdf2_sha256$210000$"
        + base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
        + "$"
        + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    }, 200


def _supabase_enabled() -> bool:
    url, key = _supabase_config()
    return bool(url and key)


def _supabase_headers(prefer: str = "return=representation") -> dict[str, str]:
    _, key = _supabase_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _supabase_request(method: str, path: str, **kwargs: Any) -> Any:
    if not _supabase_enabled():
        return None
    try:
        import requests

        url, _ = _supabase_config()
        response = requests.request(
            method,
            f"{url}/rest/v1/{path.lstrip('/')}",
            headers=_supabase_headers(kwargs.pop("prefer", "return=representation")),
            timeout=SUPABASE_TIMEOUT,
            **kwargs,
        )
        if response.status_code >= 400:
            print(f"[supabase] {method} {path} failed status={response.status_code} body={response.text[:280]}")
            return None
        if not response.content:
            return []
        return response.json()
    except Exception as exc:
        print(f"[supabase] {method} {path} error: {exc}")
        return None


def _coach_messages_from_supabase(session_id: str, limit: int = 12) -> list[dict[str, str]]:
    if not session_id or not _supabase_enabled():
        return []
    rows = _supabase_request(
        "GET",
        f"coach_messages?select={SUPABASE_COACH_COLUMNS}&session_id=eq.{quote(session_id, safe='')}&order=created_at.desc&limit={int(limit)}",
    )
    if not isinstance(rows, list):
        return []
    rows = list(reversed(rows))
    out: list[dict[str, str]] = []
    for row in rows:
        role = "assistant" if str(row.get("role", "")).lower() == "assistant" else "user"
        content = _clean(row.get("content", ""), 1200)
        if content:
            out.append({"role": role, "content": content})
    return out


def _save_coach_message_supabase(session_id: str, role: str, content: str, detected_entity: str = "", detected_intent: str = "") -> None:
    if not session_id or not _supabase_enabled():
        return
    payload = {
        "session_id": _clean(session_id, 120),
        "role": "assistant" if role == "assistant" else "user",
        "content": _clean(content, 2400),
        "detected_entity": _clean(detected_entity, 120),
        "detected_intent": _clean(detected_intent, 80),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    saved = _supabase_request("POST", "coach_messages", json=payload)
    if saved is None:
        print(f"[coach] Supabase save message failed session_id={session_id}")


def _search_short_answer(text: str) -> str:
    clean = " ".join(str(text or "").split())
    if not clean:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    return " ".join(sentences[:3]).strip()[:420]


def _search_ai_answer_get(normalized_query: str) -> dict[str, Any] | None:
    if not _supabase_enabled():
        return None
    row = _supabase_request(
        "GET",
        f"search_ai_answers?select=id,answer,usage_count,entity_type&normalized_query=eq.{quote(normalized_query, safe='')}&order=created_at.desc&limit=1",
    )
    if row is None:
        row = _supabase_request(
            "GET",
            f"search_ai_answers?select=id,answer,usage_count&normalized_query=eq.{quote(normalized_query, safe='')}&order=created_at.desc&limit=1",
        )
    if isinstance(row, list) and row:
        return row[0]
    return None


def _search_ai_answer_increment_usage(answer_id: Any) -> None:
    if answer_id is None or not _supabase_enabled():
        return
    current = _supabase_request("GET", f"search_ai_answers?select=usage_count&id=eq.{quote(str(answer_id), safe='')}&limit=1")
    if not isinstance(current, list) or not current:
        return
    count = int(current[0].get("usage_count", 0) or 0) + 1
    _supabase_request("PATCH", f"search_ai_answers?id=eq.{quote(str(answer_id), safe='')}", json={"usage_count": count})


def _search_ai_answer_upsert(query: str, normalized_query: str, answer: str, entity_type: str = "") -> None:
    if not _supabase_enabled() or not answer:
        return
    payload = {
        "query": query,
        "normalized_query": normalized_query,
        "answer": answer,
        "entity_type": entity_type or None,
        "usage_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    saved = _supabase_request("POST", "search_ai_answers", json=payload)
    if saved is None and entity_type:
        payload.pop("entity_type", None)
        saved = _supabase_request("POST", "search_ai_answers", json=payload)
    if saved is None:
        print(f"[search-coach] Supabase save failed for normalized_query='{normalized_query}'")


def _read_supabase_community(matches: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not _supabase_enabled():
        return {"available": False}
    profiles = _supabase_request("GET", f"profiles?select={SUPABASE_PROFILE_COLUMNS}&order=created_at.desc")
    predictions = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&order=created_at.desc")
    if profiles is None or predictions is None:
        return {"available": False}
    profile_by_id = {str(profile.get("id")): profile for profile in profiles if profile.get("id") is not None}
    profile_by_pseudo = {str(profile.get("pseudo")): profile for profile in profiles if profile.get("pseudo")}
    brackets = _supabase_request("GET", "user_brackets?select=profile_id,likes_count,dislikes_count&is_published=eq.true") or []
    bracket_votes_by_profile: dict[str, dict[str, int]] = {}
    for bracket in brackets if isinstance(brackets, list) else []:
        profile_id = str(bracket.get("profile_id") or "")
        if not profile_id:
            continue
        totals = bracket_votes_by_profile.setdefault(profile_id, {"likes": 0, "dislikes": 0})
        totals["likes"] += int(bracket.get("likes_count") or 0)
        totals["dislikes"] += int(bracket.get("dislikes_count") or 0)
    for profile in profiles:
        totals = bracket_votes_by_profile.get(str(profile.get("id") or ""), {})
        profile["bracket_likes_received"] = totals.get("likes", 0)
        profile["bracket_dislikes_received"] = totals.get("dislikes", 0)
    normalized_predictions = [_prediction_from_supabase(row, profile_by_id) for row in predictions]
    return {
        "available": True,
        "users": profiles,
        "predictions": normalized_predictions,
        "badges": _read_supabase_badges_by_user(profile_by_id, profile_by_pseudo),
    }


def _prediction_from_supabase(row: dict[str, Any], user_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    profile_id = row.get("profile_id") or row.get("user_id")
    user = user_by_id.get(str(profile_id), {})
    return {
        "id": row.get("id"),
        "user_id": profile_id,
        "pseudo": row.get("pseudo") or user.get("pseudo") or "",
        "match_id": row.get("match_id", ""),
        "home_score": row.get("predicted_home_score", row.get("home_score")),
        "away_score": row.get("predicted_away_score", row.get("away_score")),
        "stored_actual_home_score": row.get("actual_home_score"),
        "stored_actual_away_score": row.get("actual_away_score"),
        "stored_status": row.get("status"),
        "stored_points": row.get("points", 0),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }


def _read_supabase_badges_by_user(user_by_id: dict[str, dict[str, Any]], user_by_pseudo: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows = _supabase_request("GET", f"profile_badges?select={SUPABASE_PROFILE_BADGE_COLUMNS}&order=unlocked_at.asc")
    if rows is None:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        user = user_by_id.get(str(row.get("profile_id")), {})
        pseudo = str(user.get("pseudo") or row.get("pseudo") or "")
        badge = {
            "name": row.get("badge_name") or row.get("badge_key") or "Badge",
            "badge_key": row.get("badge_key"),
            "earned_at": row.get("unlocked_at"),
        }
        if pseudo:
            out.setdefault(pseudo, []).append(badge)
    return out


def _supabase_badge_catalog() -> dict[str, dict[str, Any]]:
    return {}


def _save_prediction_supabase(pseudo: str, match_id: str, home_score: int, away_score: int, matches: dict[str, dict[str, Any]]) -> bool:
    if not _supabase_enabled():
        return False
    user = _supabase_get_or_create_user(pseudo)
    if not user:
        return False
    match = matches.get(match_id)
    points = _points({"match_id": match_id, "home_score": home_score, "away_score": away_score}, match)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    profile_id = str(user.get("id") or "")
    existing = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&profile_id=eq.{quote(profile_id, safe='')}&match_id=eq.{quote(match_id, safe='')}&limit=1")
    payload = {
        "profile_id": profile_id,
        "pseudo": pseudo or "Utilisateur",
        "match_id": match_id,
        "home_team": str((match or {}).get("home_team") or ""),
        "away_team": str((match or {}).get("away_team") or ""),
        "predicted_home_score": home_score,
        "predicted_away_score": away_score,
        "actual_home_score": _to_score((match or {}).get("home_score")),
        "actual_away_score": _to_score((match or {}).get("away_score")),
        "status": "completed" if (match or {}).get("completed") else "pending",
        "points": points,
    }
    if existing:
        saved = _supabase_request("PATCH", f"predictions?id=eq.{quote(str(existing[0].get('id')), safe='')}", json=payload)
    else:
        payload["created_at"] = now
        saved = _supabase_request("POST", "predictions", json=payload)
    if saved is None:
        return False
    _sync_supabase_user_totals(profile_id, pseudo, matches)
    return True


def _supabase_get_or_create_user(pseudo: str) -> dict[str, Any] | None:
    existing = _supabase_request("GET", f"profiles?select={SUPABASE_PROFILE_COLUMNS}&pseudo=eq.{quote(pseudo, safe='')}&limit=1")
    if existing:
        return existing[0]
    print("[supabase] profil introuvable par pseudo; création serveur ignorée car profiles.id doit venir de Supabase Auth")
    return None


def _sync_supabase_user_totals(user_id: str, pseudo: str, matches: dict[str, dict[str, Any]]) -> None:
    rows = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&profile_id=eq.{quote(user_id, safe='')}")
    if rows is None:
        return
    predictions = [_prediction_from_supabase(row, {user_id: {"pseudo": pseudo}}) for row in rows]
    scored = _predictions_with_points(predictions, matches)
    points = sum(int(item.get("points", 0) or 0) for item in scored)
    count = len(scored)
    completed = [item for item in scored if matches.get(str(item.get("match_id", "")), {}).get("completed")]
    correct = len([item for item in completed if int(item.get("points", 0) or 0) > 0])
    success_rate = round((correct / len(completed)) * 100) if completed else 0
    level = _community_level(count)
    patch = {
        "profile_id": user_id,
        "total_predictions": count,
        "correct_scores": len([item for item in completed if int(item.get("points", 0) or 0) >= 3]),
        "correct_results": correct,
        "total_points": points,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    existing = _supabase_request("GET", f"profile_stats?select={SUPABASE_PROFILE_STATS_COLUMNS}&profile_id=eq.{quote(user_id, safe='')}&limit=1")
    if existing:
        _supabase_request("PATCH", f"profile_stats?profile_id=eq.{quote(user_id, safe='')}", json=patch)
    else:
        _supabase_request("POST", "profile_stats", json=patch)
    _award_supabase_badge(user_id, level)
    _sync_supabase_prediction_points(scored, matches)


def _sync_supabase_prediction_points(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]] | None = None) -> set[tuple[str, str]]:
    changed_profiles: set[tuple[str, str]] = set()
    for prediction in predictions:
        prediction_id = prediction.get("id")
        if prediction_id is None:
            continue
        match = (matches or {}).get(str(prediction.get("match_id", "")))
        patch: dict[str, Any] = {}
        points = int(prediction.get("points", 0) or 0)
        if int(prediction.get("stored_points", -1) or -1) != points:
            patch["points"] = points
        if match:
            actual_home = _to_score(match.get("home_score"))
            actual_away = _to_score(match.get("away_score"))
            status = "completed" if match.get("completed") else "pending"
            if _to_score(prediction.get("stored_actual_home_score")) != actual_home:
                patch["actual_home_score"] = actual_home
            if _to_score(prediction.get("stored_actual_away_score")) != actual_away:
                patch["actual_away_score"] = actual_away
            if str(prediction.get("stored_status") or "") != status:
                patch["status"] = status
        if not patch:
            continue
        saved = _supabase_request("PATCH", f"predictions?id=eq.{quote(str(prediction_id), safe='')}", json=patch)
        if saved is not None and prediction.get("user_id") and ("points" in patch or patch.get("status") == "completed"):
            changed_profiles.add((str(prediction.get("user_id")), str(prediction.get("pseudo") or "Utilisateur")))
    return changed_profiles


def _award_supabase_badge(user_id: str, level: dict[str, Any]) -> None:
    badge_key = str(level.get("level") or level.get("badge") or "badge")
    existing = _supabase_request("GET", f"profile_badges?select={SUPABASE_PROFILE_BADGE_COLUMNS}&profile_id=eq.{quote(user_id, safe='')}&badge_key=eq.{quote(badge_key, safe='')}&limit=1")
    if existing:
        return
    _supabase_request(
        "POST",
        "profile_badges",
        json={"profile_id": user_id, "badge_key": badge_key, "badge_name": str(level.get("level") or "Badge"), "unlocked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    )


def _ensure_supabase_badge(level: dict[str, Any]) -> dict[str, Any] | None:
    return None


def _icon_content_type(path: str) -> str:
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".svg"):
        return "image/svg+xml; charset=utf-8"
    return "application/octet-stream"


def _read_community() -> dict[str, Any]:
    data = _read_json(COMMUNITY_FILE, {"messages": [], "predictions": []})
    data.setdefault("messages", [])
    data.setdefault("predictions", [])
    data.setdefault("watch_messages", [])
    return data


def _write_community(data: dict[str, Any]) -> None:
    COMMUNITY_FILE.parent.mkdir(exist_ok=True)
    COMMUNITY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _dashboard_matches(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for group in data.get("group_matches", []):
        for match in group.get("matches", []):
            _add_match(matches, match, group.get("name", "Poules"))
    for round_data in data.get("knockout", []):
        for match in round_data.get("matches", []):
            _add_match(matches, match, round_data.get("name", "Élimination"))
    return matches


def _all_dashboard_matches(worldcup_data: dict[str, Any], champions_data: dict[str, Any], leagues_data: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for match_id, match in _dashboard_matches(worldcup_data).items():
        matches[f"worldcup:{match_id}"] = {**match, "id": f"worldcup:{match_id}", "competition": "Coupe du Monde"}
    for match_id, match in _dashboard_matches(champions_data).items():
        matches[f"champions:{match_id}"] = {**match, "id": f"champions:{match_id}", "competition": "Ligue des Champions"}
    for league_key, league in (leagues_data or {}).get("leagues", {}).items():
        for match_id, match in _dashboard_matches(league).items():
            prefix = f"league-{league_key}:{match_id}"
            matches[prefix] = {**match, "id": prefix, "competition": league.get("name", "Championnat")}
    return matches


def _add_match(out: dict[str, dict[str, Any]], match: dict[str, Any], phase: str) -> None:
    match_id = str(match.get("id") or f"{phase}-{match.get('home_team')}-{match.get('away_team')}-{match.get('date')}")
    match = _apply_prediction_match_overrides(match, phase)
    out[match_id] = {
        "id": match_id,
        "phase": phase,
        "date": match.get("date", ""),
        "home_team": match.get("home_team", "À déterminer"),
        "away_team": match.get("away_team", "À déterminer"),
        "home_flag_url": match.get("home_flag_url", ""),
        "away_flag_url": match.get("away_flag_url", ""),
        "home_score": match.get("home_score", ""),
        "away_score": match.get("away_score", ""),
        "status": match.get("status", ""),
        "completed": bool(match.get("completed")),
        "winner_team": match.get("winner_team", ""),
        "winner_side": match.get("winner_side", ""),
        "penalty_home_score": match.get("penalty_home_score", ""),
        "penalty_away_score": match.get("penalty_away_score", ""),
        "locked": _is_locked(match),
    }


def _normalized_match_team(value: Any) -> str:
    return re.sub(r"\s+", " ", _normalize_football_text(value)).strip()


def _apply_prediction_match_overrides(match: dict[str, Any], phase: str) -> dict[str, Any]:
    home = _normalized_match_team(match.get("home_team"))
    away = _normalized_match_team(match.get("away_team"))
    is_champions_final = (
        str(match.get("id") or "") == "401862897"
        or (
            "final" in _normalize_football_text(phase)
            and home in {"paris saint germain", "psg", "paris sg"}
            and away == "arsenal"
            and str(match.get("date") or "").startswith("2026-05-30")
        )
    )
    if not is_champions_final:
        return match
    return {
        **match,
        "home_score": 1,
        "away_score": 1,
        "status": "Terminé",
        "status_state": "post",
        "completed": True,
        "winner_team": match.get("home_team") or "Paris Saint-Germain",
        "winner_side": "home",
        "penalty_home_score": 4,
        "penalty_away_score": 3,
    }


def _predictions_with_points(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**prediction, "points": _points(prediction, matches.get(prediction.get("match_id", "")))} for prediction in predictions]


def _leaderboard(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]] | None = None, badges: dict[str, list[dict[str, Any]]] | None = None, users: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    profiles = _community_profiles(predictions, matches or {}, badges)
    if users:
        _enrich_profiles_with_supabase_users(profiles, users)
    rows = sorted(profiles.values(), key=lambda item: (-int(item.get("points", 0)), -int(item.get("exact_scores", 0)), str(item.get("pseudo", "")).lower()))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _community_profiles(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]], badges: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        pseudo = _clean(prediction.get("pseudo", ""), 32)
        if not pseudo:
            continue
        profile = profiles.setdefault(pseudo, _empty_profile(pseudo))
        points = int(prediction.get("points", 0) or 0)
        profile["points"] += points
        profile["predictions_count"] += 1
        if points == 3:
            profile["exact_scores"] += 1
            profile["correct_results"] += 1
        elif points == 1:
            profile["correct_results"] += 1
        match = matches.get(str(prediction.get("match_id", ""))) if matches else None
        profile["history"].append(_profile_prediction_row(prediction, match, points))
    for profile in profiles.values():
        completed = [item for item in profile["history"] if item.get("completed")]
        completed_count = len(completed)
        profile["completed_predictions"] = completed_count
        profile["success_rate"] = round((profile["correct_results"] / completed_count) * 100) if completed_count else 0
        level = _community_level(profile["predictions_count"], badges.get(str(profile.get("pseudo", "")), []) if badges else None)
        profile.update(level)
        profile["recent_predictions"] = sorted(profile["history"], key=lambda item: str(item.get("created_at", "")), reverse=True)[:12]
    return profiles


def _enrich_profiles_with_supabase_users(profiles: dict[str, dict[str, Any]], users: list[dict[str, Any]]) -> None:
    for user in users or []:
        pseudo = _clean(user.get("pseudo", ""), 32)
        if not pseudo or pseudo not in profiles:
            continue
        profile = profiles[pseudo]
        if user.get("id"):
            profile["id"] = user.get("id")
        for key in ("avatar_url", "favorite_club", "favorite_club_logo", "favorite_nation", "favorite_nation_flag", "bracket_likes_received", "bracket_dislikes_received"):
            if user.get(key) is not None:
                profile[key] = user.get(key)


def _empty_profile(pseudo: str) -> dict[str, Any]:
    level = _community_level(0)
    return {
        "pseudo": pseudo,
        "points": 0,
        "predictions_count": 0,
        "completed_predictions": 0,
        "correct_results": 0,
        "exact_scores": 0,
        "success_rate": 0,
        "history": [],
        "recent_predictions": [],
        **level,
    }


def _community_level(predictions_count: int, awarded_badges: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    index = max(0, min(len(COMMUNITY_LEVELS) - 1, predictions_count // 10))
    level_name, badge, icon = COMMUNITY_LEVELS[index]
    next_goal = (index + 1) * 10 if index < len(COMMUNITY_LEVELS) - 1 else predictions_count
    badges = awarded_badges or []
    current_badge = badges[-1] if badges else {}
    return {
        "level_index": index + 1,
        "level": str(current_badge.get("name") or level_name),
        "badge": str(current_badge.get("badge") or current_badge.get("name") or badge),
        "badge_icon": str(current_badge.get("icon") or icon),
        "badges": badges,
        "next_level_at": next_goal,
    }


def _profile_prediction_row(prediction: dict[str, Any], match: dict[str, Any] | None, points: int) -> dict[str, Any]:
    home = match.get("home_team", "Match") if match else "Match"
    away = match.get("away_team", "inconnu") if match else "inconnu"
    real_score = ""
    completed = bool(match and match.get("completed"))
    if match and match.get("home_score", "") != "" and match.get("away_score", "") != "":
        real_score = f"{match.get('home_score')} - {match.get('away_score')}"
    return {
        "match_id": prediction.get("match_id", ""),
        "competition": match.get("competition", "") if match else "",
        "date": match.get("date", "") if match else "",
        "home_team": home,
        "away_team": away,
        "prediction": f"{prediction.get('home_score', '')} - {prediction.get('away_score', '')}",
        "real_score": real_score,
        "status": match.get("status", "") if match else "",
        "completed": completed,
        "points": points,
        "created_at": prediction.get("created_at", ""),
    }


def _points(prediction: dict[str, Any], match: dict[str, Any] | None) -> int:
    if not match or not match.get("completed"):
        return 0
    real_home = _to_score(match.get("home_score"))
    real_away = _to_score(match.get("away_score"))
    pred_home = _to_score(prediction.get("home_score"))
    pred_away = _to_score(prediction.get("away_score"))
    if None in (real_home, real_away, pred_home, pred_away):
        return 0
    if pred_home == real_home and pred_away == real_away:
        return 3
    winner_side = str(match.get("winner_side") or "").lower()
    if winner_side in {"home", "away"}:
        predicted_side = "draw" if pred_home == pred_away else "home" if pred_home > pred_away else "away"
        return 1 if predicted_side == winner_side else 0
    return 1 if _result(pred_home, pred_away) == _result(real_home, real_away) else 0


def _result(home: int, away: int) -> str:
    if home == away:
        return "draw"
    return "home" if home > away else "away"


def _is_locked(match: dict[str, Any]) -> bool:
    if match.get("completed") or match.get("status_state") == "in":
        return True
    try:
        date = datetime.fromisoformat(str(match.get("date", "")).replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) >= date


def _to_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 99 else None


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_color(value: Any) -> str:
    color = str(value or "").strip()
    if len(color) == 7 and color.startswith("#"):
        try:
            int(color[1:], 16)
            return color
        except ValueError:
            pass
    return "#bfe6ff"


def save_watch_message(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    pseudo = _clean(payload.get("pseudo", ""), 32)
    text = _clean(payload.get("message", ""), 500)
    if not pseudo or not text:
        return {"error": "Pseudo et message obligatoires."}, 400
    community = _read_community()
    community.setdefault("watch_messages", []).append(
        {
            "pseudo": pseudo,
            "message": text,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    community["watch_messages"] = community["watch_messages"][-300:]
    _write_community(community)
    return {"ok": True}, 200


def _watch_messages() -> list[dict[str, Any]]:
    return _read_community().get("watch_messages", [])


def make_livekit_token(pseudo: str, role: str) -> tuple[dict[str, Any], int]:
    api_key = os.environ.get("LIVEKIT_API_KEY", "")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "")
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    if not api_key or not api_secret or not livekit_url:
        return {"error": "Configuration LiveKit manquante."}, 503
    token = _livekit_jwt(api_key, api_secret, pseudo, role)
    return {"token": token, "url": livekit_url, "room": WATCH_ROOM, "role": role}, 200


def _livekit_jwt(api_key: str, api_secret: str, pseudo: str, role: str) -> str:
    now = int(time.time())
    identity = f"{role}-{_slug(pseudo)}-{now}"
    grants = {
        "roomJoin": True,
        "room": WATCH_ROOM,
        "canSubscribe": True,
        "canPublish": role == "admin",
        "canPublishData": True,
        "canPublishSources": ["screen_share", "screen_share_audio"] if role == "admin" else [],
    }
    payload = {
        "iss": api_key,
        "sub": identity,
        "name": pseudo,
        "nbf": now - 10,
        "exp": now + 60 * 60 * 6,
        "video": grants,
    }
    header = {"alg": "HS256", "typ": "JWT"}
    body = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = hmac.new(api_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def _b64_json(value: dict[str, Any]) -> str:
    return _b64(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return slug or "invite"


def _is_admin_key(value: str) -> bool:
    expected = os.environ.get("WATCH_PARTY_ADMIN_KEY", "")
    return bool(expected) and hmac.compare_digest(value, expected)


def _url_decode(value: str) -> str:
    from urllib.parse import unquote_plus

    return unquote_plus(value)


def watch_party_html() -> str:
    return """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Watch Party Coupe du Monde 2026</title>
  <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
  <style>
    :root { color-scheme: dark; --ink:#eef5ff; --muted:#9fb0c2; --line:rgba(255,255,255,.14); --gold:#f5c96b; --red:#ef3340; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; color:var(--ink); font-family:Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 20% 10%, rgba(31,111,235,.38), transparent 24rem), linear-gradient(180deg,#06101e,#07111f); }
    main { width:min(1320px, calc(100% - 24px)); margin:0 auto; padding:22px 0 36px; }
    .top { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; margin-bottom:16px; }
    h1 { margin:0; font-size:clamp(30px,5vw,58px); line-height:1; }
    .badge { display:inline-flex; align-items:center; gap:8px; border:1px solid rgba(245,201,107,.35); background:rgba(245,201,107,.1); color:#ffe1a0; border-radius:999px; padding:8px 11px; font-weight:900; }
    .layout { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:16px; }
    .panel { border:1px solid var(--line); border-radius:18px; background:linear-gradient(180deg,rgba(255,255,255,.1),rgba(255,255,255,.055)); box-shadow:0 24px 70px rgba(0,0,0,.34); overflow:hidden; }
    .video-wrap { min-height:62vh; display:grid; place-items:center; background:radial-gradient(circle at center, rgba(245,201,107,.12), transparent 22rem), #050c16; }
    #screenStage video { width:100%; height:100%; max-height:72vh; object-fit:contain; background:#000; }
    .empty { color:var(--muted); text-align:center; padding:20px; }
    .controls, .chat-form, .join-form { display:grid; gap:10px; padding:14px; border-top:1px solid var(--line); }
    .join-form { grid-template-columns:1fr 130px 1fr auto; border-top:0; }
    input, select, textarea, button { font:inherit; border-radius:10px; border:1px solid rgba(255,255,255,.16); padding:10px 11px; color:var(--ink); background:rgba(255,255,255,.08); }
    button { cursor:pointer; font-weight:900; background:rgba(245,201,107,.14); color:#ffe1a0; }
    button[disabled] { opacity:.48; cursor:not-allowed; }
    .admin-actions { display:flex; flex-wrap:wrap; gap:10px; }
    .help { color:var(--muted); font-size:13px; line-height:1.45; }
    .chat { display:grid; grid-template-rows:auto 1fr auto; max-height:78vh; }
    .chat h2 { margin:0; padding:15px; border-bottom:1px solid var(--line); }
    .messages { overflow:auto; padding:14px; display:grid; align-content:start; gap:10px; min-height:320px; }
    .message { border:1px solid rgba(255,255,255,.1); background:rgba(255,255,255,.055); border-radius:12px; padding:10px; }
    .message-top { display:flex; justify-content:space-between; gap:10px; color:var(--muted); font-size:12px; margin-bottom:5px; }
    .status { color:#ffe1a0; min-height:18px; font-size:13px; }
    a { color:#bfe6ff; }
    @media (max-width: 900px) { .layout { grid-template-columns:1fr; } .join-form { grid-template-columns:1fr; } .chat { max-height:none; } }
  </style>
</head>
<body>
  <main>
    <div class="top">
      <div>
        <div class="badge">Watch Party en direct</div>
        <h1>LIVE</h1>
      </div>
      <a class="badge" href="/">Retour dashboard</a>
    </div>
    <section class="panel join-form">
      <input id="pseudo" placeholder="Pseudo" autocomplete="nickname">
      <select id="role"><option value="viewer">Spectateur</option><option value="admin">Admin</option></select>
      <input id="adminKey" placeholder="Clé admin" type="password">
      <button id="joinButton">Rejoindre</button>
    </section>
    <div class="layout">
      <section class="panel">
        <div class="video-wrap" id="screenStage"><div class="empty">En attente du partage d’écran admin.</div></div>
        <div class="controls">
          <div class="admin-actions">
            <button id="startShare" disabled>Démarrer le partage</button>
            <button id="stopShare" disabled>Arrêter le partage</button>
          </div>
          <div class="help">Pour partager le son, sélectionnez un onglet Chrome et cochez Partager l’audio de l’onglet. Les spectateurs peuvent seulement regarder, écouter et écrire dans le tchat.</div>
          <div class="status" id="status"></div>
        </div>
      </section>
      <aside class="panel chat">
        <h2>Tchat en direct</h2>
        <div class="messages" id="watchMessages"></div>
        <form class="chat-form" id="watchChatForm">
          <textarea id="watchMessage" maxlength="500" placeholder="Question ou réaction"></textarea>
          <button type="submit">Envoyer</button>
        </form>
      </aside>
    </div>
  </main>
  <script>
    const statusEl = document.getElementById('status');
    const stage = document.getElementById('screenStage');
    const startButton = document.getElementById('startShare');
    const stopButton = document.getElementById('stopShare');
    const joinButton = document.getElementById('joinButton');
    const messagesEl = document.getElementById('watchMessages');
    let room;
    let currentRole = 'viewer';

    function setStatus(text) { statusEl.textContent = text || ''; }
    function esc(value) { return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function shortDate(value) { const d = new Date(value); return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'}); }

    async function joinRoom() {
      const pseudo = document.getElementById('pseudo').value.trim() || 'Invite';
      const role = document.getElementById('role').value;
      const adminKey = document.getElementById('adminKey').value;
      const params = new URLSearchParams({pseudo, role, admin_key: adminKey});
      const response = await fetch(`/api/livekit-token?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Connexion impossible');
      currentRole = data.role;
      room = new LivekitClient.Room();
      room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === LivekitClient.Track.Kind.Video || track.kind === LivekitClient.Track.Kind.Audio) {
          const element = track.attach();
          if (track.kind === LivekitClient.Track.Kind.Video) stage.innerHTML = '';
          stage.appendChild(element);
        }
      });
      room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach(el => el.remove()));
      await room.connect(data.url, data.token);
      startButton.disabled = currentRole !== 'admin';
      stopButton.disabled = currentRole !== 'admin';
      setStatus(currentRole === 'admin' ? 'Connecté en admin.' : 'Connecté en spectateur.');
      loadWatchChat();
    }

    async function startShare() {
      if (!room || currentRole !== 'admin') return;
      await room.localParticipant.setScreenShareEnabled(true, {audio: true});
      setStatus('Partage d’écran démarré.');
    }

    async function stopShare() {
      if (!room || currentRole !== 'admin') return;
      await room.localParticipant.setScreenShareEnabled(false);
      setStatus('Partage arrêté.');
    }

    async function loadWatchChat() {
      const response = await fetch('/api/watch-chat');
      const data = await response.json();
      messagesEl.innerHTML = data.messages && data.messages.length ? data.messages.slice().reverse().map(msg => `
        <article class="message"><div class="message-top"><strong>${esc(msg.pseudo)}</strong><span>${shortDate(msg.created_at)}</span></div><div>${esc(msg.message)}</div></article>
      `).join('') : '<div class="empty">Aucun message pour le moment.</div>';
    }

    joinButton.addEventListener('click', async () => {
      try { await joinRoom(); } catch (error) { setStatus(error.message); }
    });
    startButton.addEventListener('click', async () => {
      try { await startShare(); } catch (error) { setStatus(error.message); }
    });
    stopButton.addEventListener('click', async () => {
      try { await stopShare(); } catch (error) { setStatus(error.message); }
    });
    document.getElementById('watchChatForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      const pseudo = document.getElementById('pseudo').value.trim() || 'Invite';
      const message = document.getElementById('watchMessage').value;
      const response = await fetch('/api/watch-chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pseudo, message})});
      if (response.ok) document.getElementById('watchMessage').value = '';
      loadWatchChat();
    });
    setInterval(loadWatchChat, 3000);
    loadWatchChat();
  </script>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    if app:
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        print(f"Flask non installé : serveur Python intégré lancé sur http://0.0.0.0:{port}")
        ThreadingHTTPServer(("0.0.0.0", port), CommunityHandler).serve_forever()
