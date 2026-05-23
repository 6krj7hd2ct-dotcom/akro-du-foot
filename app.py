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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

try:
    from flask import Flask, Response, jsonify, request, send_file
except ImportError:
    Flask = None
    Response = None
    jsonify = None
    request = None
    send_file = None

from src.config import BASE_DIR, CACHE_FILE, CHAMPIONS_LEAGUE_CACHE_FILE, LEAGUES_CACHE_FILE, MERCATO_LIVE_CACHE_FILE, NEWS_CACHE_FILE, OUTPUT_HTML
from src.fetchers import fetch_all_news, fetch_champions_league_news, fetch_france_header_news, fetch_league_news, fetch_world_cup_news, filter_news_articles, rank_articles, dedupe_articles

COMMUNITY_FILE = BASE_DIR / "data" / "community.json"
WATCH_ROOM = "worldcup-watch-party"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
COACH_REFUSAL = "Je suis Coach, je réponds uniquement aux questions liées au football."
COACH_UNAVAILABLE = "Coach indisponible : clé OpenAI absente ou invalide."
COACH_DISCLAIMER = "Analyse fictive pour le jeu entre amis. Aucun conseil de pari réel."

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
SUPABASE_USER_COLUMNS = "id,pseudo,total_points,predictions_count,current_badge,success_rate,created_at,updated_at"
SUPABASE_PREDICTION_COLUMNS = "id,user_id,pseudo,match_id,home_score,away_score,points,created_at,updated_at"
SUPABASE_BADGE_COLUMNS = "id,name,level,icon,min_predictions"
SUPABASE_COACH_COLUMNS = "id,session_id,role,content,detected_entity,detected_intent,created_at"
BUILD_VERSION_TOKEN = "__AKRO_BUILD_VERSION__"
NO_STORE_CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"

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
    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    leagues_dashboard = _read_json(LEAGUES_CACHE_FILE, {})
    community = _read_community()
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard, leagues_dashboard)
    supabase = _read_supabase_community(matches)
    source_predictions = supabase.get("predictions") if supabase.get("available") else community.get("predictions", [])
    predictions = _predictions_with_points(source_predictions or [], matches)
    profiles = _community_profiles(predictions, matches, supabase.get("badges", {}))
    leaderboard = _leaderboard(predictions, matches, supabase.get("badges", {}))
    return {
        "messages": community.get("messages", [])[-100:],
        "predictions": predictions,
        "leaderboard": leaderboard,
        "profiles": profiles,
        "matches": list(matches.values()),
        "storage": "supabase" if supabase.get("available") else "json",
    }


if app:
    @app.get("/api/community")
    def get_community():
        return jsonify(community_payload())

    @app.get("/api/supabase-public-config")
    def supabase_public_config():
        url, key = _supabase_config()
        return jsonify({"url": url, "anon_key": key, "configured": bool(url and key)})

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

    @app.get("/api/mercato-live")
    def mercato_live():
        return jsonify(_read_json(MERCATO_LIVE_CACHE_FILE, {"items": [], "source": "Mercato Live", "url": "https://www.mercatolive.fr/"}))

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


