from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def render_html(data: dict[str, Any], output: Path) -> None:
    output.write_text(_page(data), encoding="utf-8")


def _page(data: dict[str, Any]) -> str:
    worldcup_data = data.get("worldcup", data)
    champions_data = data.get("champions_league")
    data = worldcup_data
    generated = _format_datetime(data.get("generated_at", ""), with_time=True)
    groups = data.get("standings", [])
    group_matches = data.get("group_matches", [])
    knockout = data.get("knockout", [])
    today_matches = data.get("today_matches", [])
    scorers = data.get("top_scorers", [])[:5]
    assists = data.get("top_assists", [])[:5]
    all_time_scorers = data.get("all_time_top_scorers", [])
    champions_all_time_scorers = champions_data.get("all_time_top_scorers", []) if champions_data else []
    world_cup_news = data.get("world_cup_news", [])[:3]
    france_news = data.get("france_news", [])[:3]
    group_total = data.get("group_matches_total", _count_matches(group_matches))
    group_remaining = data.get("group_matches_remaining", _count_remaining_groups(group_matches))
    knockout_total = data.get("knockout_matches_total", _count_knockout(knockout))
    knockout_remaining = data.get("knockout_matches_remaining", _count_remaining_knockout(knockout))
    competition_stage = data.get("competition_stage", "Phase de groupes")
    france_next_match = data.get("france_next_match")
    teams_details = _merged_teams_details(data, champions_data)
    prediction_matches = _global_prediction_matches(data, champions_data)

    sources = "\n".join(
        f'<a href="{escape(source["url"])}" target="_blank" rel="noreferrer">{escape(source["name"])}</a>'
        for source in data.get("sources", [])
    )

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Centre de suivi Football</title>
  <style>
    :root {{
      color-scheme: dark;
      --ink: #eef5ff;
      --muted: #9fb0c2;
      --line: rgba(255,255,255,0.12);
      --panel: rgba(14,31,53,0.82);
      --panel-2: rgba(18,43,70,0.9);
      --blue: #1f6feb;
      --red: #ef3340;
      --white: #f7fbff;
      --gold: #f5c96b;
      --green: #32d3a2;
      --shadow: 0 24px 70px rgba(0,0,0,0.36);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 18% 8%, rgba(31,111,235,0.42), transparent 28rem),
        radial-gradient(circle at 78% 0%, rgba(239,51,64,0.24), transparent 24rem),
        radial-gradient(circle at 50% 18%, rgba(245,201,107,0.18), transparent 28rem),
        linear-gradient(180deg, #06101e 0%, #0b1a2c 42%, #07111f 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(110deg, transparent 0 42%, rgba(255,255,255,0.07) 48%, transparent 56%),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.035) 0 1px, transparent 1px 84px);
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.9), transparent 72%);
    }}
    main {{ width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 26px 0 54px; position: relative; }}
    a {{ color: #bfe6ff; }}
    h1, h2, h3 {{ margin: 0; letter-spacing: 0; }}
    .hero {{
      position: relative;
      overflow: hidden;
      min-height: 390px;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: clamp(24px, 5vw, 54px);
      background:
        linear-gradient(135deg, rgba(8,23,43,0.94), rgba(9,39,66,0.78)),
        radial-gradient(circle at 75% 35%, rgba(245,201,107,0.32), transparent 14rem);
      box-shadow: var(--shadow);
    }}
    .app-header {{
      position: relative;
      overflow: hidden;
      margin-bottom: 18px;
      padding: clamp(22px, 4vw, 42px);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 22px;
      background:
        radial-gradient(circle at 80% 18%, rgba(245,201,107,0.24), transparent 18rem),
        radial-gradient(circle at 18% 10%, rgba(31,111,235,0.42), transparent 20rem),
        linear-gradient(135deg, rgba(6,16,30,0.96), rgba(11,35,63,0.86));
      box-shadow: var(--shadow);
    }}
    .app-header::after {{
      content: "";
      position: absolute;
      inset: auto 0 0;
      height: 6px;
      background: linear-gradient(90deg, var(--blue), var(--white), var(--red), var(--gold));
      opacity: 0.8;
    }}
    .app-top {{ position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: end; }}
    .app-title {{ font-size: clamp(42px, 8vw, 92px); line-height: 0.9; }}
    .app-copy {{ color: #c5d3e4; max-width: 650px; margin: 12px 0 0; font-size: 16px; line-height: 1.5; }}
    .global-controls {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; align-items: center; }}
    .pseudo-field {{ width: min(260px, 100%); }}
    .hero.champions {{
      background:
        linear-gradient(135deg, rgba(5,12,35,0.96), rgba(17,33,77,0.82)),
        radial-gradient(circle at 75% 35%, rgba(132,173,255,0.32), transparent 14rem);
    }}
    .hero.champions::after {{
      opacity: 0.30;
      background:
        radial-gradient(circle at 50% 12%, rgba(255,255,255,0.92) 0 10%, transparent 11%),
        radial-gradient(circle at 50% 50%, transparent 0 42%, rgba(183,209,255,0.88) 43% 51%, transparent 52%);
      clip-path: polygon(50% 0, 58% 28%, 88% 28%, 64% 46%, 75% 78%, 50% 58%, 25% 78%, 36% 46%, 12% 28%, 42% 28%);
    }}
    .tabs-nav {{
      position: sticky;
      top: 12px;
      z-index: 20;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin: 0 0 16px;
      padding: 8px;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 999px;
      background: rgba(4,13,25,0.72);
      backdrop-filter: blur(16px);
      box-shadow: 0 16px 40px rgba(0,0,0,0.24);
    }}
    .tab-button {{
      appearance: none;
      border: 1px solid transparent;
      border-radius: 999px;
      background: transparent;
      color: #c8d8ea;
      padding: 10px 14px;
      font: inherit;
      font-size: 14px;
      font-weight: 950;
      cursor: pointer;
    }}
    .tab-button.is-active {{
      color: #07111f;
      background: linear-gradient(180deg, #ffffff, #c8d6e6);
      border-color: rgba(255,255,255,0.28);
    }}
    .tab-panel {{ display: block; }}
    .tab-panel:not(.is-active) {{ display: none; }}
    .hero::before {{
      content: "";
      position: absolute;
      inset: auto -8% -36% -8%;
      height: 58%;
      background: radial-gradient(ellipse at center, rgba(50,211,162,0.20), transparent 62%), repeating-linear-gradient(90deg, rgba(255,255,255,0.11) 0 2px, transparent 2px 96px);
      border-top: 1px solid rgba(255,255,255,0.16);
      transform: perspective(540px) rotateX(58deg);
      transform-origin: bottom;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: clamp(26px, 8vw, 110px);
      top: 54px;
      width: clamp(130px, 22vw, 245px);
      aspect-ratio: 0.62;
      opacity: 0.44;
      background:
        radial-gradient(circle at 50% 18%, transparent 0 24%, rgba(245,201,107,0.88) 25% 34%, transparent 35%),
        linear-gradient(90deg, transparent 0 24%, rgba(245,201,107,0.88) 25% 75%, transparent 76%),
        radial-gradient(ellipse at 50% 88%, rgba(245,201,107,0.92) 0 43%, transparent 44%);
      clip-path: polygon(28% 0, 72% 0, 66% 32%, 58% 52%, 72% 72%, 86% 100%, 14% 100%, 28% 72%, 42% 52%, 34% 32%);
      filter: drop-shadow(0 0 32px rgba(245,201,107,0.45));
    }}
    .hero-content {{ position: relative; z-index: 1; max-width: 760px; }}
    .kicker, .pill, .status {{ display: inline-flex; align-items: center; border-radius: 999px; font-weight: 850; }}
    .kicker {{ gap: 9px; padding: 8px 11px; border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.08); color: #d8e9ff; font-size: 13px; text-transform: uppercase; }}
    .ball {{ width: 18px; height: 18px; border-radius: 50%; background: radial-gradient(circle at 38% 38%, #fff 0 24%, transparent 25%), conic-gradient(from 18deg, #fff 0 14%, #17202a 15% 26%, #fff 27% 48%, #17202a 49% 59%, #fff 60% 100%); }}
    h1 {{ margin-top: 18px; font-size: clamp(38px, 7vw, 82px); line-height: 0.95; max-width: 820px; }}
    .hero-copy {{ color: #c5d3e4; font-size: clamp(16px, 2vw, 20px); line-height: 1.5; margin: 18px 0 0; max-width: 650px; }}
    .hero-badges {{ display: grid; gap: 9px; margin-top: 24px; }}
    .hero-row {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .pill {{ gap: 8px; padding: 9px 12px; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14); color: #e9f4ff; font-size: 13px; }}
    .pill .flag {{ width: 18px; height: 18px; margin-right: 2px; }}
    .france-pill::before {{ content: ""; width: 26px; height: 14px; border-radius: 2px; background: linear-gradient(90deg, var(--blue) 0 33%, var(--white) 33% 66%, var(--red) 66%); }}
    .section-head {{ display: flex; align-items: end; justify-content: space-between; gap: 18px; margin: 34px 0 14px; }}
    .section-title {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    h2 {{ font-size: clamp(24px, 3vw, 34px); line-height: 1.05; }}
    .section-note {{ color: var(--muted); font-size: 14px; max-width: 540px; text-align: right; }}
    .alltime-badge {{ appearance: none; border: 1px solid rgba(245,201,107,0.34); border-radius: 999px; background: rgba(245,201,107,0.10); color: #ffe1a0; padding: 7px 10px; font: inherit; font-size: 12px; font-weight: 950; cursor: pointer; }}
    .alltime-badge:hover, .alltime-badge:focus-visible {{ background: rgba(245,201,107,0.18); outline: 1px solid rgba(245,201,107,0.45); }}
    .action-button {{ appearance: none; border: 1px solid rgba(255,255,255,0.16); border-radius: 999px; background: rgba(255,255,255,0.10); color: var(--ink); padding: 9px 12px; font: inherit; font-size: 13px; font-weight: 900; cursor: pointer; text-decoration: none; }}
    .action-button:hover, .action-button:focus-visible {{ background: rgba(255,255,255,0.17); outline: 1px solid rgba(255,255,255,0.28); }}
    .today-strip, .leaders, .news, .grid, .matches, .calendar-days {{ display: grid; gap: 16px; }}
    .today-strip {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin-top: 18px; }}
    .leaders {{ grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }}
    .news {{ grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); }}
    .grid {{ grid-template-columns: repeat(auto-fit, minmax(286px, 1fr)); }}
    .matches {{ grid-template-columns: repeat(auto-fit, minmax(370px, 1fr)); }}
    .calendar-days {{ grid-template-columns: 1fr; }}
    .today-tile, .card, .notice {{ background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.055)); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 14px 36px rgba(0,0,0,0.20); backdrop-filter: blur(14px); overflow: hidden; }}
    .today-tile {{ padding: 16px; min-height: 104px; position: relative; }}
    .today-tile::after {{ content: ""; position: absolute; inset: auto 14px 12px 14px; height: 3px; border-radius: 999px; background: linear-gradient(90deg, var(--blue), var(--white), var(--red)); opacity: 0.72; }}
    .subtle {{ color: var(--muted); font-size: 12px; }}
    .card h3 {{ padding: 16px 16px 0; font-size: 17px; }}
    .card.france {{ border-color: rgba(255,255,255,0.22); background: linear-gradient(90deg, rgba(31,111,235,0.28), rgba(255,255,255,0.08), rgba(239,51,64,0.22)), linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.06)); }}
    .flag {{ width: 24px; height: 24px; border-radius: 50%; object-fit: cover; vertical-align: middle; margin-right: 8px; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14); }}
    .flag.placeholder {{ display: inline-grid; place-items: center; color: #9fb0c2; font-size: 11px; }}
    .team {{ font-weight: 850; }}
    .team-button {{ appearance: none; border: 0; background: transparent; color: inherit; font: inherit; font-weight: inherit; display: inline-flex; align-items: center; gap: 0; max-width: 100%; padding: 2px 3px; margin: -2px -3px; border-radius: 999px; cursor: pointer; text-align: inherit; }}
    .team-button:hover, .team-button:focus-visible {{ color: #fff; background: rgba(245,201,107,0.14); outline: 1px solid rgba(245,201,107,0.34); }}
    .away .team-button {{ justify-content: flex-end; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #edf6ff; }}
    th, td {{ padding: 10px 9px; border-bottom: 1px solid rgba(255,255,255,0.08); text-align: right; vertical-align: middle; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ color: #91a6bb; font-size: 11px; text-transform: uppercase; background: rgba(255,255,255,0.035); }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ padding: 18px 16px 20px; color: var(--muted); font-size: 14px; }}
    .player-card {{ padding: 16px; display: grid; grid-template-columns: 62px 1fr; gap: 14px; align-items: center; }}
    .avatar-wrap {{ position: relative; width: 62px; height: 62px; }}
    .avatar {{ width: 62px; height: 62px; border-radius: 50%; object-fit: cover; background: radial-gradient(circle at 35% 30%, #dbe7f7, #708196); border: 2px solid rgba(255,255,255,0.16); }}
    .avatar.placeholder {{ display: grid; place-items: center; font-size: 25px; font-weight: 900; color: #07111f; }}
    .player-country-flag {{ position: absolute; right: -2px; bottom: -2px; width: 22px; height: 22px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(7,17,31,0.92); background: rgba(255,255,255,0.14); }}
    .player-stat {{ color: var(--gold); font-size: 28px; font-weight: 950; line-height: 1; margin-top: 8px; }}
    .rank-note {{ color: #b7c6d7; font-size: 12px; margin-top: 5px; }}
    .today-teams {{ display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 12px; }}
    .today-team {{ text-align: center; font-weight: 900; }}
    .today-score {{ font-size: 26px; font-weight: 950; color: var(--gold); }}
    .day-card {{ padding: 0; }}
    .day-card h3 {{ padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #ffe1a0; }}
    .day-list {{ padding: 6px 14px 14px; }}
    .calendar-match {{ display: grid; grid-template-columns: 70px minmax(0, 1fr) 76px minmax(0, 1fr) 130px; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }}
    .calendar-match:last-child {{ border-bottom: 0; }}
    .match-meta {{ min-width: 0; }}
    .match-group {{ color: var(--gold); font-size: 12px; font-weight: 900; text-transform: uppercase; }}
    .date {{ color: #9cafc2; font-size: 12px; line-height: 1.35; }}
    .away {{ text-align: right; }}
    .score {{ min-width: 54px; text-align: center; font-weight: 950; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); border-radius: 9px; padding: 6px 8px; }}
    .status {{ padding: 4px 8px; font-size: 12px; background: rgba(31,111,235,0.18); color: #b9d7ff; margin-top: 5px; }}
    .status.done {{ background: rgba(50,211,162,0.18); color: #9ff0d5; }}
    .status.live {{ background: rgba(239,51,64,0.22); color: #ffb8bf; box-shadow: 0 0 0 1px rgba(239,51,64,0.45); }}
    .article {{ padding: 16px; min-height: 190px; display: flex; flex-direction: column; }}
    .article h3 {{ padding: 0; font-size: 16px; line-height: 1.25; }}
    .article p {{ color: #b7c6d7; font-size: 13px; line-height: 1.5; margin: 11px 0 0; }}
    .article-meta {{ color: #95a9bd; font-size: 12px; margin-bottom: 10px; text-transform: uppercase; font-weight: 800; }}
    .read-link {{ margin-top: auto; padding-top: 14px; font-weight: 850; font-size: 13px; text-decoration: none; }}
    .bracket-wrap {{ width: 100%; max-width: 100%; overflow-x: visible; padding: 8px 0 18px; }}
    .bracket-stage {{
      width: 100%;
      max-width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) clamp(170px, 19vw, 240px) minmax(0, 1fr);
      gap: clamp(8px, 1.4vw, 16px);
      align-items: stretch;
      padding: clamp(10px, 1.6vw, 18px);
      border: 1px solid rgba(245,201,107,0.22);
      border-radius: 18px;
      background:
        radial-gradient(circle at 50% 18%, rgba(245,201,107,0.18), transparent 24rem),
        linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.035));
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.05), 0 24px 70px rgba(0,0,0,0.26);
    }}
    .bracket-stage.ucl-official {{
      grid-template-columns: minmax(0, 1.25fr) clamp(170px, 17vw, 230px) minmax(0, 1.25fr);
      border-color: rgba(132,173,255,0.28);
      background:
        radial-gradient(circle at 50% 16%, rgba(132,173,255,0.18), transparent 24rem),
        linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.035));
    }}
    .bracket-wing {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: clamp(7px, 1vw, 12px);
      align-items: center;
      position: relative;
      min-width: 0;
    }}
    .bracket-wing.ucl-wing {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .bracket-wing.left::after, .bracket-wing.right::before {{
      content: "";
      position: absolute;
      top: 50%;
      width: 26px;
      height: 2px;
      background: linear-gradient(90deg, transparent, rgba(245,201,107,0.82), transparent);
    }}
    .bracket-wing.left::after {{ right: -20px; }}
    .bracket-wing.right::before {{ left: -20px; }}
    .round {{
      position: relative;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: clamp(7px, 0.8vw, 10px);
      min-height: 100%;
      min-width: 0;
    }}
    .round::after {{
      content: "";
      position: absolute;
      top: 50%;
      right: -16px;
      width: 16px;
      height: 2px;
      background: rgba(245,201,107,0.55);
    }}
    .bracket-wing.right .round::after {{ right: auto; left: -16px; }}
    .bracket-wing .round:last-child::after {{ display: none; }}
    .round-title {{
      text-align: center;
      color: #ffe1a0;
      font-weight: 950;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
      padding: 7px 8px;
      border: 1px solid rgba(245,201,107,0.22);
      border-radius: 999px;
      background: rgba(245,201,107,0.08);
    }}
    .ko-match {{
      position: relative;
      padding: clamp(7px, 0.9vw, 10px);
      border: 1px solid rgba(7,17,31,0.12);
      border-radius: 12px;
      background: linear-gradient(180deg, rgba(247,251,255,0.96), rgba(218,230,244,0.92));
      color: #07111f;
      box-shadow: 0 12px 26px rgba(0,0,0,0.22);
    }}
    .ko-match::before {{
      content: "";
      position: absolute;
      top: 50%;
      right: -17px;
      width: 17px;
      height: 2px;
      background: rgba(245,201,107,0.62);
    }}
    .bracket-wing.right .ko-match::before {{ right: auto; left: -17px; }}
    .ko-line {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; align-items: center; font-weight: 850; margin: 4px 0; font-size: clamp(10px, 0.92vw, 13px); }}
    .ko-line span:first-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .ko-match .subtle {{ color: #526274; }}
    .ko-match .status {{ color: #12457a; background: rgba(31,111,235,0.13); }}
    .ko-match .status.done {{ color: #0d684d; background: rgba(50,211,162,0.16); }}
    .ko-match .status.live {{ color: #a41422; background: rgba(239,51,64,0.16); }}
    .bracket-center {{
      display: grid;
      align-content: center;
      gap: 14px;
      text-align: center;
      position: relative;
    }}
    .trophy-card {{
      min-height: clamp(190px, 21vw, 250px);
      padding: clamp(14px, 1.4vw, 20px) clamp(10px, 1.2vw, 16px);
      border-radius: 18px;
      border: 1px solid rgba(245,201,107,0.36);
      background:
        radial-gradient(circle at 50% 20%, rgba(245,201,107,0.32), transparent 9rem),
        linear-gradient(180deg, rgba(17,39,64,0.94), rgba(7,17,31,0.95));
      box-shadow: 0 0 46px rgba(245,201,107,0.18), inset 0 0 0 1px rgba(255,255,255,0.05);
    }}
    .trophy {{
      width: clamp(58px, 6.5vw, 86px);
      height: clamp(92px, 10vw, 136px);
      margin: 4px auto 12px;
      position: relative;
      filter: drop-shadow(0 0 28px rgba(245,201,107,0.38));
    }}
    .trophy::before {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 50% 18%, transparent 0 24%, var(--gold) 25% 35%, transparent 36%),
        linear-gradient(90deg, transparent 0 28%, var(--gold) 29% 71%, transparent 72%),
        radial-gradient(ellipse at 50% 88%, var(--gold) 0 42%, transparent 43%);
      clip-path: polygon(27% 0, 73% 0, 67% 31%, 58% 53%, 74% 74%, 88% 100%, 12% 100%, 26% 74%, 42% 53%, 33% 31%);
    }}
    .trophy-title {{ color: #ffe1a0; font-size: 13px; font-weight: 950; text-transform: uppercase; }}
    .final-card {{ transform: scale(1.03); border-color: rgba(245,201,107,0.48); }}
    .third-place-card {{ opacity: 0.92; }}
    .notice {{ padding: 14px; margin-top: 18px; color: #ffe5aa; background: rgba(138,90,0,0.20); border-color: rgba(245,201,107,0.32); font-size: 14px; }}
    .sources {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; font-size: 13px; }}
    .sources a {{ color: #d7ecff; text-decoration: none; border: 1px solid rgba(255,255,255,0.12); background: rgba(255,255,255,0.06); border-radius: 999px; padding: 7px 10px; font-weight: 750; }}
    .team-modal {{ position: fixed; inset: 0; z-index: 50; display: none; place-items: center; padding: 20px; background: rgba(2,8,18,0.74); backdrop-filter: blur(10px); }}
    .team-modal.is-open {{ display: grid; }}
    .team-dialog {{ width: min(880px, 100%); max-height: min(86vh, 860px); overflow: auto; border: 1px solid rgba(255,255,255,0.16); border-radius: 20px; background: linear-gradient(180deg, rgba(12,29,51,0.98), rgba(7,17,31,0.98)); box-shadow: var(--shadow); }}
    .team-modal-head {{ position: sticky; top: 0; z-index: 1; display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 18px; background: linear-gradient(90deg, rgba(31,111,235,0.24), rgba(255,255,255,0.06), rgba(239,51,64,0.18)), rgba(8,23,43,0.96); border-bottom: 1px solid rgba(255,255,255,0.10); }}
    .team-modal-flag {{ width: 58px; height: 58px; border-radius: 50%; object-fit: cover; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18); }}
    .team-modal-title {{ font-size: clamp(24px, 4vw, 38px); font-weight: 950; line-height: 1; }}
    .modal-close {{ width: 38px; height: 38px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.16); background: rgba(255,255,255,0.08); color: var(--ink); font-size: 24px; cursor: pointer; }}
    .team-modal-body {{ padding: 18px; display: grid; gap: 18px; }}
    .team-info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
    .team-info {{ padding: 13px; border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; background: rgba(255,255,255,0.06); }}
    .team-info-label {{ color: var(--muted); font-size: 11px; font-weight: 900; text-transform: uppercase; margin-bottom: 6px; }}
    .team-info-value {{ font-weight: 850; }}
    .formation-board {{ min-height: 140px; display: grid; place-items: center; border: 1px dashed rgba(245,201,107,0.30); border-radius: 16px; background: radial-gradient(ellipse at center, rgba(50,211,162,0.14), transparent 68%), linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.035)); color: #d6e5f7; font-weight: 850; }}
    .roster-section h3 {{ padding: 0; margin-bottom: 10px; color: #ffe1a0; }}
    .player-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
    .mini-player {{ display: grid; grid-template-columns: 42px 1fr; gap: 10px; align-items: center; padding: 10px; border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; background: rgba(255,255,255,0.055); }}
    .mini-avatar {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; background: radial-gradient(circle at 35% 30%, #dbe7f7, #708196); }}
    .mini-avatar.placeholder {{ display: grid; place-items: center; color: #07111f; font-weight: 950; }}
    .alltime-list {{ display: grid; gap: 10px; }}
    .alltime-row {{ display: grid; grid-template-columns: 44px 52px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 12px; border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; background: rgba(255,255,255,0.06); }}
    .alltime-rank {{ width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; color: #07111f; background: linear-gradient(180deg, #ffe1a0, #d5a63a); font-weight: 950; }}
    .alltime-value {{ color: var(--gold); font-size: 24px; font-weight: 950; text-align: right; }}
    .community-grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .community-panel {{ padding: 16px; }}
    .community-predictions {{ display: grid; grid-template-columns: minmax(240px, 0.82fr) minmax(0, 1.18fr); gap: 16px; align-items: start; }}
    .community-side {{ min-width: 0; }}
    .follow-zone {{ display: grid; gap: 12px; }}
    .follow-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .follow-card {{ padding: 13px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.10); background: radial-gradient(circle at center, rgba(245,201,107,0.10), transparent 18rem), rgba(255,255,255,0.055); }}
    .follow-meta {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; font-weight: 850; text-transform: uppercase; }}
    .follow-teams {{ display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 10px; margin-top: 12px; }}
    .follow-team {{ min-width: 0; display: flex; align-items: center; gap: 8px; font-weight: 950; }}
    .follow-team.away {{ justify-content: flex-end; text-align: right; }}
    .follow-team span:last-child {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .follow-center {{ min-width: 58px; text-align: center; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); border-radius: 10px; padding: 7px 9px; font-weight: 950; }}
    .follow-status {{ display: inline-flex; align-items: center; justify-content: center; margin-top: 10px; padding: 4px 8px; border-radius: 999px; color: #b9d7ff; background: rgba(31,111,235,0.18); font-size: 12px; font-weight: 900; }}
    .follow-status.done {{ color: #9ff0d5; background: rgba(50,211,162,0.18); }}
    .follow-status.live {{ color: #ffb8bf; background: rgba(239,51,64,0.22); box-shadow: 0 0 0 1px rgba(239,51,64,0.45); }}
    .community-form {{ display: grid; gap: 10px; margin-top: 12px; }}
    .field-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    input, textarea, select {{ width: 100%; color: var(--ink); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 10px 11px; font: inherit; }}
    textarea {{ min-height: 82px; resize: vertical; }}
    .message-list, .prediction-list, .leaderboard-list {{ display: grid; gap: 10px; margin-top: 14px; }}
    .leaderboard-list {{ max-height: 292px; overflow-y: auto; padding-right: 8px; scrollbar-width: thin; scrollbar-color: rgba(245,201,107,0.55) rgba(255,255,255,0.08); }}
    .leaderboard-list::-webkit-scrollbar {{ width: 8px; }}
    .leaderboard-list::-webkit-scrollbar-track {{ background: rgba(255,255,255,0.08); border-radius: 999px; }}
    .leaderboard-list::-webkit-scrollbar-thumb {{ background: rgba(245,201,107,0.55); border-radius: 999px; }}
    .message-item, .prediction-item, .leaderboard-item {{ padding: 11px; border-radius: 12px; background: rgba(255,255,255,0.055); border: 1px solid rgba(255,255,255,0.09); }}
    .message-top, .prediction-top, .leaderboard-item {{ display: flex; justify-content: space-between; gap: 10px; align-items: center; }}
    .leaderboard-item.top-rank {{ border-color: rgba(245,201,107,0.34); background: linear-gradient(90deg, rgba(245,201,107,0.14), rgba(255,255,255,0.055)); }}
    .leaderboard-rank {{ display: inline-flex; align-items: center; justify-content: center; width: 34px; height: 34px; margin-right: 8px; border-radius: 50%; color: #07111f; background: linear-gradient(180deg, #ffffff, #b9c9dc); font-weight: 950; }}
    .top-rank .leaderboard-rank {{ background: linear-gradient(180deg, #ffe1a0, #d5a63a); }}
    .prediction-scoreboard {{ display: grid; grid-template-columns: minmax(0, 1fr) auto auto auto minmax(0, 1fr); align-items: center; gap: 12px; padding: 14px; border: 1px solid rgba(245,201,107,0.22); border-radius: 16px; background: radial-gradient(circle at center, rgba(245,201,107,0.12), transparent 18rem), rgba(255,255,255,0.055); }}
    .prediction-team {{ min-width: 0; display: flex; align-items: center; gap: 8px; font-weight: 950; }}
    .prediction-team.home {{ justify-content: flex-end; text-align: right; }}
    .prediction-team.away {{ justify-content: flex-start; text-align: left; }}
    .prediction-team-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .prediction-scoreboard input {{ width: 64px; text-align: center; font-size: 22px; font-weight: 950; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); }}
    .prediction-separator {{ color: var(--gold); font-size: 26px; font-weight: 950; }}
    .community-status {{ margin-top: 10px; color: #ffe1a0; font-size: 13px; min-height: 18px; }}
    .match-context {{ text-align: center; color: var(--muted); font-size: 12px; font-weight: 800; }}
    @media (max-width: 860px) {{
      main {{ width: min(100% - 20px, 1240px); padding-top: 14px; }}
      .app-top {{ grid-template-columns: 1fr; align-items: start; }}
      .global-controls {{ justify-content: flex-start; }}
      .hero {{ min-height: 430px; border-radius: 14px; }}
      .hero::after {{ right: 18px; top: auto; bottom: 28px; opacity: 0.30; }}
      .section-head {{ align-items: start; flex-direction: column; }}
      .section-note {{ text-align: left; }}
      .matches {{ grid-template-columns: 1fr; }}
      .calendar-match {{ grid-template-columns: 62px minmax(0, 1fr) 58px minmax(0, 1fr); gap: 8px; }}
      .match-meta {{ grid-column: 1 / -1; display: flex; gap: 10px; flex-wrap: wrap; }}
      th, td {{ padding: 8px 6px; }}
      .bracket-stage {{ grid-template-columns: 1fr; gap: 14px; }}
      .bracket-stage.ucl-official {{ grid-template-columns: 1fr; }}
      .bracket-center {{ order: -1; }}
      .bracket-wing {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .bracket-wing.left::after, .bracket-wing.right::before, .round::after, .ko-match::before {{ display: none; }}
      .trophy-card {{ min-height: 150px; }}
      .team-dialog {{ max-height: 90vh; }}
      .alltime-row {{ grid-template-columns: 38px 46px minmax(0, 1fr); }}
      .alltime-value {{ grid-column: 3; font-size: 20px; text-align: left; }}
      .community-grid, .community-predictions, .field-row, .follow-list {{ grid-template-columns: 1fr; }}
      .prediction-scoreboard {{ grid-template-columns: 1fr auto auto auto 1fr; gap: 8px; }}
    }}
    @media (max-width: 480px) {{
      h1 {{ font-size: 40px; }}
      .today-strip, .leaders, .news, .grid, .matches {{ grid-template-columns: 1fr; }}
      .calendar-match {{ grid-template-columns: 1fr auto 1fr; }}
      .calendar-match .date, .calendar-match .match-meta {{ grid-column: 1 / -1; }}
      .bracket-stage {{ padding: 10px; }}
      .bracket-wing {{ grid-template-columns: 1fr; }}
      .bracket-wing.ucl-wing {{ grid-template-columns: 1fr; }}
      .round {{ gap: 8px; }}
      .ko-line {{ font-size: 12px; }}
      .team-modal {{ padding: 10px; }}
      .team-modal-head {{ grid-template-columns: auto 1fr auto; padding: 14px; }}
      .team-modal-flag {{ width: 46px; height: 46px; }}
      .alltime-row {{ gap: 9px; padding: 10px; }}
      .prediction-scoreboard {{ grid-template-columns: 1fr; justify-items: center; }}
      .prediction-team.home, .prediction-team.away {{ justify-content: center; text-align: center; }}
    }}
  </style>
</head>
<body>
  <main>
    {_app_header()}
    {_community_section()}
    {_tabs_nav(champions_data)}
    <section class="tab-panel is-active" id="tab-worldcup" data-tab-panel="worldcup">
    <section class="hero">
      <div class="hero-content">
        <div class="kicker"><span class="ball"></span> Coupe du Monde 2026</div>
        <h1>{escape(data.get("competition", "Coupe du Monde 2026"))}</h1>
        <p class="hero-copy">Centre de suivi automatisé des groupes, matchs, buteurs, passeurs, actualités et phases finales. Données publiées uniquement lorsqu’elles sont disponibles auprès des sources.</p>
        <div class="hero-badges">
          <div class="hero-row">
            <span class="pill">Mis à jour : {escape(generated)}</span>
            <span class="pill france-pill">Focus Équipe de France</span>
          </div>
          <div class="hero-row">
            <span class="pill">{_france_next_match_badge(france_next_match)}</span>
          </div>
          <div class="hero-row">
            <span class="pill">{group_remaining}/{group_total} matchs de poules</span>
            <span class="pill">{knockout_remaining}/{knockout_total} matchs à élimination</span>
            <span class="pill">Avancement : {escape(competition_stage)}</span>
          </div>
        </div>
      </div>
    </section>

    {_errors(data.get("errors", []))}

    <section class="today-strip" aria-label="Matchs du jour">{_today_matches(today_matches)}</section>

    {_section_head("Meilleurs buteurs", "Top 5 uniquement, avec photo si la source la fournit.", _all_time_badge("scorers"))}
    <section class="leaders">{_player_cards(scorers, "buts")}</section>

    {_section_head("Meilleurs passeurs", "Top 5 uniquement, avec photo si la source la fournit.")}
    <section class="leaders">{_player_cards(assists, "passes")}</section>

    {_news_section("Actualité Coupe du Monde", world_cup_news, "Les 3 dernières nouvelles générales publiées par les sources suivies.", france=False)}
    {_news_section("Actualité Équipe de France", france_news, "Les 3 dernières nouvelles des Bleus, séparées du flux général.", france=True)}

    {_section_head("Arbre à élimination directe", "Bracket officiel horizontal : les deux ailes convergent vers la finale au centre.")}
    {render_worldcup_bracket(knockout)}

    {_section_head("Classements des groupes", "Drapeaux, points, différence de buts, matchs joués, victoires, nuls et défaites.")}
    <section class="grid">{''.join(_group_card(group) for group in groups) or _empty_block("Les classements ne sont pas encore disponibles.")}</section>

    {_section_head("Résultats et calendrier des poules", "Calendrier par journée, avec groupe, stade, statut et score central.")}
    <section class="calendar-days">{_calendar_by_day(group_matches)}</section>

    <nav class="sources" aria-label="Sources">{sources}</nav>
    </section>
    {_champions_tab(champions_data)}
  </main>
  {_team_modal()}
  {_all_time_modal()}
  {_team_script(teams_details)}
  {_all_time_script(all_time_scorers, champions_all_time_scorers)}
  {_community_script(prediction_matches)}
  {_tabs_script(champions_data)}
</body>
</html>
"""


def _section_head(title: str, note: str, action: str = "") -> str:
    return (
        '<div class="section-head">'
        f'<div class="section-title"><h2>{escape(title)}</h2>{action}</div>'
        f'<div class="section-note">{escape(note)}</div>'
        "</div>"
    )


def _all_time_badge(kind: str) -> str:
    return f'<button class="alltime-badge" type="button" data-alltime="{escape(kind, quote=True)}">Top 10 all-time</button>'


def _app_header() -> str:
    return """
    <header class="app-header">
      <div class="app-top">
        <div>
          <div class="kicker"><span class="ball"></span> Plateforme football</div>
          <h1 class="app-title">Akro du Foot</h1>
          <p class="app-copy">Un espace unique pour suivre les compétitions, discuter entre amis, faire des pronostics fictifs sans argent et lancer une Watch Party.</p>
        </div>
        <div class="global-controls">
          <input class="pseudo-field" id="globalPseudo" maxlength="32" placeholder="Ton pseudo" autocomplete="nickname">
          <a class="action-button" href="#community">Pronostics</a>
          <button class="action-button" type="button" id="shareButton">Partager</button>
          <a class="action-button" href="/watch-party">Watch Party</a>
        </div>
      </div>
    </header>
"""


def _merged_teams_details(worldcup_data: dict[str, Any], champions_data: dict[str, Any] | None) -> dict[str, Any]:
    teams = dict(worldcup_data.get("teams_details", {}))
    if champions_data:
        teams.update(champions_data.get("teams_details", {}))
    return teams


def _tabs_nav(champions_data: dict[str, Any] | None) -> str:
    if not champions_data:
        return ""
    return """
    <nav class="tabs-nav" aria-label="Compétitions">
      <button class="tab-button is-active" type="button" data-tab-target="worldcup">Coupe du Monde 2026</button>
      <button class="tab-button" type="button" data-tab-target="champions">Ligue des Champions</button>
    </nav>
"""


def _champions_tab(data: dict[str, Any] | None) -> str:
    if not data:
        return ""
    generated = _format_datetime(data.get("generated_at", ""), with_time=True)
    standings = data.get("standings", [])
    matches = data.get("group_matches", [])
    knockout = data.get("knockout", [])
    today_matches = data.get("today_matches", [])
    scorers = data.get("top_scorers", [])[:5]
    assists = data.get("top_assists", [])[:5]
    news = data.get("world_cup_news", [])[:3]
    phase_total = data.get("group_matches_total", _count_matches(matches))
    phase_remaining = data.get("group_matches_remaining", _count_remaining_groups(matches))
    knockout_total = data.get("knockout_matches_total", _count_knockout(knockout))
    knockout_remaining = data.get("knockout_matches_remaining", _count_remaining_knockout(knockout))
    stage = data.get("competition_stage", "Phase de ligue")
    psg_next_match = data.get("psg_next_match")
    sources = "\n".join(
        f'<a href="{escape(source["url"])}" target="_blank" rel="noreferrer">{escape(source["name"])}</a>'
        for source in data.get("sources", [])
    )
    return f"""
    <section class="tab-panel" id="tab-champions" data-tab-panel="champions">
      <section class="hero champions">
        <div class="hero-content">
          <div class="kicker"><span class="ball"></span> UEFA Champions League</div>
          <h1>{escape(data.get("competition", "Ligue des Champions"))}</h1>
          <p class="hero-copy">Suivi automatisé des matchs, du classement de phase de ligue, des statistiques joueurs, actualités et phase finale dès publication par les sources.</p>
          <div class="hero-badges">
            <div class="hero-row">
              <span class="pill">Mis à jour : {escape(generated)}</span>
              <span class="pill psg-pill">{_logo_or_placeholder(_psg_logo(data))}Focus PSG</span>
            </div>
            <div class="hero-row">
              <span class="pill">{_psg_next_match_badge(psg_next_match)}</span>
            </div>
            <div class="hero-row">
              <span class="pill">{phase_remaining}/{phase_total} matchs de phase de ligue</span>
              <span class="pill">{knockout_remaining}/{knockout_total} matchs à élimination</span>
              <span class="pill">Avancement : {escape(stage)}</span>
            </div>
          </div>
        </div>
      </section>

      {_errors(data.get("errors", []))}

      <section class="today-strip" aria-label="Matchs du jour Ligue des Champions">{_today_matches(today_matches)}</section>

      {_section_head("Meilleurs buteurs", "Top 5 Ligue des Champions, avec photo si la source la fournit.", _all_time_badge("champions-scorers"))}
      <section class="leaders">{_player_cards(scorers, "buts", prefer_country_flag=True)}</section>

      {_section_head("Meilleurs passeurs", "Top 5 Ligue des Champions, avec photo si la source la fournit.")}
      <section class="leaders">{_player_cards(assists, "passes", prefer_country_flag=True)}</section>

      {_news_section("Actualité Ligue des Champions", news, "Les 3 dernières nouvelles publiées par les sources suivies.", france=False)}

      {_section_head("Phase finale", "Bracket Ligue des Champions affiché dès disponibilité des matchs à élimination directe.")}
      {render_champions_league_bracket(knockout)}

      {_section_head("Classement de la phase de ligue", "Clubs, matchs joués, victoires, nuls, défaites, différence et points.")}
      <section class="grid">{''.join(_group_card(group) for group in standings) or _empty_block("Le classement n’est pas encore disponible.")}</section>

      {_section_head("Résultats et calendrier", "Calendrier par journée, avec stade, statut et score central.")}
      <section class="calendar-days">{_calendar_by_day(matches)}</section>

      <nav class="sources" aria-label="Sources Ligue des Champions">{sources}</nav>
    </section>
"""


def _tabs_script(champions_data: dict[str, Any] | None) -> str:
    if not champions_data:
        return ""
    return """<script>
    document.querySelectorAll('[data-tab-target]').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.dataset.tabTarget;
        document.querySelectorAll('[data-tab-target]').forEach((item) => {
          item.classList.toggle('is-active', item === button);
        });
        document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
          panel.classList.toggle('is-active', panel.dataset.tabPanel === target);
        });
      });
    });
  </script>"""


def _france_next_match_badge(match: dict[str, Any] | None) -> str:
    if not match:
        return "France : prochain match à déterminer"
    date = _format_datetime(match.get("date", ""), with_time=True)
    opponent = match.get("opponent_display") or match.get("opponent") or "À déterminer"
    france_flag = _flag(match.get("france_flag_url", ""))
    opponent_flag = _flag(match.get("opponent_flag_url", ""))
    if opponent == "À déterminer":
        return f"{france_flag}France vs À déterminer — {escape(date)}"
    return f"{france_flag}France vs {escape(opponent)} {opponent_flag}— {escape(date)}"


def _psg_next_match_badge(match: dict[str, Any] | None) -> str:
    if not match:
        return "PSG : prochain match à déterminer"
    date = _format_datetime(match.get("date", ""), with_time=True)
    team = match.get("team") or "PSG"
    opponent = match.get("opponent") or "À déterminer"
    return f'{_logo_or_placeholder(match.get("team_logo_url", ""))}{escape(_psg_display_name(team))} vs {escape(opponent)} {_logo_or_placeholder(match.get("opponent_logo_url", ""))}— {escape(date)}'


def _psg_display_name(name: str) -> str:
    return "PSG" if str(name).lower() in {"paris saint-germain", "paris sg", "psg"} else str(name)


def _psg_logo(data: dict[str, Any]) -> str:
    for name, details in data.get("teams_details", {}).items():
        if str(name).lower() in {"paris saint-germain", "paris sg", "psg"} or "paris saint" in str(name).lower():
            return details.get("flag_url", "")
    match = data.get("psg_next_match") or {}
    return match.get("team_logo_url", "")


def _logo_or_placeholder(url: str) -> str:
    return _flag(url)


def _today_matches(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return '<article class="today-tile" style="grid-column:1/-1"><strong>Aucun match prévu aujourd’hui</strong><div class="subtle">La carte se remplira automatiquement les jours de match.</div></article>'
    return "".join(f'<article class="today-tile">{_today_match(match)}</article>' for match in matches)


def _today_match(match: dict[str, Any]) -> str:
    center = _score_text(match)
    if center == "vs":
        center = _format_time(match.get("date", "")) or "vs"
    return (
        f'<div class="today-teams"><div class="today-team">{_team_button(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}</div>'
        f'<div class="today-score">{escape(center)}<br><span class="{_status_class(match)}">{escape(match.get("status", ""))}</span></div>'
        f'<div class="today-team">{_team_button(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""))}</div></div>'
        f'<div class="subtle" style="text-align:center;margin-top:12px">{escape(_venue_text(match))}</div>'
    )


def _community_section() -> str:
    return """
    <div class="section-head" id="community">
      <div class="section-title"><h2>Communauté</h2><span class="alltime-badge">Global</span><span class="alltime-badge">Jeu privé sans argent</span></div>
      <div class="section-note">Pronostics fictifs globaux pour la Coupe du Monde et la Ligue des Champions.</div>
    </div>
    <section class="community-grid">
      <article class="card community-panel follow-zone">
        <div class="section-title"><h3>Matchs à suivre</h3><span class="alltime-badge" id="followMode">Aujourd’hui</span></div>
        <div class="follow-list" id="communityFollowMatches"></div>
      </article>
      <article class="card community-panel community-predictions">
        <div class="community-side">
          <h3>Classement</h3>
          <div class="leaderboard-list" id="leaderboardList"></div>
        </div>
        <div class="community-side">
          <h3 id="predictions">Pronostics du jour</h3>
          <form class="community-form" id="predictionForm">
            <div class="field-row">
              <select id="competitionFilter">
                <option value="today" selected>Matchs du jour</option>
                <option value="all">Tous les matchs</option>
                <option value="Coupe du Monde">Coupe du Monde</option>
                <option value="Ligue des Champions">Ligue des Champions</option>
              </select>
              <select id="predictionMatch"></select>
            </div>
            <div class="prediction-scoreboard" id="predictionTeams">
              <div class="prediction-team home"><span class="prediction-team-name" id="predictionHomeName">Équipe A</span><span id="predictionHomeFlag" class="flag placeholder">?</span></div>
              <input id="homePrediction" type="number" min="0" max="99" value="0" aria-label="Score équipe A">
              <div class="prediction-separator">-</div>
              <input id="awayPrediction" type="number" min="0" max="99" value="0" aria-label="Score équipe B">
              <div class="prediction-team away"><span id="predictionAwayFlag" class="flag placeholder">?</span><span class="prediction-team-name" id="predictionAwayName">Équipe B</span></div>
            </div>
            <div class="match-context" id="predictionContext"></div>
            <button class="action-button" type="submit">Valider le pronostic</button>
          </form>
          <div class="community-status" id="predictionStatus"></div>
        </div>
      </article>
    </section>
"""


def _player_cards(players: list[dict[str, Any]], label: str, prefer_country_flag: bool = False) -> str:
    if not players:
        return _empty_block("Aucune donnée publiée pour le moment.")
    return "".join(_player_card(player, label, prefer_country_flag) for player in players[:5])


def _player_card(player: dict[str, Any], label: str, prefer_country_flag: bool = False) -> str:
    country_flag = player.get("country_flag_url", "")
    real_photo = player.get("photo_url", "")
    photo = country_flag if prefer_country_flag else real_photo or country_flag
    avatar = f'<img class="avatar" src="{escape(photo)}" alt="">' if photo else '<div class="avatar placeholder">?</div>'
    flag_badge = f'<img class="player-country-flag" src="{escape(country_flag)}" alt="">' if country_flag and real_photo and not prefer_country_flag else ""
    all_time = player.get("all_time_rank", "")
    all_time_html = f'<div class="rank-note">({escape(str(all_time))})</div>' if all_time else ""
    return (
        '<article class="card player-card">'
        f'<div class="avatar-wrap">{avatar}{flag_badge}</div><div><div class="team">{escape(str(player.get("name", "")))}</div>'
        f'<div class="subtle">{_flag(player.get("flag_url", ""))}{escape(str(player.get("team", "")))}</div>'
        f'<div class="player-stat">{escape(str(player.get("value", "0")))} <span class="subtle">{escape(label)}</span></div>{all_time_html}</div>'
        "</article>"
    )


def _group_card(group: dict[str, Any]) -> str:
    rows = []
    for team in group.get("teams", []):
        rows.append(
            "<tr>"
            f"<td>{escape(str(team.get('rank', '')))}</td>"
            f"<td>{_team_button(team.get('team', ''), team.get('flag_url', ''))}</td>"
            f"<td>{escape(str(team.get('played', '0')))}</td>"
            f"<td>{escape(str(team.get('wins', '0')))}</td>"
            f"<td>{escape(str(team.get('draws', '0')))}</td>"
            f"<td>{escape(str(team.get('losses', '0')))}</td>"
            f"<td>{escape(str(team.get('goal_diff', '0')))}</td>"
            f"<td><strong>{escape(str(team.get('points', '0')))}</strong></td>"
            "</tr>"
        )
    return f"""<article class="card">
  <h3>{escape(group.get("name", "Groupe"))}</h3>
  <table>
    <thead><tr><th>#</th><th>Équipe</th><th>J</th><th>G</th><th>N</th><th>P</th><th>Diff.</th><th>Pts</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</article>"""


def _calendar_by_day(groups: list[dict[str, Any]]) -> str:
    entries = []
    for group in groups:
        for match in group.get("matches", []):
            entries.append({**match, "group": group.get("name", "")})
    if not entries:
        return _empty_block("Les matchs de poules ne sont pas encore disponibles.")

    entries.sort(key=lambda item: item.get("date", ""))
    days: dict[str, list[dict[str, Any]]] = {}
    for match in entries:
        day_key = _format_datetime(match.get("date", ""), with_time=False)
        days.setdefault(day_key, []).append(match)

    return "".join(
        f'<article class="card day-card"><h3>{escape(day)}</h3><div class="day-list">{"".join(_calendar_match(match) for match in matches)}</div></article>'
        for day, matches in days.items()
    )


def _calendar_match(match: dict[str, Any]) -> str:
    return (
        '<div class="calendar-match">'
        f'<div class="date">{escape(_format_datetime(match.get("date", ""), with_time=False))}<br>{escape(_format_time(match.get("date", "")))}</div>'
        f'<div>{_team_button(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}</div>'
        f'<div class="score">{escape(_calendar_score_text(match))}</div>'
        f'<div class="away">{_team_button(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""), reverse=True)}</div>'
        f'<div class="match-meta"><div class="match-group">{escape(match.get("group", ""))}</div><div class="subtle">{escape(_venue_text(match))}</div><span class="{_status_class(match)}">{escape(match.get("status", ""))}</span></div>'
        "</div>"
    )


def _news_section(title: str, news: list[dict[str, Any]], note: str, france: bool) -> str:
    if not news:
        return f'{_section_head(title, note)}<section class="news">{_empty_block("Aucune actualité disponible pour le moment.")}</section>'
    articles = []
    france_class = " france" if france else ""
    for article in news[:3]:
        articles.append(
            f'<article class="card article{france_class}">'
            f'<div class="article-meta">{escape(article.get("source", ""))} · {escape(_format_datetime(article.get("date", ""), with_time=False))}</div>'
            f'<h3><a href="{escape(article.get("url", ""))}" target="_blank" rel="noreferrer">{escape(article.get("title", ""))}</a></h3>'
            f'<p>{escape(article.get("summary", ""))}</p>'
            f'<a class="read-link" href="{escape(article.get("url", ""))}" target="_blank" rel="noreferrer">Lire l’article</a>'
            "</article>"
        )
    return f'{_section_head(title, note)}<section class="news">{"".join(articles)}</section>'


def render_worldcup_bracket(rounds: list[dict[str, Any]]) -> str:
    return _bracket(rounds, "Coupe du Monde FIFA 2026")


def _bracket(rounds: list[dict[str, Any]], trophy_title: str = "Coupe du Monde FIFA 2026") -> str:
    by_name = {round_data.get("name", ""): round_data for round_data in rounds}
    round_32 = by_name.get("16es de finale", {"name": "16es de finale", "matches": []})
    round_16 = by_name.get("8es de finale", {"name": "8es de finale", "matches": []})
    quarter = by_name.get("Quarts de finale", {"name": "Quarts de finale", "matches": []})
    semi = by_name.get("Demi-finales", {"name": "Demi-finales", "matches": []})
    third = by_name.get("Match pour la 3e place", {"name": "Match pour la 3e place", "matches": []})
    final = by_name.get("Finale", {"name": "Finale", "matches": []})

    left = [
        {"name": "16es", "matches": round_32.get("matches", [])[:8]},
        {"name": "8es", "matches": round_16.get("matches", [])[:4]},
        {"name": "Quarts", "matches": quarter.get("matches", [])[:2]},
    ]
    right = [
        {"name": "Quarts", "matches": quarter.get("matches", [])[2:]},
        {"name": "8es", "matches": round_16.get("matches", [])[4:]},
        {"name": "16es", "matches": round_32.get("matches", [])[8:]},
    ]
    final_match = (final.get("matches") or [{}])[0]
    third_match = (third.get("matches") or [{}])[0]
    center = (
        '<div class="bracket-center">'
        f'<div class="trophy-card"><div class="trophy"></div><div class="trophy-title">{escape(trophy_title)}</div></div>'
        '<div class="round-title">Finale</div>'
        f'{_ko_match(final_match, extra_class="final-card")}'
        '<div class="round-title">3e place</div>'
        f'{_ko_match(third_match, extra_class="third-place-card")}'
        "</div>"
    )
    return (
        '<section class="bracket-wrap"><div class="bracket-stage">'
        f'<div class="bracket-wing left">{"".join(_bracket_round(round_data) for round_data in left)}</div>'
        f"{center}"
        f'<div class="bracket-wing right">{"".join(_bracket_round(round_data) for round_data in right)}</div>'
        "</div></section>"
    )


def render_champions_league_bracket(rounds: list[dict[str, Any]]) -> str:
    by_name = {round_data.get("name", ""): round_data for round_data in rounds}
    playoffs = by_name.get("Barrages", {"name": "Barrages", "matches": []})
    round_16 = by_name.get("8es de finale", {"name": "8es de finale", "matches": []})
    quarter = by_name.get("Quarts de finale", {"name": "Quarts de finale", "matches": []})
    semi = by_name.get("Demi-finales", {"name": "Demi-finales", "matches": []})
    final = by_name.get("Finale", {"name": "Finale", "matches": []})

    left = [
        {"name": "Barrages", "matches": playoffs.get("matches", [])[:8]},
        {"name": "8es", "matches": round_16.get("matches", [])[:8]},
        {"name": "Quarts", "matches": quarter.get("matches", [])[:4]},
        {"name": "Demies", "matches": semi.get("matches", [])[:2]},
    ]
    right = [
        {"name": "Demies", "matches": semi.get("matches", [])[2:]},
        {"name": "Quarts", "matches": quarter.get("matches", [])[4:]},
        {"name": "8es", "matches": round_16.get("matches", [])[8:]},
        {"name": "Barrages", "matches": playoffs.get("matches", [])[8:]},
    ]
    final_match = (final.get("matches") or [{}])[0]
    center = (
        '<div class="bracket-center">'
        '<div class="trophy-card"><div class="trophy"></div><div class="trophy-title">Ligue des Champions</div></div>'
        '<div class="round-title">Finale</div>'
        f'{_ko_match(final_match, extra_class="final-card")}'
        "</div>"
    )
    return (
        '<section class="bracket-wrap"><div class="bracket-stage ucl-official">'
        f'<div class="bracket-wing ucl-wing left">{"".join(_bracket_round(round_data) for round_data in left)}</div>'
        f"{center}"
        f'<div class="bracket-wing ucl-wing right">{"".join(_bracket_round(round_data) for round_data in right)}</div>'
        "</div></section>"
    )


def _bracket_round(round_data: dict[str, Any]) -> str:
    matches = "".join(_ko_match(match) for match in round_data.get("matches", []))
    if not matches:
        matches = _empty_block("À déterminer.")
    return f'<article class="round"><div class="round-title">{escape(round_data.get("name", ""))}</div>{matches}</article>'


def _ko_match(match: dict[str, Any], extra_class: str = "") -> str:
    class_name = f"ko-match {extra_class}".strip()
    home_score = _display_score(match.get("home_score", ""))
    away_score = _display_score(match.get("away_score", ""))
    return (
        f'<div class="{escape(class_name)}">'
        f'<div class="ko-line"><span>{_team_button(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}</span><span>{home_score}</span></div>'
        f'<div class="ko-line"><span>{_team_button(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""))}</span><span>{away_score}</span></div>'
        f'<div class="subtle">{escape(_format_datetime(match.get("date", ""), with_time=True))}</div>'
        f'<span class="{_status_class(match)}">{escape(match.get("status", ""))}</span>'
        "</div>"
    )


def _team_button(name: str, flag_url: str = "", reverse: bool = False) -> str:
    label = str(name or "À déterminer")
    if label == "À déterminer":
        content = f"{escape(label)}{_flag(flag_url)}" if reverse else f"{_flag(flag_url)}{escape(label)}"
        return f'<span class="team">{content}</span>'
    content = f"{escape(label)}{_flag(flag_url)}" if reverse else f"{_flag(flag_url)}{escape(label)}"
    return f'<button class="team team-button" type="button" data-team="{escape(label, quote=True)}">{content}</button>'


def _team_modal() -> str:
    return """
  <div class="team-modal" id="teamModal" aria-hidden="true">
    <article class="team-dialog" role="dialog" aria-modal="true" aria-labelledby="teamModalTitle">
      <header class="team-modal-head">
        <div id="teamModalFlag"></div>
        <div>
          <div class="team-modal-title" id="teamModalTitle">Équipe</div>
          <div class="subtle" id="teamModalSources"></div>
        </div>
        <button class="modal-close" type="button" id="teamModalClose" aria-label="Fermer">×</button>
      </header>
      <div class="team-modal-body">
        <div class="team-info-grid">
          <div class="team-info"><div class="team-info-label">Sélectionneur</div><div class="team-info-value" id="teamCoach">Non disponible</div></div>
          <div class="team-info"><div class="team-info-label">Formation</div><div class="team-info-value" id="teamFormation">Formation non disponible</div></div>
        </div>
        <div class="formation-board" id="teamFormationBoard">Formation non disponible</div>
        <div id="teamRoster"></div>
      </div>
    </article>
  </div>
"""


def _all_time_modal() -> str:
    return """
  <div class="team-modal" id="allTimeModal" aria-hidden="true">
    <article class="team-dialog" role="dialog" aria-modal="true" aria-labelledby="allTimeTitle">
      <header class="team-modal-head">
        <div class="alltime-rank">10</div>
        <div>
          <div class="team-modal-title" id="allTimeTitle">Top 10 all-time</div>
          <div class="subtle" id="allTimeSource">Sources : UEFA / StatBunker selon disponibilité</div>
        </div>
        <button class="modal-close" type="button" id="allTimeClose" aria-label="Fermer">×</button>
      </header>
      <div class="team-modal-body">
        <div id="allTimeBody"></div>
      </div>
    </article>
  </div>
"""


def _team_script(teams_details: dict[str, Any]) -> str:
    payload = json.dumps(teams_details, ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const TEAMS_DETAILS = {payload};
    const modal = document.getElementById('teamModal');
    const modalTitle = document.getElementById('teamModalTitle');
    const modalFlag = document.getElementById('teamModalFlag');
    const modalSources = document.getElementById('teamModalSources');
    const teamCoach = document.getElementById('teamCoach');
    const teamFormation = document.getElementById('teamFormation');
    const teamFormationBoard = document.getElementById('teamFormationBoard');
    const teamRoster = document.getElementById('teamRoster');
    const closeModal = document.getElementById('teamModalClose');

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    }}

    function flagHtml(url) {{
      return url ? `<img class="team-modal-flag" src="${{escapeHtml(url)}}" alt="">` : '<div class="team-modal-flag flag placeholder">?</div>';
    }}

    function playerCard(player) {{
      const photo = player.photo_url ? `<img class="mini-avatar" src="${{escapeHtml(player.photo_url)}}" alt="">` : '<div class="mini-avatar placeholder">?</div>';
      const position = player.position ? `<div class="subtle">${{escapeHtml(player.position)}}</div>` : '';
      return `<article class="mini-player">${{photo}}<div><strong>${{escapeHtml(player.name || 'Joueur')}}</strong>${{position}}</div></article>`;
    }}

    function rosterSection(title, players) {{
      if (!players || !players.length) return '';
      return `<section class="roster-section"><h3>${{escapeHtml(title)}}</h3><div class="player-grid">${{players.map(playerCard).join('')}}</div></section>`;
    }}

    function openTeam(name) {{
      const details = TEAMS_DETAILS[name] || {{name}};
      modalTitle.textContent = details.name || name;
      modalFlag.innerHTML = flagHtml(details.flag_url || '');
      modalSources.textContent = details.sources && details.sources.length ? `Source : ${{details.sources.join(', ')}}` : 'Détails enrichis dès publication par les sources suivies';
      teamCoach.textContent = details.coach || 'Non disponible';
      teamFormation.textContent = details.formation || 'Formation non disponible';
      teamFormationBoard.textContent = details.formation || 'Formation non disponible';

      const starters = details.starters || [];
      const substitutes = details.substitutes || [];
      const squad = details.squad || [];
      const hasLineup = starters.length || substitutes.length;
      const sections = hasLineup
        ? [rosterSection('Titulaires', starters), rosterSection('Remplaçants', substitutes), rosterSection('Effectif complet', squad)].join('')
        : rosterSection('Effectif', squad);
      teamRoster.innerHTML = sections || '<div class="empty">Effectif non disponible</div>';
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      closeModal.focus();
    }}

    function hideTeam() {{
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
    }}

    document.addEventListener('click', (event) => {{
      const trigger = event.target.closest('[data-team]');
      if (trigger) openTeam(trigger.dataset.team);
      if (event.target === modal) hideTeam();
    }});
    closeModal.addEventListener('click', hideTeam);
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape' && modal.classList.contains('is-open')) hideTeam();
    }});
  </script>"""


def _all_time_script(worldcup_scorers: list[dict[str, Any]], champions_scorers: list[dict[str, Any]]) -> str:
    worldcup_scorers_payload = json.dumps(worldcup_scorers[:10], ensure_ascii=False).replace("</", "<\\/")
    champions_scorers_payload = json.dumps(champions_scorers[:10], ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const ALL_TIME_LISTS = {{
      'scorers': {{
        players: {worldcup_scorers_payload},
        title: 'Top 10 buteurs all-time Coupe du Monde',
        empty: 'Classement all-time des buteurs indisponible',
        label: 'buts'
      }},
      'champions-scorers': {{
        players: {champions_scorers_payload},
        title: 'Top 10 buteurs all-time Ligue des Champions',
        empty: 'Classement all-time des buteurs Ligue des Champions indisponible',
        label: 'buts'
      }}
    }};
    const allTimeModal = document.getElementById('allTimeModal');
    const allTimeTitle = document.getElementById('allTimeTitle');
    const allTimeBody = document.getElementById('allTimeBody');
    const allTimeClose = document.getElementById('allTimeClose');

    function allTimeAvatar(player) {{
      return player.flag_url
        ? `<img class="mini-avatar" src="${{escapeHtml(player.flag_url)}}" alt="">`
        : '<div class="mini-avatar placeholder">?</div>';
    }}

    function allTimeRow(player, label) {{
      const country = player.country || player.team || 'Pays non disponible';
      return `<article class="alltime-row">
        <div class="alltime-rank">${{escapeHtml(player.rank || '')}}</div>
        ${{allTimeAvatar(player)}}
        <div><strong>${{escapeHtml(player.name || '')}}</strong><div class="subtle">${{escapeHtml(country)}}</div></div>
        <div class="alltime-value">${{escapeHtml(player.value || '')}} <span class="subtle">${{label}}</span></div>
      </article>`;
    }}

    function openAllTime(kind) {{
      const config = ALL_TIME_LISTS[kind] || ALL_TIME_LISTS.scorers;
      allTimeTitle.textContent = config.title;
      allTimeBody.innerHTML = config.players && config.players.length
        ? `<div class="alltime-list">${{config.players.map((player) => allTimeRow(player, config.label)).join('')}}</div>`
        : `<div class="empty">${{config.empty}}</div>`;
      allTimeModal.classList.add('is-open');
      allTimeModal.setAttribute('aria-hidden', 'false');
      allTimeClose.focus();
    }}

    function hideAllTime() {{
      allTimeModal.classList.remove('is-open');
      allTimeModal.setAttribute('aria-hidden', 'true');
    }}

    document.addEventListener('click', (event) => {{
      const trigger = event.target.closest('[data-alltime]');
      if (trigger) openAllTime(trigger.dataset.alltime);
      if (event.target === allTimeModal) hideAllTime();
    }});
    allTimeClose.addEventListener('click', hideAllTime);
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape' && allTimeModal.classList.contains('is-open')) hideAllTime();
    }});
  </script>"""


def _global_prediction_matches(worldcup_data: dict[str, Any], champions_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    matches = _prediction_matches(
        worldcup_data.get("group_matches", []),
        worldcup_data.get("knockout", []),
        "Coupe du Monde",
        "worldcup",
    )
    if champions_data:
        matches.extend(
            _prediction_matches(
                champions_data.get("group_matches", []),
                champions_data.get("knockout", []),
                "Ligue des Champions",
                "champions",
            )
        )
    return sorted(matches, key=lambda item: item.get("date", ""))


def _prediction_matches(
    group_matches: list[dict[str, Any]],
    knockout: list[dict[str, Any]],
    competition: str = "Coupe du Monde",
    prefix: str = "worldcup",
) -> list[dict[str, Any]]:
    matches = []
    for group in group_matches:
        for match in group.get("matches", []):
            matches.append(_prediction_match(match, group.get("name", "Poules"), competition, prefix))
    for round_data in knockout:
        for match in round_data.get("matches", []):
            matches.append(_prediction_match(match, round_data.get("name", "Élimination"), competition, prefix))
    return sorted(matches, key=lambda item: item.get("date", ""))


def _prediction_match(match: dict[str, Any], phase: str, competition: str, prefix: str) -> dict[str, Any]:
    raw_id = str(match.get("id") or f"{phase}-{match.get('home_team')}-{match.get('away_team')}-{match.get('date')}")
    match_id = f"{prefix}:{raw_id}"
    return {
        "id": match_id,
        "phase": phase,
        "competition": competition,
        "date": match.get("date", ""),
        "home_team": match.get("home_team", "À déterminer"),
        "away_team": match.get("away_team", "À déterminer"),
        "home_flag_url": match.get("home_flag_url", ""),
        "away_flag_url": match.get("away_flag_url", ""),
        "home_score": match.get("home_score", ""),
        "away_score": match.get("away_score", ""),
        "status": match.get("status", ""),
        "completed": bool(match.get("completed")),
    }


def _community_script(matches: list[dict[str, Any]]) -> str:
    payload = json.dumps(matches, ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const DASHBOARD_MATCHES = {payload};
    const serverMode = location.protocol === 'http:' || location.protocol === 'https:';
    const shareButton = document.getElementById('shareButton');
    const globalPseudo = document.getElementById('globalPseudo');
    const predictionForm = document.getElementById('predictionForm');
    const communityFollowMatches = document.getElementById('communityFollowMatches');
    const followMode = document.getElementById('followMode');
    const competitionFilter = document.getElementById('competitionFilter');
    const predictionMatch = document.getElementById('predictionMatch');
    const predictionTeams = document.getElementById('predictionTeams');
    const predictionHomeName = document.getElementById('predictionHomeName');
    const predictionAwayName = document.getElementById('predictionAwayName');
    const predictionHomeFlag = document.getElementById('predictionHomeFlag');
    const predictionAwayFlag = document.getElementById('predictionAwayFlag');
    const predictionContext = document.getElementById('predictionContext');
    const predictionStatus = document.getElementById('predictionStatus');
    let communityMatches = DASHBOARD_MATCHES;

    function pseudoValue() {{
      return (globalPseudo.value || '').trim();
    }}

    function persistPseudo() {{
      localStorage.setItem('akrodufoot:pseudo', pseudoValue());
    }}

    function shortDate(value) {{
      if (!value) return '';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString('fr-FR', {{day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}});
    }}

    function localDateKey(value) {{
      if (!value) return '';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('fr-CA');
    }}

    function isTodayMatch(match) {{
      return localDateKey(match.date) === localDateKey(new Date().toISOString());
    }}

    function matchTimestamp(match) {{
      const date = new Date(match.date);
      return Number.isNaN(date.getTime()) ? 0 : date.getTime();
    }}

    function isMatchAvailable(match) {{
      return !match.completed && match.status !== 'Terminé' && matchTimestamp(match) >= Date.now();
    }}

    function closestPredictionMatch(matches, selectedCompetition) {{
      if (!matches.length) return null;
      const available = matches
        .filter(isMatchAvailable)
        .sort((a, b) => matchTimestamp(a) - matchTimestamp(b));
      if (available.length) return available[0];
      const fallback = matches.slice().sort((a, b) => matchTimestamp(b) - matchTimestamp(a));
      return fallback[0] || null;
    }}

    function statusClass(match) {{
      if (match.completed || match.status === 'Terminé') return 'done';
      return match.status === 'LIVE' ? 'live' : '';
    }}

    function matchCenter(match) {{
      const hasScore = match.home_score !== '' && match.away_score !== '';
      return hasScore ? `${{match.home_score}} - ${{match.away_score}}` : shortDate(match.date).split(' ').pop() || 'VS';
    }}

    function followMatchCard(match) {{
      return `<article class="follow-card">
        <div class="follow-meta"><span>${{escapeHtml(match.competition || 'Compétition')}}</span><span>${{escapeHtml(shortDate(match.date))}}</span></div>
        <div class="follow-teams">
          <div class="follow-team">${{flagMarkup(match.home_flag_url)}}<span>${{escapeHtml(match.home_team)}}</span></div>
          <div class="follow-center">${{escapeHtml(matchCenter(match))}}</div>
          <div class="follow-team away"><span>${{escapeHtml(match.away_team)}}</span>${{flagMarkup(match.away_flag_url)}}</div>
        </div>
        <span class="follow-status ${{statusClass(match)}}">${{escapeHtml(match.status || 'À venir')}}</span>
      </article>`;
    }}

    function renderFollowMatches(matches) {{
      const source = matches && matches.length ? matches : DASHBOARD_MATCHES;
      const sorted = source.slice().sort((a, b) => matchTimestamp(a) - matchTimestamp(b));
      const today = sorted.filter(isTodayMatch);
      const upcoming = sorted.filter(isMatchAvailable);
      const selected = today.length ? today : upcoming.slice(0, 3);
      followMode.textContent = today.length ? 'Aujourd’hui' : '3 prochains';
      communityFollowMatches.innerHTML = selected.length
        ? selected.map(followMatchCard).join('')
        : '<div class="empty">Aucun match à suivre pour le moment.</div>';
    }}

    async function sharePage() {{
      const url = location.href;
      try {{
        if (navigator.share) {{
          await navigator.share({{title: document.title, url}});
          return;
        }}
        await navigator.clipboard.writeText(url);
        shareButton.textContent = 'Lien copié';
      }} catch (error) {{
        shareButton.textContent = 'Copie impossible';
      }}
      setTimeout(() => shareButton.textContent = 'Partager', 1800);
    }}

    function renderMatchOptions(matches) {{
      communityMatches = matches && matches.length ? matches : DASHBOARD_MATCHES;
      const selectedCompetition = competitionFilter.value;
      const filtered = selectedCompetition === 'all'
        ? communityMatches
        : selectedCompetition === 'today'
          ? communityMatches.filter(isTodayMatch)
          : communityMatches.filter((match) => match.competition === selectedCompetition);
      const selected = closestPredictionMatch(filtered, selectedCompetition);
      predictionMatch.innerHTML = filtered.map((match) => {{
        const label = `${{match.competition || 'Compétition'}} · ${{shortDate(match.date)}} · ${{match.home_team}} vs ${{match.away_team}}`;
        return `<option value="${{escapeHtml(match.id)}}">${{escapeHtml(label)}}</option>`;
      }}).join('');
      if (selected) predictionMatch.value = selected.id;
      const hasMatches = filtered.length > 0;
      const matchAvailable = Boolean(selected && isMatchAvailable(selected));
      predictionMatch.disabled = !hasMatches;
      document.getElementById('homePrediction').disabled = !matchAvailable;
      document.getElementById('awayPrediction').disabled = !matchAvailable;
      predictionForm.querySelector('button[type="submit"]').disabled = !matchAvailable;
      predictionStatus.textContent = !hasMatches
        ? (selectedCompetition === 'today' ? 'Aucun match du jour disponible pour les pronostics' : 'Aucun match disponible avec ce filtre')
        : matchAvailable ? '' : 'Tous les matchs de ce filtre sont terminés';
      updatePredictionTeams();
    }}

    function selectedMatch() {{
      return communityMatches.find((match) => match.id === predictionMatch.value);
    }}

    function flagMarkup(url) {{
      return url ? `<img class="flag" src="${{escapeHtml(url)}}" alt="">` : '<span class="flag placeholder">?</span>';
    }}

    function updatePredictionTeams() {{
      const match = selectedMatch();
      if (!match) {{
        predictionHomeName.textContent = 'Aucun match';
        predictionAwayName.textContent = 'disponible';
        predictionHomeFlag.innerHTML = '<span class="flag placeholder">?</span>';
        predictionAwayFlag.innerHTML = '<span class="flag placeholder">?</span>';
        predictionContext.textContent = competitionFilter.value === 'today'
          ? 'Aucun match du jour disponible pour les pronostics'
          : 'Aucun match disponible avec ce filtre';
        return;
      }}
      predictionHomeName.textContent = match.home_team;
      predictionAwayName.textContent = match.away_team;
      predictionHomeFlag.innerHTML = flagMarkup(match.home_flag_url);
      predictionAwayFlag.innerHTML = flagMarkup(match.away_flag_url);
      predictionContext.textContent = `${{match.competition || 'Compétition'}} · ${{shortDate(match.date)}} · ${{match.phase || ''}}`;
    }}

    function renderLeaderboard(rows) {{
      const list = document.getElementById('leaderboardList');
      list.innerHTML = rows && rows.length ? rows.map((row, index) => `
        <div class="leaderboard-item ${{index < 3 ? 'top-rank' : ''}}"><strong><span class="leaderboard-rank">${{index + 1}}</span>${{escapeHtml(row.pseudo)}}</strong><span>${{escapeHtml(row.points)}} pts</span></div>
      `).join('') : '<div class="empty">Aucun point pour le moment.</div>';
    }}

    async function loadCommunity() {{
      if (!serverMode) {{
        predictionStatus.textContent = 'Mode fichier statique : pronostics désactivés.';
        renderMatchOptions(DASHBOARD_MATCHES);
        renderFollowMatches(DASHBOARD_MATCHES);
        return;
      }}
      try {{
        const response = await fetch('/api/community');
        const data = await response.json();
        renderMatchOptions(data.matches);
        renderFollowMatches(data.matches);
        renderLeaderboard(data.leaderboard);
        predictionStatus.textContent = '';
      }} catch (error) {{
        predictionStatus.textContent = 'Serveur communautaire indisponible.';
      }}
    }}

    async function postJson(url, payload) {{
      const response = await fetch(url, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(payload)
      }});
      const data = await response.json().catch(() => ({{}}));
      if (!response.ok) throw new Error(data.error || 'Action impossible');
      return data;
    }}

    shareButton.addEventListener('click', sharePage);
    globalPseudo.value = localStorage.getItem('akrodufoot:pseudo') || '';
    globalPseudo.addEventListener('input', persistPseudo);
    competitionFilter.addEventListener('change', () => renderMatchOptions(communityMatches));
    predictionMatch.addEventListener('change', updatePredictionTeams);
    predictionForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (!serverMode) return loadCommunity();
      try {{
        await postJson('/api/predictions', {{
          pseudo: pseudoValue(),
          match_id: predictionMatch.value,
          home_score: document.getElementById('homePrediction').value,
          away_score: document.getElementById('awayPrediction').value
        }});
        await loadCommunity();
      }} catch (error) {{
        predictionStatus.textContent = error.message;
      }}
    }});
    renderMatchOptions(DASHBOARD_MATCHES);
    loadCommunity();
  </script>"""


def _display_score(value: Any) -> str:
    text = str(value)
    return escape(text) if text else ""


def _flag(url: str) -> str:
    if url:
        return f'<img class="flag" src="{escape(url)}" alt="">'
    return '<span class="flag placeholder">?</span>'


def _status_class(match: dict[str, Any]) -> str:
    if match.get("completed"):
        return "status done"
    if match.get("status_state") == "in":
        return "status live"
    return "status"


def _score_text(match: dict[str, Any]) -> str:
    home = match.get("home_score", "")
    away = match.get("away_score", "")
    if home == "" and away == "":
        return "vs"
    return f"{home}-{away}"


def _calendar_score_text(match: dict[str, Any]) -> str:
    home = match.get("home_score", "")
    away = match.get("away_score", "")
    if home == "" or away == "":
        return "0 - 0"
    return f"{home} - {away}"


def _venue_text(match: dict[str, Any]) -> str:
    venue = match.get("venue", "")
    city = match.get("city", "")
    if venue and city:
        return f"{venue}, {city}"
    return venue or city


def _count_matches(groups: list[dict[str, Any]]) -> int:
    return sum(len(group.get("matches", [])) for group in groups)


def _count_knockout(rounds: list[dict[str, Any]]) -> int:
    return sum(len(round_data.get("matches", [])) for round_data in rounds)


def _count_remaining_groups(groups: list[dict[str, Any]]) -> int:
    return sum(1 for group in groups for match in group.get("matches", []) if not match.get("completed"))


def _count_remaining_knockout(rounds: list[dict[str, Any]]) -> int:
    return sum(1 for round_data in rounds for match in round_data.get("matches", []) if not match.get("completed"))


def _empty_block(message: str) -> str:
    return f'<div class="empty">{escape(message)}</div>'


def _errors(errors: list[str]) -> str:
    if not errors:
        return ""
    count = len(errors)
    return (
        '<section class="notice">'
        f"{count} source{'s' if count > 1 else ''} n’ont pas répondu pendant la dernière mise à jour. "
        "Le dashboard reste généré avec les données disponibles ; relance la mise à jour plus tard si une section est vide."
        "</section>"
    )


def _format_datetime(value: str, with_time: bool) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(PARIS)
        return parsed.strftime("%d/%m/%Y %H:%M") if with_time else parsed.strftime("%d/%m/%Y")
    except ValueError:
        return value


def _format_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(PARIS)
        return parsed.strftime("%H:%M")
    except ValueError:
        return ""
