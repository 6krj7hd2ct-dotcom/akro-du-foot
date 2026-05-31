-- Akro du Foot - articles automatiques de matchs.
-- Migration non destructive : crée uniquement la table si elle n'existe pas,
-- puis ajoute les contraintes/index nécessaires.

create table if not exists public.match_articles (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null references public.matches(id) on delete cascade,
  match_api_id text,
  slug text not null,
  title text not null,
  summary text,
  content text,
  competition text,
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  constraint match_articles_status_check check (status in ('draft', 'published')),
  constraint match_articles_match_id_key unique (match_id)
);

create unique index if not exists match_articles_slug_idx
  on public.match_articles(slug);

create index if not exists match_articles_status_published_at_idx
  on public.match_articles(status, published_at desc);

drop trigger if exists set_match_articles_updated_at on public.match_articles;

create trigger set_match_articles_updated_at
before update on public.match_articles
for each row execute function public.set_updated_at();

alter table public.match_articles enable row level security;

drop policy if exists "match_articles_public_read_published" on public.match_articles;

create policy "match_articles_public_read_published"
on public.match_articles for select
to anon, authenticated
using (status = 'published');

grant select on public.match_articles to anon, authenticated;
grant all on public.match_articles to service_role;
