import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Json = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const API_KEY = Deno.env.get("FOOTBALL_API_KEY") ?? "";
const API_BASE_URL = (Deno.env.get("FOOTBALL_API_BASE_URL") ?? "").replace(/\/$/, "");
const API_KEY_HEADER = Deno.env.get("FOOTBALL_API_KEY_HEADER") ?? "x-apisports-key";

const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const jsonHeaders = {"Content-Type": "application/json; charset=utf-8"};

function response(payload: Json, status = 200) {
  return new Response(JSON.stringify(payload), {status, headers: jsonHeaders});
}

function asArray(payload: unknown): Json[] {
  if (!payload) return [];
  if (Array.isArray(payload)) return payload as Json[];
  if (typeof payload === "object") {
    const obj = payload as Json;
    if (Array.isArray(obj.response)) return obj.response as Json[];
    if (Array.isArray(obj.data)) return obj.data as Json[];
    if (Array.isArray(obj.results)) return obj.results as Json[];
  }
  return [];
}

function pick<T = unknown>(obj: Json, paths: string[], fallback: T): T {
  for (const path of paths) {
    let current: unknown = obj;
    for (const part of path.split(".")) {
      if (!current || typeof current !== "object") {
        current = undefined;
        break;
      }
      current = (current as Json)[part];
    }
    if (current !== undefined && current !== null && current !== "") return current as T;
  }
  return fallback;
}

async function withRetry(url: string, attempt = 1): Promise<Json[]> {
  const res = await fetch(url, {headers: {[API_KEY_HEADER]: API_KEY, "Accept": "application/json"}});
  if ((res.status === 429 || res.status >= 500) && attempt < 3) {
    await new Promise(resolve => setTimeout(resolve, 600 * attempt));
    return withRetry(url, attempt + 1);
  }
  if (!res.ok) throw new Error(`API ${res.status} ${url}`);
  return asArray(await res.json());
}

