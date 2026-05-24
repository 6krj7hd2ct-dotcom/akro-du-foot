import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Json = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const API_KEY = Deno.env.get("FOOTBALL_API_KEY") ?? "";
const API_BASE_URL = (Deno.env.get("FOOTBALL_API_BASE_URL") ?? "").replace(/\/$/, "");
const API_KEY_HEADER = Deno.env.get("FOOTBALL_API_KEY_HEADER") ?? "x-apisports-key";
const DEFAULT_LEAGUE_LIMIT = 1;
const DEFAULT_TEAM_LIMIT = 3;
const DEFAULT_TEAMS_TOTAL_LIMIT = 50;
const DEFAULT_MATCHES_TOTAL_LIMIT = 50;
const DEFAULT_TEAM_LEAGUES = "61,39,140,135,78";
const INCLUDE_DETAILS = (Deno.env.get("FOOTBALL_SYNC_INCLUDE_DETAILS") ?? "false").toLowerCase() === "true";
const INCLUDE_MATCHES = (Deno.env.get("FOOTBALL_SYNC_INCLUDE_MATCHES") ?? "false").toLowerCase() === "true";

console.log("[sync-football-data] boot", {
  hasSupabaseUrl: Boolean(SUPABASE_URL),
  hasServiceKey: Boolean(SERVICE_KEY),
  hasFootballApiKey: Boolean(API_KEY),
  hasFootballApiBaseUrl: Boolean(API_BASE_URL),
  footballApiBaseUrl: API_BASE_URL || "(missing)",
  footballApiKeyHeader: API_KEY_HEADER,
  leagueLimit: Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(DEFAULT_LEAGUE_LIMIT),
  teamLimit: Deno.env.get("FOOTBALL_SYNC_TEAM_LIMIT") ?? String(DEFAULT_TEAM_LIMIT),
  teamsTotalLimit: Deno.env.get("FOOTBALL_SYNC_TEAMS_TOTAL_LIMIT") ?? String(DEFAULT_TEAMS_TOTAL_LIMIT),
  teamLeagues: Deno.env.get("FOOTBALL_SYNC_TEAM_LEAGUES") ?? DEFAULT_TEAM_LEAGUES,
  matchesTotalLimit: Deno.env.get("FOOTBALL_SYNC_MATCHES_TOTAL_LIMIT") ?? String(DEFAULT_MATCHES_TOTAL_LIMIT),
  includeDetails: INCLUDE_DETAILS,
  includeMatches: INCLUDE_MATCHES,
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

function dedupeRows(table: string, rows: Json[], keyForRow: (row: Json) => string) {
  const byKey = new Map<string, Json>();
  let missingKey = 0;
  for (const row of rows) {
    const key = keyForRow(row).trim();
    if (!key) {
      missingKey += 1;
      continue;
    }
    byKey.set(key, row);
  }
  const deduped = Array.from(byKey.values());
  const removed = rows.length - deduped.length;
  console.log("[sync-football-data] dedupe before upsert", {
    table,
    input: rows.length,
    output: deduped.length,
    removed,
    missingKey,
  });
  return deduped;
}

function apiIdKey(row: Json) {
  return String(row.api_id ?? "");
}

function norm(value: unknown) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function currentFootballSeason() {
  const now = new Date();
  const year = now.getUTCFullYear();
  return now.getUTCMonth() < 6 ? year - 1 : year;
}

function configuredLeagueIds() {
  return (Deno.env.get("FOOTBALL_SYNC_TEAM_LEAGUES") ?? DEFAULT_TEAM_LEAGUES)
    .split(",")
    .map(value => value.trim())
    .filter(Boolean);
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

async function readCompetitionTargets() {
  const leagueIds = configuredLeagueIds();
  console.log("[sync-football-data] read competition targets start", {leagueIds});
  const {data, error} = await supabase
    .from("competitions")
    .select("id,api_id,name,season")
    .in("api_id", leagueIds);
  if (error) {
    console.error("[sync-football-data] read competition targets error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`competitions targets: ${error.message}`);
  }
  const byApiId = new Map((data ?? []).map((row: Json) => [String(row.api_id), row]));
  const fallbackSeason = String(Deno.env.get("FOOTBALL_SYNC_SEASON") ?? currentFootballSeason());
  const targets = leagueIds.map(apiId => {
    const row = byApiId.get(apiId);
    return {
      api_id: apiId,
      id: row ? String(row.id ?? "") : "",
      name: row ? String(row.name ?? "") : "",
      season: String(Deno.env.get("FOOTBALL_SYNC_SEASON") ?? row?.season ?? fallbackSeason),
    };
  });
  console.log("[sync-football-data] read competition targets success", {found: data?.length ?? 0, targets});
  return targets;
}

async function readCountryLookup() {
  console.log("[sync-football-data] read country lookup start");
  const {data, error} = await supabase.from("countries").select("id,api_id,name,code");
  if (error) {
    console.error("[sync-football-data] read country lookup error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`countries lookup: ${error.message}`);
  }
  const map = new Map<string, string>();
  for (const row of data ?? []) {
    const record = row as Json;
    const id = String(record.id ?? "");
    [record.api_id, record.name, record.code].forEach(value => {
      const key = norm(value);
      if (key && id) map.set(key, id);
    });
  }
  console.log("[sync-football-data] read country lookup success", {keys: map.size, rows: data?.length ?? 0});
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
    const countryRows = dedupeRows("countries", countries.map(item => ({
      api_id: String(pick(item, ["code", "name"], "")),
      name: String(pick(item, ["name", "country.name"], "Information non disponible")),
      code: String(pick(item, ["code"], "")),
      flag_url: String(pick(item, ["flag", "country.flag"], "")),
      updated_at: new Date().toISOString(),
    })).filter(row => row.api_id && row.name), row => apiIdKey(row) || `${row.code ?? ""}:${row.name ?? ""}`);
    counts.countries = await upsert("countries", countryRows);
    console.log("[sync-football-data] step countries done", {inserted: counts.countries});

    console.log("[sync-football-data] step competitions start");
    const countryLookup = await readCountryLookup();
    const competitions = await football("leagues", {current: "true"});
    console.log("[sync-football-data] step competitions fetched", {count: competitions.length});
    const competitionRows = dedupeRows("competitions", competitions.map(item => {
      const league = pick<Json>(item, ["league"], {});
      const country = pick<Json>(item, ["country"], {});
      const seasons = pick<Json[]>(item, ["seasons"], []);
      const currentSeason = seasons.find(season => Boolean(pick(season, ["current"], false))) ?? seasons.at(-1) ?? {};
      return {
        api_id: String(pick(league, ["id"], "")),
        country_id: countryLookup.get(norm(pick(country, ["code"], ""))) ?? countryLookup.get(norm(pick(country, ["name"], ""))) ?? null,
        name: String(pick(league, ["name"], "Information non disponible")),
        type: String(pick(league, ["type"], "")),
        logo_url: String(pick(league, ["logo"], "")),
        season: String(pick(currentSeason, ["year"], currentFootballSeason())),
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      };
    }).filter(row => row.api_id && row.name), apiIdKey);
    counts.competitions = await upsert("competitions", competitionRows);
    console.log("[sync-football-data] step competitions done", {inserted: counts.competitions});

    console.log("[sync-football-data] step teams start");
    const leagueLimit = Number(Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(DEFAULT_LEAGUE_LIMIT));
    const teamsTotalLimit = Number(Deno.env.get("FOOTBALL_SYNC_TEAMS_TOTAL_LIMIT") ?? String(DEFAULT_TEAMS_TOTAL_LIMIT));
    const competitionTargets = (await readCompetitionTargets()).slice(0, leagueLimit);
    const competitionMap = new Map(competitionTargets.map(target => [target.api_id, target.id]).filter(([, id]) => Boolean(id)));
    const leagueIds = competitionTargets.map(target => target.api_id);
    const syncedTeamApiIds: string[] = [];
    console.log("[sync-football-data] league ids selected", {leagueLimit, teamsTotalLimit, competitionTargets});
    for (const target of competitionTargets) {
      const leagueId = target.api_id;
      const season = target.season || String(currentFootballSeason());
      if (Number(counts.teams) >= teamsTotalLimit) {
        console.log("[sync-football-data] teams total limit reached before league", {teams: counts.teams, teamsTotalLimit});
        break;
      }
      console.log("[sync-football-data] fetch teams", {leagueId, season, competitionName: target.name});
      const teams = await football("teams", {league: leagueId, season});
      console.log("[sync-football-data] teams fetched", {leagueId, season, count: teams.length});
      const teamRows = dedupeRows("teams", teams.map(item => {
        const team = pick<Json>(item, ["team"], {});
        const venue = pick<Json>(item, ["venue"], {});
        const countryName = String(pick(team, ["country"], ""));
        const countryKey = norm(countryName);
        return {
          api_id: String(pick(team, ["id"], "")),
          country_id: countryLookup.get(countryKey) ?? null,
          name: String(pick(team, ["name"], "Information non disponible")),
          code: String(pick(team, ["code"], "")),
          type: "club",
          logo_url: String(pick(team, ["logo"], "")),
          venue_name: String(pick(venue, ["name"], "")),
          is_active: true,
          raw_data: item,
          updated_at: new Date().toISOString(),
        };
      }).filter(row => row.api_id && row.name), apiIdKey);
      const remaining = Math.max(0, teamsTotalLimit - Number(counts.teams));
      const limitedTeamRows = teamRows.slice(0, remaining);
      const linkedCountries = limitedTeamRows.filter(row => row.country_id).length;
      syncedTeamApiIds.push(...limitedTeamRows.map(row => String(row.api_id ?? "")).filter(Boolean));
      console.log("[sync-football-data] teams prepared", {
        leagueId,
        season,
        fetched: teams.length,
        deduped: teamRows.length,
        limited: limitedTeamRows.length,
        linkedCountries,
        teamsTotalLimit,
      });
      counts.teams = Number(counts.teams) + await upsert("teams", limitedTeamRows);
      console.log("[sync-football-data] teams upserted cumulative", {teams: counts.teams, teamsTotalLimit});
    }

    if (!INCLUDE_DETAILS) {
      console.log("[sync-football-data] details skipped", {reason: "FOOTBALL_SYNC_INCLUDE_DETAILS is not true"});
      await finishLog(logId, "success", "Synchronisation football équipes terminée. Joueurs/coachs ignorés en mode petit volume.", counts);
      return response({ok: true, counts, skipped: {details: true, matches: !INCLUDE_MATCHES}});
    }

    console.log("[sync-football-data] step squads/coaches start");
    const teamMap = await readIdMap("teams");
    const teamLimit = Number(Deno.env.get("FOOTBALL_SYNC_TEAM_LIMIT") ?? String(DEFAULT_TEAM_LIMIT));
    const teamApiIds = syncedTeamApiIds.slice(0, teamLimit);
    console.log("[sync-football-data] team ids selected", {
      teamLimit,
      teamApiIds,
      source: "teams synchronized in this run only",
    });
    for (const teamApiId of teamApiIds) {
      console.log("[sync-football-data] fetch squad", {teamApiId});
      const squad = await football("players/squads", {team: teamApiId});
      const players = squad.flatMap(item => asArray((item as Json).players));
      console.log("[sync-football-data] squad fetched", {teamApiId, squadRows: squad.length, players: players.length});
      const playerRows = dedupeRows("players", players.map(item => ({
        api_id: String(pick(item, ["id"], "")),
        name: String(pick(item, ["name"], "Information non disponible")),
        position: String(pick(item, ["position"], "")),
        photo_url: String(pick(item, ["photo"], "")),
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      })).filter(row => row.api_id && row.name), apiIdKey);
      console.log("[sync-football-data] players prepared", {teamApiId, fetched: players.length, deduped: playerRows.length});
      counts.players = Number(counts.players) + await upsert("players", playerRows);

      const playerMap = await readIdMap("players");
      console.log("[sync-football-data] upsert team_players", {teamApiId, players: players.length});
      const teamPlayerRows = dedupeRows("team_players", players.map(item => {
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
      }).filter(row => row.team_id && row.player_id), row => apiIdKey(row) || `${row.team_id ?? ""}:${row.player_id ?? ""}:${row.season ?? ""}`);
      counts.team_players = Number(counts.team_players) + await upsert("team_players", teamPlayerRows, "api_id");

      console.log("[sync-football-data] fetch coaches", {teamApiId});
      const coaches = await football("coachs", {team: teamApiId});
      console.log("[sync-football-data] coaches fetched", {teamApiId, count: coaches.length});
      const coachRows = dedupeRows("coaches", coaches.map(item => ({
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
      })).filter(row => row.api_id && row.name), apiIdKey);
      console.log("[sync-football-data] coaches prepared", {teamApiId, fetched: coaches.length, deduped: coachRows.length});
      counts.coaches = Number(counts.coaches) + await upsert("coaches", coachRows);

      const coachMap = await readIdMap("coaches");
      console.log("[sync-football-data] upsert team_coaches", {teamApiId, coaches: coaches.length});
      const teamCoachRows = dedupeRows("team_coaches", coaches.map(item => ({
        api_id: `${teamApiId}:${pick(item, ["id"], "")}:${new Date().getUTCFullYear()}`,
        team_id: teamMap.get(teamApiId),
        coach_id: coachMap.get(String(pick(item, ["id"], ""))),
        season: String(new Date().getUTCFullYear()),
        role: "head_coach",
        is_active: true,
        raw_data: item,
        updated_at: new Date().toISOString(),
      })).filter(row => row.team_id && row.coach_id), row => apiIdKey(row) || `${row.team_id ?? ""}:${row.coach_id ?? ""}:${row.season ?? ""}:${row.role ?? ""}`);
      counts.team_coaches = Number(counts.team_coaches) + await upsert("team_coaches", teamCoachRows, "api_id");
    }

    if (!INCLUDE_MATCHES) {
      console.log("[sync-football-data] matches skipped", {reason: "FOOTBALL_SYNC_INCLUDE_MATCHES is not true"});
      await finishLog(logId, "success", "Synchronisation football terminée. Matchs ignorés en mode petit volume.", counts);
      return response({ok: true, counts, skipped: {matches: true}});
    }

    console.log("[sync-football-data] step matches start");
    const matchesTotalLimit = Number(Deno.env.get("FOOTBALL_SYNC_MATCHES_TOTAL_LIMIT") ?? String(DEFAULT_MATCHES_TOTAL_LIMIT));
    console.log("[sync-football-data] matches limit", {matchesTotalLimit});
    for (const leagueId of leagueIds) {
      if (Number(counts.matches) >= matchesTotalLimit) {
        console.log("[sync-football-data] matches total limit reached before league", {matches: counts.matches, matchesTotalLimit});
        break;
      }
      console.log("[sync-football-data] fetch fixtures", {leagueId});
      const fixtures = await football("fixtures", {league: leagueId, season: new Date().getUTCFullYear()});
      console.log("[sync-football-data] fixtures fetched", {leagueId, count: fixtures.length});
      const matchRows = dedupeRows("matches", fixtures.map(item => {
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
      }).filter(row => row.api_id), apiIdKey);
      const remainingMatches = Math.max(0, matchesTotalLimit - Number(counts.matches));
      const limitedMatchRows = matchRows.slice(0, remainingMatches);
      console.log("[sync-football-data] matches prepared", {
        leagueId,
        fetched: fixtures.length,
        deduped: matchRows.length,
        limited: limitedMatchRows.length,
        matchesTotalLimit,
      });
      counts.matches = Number(counts.matches) + await upsert("matches", limitedMatchRows);
      console.log("[sync-football-data] fixtures upserted cumulative", {matches: counts.matches, matchesTotalLimit});
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
