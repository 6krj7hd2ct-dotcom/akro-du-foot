from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")



def _competition_trophy_svg(kind: str, placement: str = "hero") -> str:
    base_class = "hero-logo-mark" if placement == "hero" else "bracket-logo"
    if kind == "champions":
        return f"""
        <div class="{base_class} premium-trophy ucl-trophy {placement}-trophy" aria-hidden="true">
          <svg viewBox="0 0 220 300" role="img" focusable="false">
            <defs>
              <linearGradient id="uclChrome" x1="20%" x2="82%" y1="8%" y2="92%">
                <stop offset="0" stop-color="#ffffff"/><stop offset="0.22" stop-color="#cfd8e8"/><stop offset="0.48" stop-color="#7f91ad"/><stop offset="0.72" stop-color="#eef5ff"/><stop offset="1" stop-color="#92a5c4"/>
              </linearGradient>
              <linearGradient id="uclStem" x1="0" x2="1"><stop offset="0" stop-color="#75879f"/><stop offset="0.48" stop-color="#f7fbff"/><stop offset="1" stop-color="#6c7d97"/></linearGradient>
              <radialGradient id="uclGlow" cx="50%" cy="30%" r="70%"><stop offset="0" stop-color="#ddebff" stop-opacity="0.90"/><stop offset="0.52" stop-color="#7ba9ff" stop-opacity="0.22"/><stop offset="1" stop-color="#0b1735" stop-opacity="0"/></radialGradient>
            </defs>
            <ellipse cx="110" cy="151" rx="92" ry="122" fill="url(#uclGlow)"/>
            <path d="M52 71c-29 13-43 41-38 73 5 31 27 51 57 58" fill="none" stroke="url(#uclChrome)" stroke-width="13" stroke-linecap="round"/>
            <path d="M168 71c29 13 43 41 38 73-5 31-27 51-57 58" fill="none" stroke="url(#uclChrome)" stroke-width="13" stroke-linecap="round"/>
            <path d="M58 48h104l-12 124c-3 35-22 57-40 57s-37-22-40-57L58 48Z" fill="url(#uclChrome)" stroke="rgba(255,255,255,.72)" stroke-width="3"/>
            <path d="M82 71h56l-7 92c-2 24-11 39-21 39s-19-15-21-39L82 71Z" fill="rgba(255,255,255,.20)"/>
            <path d="M110 226v33" stroke="url(#uclStem)" stroke-width="18" stroke-linecap="round"/>
            <path d="M68 269h84l15 18H53l15-18Z" fill="url(#uclStem)"/>
            <path d="M82 288h56" stroke="#ffffff" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>
            <circle cx="110" cy="118" r="31" fill="none" stroke="#f8fbff" stroke-opacity=".64" stroke-width="5"/>
            <path d="M110 86l10 23h25l-20 15 8 24-23-14-22 14 8-24-20-15h25l9-23Z" fill="#f8fbff" fill-opacity=".74"/>
          </svg>
        </div>"""
    return f"""
        <div class="{base_class} premium-trophy worldcup-trophy {placement}-trophy" aria-hidden="true">
          <svg viewBox="0 0 220 300" role="img" focusable="false">
            <defs>
              <linearGradient id="wcGold" x1="18%" x2="86%" y1="2%" y2="100%"><stop offset="0" stop-color="#fff6c7"/><stop offset="0.18" stop-color="#ffd76d"/><stop offset="0.45" stop-color="#c99224"/><stop offset="0.72" stop-color="#ffe69a"/><stop offset="1" stop-color="#9f6817"/></linearGradient>
              <linearGradient id="wcGreen" x1="0" x2="1"><stop offset="0" stop-color="#37d49a"/><stop offset="1" stop-color="#0f8d68"/></linearGradient>
              <radialGradient id="wcGlow" cx="50%" cy="38%" r="66%"><stop offset="0" stop-color="#ffe8a5" stop-opacity="0.92"/><stop offset="0.58" stop-color="#d5a63a" stop-opacity="0.24"/><stop offset="1" stop-color="#07111f" stop-opacity="0"/></radialGradient>
            </defs>
            <ellipse cx="110" cy="150" rx="94" ry="124" fill="url(#wcGlow)"/>
            <path d="M70 52c-24 10-39 30-38 55 1 31 25 51 57 64l7-25c-23-10-34-23-34-39 0-15 9-25 24-32l-16-23Z" fill="url(#wcGold)" opacity=".94"/>
            <path d="M150 52c24 10 39 30 38 55-1 31-25 51-57 64l-7-25c23-10 34-23 34-39 0-15-9-25-24-32l16-23Z" fill="url(#wcGold)" opacity=".94"/>
            <path d="M76 44c7-19 24-30 34-30s27 11 34 30c11 30-2 64-20 86-8 10-12 24-12 39v22H108v-22c0-15-4-29-12-39-18-22-31-56-20-86Z" fill="url(#wcGold)" stroke="rgba(255,255,255,.52)" stroke-width="3"/>
            <path d="M79 92c26-12 56-9 76 12-5 17-15 31-29 43-15-17-37-25-61-20 2-13 7-25 14-35Z" fill="url(#wcGreen)" opacity=".90"/>
            <path d="M74 170c24 18 50 18 72 0 2 16 7 30 16 42H58c9-12 14-26 16-42Z" fill="url(#wcGold)"/>
            <path d="M85 212h50l10 48H75l10-48Z" fill="url(#wcGold)"/>
            <path d="M56 263h108l18 23H38l18-23Z" fill="url(#wcGold)"/>
            <path d="M75 286h70" stroke="#fff3c1" stroke-opacity=".62" stroke-width="4" stroke-linecap="round"/>
            <circle cx="108" cy="50" r="20" fill="#fff4ba" fill-opacity=".30"/>
          </svg>
        </div>"""

def render_html(data: dict[str, Any], output: Path) -> None:
    output.write_text(_page(data), encoding="utf-8")