async function football(path: string, params: Record<string, string | number | undefined> = {}) {
  const url = new URL(`${API_BASE_URL}/${path.replace(/^\//, "")}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  });
  return withRetry(url.toString());
}

async function upsert(table: string, rows: Json[], onConflict = "api_id") {
  if (!rows.length) return 0;
  const {error} = await supabase.from(table).upsert(rows, {onConflict, ignoreDuplicates: false});
  if (error) throw new Error(`${table}: ${error.message}`);
  return rows.length;
}

async function startLog() {
  const {data, error} = await supabase.from("sync_logs").insert({
    job_name: "sync-football-data",
    status: "running",
    message: "Synchronisation football démarrée.",
  }).select("id").single();
  if (error) throw new Error(`sync_logs insert: ${error.message}`);
  return data.id as string;
}

async function finishLog(id: string, status: "success" | "error", message: string, counts: Json, errorDetail = "") {
  await supabase.from("sync_logs").update({
    status,
    message,
    processed_counts: counts,
    error_detail: errorDetail || null,
    finished_at: new Date().toISOString(),
  }).eq("id", id);
}

async function readIdMap(table: string) {
  const {data, error} = await supabase.from(table).select("id,api_id").not("api_id", "is", null);
  if (error) throw new Error(`${table} map: ${error.message}`);
  return new Map((data ?? []).map((row: Json) => [String(row.api_id), String(row.id)]));
}

Deno.serve(async () => {
  if (!SUPABASE_URL || !SERVICE_KEY) return response({error: "Supabase service role manquant."}, 500);
  const logId = await startLog();
  const counts: Json = {countries: 0, competitions: 0, teams: 0, players: 0, coaches: 0, team_players: 0, team_coaches: 0, matches: 0};
  try {
    if (!API_KEY || !API_BASE_URL) {
      const message = "Clé API football absente : mode offline, aucune table vidée.";
      await finishLog(logId, "error", message, counts, "FOOTBALL_API_KEY ou FOOTBALL_API_BASE_URL manquant.");
      return response({ok: false, offline: true, message, counts}, 200);
    }

    const countries = await football("countries");
    counts.countries = await upsert("countries", countries.map(item => ({
      api_id: String(pick(item, ["code", "name"], "")),
      name: String(pick(item, ["name", "country.name"], "Information non disponible")),
      code: String(pick(item, ["code"], "")),
      flag_url: String(pick(item, ["flag", "country.flag"], "")),
      updated_at: new Date().toISOString(),
    })).filter(row => row.api_id && row.name));

    const countryMap = await readIdMap("countries");
    const competitions = await football("leagues", {current: "true"});
    counts.competitions = await upsert("competitions", competitions.map(item => {
      const league = pick<Json>(item, ["league"], {});
      const country = pick<Json>(item, ["country"], {});
      const seasons = pick<Json[]>(item, ["seasons"], []);
      return {
        api_id: String(pick(league, ["id"], "")),
        country_id: countryMap.get(String(pick(country, ["code", "name"], ""))) ?? null,
        name: String(pick(league, ["name"], "Information non disponible")),
        type: String(pick(league, ["type"], "")),
        logo_url: String(pick(league, ["logo"], "")),
        season: String(pick(seasons[0] ?? {}, ["year"], "")),
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      };
    }).filter(row => row.api_id && row.name));

    const competitionMap = await readIdMap("competitions");
    const leagueIds = Array.from(competitionMap.keys()).slice(0, Number(Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? "12"));
    for (const leagueId of leagueIds) {
      const teams = await football("teams", {league: leagueId, season: new Date().getUTCFullYear()});
      counts.teams = Number(counts.teams) + await upsert("teams", teams.map(item => {
        const team = pick<Json>(item, ["team"], {});
        const venue = pick<Json>(item, ["venue"], {});
        const countryName = String(pick(team, ["country"], ""));
        return {
          api_id: String(pick(team, ["id"], "")),
          country_id: countryMap.get(countryName) ?? null,
          name: String(pick(team, ["name"], "Information non disponible")),
          code: String(pick(team, ["code"], "")),
          type: "club",
          logo_url: String(pick(team, ["logo"], "")),
          venue_name: String(pick(venue, ["name"], "")),
          is_active: true,
          raw_data: item,
          updated_at: new Date().toISOString(),
        };
      }).filter(row => row.api_id && row.name));
    }

    const teamMap = await readIdMap("teams");
    for (const teamApiId of Array.from(teamMap.keys()).slice(0, Number(Deno.env.get("FOOTBALL_SYNC_TEAM_LIMIT") ?? "40"))) {
      const squad = await football("players/squads", {team: teamApiId});
      const players = squad.flatMap(item => asArray((item as Json).players));
      counts.players = Number(counts.players) + await upsert("players", players.map(item => ({
        api_id: String(pick(item, ["id"], "")),
        name: String(pick(item, ["name"], "Information non disponible")),
        position: String(pick(item, ["position"], "")),
        photo_url: String(pick(item, ["photo"], "")),
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      })).filter(row => row.api_id && row.name));

      const playerMap = await readIdMap("players");
      counts.team_players = Number(counts.team_players) + await upsert("team_players", players.map(item => {
        const playerId = playerMap.get(String(pick(item, ["id"], "")));
        return {
          api_id: `${teamApiId}:${pick(item, ["id"], "")}:${new Date().getUTCFullYear()}`,
          team_id: teamMap.get(teamApiId),
          player_id: playerId,
          season: String(new Date().getUTCFullYear()),
          shirt_number: pick<number | null>(item, ["number"], null),
          position: String(pick(item, ["position"], "")),
          is_active: true,
          raw_data: item,
          updated_at: new Date().toISOString(),
        };
      }).filter(row => row.team_id && row.player_id), "api_id");

      const coaches = await football("coachs", {team: teamApiId});
      counts.coaches = Number(counts.coaches) + await upsert("coaches", coaches.map(item => ({
        api_id: String(pick(item, ["id"], "")),
        name: String(pick(item, ["name"], "Information non disponible")),
        firstname: String(pick(item, ["firstname"], "")),
        lastname: String(pick(item, ["lastname"], "")),
        birth_date: pick(item, ["birth.date"], null),
        nationality: String(pick(item, ["nationality"], "")),
        photo_url: String(pick(item, ["photo"], "")),
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      })).filter(row => row.api_id && row.name));

      const coachMap = await readIdMap("coaches");
      counts.team_coaches = Number(counts.team_coaches) + await upsert("team_coaches", coaches.map(item => ({
        api_id: `${teamApiId}:${pick(item, ["id"], "")}:${new Date().getUTCFullYear()}`,
        team_id: teamMap.get(teamApiId),
        coach_id: coachMap.get(String(pick(item, ["id"], ""))),
        season: String(new Date().getUTCFullYear()),
        role: "head_coach",
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      })).filter(row => row.team_id && row.coach_id), "api_id");
    }

    for (const leagueId of leagueIds) {
      const fixtures = await football("fixtures", {league: leagueId, season: new Date().getUTCFullYear()});
      counts.matches = Number(counts.matches) + await upsert("matches", fixtures.map(item => {
        const fixture = pick<Json>(item, ["fixture"], {});
        const teams = pick<Json>(item, ["teams"], {});
        const goals = pick<Json>(item, ["goals"], {});
        const home = pick<Json>(teams, ["home"], {});
        const away = pick<Json>(teams, ["away"], {});
        return {
          api_id: String(pick(fixture, ["id"], "")),
          competition_id: competitionMap.get(leagueId) ?? null,
          season: String(new Date().getUTCFullYear()),
          round: String(pick(item, ["league.round"], "")),
          status: String(pick(fixture, ["status.short", "status.long"], "")),
          match_date: pick(fixture, ["date"], null),
          venue_name: String(pick(fixture, ["venue.name"], "")),
          home_team_id: teamMap.get(String(pick(home, ["id"], ""))) ?? null,
          away_team_id: teamMap.get(String(pick(away, ["id"], ""))) ?? null,
          home_score: pick<number | null>(goals, ["home"], null),
          away_score: pick<number | null>(goals, ["away"], null),
          raw_data: item,
          updated_at: new Date().toISOString(),
        };
      }).filter(row => row.api_id));
    }

    await finishLog(logId, "success", "Synchronisation football terminée.", counts);
    return response({ok: true, counts});
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await finishLog(logId, "error", "Synchronisation football échouée. Les données existantes sont conservées.", counts, message);
    return response({ok: false, error: message, counts}, 500);
  }
});
