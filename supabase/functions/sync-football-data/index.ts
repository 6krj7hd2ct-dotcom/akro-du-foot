import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Json = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const API_KEY = Deno.env.get("FOOTBALL_API_KEY") ?? "";
const API_BASE_URL = (Deno.env.get("FOOTBALL_API_BASE_URL") ?? "").replace(/\/$/, "");
const API_KEY_HEADER = Deno.env.get("FOOTBALL_API_KEY_HEADER") ?? "x-apisports-key";
const DEFAULT_LEAGUE_LIMIT = 24;
const DEFAULT_TEAMS_TOTAL_LIMIT = 50;
const DEFAULT_PLAYER_TEAMS_LIMIT = 3;
const DEFAULT_COACH_TEAMS_LIMIT = 3;
const DEFAULT_MATCHES_TOTAL_LIMIT = 50;
const DEFAULT_COMPLETE_ROSTER_SIZE = 25;
const DEFAULT_TEAM_LEAGUES = "61,39,140,135,78,2,3,88,94,144,203,179,71,128,262,253,307,98,113,106,119,103,197,383";
const DEFAULT_PRIORITY_TEAMS = [
  "Colombia", "Colombie", "Argentina", "Argentine", "Cape Verde", "Cap-Vert", "Bosnia-Herzegovina", "Bosnia and Herzegovina", "Bosnie-Herzégovine", "South Africa", "Afrique du Sud",
  "Croatia", "Croatie", "England", "Angleterre", "Portugal", "Austria", "Autriche", "Sweden", "Suède", "Türkiye", "Turkey", "Turquie", "Mexico", "Mexique", "Norway", "Norvège",
  "Czechia", "Czech Republic", "République Tchèque", "Haiti", "Haïti", "Scotland", "Écosse", "Curacao", "Curaçao", "Iraq", "Irak", "Jordan", "Jordanie",
  "Uzbekistan", "Ouzbékistan", "Panama", "New Zealand", "Nouvelle-Zélande", "Congo DR", "DR Congo",
  "Ghana", "Senegal", "Sénégal", "Algeria", "Algérie", "Morocco", "Maroc", "Tunisia", "Tunisie", "Saudi Arabia", "Arabie Saoudite", "Iran",
  "South Korea", "Korea Republic", "Corée du Sud", "Canada", "Qatar", "Switzerland", "Suisse",
  "Brazil", "Brésil", "United States", "USA", "États-Unis", "Paraguay", "Australia", "Australie",
  "Germany", "Allemagne", "Ivory Coast", "Côte d'Ivoire", "Ecuador", "Équateur", "Netherlands", "Pays-Bas", "Japan", "Japon",
  "Belgium", "Belgique", "Egypt", "Égypte", "Spain", "Espagne", "Uruguay", "France", "Norway", "Norvège",
  "Paris Saint-Germain", "PSG", "Arsenal", "Real Madrid", "Barcelona", "Barcelone", "Bayern Munich", "Bayern München", "Bayern Munchen",
  "Inter", "Internazionale", "Manchester City", "Liverpool", "Atletico Madrid", "Atlético Madrid", "Borussia Dortmund",
].join(",");
const INCLUDE_PLAYERS = (Deno.env.get("FOOTBALL_SYNC_INCLUDE_PLAYERS") ?? "false").toLowerCase() === "true";
const INCLUDE_COACHES = (Deno.env.get("FOOTBALL_SYNC_INCLUDE_COACHES") ?? "false").toLowerCase() === "true";
const INCLUDE_MATCHES = (Deno.env.get("FOOTBALL_SYNC_INCLUDE_MATCHES") ?? "false").toLowerCase() === "true";

