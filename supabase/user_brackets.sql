create table if not exists public.user_brackets (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  competition text not null,
  season text not null,
  bracket_data jsonb not null default '{}'::jsonb,
  champion text,
  runner_up text,
  is_published boolean not null default false,
  published_at timestamptz,
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
  add column if not exists is_published boolean not null default false,
  add column if not exists published_at timestamptz,
  add column if not exists likes_count integer not null default 0,
  add column if not exists dislikes_count integer not null default 0,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists user_brackets_profile_competition_season_idx
  on public.user_brackets(profile_id, competition, season);

create index if not exists user_brackets_profile_id_idx
  on public.user_brackets(profile_id);

create index if not exists user_brackets_published_idx
  on public.user_brackets(competition, season, published_at desc)
  where is_published = true;

create table if not exists public.user_bracket_votes (
  id uuid primary key default gen_random_uuid(),
  bracket_id uuid not null references public.user_brackets(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  vote_type text not null check (vote_type in ('like', 'dislike')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (bracket_id, profile_id)
);

alter table public.user_bracket_votes
  add column if not exists bracket_id uuid references public.user_brackets(id) on delete cascade,
  add column if not exists profile_id uuid references public.profiles(id) on delete cascade,
  add column if not exists vote_type text,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table public.user_bracket_votes
  drop constraint if exists user_bracket_votes_vote_type_check;

alter table public.user_bracket_votes
  add constraint user_bracket_votes_vote_type_check check (vote_type in ('like', 'dislike'));

create unique index if not exists user_bracket_votes_bracket_profile_idx
  on public.user_bracket_votes(bracket_id, profile_id);

create index if not exists user_bracket_votes_bracket_id_idx
  on public.user_bracket_votes(bracket_id);

alter table public.user_brackets enable row level security;
alter table public.user_bracket_votes enable row level security;

drop policy if exists "user_brackets_select_own" on public.user_brackets;
create policy "user_brackets_select_own"
on public.user_brackets for select
to authenticated
using (auth.uid() = profile_id or is_published = true);

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

drop policy if exists "user_bracket_votes_select" on public.user_bracket_votes;
create policy "user_bracket_votes_select"
on public.user_bracket_votes for select
to authenticated
using (true);

drop policy if exists "user_bracket_votes_insert_own" on public.user_bracket_votes;
create policy "user_bracket_votes_insert_own"
on public.user_bracket_votes for insert
to authenticated
with check (auth.uid() = profile_id);

drop policy if exists "user_bracket_votes_update_own" on public.user_bracket_votes;
create policy "user_bracket_votes_update_own"
on public.user_bracket_votes for update
to authenticated
using (auth.uid() = profile_id)
with check (auth.uid() = profile_id);

create or replace function public.refresh_user_bracket_vote_counts(target_bracket_id uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.user_brackets
  set
    likes_count = (
      select count(*)::integer
      from public.user_bracket_votes
      where bracket_id = target_bracket_id and vote_type = 'like'
    ),
    dislikes_count = (
      select count(*)::integer
      from public.user_bracket_votes
      where bracket_id = target_bracket_id and vote_type = 'dislike'
    ),
    updated_at = now()
  where id = target_bracket_id;
$$;

create or replace function public.refresh_user_bracket_vote_counts_trigger()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'DELETE' then
    perform public.refresh_user_bracket_vote_counts(old.bracket_id);
    return old;
  end if;

  perform public.refresh_user_bracket_vote_counts(new.bracket_id);

  if tg_op = 'UPDATE' and old.bracket_id is distinct from new.bracket_id then
    perform public.refresh_user_bracket_vote_counts(old.bracket_id);
  end if;

  return new;
end;
$$;

drop trigger if exists user_bracket_votes_refresh_counts on public.user_bracket_votes;
create trigger user_bracket_votes_refresh_counts
after insert or update or delete on public.user_bracket_votes
for each row execute function public.refresh_user_bracket_vote_counts_trigger();

grant select, insert, update on public.user_brackets to authenticated;
grant select, insert, update on public.user_bracket_votes to authenticated;
