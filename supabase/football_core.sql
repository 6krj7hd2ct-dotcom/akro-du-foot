-- Akro du Foot - base football Supabase progressive.
-- Ce script ajoute uniquement les objets manquants. Il ne supprime pas,
-- ne renomme pas et ne vide aucune donnée existante.

create extension if not exists pgcrypto;
create extension if not exists vector;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.countries (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  name text not null,
  code text,
  flag_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.competitions (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  country_id uuid references public.countries(id) on delete set null,
  name text not null,
  type text,
  logo_url text,
  season text,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.teams (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  country_id uuid references public.countries(id) on delete set null,
  name text not null,
  short_name text,
  code text,
  type text not null default 'club',
  logo_url text,
  venue_name text,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.players (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  country_id uuid references public.countries(id) on delete set null,
  name text not null,
  firstname text,
  lastname text,
  birth_date date,
  nationality text,
  position text,
  photo_url text,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.coaches (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  country_id uuid references public.countries(id) on delete set null,
  name text not null,
  firstname text,
  lastname text,
  birth_date date,
  nationality text,
  photo_url text,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.matches (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  competition_id uuid references public.competitions(id) on delete set null,
  season text,
  round text,
  status text,
  match_date timestamptz,
  venue_name text,
  home_team_id uuid references public.teams(id) on delete set null,
  away_team_id uuid references public.teams(id) on delete set null,
  home_score int,
  away_score int,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.team_players (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  team_id uuid not null references public.teams(id) on delete cascade,
  player_id uuid not null references public.players(id) on delete cascade,
  competition_id uuid references public.competitions(id) on delete set null,
  season text,
  shirt_number int,
  position text,
  joined_at date,
  left_at date,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint team_players_unique_membership unique(team_id, player_id, season)
);

create table if not exists public.team_coaches (
  id uuid primary key default gen_random_uuid(),
  api_id text unique,
  team_id uuid not null references public.teams(id) on delete cascade,
  coach_id uuid not null references public.coaches(id) on delete cascade,
  season text,
  role text,
  started_at date,
  ended_at date,
  is_active boolean not null default true,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint team_coaches_unique_membership unique(team_id, coach_id, season, role)
);

create table if not exists public.entity_profiles (
  id uuid primary key default gen_random_uuid(),
  entity_type text not null,
  entity_id uuid not null,
  summary text,
  searchable_text text,
  embedding vector(1536),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint entity_profiles_entity_key unique(entity_type, entity_id)
);

create table if not exists public.sync_logs (
  id uuid primary key default gen_random_uuid(),
  job_name text not null,
  status text not null default 'running' check (status in ('running', 'success', 'error', 'cancelled')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  message text,
  processed_counts jsonb not null default '{}'::jsonb,
  error_detail text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.sync_logs add column if not exists cancel_requested boolean not null default false;
alter table public.sync_logs add column if not exists cancelled_at timestamptz;
alter table public.sync_logs drop constraint if exists sync_logs_status_check;
alter table public.sync_logs add constraint sync_logs_status_check check (status in ('running', 'success', 'error', 'cancelled'));

create unique index if not exists countries_api_id_key on public.countries(api_id) where api_id is not null;
create unique index if not exists teams_api_id_key on public.teams(api_id) where api_id is not null;
create unique index if not exists players_api_id_key on public.players(api_id) where api_id is not null;
create unique index if not exists coaches_api_id_key on public.coaches(api_id) where api_id is not null;
create unique index if not exists competitions_api_id_key on public.competitions(api_id) where api_id is not null;
create unique index if not exists matches_api_id_key on public.matches(api_id) where api_id is not null;
create unique index if not exists team_players_api_id_key on public.team_players(api_id) where api_id is not null;
create unique index if not exists team_coaches_api_id_key on public.team_coaches(api_id) where api_id is not null;

create index if not exists idx_teams_api_id on public.teams(api_id);
create index if not exists idx_players_api_id on public.players(api_id);
create index if not exists idx_coaches_api_id on public.coaches(api_id);
create index if not exists idx_competitions_api_id on public.competitions(api_id);
create index if not exists idx_matches_api_id on public.matches(api_id);
create index if not exists idx_team_players_team_id on public.team_players(team_id);
create index if not exists idx_team_players_player_id on public.team_players(player_id);
create index if not exists idx_team_coaches_team_id on public.team_coaches(team_id);
create index if not exists idx_team_coaches_coach_id on public.team_coaches(coach_id);
create index if not exists idx_matches_competition_id on public.matches(competition_id);
create index if not exists idx_matches_match_date on public.matches(match_date desc);
create index if not exists idx_entity_profiles_entity on public.entity_profiles(entity_type, entity_id);
create index if not exists idx_sync_logs_job_started on public.sync_logs(job_name, started_at desc);

do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname = 'public' and indexname = 'idx_entity_profiles_embedding'
  ) then
    execute 'create index idx_entity_profiles_embedding on public.entity_profiles using ivfflat (embedding vector_cosine_ops) with (lists = 100)';
  end if;
end $$;

drop trigger if exists set_countries_updated_at on public.countries;
create trigger set_countries_updated_at before update on public.countries for each row execute function public.set_updated_at();
drop trigger if exists set_teams_updated_at on public.teams;
create trigger set_teams_updated_at before update on public.teams for each row execute function public.set_updated_at();
drop trigger if exists set_players_updated_at on public.players;
create trigger set_players_updated_at before update on public.players for each row execute function public.set_updated_at();
drop trigger if exists set_coaches_updated_at on public.coaches;
create trigger set_coaches_updated_at before update on public.coaches for each row execute function public.set_updated_at();
drop trigger if exists set_competitions_updated_at on public.competitions;
create trigger set_competitions_updated_at before update on public.competitions for each row execute function public.set_updated_at();
drop trigger if exists set_matches_updated_at on public.matches;
create trigger set_matches_updated_at before update on public.matches for each row execute function public.set_updated_at();
drop trigger if exists set_team_players_updated_at on public.team_players;
create trigger set_team_players_updated_at before update on public.team_players for each row execute function public.set_updated_at();
drop trigger if exists set_team_coaches_updated_at on public.team_coaches;
create trigger set_team_coaches_updated_at before update on public.team_coaches for each row execute function public.set_updated_at();
drop trigger if exists set_entity_profiles_updated_at on public.entity_profiles;
create trigger set_entity_profiles_updated_at before update on public.entity_profiles for each row execute function public.set_updated_at();
drop trigger if exists set_sync_logs_updated_at on public.sync_logs;
create trigger set_sync_logs_updated_at before update on public.sync_logs for each row execute function public.set_updated_at();

create or replace function public.match_entity_profiles(
  query_embedding vector(1536),
  match_count int default 8,
  entity_type_filter text default null
)
returns table (
  id uuid,
  entity_type text,
  entity_id uuid,
  summary text,
  searchable_text text,
  similarity float
)
language sql
stable
as $$
  select
    ep.id,
    ep.entity_type,
    ep.entity_id,
    ep.summary,
    ep.searchable_text,
    1 - (ep.embedding <=> query_embedding) as similarity
  from public.entity_profiles ep
  where ep.embedding is not null
    and (entity_type_filter is null or ep.entity_type = entity_type_filter)
  order by ep.embedding <=> query_embedding
  limit greatest(1, least(match_count, 30));
$$;

grant usage on schema public to anon, authenticated, service_role;
grant select on public.countries, public.teams, public.players, public.coaches, public.competitions, public.matches, public.team_players, public.team_coaches, public.entity_profiles to anon, authenticated;
grant select on public.sync_logs to authenticated;
grant all on public.countries, public.teams, public.players, public.coaches, public.competitions, public.matches, public.team_players, public.team_coaches, public.entity_profiles, public.sync_logs to service_role;
grant execute on all functions in schema public to service_role;

alter table public.countries enable row level security;
alter table public.teams enable row level security;
alter table public.players enable row level security;
alter table public.coaches enable row level security;
alter table public.competitions enable row level security;
alter table public.matches enable row level security;
alter table public.team_players enable row level security;
alter table public.team_coaches enable row level security;
alter table public.entity_profiles enable row level security;
alter table public.sync_logs enable row level security;

drop policy if exists "football_public_read_countries" on public.countries;
create policy "football_public_read_countries" on public.countries for select to anon, authenticated using (true);
drop policy if exists "football_public_read_teams" on public.teams;
create policy "football_public_read_teams" on public.teams for select to anon, authenticated using (true);
drop policy if exists "football_public_read_players" on public.players;
create policy "football_public_read_players" on public.players for select to anon, authenticated using (true);
drop policy if exists "football_public_read_coaches" on public.coaches;
create policy "football_public_read_coaches" on public.coaches for select to anon, authenticated using (true);
drop policy if exists "football_public_read_competitions" on public.competitions;
create policy "football_public_read_competitions" on public.competitions for select to anon, authenticated using (true);
drop policy if exists "football_public_read_matches" on public.matches;
create policy "football_public_read_matches" on public.matches for select to anon, authenticated using (true);
drop policy if exists "football_public_read_team_players" on public.team_players;
create policy "football_public_read_team_players" on public.team_players for select to anon, authenticated using (true);
drop policy if exists "football_public_read_team_coaches" on public.team_coaches;
create policy "football_public_read_team_coaches" on public.team_coaches for select to anon, authenticated using (true);
drop policy if exists "football_public_read_entity_profiles" on public.entity_profiles;
create policy "football_public_read_entity_profiles" on public.entity_profiles for select to anon, authenticated using (true);
drop policy if exists "sync_logs_authenticated_read" on public.sync_logs;
create policy "sync_logs_authenticated_read" on public.sync_logs for select to authenticated using (true);
