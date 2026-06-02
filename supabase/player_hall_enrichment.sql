-- Akro du Foot - enrichissement joueurs + Hall of Fame.
-- Migration additive, non destructive et relançable.
-- Objectif : créer la mémoire historique durable du Coach / THE GOAT / Top 10 / Quiz.

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

alter table public.players add column if not exists full_name text;
alter table public.players add column if not exists display_name text;
alter table public.players add column if not exists age int;
alter table public.players add column if not exists height text;
alter table public.players add column if not exists current_club text;
alter table public.players add column if not exists current_team_id uuid references public.teams(id) on delete set null;
alter table public.players add column if not exists national_team text;
alter table public.players add column if not exists career_clubs jsonb not null default '[]'::jsonb;
alter table public.players add column if not exists major_titles jsonb not null default '[]'::jsonb;
alter table public.players add column if not exists individual_awards jsonb not null default '[]'::jsonb;
alter table public.players add column if not exists playing_style text;
alter table public.players add column if not exists preferred_foot text;
alter table public.players add column if not exists nickname text;
alter table public.players add column if not exists photo_source text;
alter table public.players add column if not exists last_enriched_at timestamptz;

create index if not exists idx_players_current_team_id on public.players(current_team_id);
create index if not exists idx_players_last_enriched_at on public.players(last_enriched_at desc);
create index if not exists idx_players_display_name on public.players(display_name);

