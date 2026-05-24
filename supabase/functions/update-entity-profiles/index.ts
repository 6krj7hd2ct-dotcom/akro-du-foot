import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

type Row = Record<string, unknown>;

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY") ?? "";
const EMBEDDING_MODEL = Deno.env.get("OPENAI_EMBEDDING_MODEL") ?? "text-embedding-3-small";
const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {auth: {persistSession: false}});

function json(payload: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(payload), {status, headers: {"Content-Type": "application/json; charset=utf-8"}});
}

function text(value: unknown) {
  return String(value ?? "").trim();
}

function summaryFor(type: string, row: Row) {
  if (type === "player") return `${text(row.name)} · ${text(row.position) || "poste non renseigné"} · ${text(row.nationality) || "nationalité non renseignée"}`;
  if (type === "coach") return `${text(row.name)} · coach · ${text(row.nationality) || "nationalité non renseignée"}`;
  if (type === "team") return `${text(row.name)} · ${text(row.type) || "équipe"} · ${text(row.code) || ""}`;
  if (type === "competition") return `${text(row.name)} · ${text(row.type) || "compétition"} · saison ${text(row.season) || "non renseignée"}`;
  return text(row.name);
}

function searchableText(type: string, row: Row) {
  const raw = row.raw_data ? JSON.stringify(row.raw_data).slice(0, 3000) : "";
  return [
    `Type : ${type}`,
    `Nom : ${text(row.name)}`,
    `Code : ${text(row.code)}`,
    `Poste : ${text(row.position)}`,
    `Nationalité : ${text(row.nationality)}`,
    `Saison : ${text(row.season)}`,
    `Résumé : ${summaryFor(type, row)}`,
    raw ? `Données brutes utiles : ${raw}` : "",
  ].filter(Boolean).join("\n");
}

async function embedding(input: string) {
  const res = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {"Authorization": `Bearer ${OPENAI_API_KEY}`, "Content-Type": "application/json"},
    body: JSON.stringify({model: EMBEDDING_MODEL, input}),
  });
  if (!res.ok) throw new Error(`OpenAI embeddings ${res.status}`);
  const data = await res.json();
  return data.data?.[0]?.embedding as number[];
}

async function changedRows(table: string, since: string) {
  const {data, error} = await supabase
    .from(table)
    .select("*")
    .gte("updated_at", since)
    .eq("is_active", true)
    .limit(250);
  if (error) throw new Error(`${table}: ${error.message}`);
  return data ?? [];
}

Deno.serve(async req => {
  if (!SUPABASE_URL || !SERVICE_KEY) return json({error: "Supabase service role manquant."}, 500);
  if (!OPENAI_API_KEY) return json({error: "OPENAI_API_KEY manquante."}, 500);
  const body = await req.json().catch(() => ({}));
  const since = text(body.since) || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const targets: Array<[string, string]> = [["player", "players"], ["coach", "coaches"], ["team", "teams"], ["competition", "competitions"]];
  const counts: Record<string, number> = {};
  try {
    for (const [entityType, table] of targets) {
      const rows = await changedRows(table, since);
      counts[entityType] = rows.length;
      for (const row of rows) {
        const searchable_text = searchableText(entityType, row);
        const summary = summaryFor(entityType, row);
        const vector = await embedding(searchable_text);
        const {error} = await supabase.from("entity_profiles").upsert({
          entity_type: entityType,
          entity_id: row.id,
          summary,
          searchable_text,
          embedding: vector,
          updated_at: new Date().toISOString(),
        }, {onConflict: "entity_type,entity_id"});
        if (error) throw new Error(`entity_profiles ${entityType}: ${error.message}`);
      }
    }
    return json({ok: true, since, counts});
  } catch (error) {
    return json({ok: false, error: error instanceof Error ? error.message : String(error), counts}, 500);
  }
});
