-- Reset ciblé des pronostics + correction de l'ancienne FK user_id.
-- Ne supprime pas les profils, badges, quiz_results ni progressions de jeux.

-- 1) Diagnostic : vérifier exactement où pointe predictions_user_id_fkey.
select
  con.conname as constraint_name,
  src_ns.nspname as source_schema,
  src.relname as source_table,
  src_col.attname as source_column,
  ref_ns.nspname as referenced_schema,
  ref.relname as referenced_table,
  ref_col.attname as referenced_column
from pg_constraint con
join pg_class src on src.oid = con.conrelid
join pg_namespace src_ns on src_ns.oid = src.relnamespace
join pg_class ref on ref.oid = con.confrelid
join pg_namespace ref_ns on ref_ns.oid = ref.relnamespace
join unnest(con.conkey) with ordinality as src_key(attnum, ord) on true
join unnest(con.confkey) with ordinality as ref_key(attnum, ord) on ref_key.ord = src_key.ord
join pg_attribute src_col on src_col.attrelid = src.oid and src_col.attnum = src_key.attnum
join pg_attribute ref_col on ref_col.attrelid = ref.oid and ref_col.attnum = ref_key.attnum
where con.conname = 'predictions_user_id_fkey';

-- 2) Vider uniquement les pronostics.
delete from public.predictions;

-- 3) Remettre les stats pronostics à zéro sans toucher aux profils/badges/quiz.
update public.profile_stats
set total_predictions = 0,
    correct_scores = 0,
    correct_results = 0,
    total_points = 0,
    rank = null,
    updated_at = now();

-- 4) Conserver profile_id comme identifiant canonique des pronostics.
alter table public.predictions
  add column if not exists profile_id uuid;

update public.predictions
set profile_id = user_id
where profile_id is null
  and user_id is not null
  and exists (select 1 from public.profiles p where p.id = public.predictions.user_id);

alter table public.predictions
  drop constraint if exists predictions_user_id_fkey;

-- 5) Neutraliser l'ancienne colonne user_id si elle existe encore.
-- Elle ne doit plus bloquer les inserts faits avec profile_id.
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'predictions'
      and column_name = 'user_id'
  ) then
    alter table public.predictions alter column user_id drop not null;
    alter table public.predictions alter column user_id drop default;
  end if;
end $$;

-- 5bis) Si l'ancienne colonne user_id est encore là, elle reste passive :
-- elle ne doit plus participer aux insertions ni aux relations.
drop index if exists predictions_user_match_key;
drop index if exists idx_predictions_user_created;

-- 6) Recréer la FK correcte sur profile_id.
alter table public.predictions
  drop constraint if exists predictions_profile_id_fkey;

alter table public.predictions
  add constraint predictions_profile_id_fkey
  foreign key (profile_id) references public.profiles(id)
  on delete cascade
  not valid;

create unique index if not exists predictions_profile_match_key
  on public.predictions (profile_id, match_id);

create index if not exists idx_predictions_profile_created
  on public.predictions (profile_id, created_at desc);

notify pgrst, 'reload schema';
