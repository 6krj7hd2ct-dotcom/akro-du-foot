import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY") ?? "";
const EMBEDDING_MODEL = Deno.env.get("OPENAI_EMBEDDING_MODEL") ?? "text-embedding-3-small";
const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {auth: {persistSession: false}});

function json(payload: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(payload), {status, headers: {"Content-Type": "application/json; charset=utf-8"}});
}

async function questionEmbedding(question: string) {
  const res = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {"Authorization": `Bearer ${OPENAI_API_KEY}`, "Content-Type": "application/json"},
    body: JSON.stringify({model: EMBEDDING_MODEL, input: question}),
  });
  if (!res.ok) throw new Error(`OpenAI embeddings ${res.status}`);
  const data = await res.json();
  return data.data?.[0]?.embedding as number[];
}

Deno.serve(async req => {
  if (!SUPABASE_URL || !SERVICE_KEY) return json({error: "Supabase service role manquant."}, 500);
  if (!OPENAI_API_KEY) return json({error: "OPENAI_API_KEY manquante."}, 500);
  const body = await req.json().catch(() => ({}));
  const question = String(body.question ?? "").trim();
  const matchCount = Math.min(Math.max(Number(body.match_count ?? 8), 1), 20);
  const entityType = String(body.entity_type ?? "").trim() || null;
  if (!question) return json({error: "Question vide."}, 400);
  try {
    const embedding = await questionEmbedding(question);
    const {data, error} = await supabase.rpc("match_entity_profiles", {
      query_embedding: embedding,
      match_count: matchCount,
      entity_type_filter: entityType,
    });
    if (error) throw new Error(error.message);
    return json({ok: true, results: data ?? []});
  } catch (error) {
    return json({ok: false, error: error instanceof Error ? error.message : String(error)}, 500);
  }
});
