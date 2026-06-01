-- Akro du Foot - THE GOAT V1.
-- Migration additive et non destructive.

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

create table if not exists public.goat_player_tags (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references public.players(id) on delete cascade,
  player_api_id text,
  player_name text not null,
  tag_type text not null check (tag_type in ('nation', 'club', 'worldcup', 'euro', 'champions', 'position')),
  tag_value text not null,
  source text not null default 'akro',
  confidence numeric,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (player_name, tag_type, tag_value)
);

create table if not exists public.goat_sessions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  position_group text not null,
  context_type text not null,
  context_value text,
  winner_player_name text not null,
  winner_photo_url text not null,
  winner_nationality text,
  winner_club text,
  duel_path jsonb not null default '[]'::jsonb,
  share_card jsonb not null default '{}'::jsonb,
  is_published boolean not null default true,
  agree_count int not null default 0,
  disagree_count int not null default 0,
  other_count int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.goat_votes (
  id uuid primary key default gen_random_uuid(),
  goat_session_id uuid not null references public.goat_sessions(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  vote_type text not null check (vote_type in ('agree', 'disagree', 'other')),
  alternative_player_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (goat_session_id, profile_id)
);

create index if not exists idx_goat_player_tags_lookup
  on public.goat_player_tags(tag_type, tag_value);

create index if not exists idx_goat_sessions_profile
  on public.goat_sessions(profile_id, created_at desc);

create index if not exists idx_goat_sessions_published
  on public.goat_sessions(is_published, created_at desc);

create index if not exists idx_goat_votes_session
  on public.goat_votes(goat_session_id);

drop trigger if exists set_goat_player_tags_updated_at on public.goat_player_tags;
create trigger set_goat_player_tags_updated_at
before update on public.goat_player_tags
for each row execute function public.set_updated_at();

drop trigger if exists set_goat_sessions_updated_at on public.goat_sessions;
create trigger set_goat_sessions_updated_at
before update on public.goat_sessions
for each row execute function public.set_updated_at();

drop trigger if exists set_goat_votes_updated_at on public.goat_votes;
create trigger set_goat_votes_updated_at
before update on public.goat_votes
for each row execute function public.set_updated_at();

create or replace function public.refresh_goat_session_vote_counts()
returns trigger
language plpgsql
security definer
as $$
declare
  target_session uuid;
begin
  target_session := coalesce(new.goat_session_id, old.goat_session_id);
  update public.goat_sessions
  set
    agree_count = (select count(*) from public.goat_votes where goat_session_id = target_session and vote_type = 'agree'),
    disagree_count = (select count(*) from public.goat_votes where goat_session_id = target_session and vote_type = 'disagree'),
    other_count = (select count(*) from public.goat_votes where goat_session_id = target_session and vote_type = 'other'),
    updated_at = now()
  where id = target_session;
  return null;
end;
$$;

drop trigger if exists goat_votes_refresh_counts on public.goat_votes;
create trigger goat_votes_refresh_counts
after insert or update or delete on public.goat_votes
for each row execute function public.refresh_goat_session_vote_counts();

alter table public.goat_player_tags enable row level security;
alter table public.goat_sessions enable row level security;
alter table public.goat_votes enable row level security;

drop policy if exists "goat_player_tags_select" on public.goat_player_tags;
create policy "goat_player_tags_select"
on public.goat_player_tags for select
to anon, authenticated
using (true);

drop policy if exists "goat_sessions_select" on public.goat_sessions;
create policy "goat_sessions_select"
on public.goat_sessions for select
to anon, authenticated
using (is_published = true or auth.uid() = profile_id);

drop policy if exists "goat_sessions_insert_own" on public.goat_sessions;
create policy "goat_sessions_insert_own"
on public.goat_sessions for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "goat_sessions_update_own" on public.goat_sessions;
create policy "goat_sessions_update_own"
on public.goat_sessions for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

drop policy if exists "goat_votes_select" on public.goat_votes;
create policy "goat_votes_select"
on public.goat_votes for select
to anon, authenticated
using (true);

drop policy if exists "goat_votes_insert_own" on public.goat_votes;
create policy "goat_votes_insert_own"
on public.goat_votes for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "goat_votes_update_own" on public.goat_votes;
create policy "goat_votes_update_own"
on public.goat_votes for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

grant select on public.goat_player_tags, public.goat_sessions, public.goat_votes to anon, authenticated;
grant insert, update on public.goat_sessions, public.goat_votes to authenticated;
grant all on public.goat_player_tags, public.goat_sessions, public.goat_votes to service_role;
