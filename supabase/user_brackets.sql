create table if not exists public.user_brackets (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  competition text not null,
  season text not null,
  bracket_data jsonb not null default '{}'::jsonb,
  champion text,
  runner_up text,
  likes_count integer not null default 0,
  dislikes_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (profile_id, competition, season)
);

alter table public.user_brackets
  add column if not exists profile_id uuid references public.profiles(id) on delete cascade,
  add column if not exists competition text,
  add column if not exists season text,
  add column if not exists bracket_data jsonb not null default '{}'::jsonb,
  add column if not exists champion text,
  add column if not exists runner_up text,
  add column if not exists likes_count integer not null default 0,
  add column if not exists dislikes_count integer not null default 0,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists user_brackets_profile_competition_season_idx
  on public.user_brackets(profile_id, competition, season);

create index if not exists user_brackets_profile_id_idx
  on public.user_brackets(profile_id);

alter table public.user_brackets enable row level security;

drop policy if exists "user_brackets_select_own" on public.user_brackets;
create policy "user_brackets_select_own"
on public.user_brackets for select
to authenticated
using (auth.uid() = profile_id);

drop policy if exists "user_brackets_insert_own" on public.user_brackets;
create policy "user_brackets_insert_own"
on public.user_brackets for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "user_brackets_update_own" on public.user_brackets;
create policy "user_brackets_update_own"
on public.user_brackets for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

grant select, insert, update on public.user_brackets to authenticated;
