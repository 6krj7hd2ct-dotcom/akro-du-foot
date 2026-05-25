-- Diagnostic : voir exactement où pointe l'ancienne contrainte.
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

-- Correction progressive : conserver user_id si l'ancienne table l'exige,
-- mais le faire pointer vers public.profiles(id), qui est l'id Auth du profil connecté.
alter table public.predictions
  add column if not exists profile_id uuid,
  add column if not exists user_id uuid;

update public.predictions
set profile_id = coalesce(profile_id, user_id),
    user_id = coalesce(user_id, profile_id)
where profile_id is null or user_id is null;

alter table public.predictions
  drop constraint if exists predictions_user_id_fkey;

alter table public.predictions
  add constraint predictions_user_id_fkey
  foreign key (user_id) references public.profiles(id)
  on delete cascade
  not valid;

alter table public.predictions
  drop constraint if exists predictions_profile_id_fkey;

alter table public.predictions
  add constraint predictions_profile_id_fkey
  foreign key (profile_id) references public.profiles(id)
  on delete cascade
  not valid;

create unique index if not exists predictions_profile_match_key
  on public.predictions (profile_id, match_id);

notify pgrst, 'reload schema';