console.log("[sync-football-data] boot", {
  hasSupabaseUrl: Boolean(SUPABASE_URL),
  hasServiceKey: Boolean(SERVICE_KEY),
  hasFootballApiKey: Boolean(API_KEY),
  hasFootballApiBaseUrl: Boolean(API_BASE_URL),
  footballApiBaseUrl: API_BASE_URL || "(missing)",
  footballApiKeyHeader: API_KEY_HEADER,
  leagueLimit: Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(Math.max(DEFAULT_LEAGUE_LIMIT, (Deno.env.get("FOOTBALL_SYNC_TEAM_LEAGUES") ?? DEFAULT_TEAM_LEAGUES).split(",").map(value => value.trim()).filter(Boolean).length)),
  teamsTotalLimit: Deno.env.get("FOOTBALL_SYNC_TEAMS_TOTAL_LIMIT") ?? String(DEFAULT_TEAMS_TOTAL_LIMIT),
  playerTeamsLimit: Deno.env.get("FOOTBALL_SYNC_PLAYER_TEAMS_LIMIT") ?? String(DEFAULT_PLAYER_TEAMS_LIMIT),
  coachTeamsLimit: Deno.env.get("FOOTBALL_SYNC_COACH_TEAMS_LIMIT") ?? String(DEFAULT_COACH_TEAMS_LIMIT),
  completeRosterSize: Deno.env.get("FOOTBALL_SYNC_COMPLETE_ROSTER_SIZE") ?? String(DEFAULT_COMPLETE_ROSTER_SIZE),
  teamLeagues: Deno.env.get("FOOTBALL_SYNC_TEAM_LEAGUES") ?? DEFAULT_TEAM_LEAGUES,
  priorityTeams: Deno.env.get("FOOTBALL_SYNC_PRIORITY_TEAMS") ?? DEFAULT_PRIORITY_TEAMS,
  matchesTotalLimit: Deno.env.get("FOOTBALL_SYNC_MATCHES_TOTAL_LIMIT") ?? String(DEFAULT_MATCHES_TOTAL_LIMIT),
  includePlayers: INCLUDE_PLAYERS,
  includeCoaches: INCLUDE_COACHES,
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

function configuredPriorityTeams() {
  return (Deno.env.get("FOOTBALL_SYNC_PRIORITY_TEAMS") ?? DEFAULT_PRIORITY_TEAMS)
    .split(",")
    .map(value => value.trim())
    .filter(Boolean);
}

function countryIdForName(countryLookup: Map<string, string>, name: unknown) {
  const key = norm(name);
  return key ? countryLookup.get(key) ?? null : null;
}

function priorityIndexForTeam(name: unknown) {
  const teamName = norm(name);
  if (!teamName) return -1;
  return configuredPriorityTeams()
    .map(norm)
    .filter(Boolean)
    .findIndex(priorityName => teamName === priorityName);
}

function priorityAliasForTeam(name: unknown) {
  const teamName = norm(name);
  if (!teamName) return "";
  return configuredPriorityTeams().find(priorityName => norm(priorityName) === teamName) ?? "";
}

function teamRowFromApi(item: Json, countryLookup: Map<string, string>) {
  const team = pick<Json>(item, ["team"], {});
  const venue = pick<Json>(item, ["venue"], {});
  const countryName = String(pick(team, ["country"], ""));
  const national = Boolean(pick(team, ["national"], false));
  return {
    api_id: String(pick(team, ["id"], "")),
    country_id: countryIdForName(countryLookup, countryName),
    name: String(pick(team, ["name"], "Information non disponible")),
    code: String(pick(team, ["code"], "")),
    type: national ? "nation" : "club",
    logo_url: String(pick(team, ["logo"], "")),
    venue_name: String(pick(venue, ["name"], "")),
    is_active: true,
    raw_data: item,
    updated_at: new Date().toISOString(),
  };
}

function normalizePlayerItem(item: Json, countryLookup: Map<string, string>) {
  const nestedPlayer = pick<Json>(item, ["player"], {});
  const stats = pick<Json[]>(item, ["statistics"], []);
  const firstStats = stats[0] ?? {};
  const games = pick<Json>(firstStats, ["games"], {});
  const birth = pick<Json>(item, ["birth"], pick<Json>(nestedPlayer, ["birth"], {}));
  const apiId = String(pick(item, ["id"], pick(nestedPlayer, ["id"], "")));
  const name = String(pick(item, ["name"], pick(nestedPlayer, ["name"], "Information non disponible")));
  const nationality = String(pick(item, ["nationality"], pick(nestedPlayer, ["nationality"], "")));
  const position = String(pick(item, ["position"], pick(nestedPlayer, ["position"], pick(games, ["position"], ""))));
  return {
    api_id: apiId,
    name,
    firstname: String(pick(item, ["firstname"], pick(nestedPlayer, ["firstname"], ""))),
    lastname: String(pick(item, ["lastname"], pick(nestedPlayer, ["lastname"], ""))),
    birth_date: pick(item, ["birth.date", "birth_date"], pick(nestedPlayer, ["birth.date", "birth_date"], pick(birth, ["date"], null))),
    nationality,
    country_id: countryIdForName(countryLookup, nationality),
    position,
    photo_url: String(pick(item, ["photo"], pick(nestedPlayer, ["photo"], ""))),
    shirt_number: pick<number | null>(item, ["number"], pick<number | null>(games, ["number"], null)),
    is_active: true,
    raw_data: item,
    updated_at: new Date().toISOString(),
  };
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

async function tableCount(table: string) {
  const {count, error} = await supabase.from(table).select("id", {count: "exact", head: true});
  if (error) {
    console.error("[sync-football-data] count error", {table, message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`${table} count: ${error.message}`);
  }
  return count ?? 0;
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

async function readIdMapForApiIds(table: string, apiIds: string[]) {
  const uniqueApiIds = Array.from(new Set(apiIds.map(value => String(value || "").trim()).filter(Boolean)));
  console.log("[sync-football-data] read scoped id map start", {table, requested: uniqueApiIds.length});
  const map = new Map<string, string>();
  for (let index = 0; index < uniqueApiIds.length; index += 100) {
    const chunk = uniqueApiIds.slice(index, index + 100);
    const {data, error} = await supabase
      .from(table)
      .select("id,api_id")
      .in("api_id", chunk);
    if (error) {
      console.error("[sync-football-data] read scoped id map error", {table, message: error.message, details: error.details, hint: error.hint, code: error.code});
      throw new Error(`${table} scoped map: ${error.message}`);
    }
    for (const row of data ?? []) {
      map.set(String(row.api_id), String(row.id));
    }
  }
  console.log("[sync-football-data] read scoped id map success", {table, requested: uniqueApiIds.length, found: map.size, missing: uniqueApiIds.length - map.size});
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

async function readTeamPlayerCounts() {
  console.log("[sync-football-data] read team player counts start");
  const counts = new Map<string, number>();
  const {data, error} = await supabase
    .from("team_players")
    .select("team_id")
    .eq("is_active", true)
    .limit(20000);
  if (error) {
    console.error("[sync-football-data] read team player counts error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`team_players counts: ${error.message}`);
  }
  for (const row of data ?? []) {
    const teamId = String((row as Json).team_id ?? "");
    if (teamId) counts.set(teamId, (counts.get(teamId) ?? 0) + 1);
  }
  console.log("[sync-football-data] read team player counts success", {relations: data?.length ?? 0, teams: counts.size});
  return counts;
}

async function readTeamTargets(limit: number, options: {rosterCounts?: Map<string, number>; completeRosterSize?: number; skipComplete?: boolean} = {}) {
  console.log("[sync-football-data] read team targets start", {limit, skipComplete: Boolean(options.skipComplete), completeRosterSize: options.completeRosterSize ?? 0});
  const {data, error} = await supabase
    .from("teams")
    .select("id,api_id,name,type,updated_at")
    .not("api_id", "is", null)
    .order("updated_at", {ascending: true})
    .limit(5000);
  if (error) {
    console.error("[sync-football-data] read team targets error", {message: error.message, details: error.details, hint: error.hint, code: error.code});
    throw new Error(`teams targets: ${error.message}`);
  }
  const rows = (data ?? []).map((row: Json) => ({
    id: String(row.id ?? ""),
    api_id: String(row.api_id ?? ""),
    name: String(row.name ?? ""),
    type: String(row.type ?? ""),
    linkedPlayers: options.rosterCounts?.get(String(row.id ?? "")) ?? 0,
    priorityIndex: priorityIndexForTeam(row.name),
    priorityAlias: priorityAliasForTeam(row.name),
  })).filter(row => row.id && row.api_id);
  const enriched = rows.map(row => ({...row, priority: row.priorityIndex >= 0}));
  const completeRosterSize = options.completeRosterSize ?? DEFAULT_COMPLETE_ROSTER_SIZE;
  const completeRows = options.skipComplete ? enriched.filter(row => row.linkedPlayers >= completeRosterSize) : [];
  const availableRows = options.skipComplete ? enriched.filter(row => row.linkedPlayers < completeRosterSize) : enriched;
  const priority = availableRows
    .filter(row => row.priority)
    .sort((a, b) => a.priorityIndex - b.priorityIndex || a.linkedPlayers - b.linkedPlayers || a.name.localeCompare(b.name));
  const regular = availableRows
    .filter(row => !row.priority)
    .sort((a, b) => a.linkedPlayers - b.linkedPlayers || a.name.localeCompare(b.name));
  const targets = [...priority, ...regular].slice(0, limit);
  console.log("[sync-football-data] read team targets success", {
    rows: targets.length,
    priorityRows: priority.length,
    skippedComplete: completeRows.length,
    skippedCompleteSample: completeRows.slice(0, 8).map(row => ({name: row.name, type: row.type, linkedPlayers: row.linkedPlayers})),
    limit,
    targets,
  });
  return {targets, skippedComplete: completeRows};
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
    const configuredTeamLeagueCount = configuredLeagueIds().length;
    const leagueLimit = Number(Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT") ?? String(Math.max(DEFAULT_LEAGUE_LIMIT, configuredTeamLeagueCount)));
    const teamsTotalLimit = Number(Deno.env.get("FOOTBALL_SYNC_TEAMS_TOTAL_LIMIT") ?? String(DEFAULT_TEAMS_TOTAL_LIMIT));
    const priorityTeamNames = configuredPriorityTeams();
    const competitionTargets = (await readCompetitionTargets()).slice(0, leagueLimit);
    const competitionMap = new Map(competitionTargets.map(target => [target.api_id, target.id]).filter(([, id]) => Boolean(id)));
    let teamCandidates = 0;
    let teamUpserted = 0;
    console.log("[sync-football-data] teams limits", {
      teamsTotalLimit,
      leagueLimit,
      configuredTeamLeagueCount,
      leaguesToScan: competitionTargets.length,
      hasTeamsTotalLimitSecret: Boolean(Deno.env.get("FOOTBALL_SYNC_TEAMS_TOTAL_LIMIT")),
      hasLeagueLimitSecret: Boolean(Deno.env.get("FOOTBALL_SYNC_LEAGUE_LIMIT")),
      hasTeamLeaguesSecret: Boolean(Deno.env.get("FOOTBALL_SYNC_TEAM_LEAGUES")),
      priorityTeams: priorityTeamNames,
    });
    if (priorityTeamNames.length && teamsTotalLimit > 0) {
      console.log("[sync-football-data] priority teams start", {count: priorityTeamNames.length});
      const priorityItems: Json[] = [];
      for (const teamName of priorityTeamNames) {
        if (priorityItems.length >= teamsTotalLimit) break;
        console.log("[sync-football-data] fetch priority team", {teamName});
        const found = await football("teams", {search: teamName});
        const exact = found.filter(item => {
          const apiTeam = pick<Json>(item, ["team"], {});
          const apiName = norm(pick(apiTeam, ["name"], ""));
          const wanted = norm(teamName);
          return Boolean(apiName && wanted) && apiName === wanted;
        });
        const selected = exact.length ? exact : found.slice(0, 2);
        priorityItems.push(...selected);
        console.log("[sync-football-data] priority team fetched", {teamName, fetched: found.length, selected: selected.length});
      }
      const priorityRows = dedupeRows("teams", priorityItems.map(item => teamRowFromApi(item, countryLookup)).filter(row => row.api_id && row.name), apiIdKey);
      const limitedPriorityRows = priorityRows.slice(0, teamsTotalLimit);
      const upsertedPriority = await upsert("teams", limitedPriorityRows);
      counts.teams = Number(counts.teams) + upsertedPriority;
      teamCandidates += priorityItems.length;
      teamUpserted += upsertedPriority;
      console.log("[sync-football-data] priority teams done", {
        fetched: priorityItems.length,
        deduped: priorityRows.length,
        upserted: upsertedPriority,
        teamsTotalLimit,
      });
    }
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
      teamCandidates += teams.length;
      const teamRows = dedupeRows("teams", teams.map(item => teamRowFromApi(item, countryLookup)).filter(row => row.api_id && row.name), apiIdKey);
      const remaining = Math.max(0, teamsTotalLimit - Number(counts.teams));
      const limitedTeamRows = teamRows.slice(0, remaining);
      const linkedCountries = limitedTeamRows.filter(row => row.country_id).length;
      console.log("[sync-football-data] teams prepared", {
        leagueId,
        season,
        fetched: teams.length,
        deduped: teamRows.length,
        limited: limitedTeamRows.length,
        linkedCountries,
        teamsTotalLimit,
      });
      const upserted = await upsert("teams", limitedTeamRows);
      counts.teams = Number(counts.teams) + upserted;
      teamUpserted += upserted;
      console.log("[sync-football-data] teams upserted cumulative", {teams: counts.teams, teamCandidates, teamUpserted, teamsTotalLimit, leaguesScanned: competitionTargets.indexOf(target) + 1});
    }
    console.log("[sync-football-data] teams step done", {
      teamsTotalLimit,
      leaguesScanned: competitionTargets.length,
      teamCandidates,
      teamUpserted,
      reportedTeams: counts.teams,
    });

    const teamMap = await readIdMap("teams");
    const syncSeason = String(Deno.env.get("FOOTBALL_SYNC_SEASON") ?? currentFootballSeason());

    if (INCLUDE_PLAYERS) {
      console.log("[sync-football-data] step players start");
      const playerTeamsLimit = Number(Deno.env.get("FOOTBALL_SYNC_PLAYER_TEAMS_LIMIT") ?? String(DEFAULT_PLAYER_TEAMS_LIMIT));
      const completeRosterSize = Number(Deno.env.get("FOOTBALL_SYNC_COMPLETE_ROSTER_SIZE") ?? String(DEFAULT_COMPLETE_ROSTER_SIZE));
      const rosterCounts = await readTeamPlayerCounts();
      const {targets: playerTeamTargets, skippedComplete} = await readTeamTargets(playerTeamsLimit, {rosterCounts, completeRosterSize, skipComplete: true});
      let playerTeamsVisited = 0;
      let playersFound = 0;
      let teamPlayersUpserted = 0;
      let relationCandidates = 0;
      let missingPlayerLinks = 0;
      let apiErrors = 0;
      let priorityTeamsProcessed = 0;
      let priorityNationsProcessed = 0;
      let clubsProcessed = 0;
      let nationsProcessed = 0;
      let nationsWithoutSquad = 0;
      const teamLogs: Json[] = [];
      console.log("[sync-football-data] players limits", {playerTeamsLimit, teamsToVisit: playerTeamTargets.length, completeRosterSize, skippedComplete: skippedComplete.length});
      for (const teamTarget of playerTeamTargets) {
        playerTeamsVisited += 1;
        if (teamTarget.priority) priorityTeamsProcessed += 1;
        if (teamTarget.type === "nation") {
          nationsProcessed += 1;
          if (teamTarget.priority) priorityNationsProcessed += 1;
        } else {
          clubsProcessed += 1;
        }
        console.log("[sync-football-data] fetch squad", {teamApiId: teamTarget.api_id, teamName: teamTarget.name, teamType: teamTarget.type, priority: teamTarget.priority, linkedPlayers: teamTarget.linkedPlayers});
        let squad: Json[] = [];
        let fallbackPlayers: Json[] = [];
        try {
          squad = await football("players/squads", {team: teamTarget.api_id});
        } catch (error) {
          apiErrors += 1;
          console.error("[sync-football-data] squad fetch failed", {teamApiId: teamTarget.api_id, teamName: teamTarget.name, message: error instanceof Error ? error.message : String(error)});
        }
        let players = squad.flatMap(item => asArray((item as Json).players));
        if (players.length < 18) {
          try {
            console.log("[sync-football-data] fetch players fallback", {teamApiId: teamTarget.api_id, teamName: teamTarget.name, reason: "squad below 18", squadPlayers: players.length, season: syncSeason});
            fallbackPlayers = await football("players", {team: teamTarget.api_id, season: syncSeason});
            players = [...players, ...fallbackPlayers];
          } catch (error) {
            apiErrors += 1;
            console.error("[sync-football-data] players fallback failed", {teamApiId: teamTarget.api_id, teamName: teamTarget.name, message: error instanceof Error ? error.message : String(error)});
          }
        }
        const normalizedPlayers = dedupeRows("players_normalized", players.map(item => normalizePlayerItem(item, countryLookup)).filter(row => row.api_id && row.name), apiIdKey);
        if (teamTarget.type === "nation" && !normalizedPlayers.length) nationsWithoutSquad += 1;
        playersFound += players.length;
        const positionsDetected = Array.from(new Set(normalizedPlayers.map(item => String(item.position ?? "")).filter(Boolean))).sort();
        console.log("[sync-football-data] squad fetched", {teamApiId: teamTarget.api_id, squadRows: squad.length, squadPlayers: players.length - fallbackPlayers.length, fallbackPlayers: fallbackPlayers.length, normalizedPlayers: normalizedPlayers.length, positionsDetected});
        const playerRows = normalizedPlayers.map(item => ({
          api_id: item.api_id,
          name: item.name,
          firstname: item.firstname,
          lastname: item.lastname,
          birth_date: item.birth_date,
          nationality: item.nationality,
          country_id: item.country_id,
          position: item.position,
          photo_url: item.photo_url,
          is_active: true,
          raw_data: item.raw_data,
          updated_at: new Date().toISOString(),
        }));
        console.log("[sync-football-data] players prepared", {teamApiId: teamTarget.api_id, fetched: players.length, deduped: playerRows.length});
        counts.players = Number(counts.players) + await upsert("players", playerRows);

        const playerApiIds = normalizedPlayers.map(item => String(item.api_id)).filter(Boolean);
        const playerMap = await readIdMapForApiIds("players", playerApiIds);
        const teamPlayerCandidates = normalizedPlayers.map(item => {
          const playerApiId = String(item.api_id);
          const playerId = playerMap.get(playerApiId);
          return {
            api_id: `${teamTarget.api_id}:${playerApiId}:${syncSeason}`,
            team_id: teamTarget.id,
            player_id: playerId,
            season: syncSeason,
            shirt_number: item.shirt_number,
            position: String(item.position ?? ""),
            is_active: true,
            raw_data: item.raw_data,
            updated_at: new Date().toISOString(),
          };
        });
        const missingForTeam = teamPlayerCandidates.filter(row => !row.player_id).length;
        const validCandidates = teamPlayerCandidates.filter(row => row.team_id && row.player_id);
        relationCandidates += teamPlayerCandidates.length;
        missingPlayerLinks += missingForTeam;
        console.log("[sync-football-data] team_players prepared", {
          teamName: teamTarget.name,
          teamId: teamTarget.id,
          teamApiId: teamTarget.api_id,
          teamType: teamTarget.type,
          priority: teamTarget.priority,
          playersFoundForTeam: players.length,
          normalizedPlayers: normalizedPlayers.length,
          playerRowsUpserted: playerRows.length,
          playerIdsResolved: playerMap.size,
          relationCandidates: teamPlayerCandidates.length,
          validRelations: validCandidates.length,
          missingPlayerIds: missingForTeam,
          positionsDetected,
        });
        const teamPlayerRows = dedupeRows("team_players", validCandidates, row => apiIdKey(row) || `${row.team_id ?? ""}:${row.player_id ?? ""}:${row.season ?? ""}`);
        const upsertedTeamPlayers = await upsert("team_players", teamPlayerRows, "api_id");
        teamPlayersUpserted += upsertedTeamPlayers;
        counts.team_players_upserted = teamPlayersUpserted;
        teamLogs.push({
          name: teamTarget.name,
          requested_name: teamTarget.priorityAlias || teamTarget.name,
          api_alias_used: teamTarget.name,
          api_football_id: teamTarget.api_id,
          supabase_team_id: teamTarget.id,
          type: teamTarget.type,
          priority: teamTarget.priority,
          linked_before: teamTarget.linkedPlayers,
          players_found: players.length,
          normalized_players: normalizedPlayers.length,
          relation_candidates: teamPlayerCandidates.length,
          relations_upserted: upsertedTeamPlayers,
          missing_player_ids: missingForTeam,
          positions: positionsDetected,
        });
        console.log("[sync-football-data] players cumulative", {
          players: counts.players,
          team_players_upserted: teamPlayersUpserted,
          teamsVisited: playerTeamsVisited,
          playersFound,
          relationCandidates,
          missingPlayerLinks,
          deletedRelations: 0,
        });
      }
      counts.player_teams_visited = playerTeamsVisited;
      counts.players_found = playersFound;
      counts.team_player_relation_candidates = relationCandidates;
      counts.team_player_missing_player_ids = missingPlayerLinks;
      counts.roster_priority_teams_processed = priorityTeamsProcessed;
      counts.roster_priority_nations_processed = priorityNationsProcessed;
      counts.roster_clubs_processed = clubsProcessed;
      counts.roster_nations_processed = nationsProcessed;
      counts.roster_teams_skipped_complete = skippedComplete.length;
      counts.roster_priority_nations_skipped_complete = skippedComplete.filter(row => row.type === "nation" && row.priority).length;
      counts.roster_nations_without_squad = nationsWithoutSquad;
      counts.roster_team_logs = teamLogs;
      counts.api_errors = apiErrors;
      counts.players_total = await tableCount("players");
      counts.team_players = await tableCount("team_players");
      console.log("[sync-football-data] players step done", {
        teamsVisited: playerTeamsVisited,
        priorityTeamsProcessed,
        priorityNationsProcessed,
        clubsProcessed,
        nationsProcessed,
        nationsWithoutSquad,
        skippedComplete: skippedComplete.length,
        playersFound,
        teamPlayersUpserted,
        relationCandidates,
        missingPlayerLinks,
        apiErrors,
        teamLogs,
        playersTotal: counts.players_total,
        teamPlayersTotal: counts.team_players,
        deletedRelations: 0,
      });
    } else {
      console.log("[sync-football-data] players skipped", {reason: "FOOTBALL_SYNC_INCLUDE_PLAYERS is not true"});
      counts.players_total = await tableCount("players");
      counts.team_players = await tableCount("team_players");
      console.log("[sync-football-data] team_players retained", {playersTotal: counts.players_total, teamPlayersTotal: counts.team_players, deletedRelations: 0});
    }

    if (INCLUDE_COACHES) {
      console.log("[sync-football-data] step coaches start");
      const coachTeamsLimit = Number(Deno.env.get("FOOTBALL_SYNC_COACH_TEAMS_LIMIT") ?? String(DEFAULT_COACH_TEAMS_LIMIT));
      const {targets: coachTeamTargets} = await readTeamTargets(coachTeamsLimit);
      let coachTeamsVisited = 0;
      for (const teamTarget of coachTeamTargets) {
        coachTeamsVisited += 1;
        console.log("[sync-football-data] fetch coaches", {teamApiId: teamTarget.api_id, teamName: teamTarget.name});
        const coaches = await football("coachs", {team: teamTarget.api_id});
        console.log("[sync-football-data] coaches fetched", {teamApiId: teamTarget.api_id, count: coaches.length});
        const coachRows = dedupeRows("coaches", coaches.map(item => ({
          api_id: String(pick(item, ["id"], "")),
          name: String(pick(item, ["name"], "Information non disponible")),
          firstname: String(pick(item, ["firstname"], "")),
          lastname: String(pick(item, ["lastname"], "")),
          birth_date: pick(item, ["birth.date"], null),
          nationality: String(pick(item, ["nationality"], "")),
          country_id: countryIdForName(countryLookup, pick(item, ["nationality"], "")),
          photo_url: String(pick(item, ["photo"], "")),
          is_active: true,
          raw_data: item,
          updated_at: new Date().toISOString(),
        })).filter(row => row.api_id && row.name), apiIdKey);
        console.log("[sync-football-data] coaches prepared", {teamApiId: teamTarget.api_id, fetched: coaches.length, deduped: coachRows.length});
        counts.coaches = Number(counts.coaches) + await upsert("coaches", coachRows);

        const coachApiIds = coaches.map(item => String(pick(item, ["id"], ""))).filter(Boolean);
        const coachMap = await readIdMapForApiIds("coaches", coachApiIds);
        const teamCoachRows = dedupeRows("team_coaches", coaches.map(item => ({
          api_id: `${teamTarget.api_id}:${pick(item, ["id"], "")}:${syncSeason}`,
          team_id: teamTarget.id,
          coach_id: coachMap.get(String(pick(item, ["id"], ""))),
          season: syncSeason,
          role: "head_coach",
          is_active: true,
          raw_data: item,
          updated_at: new Date().toISOString(),
        })).filter(row => row.team_id && row.coach_id), row => apiIdKey(row) || `${row.team_id ?? ""}:${row.coach_id ?? ""}:${row.season ?? ""}:${row.role ?? ""}`);
        counts.team_coaches = Number(counts.team_coaches) + await upsert("team_coaches", teamCoachRows, "api_id");
        console.log("[sync-football-data] coaches cumulative", {coaches: counts.coaches, team_coaches: counts.team_coaches});
      }
      counts.coach_teams_visited = coachTeamsVisited;
      counts.coaches_total = await tableCount("coaches");
      counts.team_coaches_total = await tableCount("team_coaches");
      console.log("[sync-football-data] coaches step done", {coachesTotal: counts.coaches_total, teamCoachesTotal: counts.team_coaches_total});
    } else {
      console.log("[sync-football-data] coaches skipped", {reason: "FOOTBALL_SYNC_INCLUDE_COACHES is not true"});
      counts.coaches_total = await tableCount("coaches");
      counts.team_coaches_total = await tableCount("team_coaches");
    }

    if (!INCLUDE_MATCHES) {
      console.log("[sync-football-data] matches skipped", {reason: "FOOTBALL_SYNC_INCLUDE_MATCHES is not true"});
      await finishLog(logId, "success", "Synchronisation football terminée. Matchs ignorés en mode petit volume.", counts);
      return response({ok: true, counts, skipped: {matches: true}});
    }

    console.log("[sync-football-data] step matches start");
    const matchesTotalLimit = Number(Deno.env.get("FOOTBALL_SYNC_MATCHES_TOTAL_LIMIT") ?? String(DEFAULT_MATCHES_TOTAL_LIMIT));
    console.log("[sync-football-data] matches limit", {matchesTotalLimit});
    for (const target of competitionTargets) {
      const leagueId = target.api_id;
      const season = target.season || syncSeason;
      if (Number(counts.matches) >= matchesTotalLimit) {
        console.log("[sync-football-data] matches total limit reached before league", {matches: counts.matches, matchesTotalLimit});
        break;
      }
      console.log("[sync-football-data] fetch fixtures", {leagueId, season, competitionName: target.name});
      const fixtures = await football("fixtures", {league: leagueId, season});
      console.log("[sync-football-data] fixtures fetched", {leagueId, season, count: fixtures.length});
      const matchRows = dedupeRows("matches", fixtures.map(item => {
        const fixture = pick<Json>(item, ["fixture"], {});
        const teams = pick<Json>(item, ["teams"], {});
        const goals = pick<Json>(item, ["goals"], {});
        const home = pick<Json>(teams, ["home"], {});
        const away = pick<Json>(teams, ["away"], {});
        return {
          api_id: String(pick(fixture, ["id"], "")),
          competition_id: competitionMap.get(leagueId) ?? null,
          season,
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
        season,
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