create table if not exists public.hall_of_fame_players (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references public.players(id) on delete set null,
  name text not null,
  display_name text,
  photo_url text,
  nationality text,
  position text,
  era text,
  clubs jsonb not null default '[]'::jsonb,
  national_team text,
  ballon_dor_count int not null default 0,
  ballon_dor_years jsonb not null default '[]'::jsonb,
  world_cup_titles jsonb not null default '[]'::jsonb,
  euro_titles jsonb not null default '[]'::jsonb,
  copa_america_titles jsonb not null default '[]'::jsonb,
  champions_league_titles jsonb not null default '[]'::jsonb,
  fifa_awards jsonb not null default '[]'::jsonb,
  major_records jsonb not null default '[]'::jsonb,
  iconic_moments jsonb not null default '[]'::jsonb,
  nickname text,
  legacy text,
  playing_style text,
  why_legend text,
  goat_score numeric,
  hall_of_fame_tier text,
  source text not null default 'akro',
  last_enriched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists hall_of_fame_players_name_key on public.hall_of_fame_players(name);
create index if not exists idx_hall_of_fame_players_player_id on public.hall_of_fame_players(player_id) where player_id is not null;
create index if not exists idx_hall_of_fame_players_tier_score on public.hall_of_fame_players(hall_of_fame_tier, goat_score desc);
create index if not exists idx_hall_of_fame_players_last_enriched_at on public.hall_of_fame_players(last_enriched_at desc);

drop trigger if exists set_hall_of_fame_players_updated_at on public.hall_of_fame_players;
create trigger set_hall_of_fame_players_updated_at
before update on public.hall_of_fame_players
for each row execute function public.set_updated_at();

create table if not exists public.player_enrichment_logs (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references public.players(id) on delete set null,
  player_name text,
  enrichment_type text not null,
  source text not null default 'akro',
  status text not null default 'success',
  message text,
  created_at timestamptz not null default now(),
  constraint player_enrichment_logs_status_check
    check (status in ('success', 'error', 'skipped', 'pending', 'running'))
);

create index if not exists idx_player_enrichment_logs_player on public.player_enrichment_logs(player_id, created_at desc);
create index if not exists idx_player_enrichment_logs_type_status on public.player_enrichment_logs(enrichment_type, status, created_at desc);

create table if not exists public.goat_player_tags (
  id uuid primary key default gen_random_uuid(),
  player_id uuid references public.players(id) on delete cascade,
  player_api_id text,
  player_name text not null,
  tag_type text not null,
  tag_value text not null,
  source text not null default 'akro',
  confidence numeric,
  raw_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (player_name, tag_type, tag_value)
);

alter table public.goat_player_tags drop constraint if exists goat_player_tags_tag_type_check;
alter table public.goat_player_tags
  add constraint goat_player_tags_tag_type_check
  check (tag_type in ('nation', 'club', 'worldcup', 'euro', 'champions', 'position', 'era'));

create index if not exists idx_goat_player_tags_lookup
  on public.goat_player_tags(tag_type, tag_value);

alter table public.goat_player_tags enable row level security;
drop policy if exists "goat_player_tags_select" on public.goat_player_tags;
create policy "goat_player_tags_select"
on public.goat_player_tags for select
to anon, authenticated
using (true);

alter table public.hall_of_fame_players enable row level security;
alter table public.player_enrichment_logs enable row level security;

drop policy if exists "hall_of_fame_players_public_read" on public.hall_of_fame_players;
create policy "hall_of_fame_players_public_read"
on public.hall_of_fame_players for select
to anon, authenticated
using (true);

drop policy if exists "player_enrichment_logs_service_only" on public.player_enrichment_logs;
create policy "player_enrichment_logs_service_only"
on public.player_enrichment_logs for all
to service_role
using (true)
with check (true);

grant select on public.hall_of_fame_players to anon, authenticated;
grant all on public.hall_of_fame_players, public.player_enrichment_logs to service_role;
grant select on public.goat_player_tags to anon, authenticated;
grant all on public.goat_player_tags to service_role;

with seed as (
  select *
  from jsonb_to_recordset($hof$
[
  {"name":"Pelé","display_name":"Pelé","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Pele_con_brasil_%28cropped%29.jpg/500px-Pele_con_brasil_%28cropped%29.jpg","nationality":"Brésil","position":"Attaquant","goat_positions":["attackers"],"era":"années 1950-1970","clubs":["Santos","New York Cosmos"],"national_team":"Brésil","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["1958","1962","1970"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":["Ballon d'Or d'honneur France Football"],"major_records":["Seul joueur triple champion du monde","Icône mondiale du football brésilien"],"iconic_moments":["Coupe du Monde 1958 à 17 ans","Brésil 1970","Ère Santos dominante"],"nickname":"O Rei","legacy":"Figure fondatrice du football moderne, référence historique du buteur créatif et de la domination internationale.","playing_style":"Attaquant complet, finition, jeu aérien, passe, mobilité et sens du spectacle.","why_legend":"Trois Coupes du Monde, un impact culturel mondial et une domination historique avec Santos et le Brésil.","goat_score":99,"hall_of_fame_tier":"S+","contexts":["worldcup"]},
  {"name":"Diego Maradona","display_name":"Diego Maradona","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Maradona-Mundial_86_con_la_copa.JPG/500px-Maradona-Mundial_86_con_la_copa.JPG","nationality":"Argentine","position":"Milieu offensif","goat_positions":["midfielders","attackers"],"era":"années 1980-1990","clubs":["Argentinos Juniors","Boca Juniors","FC Barcelone","Napoli","Sevilla"],"national_team":"Argentine","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["1986"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":["Ballon d'Or d'honneur France Football"],"major_records":["Auteur du But du siècle","Icône absolue du football argentin","Napoli champion d'Italie avec Maradona comme leader"],"iconic_moments":["Coupe du Monde 1986","But du siècle contre l'Angleterre","Titres historiques avec Napoli"],"nickname":"El Pibe de Oro","legacy":"L'un des plus grands joueurs de l'histoire, capable de porter une sélection ou un club au-delà de son niveau collectif.","playing_style":"Meneur total, dribble bas, conduite sous pression, créativité et leadership émotionnel.","why_legend":"Il a incarné la Coupe du Monde 1986 et changé l'histoire de Napoli quasiment à lui seul.","goat_score":97,"hall_of_fame_tier":"S+","contexts":["worldcup"]},
  {"name":"Lionel Messi","display_name":"Lionel Messi","photo_url":"https://images.fotmob.com/image_resources/playerimages/30981.png","nationality":"Argentine","position":"Attaquant / meneur","goat_positions":["attackers","midfielders"],"era":"années 2000-2020","clubs":["FC Barcelone","PSG","Inter Miami"],"national_team":"Argentine","ballon_dor_count":8,"ballon_dor_years":["2009","2010","2011","2012","2015","2019","2021","2023"],"world_cup_titles":["2022"],"euro_titles":[],"copa_america_titles":["2021"],"champions_league_titles":["2006","2009","2011","2015"],"fifa_awards":["The Best FIFA","Ballon d'Or Coupe du Monde 2014 et 2022"],"major_records":["Recordman de Ballons d'Or","Référence historique du FC Barcelone"],"iconic_moments":["Saison 2011-2012 record","Coupe du Monde 2022","Années Guardiola au Barça"],"nickname":"La Pulga","legacy":"Souvent cité comme le joueur le plus complet de l'ère moderne par son mélange buts, création, dribble et continuité.","playing_style":"Meneur-buteur total, dribble court, dernière passe, finition et contrôle du rythme.","why_legend":"Une combinaison unique de statistiques, titres, création, longévité et Coupe du Monde 2022.","goat_score":100,"hall_of_fame_tier":"S+","contexts":["worldcup","champions"]},
  {"name":"Cristiano Ronaldo","display_name":"Cristiano Ronaldo","photo_url":"https://images.fotmob.com/image_resources/playerimages/30893.png","nationality":"Portugal","position":"Attaquant","goat_positions":["attackers"],"era":"années 2000-2020","clubs":["Sporting CP","Manchester United","Real Madrid","Juventus","Al Nassr"],"national_team":"Portugal","ballon_dor_count":5,"ballon_dor_years":["2008","2013","2014","2016","2017"],"world_cup_titles":[],"euro_titles":["2016"],"copa_america_titles":[],"champions_league_titles":["2008","2014","2016","2017","2018"],"fifa_awards":["FIFA World Player / The Best","Souliers d'or européens"],"major_records":["Meilleur buteur historique de la Ligue des Champions","Référence absolue du buteur moderne"],"iconic_moments":["Finale de Ligue des Champions 2008","Triplés européens avec le Real Madrid","Euro 2016 avec le Portugal"],"nickname":"CR7","legacy":"Incarne le rendement, la longévité, l'exigence physique et l'impact décisif dans les grands rendez-vous européens.","playing_style":"Buteur d'élite, jeu aérien, appel dans la surface, puissance et obsession du rendement.","why_legend":"Cinq Ligues des Champions, cinq Ballons d'Or, records européens et longévité exceptionnelle.","goat_score":98,"hall_of_fame_tier":"S+","contexts":["worldcup","euro","champions"]},
  {"name":"Ronaldo Nazário","display_name":"Ronaldo Nazário","photo_url":"https://images.fotmob.com/image_resources/playerimages/93179.png","nationality":"Brésil","position":"Attaquant","goat_positions":["attackers"],"era":"années 1990-2000","clubs":["Cruzeiro","PSV","FC Barcelone","Inter","Real Madrid","AC Milan","Corinthians"],"national_team":"Brésil","ballon_dor_count":2,"ballon_dor_years":["1997","2002"],"world_cup_titles":["1994","2002"],"euro_titles":[],"copa_america_titles":["1997","1999"],"champions_league_titles":[],"fifa_awards":["FIFA World Player 1996, 1997, 2002"],"major_records":["15 buts en Coupe du Monde","Un des attaquants les plus dominants de l'histoire"],"iconic_moments":["Coupe du Monde 2002","Saison 1996-1997 au Barça","Années Inter avant blessures"],"nickname":"O Fenômeno","legacy":"Le modèle de l'attaquant moderne explosif, mélange rare de vitesse, dribble et finition.","playing_style":"Avant-centre ultra explosif, dribble en course, finition froide, puissance et changements d'appuis.","why_legend":"À son pic, il a donné l'impression de réinventer le poste d'avant-centre.","goat_score":95,"hall_of_fame_tier":"S","contexts":["worldcup","champions"]},
  {"name":"Zinedine Zidane","display_name":"Zinedine Zidane","photo_url":"https://images.fotmob.com/image_resources/playerimages/25760.png","nationality":"France","position":"Milieu offensif","goat_positions":["midfielders"],"era":"années 1990-2000","clubs":["Cannes","Bordeaux","Juventus","Real Madrid"],"national_team":"France","ballon_dor_count":1,"ballon_dor_years":["1998"],"world_cup_titles":["1998"],"euro_titles":["2000"],"copa_america_titles":[],"champions_league_titles":["2002"],"fifa_awards":["FIFA World Player 1998, 2000, 2003"],"major_records":["Légende Juventus et Real Madrid","Buteur de la finale de Ligue des Champions 2002"],"iconic_moments":["Doublé en finale de Coupe du Monde 1998","Volée de Glasgow 2002","Euro 2000"],"nickname":"Zizou","legacy":"Considéré comme l'un des plus grands milieux de terrain de l'histoire par son contrôle du tempo et ses grands matchs.","playing_style":"Meneur de jeu calme, toucher de balle, protection du ballon, vision et maîtrise du tempo.","why_legend":"Ballon d'Or, champion du monde, champion d'Europe, et des finales marquées par des gestes historiques.","goat_score":94,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Ronaldinho","display_name":"Ronaldinho","photo_url":"https://images.fotmob.com/image_resources/playerimages/2409.png","nationality":"Brésil","position":"Milieu offensif / ailier","goat_positions":["midfielders","attackers"],"era":"années 2000","clubs":["Grêmio","PSG","FC Barcelone","AC Milan","Atlético Mineiro"],"national_team":"Brésil","ballon_dor_count":1,"ballon_dor_years":["2005"],"world_cup_titles":["2002"],"euro_titles":[],"copa_america_titles":["1999"],"champions_league_titles":["2006"],"fifa_awards":["FIFA World Player 2004 et 2005"],"major_records":["Icône du FC Barcelone","Symbole du football-spectacle des années 2000"],"iconic_moments":["Ovation au Bernabéu en 2005","Ligue des Champions 2006 avec le Barça","Coupe du Monde 2002"],"nickname":"O Bruxo","legacy":"Considéré comme l'un des meilleurs dribbleurs de l'histoire, avec une influence énorme sur une génération de joueurs.","playing_style":"Dribble, improvisation, passes impossibles, coups francs et magie dans les petits espaces.","why_legend":"Il a rendu le football spectaculaire au plus haut niveau tout en gagnant Ballon d'Or, Mondial et Ligue des Champions.","goat_score":90,"hall_of_fame_tier":"S","contexts":["worldcup","champions"]},
  {"name":"Johan Cruyff","display_name":"Johan Cruyff","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Johan_Cruijff_1974c.jpg/500px-Johan_Cruijff_1974c.jpg","nationality":"Pays-Bas","position":"Attaquant / meneur","goat_positions":["attackers","midfielders"],"era":"années 1960-1970","clubs":["Ajax","FC Barcelone","Feyenoord"],"national_team":"Pays-Bas","ballon_dor_count":3,"ballon_dor_years":["1971","1973","1974"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1971","1972","1973"],"fifa_awards":[],"major_records":["Figure centrale du football total","Triple Ballon d'Or"],"iconic_moments":["Ajax triple champion d'Europe","Coupe du Monde 1974","Influence fondatrice au Barça"],"nickname":"El Flaco","legacy":"L'un des plus grands penseurs-joueurs de l'histoire, influence majeure sur Ajax, Barcelone et le football moderne.","playing_style":"Meneur libre, intelligence positionnelle, accélérations, créativité et lecture collective.","why_legend":"Son influence dépasse ses statistiques : il a transformé la manière de penser le jeu.","goat_score":96,"hall_of_fame_tier":"S+","contexts":["worldcup","euro","champions"]},
  {"name":"Franz Beckenbauer","display_name":"Franz Beckenbauer","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/Franz_Beckenbauer_1975_%28cropped%29.jpg/500px-Franz_Beckenbauer_1975_%28cropped%29.jpg","nationality":"Allemagne","position":"Défenseur","goat_positions":["defenders"],"era":"années 1960-1970","clubs":["Bayern Munich","New York Cosmos","Hamburger SV"],"national_team":"Allemagne","ballon_dor_count":2,"ballon_dor_years":["1972","1976"],"world_cup_titles":["1974"],"euro_titles":["1972"],"copa_america_titles":[],"champions_league_titles":["1974","1975","1976"],"fifa_awards":[],"major_records":["Référence historique du libéro","Triple champion d'Europe avec le Bayern"],"iconic_moments":["Coupe du Monde 1974","Euro 1972","Bayern triple champion d'Europe"],"nickname":"Der Kaiser","legacy":"A redéfini le rôle de défenseur-libéro par son élégance, son leadership et sa relance.","playing_style":"Libéro élégant, anticipation, relance, conduite de balle et autorité tactique.","why_legend":"Ballons d'Or, Mondial, Euro, Coupes d'Europe : le défenseur total par excellence.","goat_score":95,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Michel Platini","display_name":"Michel Platini","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Michel_Platini_1984.jpg/500px-Michel_Platini_1984.jpg","nationality":"France","position":"Milieu offensif","goat_positions":["midfielders"],"era":"années 1980","clubs":["Nancy","Saint-Étienne","Juventus"],"national_team":"France","ballon_dor_count":3,"ballon_dor_years":["1983","1984","1985"],"world_cup_titles":[],"euro_titles":["1984"],"copa_america_titles":[],"champions_league_titles":["1985"],"fifa_awards":[],"major_records":["9 buts à l'Euro 1984","Triple Ballon d'Or consécutif"],"iconic_moments":["Euro 1984","Trois Ballons d'Or consécutifs","Juventus des années 1980"],"nickname":"Le Roi Michel","legacy":"Meneur-buteur rarissime, symbole d'une France techniquement dominante dans les années 1980.","playing_style":"Meneur-buteur, vision, coups francs, jeu long et arrivée dans la surface.","why_legend":"Un Euro 1984 légendaire et trois Ballons d'Or qui résument une domination individuelle rare.","goat_score":91,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Thierry Henry","display_name":"Thierry Henry","photo_url":"https://images.fotmob.com/image_resources/playerimages/7867.png","nationality":"France","position":"Attaquant","goat_positions":["attackers"],"era":"années 2000","clubs":["Monaco","Juventus","Arsenal","FC Barcelone","New York Red Bulls"],"national_team":"France","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["1998"],"euro_titles":["2000"],"copa_america_titles":[],"champions_league_titles":["2009"],"fifa_awards":[],"major_records":["Meilleur buteur historique d'Arsenal","Référence majeure de Premier League"],"iconic_moments":["Arsenal Invincibles 2003-2004","Années Wenger","Triplé 2009 avec le Barça"],"nickname":"Titi","legacy":"Attaquant complet, référence d'Arsenal et de la Premier League par sa vitesse, sa finition et son élégance.","playing_style":"Attaquant lancé côté gauche, vitesse, finition enroulée et intelligence d'appel.","why_legend":"Champion du monde, champion d'Europe, icône d'Arsenal et attaquant emblématique de Premier League.","goat_score":86,"hall_of_fame_tier":"A+","contexts":["worldcup","euro","champions"]},
  {"name":"Neymar","display_name":"Neymar","photo_url":"https://images.fotmob.com/image_resources/playerimages/26399.png","nationality":"Brésil","position":"Ailier / meneur","goat_positions":["attackers","midfielders"],"era":"années 2010-2020","clubs":["Santos","FC Barcelone","PSG","Al Hilal"],"national_team":"Brésil","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["2015"],"fifa_awards":[],"major_records":["Parmi les meilleurs buteurs de l'histoire du Brésil","Membre majeur du trio MSN"],"iconic_moments":["Copa Libertadores 2011","Remontada 2017","Titre olympique 2016"],"nickname":"Ney","legacy":"Créateur spectaculaire, dribbleur d'élite et joueur qui a marqué toute une génération par son style.","playing_style":"Dribbleur créatif, un contre un, conduite de balle spectaculaire et dernière passe.","why_legend":"Un talent technique immense, une Ligue des Champions avec le Barça et une place majeure dans l'histoire moderne du Brésil.","goat_score":82,"hall_of_fame_tier":"A+","contexts":["worldcup","champions"]},
  {"name":"Kylian Mbappé","display_name":"Kylian Mbappé","photo_url":"https://images.fotmob.com/image_resources/playerimages/701154.png","nationality":"France","position":"Attaquant","goat_positions":["attackers"],"era":"années 2010-2020","clubs":["AS Monaco","PSG","Real Madrid"],"national_team":"France","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["2018"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["2025"],"fifa_awards":["Soulier d'or Coupe du Monde 2022"],"major_records":["Un des joueurs les plus précoces de l'histoire en Coupe du Monde"],"iconic_moments":["Éclosion Monaco 2017","Coupe du Monde 2018","Triplé en finale 2022"],"nickname":"Kyks","legacy":"Référence de vitesse, d'attaque de profondeur et de précocité au très haut niveau.","playing_style":"Attaquant de rupture, vitesse extrême, appels profonds et finition en transition.","why_legend":"Champion du monde très jeune, finaliste 2022 avec triplé en finale, potentiel historique encore ouvert.","goat_score":84,"hall_of_fame_tier":"A+","contexts":["worldcup","euro","champions"]},
  {"name":"Luka Modrić","display_name":"Luka Modrić","photo_url":"https://images.fotmob.com/image_resources/playerimages/170323.png","nationality":"Croatie","position":"Milieu","goat_positions":["midfielders"],"era":"années 2010-2020","clubs":["Dinamo Zagreb","Tottenham Hotspur","Real Madrid"],"national_team":"Croatie","ballon_dor_count":1,"ballon_dor_years":["2018"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["2014","2016","2017","2018","2022","2024"],"fifa_awards":["The Best FIFA 2018"],"major_records":["Ballon d'Or 2018","Meneur de la Croatie finaliste du Mondial 2018"],"iconic_moments":["Coupe du Monde 2018","Triplés européens du Real Madrid","Longévité au Real"],"nickname":"Lukita","legacy":"Milieu moderne de référence par sa technique, son endurance, son intelligence et son impact dans les grands matchs.","playing_style":"Milieu relayeur créatif, extérieur du pied, contrôle du tempo et déplacements entre lignes.","why_legend":"Ballon d'Or dans l'ère Messi/Ronaldo et pilier d'un Real Madrid multi-champion d'Europe.","goat_score":89,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Andrés Iniesta","display_name":"Andrés Iniesta","photo_url":"https://images.fotmob.com/image_resources/playerimages/17029.png","nationality":"Espagne","position":"Milieu","goat_positions":["midfielders"],"era":"années 2000-2010","clubs":["FC Barcelone","Vissel Kobe"],"national_team":"Espagne","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["2010"],"euro_titles":["2008","2012"],"copa_america_titles":[],"champions_league_titles":["2006","2009","2011","2015"],"fifa_awards":[],"major_records":["Buteur en finale de Coupe du Monde 2010","Icône du Barça et de la Roja"],"iconic_moments":["But contre les Pays-Bas en 2010","Barça Guardiola","Euro 2012"],"nickname":"Don Andrés","legacy":"Symbole de la maîtrise technique espagnole et du jeu de possession le plus dominant de l'époque moderne.","playing_style":"Milieu d'équilibre, conduite fluide, passe, orientation et calme sous pression.","why_legend":"But de Coupe du Monde, Euros, Ligues des Champions et influence majeure dans deux équipes historiques.","goat_score":90,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Xavi","display_name":"Xavi","photo_url":"https://images.fotmob.com/image_resources/playerimages/12234.png","nationality":"Espagne","position":"Milieu","goat_positions":["midfielders"],"era":"années 2000-2010","clubs":["FC Barcelone","Al Sadd"],"national_team":"Espagne","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["2010"],"euro_titles":["2008","2012"],"copa_america_titles":[],"champions_league_titles":["2006","2009","2011","2015"],"fifa_awards":[],"major_records":["Chef d'orchestre du Barça et de l'Espagne","Référence mondiale du jeu de possession"],"iconic_moments":["Euro 2008","Coupe du Monde 2010","Barça Guardiola"],"nickname":"El Maestro","legacy":"Un des plus grands organisateurs de jeu de l'histoire, incarnation du contrôle par la passe.","playing_style":"Métronome, jeu court, orientation, lecture des espaces et contrôle du rythme.","why_legend":"Il a incarné le cœur tactique du Barça et de l'Espagne dans une période de domination exceptionnelle.","goat_score":89,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Paolo Maldini","display_name":"Paolo Maldini","photo_url":"https://images.fotmob.com/image_resources/playerimages/5589.png","nationality":"Italie","position":"Défenseur","goat_positions":["defenders"],"era":"années 1980-2000","clubs":["AC Milan"],"national_team":"Italie","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1989","1990","1994","2003","2007"],"fifa_awards":[],"major_records":["5 Ligues des Champions","Référence historique des défenseurs"],"iconic_moments":["Dynastie Milan","Finale 2003","Ligue des Champions 2007"],"nickname":"Il Capitano","legacy":"Défenseur total, modèle de classe, longévité et excellence défensive.","playing_style":"Défenseur élégant, anticipation, duel, placement et relance propre.","why_legend":"Une carrière entière à Milan, cinq Coupes d'Europe et une référence absolue du poste.","goat_score":93,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Sergio Ramos","display_name":"Sergio Ramos","photo_url":"https://images.fotmob.com/image_resources/playerimages/25538.png","nationality":"Espagne","position":"Défenseur","goat_positions":["defenders"],"era":"années 2000-2020","clubs":["Sevilla","Real Madrid","PSG"],"national_team":"Espagne","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["2010"],"euro_titles":["2008","2012"],"copa_america_titles":[],"champions_league_titles":["2014","2016","2017","2018"],"fifa_awards":[],"major_records":["Défenseur buteur dans les grands matchs","Pilier du Real Madrid européen"],"iconic_moments":["But de Lisbonne 2014","Espagne 2008-2012","Quatre Ligues des Champions"],"nickname":"SR4","legacy":"Défenseur de caractère, leader, buteur décisif et figure majeure du Real Madrid moderne.","playing_style":"Défenseur agressif, jeu aérien, leadership, relance et buts sur coups de pied arrêtés.","why_legend":"Son but en 2014 et son palmarès club/sélection le placent parmi les défenseurs les plus marquants.","goat_score":88,"hall_of_fame_tier":"A+","contexts":["worldcup","euro","champions"]},
  {"name":"Gianluigi Buffon","display_name":"Gianluigi Buffon","photo_url":"https://images.fotmob.com/image_resources/playerimages/1099.png","nationality":"Italie","position":"Gardien","goat_positions":["goalkeepers"],"era":"années 1990-2020","clubs":["Parma","Juventus","PSG"],"national_team":"Italie","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["2006"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":["Meilleur gardien FIFA / UEFA à plusieurs reprises"],"major_records":["Recordman de longévité au très haut niveau","Légende de la Juventus et de l'Italie"],"iconic_moments":["Coupe du Monde 2006","Années Juventus","Finales européennes"],"nickname":"Gigi","legacy":"L'un des plus grands gardiens de l'histoire, symbole de longévité, charisme et régularité.","playing_style":"Gardien complet, réflexes, lecture, sorties, autorité et calme dans les grands matchs.","why_legend":"Champion du monde 2006 et référence mondiale du poste pendant plus de vingt ans.","goat_score":92,"hall_of_fame_tier":"S","contexts":["worldcup","euro","champions"]},
  {"name":"Lev Yashin","display_name":"Lev Yashin","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Lev_Yashin_1965.jpg/500px-Lev_Yashin_1965.jpg","nationality":"URSS / Russie","position":"Gardien","goat_positions":["goalkeepers"],"era":"années 1950-1960","clubs":["Dynamo Moscow"],"national_team":"URSS","ballon_dor_count":1,"ballon_dor_years":["1963"],"world_cup_titles":[],"euro_titles":["1960"],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":[],"major_records":["Seul gardien Ballon d'Or","Référence historique du poste"],"iconic_moments":["Ballon d'Or 1963","Euro 1960","Dynamo Moscow"],"nickname":"L'Araignée noire","legacy":"Le gardien mythique par excellence, symbole du poste et de ses exigences modernes.","playing_style":"Gardien anticipateur, réflexes, sorties et présence intimidante.","why_legend":"Seul gardien Ballon d'Or, il reste la référence historique absolue du poste.","goat_score":94,"hall_of_fame_tier":"S","contexts":["worldcup","euro"]},
  {"name":"Alfredo Di Stéfano","display_name":"Alfredo Di Stéfano","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Alfredo_Di_St%C3%A9fano_1963.jpg/500px-Alfredo_Di_St%C3%A9fano_1963.jpg","nationality":"Argentine / Espagne","position":"Attaquant / meneur","goat_positions":["attackers","midfielders"],"era":"années 1950-1960","clubs":["River Plate","Millonarios","Real Madrid","Espanyol"],"national_team":"Argentine / Espagne","ballon_dor_count":2,"ballon_dor_years":["1957","1959"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":["1947"],"champions_league_titles":["1956","1957","1958","1959","1960"],"fifa_awards":["Super Ballon d'Or France Football 1989"],"major_records":["Figure fondatrice du Real Madrid européen","5 Coupes d'Europe consécutives"],"iconic_moments":["Real Madrid des années 1950","Finale européenne 1960","Super Ballon d'Or"],"nickname":"La Saeta Rubia","legacy":"Joueur total avant l'heure, symbole du Real Madrid européen et de la domination continentale.","playing_style":"Attaquant complet, décrochages, pressing, création, finition et influence totale sur le jeu.","why_legend":"Il a incarné le Real Madrid des cinq premières Coupes d'Europe et le joueur total moderne.","goat_score":96,"hall_of_fame_tier":"S+","contexts":["champions"]},
  {"name":"Ferenc Puskás","display_name":"Ferenc Puskás","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Ferenc_Puskas_1971.jpg/500px-Ferenc_Puskas_1971.jpg","nationality":"Hongrie","position":"Attaquant","goat_positions":["attackers"],"era":"années 1950-1960","clubs":["Budapest Honvéd","Real Madrid"],"national_team":"Hongrie","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1959","1960","1966"],"fifa_awards":[],"major_records":["Icône de la Hongrie magique","Prix Puskás nommé en son honneur"],"iconic_moments":["Hongrie des années 1950","Real Madrid européen","Finale Coupe du Monde 1954"],"nickname":"Le Major galopant","legacy":"Buteur mythique, symbole d'une Hongrie révolutionnaire et du Real Madrid continental.","playing_style":"Avant-centre gaucher, frappe puissante, sens du but et leadership offensif.","why_legend":"Son nom est devenu synonyme de but exceptionnel et son influence traverse les générations.","goat_score":92,"hall_of_fame_tier":"S","contexts":["worldcup","champions"]},
  {"name":"Eusébio","display_name":"Eusébio","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Eusebio_1966.jpg/500px-Eusebio_1966.jpg","nationality":"Portugal","position":"Attaquant","goat_positions":["attackers"],"era":"années 1960-1970","clubs":["Benfica"],"national_team":"Portugal","ballon_dor_count":1,"ballon_dor_years":["1965"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1962"],"fifa_awards":[],"major_records":["Soulier d'or Coupe du Monde 1966","Légende absolue du Benfica"],"iconic_moments":["Coupe du Monde 1966","Benfica européen","Ballon d'Or 1965"],"nickname":"La Panthère noire","legacy":"Attaquant puissant et explosif, icône du Portugal et de Benfica.","playing_style":"Vitesse, frappe lourde, puissance, finition et générosité offensive.","why_legend":"Ballon d'Or, star du Mondial 1966 et figure fondatrice du football portugais moderne.","goat_score":91,"hall_of_fame_tier":"S","contexts":["worldcup","champions"]},
  {"name":"George Best","display_name":"George Best","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/George_Best_%281976%29.jpg/500px-George_Best_%281976%29.jpg","nationality":"Irlande du Nord","position":"Ailier","goat_positions":["attackers"],"era":"années 1960-1970","clubs":["Manchester United"],"national_team":"Irlande du Nord","ballon_dor_count":1,"ballon_dor_years":["1968"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1968"],"fifa_awards":[],"major_records":["Icône technique de Manchester United","Ballon d'Or 1968"],"iconic_moments":["Ligue des Champions 1968","Manchester United des Busby Babes post-Munich"],"nickname":"El Beatle","legacy":"Génie du dribble et icône culturelle du football britannique.","playing_style":"Ailier dribbleur, changement de rythme, créativité et finition spectaculaire.","why_legend":"Son talent pur et son aura ont marqué Manchester United et toute une époque.","goat_score":88,"hall_of_fame_tier":"A+","contexts":["champions"]},
  {"name":"Bobby Charlton","display_name":"Bobby Charlton","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Bobby_Charlton_1966.jpg/500px-Bobby_Charlton_1966.jpg","nationality":"Angleterre","position":"Milieu offensif","goat_positions":["midfielders"],"era":"années 1950-1970","clubs":["Manchester United"],"national_team":"Angleterre","ballon_dor_count":1,"ballon_dor_years":["1966"],"world_cup_titles":["1966"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["1968"],"fifa_awards":[],"major_records":["Légende de Manchester United et de l'Angleterre","Survivant et symbole de Munich"],"iconic_moments":["Coupe du Monde 1966","Ligue des Champions 1968","Renaissance de Manchester United"],"nickname":"Sir Bobby","legacy":"Milieu offensif historique, symbole d'élégance, loyauté et grandeur anglaise.","playing_style":"Frappe longue, conduite, vision, volume et sens du but depuis le milieu.","why_legend":"Champion du monde, Ballon d'Or, champion d'Europe et figure morale de Manchester United.","goat_score":89,"hall_of_fame_tier":"S","contexts":["worldcup","champions"]},
  {"name":"Garrincha","display_name":"Garrincha","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Garrincha_1962.jpg/500px-Garrincha_1962.jpg","nationality":"Brésil","position":"Ailier","goat_positions":["attackers"],"era":"années 1950-1960","clubs":["Botafogo"],"national_team":"Brésil","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["1958","1962"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":[],"major_records":["Héros de la Coupe du Monde 1962","Un des plus grands dribbleurs de l'histoire"],"iconic_moments":["Coupe du Monde 1962","Duo Pelé-Garrincha","Années Botafogo"],"nickname":"Alegria do Povo","legacy":"Symbole du football joyeux, instinctif et imprévisible du Brésil.","playing_style":"Ailier dribbleur, feintes, accélérations courtes et créativité pure.","why_legend":"Il a porté le Brésil en 1962 et reste une référence absolue du dribble.","goat_score":90,"hall_of_fame_tier":"S","contexts":["worldcup"]},
  {"name":"Romário","display_name":"Romário","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Romario_2015.jpg/500px-Romario_2015.jpg","nationality":"Brésil","position":"Attaquant","goat_positions":["attackers"],"era":"années 1980-2000","clubs":["Vasco da Gama","PSV","FC Barcelone","Flamengo"],"national_team":"Brésil","ballon_dor_count":0,"ballon_dor_years":[],"world_cup_titles":["1994"],"euro_titles":[],"copa_america_titles":["1989","1997"],"champions_league_titles":[],"fifa_awards":["FIFA World Player 1994"],"major_records":["Champion du Monde 1994","Buteur brésilien majeur"],"iconic_moments":["Coupe du Monde 1994","FC Barcelone 1993-1995","Années PSV"],"nickname":"Baixinho","legacy":"Renard de surface génial, clinique, imprévisible et décisif.","playing_style":"Finition courte distance, appels, sang-froid, petits espaces et instinct de buteur.","why_legend":"Il a été le visage offensif du Brésil champion du monde 1994.","goat_score":87,"hall_of_fame_tier":"A+","contexts":["worldcup","champions"]},
  {"name":"Rivaldo","display_name":"Rivaldo","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Rivaldo_2014.jpg/500px-Rivaldo_2014.jpg","nationality":"Brésil","position":"Milieu offensif / attaquant","goat_positions":["midfielders","attackers"],"era":"années 1990-2000","clubs":["Palmeiras","Deportivo La Coruña","FC Barcelone","AC Milan"],"national_team":"Brésil","ballon_dor_count":1,"ballon_dor_years":["1999"],"world_cup_titles":["2002"],"euro_titles":[],"copa_america_titles":["1999"],"champions_league_titles":["2003"],"fifa_awards":["FIFA World Player 1999"],"major_records":["Ballon d'Or 1999","Membre clé du Brésil 2002"],"iconic_moments":["Retourné contre Valence 2001","Coupe du Monde 2002","Barça fin des années 1990"],"nickname":"Riva","legacy":"Gaucher créatif, imprévisible et décisif, symbole d'un Brésil offensif et technique.","playing_style":"Frappe gauche, dribble, passes, tirs lointains et gestes spectaculaires.","why_legend":"Ballon d'Or, champion du monde et auteur de moments techniques inoubliables.","goat_score":86,"hall_of_fame_tier":"A+","contexts":["worldcup","champions"]},
  {"name":"Kaká","display_name":"Kaká","photo_url":"https://images.fotmob.com/image_resources/playerimages/10884.png","nationality":"Brésil","position":"Milieu offensif","goat_positions":["midfielders"],"era":"années 2000","clubs":["São Paulo","AC Milan","Real Madrid","Orlando City"],"national_team":"Brésil","ballon_dor_count":1,"ballon_dor_years":["2007"],"world_cup_titles":["2002"],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":["2007"],"fifa_awards":["FIFA World Player 2007"],"major_records":["Ballon d'Or 2007","Leader offensif de l'AC Milan 2007"],"iconic_moments":["Ligue des Champions 2007","Percées avec Milan","Ballon d'Or 2007"],"nickname":"Kaká","legacy":"Dernier Ballon d'Or avant la grande ère Messi/Ronaldo, meneur vertical et élégant.","playing_style":"Conduite longue, accélération axe, passe, frappe et transition offensive.","why_legend":"Son année 2007 reste une des saisons individuelles les plus marquantes d'un meneur moderne.","goat_score":85,"hall_of_fame_tier":"A+","contexts":["worldcup","champions"]},
  {"name":"Roberto Baggio","display_name":"Roberto Baggio","photo_url":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Roberto_Baggio_1990.jpg/500px-Roberto_Baggio_1990.jpg","nationality":"Italie","position":"Attaquant / meneur","goat_positions":["attackers","midfielders"],"era":"années 1990-2000","clubs":["Fiorentina","Juventus","AC Milan","Bologna","Inter","Brescia"],"national_team":"Italie","ballon_dor_count":1,"ballon_dor_years":["1993"],"world_cup_titles":[],"euro_titles":[],"copa_america_titles":[],"champions_league_titles":[],"fifa_awards":["FIFA World Player 1993"],"major_records":["Ballon d'Or 1993","Icône technique du football italien"],"iconic_moments":["Coupe du Monde 1994","Juventus début 1990","Retour à Brescia"],"nickname":"Il Divin Codino","legacy":"Un des plus grands artistes italiens, mélange de poésie, technique et tragédie sportive.","playing_style":"Meneur-attaquant, dribble, coups francs, passes, finition et élégance.","why_legend":"Ballon d'Or, génie technique et personnage mythique du football italien.","goat_score":84,"hall_of_fame_tier":"A+","contexts":["worldcup","euro"]} 
]$hof$::jsonb) as x(
    name text, display_name text, photo_url text, nationality text, position text, goat_positions jsonb,
    era text, clubs jsonb, national_team text, ballon_dor_count int, ballon_dor_years jsonb,
    world_cup_titles jsonb, euro_titles jsonb, copa_america_titles jsonb, champions_league_titles jsonb,
    fifa_awards jsonb, major_records jsonb, iconic_moments jsonb, nickname text, legacy text,
    playing_style text, why_legend text, goat_score numeric, hall_of_fame_tier text, contexts jsonb
  )
),
seed_with_player as (
  select
    s.*,
    (
      select p.id
      from public.players p
      where lower(p.name) in (lower(s.name), lower(s.display_name))
      order by p.updated_at desc nulls last
      limit 1
    ) as player_id
  from seed s
)
insert into public.hall_of_fame_players (
  player_id, name, display_name, photo_url, nationality, position, era, clubs, national_team,
  ballon_dor_count, ballon_dor_years, world_cup_titles, euro_titles, copa_america_titles,
  champions_league_titles, fifa_awards, major_records, iconic_moments, nickname, legacy,
  playing_style, why_legend, goat_score, hall_of_fame_tier, source, last_enriched_at
)
select
  player_id, name, display_name, photo_url, nationality, position, era, clubs, national_team,
  ballon_dor_count, ballon_dor_years, world_cup_titles, euro_titles, copa_america_titles,
  champions_league_titles, fifa_awards, major_records, iconic_moments, nickname, legacy,
  playing_style, why_legend, goat_score, hall_of_fame_tier, 'akro-curated-v1', now()
from seed_with_player
on conflict (name) do update set
  player_id = coalesce(excluded.player_id, public.hall_of_fame_players.player_id),
  display_name = coalesce(nullif(excluded.display_name, ''), public.hall_of_fame_players.display_name),
  photo_url = coalesce(nullif(excluded.photo_url, ''), public.hall_of_fame_players.photo_url),
  nationality = coalesce(nullif(excluded.nationality, ''), public.hall_of_fame_players.nationality),
  position = coalesce(nullif(excluded.position, ''), public.hall_of_fame_players.position),
  era = coalesce(nullif(excluded.era, ''), public.hall_of_fame_players.era),
  clubs = case when jsonb_array_length(excluded.clubs) > 0 then excluded.clubs else public.hall_of_fame_players.clubs end,
  national_team = coalesce(nullif(excluded.national_team, ''), public.hall_of_fame_players.national_team),
  ballon_dor_count = greatest(public.hall_of_fame_players.ballon_dor_count, excluded.ballon_dor_count),
  ballon_dor_years = case when jsonb_array_length(excluded.ballon_dor_years) > 0 then excluded.ballon_dor_years else public.hall_of_fame_players.ballon_dor_years end,
  world_cup_titles = case when jsonb_array_length(excluded.world_cup_titles) > 0 then excluded.world_cup_titles else public.hall_of_fame_players.world_cup_titles end,
  euro_titles = case when jsonb_array_length(excluded.euro_titles) > 0 then excluded.euro_titles else public.hall_of_fame_players.euro_titles end,
  copa_america_titles = case when jsonb_array_length(excluded.copa_america_titles) > 0 then excluded.copa_america_titles else public.hall_of_fame_players.copa_america_titles end,
  champions_league_titles = case when jsonb_array_length(excluded.champions_league_titles) > 0 then excluded.champions_league_titles else public.hall_of_fame_players.champions_league_titles end,
  fifa_awards = case when jsonb_array_length(excluded.fifa_awards) > 0 then excluded.fifa_awards else public.hall_of_fame_players.fifa_awards end,
  major_records = case when jsonb_array_length(excluded.major_records) > 0 then excluded.major_records else public.hall_of_fame_players.major_records end,
  iconic_moments = case when jsonb_array_length(excluded.iconic_moments) > 0 then excluded.iconic_moments else public.hall_of_fame_players.iconic_moments end,
  nickname = coalesce(nullif(excluded.nickname, ''), public.hall_of_fame_players.nickname),
  legacy = coalesce(nullif(excluded.legacy, ''), public.hall_of_fame_players.legacy),
  playing_style = coalesce(nullif(excluded.playing_style, ''), public.hall_of_fame_players.playing_style),
  why_legend = coalesce(nullif(excluded.why_legend, ''), public.hall_of_fame_players.why_legend),
  goat_score = greatest(coalesce(public.hall_of_fame_players.goat_score, 0), coalesce(excluded.goat_score, 0)),
  hall_of_fame_tier = coalesce(nullif(excluded.hall_of_fame_tier, ''), public.hall_of_fame_players.hall_of_fame_tier),
  source = 'akro-curated-v1',
  last_enriched_at = now(),
  updated_at = now();

with hof as (
  select *
  from public.hall_of_fame_players
  where source = 'akro-curated-v1'
),
seed as (
  select *
  from jsonb_to_recordset($tags$
[
  {"name":"Pelé","goat_positions":["attackers"],"contexts":["worldcup"],"clubs":["Santos","New York Cosmos"],"nation":"Brésil","era":"années 1950-1970"},
  {"name":"Diego Maradona","goat_positions":["midfielders","attackers"],"contexts":["worldcup"],"clubs":["Argentinos Juniors","Boca Juniors","FC Barcelone","Napoli","Sevilla"],"nation":"Argentine","era":"années 1980-1990"},
  {"name":"Lionel Messi","goat_positions":["attackers","midfielders"],"contexts":["worldcup","champions"],"clubs":["FC Barcelone","PSG","Inter Miami"],"nation":"Argentine","era":"années 2000-2020"},
  {"name":"Cristiano Ronaldo","goat_positions":["attackers"],"contexts":["worldcup","euro","champions"],"clubs":["Sporting CP","Manchester United","Real Madrid","Juventus","Al Nassr"],"nation":"Portugal","era":"années 2000-2020"},
  {"name":"Ronaldo Nazário","goat_positions":["attackers"],"contexts":["worldcup","champions"],"clubs":["Cruzeiro","PSV","FC Barcelone","Inter","Real Madrid","AC Milan","Corinthians"],"nation":"Brésil","era":"années 1990-2000"},
  {"name":"Zinedine Zidane","goat_positions":["midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["Cannes","Bordeaux","Juventus","Real Madrid"],"nation":"France","era":"années 1990-2000"},
  {"name":"Ronaldinho","goat_positions":["midfielders","attackers"],"contexts":["worldcup","champions"],"clubs":["Grêmio","PSG","FC Barcelone","AC Milan","Atlético Mineiro"],"nation":"Brésil","era":"années 2000"},
  {"name":"Johan Cruyff","goat_positions":["attackers","midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["Ajax","FC Barcelone","Feyenoord"],"nation":"Pays-Bas","era":"années 1960-1970"},
  {"name":"Franz Beckenbauer","goat_positions":["defenders"],"contexts":["worldcup","euro","champions"],"clubs":["Bayern Munich","New York Cosmos","Hamburger SV"],"nation":"Allemagne","era":"années 1960-1970"},
  {"name":"Michel Platini","goat_positions":["midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["Nancy","Saint-Étienne","Juventus"],"nation":"France","era":"années 1980"},
  {"name":"Thierry Henry","goat_positions":["attackers"],"contexts":["worldcup","euro","champions"],"clubs":["Monaco","Juventus","Arsenal","FC Barcelone","New York Red Bulls"],"nation":"France","era":"années 2000"},
  {"name":"Neymar","goat_positions":["attackers","midfielders"],"contexts":["worldcup","champions"],"clubs":["Santos","FC Barcelone","PSG","Al Hilal"],"nation":"Brésil","era":"années 2010-2020"},
  {"name":"Kylian Mbappé","goat_positions":["attackers"],"contexts":["worldcup","euro","champions"],"clubs":["AS Monaco","PSG","Real Madrid"],"nation":"France","era":"années 2010-2020"},
  {"name":"Luka Modrić","goat_positions":["midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["Dinamo Zagreb","Tottenham Hotspur","Real Madrid"],"nation":"Croatie","era":"années 2010-2020"},
  {"name":"Andrés Iniesta","goat_positions":["midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["FC Barcelone","Vissel Kobe"],"nation":"Espagne","era":"années 2000-2010"},
  {"name":"Xavi","goat_positions":["midfielders"],"contexts":["worldcup","euro","champions"],"clubs":["FC Barcelone","Al Sadd"],"nation":"Espagne","era":"années 2000-2010"},
  {"name":"Paolo Maldini","goat_positions":["defenders"],"contexts":["worldcup","euro","champions"],"clubs":["AC Milan"],"nation":"Italie","era":"années 1980-2000"},
  {"name":"Sergio Ramos","goat_positions":["defenders"],"contexts":["worldcup","euro","champions"],"clubs":["Sevilla","Real Madrid","PSG"],"nation":"Espagne","era":"années 2000-2020"},
  {"name":"Gianluigi Buffon","goat_positions":["goalkeepers"],"contexts":["worldcup","euro","champions"],"clubs":["Parma","Juventus","PSG"],"nation":"Italie","era":"années 1990-2020"},
  {"name":"Lev Yashin","goat_positions":["goalkeepers"],"contexts":["worldcup","euro"],"clubs":["Dynamo Moscow"],"nation":"URSS","era":"années 1950-1960"},
  {"name":"Alfredo Di Stéfano","goat_positions":["attackers","midfielders"],"contexts":["champions"],"clubs":["River Plate","Millonarios","Real Madrid","Espanyol"],"nation":"Argentine / Espagne","era":"années 1950-1960"},
  {"name":"Ferenc Puskás","goat_positions":["attackers"],"contexts":["worldcup","champions"],"clubs":["Budapest Honvéd","Real Madrid"],"nation":"Hongrie","era":"années 1950-1960"},
  {"name":"Eusébio","goat_positions":["attackers"],"contexts":["worldcup","champions"],"clubs":["Benfica"],"nation":"Portugal","era":"années 1960-1970"},
  {"name":"George Best","goat_positions":["attackers"],"contexts":["champions"],"clubs":["Manchester United"],"nation":"Irlande du Nord","era":"années 1960-1970"},
  {"name":"Bobby Charlton","goat_positions":["midfielders"],"contexts":["worldcup","champions"],"clubs":["Manchester United"],"nation":"Angleterre","era":"années 1950-1970"},
  {"name":"Garrincha","goat_positions":["attackers"],"contexts":["worldcup"],"clubs":["Botafogo"],"nation":"Brésil","era":"années 1950-1960"},
  {"name":"Romário","goat_positions":["attackers"],"contexts":["worldcup","champions"],"clubs":["Vasco da Gama","PSV","FC Barcelone","Flamengo"],"nation":"Brésil","era":"années 1980-2000"},
  {"name":"Rivaldo","goat_positions":["midfielders","attackers"],"contexts":["worldcup","champions"],"clubs":["Palmeiras","Deportivo La Coruña","FC Barcelone","AC Milan"],"nation":"Brésil","era":"années 1990-2000"},
  {"name":"Kaká","goat_positions":["midfielders"],"contexts":["worldcup","champions"],"clubs":["São Paulo","AC Milan","Real Madrid","Orlando City"],"nation":"Brésil","era":"années 2000"},
  {"name":"Roberto Baggio","goat_positions":["attackers","midfielders"],"contexts":["worldcup","euro"],"clubs":["Fiorentina","Juventus","AC Milan","Bologna","Inter","Brescia"],"nation":"Italie","era":"années 1990-2000"}
]$tags$::jsonb) as x(name text, goat_positions jsonb, contexts jsonb, clubs jsonb, nation text, era text)
),
tag_rows as (
  select h.player_id, h.name as player_name, 'nation' as tag_type, s.nation as tag_value from hof h join seed s on s.name = h.name
  union all
  select h.player_id, h.name, 'club', value #>> '{}' from hof h join seed s on s.name = h.name cross join lateral jsonb_array_elements(s.clubs)
  union all
  select h.player_id, h.name, 'position', value #>> '{}' from hof h join seed s on s.name = h.name cross join lateral jsonb_array_elements(s.goat_positions)
  union all
  select h.player_id, h.name, 'era', s.era from hof h join seed s on s.name = h.name
  union all
  select h.player_id, h.name, value #>> '{}', value #>> '{}' from hof h join seed s on s.name = h.name cross join lateral jsonb_array_elements(s.contexts)
)
insert into public.goat_player_tags (
  player_id, player_name, tag_type, tag_value, source, confidence, raw_data, updated_at
)
select
  player_id,
  player_name,
  tag_type,
  tag_value,
  'hall-of-fame-seed',
  0.98,
  jsonb_build_object('seed', 'hall_of_fame_players', 'version', 'akro-curated-v1'),
  now()
from tag_rows
where coalesce(tag_value, '') <> ''
on conflict (player_name, tag_type, tag_value) do update set
  player_id = coalesce(excluded.player_id, public.goat_player_tags.player_id),
  source = excluded.source,
  confidence = greatest(coalesce(public.goat_player_tags.confidence, 0), excluded.confidence),
  raw_data = excluded.raw_data,
  updated_at = now();

update public.players p
set
  full_name = coalesce(nullif(p.full_name, ''), h.name),
  display_name = coalesce(nullif(p.display_name, ''), h.display_name, h.name),
  national_team = coalesce(nullif(p.national_team, ''), h.national_team),
  career_clubs = case when p.career_clubs = '[]'::jsonb then h.clubs else p.career_clubs end,
  major_titles = case when p.major_titles = '[]'::jsonb then (
    h.world_cup_titles || h.euro_titles || h.copa_america_titles || h.champions_league_titles
  ) else p.major_titles end,
  individual_awards = case when p.individual_awards = '[]'::jsonb then (
    h.ballon_dor_years || h.fifa_awards
  ) else p.individual_awards end,
  playing_style = coalesce(nullif(p.playing_style, ''), h.playing_style),
  nickname = coalesce(nullif(p.nickname, ''), h.nickname),
  photo_source = coalesce(nullif(p.photo_source, ''), 'hall-of-fame-seed'),
  last_enriched_at = coalesce(p.last_enriched_at, now())
from public.hall_of_fame_players h
where p.id = h.player_id;

insert into public.player_enrichment_logs (
  player_id, player_name, enrichment_type, source, status, message
)
select
  player_id,
  name,
  'hall_of_fame_seed',
  'akro-curated-v1',
  'success',
  'Légende Hall of Fame enrichie et tags THE GOAT préparés.'
from public.hall_of_fame_players
where source = 'akro-curated-v1';