def football_chatbot_response(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    question = _clean(payload.get("message", ""), 500)
    history = _chat_history(payload.get("history", []))
    session_id = _clean(payload.get("session_id", ""), 120)
    client_context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    merged_history = history[-12:]
    if session_id:
        merged_history = _chat_history(_coach_messages_from_supabase(session_id, 12) + merged_history)[-12:]
    context_state = _detect_conversation_context(merged_history, question, client_context)
    resolved_question = _resolve_followup_question(question, context_state)
    if not question:
        return {"error": "Question vide."}, 400
    if session_id:
        _save_coach_message_supabase(session_id, "user", question, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
    if not _looks_like_football_question(resolved_question, merged_history):
        return {"answer": COACH_REFUSAL}, 200

    local_answer = _local_coach_answer(resolved_question, merged_history)
    if local_answer:
        answer = _format_coach_answer(local_answer)
        if session_id:
            _save_coach_message_supabase(session_id, "assistant", answer, context_state.get("lastEntity", ""), context_state.get("lastIntent", ""))
        return {"answer": answer, "detected_context": context_state, "resolved_question": resolved_question}, 200

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"error": COACH_UNAVAILABLE}, 503

    context = _coach_context_summary()
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
        return {"answer": answer or COACH_UNAVAILABLE, "detected_context": context_state, "resolved_question": resolved_question}, 200
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

    cached = _search_ai_answer_get(normalized_query)
    if cached:
        _search_ai_answer_increment_usage(cached.get("id"))
        return {
            "answer": str(cached.get("answer", "")),
            "source": "supabase",
            "cached": True,
            "normalized_query": normalized_query,
            "entity_type": cached.get("entity_type") or entity_type,
        }, 200

    local_answer = _local_coach_answer(query, [])
    if local_answer:
        answer = _format_coach_answer(local_answer)
        _search_ai_answer_upsert(query, normalized_query, answer, entity_type)
        return {"answer": answer, "source": "local", "cached": False, "normalized_query": normalized_query, "entity_type": entity_type}, 200

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"error": COACH_UNAVAILABLE}, 503

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
                            "Reste 100% football et n'invente pas d'actualité si elle n'est pas dans les données."
                        ),
                    },
                    {"role": "user", "content": query},
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
        _search_ai_answer_upsert(query, normalized_query, answer, entity_type)
        return {"answer": answer, "source": "openai", "cached": False, "normalized_query": normalized_query, "entity_type": entity_type}, 200
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
    for item in value[-12:]:
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
    return "\n".join(f"{item['role']}: {item['content']}" for item in history[-12:])


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
        elif path == "/api/coach/messages":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            session_id = _clean(_url_decode(query.get("session_id", "")), 120)
            raw_limit = _clean(_url_decode(query.get("limit", "12")), 8)
            try:
                limit = min(30, max(1, int(raw_limit or "12")))
            except ValueError:
                limit = 12
            self._send_json({"messages": _coach_messages_from_supabase(session_id, limit) if session_id else []})
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
    users = _supabase_request("GET", f"users?select={SUPABASE_USER_COLUMNS}&order=total_points.desc.nullslast")
    predictions = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&order=created_at.desc")
    if users is None or predictions is None:
        return {"available": False}
    user_by_id = {str(user.get("id")): user for user in users if user.get("id") is not None}
    user_by_pseudo = {str(user.get("pseudo")): user for user in users if user.get("pseudo")}
    normalized_predictions = [_prediction_from_supabase(row, user_by_id) for row in predictions]
    return {
        "available": True,
        "users": users,
        "predictions": normalized_predictions,
        "badges": _read_supabase_badges_by_user(user_by_id, user_by_pseudo),
    }