def _page(data: dict[str, Any]) -> str:
    worldcup_data = data.get("worldcup", data)
    champions_data = data.get("champions_league")
    leagues_data = data.get("leagues")
    mercato_data = data.get("mercato_live", {})
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
    world_cup_news = (data.get("general_news") or data.get("world_cup_news", []))[:6]
    france_news = data.get("france_news", [])[:6]
    group_total = data.get("group_matches_total", _count_matches(group_matches))
    group_remaining = data.get("group_matches_remaining", _count_remaining_groups(group_matches))
    knockout_total = data.get("knockout_matches_total", _count_knockout(knockout))
    knockout_remaining = data.get("knockout_matches_remaining", _count_remaining_knockout(knockout))
    competition_stage = data.get("competition_stage", "Phase de groupes")
    france_next_match = data.get("france_next_match")
    teams_details = _merged_teams_details(data, champions_data, leagues_data)
    prediction_matches = _global_prediction_matches(data, champions_data, leagues_data)

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
    html, body {{ max-width: 100%; overflow-x: hidden; }}
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
    .hero.champions {{
      background:
        linear-gradient(135deg, rgba(5,12,35,0.96), rgba(17,33,77,0.82)),
        radial-gradient(circle at 75% 35%, rgba(132,173,255,0.32), transparent 14rem);
    }}
    .hero.champions::after {{ display: none; }}
    .leagues-hero::after {{ display: none; }}
    .hero-logo-mark {{ position: absolute; z-index: 0; right: clamp(26px, 8vw, 110px); top: 50%; transform: translateY(-50%); width: clamp(150px, 21vw, 260px); aspect-ratio: 0.74; display: grid; place-items: center; opacity: 0.96; pointer-events: none; }}
    .premium-trophy svg {{ width: 100%; height: 100%; display: block; overflow: visible; }}
    .worldcup-trophy {{ filter: drop-shadow(0 0 22px rgba(245,201,107,0.32)) drop-shadow(0 18px 34px rgba(0,0,0,0.30)); }}
    .ucl-trophy {{ filter: drop-shadow(0 0 24px rgba(180,210,255,0.30)) drop-shadow(0 18px 34px rgba(0,0,0,0.32)); }}
    .hero.champions .hero-logo-mark {{ opacity: 0.96; }}
    .league-focus-backdrop {{
      position: absolute;
      right: clamp(22px, 7vw, 96px);
      top: clamp(36px, 7vw, 70px);
      width: clamp(120px, 21vw, 230px);
      aspect-ratio: 1;
      display: grid;
      place-items: center;
      opacity: 0.48;
      pointer-events: none;
      z-index: 0;
      filter: drop-shadow(0 0 34px rgba(245,201,107,0.25));
    }}
    .league-focus-backdrop img {{ width: 100%; height: 100%; object-fit: contain; }}
    .league-focus-backdrop .flag.placeholder {{ width: 100%; height: 100%; border-radius: 28px; margin: 0; }}
    .mercato-ticker {{
      margin: 18px 0 16px;
      border: 1px solid rgba(245,201,107,0.24);
      border-radius: 18px;
      background: linear-gradient(90deg, rgba(7,17,31,0.96), rgba(16,38,66,0.94));
      overflow: hidden;
      box-shadow: 0 18px 42px rgba(0,0,0,0.22);
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: stretch;
    }}
    .mercato-badge {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 15px;
      color: #07111f;
      background: linear-gradient(180deg, #ffe1a0, #d5a63a);
      font-size: 12px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: .04em;
      white-space: nowrap;
    }}
    .mercato-badge::before {{
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #ef3340;
      box-shadow: 0 0 14px rgba(239,51,64,0.75);
    }}
    .mercato-track {{ min-width: 0; overflow: hidden; display: flex; align-items: center; }}
    .mercato-marquee {{ display: flex; width: max-content; animation: mercato-scroll 42s linear infinite; will-change: transform; }}
    .mercato-track:hover .mercato-marquee {{ animation-play-state: paused; }}
    .mercato-items {{ display: flex; align-items: center; gap: 28px; padding: 0 28px; white-space: nowrap; }}
    .mercato-link {{ display: inline-flex; align-items: center; gap: 8px; color: #eaf4ff; text-decoration: none; font-size: 14px; font-weight: 850; }}
    .mercato-link:hover, .mercato-link:focus-visible {{ color: #ffe1a0; outline: none; }}
    .mercato-time {{ color: #ffe1a0; font-size: 12px; font-weight: 950; }}
    .mercato-entity {{ color: #ffb7bd; font-size: 12px; font-weight: 950; }}
    .mercato-source {{ color: #8fa8c4; font-size: 12px; font-weight: 800; }}
    .mercato-empty {{ padding: 12px 16px; color: #c5d3e4; font-size: 14px; font-weight: 850; }}
    @keyframes mercato-scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
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
    .season-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      width: min(1180px, calc(100% - 32px));
      margin: -12px auto 28px;
      padding: 8px;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 18px;
      background: rgba(4,13,25,0.62);
      backdrop-filter: blur(14px);
      box-shadow: 0 14px 34px rgba(0,0,0,0.20);
    }}
    .season-tabs .tab-button {{ padding: 9px 13px; font-size: 13px; }}
    .season-tabs-label {{
      display: inline-flex;
      align-items: center;
      padding: 0 8px;
      color: #8fa8c4;
      font-size: 12px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: .04em;
    }}
    .tab-panel {{ display: block; min-width: 0; max-width: 100%; }}
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
      display: none;
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
    .pill {{ gap: 8px; padding: 9px 12px; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14); color: #e9f4ff; font-size: 13px; flex-wrap: wrap; min-width: 0; max-width: 100%; line-height: 1.25; overflow-wrap: normal; word-break: normal; }}
    .pill .flag {{ width: 18px; height: 18px; margin-right: 2px; flex: 0 0 auto; }}
    .focus-pill {{ display: inline-flex; align-items: center; gap: 8px; }}
    .focus-select {{ width: auto; max-width: min(48vw, 240px); min-width: 132px; padding: 5px 24px 5px 8px; border-radius: 999px; font-size: 12px; font-weight: 900; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); }}
    .next-match-pill {{ flex-wrap: nowrap; white-space: nowrap; overflow-wrap: normal; word-break: keep-all; font-size: clamp(9px, 2.4vw, 13px); align-items: center; }}
    .next-match-pill .focus-match-text {{ white-space: nowrap; min-width: 0; }}
    .france-pill::before {{ content: none; }}
    .section-head {{ display: flex; align-items: end; justify-content: space-between; gap: 18px; margin: 34px 0 14px; }}
    .section-title {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
    h2 {{ font-size: clamp(24px, 3vw, 34px); line-height: 1.05; }}
    .section-note {{ color: var(--muted); font-size: 14px; max-width: 540px; text-align: right; }}
    .alltime-badge {{ appearance: none; border: 1px solid rgba(245,201,107,0.34); border-radius: 999px; background: rgba(245,201,107,0.10); color: #ffe1a0; padding: 7px 10px; font: inherit; font-size: 12px; font-weight: 950; cursor: pointer; }}
    .alltime-badge:hover, .alltime-badge:focus-visible {{ background: rgba(245,201,107,0.18); outline: 1px solid rgba(245,201,107,0.45); }}
    .history-badge {{ align-self: center; }}
    .action-button {{ appearance: none; border: 1px solid rgba(255,255,255,0.16); border-radius: 999px; background: rgba(255,255,255,0.10); color: var(--ink); padding: 9px 12px; font: inherit; font-size: 13px; font-weight: 900; cursor: pointer; text-decoration: none; }}
    .action-button:hover, .action-button:focus-visible {{ background: rgba(255,255,255,0.17); outline: 1px solid rgba(255,255,255,0.28); }}
    .today-strip, .leaders, .news, .grid, .matches, .calendar-days {{ display: grid; gap: 16px; }}
    .today-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 18px; }}
    .leaders {{ grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }}
    .news {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .standings-wide {{ grid-template-columns: 1fr; width: 100%; }}
    .standings-wide .card {{ width: 100%; max-width: none; }}
    .standings-wide .table-scroll {{ width: 100%; }}
    .standings-wide table {{ min-width: 820px; table-layout: auto; }}
    .standings-wide th:nth-child(2), .standings-wide td:nth-child(2) {{ min-width: 340px; width: 42%; }}
    .matches {{ grid-template-columns: repeat(auto-fit, minmax(370px, 1fr)); }}
    .calendar-days {{ grid-template-columns: 1fr; }}
    .calendar-day .matches {{ grid-template-columns: 1fr; }}
    .today-tile, .card, .notice {{ background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.055)); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 14px 36px rgba(0,0,0,0.20); backdrop-filter: blur(14px); overflow: hidden; }}
    .today-tile {{ padding: 16px; min-height: 104px; position: relative; }}
    .today-meta {{ text-align: center; margin: 0 0 10px; font-weight: 850; }}
    .today-tile::after {{ content: ""; position: absolute; inset: auto 14px 12px 14px; height: 3px; border-radius: 999px; background: linear-gradient(90deg, var(--blue), var(--white), var(--red)); opacity: 0.72; }}
    .subtle {{ color: var(--muted); font-size: 12px; }}
    .card h3 {{ padding: 16px 16px 0; font-size: 17px; }}
    .card.france {{ border-color: rgba(255,255,255,0.22); background: linear-gradient(90deg, rgba(31,111,235,0.28), rgba(255,255,255,0.08), rgba(239,51,64,0.22)), linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.06)); }}
    .flag {{ width: 24px; height: 24px; flex: 0 0 24px; border-radius: 50%; object-fit: cover; vertical-align: middle; margin-right: 8px; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.14); }}
    .flag.placeholder {{ display: inline-grid; place-items: center; color: #9fb0c2; font-size: 11px; }}
    .team {{ font-weight: 850; }}
    .team-button {{ appearance: none; border: 0; background: transparent; color: inherit; font: inherit; font-weight: inherit; display: inline-flex; align-items: center; gap: 0; max-width: 100%; min-width: 0; white-space: normal; overflow-wrap: break-word; word-break: normal; line-height: 1.18; padding: 2px 3px; margin: -2px -3px; border-radius: 999px; cursor: pointer; text-align: inherit; }}
    .team-button:hover, .team-button:focus-visible {{ color: #fff; background: rgba(245,201,107,0.14); outline: 1px solid rgba(245,201,107,0.34); }}
    .away .team-button {{ justify-content: flex-end; }}
    .table-scroll {{ width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; color: #edf6ff; }}
    th, td {{ padding: 10px 9px; border-bottom: 1px solid rgba(255,255,255,0.08); text-align: right; vertical-align: middle; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ color: #91a6bb; font-size: 11px; text-transform: uppercase; background: rgba(255,255,255,0.035); }}
    tr:last-child td {{ border-bottom: 0; }}
    .empty {{ padding: 18px 16px 20px; color: var(--muted); font-size: 14px; }}
    .player-card {{ padding: 16px; display: grid; grid-template-columns: 62px 1fr; gap: 14px; align-items: center; }}
    .player-card.rank-1, .player-card.rank-2, .player-card.rank-3 {{ position: relative; overflow: hidden; }}
    .player-card.rank-1 {{ border-color: rgba(245,201,107,0.68); background: linear-gradient(145deg, rgba(245,201,107,0.20), rgba(255,255,255,0.075)); box-shadow: 0 18px 42px rgba(245,201,107,0.12); }}
    .player-card.rank-2 {{ border-color: rgba(215,226,238,0.54); background: linear-gradient(145deg, rgba(215,226,238,0.16), rgba(255,255,255,0.065)); }}
    .player-card.rank-3 {{ border-color: rgba(205,127,50,0.58); background: linear-gradient(145deg, rgba(205,127,50,0.16), rgba(255,255,255,0.065)); }}
    .player-card.rank-1 .avatar {{ border-color: rgba(245,201,107,0.88); box-shadow: 0 0 0 4px rgba(245,201,107,0.14); }}
    .player-card.rank-2 .avatar {{ border-color: rgba(215,226,238,0.82); box-shadow: 0 0 0 4px rgba(215,226,238,0.12); }}
    .player-card.rank-3 .avatar {{ border-color: rgba(205,127,50,0.82); box-shadow: 0 0 0 4px rgba(205,127,50,0.12); }}
    .player-card.big5-card {{ position: relative; overflow: hidden; }}
    .player-card.big5-card::before {{ content: ""; position: absolute; inset: 0; opacity: 0.16; pointer-events: none; }}
    .player-card.big5-card > * {{ position: relative; z-index: 1; }}
    .league-bg-ligue1::before {{ background: linear-gradient(90deg, #0055a4 0 33%, #fff 33% 66%, #ef4135 66%); }}
    .league-bg-laliga::before {{ background: linear-gradient(180deg, #aa151b 0 28%, #f1bf00 28% 72%, #aa151b 72%); }}
    .league-bg-bundesliga::before {{ background: linear-gradient(180deg, #000 0 33%, #dd0000 33% 66%, #ffce00 66%); }}
    .league-bg-premierleague::before {{ background: linear-gradient(90deg, #fff 0 18%, #c8102e 18% 34%, #fff 34% 66%, #c8102e 66% 82%, #fff 82%); }}
    .league-bg-seriea::before {{ background: linear-gradient(90deg, #009246 0 33%, #fff 33% 66%, #ce2b37 66%); }}
    .avatar-wrap {{ position: relative; width: 62px; height: 62px; }}
    .avatar {{ width: 62px; height: 62px; border-radius: 50%; object-fit: cover; background: radial-gradient(circle at 35% 30%, #dbe7f7, #708196); border: 2px solid rgba(255,255,255,0.16); }}
    .avatar.placeholder {{ display: grid; place-items: center; color: #07111f; }}
    .avatar.placeholder::before {{ content: ""; width: 30px; height: 36px; border-radius: 9px 9px 12px 12px; background: linear-gradient(180deg, #ffffff, #9fb0c2); box-shadow: inset 0 -10px 0 rgba(7,17,31,0.15); }}
    .club-line {{ display: inline-flex; align-items: center; gap: 7px; min-width: 0; max-width: 100%; }}
    .club-logo {{ width: 22px; height: 22px; flex: 0 0 22px; border-radius: 50%; object-fit: contain; padding: 2px; background: rgba(255,255,255,0.90); border: 1px solid rgba(255,255,255,0.18); }}
    .club-logo.placeholder {{ display: inline-grid; place-items: center; background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.07)); padding: 0; }}
    .club-logo.placeholder::before {{ content: ""; width: 12px; height: 15px; border-radius: 3px 3px 5px 5px; background: linear-gradient(180deg, #dbe7f7, #708196); }}
    .club-name {{ white-space: normal; overflow-wrap: break-word; word-break: normal; line-height: 1.18; }}
    .player-country-flag {{ position: absolute; right: -2px; bottom: -2px; width: 22px; height: 22px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(7,17,31,0.92); background: rgba(255,255,255,0.14); }}
    .player-stat {{ color: var(--gold); font-size: 28px; font-weight: 950; line-height: 1; margin-top: 8px; }}
    .rank-note {{ color: #b7c6d7; font-size: 12px; margin-top: 5px; }}
    .today-teams {{ display: grid; grid-template-columns: minmax(0, 1.3fr) clamp(70px, 10vw, 96px) minmax(0, 1.3fr); align-items: center; gap: 14px; }}
    .today-team {{ min-width: 0; text-align: center; font-weight: 900; font-size: clamp(13px, 1.15vw, 15px); line-height: 1.18; }}
    .today-team .team-button {{ justify-content: center; }}
    .today-score {{ min-width: 70px; text-align: center; font-size: clamp(20px, 2.4vw, 26px); line-height: 1.08; font-weight: 950; color: var(--gold); }}
    .day-card {{ padding: 0; }}
    .day-card h3 {{ padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #ffe1a0; }}
    .day-list {{ padding: 6px 14px 14px; }}
    .calendar-match {{ display: grid; grid-template-columns: 70px minmax(0, 1fr) 76px minmax(0, 1fr) 130px; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }}
    .league-calendar-match {{
      grid-template-columns: minmax(98px, 0.72fr) minmax(0, 1.45fr) 84px minmax(0, 1.45fr) minmax(160px, 0.9fr);
      gap: 14px;
      padding: 14px 16px;
      min-height: 72px;
    }}
    .league-calendar-match > div {{ min-width: 0; }}
    .league-calendar-match .team-button {{ width: 100%; gap: 6px; }}
    .league-calendar-match .away .team-button {{ justify-content: flex-end; }}
    .league-calendar-match .score {{ justify-self: center; }}
    .calendar-match:last-child {{ border-bottom: 0; }}
    .match-meta {{ min-width: 0; }}
    .match-group {{ color: var(--gold); font-size: 12px; font-weight: 900; text-transform: uppercase; }}
    .date {{ color: #9cafc2; font-size: 12px; line-height: 1.35; }}
    .away {{ text-align: right; }}
    .score {{ min-width: 54px; text-align: center; font-weight: 950; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); border-radius: 9px; padding: 6px 8px; }}
    .status {{ padding: 4px 8px; font-size: 12px; background: rgba(31,111,235,0.18); color: #b9d7ff; margin-top: 5px; }}
    .status.done {{ background: rgba(50,211,162,0.18); color: #9ff0d5; }}
    .status.live {{ background: rgba(239,51,64,0.22); color: #ffb8bf; box-shadow: 0 0 0 1px rgba(239,51,64,0.45); }}
    .article {{ min-height: 310px; display: flex; flex-direction: column; position: relative; }}
    .article-visual {{ position: relative; height: 132px; overflow: hidden; background: radial-gradient(circle at 28% 20%, rgba(245,201,107,0.22), transparent 10rem), linear-gradient(135deg, rgba(31,111,235,0.18), rgba(239,51,64,0.12)); }}
    .article-image {{ width: 100%; height: 100%; object-fit: cover; display: block; opacity: 0.92; }}
    .article-image.is-hidden {{ display: none; }}
    .article-visual-fallback {{ width: 100%; height: 100%; display: grid; place-items: center; color: rgba(255,255,255,0.72); font-size: 12px; font-weight: 950; text-transform: uppercase; letter-spacing: .08em; }}
    .article-source {{ position: absolute; left: 12px; top: 12px; display: inline-flex; align-items: center; gap: 8px; max-width: calc(100% - 24px); padding: 6px 9px; border-radius: 999px; background: rgba(7,17,31,0.76); border: 1px solid rgba(255,255,255,0.16); backdrop-filter: blur(10px); color: #f3f8ff; font-size: 11px; font-weight: 950; text-transform: uppercase; }}
    .source-logo {{ width: 20px; height: 20px; flex: 0 0 20px; border-radius: 50%; object-fit: contain; background: rgba(255,255,255,0.94); padding: 2px; }}
    .source-logo.is-hidden {{ display: none; }}
    .article-body {{ padding: 15px 16px 16px; display: flex; flex-direction: column; flex: 1; }}
    .article h3 {{ padding: 0; font-size: 16px; line-height: 1.25; }}
    .article p {{ color: #b7c6d7; font-size: 13px; line-height: 1.5; margin: 11px 0 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
    .article-meta {{ color: #95a9bd; font-size: 12px; margin-bottom: 10px; text-transform: uppercase; font-weight: 800; }}
    .read-link {{ margin-top: auto; padding-top: 14px; font-weight: 850; font-size: 13px; text-decoration: none; }}
    .bracket-wrap {{ width: 100%; max-width: 100%; overflow-x: visible; padding: 8px 0 18px; }}
    .bracket-wrap::-webkit-scrollbar {{ height: 9px; }}
    .bracket-wrap::-webkit-scrollbar-track {{ background: rgba(255,255,255,0.08); border-radius: 999px; }}
    .bracket-wrap::-webkit-scrollbar-thumb {{ background: rgba(245,201,107,0.55); border-radius: 999px; }}
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
      grid-template-columns: repeat(4, minmax(0, 1fr));
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
    .ko-line {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; font-weight: 850; margin: 6px 0; font-size: clamp(10px, 0.92vw, 13px); }}
    .bracket-team {{ appearance: none; border: 0; background: transparent; color: inherit; font: inherit; font-weight: 900; display: grid; justify-items: center; gap: 4px; min-width: 0; width: 100%; padding: 2px; cursor: pointer; text-align: center; }}
    .bracket-team .flag {{ margin: 0; width: 22px; height: 22px; }}
    .bracket-team-name {{ display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; white-space: normal; overflow-wrap: break-word; word-break: normal; line-height: 1.12; }}
    .ko-score {{ font-weight: 950; color: #07111f; min-width: 22px; text-align: center; }}
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
    .bracket-logo {{ width: clamp(88px, 9vw, 132px); aspect-ratio: 0.74; margin: 0 auto 12px; display: grid; place-items: center; }}
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
    .coach-card {{ display: grid; gap: 14px; padding: 14px; border: 1px solid rgba(245,201,107,0.20); border-radius: 16px; background: linear-gradient(135deg, rgba(245,201,107,0.10), rgba(31,111,235,0.10)); }}
    .coach-profile {{ display: grid; grid-template-columns: 62px minmax(0, 1fr); gap: 12px; align-items: center; }}
    .coach-photo {{ width: 62px; height: 62px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(255,255,255,0.18); background: radial-gradient(circle at 35% 30%, #dbe7f7, #708196); }}
    .coach-photo.placeholder {{ display: grid; place-items: center; color: #07111f; font-weight: 950; font-size: 11px; }}
    .coach-name {{ font-size: 20px; font-weight: 950; line-height: 1.1; }}
    .coach-stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .coach-stat {{ padding: 11px; border-radius: 13px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.06); }}
    .coach-stat strong {{ display: block; color: var(--gold); font-size: 22px; line-height: 1; }}
    .coach-stat span {{ display: block; margin-top: 5px; color: var(--muted); font-size: 12px; font-weight: 850; text-transform: uppercase; }}
    .coach-source {{ color: var(--muted); font-size: 12px; font-weight: 800; }}
    .honors-list {{ display: grid; gap: 9px; }}
    .honor-row {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 11px; border-radius: 13px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.055); }}
    .honor-row strong {{ display: block; line-height: 1.16; }}
    .honor-value {{ color: var(--gold); font-weight: 950; white-space: nowrap; }}
    .formation-board {{ min-height: 140px; display: grid; place-items: center; border: 1px dashed rgba(245,201,107,0.30); border-radius: 16px; background: radial-gradient(ellipse at center, rgba(50,211,162,0.14), transparent 68%), linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.035)); color: #d6e5f7; font-weight: 850; }}
    .roster-section h3 {{ padding: 0; margin-bottom: 10px; color: #ffe1a0; }}
    .player-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }}
    .mini-player {{ display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 10px; align-items: center; padding: 10px; border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; background: rgba(255,255,255,0.055); min-width: 0; }}
    .mini-player strong {{ display: block; overflow-wrap: break-word; word-break: normal; line-height: 1.15; }}
    .mini-avatar {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; background: radial-gradient(circle at 35% 30%, #dbe7f7, #708196); }}
    .mini-avatar.placeholder {{ display: grid; place-items: center; color: #07111f; font-weight: 950; }}
    .mini-player-meta {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 4px; color: var(--muted); font-size: 12px; font-weight: 750; }}
    .mini-player-flag {{ width: 18px; height: 18px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(255,255,255,0.18); }}
    .mini-player-number {{ color: #07111f; background: linear-gradient(180deg, #ffe1a0, #d5a63a); border-radius: 999px; padding: 2px 7px; font-size: 11px; font-weight: 950; }}
    .alltime-list {{ display: grid; gap: 10px; }}
    .chatbot-dialog {{ width: min(430px, 100%); max-height: min(78vh, 620px); display: grid; grid-template-rows: auto minmax(190px, 1fr) auto; overflow: hidden; }}
    .chatbot-messages {{ padding: 14px; display: grid; gap: 10px; align-content: start; overflow-y: auto; min-height: 220px; max-height: min(48vh, 430px); scrollbar-width: thin; scrollbar-color: rgba(245,201,107,0.55) rgba(255,255,255,0.08); }}
    .chatbot-messages::-webkit-scrollbar {{ width: 8px; }}
    .chatbot-messages::-webkit-scrollbar-track {{ background: rgba(255,255,255,0.08); border-radius: 999px; }}
    .chatbot-messages::-webkit-scrollbar-thumb {{ background: rgba(245,201,107,0.55); border-radius: 999px; }}
    .recent-list {{ display: grid; gap: 10px; }}
    .recent-match {{ display: grid; grid-template-columns: minmax(110px, 0.8fr) minmax(0, 1.5fr) auto auto; gap: 12px; align-items: center; padding: 12px; border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; background: rgba(255,255,255,0.055); }}
    .recent-score {{ color: var(--gold); font-size: 18px; font-weight: 950; white-space: nowrap; }}
    .recent-result {{ justify-self: end; border-radius: 999px; padding: 5px 9px; font-size: 11px; font-weight: 950; background: rgba(255,255,255,0.10); }}
    .recent-result.win {{ color: #9af6d3; background: rgba(50,211,162,0.15); }}
    .recent-result.draw {{ color: #ffe1a0; background: rgba(245,201,107,0.14); }}
    .recent-result.loss {{ color: #ffb4bd; background: rgba(239,51,64,0.14); }}
    .chatbot-message {{ max-width: 86%; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.07); color: #dfeeff; line-height: 1.48; font-size: 14px; white-space: normal; }}
    .chatbot-message p {{ margin: 0 0 8px; }}
    .chatbot-message p:last-child {{ margin-bottom: 0; }}
    .chatbot-message ul {{ margin: 8px 0 0; padding-left: 18px; }}
    .chatbot-message.user {{ justify-self: end; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); }}
    .chatbot-message.bot {{ justify-self: start; }}
    .chatbot-form {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; padding: 14px; border-top: 1px solid rgba(255,255,255,0.10); }}
    .alltime-row {{ display: grid; grid-template-columns: 44px 52px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 12px; border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; background: rgba(255,255,255,0.06); }}
    .alltime-rank {{ width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; color: #07111f; background: linear-gradient(180deg, #ffe1a0, #d5a63a); font-weight: 950; }}
    .alltime-value {{ color: var(--gold); font-size: 24px; font-weight: 950; text-align: right; }}
    .community-grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .community-panel {{ padding: 16px; }}
    .community-predictions {{ display: grid; grid-template-columns: minmax(0, 1.18fr) minmax(240px, 0.52fr); gap: 16px; align-items: start; }}
    .community-side {{ min-width: 0; }}
    .follow-zone {{ display: grid; gap: 12px; }}
    .follow-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .follow-card {{ padding: 13px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.10); background: radial-gradient(circle at center, rgba(245,201,107,0.10), transparent 18rem), rgba(255,255,255,0.055); }}
    .follow-meta {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; font-weight: 850; text-transform: uppercase; }}
    .follow-teams {{ display: grid; grid-template-columns: minmax(0, 1.25fr) clamp(62px, 9vw, 84px) minmax(0, 1.25fr); align-items: center; gap: 10px; margin-top: 12px; }}
    .follow-team {{ min-width: 0; display: flex; align-items: center; gap: 8px; font-weight: 950; line-height: 1.18; overflow-wrap: normal; word-break: normal; }}
    .follow-team.away {{ justify-content: flex-end; text-align: right; }}
    .follow-team span:last-child {{ white-space: normal; overflow-wrap: normal; word-break: normal; }}
    .follow-center {{ min-width: 62px; text-align: center; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); border-radius: 10px; padding: 7px 9px; font-weight: 950; }}
    .follow-status {{ display: inline-flex; align-items: center; justify-content: center; margin-top: 10px; padding: 4px 8px; border-radius: 999px; color: #b9d7ff; background: rgba(31,111,235,0.18); font-size: 12px; font-weight: 900; }}
    .follow-status.done {{ color: #9ff0d5; background: rgba(50,211,162,0.18); }}
    .follow-status.live {{ color: #ffb8bf; background: rgba(239,51,64,0.22); box-shadow: 0 0 0 1px rgba(239,51,64,0.45); }}
    .community-form {{ display: grid; gap: 10px; margin-top: 12px; }}
    .pseudo-row {{ display: grid; gap: 6px; }}
    .pseudo-row label {{ color: var(--muted); font-size: 12px; font-weight: 900; text-transform: uppercase; }}
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
    .prediction-team-name {{ min-width: 0; white-space: normal; overflow-wrap: normal; word-break: normal; line-height: 1.18; }}
    .prediction-scoreboard input {{ width: 64px; text-align: center; font-size: 22px; font-weight: 950; color: #07111f; background: linear-gradient(180deg, #ffffff, #c8d6e6); }}
    .prediction-separator {{ color: var(--gold); font-size: 26px; font-weight: 950; }}
    .community-status {{ margin-top: 10px; color: #ffe1a0; font-size: 13px; min-height: 18px; }}
    .match-context {{ text-align: center; color: var(--muted); font-size: 12px; font-weight: 800; }}
    .coach-prediction {{ display: grid; gap: 7px; padding: 12px; border: 1px solid rgba(245,201,107,0.24); border-radius: 14px; background: linear-gradient(135deg, rgba(245,201,107,0.12), rgba(31,111,235,0.10)); color: #eaf4ff; }}
    .coach-prediction-top {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-weight: 950; }}
    .coach-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border-radius: 999px; color: #07111f; background: linear-gradient(180deg, #ffe1a0, #d5a63a); font-size: 12px; font-weight: 950; }}
    .coach-reason {{ color: #d6e5f7; font-size: 13px; line-height: 1.4; }}
    .coach-disclaimer {{ color: var(--muted); font-size: 11px; font-weight: 800; }}
    @media (max-width: 860px) {{
      main {{ width: min(100% - 20px, 1240px); padding-top: 14px; }}
      .app-top {{ grid-template-columns: 1fr; align-items: start; }}
      .global-controls {{ justify-content: flex-start; }}
      .mercato-ticker {{ grid-template-columns: 1fr; }}
      .mercato-badge {{ justify-content: center; }}
      .mercato-marquee {{ animation-duration: 34s; }}
      .hero {{ min-height: 430px; border-radius: 14px; }}
      .hero::after {{ right: 18px; top: auto; bottom: 28px; opacity: 0.30; }}
      .hero-logo-mark {{ right: 18px; top: auto; bottom: 30px; transform: none; width: clamp(92px, 25vw, 138px); opacity: 0.62; }}
      .league-focus-backdrop {{ right: 20px; top: auto; bottom: 26px; opacity: 0.24; width: clamp(110px, 34vw, 170px); }}
      .section-head {{ align-items: start; flex-direction: column; }}
      .section-note {{ text-align: left; }}
      .today-strip {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .news, .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .matches {{ grid-template-columns: 1fr; }}
      .calendar-match {{ grid-template-columns: 62px minmax(0, 1fr) 58px minmax(0, 1fr); gap: 8px; }}
      .league-calendar-match {{ grid-template-columns: 80px minmax(0, 1fr) 64px minmax(0, 1fr); padding: 12px; }}
      .league-calendar-match .match-meta {{ grid-column: 1 / -1; }}
      .standings-wide table {{ min-width: 680px; }}
      .match-meta {{ grid-column: 1 / -1; display: flex; gap: 10px; flex-wrap: wrap; }}
      th, td {{ padding: 8px 6px; }}
      .bracket-wrap {{ overflow-x: auto; scrollbar-width: thin; scrollbar-color: rgba(245,201,107,0.55) rgba(255,255,255,0.08); }}
      .bracket-stage {{ width: max-content; min-width: 1120px; grid-template-columns: minmax(0, 440px) 190px minmax(0, 440px); gap: 12px; }}
      .bracket-stage.ucl-official {{ min-width: 1120px; grid-template-columns: minmax(0, 440px) 190px minmax(0, 440px); }}
      .bracket-center {{ order: initial; }}
      .bracket-wing {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .bracket-wing.ucl-wing {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
      .bracket-wing.left::after, .bracket-wing.right::before, .round::after, .ko-match::before {{ display: block; }}
      .trophy-card {{ min-height: 150px; }}
      .team-dialog {{ max-height: 90vh; }}
      .alltime-row {{ grid-template-columns: 38px 46px minmax(0, 1fr); }}
      .alltime-value {{ grid-column: 3; font-size: 20px; text-align: left; }}
      .community-grid, .community-predictions, .field-row, .follow-list {{ grid-template-columns: 1fr; }}
      .prediction-scoreboard {{ grid-template-columns: minmax(0, 1fr) auto auto auto minmax(0, 1fr); gap: 8px; }}
    }}
    @media (max-width: 480px) {{
      h1 {{ font-size: 40px; }}
      .next-match-pill {{ width: 100%; justify-content: center; gap: 5px; padding-inline: 8px; font-size: clamp(8px, 2.65vw, 11px); }}
      .next-match-pill .flag, .pill .flag {{ width: 15px; height: 15px; }}
      .app-title {{ font-size: clamp(34px, 12vw, 44px); }}
      .app-copy {{ font-size: 14px; }}
      .global-controls {{ width: 100%; }}
      .action-button {{ flex: 1 1 130px; text-align: center; }}
      .mercato-link {{ font-size: 13px; }}
      .mercato-items {{ gap: 20px; padding: 0 20px; }}
      .today-strip, .leaders, .news, .grid, .matches {{ grid-template-columns: 1fr; }}
      .calendar-match {{ grid-template-columns: 1fr auto 1fr; }}
      .league-calendar-match {{ grid-template-columns: 1fr; text-align: center; }}
      .league-calendar-match .away, .league-calendar-match .away .team-button {{ justify-content: center; text-align: center; }}
      .league-calendar-match .team-button {{ justify-content: center; }}
      .calendar-match .date, .calendar-match .match-meta {{ grid-column: 1 / -1; }}
      .standings-wide table {{ min-width: 620px; }}
      .bracket-stage {{ padding: 10px; min-width: 1040px; }}
      .bracket-stage.ucl-official {{ min-width: 1040px; }}
      .round {{ gap: 8px; }}
      .ko-line {{ font-size: 12px; }}
      .team-modal {{ padding: 10px; }}
      .team-modal-head {{ grid-template-columns: auto 1fr auto; padding: 14px; }}
      .team-modal-flag {{ width: 46px; height: 46px; }}
      .alltime-row {{ gap: 9px; padding: 10px; }}
      .today-teams, .follow-teams {{ grid-template-columns: minmax(0, 1fr); justify-items: center; }}
      .prediction-scoreboard {{ grid-template-columns: 1fr; justify-items: center; }}
      .prediction-team.home, .prediction-team.away, .follow-team, .follow-team.away {{ justify-content: center; text-align: center; }}
      .chatbot-form {{ grid-template-columns: 1fr; }}
      .recent-match {{ grid-template-columns: 1fr; }}
      .recent-result {{ justify-self: start; }}
      .coach-stats {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    {_app_header()}
    {_mercato_ticker(mercato_data)}
    {_tabs_nav(champions_data, leagues_data)}
    {_community_section()}
    <section class="tab-panel" id="tab-worldcup" data-tab-panel="worldcup">
    <section class="hero">
      {_competition_trophy_svg("worldcup", "hero")}
      <div class="hero-content">
        <div class="kicker"><span class="ball"></span> Coupe du Monde 2026</div>
        <h1>{escape(data.get("competition", "Coupe du Monde 2026"))}</h1>
        <p class="hero-copy">Centre de suivi automatisé des groupes, matchs, buteurs, passeurs, actualités et phases finales. Données publiées uniquement lorsqu’elles sont disponibles auprès des sources.</p>
        <div class="hero-badges">
          <div class="hero-row">
            <span class="pill">Mis à jour : {escape(generated)}</span>
            <button class="alltime-badge history-badge" type="button" data-alltime="worldcup-history">Palmarès</button>
            <span class="pill france-pill focus-pill"><span id="worldcupFocusIcon">{_flag(_focus_icon(data, "France"))}</span>Focus <select class="focus-select" id="worldcupFocusSelect" aria-label="Pays à suivre Coupe du Monde">{_focus_options(data, "France")}</select></span>
          </div>
          <div class="hero-row focus-match-row">
            <span class="pill next-match-pill" id="worldcupFocusNext" data-default-focus="France">{_france_next_match_badge(france_next_match)}</span>
          </div>
          <div class="hero-row">
            <span class="pill">{group_remaining}/{group_total} matchs de poules</span>
            <span class="pill">{knockout_remaining}/{knockout_total} matchs à élimination</span>
            <span class="pill">Avancement : {escape(competition_stage)}</span>
          </div>
        </div>
      </div>
    </section>

    {_season_tabs("worldcup", "Année", [("2026", "2026")])}

    {_errors(data.get("errors", []))}

    <section class="today-strip" aria-label="Matchs du jour">{_today_matches(today_matches, group_matches, knockout)}</section>

    {_section_head("Meilleurs buteurs", "Top 5 uniquement, avec photo si la source la fournit.", _all_time_badge("scorers"))}
    <section class="leaders">{_player_cards(scorers, "buts")}</section>

    {_section_head("Meilleurs passeurs", "Top 5 uniquement, avec photo si la source la fournit.")}
    <section class="leaders">{_player_cards(assists, "passes")}</section>

    {_dynamic_news_section("Actualité Coupe du Monde", "Actus générales + pays choisi dans le focus. Six articles maximum, triés par date.", "worldcupNewsBoard")}

    {_section_head("Arbre à élimination directe", "Bracket officiel horizontal : les deux ailes convergent vers la finale au centre.")}
    {render_worldcup_bracket(knockout)}

    {_section_head("Classements des groupes", "Drapeaux, points, différence de buts, matchs joués, victoires, nuls et défaites.")}
    <section class="grid">{''.join(_group_card(group) for group in groups) or _empty_block("Les classements ne sont pas encore disponibles.")}</section>

    {_section_head("Résultats et calendrier des poules", "Calendrier par journée, avec groupe, stade, statut et score central.")}
    <section class="calendar-days">{_calendar_by_day(group_matches)}</section>

    <nav class="sources" aria-label="Sources">{sources}</nav>
    </section>
    {_champions_tab(champions_data)}
    {_leagues_tab(leagues_data)}
  </main>
  {_team_modal()}
  {_all_time_modal()}
  {_football_chatbot_modal()}
  {_team_script(teams_details, prediction_matches)}
  {_all_time_script(all_time_scorers, champions_all_time_scorers)}
  {_community_script(prediction_matches)}
  {_news_script(data, champions_data, leagues_data)}
  {_focus_script(prediction_matches, teams_details)}
  {_leagues_script()}
  {_football_chatbot_script()}
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
          <button class="action-button" type="button" id="shareButton">Partager</button>
          <button class="action-button" type="button" id="chatbotButton">Coach</button>
          <a class="action-button" href="/watch-party">Watch Party</a>
        </div>
      </div>
    </header>
"""


def _merged_teams_details(worldcup_data: dict[str, Any], champions_data: dict[str, Any] | None, leagues_data: dict[str, Any] | None = None) -> dict[str, Any]:
    teams = dict(worldcup_data.get("teams_details", {}))
    if champions_data:
        teams.update(champions_data.get("teams_details", {}))
    for league in (leagues_data or {}).get("leagues", {}).values():
        teams.update(league.get("teams_details", {}))
    return teams


def _tabs_nav(champions_data: dict[str, Any] | None, leagues_data: dict[str, Any] | None = None) -> str:
    if not champions_data and not leagues_data:
        return ""
    leagues_button = '<button class="tab-button is-active" type="button" data-tab-target="leagues">Championnats</button>' if leagues_data else ''
    champions_button = '<button class="tab-button" type="button" data-tab-target="champions">Ligue des Champions</button>' if champions_data else ''
    worldcup_active = '' if leagues_data else ' is-active'
    return f"""
    <nav class="tabs-nav" aria-label="Compétitions">
      {leagues_button}
      {champions_button}
      <button class="tab-button{worldcup_active}" type="button" data-tab-target="worldcup">Coupe du Monde 2026</button>
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
    news = (data.get("general_news") or data.get("world_cup_news", []))[:6]
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
        {_competition_trophy_svg("champions", "hero")}
        <div class="hero-content">
          <div class="kicker"><span class="ball"></span> UEFA Champions League</div>
          <h1>{escape(data.get("competition", "Ligue des Champions"))}</h1>
          <p class="hero-copy">Suivi automatisé des matchs, du classement de phase de ligue, des statistiques joueurs, actualités et phase finale dès publication par les sources.</p>
          <div class="hero-badges">
            <div class="hero-row">
              <span class="pill">Mis à jour : {escape(generated)}</span>
              <button class="alltime-badge history-badge" type="button" data-alltime="champions-history">Palmarès</button>
              <span class="pill psg-pill focus-pill"><span id="championsFocusIcon">{_logo_or_placeholder(_focus_icon(data, "Paris Saint-Germain") or _psg_logo(data))}</span>Focus <select class="focus-select" id="championsFocusSelect" aria-label="Club à suivre Ligue des Champions">{_focus_options(data, "Paris Saint-Germain")}</select></span>
            </div>
            <div class="hero-row focus-match-row">
              <span class="pill next-match-pill" id="championsFocusNext" data-default-focus="Paris Saint-Germain">{_psg_next_match_badge(psg_next_match)}</span>
            </div>
            <div class="hero-row">
              <span class="pill">{phase_remaining}/{phase_total} matchs de phase de ligue</span>
              <span class="pill">{knockout_remaining}/{knockout_total} matchs à élimination</span>
              <span class="pill">Avancement : {escape(stage)}</span>
            </div>
          </div>
        </div>
      </section>

      {_season_tabs("champions", "Saison", [("2025-2026", "2025-2026")])}

      {_errors(data.get("errors", []))}

      <section class="today-strip" aria-label="Matchs du jour Ligue des Champions">{_today_matches(today_matches, matches, knockout)}</section>

      {_section_head("Meilleurs buteurs", "Top 5 Ligue des Champions, avec photo si la source la fournit.", _all_time_badge("champions-scorers"))}
      <section class="leaders">{_player_cards(scorers, "buts", prefer_country_flag=True)}</section>

      {_section_head("Meilleurs passeurs", "Top 5 Ligue des Champions, avec photo si la source la fournit.")}
      <section class="leaders">{_player_cards(assists, "passes", prefer_country_flag=True)}</section>

      {_dynamic_news_section("Actualité Ligue des Champions", "Actus générales + club choisi dans le focus. Six articles maximum, triés par date.", "championsNewsBoard")}

      {_section_head("Phase finale", "Bracket Ligue des Champions affiché dès disponibilité des matchs à élimination directe.")}
      {render_champions_league_bracket(knockout)}

      {_section_head("Classement de la phase de ligue", "Clubs, matchs joués, victoires, nuls, défaites, différence et points.")}
      <section class="grid standings-wide">{''.join(_group_card(group) for group in standings) or _empty_block("Le classement n’est pas encore disponible.")}</section>

      {_section_head("Résultats et calendrier", "Calendrier par journée, avec stade, statut et score central.")}
      <section class="calendar-days">{_calendar_by_day(matches)}</section>

      <nav class="sources" aria-label="Sources Ligue des Champions">{sources}</nav>
    </section>
"""



def _leagues_tab(data: dict[str, Any] | None) -> str:
    if not data:
        return ""
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    selected = data.get("selected_league", "ligue1")
    options = "".join(
        f'<option value="{escape(key, quote=True)}"{ " selected" if key == selected else ""}>{escape(league.get("name", key))}</option>'
        for key, league in (data.get("leagues") or {}).items()
    )
    return f"""
    <section class="tab-panel is-active" id="tab-leagues" data-tab-panel="leagues">
      <section class="hero leagues-hero">
        <div class="league-focus-backdrop" id="leagueFocusBackdrop" aria-hidden="true"></div>
        <div class="hero-content">
          <div class="kicker"><span class="ball"></span> Championnats européens</div>
          <h1>Championnats</h1>
          <p class="hero-copy">Suivi des 5 grands championnats : classement, calendrier, meilleurs joueurs, actualités club et prochains matchs.</p>
          <div class="hero-badges">
            <div class="hero-row">
              <span class="pill">Mis à jour : <span id="leaguesUpdated">{escape(_format_datetime(data.get('generated_at', ''), with_time=True))}</span></span>
              <button class="alltime-badge history-badge" type="button" id="leagueHonoursButton" data-alltime="league-history-ligue1">Palmarès</button>
              <span class="pill focus-pill">Championnat <select class="focus-select" id="leagueSelect" aria-label="Championnat à suivre">{options}</select></span>
              <span class="pill focus-pill"><span id="leagueFocusIcon"></span>Focus <select class="focus-select" id="leagueClubSelect" aria-label="Club à suivre"></select></span>
            </div>
            <div class="hero-row focus-match-row">
              <span class="pill next-match-pill" id="leagueFocusNext">Prochain match à déterminer</span>
            </div>
          </div>
        </div>
      </section>

      {_season_tabs("leagues", "Saison", [("2025-2026", "2025-2026")])}

      {_errors(data.get("errors", []))}

      <section class="today-strip" id="leagueUpcoming" aria-label="Matchs à venir championnat"></section>

      {_section_head("Meilleurs buteurs des 5 grands championnats", "Le meilleur buteur publié pour chaque championnat.")}
      <section class="leaders" id="big5TopScorers"></section>

      {_section_head("Meilleurs buteurs", "Top 5 du championnat sélectionné.")}
      <section class="leaders" id="leagueTopScorers"></section>

      {_section_head("Meilleurs passeurs", "Top 5 du championnat sélectionné, si disponible.")}
      <section class="leaders" id="leagueTopAssists"></section>

      {_dynamic_news_section("Actualité club", "Six derniers articles liés au club choisi dans le focus.", "leaguesNewsBoard")}

      {_section_head("Classement du championnat", "Clubs, matchs joués, victoires, nuls, défaites, différence et points.")}
      <section class="grid standings-wide" id="leagueStandings"></section>

      {_section_head("Calendrier / résultats", "Calendrier par journée du championnat sélectionné.")}
      <section class="calendar-days" id="leagueCalendar"></section>
    </section>
    <script id="leaguesData" type="application/json">{payload}</script>
  """

def _focus_options(data: dict[str, Any], selected: str) -> str:
    names = sorted(_focus_entities(data), key=lambda value: _display_focus_name(value).casefold())
    if selected and selected not in names:
        names.insert(0, selected)
    return "".join(
        f'<option value="{escape(name, quote=True)}"{ " selected" if name == selected else ""}>{escape(_display_focus_name(name))}</option>'
        for name in names
    )


def _focus_entities(data: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for group in data.get("group_matches", []):
        for match in group.get("matches", []):
            for key in ("home_team", "away_team"):
                name = str(match.get(key) or "").strip()
                if name and name != "À déterminer":
                    names.add(name)
    for round_data in data.get("knockout", []):
        for match in round_data.get("matches", []):
            for key in ("home_team", "away_team"):
                name = str(match.get(key) or "").strip()
                if name and name != "À déterminer":
                    names.add(name)
    for group in data.get("standings", []):
        for row in group.get("teams", []) or group.get("standings", []) or []:
            name = str(row.get("team") or row.get("name") or row.get("team_name") or "").strip()
            if name and name != "À déterminer":
                names.add(name)
    return names


def _focus_icon(data: dict[str, Any], name: str) -> str:
    details = (data.get("teams_details") or {}).get(name, {})
    if details.get("flag_url"):
        return str(details.get("flag_url") or "")
    for group in data.get("group_matches", []):
        for match in group.get("matches", []):
            if match.get("home_team") == name and match.get("home_flag_url"):
                return str(match.get("home_flag_url") or "")
            if match.get("away_team") == name and match.get("away_flag_url"):
                return str(match.get("away_flag_url") or "")
    for round_data in data.get("knockout", []):
        for match in round_data.get("matches", []):
            if match.get("home_team") == name and match.get("home_flag_url"):
                return str(match.get("home_flag_url") or "")
            if match.get("away_team") == name and match.get("away_flag_url"):
                return str(match.get("away_flag_url") or "")
    return _fallback_team_asset(name)


def _display_focus_name(name: str) -> str:
    aliases = {
        "Paris Saint-Germain": "PSG",
        "Paris SG": "PSG",
        "Senegal": "Sénégal",
        "Bosnia-Herzegovina": "Bosnie-Herzégovine",
        "South Africa": "Afrique du Sud",
    }
    return aliases.get(str(name), str(name))


def _fallback_team_asset(name: str) -> str:
    return _known_club_logo(name) or _known_country_flag(name)


def _known_country_flag(name: str) -> str:
    key = _normalize_team_label(name)
    slugs = {
        "afrique du sud": "rsa",
        "allemagne": "ger",
        "angleterre": "eng",
        "argentina": "arg",
        "argentine": "arg",
        "belgique": "bel",
        "brazil": "bra",
        "bresil": "bra",
        "bosnia herzegovina": "bih",
        "bosnie herzegovine": "bih",
        "cote d ivoire": "civ",
        "croatie": "cro",
        "espagne": "esp",
        "etats unis": "usa",
        "france": "fra",
        "georgie": "geo",
        "germany": "ger",
        "italie": "ita",
        "japon": "jpn",
        "maroc": "mar",
        "mexico": "mex",
        "mexique": "mex",
        "norvege": "nor",
        "pays bas": "ned",
        "pologne": "pol",
        "portugal": "por",
        "senegal": "sen",
        "south africa": "rsa",
        "uruguay": "uru",
    }
    slug = slugs.get(key)
    return f"https://a.espncdn.com/i/teamlogos/countries/500/{slug}.png" if slug else ""


def _season_tabs(kind: str, label: str, options: list[tuple[str, str]]) -> str:
    buttons = "".join(
        f'<button class="tab-button{" is-active" if index == 0 else ""}" type="button" data-season-value="{escape(value, quote=True)}">{escape(text)}</button>'
        for index, (value, text) in enumerate(options)
    )
    return f"""
    <nav class="season-tabs" data-season-tabs="{escape(kind, quote=True)}" aria-label="{escape(label, quote=True)}">
      <span class="season-tabs-label">{escape(label)}</span>
      {buttons}
    </nav>
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

    document.querySelectorAll('[data-season-tabs]').forEach((nav) => {
      const key = `akrodufoot:season:${nav.dataset.seasonTabs}`;
      const buttons = Array.from(nav.querySelectorAll('[data-season-value]'));
      const applySeason = (value) => {
        const selected = buttons.find((button) => button.dataset.seasonValue === value) || buttons[0];
        if (!selected) return;
        buttons.forEach((button) => button.classList.toggle('is-active', button === selected));
        localStorage.setItem(key, selected.dataset.seasonValue || '');
      };
      applySeason(localStorage.getItem(key));
      buttons.forEach((button) => {
        button.addEventListener('click', () => applySeason(button.dataset.seasonValue));
      });
    });
  </script>"""


def _france_next_match_badge(match: dict[str, Any] | None) -> str:
    if not match:
        return "France : prochain match à déterminer"
    date = _format_datetime(match.get("date", ""), with_time=True)
    opponent = match.get("opponent_display") or match.get("opponent") or "À déterminer"
    france_flag = _flag(match.get("france_flag_url", "") or _fallback_team_asset("France"))
    opponent_flag = _flag(match.get("opponent_flag_url", "") or _fallback_team_asset(opponent))
    if opponent == "À déterminer":
        return f"{france_flag}France vs À déterminer — {escape(date)}"
    return f"{france_flag}France vs {escape(opponent)} {opponent_flag}— {escape(date)}"


def _psg_next_match_badge(match: dict[str, Any] | None) -> str:
    if not match:
        return "PSG : prochain match à déterminer"
    date = _format_datetime(match.get("date", ""), with_time=True)
    team = match.get("team") or "PSG"
    opponent = match.get("opponent") or "À déterminer"
    team_logo = match.get("team_logo_url", "") or _fallback_team_asset(team)
    opponent_logo = match.get("opponent_logo_url", "") or _fallback_team_asset(opponent)
    return f'{_logo_or_placeholder(team_logo)}{escape(_psg_display_name(team))} vs {escape(opponent)} {_logo_or_placeholder(opponent_logo)}— {escape(date)}'


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


def _today_matches(
    matches: list[dict[str, Any]],
    group_matches: list[dict[str, Any]] | None = None,
    knockout: list[dict[str, Any]] | None = None,
) -> str:
    visible = _matches_for_display_day(matches, group_matches or [], knockout or [])
    if not visible:
        return '<article class="today-tile" style="grid-column:1/-1"><strong>Aucun match à venir disponible</strong><div class="subtle">Les cartes se rempliront automatiquement dès publication du calendrier.</div></article>'
    return "".join(f'<article class="today-tile">{_today_match(match)}</article>' for match in visible)


def _matches_for_display_day(
    today_matches: list[dict[str, Any]],
    group_matches: list[dict[str, Any]],
    knockout: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items = []
    for group in group_matches:
        items.extend(group.get("matches", []))
    for round_data in knockout:
        items.extend(round_data.get("matches", []))
    if not items:
        items = list(today_matches)

    today_key = datetime.now(PARIS).date().isoformat()
    same_day = [match for match in items if _match_day_key(match) == today_key]
    if same_day:
        return sorted(same_day, key=_match_sort_key)

    now = datetime.now(PARIS)
    upcoming = [match for match in items if not match.get("completed") and _match_sort_key(match) >= now]
    if not upcoming:
        return []
    next_day = _match_day_key(min(upcoming, key=_match_sort_key))
    return sorted([match for match in items if _match_day_key(match) == next_day], key=_match_sort_key)


def _match_sort_key(match: dict[str, Any]) -> datetime:
    return _parse_match_datetime(match.get("date", "")) or datetime.max.replace(tzinfo=PARIS)


def _match_day_key(match: dict[str, Any]) -> str:
    parsed = _parse_match_datetime(match.get("date", ""))
    return parsed.date().isoformat() if parsed else ""


def _parse_match_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARIS)
    return parsed.astimezone(PARIS)


def _today_match(match: dict[str, Any]) -> str:
    center = _score_text(match)
    if center == "vs":
        center = _format_time(match.get("date", "")) or "vs"
    date_label = _format_datetime(match.get("date", ""), with_time=False)
    time_label = _format_time(match.get("date", ""))
    meta = " · ".join(part for part in [date_label, time_label] if part)
    return (
        f'<div class="subtle today-meta">{escape(meta)}</div>'
        f'<div class="today-teams"><div class="today-team">{_team_button(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}</div>'
        f'<div class="today-score">{escape(center)}<br><span class="{_status_class(match)}">{escape(match.get("status", ""))}</span></div>'
        f'<div class="today-team">{_team_button(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""))}</div></div>'
        f'<div class="subtle" style="text-align:center;margin-top:12px">{escape(_venue_text(match))}</div>'
    )


def _mercato_ticker(mercato_data: dict[str, Any] | None) -> str:
    data = mercato_data or {}
    items = [item for item in data.get("items", []) if item.get("title") and item.get("url")]
    if not items:
        return """
    <section class="mercato-ticker" aria-label="Mercato live">
      <div class="mercato-badge">Mercato Live</div>
      <div class="mercato-empty">Mercato Live indisponible pour le moment</div>
    </section>
"""
    rendered = "".join(_mercato_item(item) for item in items[:18])
    return f"""
    <section class="mercato-ticker" aria-label="Mercato live">
      <div class="mercato-badge">Mercato Live</div>
      <div class="mercato-track">
        <div class="mercato-marquee">
          <div class="mercato-items">{rendered}</div>
          <div class="mercato-items" aria-hidden="true">{rendered}</div>
        </div>
      </div>
    </section>
"""


def _mercato_item(item: dict[str, Any]) -> str:
    title = escape(str(item.get("title") or "Info mercato"))
    url = escape(str(item.get("url") or "https://www.mercatolive.fr/"))
    published = escape(str(item.get("published_at") or ""))
    source = escape(str(item.get("source") or "Mercato Live"))
    entity = escape(str(item.get("club") or item.get("player") or ""))
    time_html = f'<span class="mercato-time">{published}</span>' if published else ""
    entity_html = f'<span class="mercato-entity">{entity}</span>' if entity else ""
    return (
        f'<a class="mercato-link" href="{url}" target="_blank" rel="noreferrer">'
        f'{time_html}<span>{title}</span>{entity_html}<span class="mercato-source">{source}</span></a>'
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
          <h3 id="predictions">Pronostics du jour</h3>
          <form class="community-form" id="predictionForm">
            <div class="pseudo-row">
              <label for="predictionPseudo">Pseudo</label>
              <input id="predictionPseudo" type="text" maxlength="32" placeholder="Votre pseudo" autocomplete="nickname">
            </div>
            <div class="field-row">
              <select id="competitionFilter">
                <option value="today" selected>Matchs du jour</option>
                <option value="all">Tous les matchs</option>
                <option value="Coupe du Monde">Coupe du Monde</option>
                <option value="Ligue des Champions">Ligue des Champions</option>
                <option value="Ligue 1">Ligue 1</option>
                <option value="Liga">Liga</option>
                <option value="Bundesliga">Bundesliga</option>
                <option value="Premier League">Premier League</option>
                <option value="Serie A">Serie A</option>
              </select>
              <select id="predictionMatch"></select>
            </div>
            <div class="prediction-scoreboard" id="predictionTeams">
              <div class="prediction-team home"><span class="prediction-team-name" id="predictionHomeName">Équipe A</span><span id="predictionHomeFlag" class="flag placeholder" aria-hidden="true"></span></div>
              <input id="homePrediction" type="number" min="0" max="99" value="0" aria-label="Score équipe A">
              <div class="prediction-separator">-</div>
              <input id="awayPrediction" type="number" min="0" max="99" value="0" aria-label="Score équipe B">
              <div class="prediction-team away"><span id="predictionAwayFlag" class="flag placeholder" aria-hidden="true"></span><span class="prediction-team-name" id="predictionAwayName">Équipe B</span></div>
            </div>
            <div class="match-context" id="predictionContext"></div>
            <div class="coach-prediction" id="coachPrediction" aria-live="polite">
              <div class="coach-prediction-top"><span class="coach-badge">Coach</span><span>Analyse fictive pour le jeu entre amis.</span></div>
              <div class="coach-reason">Coach prépare son analyse dès que le match est sélectionné.</div>
              <div class="coach-disclaimer">Aucun conseil de pari réel.</div>
            </div>
            <button class="action-button" type="submit" disabled>Valider le pronostic</button>
          </form>
          <div class="community-status" id="predictionStatus"></div>
        </div>
        <div class="community-side">
          <h3>Classement</h3>
          <div class="leaderboard-list" id="leaderboardList"></div>
        </div>
      </article>
    </section>
"""


def _player_cards(players: list[dict[str, Any]], label: str, prefer_country_flag: bool = False) -> str:
    if not players:
        return _empty_block("Aucune donnée publiée pour le moment.")
    return "".join(_player_card(player, label, prefer_country_flag, index) for index, player in enumerate(players[:5]))


def _player_card(player: dict[str, Any], label: str, prefer_country_flag: bool = False, index: int = 0) -> str:
    country_flag = player.get("country_flag_url", "")
    avatar = f'<img class="avatar" src="{escape(country_flag)}" alt="">' if country_flag else '<div class="avatar placeholder" aria-hidden="true"></div>'
    team_name = str(player.get("team", ""))
    club_logo = _player_team_logo(player)
    club_logo_html = f'<img class="club-logo" src="{escape(club_logo)}" alt="">' if club_logo else '<span class="club-logo placeholder" aria-hidden="true"></span>'
    all_time = player.get("all_time_rank", "")
    all_time_html = f'<div class="rank-note">({escape(str(all_time))})</div>' if all_time else ""
    return (
        f'<article class="card player-card rank-{index + 1}">'
        f'<div class="avatar-wrap">{avatar}</div><div><div class="team">{escape(str(player.get("name", "")))}</div>'
        f'<div class="subtle club-line">{club_logo_html}<span class="club-name">{escape(team_name)}</span></div>'
        f'<div class="player-stat">{escape(str(player.get("value", "0")))} <span class="subtle">{escape(label)}</span></div>{all_time_html}</div>'
        "</article>"
    )


def _player_team_logo(player: dict[str, Any]) -> str:
    direct = player.get("team_logo_url") or player.get("club_logo_url") or player.get("flag_url")
    if direct:
        return str(direct)
    team_id = str(player.get("team_id") or "").strip()
    if team_id:
        return f"https://images.fotmob.com/image_resources/logo/teamlogo/{escape(team_id)}.png"
    return _known_club_logo(str(player.get("team", "")))


def _known_club_logo(team: str) -> str:
    key = _normalize_team_label(team)
    logos = {
        "ac milan": "https://a.espncdn.com/i/teamlogos/soccer/500/103.png",
        "ajax": "https://a.espncdn.com/i/teamlogos/soccer/500/139.png",
        "aj auxerre": "https://a.espncdn.com/i/teamlogos/soccer/500/172.png",
        "arsenal": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png",
        "as monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
        "atletico madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
        "atlético madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/1068.png",
        "auxerre": "https://a.espncdn.com/i/teamlogos/soccer/500/172.png",
        "barcelona": "https://a.espncdn.com/i/teamlogos/soccer/500/83.png",
        "bayer leverkusen": "https://a.espncdn.com/i/teamlogos/soccer/500/131.png",
        "bayern munich": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
        "bayern munchen": "https://a.espncdn.com/i/teamlogos/soccer/500/132.png",
        "borussia dortmund": "https://a.espncdn.com/i/teamlogos/soccer/500/124.png",
        "chelsea": "https://a.espncdn.com/i/teamlogos/soccer/500/363.png",
        "internazionale": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
        "inter milan": "https://a.espncdn.com/i/teamlogos/soccer/500/110.png",
        "juventus": "https://a.espncdn.com/i/teamlogos/soccer/500/111.png",
        "lille": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
        "losc": "https://a.espncdn.com/i/teamlogos/soccer/500/166.png",
        "lyon": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
        "manchester city": "https://a.espncdn.com/i/teamlogos/soccer/500/382.png",
        "manchester united": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
        "marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/176.png",
        "monaco": "https://a.espncdn.com/i/teamlogos/soccer/500/174.png",
        "napoli": "https://a.espncdn.com/i/teamlogos/soccer/500/114.png",
        "newcastle united": "https://a.espncdn.com/i/teamlogos/soccer/500/361.png",
        "nice": "https://a.espncdn.com/i/teamlogos/soccer/500/2502.png",
        "ogc nice": "https://a.espncdn.com/i/teamlogos/soccer/500/2502.png",
        "olympique lyonnais": "https://a.espncdn.com/i/teamlogos/soccer/500/167.png",
        "olympique de marseille": "https://a.espncdn.com/i/teamlogos/soccer/500/176.png",
        "paris saint germain": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
        "psg": "https://a.espncdn.com/i/teamlogos/soccer/500/160.png",
        "rc lens": "https://a.espncdn.com/i/teamlogos/soccer/500/175.png",
        "real madrid": "https://a.espncdn.com/i/teamlogos/soccer/500/86.png",
        "villarreal": "https://a.espncdn.com/i/teamlogos/soccer/500/102.png",
        "lens": "https://a.espncdn.com/i/teamlogos/soccer/500/175.png",
    }
    return logos.get(key, "")


def _normalize_team_label(value: str) -> str:
    replacements = str.maketrans({"é": "e", "è": "e", "ê": "e", "ë": "e", "á": "a", "à": "a", "ä": "a", "ã": "a", "í": "i", "ï": "i", "ó": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c"})
    clean = str(value or "").casefold().translate(replacements)
    return " ".join(clean.replace("-", " ").split())


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
  <div class="table-scroll"><table>
    <thead><tr><th>#</th><th>Équipe</th><th>J</th><th>G</th><th>N</th><th>P</th><th>DIFF.</th><th>PTS</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
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
        '<div class="calendar-match league-calendar-match">'
        f'<div class="date">{escape(_format_datetime(match.get("date", ""), with_time=False))}<br>{escape(_format_time(match.get("date", "")))}</div>'
        f'<div>{_team_button(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}</div>'
        f'<div class="score">{escape(_calendar_score_text(match))}</div>'
        f'<div class="away">{_team_button(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""), reverse=True)}</div>'
        f'<div class="match-meta"><div class="match-group">{escape(match.get("group", ""))}</div><div class="subtle">{escape(_venue_text(match))}</div><span class="{_status_class(match)}">{escape(match.get("status", ""))}</span></div>'
        "</div>"
    )


def _dynamic_news_section(title: str, note: str, board_id: str) -> str:
    board_key = board_id.casefold()
    kind = "worldcup" if "worldcup" in board_key else "leagues" if "league" in board_key else "champions"
    action = f'<button class="alltime-badge" type="button" data-news-refresh="{escape(kind, quote=True)}">Actualiser</button>'
    return f'{_section_head(title, note, action)}<section class="news" id="{escape(board_id, quote=True)}">{_empty_block("Aucune actualité disponible pour le moment.")}</section>'


def _news_section(title: str, news: list[dict[str, Any]], note: str, france: bool) -> str:
    if not news:
        return f'{_section_head(title, note)}<section class="news">{_empty_block("Aucune actualité disponible pour le moment.")}</section>'
    articles = []
    france_class = " france" if france else ""
    for article in news[:6]:
        articles.append(_article_card_html(article, france_class))
    return f'{_section_head(title, note)}<section class="news">{"".join(articles)}</section>'


def _article_card_html(article: dict[str, Any], extra_class: str = "") -> str:
    source = str(article.get("source_name") or article.get("source") or "Source")
    logo = str(article.get("source_logo") or "")
    image = str(article.get("image_url") or "")
    date_value = str(article.get("published_at") or article.get("date") or "")
    url = str(article.get("url") or "#")
    image_html = f'<img class="article-image" src="{escape(image, quote=True)}" alt="" loading="lazy" onerror="this.classList.add(\'is-hidden\')">' if image else '<div class="article-visual-fallback">Akro du Foot</div>'
    logo_html = f'<img class="source-logo" src="{escape(logo, quote=True)}" alt="" loading="lazy" onerror="this.classList.add(\'is-hidden\')">' if logo else ''
    return (
        f'<article class="card article{extra_class}">'
        f'<div class="article-visual">{image_html}<div class="article-source">{logo_html}<span>{escape(source)}</span></div></div>'
        '<div class="article-body">'
        f'<div class="article-meta">{escape(_format_datetime(date_value, with_time=False))}</div>'
        f'<h3><a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{escape(str(article.get("title", "Article")))}</a></h3>'
        f'<p>{escape(str(article.get("summary", "")))}</p>'
        f'<a class="read-link" href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">Lire l’article</a>'
        '</div></article>'
    )


def render_worldcup_bracket(rounds: list[dict[str, Any]]) -> str:
    by_name = {round_data.get("name", ""): round_data for round_data in rounds}
    round_32 = _dedupe_matches(by_name.get("16es de finale", {}).get("matches", []))
    round_16 = _dedupe_matches(by_name.get("8es de finale", {}).get("matches", []))
    quarter = _dedupe_matches(by_name.get("Quarts de finale", {}).get("matches", []))
    semi = _dedupe_matches(by_name.get("Demi-finales", {}).get("matches", []))
    third = _dedupe_matches(by_name.get("Match pour la 3e place", {}).get("matches", []))
    final = _dedupe_matches(by_name.get("Finale", {}).get("matches", []))

    left32, right32 = _split_bracket_side(round_32)
    left16, right16 = _split_bracket_side(round_16)
    leftq, rightq = _split_bracket_side(quarter)
    lefts, rights = _split_bracket_side(semi)
    left = [
        {"name": "16es", "matches": left32},
        {"name": "8es", "matches": left16},
        {"name": "Quarts", "matches": leftq},
        {"name": "Demies", "matches": lefts},
    ]
    right = [
        {"name": "Demies", "matches": rights},
        {"name": "Quarts", "matches": rightq},
        {"name": "8es", "matches": right16},
        {"name": "16es", "matches": right32},
    ]
    return _bracket_shell(left, right, final, "Coupe du Monde FIFA 2026", third, logo_url="worldcup")


def render_champions_league_bracket(rounds: list[dict[str, Any]]) -> str:
    by_name = {round_data.get("name", ""): round_data for round_data in rounds}
    playoffs = _aggregate_two_legged_ties(by_name.get("Barrages", {}).get("matches", []))
    round_16 = _aggregate_two_legged_ties(by_name.get("8es de finale", {}).get("matches", []))
    quarter = _aggregate_two_legged_ties(by_name.get("Quarts de finale", {}).get("matches", []))
    semi = _aggregate_two_legged_ties(by_name.get("Demi-finales", {}).get("matches", []))
    final = _dedupe_matches(by_name.get("Finale", {}).get("matches", []))

    lefts, rights = _split_bracket_side(semi)
    leftq, rightq = _partition_by_path(quarter, _teams_in_matches(lefts), _teams_in_matches(rights))
    left16, right16 = _partition_by_path(round_16, _teams_in_matches(leftq), _teams_in_matches(rightq))
    leftp, rightp = _partition_by_path(playoffs, _teams_in_matches(left16), _teams_in_matches(right16))
    left = [
        {"name": "Barrages", "matches": leftp},
        {"name": "8es", "matches": left16},
        {"name": "Quarts", "matches": leftq},
        {"name": "Demies", "matches": lefts},
    ]
    right = [
        {"name": "Demies", "matches": rights},
        {"name": "Quarts", "matches": rightq},
        {"name": "8es", "matches": right16},
        {"name": "Barrages", "matches": rightp},
    ]
    return _bracket_shell(left, right, final, "Ligue des Champions", stage_class=" ucl-official", wing_class=" ucl-wing", logo_url="champions")


def _bracket_shell(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    final_matches: list[dict[str, Any]],
    trophy_title: str,
    third_matches: list[dict[str, Any]] | None = None,
    stage_class: str = "",
    wing_class: str = "",
    logo_url: str = "",
) -> str:
    final_match = (final_matches or [{}])[0]
    third_html = ""
    if third_matches is not None:
        third_match = (third_matches or [{}])[0]
        third_html = '<div class="round-title">3e place</div>' + _ko_match(third_match, extra_class="third-place-card")
    trophy_visual = _competition_trophy_svg(logo_url, "bracket") if logo_url in {"worldcup", "champions"} else '<div class="trophy"></div>'
    center = (
        '<div class="bracket-center">'
        f'<div class="trophy-card">{trophy_visual}<div class="trophy-title">{escape(trophy_title)}</div></div>'
        '<div class="round-title">Finale</div>'
        f'{_ko_match(final_match, extra_class="final-card")}'
        f'{third_html}'
        "</div>"
    )
    return (
        f'<section class="bracket-wrap"><div class="bracket-stage{stage_class}">'
        f'<div class="bracket-wing{wing_class} left">{"".join(_bracket_round(round_data) for round_data in left)}</div>'
        f"{center}"
        f'<div class="bracket-wing{wing_class} right">{"".join(_bracket_round(round_data) for round_data in right)}</div>'
        "</div></section>"
    )


def _split_bracket_side(matches: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clean = sorted(_dedupe_matches(matches), key=_match_sort_key)
    midpoint = (len(clean) + 1) // 2
    return clean[:midpoint], clean[midpoint:]


def _teams_in_matches(matches: list[dict[str, Any]]) -> set[str]:
    teams = set()
    for match in matches:
        for key in ("home_team", "away_team", "winner_team"):
            team = str(match.get(key) or "").casefold()
            if team and team != "à déterminer":
                teams.add(team)
    return teams


def _partition_by_path(
    matches: list[dict[str, Any]],
    left_targets: set[str],
    right_targets: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for match in sorted(_dedupe_matches(matches), key=_match_sort_key):
        teams = _teams_in_matches([match])
        if teams & left_targets and not teams & right_targets:
            left.append(match)
        elif teams & right_targets and not teams & left_targets:
            right.append(match)
        else:
            unresolved.append(match)
    for match in unresolved:
        if len(left) <= len(right):
            left.append(match)
        else:
            right.append(match)
    return left, right


def _dedupe_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    clean = []
    for match in sorted(matches, key=_match_sort_key):
        key = str(match.get("id") or "") or "|".join(
            str(match.get(part, "")) for part in ("home_team", "away_team", "date")
        )
        if key in seen:
            continue
        seen.add(key)
        clean.append(match)
    return clean


def _aggregate_two_legged_ties(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for match in _dedupe_matches(matches):
        home = str(match.get("home_team") or "À déterminer")
        away = str(match.get("away_team") or "À déterminer")
        key = tuple(sorted((home.casefold(), away.casefold())))
        grouped.setdefault(key, []).append(match)

    ties = []
    for legs in grouped.values():
        legs = sorted(legs, key=_match_sort_key)
        first = legs[0]
        home = str(first.get("home_team") or "À déterminer")
        away = str(first.get("away_team") or "À déterminer")
        flags = {
            str(leg.get("home_team") or ""): leg.get("home_flag_url", "") for leg in legs
        } | {
            str(leg.get("away_team") or ""): leg.get("away_flag_url", "") for leg in legs
        }
        scores: dict[str, int] = {home: 0, away: 0}
        has_all_scores = True
        for leg in legs:
            h_team = str(leg.get("home_team") or "")
            a_team = str(leg.get("away_team") or "")
            h_score = _score_number(leg.get("home_score"))
            a_score = _score_number(leg.get("away_score"))
            if h_score is None or a_score is None:
                has_all_scores = False
                continue
            scores[h_team] = scores.get(h_team, 0) + h_score
            scores[a_team] = scores.get(a_team, 0) + a_score
        if len(legs) == 1:
            ties.append(first)
            continue
        winner_team = ""
        if has_all_scores and scores.get(home, 0) != scores.get(away, 0):
            winner_team = home if scores.get(home, 0) > scores.get(away, 0) else away
        statuses = [str(leg.get("status") or "") for leg in legs]
        status = "LIVE" if any(status == "LIVE" for status in statuses) else "Terminé" if all(leg.get("completed") or status == "Terminé" for leg, status in zip(legs, statuses)) else "À venir"
        date_label = f"{_format_datetime(legs[0].get('date', ''), with_time=False)} - {_format_datetime(legs[-1].get('date', ''), with_time=False)}"
        ties.append({
            **legs[-1],
            "id": "tie:" + ":".join(sorted(str(leg.get("id") or "") for leg in legs)),
            "home_team": home,
            "away_team": away,
            "home_flag_url": flags.get(home, ""),
            "away_flag_url": flags.get(away, ""),
            "home_score": scores.get(home, "") if has_all_scores else "",
            "away_score": scores.get(away, "") if has_all_scores else "",
            "status": status,
            "completed": status == "Terminé",
            "date_label": date_label,
            "tie_note": "Score cumulé" if has_all_scores else "Confrontation aller-retour",
            "winner_team": winner_team,
        })
    return sorted(ties, key=_match_sort_key)


def _score_number(value: Any) -> int | None:
    try:
        if value == "" or value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _bracket_round(round_data: dict[str, Any]) -> str:
    matches = "".join(_ko_match(match) for match in round_data.get("matches", []))
    if not matches:
        matches = _empty_block("À déterminer.")
    return f'<article class="round"><div class="round-title">{escape(round_data.get("name", ""))}</div>{matches}</article>'


def _ko_match(match: dict[str, Any], extra_class: str = "") -> str:
    class_name = f"ko-match {extra_class}".strip()
    home_score = _display_score(match.get("home_score", ""))
    away_score = _display_score(match.get("away_score", ""))
    date_label = match.get("date_label") or _format_datetime(match.get("date", ""), with_time=True)
    tie_note = match.get("tie_note", "")
    note = f'<div class="subtle">{escape(str(tie_note))}</div>' if tie_note else ""
    return (
        f'<div class="{escape(class_name)}">'
        f'<div class="ko-line">{_bracket_team(match.get("home_team", "À déterminer"), match.get("home_flag_url", ""))}<span class="ko-score">{home_score}</span></div>'
        f'<div class="ko-line">{_bracket_team(match.get("away_team", "À déterminer"), match.get("away_flag_url", ""))}<span class="ko-score">{away_score}</span></div>'
        f'<div class="subtle">{escape(str(date_label))}</div>'
        f'{note}'
        f'<span class="{_status_class(match)}">{escape(match.get("status", ""))}</span>'
        "</div>"
    )


def _bracket_team(name: str, flag_url: str = "") -> str:
    label = str(name or "À déterminer")
    icon = _flag(flag_url or _fallback_team_asset(label))
    if label == "À déterminer":
        return f'<span class="bracket-team">{icon}<span class="bracket-team-name">{escape(label)}</span></span>'
    return f'<button class="bracket-team" type="button" data-team="{escape(label, quote=True)}">{icon}<span class="bracket-team-name">{escape(label)}</span></button>'


def _team_button(name: str, flag_url: str = "", reverse: bool = False) -> str:
    label = str(name or "À déterminer")
    icon = _flag(flag_url or _fallback_team_asset(label))
    if label == "À déterminer":
        content = f"{escape(label)}{icon}" if reverse else f"{icon}{escape(label)}"
        return f'<span class="team">{content}</span>'
    content = f"{escape(label)}{icon}" if reverse else f"{icon}{escape(label)}"
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
        <div class="team-info">
          <div class="team-info-label">Forme récente</div>
          <div class="team-info-value">10 derniers résultats disponibles dans Akro du Foot</div>
        </div>
        <div id="teamCoach"></div>
        <div id="teamHonors"></div>
        <div id="teamRecent"></div>
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


def _football_chatbot_modal() -> str:
    return """
  <div class="team-modal" id="footballChatbotModal" aria-hidden="true">
    <article class="team-dialog chatbot-dialog" role="dialog" aria-modal="true" aria-labelledby="footballChatbotTitle">
      <header class="team-modal-head">
        <div class="alltime-rank">⚽</div>
        <div>
          <div class="team-modal-title" id="footballChatbotTitle">Coach</div>
          <div class="subtle">Assistant football spécialisé, analyste et coach.</div>
        </div>
        <button class="modal-close" type="button" id="footballChatbotClose" aria-label="Fermer">×</button>
      </header>
      <div class="chatbot-messages" id="footballChatbotMessages">
        <div class="chatbot-message bot">Salut, je suis Coach. Pose-moi une question foot.</div>
      </div>
      <form class="chatbot-form" id="footballChatbotForm">
        <input id="footballChatbotInput" type="text" maxlength="500" placeholder="Pose ta question foot…" autocomplete="off">
        <button class="action-button" type="submit">Envoyer</button>
      </form>
    </article>
  </div>
"""


def _leagues_news_payload(leagues_data: dict[str, Any] | None) -> dict[str, Any]:
    data = leagues_data or {}
    by_league: dict[str, dict[str, Any]] = {}
    for key, league in (data.get("leagues") or {}).items():
        league_name = league.get("name", key)
        all_news = _dedupe_render_news([*(league.get("all_news") or []), *(data.get("all_news") or [])])
        general = [article for article in all_news if _focus_text_match(article, str(league_name))]
        by_league[key] = {
            "general": _dedupe_render_news(general or all_news),
            "focused": league.get("focused_club_news", {}),
            "all": all_news,
        }
    return {
        "general": _dedupe_render_news(data.get("all_news", [])),
        "focused": {},
        "all": _dedupe_render_news(data.get("all_news", [])),
        "byLeague": by_league,
    }


def _focus_text_match(article: dict[str, Any], focus: str) -> bool:
    normalized_focus = _normalize_render_text(focus)
    haystack = _normalize_render_text(f"{article.get('title', '')} {article.get('summary', '')} {article.get('url', '')}")
    return bool(normalized_focus and normalized_focus in haystack)


def _normalize_render_text(value: str) -> str:
    replacements = str.maketrans({"é":"e", "è":"e", "ê":"e", "ë":"e", "à":"a", "â":"a", "ä":"a", "î":"i", "ï":"i", "ô":"o", "ö":"o", "ù":"u", "û":"u", "ü":"u", "ç":"c"})
    import re
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold().translate(replacements)).split())


def _news_script(worldcup_data: dict[str, Any], champions_data: dict[str, Any] | None, leagues_data: dict[str, Any] | None = None) -> str:
    payload = {
        "worldcup": {
            "general": _dedupe_render_news([*(worldcup_data.get("general_news") or worldcup_data.get("world_cup_news", [])), *worldcup_data.get("world_cup_news", [])]),
            "focused": worldcup_data.get("focused_team_news", {}),
            "all": _dedupe_render_news([*worldcup_data.get("all_news", []), *worldcup_data.get("france_news", []), *worldcup_data.get("world_cup_news", [])]),
        },
        "champions": {
            "general": _dedupe_render_news([*((champions_data or {}).get("general_news") or (champions_data or {}).get("world_cup_news", [])), *((champions_data or {}).get("world_cup_news", []))]),
            "focused": (champions_data or {}).get("focused_club_news", {}),
            "all": _dedupe_render_news([*(champions_data or {}).get("all_news", []), *((champions_data or {}).get("world_cup_news", []))]),
        },
        "leagues": _leagues_news_payload(leagues_data),
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const NEWS_DATA = {data};

    function newsEscape(value) {{
      return String(value || '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
    }}

    function newsDate(value) {{
      if (!value) return 'Date non disponible';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('fr-FR', {{day:'2-digit', month:'2-digit', year:'numeric'}});
    }}

    function normalizeNewsText(value) {{
      return String(value || '').toLocaleLowerCase('fr-FR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
    }}

    function focusAliases(name) {{
      const normalized = normalizeNewsText(name);
      const map = {{
        'paris saint germain': ['psg', 'paris sg', 'paris saint germain'],
        'manchester city': ['man city', 'manchester city', 'city'],
        'marseille': ['om', 'olympique de marseille', 'marseille'],
        'france': ['france', 'equipe de france', 'bleus', 'deschamps'],
        'angleterre': ['angleterre', 'england', 'three lions'],
        'senegal': ['senegal', 'sénégal', 'lions de la teranga'],
        'brazil': ['brazil', 'bresil', 'brésil', 'selecao', 'seleçao'],
        'argentina': ['argentina', 'argentine', 'albiceleste'],
        'real madrid': ['real madrid'],
        'arsenal': ['arsenal', 'gunners'],
        'barcelona': ['barcelona', 'barcelone', 'barca', 'barça'],
        'bayern munich': ['bayern', 'bayern munich']
      }};
      return [normalized, ...(map[normalized] || [])].map(normalizeNewsText).filter(Boolean);
    }}

    function articleMatchesFocus(article, focus) {{
      const haystack = normalizeNewsText(`${{article.title || ''}} ${{article.summary || ''}} ${{article.url || ''}}`);
      return focusAliases(focus).some(alias => alias && haystack.includes(alias));
    }}

    function uniqueArticles(articles) {{
      const seen = new Set();
      return (articles || []).filter(article => {{
        const key = normalizeNewsText(article.title || article.url || '').slice(0, 90);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      }}).sort((a, b) => String(b.published_at || b.date || '').localeCompare(String(a.published_at || a.date || '')));
    }}

    function sourceKey(article) {{
      return normalizeNewsText(article.source_name || article.source || 'source');
    }}

    function balancedArticles(articles, limit) {{
      const sorted = uniqueArticles(articles);
      const selected = [];
      const counts = new Map();
      for (const article of sorted) {{
        const key = sourceKey(article);
        if ((counts.get(key) || 0) >= 2) continue;
        selected.push(article);
        counts.set(key, (counts.get(key) || 0) + 1);
        if (selected.length >= limit) return selected;
      }}
      for (const article of sorted) {{
        if (!selected.includes(article)) selected.push(article);
        if (selected.length >= limit) break;
      }}
      return selected;
    }}

    function articleCard(article) {{
      const source = newsEscape(article.source_name || article.source || 'Source');
      const logo = article.source_logo ? `<img class="source-logo" src="${{newsEscape(article.source_logo)}}" alt="" loading="lazy" onerror="this.classList.add('is-hidden')">` : '';
      const image = article.image_url ? `<img class="article-image" src="${{newsEscape(article.image_url)}}" alt="" loading="lazy" onerror="this.classList.add('is-hidden')">` : '<div class="article-visual-fallback">Akro du Foot</div>';
      return `<article class="card article">
        <div class="article-visual">${{image}}<div class="article-source">${{logo}}<span>${{source}}</span></div></div>
        <div class="article-body">
          <div class="article-meta">${{newsEscape(newsDate(article.published_at || article.date))}}</div>
          <h3><a href="${{newsEscape(article.url || '#')}}" target="_blank" rel="noreferrer">${{newsEscape(article.title || 'Article')}}</a></h3>
          <p>${{newsEscape(article.summary || '')}}</p>
          <a class="read-link" href="${{newsEscape(article.url || '#')}}" target="_blank" rel="noreferrer">Lire l’article</a>
        </div>
      </article>`;
    }}

    function selectedLeagueKey() {{
      const select = document.getElementById('leagueSelect');
      return select ? select.value : 'ligue1';
    }}

    function newsSelection(kind) {{
      const select = document.getElementById(kind === 'worldcup' ? 'worldcupFocusSelect' : kind === 'leagues' ? 'leagueClubSelect' : 'championsFocusSelect');
      const focus = select ? select.value : '';
      const base = NEWS_DATA[kind] || {{general: [], focused: {{}}, all: []}};
      const source = kind === 'leagues' && base.byLeague ? (base.byLeague[selectedLeagueKey()] || base) : base;
      const focusedDirect = source.focused && source.focused[focus] ? source.focused[focus] : [];
      const focusedFromPool = (source.all || []).filter(article => focus && articleMatchesFocus(article, focus));
      const focused = balancedArticles([...focusedDirect, ...focusedFromPool], 3);
      const focusedKeys = new Set(focused.map(article => normalizeNewsText(article.title || article.url || '').slice(0, 90)));
      const general = balancedArticles(source.general || source.all || [], 6).filter(article => !focusedKeys.has(normalizeNewsText(article.title || article.url || '').slice(0, 90))).slice(0, 3);
      return [...focused, ...general].slice(0, 6);
    }}

    function renderNewsBoard(kind) {{
      const board = document.getElementById(kind === 'worldcup' ? 'worldcupNewsBoard' : kind === 'leagues' ? 'leaguesNewsBoard' : 'championsNewsBoard');
      if (!board) return;
      const articles = newsSelection(kind);
      board.innerHTML = articles.length
        ? articles.map(articleCard).join('')
        : '<div class="empty">Aucune actualité française disponible pour le moment.</div>';
    }}

    async function refreshNews(kind) {{
      const board = document.getElementById(kind === 'worldcup' ? 'worldcupNewsBoard' : kind === 'leagues' ? 'leaguesNewsBoard' : 'championsNewsBoard');
      const select = document.getElementById(kind === 'worldcup' ? 'worldcupFocusSelect' : kind === 'leagues' ? 'leagueClubSelect' : 'championsFocusSelect');
      if (board) board.innerHTML = '<div class="empty">Actualisation des actualités...</div>';
      try {{
        const params = new URLSearchParams({{competition: kind, focus: select ? select.value : ''}});
        const response = await fetch(`/api/refresh-news?${{params.toString()}}`);
        if (!response.ok) throw new Error('refresh failed');
        const data = await response.json();
        NEWS_DATA[kind] = {{...(NEWS_DATA[kind] || {{}}), ...data}};
      }} catch (error) {{
        // En mode fichier statique ou hors ligne, on réaffiche les données déjà en cache.
      }}
      renderNewsBoard(kind);
    }}

    function refreshAllNewsBoards() {{
      renderNewsBoard('worldcup');
      renderNewsBoard('champions');
      renderNewsBoard('leagues');
    }}

    document.addEventListener('click', event => {{
      const trigger = event.target.closest('[data-news-refresh]');
      if (trigger) refreshNews(trigger.dataset.newsRefresh);
    }});
    document.addEventListener('akro:focus-change', refreshAllNewsBoards);
    window.addEventListener('DOMContentLoaded', refreshAllNewsBoards);
    refreshAllNewsBoards();
  </script>"""


def _dedupe_render_news(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for article in articles:
        key = str(article.get("title") or article.get("url") or "").casefold()[:90]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(article)
    return sorted(out, key=lambda item: item.get("date", ""), reverse=True)[:24]


def _focus_script(matches: list[dict[str, Any]], teams_details: dict[str, Any]) -> str:
    matches_payload = json.dumps(matches, ensure_ascii=False).replace("</", "<\\/")
    teams_payload = json.dumps(
        {name: {"flag_url": details.get("flag_url", ""), "name": details.get("name", name)} for name, details in teams_details.items()},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return f"""<script>
    const FOCUS_MATCHES = {matches_payload};
    const FOCUS_TEAMS = {teams_payload};
    const FOCUS_KEYS = {{
      worldcup: 'akrodufoot:focus:worldcup',
      champions: 'akrodufoot:focus:champions'
    }};
    const FOCUS_DEFAULTS = {{worldcup: 'France', champions: 'Paris Saint-Germain'}};

    function focusEscape(value) {{
      return String(value || '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
    }}

    function focusDisplayName(name) {{
      const aliases = {{
        'Paris Saint-Germain': 'PSG',
        'Paris SG': 'PSG',
        'England': 'Angleterre',
        'Senegal': 'Sénégal',
        'Bosnia-Herzegovina': 'Bosnie-Herzégovine',
        'South Africa': 'Afrique du Sud'
      }};
      return aliases[name] || (FOCUS_TEAMS[name] && FOCUS_TEAMS[name].name) || name || 'À déterminer';
    }}

    function focusFlag(url) {{
      return url ? `<img class="flag" src="${{focusEscape(url)}}" alt="">` : '<span class="flag placeholder" aria-hidden="true"></span>';
    }}

    function focusNormalize(name) {{
      return String(name || '').toLocaleLowerCase('fr-FR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/-/g, ' ').replace(/\s+/g, ' ').trim();
    }}

    function focusFallbackIcon(team) {{
      const key = focusNormalize(team);
      const clubs = {{
        'arsenal': 'https://a.espncdn.com/i/teamlogos/soccer/500/359.png',
        'barcelona': 'https://a.espncdn.com/i/teamlogos/soccer/500/83.png',
        'bayern munich': 'https://a.espncdn.com/i/teamlogos/soccer/500/132.png',
        'chelsea': 'https://a.espncdn.com/i/teamlogos/soccer/500/363.png',
        'liverpool': 'https://a.espncdn.com/i/teamlogos/soccer/500/364.png',
        'manchester city': 'https://a.espncdn.com/i/teamlogos/soccer/500/382.png',
        'paris saint germain': 'https://a.espncdn.com/i/teamlogos/soccer/500/160.png',
        'psg': 'https://a.espncdn.com/i/teamlogos/soccer/500/160.png',
        'real madrid': 'https://a.espncdn.com/i/teamlogos/soccer/500/86.png'
      }};
      const countries = {{
        'afrique du sud': 'rsa', 'allemagne': 'ger', 'angleterre': 'eng', 'argentine': 'arg',
        'bresil': 'bra', 'bosnie herzegovine': 'bih', 'espagne': 'esp', 'france': 'fra',
        'italie': 'ita', 'maroc': 'mar', 'mexique': 'mex', 'senegal': 'sen', 'uruguay': 'uru'
      }};
      return clubs[key] || (countries[key] ? `https://a.espncdn.com/i/teamlogos/countries/500/${{countries[key]}}.png` : '');
    }}

    function focusTeamIcon(team) {{
      const details = FOCUS_TEAMS[team] || {{}};
      if (details.flag_url) return details.flag_url;
      const match = FOCUS_MATCHES.find(item => item.home_team === team || item.away_team === team);
      if (match) return match.home_team === team ? match.home_flag_url : match.away_flag_url;
      return focusFallbackIcon(team);
    }}

    function focusTimestamp(match) {{
      const date = new Date(match.date);
      return Number.isNaN(date.getTime()) ? Number.MAX_SAFE_INTEGER : date.getTime();
    }}

    function focusDate(value) {{
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? 'date à déterminer' : date.toLocaleString('fr-FR', {{day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}}).replace(',', '');
    }}

    function focusNextMatch(competition, team) {{
      const now = Date.now();
      const candidates = FOCUS_MATCHES
        .filter(match => match.competition === competition)
        .filter(match => [match.home_team, match.away_team].includes(team))
        .filter(match => !match.completed && focusTimestamp(match) >= now)
        .sort((a, b) => focusTimestamp(a) - focusTimestamp(b));
      return candidates[0] || null;
    }}

    function updateFocusPillIcon(kind, team) {{
      const icon = document.getElementById(`${{kind}}FocusIcon`);
      if (!icon) return;
      icon.innerHTML = focusFlag(focusTeamIcon(team));
    }}

    function renderFocus(kind) {{
      const competition = kind === 'worldcup' ? 'Coupe du Monde' : 'Ligue des Champions';
      const select = document.getElementById(`${{kind}}FocusSelect`);
      const target = document.getElementById(`${{kind}}FocusNext`);
      if (!select || !target) return;
      const saved = localStorage.getItem(FOCUS_KEYS[kind]);
      if (saved && Array.from(select.options).some(option => option.value === saved)) select.value = saved;
      const team = select.value || FOCUS_DEFAULTS[kind];
      updateFocusPillIcon(kind, team);
      const match = focusNextMatch(competition, team);
      if (!match) {{
        target.innerHTML = `${{focusFlag(focusTeamIcon(team))}}<span class="focus-match-text">${{focusEscape(focusDisplayName(team))}} : prochain match à déterminer</span>`;
        return;
      }}
      const isHome = match.home_team === team;
      const opponent = isHome ? match.away_team : match.home_team;
      const teamFlag = isHome ? match.home_flag_url : match.away_flag_url;
      const opponentFlag = isHome ? match.away_flag_url : match.home_flag_url;
      target.innerHTML = `${{focusFlag(teamFlag || focusTeamIcon(team))}}<span class="focus-match-text">${{focusEscape(focusDisplayName(team))}} vs ${{focusEscape(focusDisplayName(opponent))}} — ${{focusEscape(focusDate(match.date))}}</span>${{focusFlag(opponentFlag || focusTeamIcon(opponent))}}`;
    }}

    ['worldcup', 'champions'].forEach(kind => {{
      const select = document.getElementById(`${{kind}}FocusSelect`);
      if (!select) return;
      select.addEventListener('change', () => {{
        localStorage.setItem(FOCUS_KEYS[kind], select.value);
        renderFocus(kind);
        document.dispatchEvent(new CustomEvent('akro:focus-change', {{detail: {{kind, focus: select.value}}}}));
      }});
      renderFocus(kind);
      document.dispatchEvent(new CustomEvent('akro:focus-change', {{detail: {{kind, focus: select.value}}}}));
    }});
  </script>"""


def _leagues_script() -> str:
    return """<script>
    const leaguesDataNode = document.getElementById('leaguesData');
    const LEAGUES_DATA = leaguesDataNode ? JSON.parse(leaguesDataNode.textContent || '{}') : null;
    const LEAGUE_KEY = 'akrodufoot:selected-league';
    const LEAGUE_FOCUS_KEY = 'akrodufoot:league-focus:';
    const LEAGUE_CLUB_LOGOS = {
      'ac milan': 'https://a.espncdn.com/i/teamlogos/soccer/500/103.png',
      'ajax': 'https://a.espncdn.com/i/teamlogos/soccer/500/139.png',
      'aj auxerre': 'https://a.espncdn.com/i/teamlogos/soccer/500/172.png',
      'arsenal': 'https://a.espncdn.com/i/teamlogos/soccer/500/359.png',
      'as monaco': 'https://a.espncdn.com/i/teamlogos/soccer/500/174.png',
      'atletico madrid': 'https://a.espncdn.com/i/teamlogos/soccer/500/1068.png',
      'atlético madrid': 'https://a.espncdn.com/i/teamlogos/soccer/500/1068.png',
      'auxerre': 'https://a.espncdn.com/i/teamlogos/soccer/500/172.png',
      'barcelona': 'https://a.espncdn.com/i/teamlogos/soccer/500/83.png',
      'bayer leverkusen': 'https://a.espncdn.com/i/teamlogos/soccer/500/131.png',
      'bayern munich': 'https://a.espncdn.com/i/teamlogos/soccer/500/132.png',
      'borussia dortmund': 'https://a.espncdn.com/i/teamlogos/soccer/500/124.png',
      'chelsea': 'https://a.espncdn.com/i/teamlogos/soccer/500/363.png',
      'internazionale': 'https://a.espncdn.com/i/teamlogos/soccer/500/110.png',
      'inter milan': 'https://a.espncdn.com/i/teamlogos/soccer/500/110.png',
      'juventus': 'https://a.espncdn.com/i/teamlogos/soccer/500/111.png',
      'lille': 'https://a.espncdn.com/i/teamlogos/soccer/500/166.png',
      'losc': 'https://a.espncdn.com/i/teamlogos/soccer/500/166.png',
      'lyon': 'https://a.espncdn.com/i/teamlogos/soccer/500/167.png',
      'manchester city': 'https://a.espncdn.com/i/teamlogos/soccer/500/382.png',
      'manchester united': 'https://a.espncdn.com/i/teamlogos/soccer/500/360.png',
      'marseille': 'https://a.espncdn.com/i/teamlogos/soccer/500/176.png',
      'monaco': 'https://a.espncdn.com/i/teamlogos/soccer/500/174.png',
      'napoli': 'https://a.espncdn.com/i/teamlogos/soccer/500/114.png',
      'nice': 'https://a.espncdn.com/i/teamlogos/soccer/500/2502.png',
      'ogc nice': 'https://a.espncdn.com/i/teamlogos/soccer/500/2502.png',
      'paris saint germain': 'https://a.espncdn.com/i/teamlogos/soccer/500/160.png',
      'psg': 'https://a.espncdn.com/i/teamlogos/soccer/500/160.png',
      'rc lens': 'https://a.espncdn.com/i/teamlogos/soccer/500/175.png',
      'real madrid': 'https://a.espncdn.com/i/teamlogos/soccer/500/86.png',
      'villarreal': 'https://a.espncdn.com/i/teamlogos/soccer/500/102.png'
    };

    function leagueEscape(value) {
      return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function leagueDate(value, withTime = true) {
      if (!value) return 'Date non disponible';
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString('fr-FR', withTime ? {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'} : {day:'2-digit', month:'2-digit', year:'numeric'}).replace(',', '');
    }

    function leagueFlag(url) {
      return url ? `<img class="flag" src="${leagueEscape(url)}" alt="">` : '<span class="flag placeholder" aria-hidden="true"></span>';
    }

    function leagueClubLogo(name) {
      const key = String(name || '').toLocaleLowerCase('fr-FR').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/-/g, ' ').replace(/\s+/g, ' ').trim();
      return LEAGUE_CLUB_LOGOS[key] || '';
    }

    function leagueTeam(name, logo = '', reverse = false) {
      const safeLogo = logo || leagueClubLogo(name);
      const content = reverse ? `${leagueEscape(name)}${leagueFlag(safeLogo)}` : `${leagueFlag(safeLogo)}${leagueEscape(name)}`;
      return `<button class="team team-button" type="button" data-team="${leagueEscape(name)}">${content}</button>`;
    }

    function leagueMatchScore(match) {
      return match.home_score !== '' && match.away_score !== '' ? `${match.home_score} - ${match.away_score}` : leagueDate(match.date).split(' ').pop() || 'VS';
    }

    function leagueMatchCard(match) {
      return `<article class="today-tile">
        <div class="today-meta">${leagueEscape(leagueDate(match.date))}</div>
        <div class="today-teams">
          <div class="today-team">${leagueTeam(match.home_team || 'À déterminer', match.home_flag_url || '')}</div>
          <div class="today-score">${leagueEscape(leagueMatchScore(match))}</div>
          <div class="today-team">${leagueTeam(match.away_team || 'À déterminer', match.away_flag_url || '', true)}</div>
        </div>
        <div class="subtle">${leagueEscape(match.venue || match.stadium || '')}</div>
        <span class="${match.status === 'LIVE' ? 'status live' : match.completed ? 'status done' : 'status'}">${leagueEscape(match.status || 'À venir')}</span>
      </article>`;
    }

    function leaguePlayerCard(player, label, variant = 'club') {
      const club = player.team || '';
      const clubLogo = player.team_logo_url || player.club_logo_url || leagueClubLogo(club) || player.flag_url || '';
      const countryFlag = player.country_flag_url || player.flag_url || '';
      const mainImage = variant === 'big5' ? countryFlag : clubLogo;
      const avatar = mainImage ? `<img class="avatar" src="${leagueEscape(mainImage)}" alt="">` : '<div class="avatar placeholder" aria-hidden="true"></div>';
      const bgClass = variant === 'big5' && player.league_key ? ` big5-card league-bg-${leagueEscape(player.league_key)}` : '';
      return `<article class="card player-card${bgClass}">
        <div class="avatar-wrap">${avatar}</div>
        <div><div class="team">${leagueEscape(player.name || 'Joueur')}</div>
        <div class="subtle club-line">${clubLogo ? `<img class="club-logo" src="${leagueEscape(clubLogo)}" alt="">` : '<span class="club-logo placeholder" aria-hidden="true"></span>'}<span class="club-name">${leagueEscape(club)}</span></div>
        ${player.league ? `<div class="subtle">${leagueEscape(player.league)}</div>` : ''}
        <div class="player-stat">${leagueEscape(player.value || '0')} <span class="subtle">${leagueEscape(label)}</span></div></div>
      </article>`;
    }

    function leagueGroupCard(group) {
      const rows = (group.teams || []).map(team => `<tr>
        <td>${leagueEscape(team.rank || '')}</td><td>${leagueTeam(team.team || '', team.flag_url || '')}</td>
        <td>${leagueEscape(team.played || '0')}</td><td>${leagueEscape(team.wins || '0')}</td><td>${leagueEscape(team.draws || '0')}</td><td>${leagueEscape(team.losses || '0')}</td><td>${leagueEscape(team.goal_diff || '0')}</td><td><strong>${leagueEscape(team.points || '0')}</strong></td>
      </tr>`).join('');
      return `<article class="card"><h3>${leagueEscape(group.name || 'Classement')}</h3><div class="table-scroll"><table><thead><tr><th>#</th><th>Équipe</th><th>J</th><th>G</th><th>N</th><th>P</th><th>DIFF.</th><th>PTS</th></tr></thead><tbody>${rows}</tbody></table></div></article>`;
    }

    function leagueCalendar(groups) {
      const matches = [];
      (groups || []).forEach(group => (group.matches || []).forEach(match => matches.push({...match, group: group.name || ''})));
      const byDate = new Map();
      matches.forEach(match => {
        const key = match.date ? new Date(match.date).toLocaleDateString('fr-CA') : 'date-inconnue';
        if (!byDate.has(key)) byDate.set(key, []);
        byDate.get(key).push(match);
      });
      return Array.from(byDate.entries()).sort((a,b)=>a[0].localeCompare(b[0])).map(([date, items]) => `<article class="card calendar-day"><h3>${leagueEscape(date === 'date-inconnue' ? 'Date inconnue' : leagueDate(items[0].date, false))}</h3><div class="matches">${items.map(match => `<div class="calendar-match league-calendar-match"><div class="date">${leagueEscape(leagueDate(match.date))}</div><div>${leagueTeam(match.home_team || 'À déterminer', match.home_flag_url || '')}</div><div class="score">${leagueEscape(match.home_score !== '' && match.away_score !== '' ? `${match.home_score} - ${match.away_score}` : '0 - 0')}</div><div class="away">${leagueTeam(match.away_team || 'À déterminer', match.away_flag_url || '', true)}</div><div class="match-meta"><div class="match-group">${leagueEscape(match.group || '')}</div><div class="subtle">${leagueEscape(match.venue || '')}</div><span class="status">${leagueEscape(match.status || 'À venir')}</span></div></div>`).join('')}</div></article>`).join('') || '<div class="empty">Calendrier indisponible.</div>';
    }

    function leagueFocusNews(kind, focus) {
      document.dispatchEvent(new CustomEvent('akro:league-focus-change', {detail: {kind, focus}}));
      if (typeof refreshNews === 'function') refreshNews('leagues');
    }

    function renderLeague() {
      if (!LEAGUES_DATA) return;
      const select = document.getElementById('leagueSelect');
      const clubSelect = document.getElementById('leagueClubSelect');
      const key = localStorage.getItem(LEAGUE_KEY) || (select && select.value) || LEAGUES_DATA.selected_league || 'ligue1';
      if (select && Array.from(select.options).some(option => option.value === key)) select.value = key;
      const league = (LEAGUES_DATA.leagues || {})[key] || {};
      const clubs = league.clubs || [];
      const savedClub = localStorage.getItem(LEAGUE_FOCUS_KEY + key);
      const focus = savedClub && clubs.includes(savedClub) ? savedClub : league.focused_club || clubs[0] || '';
      if (clubSelect) {
        clubSelect.innerHTML = clubs.map(club => `<option value="${leagueEscape(club)}"${club === focus ? ' selected' : ''}>${leagueEscape((FOCUS_TEAMS && FOCUS_TEAMS[club] && FOCUS_TEAMS[club].name) || club)}</option>`).join('');
      }
      const focusLogo = (typeof focusTeamIcon === 'function' ? focusTeamIcon(focus) : '') || leagueClubLogo(focus);
      const icon = document.getElementById('leagueFocusIcon');
      if (icon) icon.innerHTML = leagueFlag(focusLogo);
      const backdrop = document.getElementById('leagueFocusBackdrop');
      if (backdrop) backdrop.innerHTML = focusLogo ? `<img src="${leagueEscape(focusLogo)}" alt="">` : '<span class="flag placeholder" aria-hidden="true"></span>';
      const matches = (league.group_matches || []).flatMap(group => group.matches || []);
      const next = matches.filter(match => !match.completed && [match.home_team, match.away_team].includes(focus)).sort((a,b)=>String(a.date || '').localeCompare(String(b.date || '')))[0];
      const nextNode = document.getElementById('leagueFocusNext');
      if (nextNode) {
        if (next) {
          const isHome = next.home_team === focus;
          const opponent = isHome ? next.away_team : next.home_team;
          const focusMatchLogo = (isHome ? next.home_flag_url : next.away_flag_url) || leagueClubLogo(focus);
          const opponentMatchLogo = (isHome ? next.away_flag_url : next.home_flag_url) || leagueClubLogo(opponent);
          nextNode.innerHTML = `${leagueFlag(focusMatchLogo)}<span class="focus-match-text">${leagueEscape(focus)} vs ${leagueEscape(opponent)} — ${leagueEscape(leagueDate(next.date))}</span>${leagueFlag(opponentMatchLogo)}`;
        } else {
          nextNode.innerHTML = `${leagueFlag((typeof focusTeamIcon === 'function' ? focusTeamIcon(focus) : '') || leagueClubLogo(focus))}<span class="focus-match-text">Prochain match à déterminer</span>`;
        }
      }
      const updated = document.getElementById('leaguesUpdated');
      if (updated) updated.textContent = leagueDate(league.generated_at || LEAGUES_DATA.generated_at || '');
      const honoursButton = document.getElementById('leagueHonoursButton');
      if (honoursButton) honoursButton.dataset.alltime = `league-history-${key}`;
      document.getElementById('leagueUpcoming').innerHTML = (league.upcoming_matches || []).slice(0,3).map(leagueMatchCard).join('') || '<article class="today-tile" style="grid-column:1/-1"><strong>Aucun match à venir disponible</strong></article>';
      document.getElementById('big5TopScorers').innerHTML = (LEAGUES_DATA.big5_top_scorers || []).map(player => leaguePlayerCard(player, 'buts', 'big5')).join('') || '<div class="empty">Buteurs indisponibles.</div>';
      document.getElementById('leagueTopScorers').innerHTML = (league.top_scorers || []).slice(0,5).map(player => leaguePlayerCard(player, 'buts', 'club')).join('') || '<div class="empty">Buteurs indisponibles.</div>';
      document.getElementById('leagueTopAssists').innerHTML = (league.top_assists || []).slice(0,5).map(player => leaguePlayerCard(player, 'passes', 'club')).join('') || '<div class="empty">Passeurs indisponibles.</div>';
      document.getElementById('leagueStandings').innerHTML = (league.standings || []).map(leagueGroupCard).join('') || '<div class="empty">Classement indisponible.</div>';
      document.getElementById('leagueCalendar').innerHTML = leagueCalendar(league.group_matches || []);
      leagueFocusNews('leagues', focus);
    }

    document.addEventListener('DOMContentLoaded', renderLeague);
    document.addEventListener('change', event => {
      if (event.target && event.target.id === 'leagueSelect') {
        localStorage.setItem(LEAGUE_KEY, event.target.value);
        renderLeague();
      }
      if (event.target && event.target.id === 'leagueClubSelect') {
        const leagueKey = document.getElementById('leagueSelect').value;
        localStorage.setItem(LEAGUE_FOCUS_KEY + leagueKey, event.target.value);
        renderLeague();
      }
    });
    renderLeague();
  </script>"""


def _football_chatbot_script() -> str:
    return """<script>
    const footballChatbotButton = document.getElementById('chatbotButton');
    const footballChatbotModal = document.getElementById('footballChatbotModal');
    const footballChatbotClose = document.getElementById('footballChatbotClose');
    const footballChatbotForm = document.getElementById('footballChatbotForm');
    const footballChatbotInput = document.getElementById('footballChatbotInput');
    const footballChatbotMessages = document.getElementById('footballChatbotMessages');
    const footballChatbotHistory = [];

    function chatbotEscape(value) {
      return String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function formatChatbotContent(text) {
      const clean = chatbotEscape(text).trim();
      const paragraphs = clean.split(/\\n{2,}/).map(part => part.trim()).filter(Boolean);
      if (paragraphs.length > 1) return paragraphs.map(part => `<p>${part.replace(/\\n/g, '<br>')}</p>`).join('');
      return `<p>${clean.replace(/\\n/g, '<br>')}</p>`;
    }

    function setChatbotMessage(node, text) {
      node.innerHTML = formatChatbotContent(text);
    }

    function addChatbotMessage(role, text, save = true) {
      const node = document.createElement('div');
      node.className = `chatbot-message ${role}`;
      setChatbotMessage(node, text);
      footballChatbotMessages.appendChild(node);
      if (save) {
        footballChatbotHistory.push({role: role === 'user' ? 'user' : 'assistant', content: text});
        if (footballChatbotHistory.length > 10) footballChatbotHistory.shift();
      }
      footballChatbotMessages.scrollTop = footballChatbotMessages.scrollHeight;
      return node;
    }

    function openFootballChatbot() {
      footballChatbotModal.classList.add('is-open');
      footballChatbotModal.setAttribute('aria-hidden', 'false');
      footballChatbotInput.focus();
    }

    function closeFootballChatbot() {
      footballChatbotModal.classList.remove('is-open');
      footballChatbotModal.setAttribute('aria-hidden', 'true');
    }

    footballChatbotButton.addEventListener('click', openFootballChatbot);
    footballChatbotClose.addEventListener('click', closeFootballChatbot);
    footballChatbotModal.addEventListener('click', event => {
      if (event.target === footballChatbotModal) closeFootballChatbot();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && footballChatbotModal.classList.contains('is-open')) closeFootballChatbot();
    });

    footballChatbotForm.addEventListener('submit', async event => {
      event.preventDefault();
      const question = footballChatbotInput.value.trim();
      if (!question) return;
      footballChatbotInput.value = '';
      addChatbotMessage('user', question);
      const pending = addChatbotMessage('bot', 'Je réfléchis...', false);
      try {
        const response = await fetch('/api/football-chatbot', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: question, history: footballChatbotHistory.slice(-8)})
        });
        const data = await response.json().catch(() => ({}));
        const answer = data.answer || data.error || 'Coach indisponible : clé OpenAI absente ou invalide.';
        setChatbotMessage(pending, answer);
        footballChatbotHistory.push({role: 'assistant', content: answer});
        if (footballChatbotHistory.length > 10) footballChatbotHistory.shift();
      } catch (error) {
        const answer = 'Coach indisponible : clé OpenAI absente ou invalide.';
        setChatbotMessage(pending, answer);
        footballChatbotHistory.push({role: 'assistant', content: answer});
        if (footballChatbotHistory.length > 10) footballChatbotHistory.shift();
      }
    });
  </script>"""


def _team_script(teams_details: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    details_payload = json.dumps(teams_details, ensure_ascii=False).replace("</", "<\\/")
    matches_payload = json.dumps(matches, ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const TEAMS_DETAILS = {details_payload};
    const TEAM_MATCHES = {matches_payload};
    const modal = document.getElementById('teamModal');
    const modalTitle = document.getElementById('teamModalTitle');
    const modalFlag = document.getElementById('teamModalFlag');
    const modalSources = document.getElementById('teamModalSources');
    const teamRecent = document.getElementById('teamRecent');
    const teamCoach = document.getElementById('teamCoach');
    const teamHonors = document.getElementById('teamHonors');
    const closeModal = document.getElementById('teamModalClose');

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
    }}

    function flagHtml(url) {{
      return url ? `<img class="team-modal-flag" src="${{escapeHtml(url)}}" alt="">` : '<div class="team-modal-flag flag placeholder" aria-hidden="true"></div>';
    }}

    function teamDisplayName(name) {{
      const details = TEAMS_DETAILS[name] || {{}};
      return details.name || name || 'Équipe';
    }}

    function matchTime(value) {{
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? 'Date non disponible' : date.toLocaleDateString('fr-FR', {{day:'2-digit', month:'2-digit', year:'numeric'}});
    }}

    function recentScore(match) {{
      return match.home_score !== '' && match.away_score !== '' ? `${{match.home_score}} - ${{match.away_score}}` : 'Score non disponible';
    }}

    function recentResult(match, team) {{
      if (!match.completed || match.home_score === '' || match.away_score === '') return {{label: match.status || 'À venir', className: ''}};
      const home = Number(match.home_score);
      const away = Number(match.away_score);
      if (Number.isNaN(home) || Number.isNaN(away)) return {{label: 'Terminé', className: ''}};
      const isHome = match.home_team === team;
      const teamScore = isHome ? home : away;
      const opponentScore = isHome ? away : home;
      if (teamScore > opponentScore) return {{label: 'Victoire', className: 'win'}};
      if (teamScore < opponentScore) return {{label: 'Défaite', className: 'loss'}};
      return {{label: 'Nul', className: 'draw'}};
    }}

    function recentCard(match, team) {{
      const isHome = match.home_team === team;
      const opponent = isHome ? match.away_team : match.home_team;
      const location = isHome ? 'Domicile' : 'Extérieur';
      const result = recentResult(match, team);
      return `<article class="recent-match">
        <div><strong>${{escapeHtml(matchTime(match.date))}}</strong><div class="subtle">${{escapeHtml(match.competition || '')}} · ${{escapeHtml(location)}}</div></div>
        <div><strong>vs ${{escapeHtml(teamDisplayName(opponent))}}</strong><div class="subtle">${{escapeHtml(match.status || 'Statut non disponible')}}</div></div>
        <div class="recent-score">${{escapeHtml(recentScore(match))}}</div>
        <span class="recent-result ${{result.className}}">${{escapeHtml(result.label)}}</span>
      </article>`;
    }}

    function recentMatches(team) {{
      return TEAM_MATCHES
        .filter(match => match.home_team === team || match.away_team === team)
        .filter(match => match.date)
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))
        .slice(0, 10);
    }}

    function coachPhoto(info) {{
      return info.coach_country_flag
        ? `<img class="coach-photo" src="${{escapeHtml(info.coach_country_flag)}}" alt="">`
        : '<div class="coach-photo placeholder" aria-hidden="true">Drapeau</div>';
    }}

    function coachLine(info) {{
      const bits = [];
      if (info.coach_age) bits.push(`${{escapeHtml(info.coach_age)}} ans`);
      if (info.coach_country) bits.push(escapeHtml(info.coach_country));
      if (info.coach_matches) bits.push(`${{escapeHtml(info.coach_matches)}} matchs officiels`);
      return bits.join(' — ');
    }}

    function coachStat(label, percent, total, className) {{
      const value = percent !== undefined && percent !== null && percent !== '' ? `${{escapeHtml(percent)}}%` : '—';
      const detail = total !== undefined && total !== null && total !== '' ? `${{escapeHtml(total)}} ${{label.toLowerCase()}}` : label;
      return `<div class="coach-stat ${{className || ''}}"><strong>${{value}}</strong><span>${{escapeHtml(detail)}}</span></div>`;
    }}

    function coachCard(details) {{
      const info = details.coach_info || {{}};
      if (!info.coach_name) return '<div class="team-info"><div class="team-info-label">Entraîneur / sélectionneur</div><div class="team-info-value">Informations entraîneur non disponibles</div></div>';
      const source = info.source_url ? `<a href="${{escapeHtml(info.source_url)}}" target="_blank" rel="noreferrer">Foot Mercato</a>` : 'Foot Mercato';
      return `<section class="coach-card">
        <div class="coach-profile">
          ${{coachPhoto(info)}}
          <div><div class="team-info-label">Entraîneur / sélectionneur</div><div class="coach-name">${{escapeHtml(info.coach_name)}}</div><div class="subtle">${{coachLine(info)}}</div></div>
        </div>
        <div class="coach-stats">
          ${{coachStat('Victoires', info.coach_win_percent, info.coach_wins, 'win')}}
          ${{coachStat('Nuls', info.coach_draw_percent, info.coach_draws, 'draw')}}
          ${{coachStat('Défaites', info.coach_loss_percent, info.coach_losses, 'loss')}}
        </div>
        <div class="coach-source">Source : ${{source}}</div>
      </section>`;
    }}

    function honorsCard(details) {{
      const honors = details.honors || details.palmares || [];
      if (!honors.length) return '<div class="team-info"><div class="team-info-label">Palmarès</div><div class="team-info-value">Information non disponible</div></div>';
      return `<section class="team-info"><div class="team-info-label">Palmarès Foot Mercato</div><div class="honors-list">${{honors.map(item => `<article class="honor-row"><div><strong>${{escapeHtml(item.competition || '')}}</strong><div class="subtle">${{escapeHtml(item.years || 'Années non disponibles')}}</div></div><div class="honor-value">${{escapeHtml(item.titles || '')}} titre${{Number(item.titles) > 1 ? 's' : ''}}</div></article>`).join('')}}</div></section>`;
    }}

    function openTeam(name) {{
      const details = TEAMS_DETAILS[name] || {{name}};
      modalTitle.textContent = details.name || name;
      modalFlag.innerHTML = flagHtml(details.flag_url || '');
      modalSources.textContent = details.coach_info && details.coach_info.source ? `Source entraîneur : ${{details.coach_info.source}}` : 'Résultats disponibles dans les calendriers du dashboard';
      teamCoach.innerHTML = coachCard(details);
      teamHonors.innerHTML = honorsCard(details);
      const matches = recentMatches(name);
      teamRecent.innerHTML = matches.length
        ? `<div class="recent-list">${{matches.map(match => recentCard(match, name)).join('')}}</div>`
        : '<div class="empty">Forme récente non disponible pour cette équipe.</div>';
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



def _honours_entry(name: str, country: str, titles: int, years: str = "", asset_url: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "country": country,
        "flag_url": asset_url or _known_club_logo(name),
        "value": str(titles),
        "years": years,
    }


def _ranked_honours(title: str, empty: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_entries = sorted(entries, key=lambda item: int(item.get("value") or 0), reverse=True)
    ranked_entries = []
    previous_titles: int | None = None
    rank = 0
    for index, entry in enumerate(sorted_entries, start=1):
        titles = int(entry.get("value") or 0)
        if titles != previous_titles:
            rank = index
            previous_titles = titles
        ranked_entries.append({**entry, "rank": rank})
    return {"players": ranked_entries, "title": title, "empty": empty, "label": "titres"}


def _country_asset(code: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/countries/500/{code}.png"


def _honours_lists() -> dict[str, Any]:
    return {
        "worldcup-history": _ranked_honours(
            "Palmarès Coupe du Monde",
            "Palmarès Coupe du Monde indisponible",
            [
                _honours_entry("Brésil", "Brésil", 5, "1958, 1962, 1970, 1994, 2002", _country_asset("bra")),
                _honours_entry("Allemagne", "Allemagne", 4, "1954, 1974, 1990, 2014", _country_asset("ger")),
                _honours_entry("Italie", "Italie", 4, "1934, 1938, 1982, 2006", _country_asset("ita")),
                _honours_entry("Argentine", "Argentine", 3, "1978, 1986, 2022", _country_asset("arg")),
                _honours_entry("France", "France", 2, "1998, 2018", _country_asset("fra")),
                _honours_entry("Uruguay", "Uruguay", 2, "1930, 1950", _country_asset("uru")),
                _honours_entry("Angleterre", "Angleterre", 1, "1966", _country_asset("eng")),
                _honours_entry("Espagne", "Espagne", 1, "2010", _country_asset("esp")),
            ],
        ),
        "champions-history": _ranked_honours(
            "Palmarès Ligue des Champions",
            "Palmarès Ligue des Champions indisponible",
            [
                _honours_entry("Real Madrid", "Espagne", 15, "1956, 1957, 1958, 1959, 1960, 1966, 1998, 2000, 2002, 2014, 2016, 2017, 2018, 2022, 2024"),
                _honours_entry("AC Milan", "Italie", 7, "1963, 1969, 1989, 1990, 1994, 2003, 2007"),
                _honours_entry("Bayern Munich", "Allemagne", 6, "1974, 1975, 1976, 2001, 2013, 2020"),
                _honours_entry("Liverpool", "Angleterre", 6, "1977, 1978, 1981, 1984, 2005, 2019"),
                _honours_entry("Barcelona", "Espagne", 5, "1992, 2006, 2009, 2011, 2015"),
                _honours_entry("Ajax", "Pays-Bas", 4, "1971, 1972, 1973, 1995"),
                _honours_entry("Internazionale", "Italie", 3, "1964, 1965, 2010"),
                _honours_entry("Manchester United", "Angleterre", 3, "1968, 1999, 2008"),
                _honours_entry("Benfica", "Portugal", 2, "1961, 1962"),
                _honours_entry("Chelsea", "Angleterre", 2, "2012, 2021"),
                _honours_entry("Juventus", "Italie", 2, "1985, 1996"),
                _honours_entry("Nottingham Forest", "Angleterre", 2, "1979, 1980"),
                _honours_entry("Porto", "Portugal", 2, "1987, 2004"),
                _honours_entry("Celtic", "Écosse", 1, "1967"),
                _honours_entry("Feyenoord", "Pays-Bas", 1, "1970"),
                _honours_entry("Aston Villa", "Angleterre", 1, "1982"),
                _honours_entry("Hamburg", "Allemagne", 1, "1983"),
                _honours_entry("Steaua București", "Roumanie", 1, "1986"),
                _honours_entry("PSV", "Pays-Bas", 1, "1988"),
                _honours_entry("Red Star Belgrade", "Serbie", 1, "1991"),
                _honours_entry("Marseille", "France", 1, "1993"),
                _honours_entry("Borussia Dortmund", "Allemagne", 1, "1997"),
                _honours_entry("Manchester City", "Angleterre", 1, "2023"),
                _honours_entry("Paris Saint-Germain", "France", 1, "2025"),
            ],
        ),
        "league-history-ligue1": _ranked_honours(
            "Palmarès Ligue 1",
            "Palmarès Ligue 1 indisponible",
            [
                _honours_entry("Paris Saint-Germain", "France", 13, "1986, 1994, 2013, 2014, 2015, 2016, 2018, 2019, 2020, 2022, 2023, 2024, 2025"),
                _honours_entry("Saint-Étienne", "France", 10, "1957, 1964, 1967, 1968, 1969, 1970, 1974, 1975, 1976, 1981"),
                _honours_entry("Marseille", "France", 9, "1937, 1948, 1971, 1972, 1989, 1990, 1991, 1992, 2010"),
                _honours_entry("AS Monaco", "France", 8, "1961, 1963, 1978, 1982, 1988, 1997, 2000, 2017"),
                _honours_entry("Nantes", "France", 8, "1965, 1966, 1973, 1977, 1980, 1983, 1995, 2001"),
                _honours_entry("Lyon", "France", 7, "2002, 2003, 2004, 2005, 2006, 2007, 2008"),
                _honours_entry("Bordeaux", "France", 6, "1950, 1984, 1985, 1987, 1999, 2009"),
                _honours_entry("Reims", "France", 6, "1949, 1953, 1955, 1958, 1960, 1962"),
                _honours_entry("Lille", "France", 5, "1933, 1946, 1954, 2011, 2021"),
                _honours_entry("Nice", "France", 4, "1951, 1952, 1956, 1959"),
                _honours_entry("Sète", "France", 2, "1934, 1939"),
                _honours_entry("Sochaux", "France", 2, "1935, 1938"),
                _honours_entry("Auxerre", "France", 1, "1996"),
                _honours_entry("Lens", "France", 1, "1998"),
                _honours_entry("Montpellier", "France", 1, "2012"),
                _honours_entry("Racing Club de France", "France", 1, "1936"),
                _honours_entry("Roubaix-Tourcoing", "France", 1, "1947"),
                _honours_entry("Strasbourg", "France", 1, "1979"),
            ],
        ),
        "league-history-laliga": _ranked_honours(
            "Palmarès Liga",
            "Palmarès Liga indisponible",
            [
                _honours_entry("Real Madrid", "Espagne", 36, "1932, 1933, 1954, 1955, 1957, 1958, 1961, 1962, 1963, 1964, 1965, 1967, 1968, 1969, 1972, 1975, 1976, 1978, 1979, 1980, 1986, 1987, 1988, 1989, 1990, 1995, 1997, 2001, 2003, 2007, 2008, 2012, 2017, 2020, 2022, 2024"),
                _honours_entry("Barcelona", "Espagne", 28, "1929, 1945, 1948, 1949, 1952, 1953, 1959, 1960, 1974, 1985, 1991, 1992, 1993, 1994, 1998, 1999, 2005, 2006, 2009, 2010, 2011, 2013, 2015, 2016, 2018, 2019, 2023, 2025"),
                _honours_entry("Atlético Madrid", "Espagne", 11, "1940, 1941, 1950, 1951, 1966, 1970, 1973, 1977, 1996, 2014, 2021"),
                _honours_entry("Athletic Club", "Espagne", 8, "1930, 1931, 1934, 1936, 1943, 1956, 1983, 1984"),
                _honours_entry("Valencia", "Espagne", 6, "1942, 1944, 1947, 1971, 2002, 2004"),
                _honours_entry("Real Sociedad", "Espagne", 2, "1981, 1982"),
                _honours_entry("Deportivo La Coruña", "Espagne", 1, "2000"),
                _honours_entry("Real Betis", "Espagne", 1, "1935"),
                _honours_entry("Sevilla", "Espagne", 1, "1946"),
            ],
        ),
        "league-history-bundesliga": _ranked_honours(
            "Palmarès Bundesliga",
            "Palmarès Bundesliga indisponible",
            [
                _honours_entry("Bayern Munich", "Allemagne", 33, "1969, 1972, 1973, 1974, 1980, 1981, 1985, 1986, 1987, 1989, 1990, 1994, 1997, 1999, 2000, 2001, 2003, 2005, 2006, 2008, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2025"),
                _honours_entry("Borussia Dortmund", "Allemagne", 5, "1995, 1996, 2002, 2011, 2012"),
                _honours_entry("Borussia Mönchengladbach", "Allemagne", 5, "1970, 1971, 1975, 1976, 1977"),
                _honours_entry("Werder Bremen", "Allemagne", 4, "1965, 1988, 1993, 2004"),
                _honours_entry("Hamburg", "Allemagne", 3, "1979, 1982, 1983"),
                _honours_entry("Stuttgart", "Allemagne", 3, "1984, 1992, 2007"),
                _honours_entry("Kaiserslautern", "Allemagne", 2, "1991, 1998"),
                _honours_entry("Köln", "Allemagne", 2, "1964, 1978"),
                _honours_entry("1860 Munich", "Allemagne", 1, "1966"),
                _honours_entry("Bayer Leverkusen", "Allemagne", 1, "2024"),
                _honours_entry("Eintracht Braunschweig", "Allemagne", 1, "1967"),
                _honours_entry("Nürnberg", "Allemagne", 1, "1968"),
                _honours_entry("Wolfsburg", "Allemagne", 1, "2009"),
            ],
        ),
        "league-history-premierleague": _ranked_honours(
            "Palmarès championnat anglais",
            "Palmarès championnat anglais indisponible",
            [
                _honours_entry("Liverpool", "Angleterre", 20),
                _honours_entry("Manchester United", "Angleterre", 20),
                _honours_entry("Arsenal", "Angleterre", 13),
                _honours_entry("Manchester City", "Angleterre", 10),
                _honours_entry("Everton", "Angleterre", 9),
                _honours_entry("Aston Villa", "Angleterre", 7),
                _honours_entry("Chelsea", "Angleterre", 6),
                _honours_entry("Sunderland", "Angleterre", 6),
                _honours_entry("Newcastle United", "Angleterre", 4),
                _honours_entry("Sheffield Wednesday", "Angleterre", 4),
                _honours_entry("Blackburn Rovers", "Angleterre", 3),
                _honours_entry("Huddersfield Town", "Angleterre", 3),
                _honours_entry("Leeds United", "Angleterre", 3),
                _honours_entry("Wolverhampton Wanderers", "Angleterre", 3),
                _honours_entry("Burnley", "Angleterre", 2),
                _honours_entry("Derby County", "Angleterre", 2),
                _honours_entry("Portsmouth", "Angleterre", 2),
                _honours_entry("Preston North End", "Angleterre", 2),
                _honours_entry("Tottenham Hotspur", "Angleterre", 2),
                _honours_entry("Ipswich Town", "Angleterre", 1),
                _honours_entry("Leicester City", "Angleterre", 1),
                _honours_entry("Nottingham Forest", "Angleterre", 1),
                _honours_entry("Sheffield United", "Angleterre", 1),
                _honours_entry("West Bromwich Albion", "Angleterre", 1),
            ],
        ),
        "league-history-seriea": _ranked_honours(
            "Palmarès Serie A",
            "Palmarès Serie A indisponible",
            [
                _honours_entry("Juventus", "Italie", 36),
                _honours_entry("Internazionale", "Italie", 20),
                _honours_entry("AC Milan", "Italie", 19),
                _honours_entry("Genoa", "Italie", 9),
                _honours_entry("Bologna", "Italie", 7),
                _honours_entry("Pro Vercelli", "Italie", 7),
                _honours_entry("Torino", "Italie", 7),
                _honours_entry("Napoli", "Italie", 4, "1987, 1990, 2023, 2025"),
                _honours_entry("Roma", "Italie", 3),
                _honours_entry("Fiorentina", "Italie", 2),
                _honours_entry("Lazio", "Italie", 2),
                _honours_entry("Cagliari", "Italie", 1),
                _honours_entry("Casale", "Italie", 1),
                _honours_entry("Hellas Verona", "Italie", 1),
                _honours_entry("Novese", "Italie", 1),
                _honours_entry("Sampdoria", "Italie", 1),
            ],
        ),
    }


def _all_time_script(worldcup_scorers: list[dict[str, Any]], champions_scorers: list[dict[str, Any]]) -> str:
    worldcup_scorers_payload = json.dumps(worldcup_scorers[:10], ensure_ascii=False).replace("</", "<\\/")
    champions_scorers_payload = json.dumps(champions_scorers[:10], ensure_ascii=False).replace("</", "<\\/")
    honours_payload = json.dumps(_honours_lists(), ensure_ascii=False).replace("</", "<\\/")
    return f"""<script>
    const HONOURS_LISTS = {honours_payload};
    const ALL_TIME_LISTS = Object.assign({{
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
    }}, HONOURS_LISTS);
    const allTimeModal = document.getElementById('allTimeModal');
    const allTimeTitle = document.getElementById('allTimeTitle');
    const allTimeBody = document.getElementById('allTimeBody');
    const allTimeClose = document.getElementById('allTimeClose');

    function allTimeAvatar(player) {{
      return player.flag_url
        ? `<img class="mini-avatar" src="${{escapeHtml(player.flag_url)}}" alt="">`
        : '<div class="mini-avatar placeholder" aria-hidden="true"></div>';
    }}

    function allTimeRow(player, label) {{
      const country = player.country || player.team || 'Pays non disponible';
      const years = player.years ? `<div class="subtle">${{escapeHtml(player.years)}}</div>` : '';
      return `<article class="alltime-row">
        <div class="alltime-rank">${{escapeHtml(player.rank || '')}}</div>
        ${{allTimeAvatar(player)}}
        <div><strong>${{escapeHtml(player.name || '')}}</strong><div class="subtle">${{escapeHtml(country)}}</div>${{years}}</div>
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


def _global_prediction_matches(worldcup_data: dict[str, Any], champions_data: dict[str, Any] | None, leagues_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
    for key, league in (leagues_data or {}).get("leagues", {}).items():
        matches.extend(_prediction_matches(league.get("group_matches", []), [], league.get("name", "Championnat"), f"league-{key}"))
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
    const coachPrediction = document.getElementById('coachPrediction');
    const predictionStatus = document.getElementById('predictionStatus');
    const predictionPseudo = document.getElementById('predictionPseudo');
    const predictionSubmit = predictionForm.querySelector('button[type="submit"]');
    let communityMatches = DASHBOARD_MATCHES;
    let coachPredictionRequest = 0;

    function pseudoValue() {{
      return (predictionPseudo.value || '').trim();
    }}

    function savePseudo() {{
      const pseudo = pseudoValue();
      if (pseudo) localStorage.setItem('akrodufoot:pseudo', pseudo);
      else localStorage.removeItem('akrodufoot:pseudo');
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
      const live = matches.find(match => match.status === 'LIVE');
      if (live) return live;
      const fallback = matches.slice().sort((a, b) => matchTimestamp(b) - matchTimestamp(a));
      return fallback[0] || null;
    }}

    function sortPredictionMatches(matches) {{
      const now = Date.now();
      return matches.slice().sort((a, b) => {{
        const aAvailable = isMatchAvailable(a);
        const bAvailable = isMatchAvailable(b);
        if (aAvailable !== bAvailable) return aAvailable ? -1 : 1;
        const aDistance = Math.abs(matchTimestamp(a) - now);
        const bDistance = Math.abs(matchTimestamp(b) - now);
        if (aDistance !== bDistance) return aDistance - bDistance;
        return matchTimestamp(a) - matchTimestamp(b);
      }});
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
      const selected = source
        .filter(isTodayMatch)
        .sort((a, b) => matchTimestamp(a) - matchTimestamp(b));
      followMode.textContent = 'Aujourd’hui';
      communityFollowMatches.innerHTML = selected.length
        ? selected.map(followMatchCard).join('')
        : '<div class="empty">Aucun match aujourd’hui</div>';
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
      const ordered = sortPredictionMatches(filtered);
      const selected = closestPredictionMatch(ordered, selectedCompetition);
      predictionMatch.innerHTML = ordered.map((match) => {{
        const label = `${{match.competition || 'Compétition'}} · ${{shortDate(match.date)}} · ${{match.home_team}} vs ${{match.away_team}}`;
        return `<option value="${{escapeHtml(match.id)}}">${{escapeHtml(label)}}</option>`;
      }}).join('');
      if (selected) predictionMatch.value = selected.id;
      const hasMatches = filtered.length > 0;
      const matchAvailable = Boolean(selected && isMatchAvailable(selected));
      predictionMatch.disabled = !hasMatches;
      document.getElementById('homePrediction').disabled = !matchAvailable;
      document.getElementById('awayPrediction').disabled = !matchAvailable;
      updatePredictionButton(matchAvailable, hasMatches);
      updatePredictionTeams();
    }}

    function updatePredictionButton(matchAvailable = null, hasMatches = null) {{
      const match = selectedMatch();
      const available = matchAvailable === null ? Boolean(match && isMatchAvailable(match)) : matchAvailable;
      const hasAnyMatch = hasMatches === null ? Boolean(match) : hasMatches;
      const hasPseudo = Boolean(pseudoValue());
      predictionSubmit.disabled = !available || !hasPseudo;
      if (!hasAnyMatch) {{
        predictionStatus.textContent = competitionFilter.value === 'today'
          ? 'Aucun match du jour disponible pour les pronostics'
          : 'Aucun match disponible avec ce filtre';
      }} else if (!available) {{
        predictionStatus.textContent = 'Tous les matchs de ce filtre sont terminés';
      }} else if (!hasPseudo) {{
        predictionStatus.textContent = 'Choisis un pseudo pour participer au classement';
      }} else {{
        predictionStatus.textContent = '';
      }}
    }}

    function selectedMatch() {{
      return communityMatches.find((match) => match.id === predictionMatch.value);
    }}

    function flagMarkup(url) {{
      return url ? `<img class="flag" src="${{escapeHtml(url)}}" alt="">` : '<span class="flag placeholder" aria-hidden="true"></span>';
    }}

    function updatePredictionTeams() {{
      const match = selectedMatch();
      if (!match) {{
        predictionHomeName.textContent = 'Aucun match';
        predictionAwayName.textContent = 'disponible';
        predictionHomeFlag.innerHTML = '<span class="flag placeholder" aria-hidden="true"></span>';
        predictionAwayFlag.innerHTML = '<span class="flag placeholder" aria-hidden="true"></span>';
        predictionContext.textContent = competitionFilter.value === 'today'
          ? 'Aucun match du jour disponible pour les pronostics'
          : 'Aucun match disponible avec ce filtre';
        updateCoachPrediction(null);
        updatePredictionButton(false, false);
        return;
      }}
      predictionHomeName.textContent = match.home_team;
      predictionAwayName.textContent = match.away_team;
      predictionHomeFlag.innerHTML = flagMarkup(match.home_flag_url);
      predictionAwayFlag.innerHTML = flagMarkup(match.away_flag_url);
      predictionContext.textContent = `${{match.competition || 'Compétition'}} · ${{shortDate(match.date)}} · ${{match.phase || ''}}`;
      updateCoachPrediction(match);
      updatePredictionButton();
    }}

    function renderCoachPrediction(data) {{
      if (!coachPrediction) return;
      const fallback = {{
        predicted_winner: 'Analyse en attente',
        predicted_score: '',
        confidence: '',
        reason: 'Coach prépare son analyse dès que le match est sélectionné.',
        disclaimer: 'Analyse fictive pour le jeu entre amis. Aucun conseil de pari réel.'
      }};
      const info = data || fallback;
      const confidence = info.confidence ? ` — confiance ${{escapeHtml(info.confidence)}}%` : '';
      const score = info.predicted_score ? ` · score probable ${{escapeHtml(info.predicted_score)}}` : '';
      const reason = info.reason || fallback.reason;
      const disclaimer = info.disclaimer || fallback.disclaimer;
      coachPrediction.innerHTML = `
        <div class="coach-prediction-top"><span class="coach-badge">Coach</span><span>Coach : ${{escapeHtml(info.predicted_winner || fallback.predicted_winner)}}${{score}}${{confidence}}.</span></div>
        <div class="coach-reason">Analyse : ${{escapeHtml(reason)}}</div>
        <div class="coach-disclaimer">${{escapeHtml(disclaimer)}}</div>
      `;
    }}

    async function updateCoachPrediction(match) {{
      const requestId = ++coachPredictionRequest;
      if (!match) {{
        renderCoachPrediction(null);
        return;
      }}
      if (!serverMode) {{
        renderCoachPrediction(null);
        return;
      }}
      coachPrediction.innerHTML = `
        <div class="coach-prediction-top"><span class="coach-badge">Coach</span><span>Analyse en cours...</span></div>
        <div class="coach-reason">Analyse fictive pour le jeu entre amis.</div>
        <div class="coach-disclaimer">Aucun conseil de pari réel.</div>
      `;
      try {{
        const response = await fetch('/api/coach-prediction', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{match_id: match.id}})
        }});
        const data = await response.json().catch(() => ({{}}));
        if (requestId === coachPredictionRequest) renderCoachPrediction(data);
      }} catch (error) {{
        if (requestId === coachPredictionRequest) renderCoachPrediction(null);
      }}
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
        updatePredictionButton();
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
    competitionFilter.addEventListener('change', () => renderMatchOptions(communityMatches));
    predictionMatch.addEventListener('change', updatePredictionTeams);
    predictionPseudo.addEventListener('input', () => {{ savePseudo(); updatePredictionButton(); }});
    predictionForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (!pseudoValue()) {{
        predictionStatus.textContent = 'Choisis un pseudo pour participer au classement';
        updatePredictionButton();
        return;
      }}
      savePseudo();
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
    predictionPseudo.value = localStorage.getItem('akrodufoot:pseudo') || '';
    renderMatchOptions(DASHBOARD_MATCHES);
    loadCommunity();
  </script>"""


def _display_score(value: Any) -> str:
    text = str(value)
    return escape(text) if text else ""


def _flag(url: str) -> str:
    if url:
        return f'<img class="flag" src="{escape(url)}" alt="">'
    return '<span class="flag placeholder" aria-hidden="true"></span>'


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
