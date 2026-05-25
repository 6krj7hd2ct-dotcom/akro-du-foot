-- Reset ciblé des pronostics + correction robuste du schéma predictions.
-- Compatible si public.predictions.user_id existe encore OU a déjà été supprimé.
-- Ne supprime pas les profils, badges, quiz_results ni progressions de jeux.

-- 1) Diagnostic colonnes actuelles de public.predictions.
select
  column_name,
  data_type,
  is_nullable,
  column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'predictions'
order by ordinal_position;

-- 2) Diagnostic FK actuelles de public.predictions.
select
  con.conname as constraint_name,
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
where src_ns.nspname = 'public'
  and src.relname = 'predictions'
  and con.contype = 'f'
order by con.conname;

-- 3) Vider uniquement les pronostics.
delete from public.predictions;

-- 4) Remettre seulement les stats pronostics à zéro.
do $$
begin
  if to_regclass('public.profile_stats') is not null then
    update public.profile_stats
    set total_predictions = 0,
        correct_scores = 0,
        correct_results = 0,
        total_points = 0,
        rank = null,
        updated_at = now();
  end if;
end $$;

-- 5) Garantir profile_id comme colonne canonique.
alter table public.predictions
  add column if not exists profile_id uuid;

-- 6) Si user_id existe encore, migrer sa valeur vers profile_id puis le rendre passif.
-- Aucune référence statique à user_id : tout est dynamique après vérification.
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'predictions'
      and column_name = 'user_id'
  ) then
    execute '
      update public.predictions p
      set profile_id = p.user_id
      where p.profile_id is null
        and p.user_id is not null
        and exists (select 1 from public.profiles pr where pr.id = p.user_id)
    ';

    execute 'alter table public.predictions alter column user_id drop not null';
    execute 'alter table public.predictions alter column user_id drop default';
  end if;
end $$;

-- 7) Supprimer les anciennes contraintes/index/colonnes liés à user_id s'ils existent.
alter table public.predictions
  drop constraint if exists predictions_user_id_fkey;

drop index if exists predictions_user_match_key;
drop index if exists idx_predictions_user_created;

alter table public.predictions
  drop column if exists user_id;

-- 8) Recréer proprement la relation canonique profile_id -> profiles.id.
alter table public.predictions
  drop constraint if exists predictions_profile_id_fkey;

alter table public.predictions
  add constraint predictions_profile_id_fkey
  foreign key (profile_id) references public.profiles(id)
  on delete cascade;

-- 9) Index utiles sur le schéma actuel.
create unique index if not exists predictions_profile_match_key
  on public.predictions (profile_id, match_id);

create index if not exists idx_predictions_profile_created
  on public.predictions (profile_id, created_at desc);

-- 10) Vérifier que l'ancienne FK cassée n'existe plus.
do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'predictions_user_id_fkey'
      and conrelid = 'public.predictions'::regclass
  ) then
    raise exception 'Correction incomplète : predictions_user_id_fkey existe encore.';
  end if;
end $$;

-- 11) Test réel d'insert pronostic avec profile_id uniquement.
-- Le test utilise le premier profil existant, insère PSG 3-1 Arsenal, puis supprime cette ligne test.
do $$
declare
  test_profile record;
  test_match_id text := 'test:psg-arsenal:' || floor(extract(epoch from clock_timestamp()) * 1000)::bigint::text;
  has_pseudo boolean := false;
begin
  select id, coalesce(nullif(pseudo, ''), 'Utilisateur') as pseudo
  into test_profile
  from public.profiles
  limit 1;

  if test_profile.id is null then
    raise notice 'Test insert ignoré : aucun profil existant dans public.profiles.';
    return;
  end if;

  has_pseudo := exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'predictions'
      and column_name = 'pseudo'
  );

  if has_pseudo then
    execute '
      insert into public.predictions (
        profile_id,
        match_id,
        home_team,
        away_team,
        predicted_home_score,
        predicted_away_score,
        status,
        points,
        pseudo
      )
      values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    '
    using
      test_profile.id,
      test_match_id,
      'Paris Saint-Germain',
      'Arsenal',
      3,
      1,
      'À venir',
      0,
      test_profile.pseudo;
  else
    execute '
      insert into public.predictions (
        profile_id,
        match_id,
        home_team,
        away_team,
        predicted_home_score,
        predicted_away_score,
        status,
        points
      )
      values ($1, $2, $3, $4, $5, $6, $7, $8)
    '
    using
      test_profile.id,
      test_match_id,
      'Paris Saint-Germain',
      'Arsenal',
      3,
      1,
      'À venir',
      0;
  end if;

  delete from public.predictions
  where profile_id = test_profile.id
    and match_id = test_match_id;

  raise notice 'Test insert prediction OK : PSG 3-1 Arsenal avec profile_id=%', test_profile.id;
end $$;

-- 12) Recharger le cache PostgREST/Supabase.
notify pgrst, 'reload schema';