def _prediction_from_supabase(row: dict[str, Any], user_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    user = user_by_id.get(str(row.get("user_id")), {})
    return {
        "id": row.get("id"),
        "user_id": row.get("user_id"),
        "pseudo": row.get("pseudo") or user.get("pseudo") or "",
        "match_id": row.get("match_id", ""),
        "home_score": row.get("home_score"),
        "away_score": row.get("away_score"),
        "stored_points": row.get("points", 0),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
    }


def _read_supabase_badges_by_user(user_by_id: dict[str, dict[str, Any]], user_by_pseudo: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    badges_by_id = _supabase_badge_catalog()
    if not badges_by_id:
        return {}
    rows = _supabase_request("GET", "user_badges?select=*&order=earned_at.asc")
    if rows is None:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        user = user_by_id.get(str(row.get("user_id")), {})
        pseudo = str(user.get("pseudo") or row.get("pseudo") or "")
        badge = badges_by_id.get(str(row.get("badge_id"))) or {}
        if pseudo and badge:
            out.setdefault(pseudo, []).append(badge)
    return out


def _supabase_badge_catalog() -> dict[str, dict[str, Any]]:
    rows = _supabase_request("GET", f"badges?select={SUPABASE_BADGE_COLUMNS}&order=min_predictions.asc")
    if rows is None:
        return {}
    return {str(row.get("id")): row for row in rows if row.get("id") is not None}


def _save_prediction_supabase(pseudo: str, match_id: str, home_score: int, away_score: int, matches: dict[str, dict[str, Any]]) -> bool:
    if not _supabase_enabled():
        return False
    user = _supabase_get_or_create_user(pseudo)
    if not user:
        return False
    match = matches.get(match_id)
    points = _points({"match_id": match_id, "home_score": home_score, "away_score": away_score}, match)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    existing = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&user_id=eq.{quote(str(user.get('id')), safe='')}&match_id=eq.{quote(match_id, safe='')}&limit=1")
    payload = {
        "user_id": user.get("id"),
        "pseudo": pseudo,
        "match_id": match_id,
        "home_score": home_score,
        "away_score": away_score,
        "points": points,
        "updated_at": now,
    }
    if existing:
        saved = _supabase_request("PATCH", f"predictions?id=eq.{quote(str(existing[0].get('id')), safe='')}", json=payload)
    else:
        payload["created_at"] = now
        saved = _supabase_request("POST", "predictions", json=payload)
    if saved is None:
        return False
    _sync_supabase_user_totals(str(user.get("id")), pseudo, matches)
    return True


def _supabase_get_or_create_user(pseudo: str) -> dict[str, Any] | None:
    existing = _supabase_request("GET", f"users?select={SUPABASE_USER_COLUMNS}&pseudo=eq.{quote(pseudo, safe='')}&limit=1")
    if existing:
        return existing[0]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    created = _supabase_request(
        "POST",
        "users",
        json={"pseudo": pseudo, "total_points": 0, "predictions_count": 0, "success_rate": 0, "created_at": now, "updated_at": now},
    )
    if created:
        return created[0]
    # If the table does not expose all optional columns, retry with the strict minimum.
    created = _supabase_request("POST", "users", json={"pseudo": pseudo})
    return created[0] if created else None


def _sync_supabase_user_totals(user_id: str, pseudo: str, matches: dict[str, dict[str, Any]]) -> None:
    rows = _supabase_request("GET", f"predictions?select={SUPABASE_PREDICTION_COLUMNS}&user_id=eq.{quote(user_id, safe='')}")
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
        "total_points": points,
        "predictions_count": count,
        "success_rate": success_rate,
        "current_badge": level["level"],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _supabase_request("PATCH", f"users?id=eq.{quote(user_id, safe='')}", json=patch)
    _award_supabase_badge(user_id, level)
    _sync_supabase_prediction_points(scored)


def _sync_supabase_prediction_points(predictions: list[dict[str, Any]]) -> None:
    for prediction in predictions:
        prediction_id = prediction.get("id")
        if prediction_id is None:
            continue
        if int(prediction.get("stored_points", -1) or -1) == int(prediction.get("points", 0) or 0):
            continue
        _supabase_request("PATCH", f"predictions?id=eq.{quote(str(prediction_id), safe='')}", json={"points": int(prediction.get("points", 0) or 0)})


def _award_supabase_badge(user_id: str, level: dict[str, Any]) -> None:
    badge = _ensure_supabase_badge(level)
    if not badge or not badge.get("id"):
        return
    existing = _supabase_request("GET", f"user_badges?select=*&user_id=eq.{quote(user_id, safe='')}&badge_id=eq.{quote(str(badge.get('id')), safe='')}&limit=1")
    if existing:
        return
    _supabase_request(
        "POST",
        "user_badges",
        json={"user_id": user_id, "badge_id": badge.get("id"), "earned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    )


def _ensure_supabase_badge(level: dict[str, Any]) -> dict[str, Any] | None:
    name = str(level.get("level") or level.get("badge") or "Badge")
    existing = _supabase_request("GET", f"badges?select={SUPABASE_BADGE_COLUMNS}&name=eq.{quote(name, safe='')}&limit=1")
    if existing:
        return existing[0]
    created = _supabase_request(
        "POST",
        "badges",
        json={"name": name, "level": level.get("level_index"), "icon": level.get("badge_icon"), "min_predictions": max(0, (int(level.get("level_index", 1)) - 1) * 10)},
    )
    return created[0] if created else None


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
        "locked": _is_locked(match),
    }


def _predictions_with_points(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**prediction, "points": _points(prediction, matches.get(prediction.get("match_id", "")))} for prediction in predictions]


def _leaderboard(predictions: list[dict[str, Any]], matches: dict[str, dict[str, Any]] | None = None, badges: dict[str, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    profiles = _community_profiles(predictions, matches or {}, badges)
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
