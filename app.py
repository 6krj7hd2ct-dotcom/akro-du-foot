from __future__ import annotations

import json
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
from urllib.parse import urlparse

try:
    from flask import Flask, jsonify, request, send_file
except ImportError:
    Flask = None
    jsonify = None
    request = None
    send_file = None

from src.config import BASE_DIR, CACHE_FILE, CHAMPIONS_LEAGUE_CACHE_FILE, OUTPUT_HTML

COMMUNITY_FILE = BASE_DIR / "data" / "community.json"
WATCH_ROOM = "worldcup-watch-party"

app = Flask(__name__) if Flask else None


if app:
    @app.get("/")
    def index():
        return send_file(OUTPUT_HTML)

    @app.get("/watch-party")
    def watch_party():
        return watch_party_html()


def _background_updates_enabled() -> bool:
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


def community_payload() -> dict[str, Any]:
    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    community = _read_community()
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard)
    predictions = _predictions_with_points(community.get("predictions", []), matches)
    return {
        "messages": community.get("messages", [])[-100:],
        "predictions": predictions,
        "leaderboard": _leaderboard(predictions),
        "matches": list(matches.values()),
    }


if app:
    @app.get("/api/community")
    def get_community():
        return jsonify(community_payload())

    @app.get("/api/livekit-token")
    def livekit_token():
        pseudo = _clean(request.args.get("pseudo", ""), 32) or "Invite"
        role = "admin" if request.args.get("role") == "admin" and _is_admin_key(request.args.get("admin_key", "")) else "viewer"
        body, status = make_livekit_token(pseudo, role)
        return jsonify(body), status

    @app.get("/api/watch-chat")
    def watch_chat():
        return jsonify({"messages": _watch_messages()[-120:]})


def save_message(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    pseudo = _clean(payload.get("pseudo", ""), 32)
    text = _clean(payload.get("message", ""), 500)
    if not pseudo or not text:
        return {"error": "Pseudo et message obligatoires."}, 400

    community = _read_community()
    community.setdefault("messages", []).append(
        {
            "pseudo": pseudo,
            "message": text,
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
    worldcup_dashboard = _read_json(CACHE_FILE, {})
    champions_dashboard = _read_json(CHAMPIONS_LEAGUE_CACHE_FILE, {})
    matches = _all_dashboard_matches(worldcup_dashboard, champions_dashboard)
    match = matches.get(match_id)

    if not pseudo or not match or home_score is None or away_score is None:
        return {"error": "Pronostic invalide."}, 400
    if _is_locked(match):
        return {"error": "Pronostic verrouillé : le match a commencé."}, 423

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
    return {"ok": True}, 200


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
            self._send_file(OUTPUT_HTML, "text/html; charset=utf-8")
        elif path == "/watch-party":
            self._send_html(watch_party_html())
        elif path == "/api/community":
            self._send_json(community_payload())
        elif path == "/api/livekit-token":
            query = dict(item.split("=", 1) if "=" in item else (item, "") for item in urlparse(self.path).query.split("&") if item)
            pseudo = _clean(_url_decode(query.get("pseudo", "")), 32) or "Invite"
            role = "admin" if query.get("role") == "admin" and _is_admin_key(_url_decode(query.get("admin_key", ""))) else "viewer"
            body, status = make_livekit_token(pseudo, role)
            self._send_json(body, status)
        elif path == "/api/watch-chat":
            self._send_json({"messages": _watch_messages()[-120:]})
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

    def _send_html(self, html: str, status: int = 200) -> None:
        raw = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


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


def _all_dashboard_matches(worldcup_data: dict[str, Any], champions_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for match_id, match in _dashboard_matches(worldcup_data).items():
        matches[f"worldcup:{match_id}"] = {**match, "id": f"worldcup:{match_id}", "competition": "Coupe du Monde"}
    for match_id, match in _dashboard_matches(champions_data).items():
        matches[f"champions:{match_id}"] = {**match, "id": f"champions:{match_id}", "competition": "Ligue des Champions"}
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


def _leaderboard(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    for prediction in predictions:
        totals[prediction.get("pseudo", "")] = totals.get(prediction.get("pseudo", ""), 0) + int(prediction.get("points", 0))
    return [
        {"pseudo": pseudo, "points": points}
        for pseudo, points in sorted(totals.items(), key=lambda item: (-item[1], item[0].lower()))
        if pseudo
    ]


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
        <h1>Coupe du Monde 2026</h1>
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
