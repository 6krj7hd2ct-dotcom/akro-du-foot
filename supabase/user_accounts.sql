create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  pseudo text not null,
  avatar_url text,
  focus_teams text[] not null default '{}',
  favorite_club text,
  favorite_club_logo text,
  favorite_nation text,
  favorite_nation_flag text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles
  add column if not exists focus_teams text[] not null default '{}';
alter table public.profiles
  add column if not exists favorite_club text,
  add column if not exists favorite_club_logo text,
  add column if not exists favorite_nation text,
  add column if not exists favorite_nation_flag text;

create table if not exists public.predictions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  match_id text not null,
  home_team text not null,
  away_team text not null,
  predicted_home_score int not null,
  predicted_away_score int not null,
  actual_home_score int,
  actual_away_score int,
  status text not null default 'pending',
  points int not null default 0,
  created_at timestamptz not null default now(),
  unique(profile_id, match_id)
);

create table if not exists public.profile_stats (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  total_predictions int not null default 0,
  correct_scores int not null default 0,
  correct_results int not null default 0,
  total_points int not null default 0,
  rank int,
  updated_at timestamptz not null default now(),
  unique(profile_id)
);

create table if not exists public.profile_badges (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  badge_key text not null,
  badge_name text not null,
  unlocked_at timestamptz not null default now(),
  unique(profile_id, badge_key)
);

create index if not exists idx_predictions_profile_created
  on public.predictions (profile_id, created_at desc);

create index if not exists idx_profile_badges_profile_unlocked
  on public.profile_badges (profile_id, unlocked_at asc);

grant usage on schema public to authenticated;
grant select, insert, update on public.profiles to authenticated;
grant select, insert, update on public.predictions to authenticated;
grant select, insert, update on public.profile_stats to authenticated;
grant select, insert, update on public.profile_badges to authenticated;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;
alter table public.predictions enable row level security;
alter table public.profile_stats enable row level security;
alter table public.profile_badges enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
on public.profiles for select
to authenticated
using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
on public.profiles for insert
to authenticated
with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
on public.profiles for update
to authenticated
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "predictions_select_own" on public.predictions;
create policy "predictions_select_own"
on public.predictions for select
to authenticated
using (auth.uid() = profile_id);

drop policy if exists "predictions_insert_own" on public.predictions;
create policy "predictions_insert_own"
on public.predictions for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "predictions_update_own" on public.predictions;
create policy "predictions_update_own"
on public.predictions for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

drop policy if exists "stats_select_own" on public.profile_stats;
create policy "stats_select_own"
on public.profile_stats for select
to authenticated
using (auth.uid() = profile_id);

drop policy if exists "stats_insert_own" on public.profile_stats;
create policy "stats_insert_own"
on public.profile_stats for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "stats_update_own" on public.profile_stats;
create policy "stats_update_own"
on public.profile_stats for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

drop policy if exists "badges_select_own" on public.profile_badges;
create policy "badges_select_own"
on public.profile_badges for select
to authenticated
using (auth.uid() = profile_id);

drop policy if exists "badges_insert_own" on public.profile_badges;
create policy "badges_insert_own"
on public.profile_badges for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "badges_update_own" on public.profile_badges;
create policy "badges_update_own"
on public.profile_badges for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);
