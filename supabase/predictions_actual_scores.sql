-- Migration progressive : ajoute les scores réels sans toucher aux pronostics existants.
alter table public.predictions
  add column if not exists actual_home_score int,
  add column if not exists actual_away_score int;

-- Force PostgREST/Supabase à relire le schéma après exécution dans l'éditeur SQL.
notify pgrst, 'reload schema';
