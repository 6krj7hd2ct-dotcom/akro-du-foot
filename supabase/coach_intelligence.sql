-- Akro du Foot - Coach intelligence V1.
-- Migration additive et non destructive.
-- Objectif : stocker les statistiques récupérées à la demande par le Coach
-- sans modifier les tables football existantes.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.coach_player_season_stats (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  player_id uuid references public.players(id) on delete cascade,
  player_api_id text,
  player_name text not null,
  team_id uuid references public.teams(id) on delete set null,
  team_api_id text,
  team_name text,
  competition_id uuid references public.competitions(id) on delete set null,
  league_api_id text,
  league_name text,
  season text not null,
  appearances int,
  lineups int,
  minutes int,
  goals int,
  assists int,
  yellow_cards int,
  red_cards int,
  rating numeric,
  raw_data jsonb not null default '{}'::jsonb,
  source text not null default 'api-football',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.coach_api_cache (
  id uuid primary key default gen_random_uuid(),
  cache_key text not null unique,
  endpoint text not null,
  params jsonb not null default '{}'::jsonb,
  response jsonb not null default '{}'::jsonb,
  source text not null default 'api-football',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_coach_player_stats_player_name
  on public.coach_player_season_stats(player_name);

create index if not exists idx_coach_player_stats_player_api_season
  on public.coach_player_season_stats(player_api_id, season);

create index if not exists idx_coach_player_stats_season
  on public.coach_player_season_stats(season);

create index if not exists idx_coach_api_cache_key
  on public.coach_api_cache(cache_key);

drop trigger if exists set_coach_player_season_stats_updated_at on public.coach_player_season_stats;
create trigger set_coach_player_season_stats_updated_at
before update on public.coach_player_season_stats
for each row execute function public.set_updated_at();

drop trigger if exists set_coach_api_cache_updated_at on public.coach_api_cache;
create trigger set_coach_api_cache_updated_at
before update on public.coach_api_cache
for each row execute function public.set_updated_at();

alter table public.coach_player_season_stats enable row level security;
alter table public.coach_api_cache enable row level security;

drop policy if exists "coach_player_stats_public_read" on public.coach_player_season_stats;
create policy "coach_player_stats_public_read"
on public.coach_player_season_stats for select
to anon, authenticated
using (true);

grant select on public.coach_player_season_stats to anon, authenticated;
grant all on public.coach_player_season_stats, public.coach_api_cache to service_role;
