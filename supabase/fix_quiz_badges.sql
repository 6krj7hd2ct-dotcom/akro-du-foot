-- Nettoyage ciblé des anciens badges Quiz incohérents.
-- Ne supprime aucun profil et ne touche pas aux pronostics.
-- Le niveau Quiz affiché doit venir des thèmes validés dans quiz_results.

with levels(ord, difficulty, badge_key, badge_name) as (
  values
    (0, 'amateur', 'quiz_amateur', 'Quiz Amateur'),
    (1, 'pro', 'quiz_pro', 'Quiz Pro'),
    (2, 'expert', 'quiz_expert', 'Quiz Expert'),
    (3, 'legende', 'quiz_legende', 'Quiz Légende'),
    (4, 'crack', 'quiz_crack', 'Quiz Crack'),
    (5, 'consultant', 'quiz_consultant', 'Quiz Consultant'),
    (6, 'coach', 'quiz_coach', 'Quiz Coach')
),
themes(theme_type) as (
  values
    ('general'),
    ('club'),
    ('nation'),
    ('worldcup'),
    ('euro'),
    ('champions')
),
passed as (
  select distinct profile_id, difficulty, theme_type
  from public.quiz_results
  where profile_id is not null
    and (score >= 7 or passed is true)
),
profiles_with_quiz_progress as (
  select distinct profile_id
  from passed
),
unlocked as (
  select p.profile_id, max(l.ord) as ord
  from profiles_with_quiz_progress p
  cross join levels l
  where not exists (
    select 1
    from levels previous_level
    where previous_level.ord < l.ord
      and exists (
        select 1
        from themes required_theme
        where not exists (
          select 1
          from passed done
          where done.profile_id = p.profile_id
            and done.difficulty = previous_level.difficulty
            and done.theme_type = required_theme.theme_type
        )
      )
  )
  group by p.profile_id
),
deleted as (
  delete from public.profile_badges
  where badge_key like 'quiz_%'
     or badge_name ilike 'Quiz %'
  returning profile_id
)
insert into public.profile_badges (profile_id, badge_key, badge_name, unlocked_at)
select u.profile_id, l.badge_key, l.badge_name, now()
from unlocked u
join levels l on l.ord = u.ord
on conflict (profile_id, badge_key)
do update set badge_name = excluded.badge_name;
