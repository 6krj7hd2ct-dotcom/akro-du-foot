import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Json = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const API_KEY = Deno.env.get("FOOTBALL_API_KEY") ?? "";
const API_BASE_URL = (Deno.env.get("FOOTBALL_API_BASE_URL") ?? "").replace(/\/$/, "");
const API_KEY_HEADER = Deno.env.get("FOOTBALL_API_KEY_HEADER") ?? "x-apisports-key";
const DEFAULT_LEAGUE_LIMIT = 1;
const DEFAULT_TEAM_LIMIT = 1;

console.log("[sync-football-data] boot", {
  hasSupabaseUrl: Boolean(SUPABASE_URL),
  hasServiceKey: Boolean(SERVICE_KEY),
  hasFootballApiKey: Boolean(API_KEY),
  hasFootballApiBaseUrl: Boolean(API_BASE_URL),
  footballApiBaseUrl: API_BASE_URL || "(missing)",
  footballApiKeyHeader: API_KEY_HEADER,
  leagueLimit: Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(DEFAULT_LEAGUE_LIMIT),
  teamLimit: Deno.env.get("FOOTBALL_SYNC_TEAM_LIMIT") ?? String(DEFAULT_TEAM_LIMIT),
});

const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});
console.log("[sync-football-data] supabase client created", {hasClient: Boolean(supabase)});

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
  console.log("[sync-football-data] football api request", {url, attempt, header: API_KEY_HEADER, hasApiKey: Boolean(API_KEY)});
  const res = await fetch(url, {headers: {[API_KEY_HEADER]: API_KEY, "Accept": "application/json"}});
  console.log("[sync-football-data] football api response", {url, attempt, status: res.status, ok: res.ok});
  if ((res.status === 429 || res.status >= 500) && attempt < 3) {
    console.warn("[sync-football-data] retry scheduled", {url, attempt, status: res.status});
    await new Promise(resolve => setTimeout(resolve, 600 * attempt));
    return withRetry(url, attempt + 1);
  }
  const raw = await res.text();
  if (!res.ok) {
    console.error("[sync-football-data] football api error body", {url, status: res.status, body: raw.slice(0, 1200)});
    throw new Error(`API ${res.status} ${url} body=${raw.slice(0, 500)}`);
  }
  const parsed = raw ? JSON.parse(raw) : {};
  const rows = asArray(parsed);
  console.log("[sync-football-data] football api parsed", {url, rows: rows.length});
  return rows;
}

async function football(path: string, params: Record<string, string | number | undefined> = {}) {
  const url = new URL(`${API_BASE_URL}/${path.replace(/^\//, "")}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  });
  return withRetry(url.toString());
}

async function upsert(table: string, rows: Json[], onConflict = "api_id") {
  console.log("[sync-football-data] upsert start", {table, rows: rows.length, onConflict});
  if (!rows.length) {
    console.log("[sync-football-data] upsert skipped empty", {table});
    return 0;
  }
  const {error} = await supabase.from(table).upsert(rows, {onConflict, ignoreDuplicates: false});
  if (error) {
    console.error("[sync-football-data] upsert error", {table, message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`${table}: ${error.message}`);
  }
  console.log("[sync-football-data] upsert success", {table, rows: rows.length});
  return rows.length;
}

async function startLog() {
  console.log("[sync-football-data] start sync_logs insert");
  const {data, error} = await supabase.from("sync_logs").insert({
    job_name: "sync-football-data",
    status: "running",
    message: "Synchronisation football démarrée.",
  }).select("id").single();
  if (error) {
    console.error("[sync-football-data] sync_logs insert error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`sync_logs insert: ${error.message}`);
  }
  console.log("[sync-football-data] sync_logs inserted", {id: data.id});
  return data.id as string;
}

async function finishLog(id: string, status: "success" | "error", message: string, counts: Json, errorDetail = "") {
  console.log("[sync-football-data] finish sync_logs update", {id, status, message, counts, hasErrorDetail: Boolean(errorDetail)});
  const {error} = await supabase.from("sync_logs").update({
    status,
    message,
    processed_counts: counts,
    error_detail: errorDetail || null,
    finished_at: new Date().toISOString(),
  }).eq("id", id);
  if (error) console.error("[sync-football-data] sync_logs update error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
}

async function readIdMap(table: string) {
  console.log("[sync-football-data] read id map start", {table});
  const {data, error} = await supabase.from(table).select("id,api_id").not("api_id", "is", null);
  if (error) {
    console.error("[sync-football-data] read id map error", {table, message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`${table} map: ${error.message}`);
  }
  const map = new Map((data ?? []).map((row: Json) => [String(row.api_id), String(row.id)]));
  console.log("[sync-football-data] read id map success", {table, rows: map.size});
  return map;
}

Deno.serve(async () => {
  console.log("[sync-football-data] request received");
  if (!SUPABASE_URL || !SERVICE_KEY) {
    console.error("[sync-football-data] missing supabase env", {hasSupabaseUrl: Boolean(SUPABASE_URL), hasServiceKey: Boolean(SERVICE_KEY)});
    return response({error: "Supabase service role manquant."}, 500);
  }
  let logId = "";
  const counts: Json = {countries: 0, competitions: 0, teams: 0, players: 0, coaches: 0, team_players: 0, team_coaches: 0, matches: 0};
  try {
    logId = await startLog();
    console.log("[sync-football-data] sync started", {logId});
    if (!API_KEY || !API_BASE_URL) {
      const message = "Clé API football absente : mode offline, aucune table vidée.";
      console.warn("[sync-football-data] missing football env", {hasFootballApiKey: Boolean(API_KEY), hasFootballApiBaseUrl: Boolean(API_BASE_URL)});
      await finishLog(logId, "error", message, counts, "FOOTBALL_API_KEY ou FOOTBALL_API_BASE_URL manquant.");
      return response({ok: false, offline: true, message, counts}, 200);
    }

    console.log("[sync-football-data] step countries start");
    const countries = await football("countries");
    console.log("[sync-football-data] step countries fetched", {count: countries.length});
    counts.countries = await upsert("countries", countries.map(item => ({
      api_id: String(pick(item, ["code", "name"], "")),
      name: String(pick(item, ["name", "country.name"], "Information non disponible")),
      code: String(pick(item, ["code"], "")),
      flag_url: String(pick(item, ["flag", "country.flag"], "")),
      updated_at: new Date().toISOString(),
    })).filter(row => row.api_id && row.name));
    console.log("[sync-football-data] step countries done", {inserted: counts.countries});

    console.log("[sync-football-data] step competitions start");
    const countryMap = await readIdMap("countries");
    const competitions = await football("leagues", {current: "true"});
    console.log("[sync-football-data] step competitions fetched", {count: competitions.length});
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
    console.log("[sync-football-data] step competitions done", {inserted: counts.competitions});

    console.log("[sync-football-data] step teams start");
    const competitionMap = await readIdMap("competitions");
    const leagueLimit = Number(Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(DEFAULT_LEAGUE_LIMIT));
    const leagueIds = Array.from(competitionMap.keys()).slice(0, leagueLimit);
    console.log("[sync-football-data] league ids selected", {leagueLimit, leagueIds});
    for (const leagueId of leagueIds) {
      console.log("[sync-football-data] fetch teams", {leagueId});
      const teams = await football("teams", {league: leagueId, season: new Date().getUTCFullYear()});
      console.log("[sync-football-data] teams fetched", {leagueId, count: teams.length});
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
      console.log("[sync-football-data] teams upserted cumulative", {teams: counts.teams});
    }

    console.log("[sync-football-data] step squads/coaches start");
    const teamMap = await readIdMap("teams");
    const teamLimit = Number(Deno.env.get("FOOTBALL_SYNC_TEAM_LIMIT") ?? String(DEFAULT_TEAM_LIMIT));
    const teamApiIds = Array.from(teamMap.keys()).slice(0, teamLimit);
    console.log("[sync-football-data] team ids selected", {teamLimit, teamApiIds});
    for (const teamApiId of teamApiIds) {
      console.log("[sync-football-data] fetch squad", {teamApiId});
      const squad = await football("players/squads", {team: teamApiId});
      const players = squad.flatMap(item => asArray((item as Json).players));
      console.log("[sync-football-data] squad fetched", {teamApiId, squadRows: squad.length, players: players.length});
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
      console.log("[sync-football-data] upsert team_players", {teamApiId, players: players.length});
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

      console.log("[sync-football-data] fetch coaches", {teamApiId});
      const coaches = await football("coachs", {team: teamApiId});
      console.log("[sync-football-data] coaches fetched", {teamApiId, count: coaches.length});
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
      console.log("[sync-football-data] upsert team_coaches", {teamApiId, coaches: coaches.length});
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

    console.log("[sync-football-data] step matches start");
    for (const leagueId of leagueIds) {
      console.log("[sync-football-data] fetch fixtures", {leagueId});
      const fixtures = await football("fixtures", {league: leagueId, season: new Date().getUTCFullYear()});
      console.log("[sync-football-data] fixtures fetched", {leagueId, count: fixtures.length});
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
      console.log("[sync-football-data] fixtures upserted cumulative", {matches: counts.matches});
    }

    console.log("[sync-football-data] sync success", {counts});
    await finishLog(logId, "success", "Synchronisation football terminée.", counts);
    return response({ok: true, counts});
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error("[sync-football-data] sync failed", {
      message,
      stack: error instanceof Error ? error.stack : "",
      counts,
      logId,
    });
    if (logId) {
      await finishLog(logId, "error", "Synchronisation football échouée. Les données existantes sont conservées.", counts, message);
    }
    return response({ok: false, error: message, counts}, 500);
  }
});
