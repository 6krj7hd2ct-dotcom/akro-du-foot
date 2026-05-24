# Akro du Foot

Akro du Foot génère automatiquement `index.html` pour suivre plusieurs compétitions dans une seule application : Coupe du Monde FIFA 2026 et Ligue des Champions. La page possède un header général, une zone communautaire globale, puis des onglets de compétitions. L’interface reste moderne, responsive et sans données inventées. Les données proviennent de sources publiques fiables quand elles répondent : ESPN, FotMob, BBC Sport, France Info, RMC Sport, UEFA/FIFA/L'Équipe/Statbunker si des flux exploitables sont ajoutés ensuite.

## Installation

```bash
cd "/Users/akro/akro-du-foot"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancer la mise à jour

```bash
python update_dashboard.py
```

Le script régénère :

- `data/worldcup_dashboard.json`
- `data/champions_league_dashboard.json`
- `index.html`

## Ouvrir le dashboard

```bash
open index.html
```

Tu peux aussi ouvrir directement `index.html` dans le navigateur intégré de Codex.

## Lancer la version communautaire

Le tchat et les pronostics ont besoin d'un petit serveur local.

```bash
cd "/Users/akro/akro-du-foot"
source .venv/bin/activate
python update_dashboard.py
python app.py
```

Ouvre ensuite :

```bash
http://localhost:5000
```

## Déployer sur Render

Le projet est prêt pour Render avec :

- `requirements.txt` : dépendances Python, dont Flask et Gunicorn.
- `Procfile` : commande de démarrage Render.
- `app.py` : serveur compatible avec la variable `PORT`.

### 1. Préparer le dépôt

Pousse le projet sur GitHub, GitLab ou Bitbucket avec au minimum :

- `app.py`
- `update_dashboard.py`
- `src/`
- `data/`
- `requirements.txt`
- `Procfile`
- `index.html`

### 2. Créer le service Render

Dans Render :

1. Clique sur `New`.
2. Choisis `Web Service`.
3. Connecte ton dépôt.
4. Runtime : `Python`.
5. Build Command :

```bash
pip install -r requirements.txt
```

6. Start Command :

```bash
python update_dashboard.py && AKRO_BACKGROUND_UPDATES=1 gunicorn app:app --bind 0.0.0.0:$PORT
```

Render fournit automatiquement la variable `PORT`. `AKRO_BACKGROUND_UPDATES=1` active aussi la régénération horaire de `data/worldcup_dashboard.json`, `data/champions_league_dashboard.json` et `index.html` pendant que le serveur tourne.

Render sert directement `index.html` via `app.py` : il n'y a pas de dossier `dist/` ou `build/` dans ce déploiement. Pour éviter qu'une ancienne PWA reste affichée après un déploiement, `app.py` envoie `index.html`, `manifest.json` et `service-worker.js` avec `Cache-Control: no-store` et remplace `__AKRO_BUILD_VERSION__` par `RENDER_GIT_COMMIT` quand Render fournit cette variable. Le navigateur enregistre donc `/service-worker.js?v=<version>` et recharge aussi `/manifest.json?v=<version>`.

Sur Render, `update_dashboard.py` ne régénère plus `index.html` par défaut afin de ne pas écraser la version validée dans la branche déployée. Pour réactiver explicitement la génération HTML serveur, ajoute `AKRO_RENDER_HTML_DURING_UPDATE=1`.

### 3. Données communautaires et comptes

Les comptes, profils, pronostics, statistiques et badges utilisent Supabase comme source principale de vérité. Applique le script SQL `supabase/user_accounts.sql` dans l'éditeur SQL Supabase, puis configure ces variables Render :

```bash
SUPABASE_URL="https://TON-PROJET.supabase.co"
SUPABASE_ANON_KEY="TA_CLE_ANON_PUBLIC"
```

Cette application n'est pas un build React/Vite dans ce dossier : `app.py` expose ces deux valeurs publiques au navigateur via `/api/supabase-public-config`. Si une version React/Vite est ajoutée plus tard, il faudra renommer les variables frontend en `VITE_SUPABASE_URL` et `VITE_SUPABASE_ANON_KEY`. Ne mets jamais `service_role` côté frontend.

Dans Supabase, active aussi les connexions anonymes : `Authentication` -> `Sign In / Providers` -> `Anonymous sign-ins`.

Les avatars prédéfinis sont servis depuis `public/avatars/`. Supabase stocke uniquement le chemin choisi dans `profiles.avatar_url`, par exemple `/avatars/avatar-cool.png`.

`data/community.json` reste seulement un filet de secours local pour les anciens messages/pronostics si Supabase est indisponible.

### 3bis. Base football Supabase, IA et synchronisation

Applique d'abord les scripts existants, puis la migration progressive :

```sql
-- Editeur SQL Supabase
-- 1. supabase/user_accounts.sql
-- 2. supabase/coach_messages.sql
-- 3. supabase/search_ai_answers.sql
-- 4. supabase/football_core.sql
```

`supabase/football_core.sql` ajoute uniquement des tables/colonnes manquantes. Il ne supprime pas, ne renomme pas et ne vide aucune table existante. Les nouvelles tables sont :

- `countries`
- `teams`
- `players`
- `coaches`
- `competitions`
- `matches`
- `team_players`
- `team_coaches`
- `entity_profiles`
- `sync_logs`

Le script active aussi `pgvector` avec :

```sql
create extension if not exists vector;
```

Variables serveur à configurer sur Render et dans les secrets Supabase :

```bash
SUPABASE_URL="https://TON-PROJET.supabase.co"
SUPABASE_ANON_KEY="TA_CLE_ANON_PUBLIC"
SUPABASE_SERVICE_ROLE_KEY="TA_CLE_SERVICE_ROLE_PRIVEE"
FOOTBALL_API_KEY="TA_CLE_API_FOOTBALL"
FOOTBALL_API_BASE_URL="https://v3.football.api-sports.io"
OPENAI_API_KEY="TA_CLE_OPENAI"
```

Ne mets jamais `SUPABASE_SERVICE_ROLE_KEY`, `FOOTBALL_API_KEY` ou `OPENAI_API_KEY` côté frontend.

Déployer les Edge Functions Supabase :

```bash
supabase functions deploy sync-football-data
supabase functions deploy update-entity-profiles
supabase functions deploy search-entity-profiles
```

Ajouter les secrets Edge Functions :

```bash
supabase secrets set SUPABASE_URL="https://TON-PROJET.supabase.co"
supabase secrets set SUPABASE_SERVICE_ROLE_KEY="TA_CLE_SERVICE_ROLE_PRIVEE"
supabase secrets set FOOTBALL_API_KEY="TA_CLE_API_FOOTBALL"
supabase secrets set FOOTBALL_API_BASE_URL="https://v3.football.api-sports.io"
supabase secrets set OPENAI_API_KEY="TA_CLE_OPENAI"
```

Lancer une synchronisation manuelle :

```bash
supabase functions invoke sync-football-data --no-verify-jwt
```

Depuis l'application, ouvre :

```bash
/admin/sync
```

La page affiche la dernière synchronisation, les 20 derniers logs `sync_logs`, un message si les données sont anciennes, et un bouton `Mettre à jour maintenant`. Si `WATCH_PARTY_ADMIN_KEY` est configurée, la même clé est demandée avant de déclencher la sync.

Vérifier les logs :

```sql
select *
from public.sync_logs
where job_name = 'sync-football-data'
order by started_at desc
limit 20;
```

Mode offline :

- si `FOOTBALL_API_KEY` ou `FOOTBALL_API_BASE_URL` manque, `sync-football-data` écrit un log d'erreur propre et ne vide aucune table ;
- si l'API football échoue ou atteint un quota, les données déjà stockées restent disponibles ;
- la page `/admin/sync` signale les données absentes ou anciennes ;
- quand une clé API active est ajoutée, relance une grosse synchronisation depuis `/admin/sync`.

Cron quotidien Supabase :

Supabase planifie généralement en UTC. Pour lancer vers 06:00 en France métropolitaine, utilise :

- hiver : `0 5 * * *`
- été : `0 4 * * *`

Si tu veux garder l'expression demandée telle quelle, `0 6 * * *` lance à 06:00 UTC, donc 07:00 en hiver et 08:00 en été en France.

Exemple avec `pg_cron` et `pg_net` si disponibles dans ton projet Supabase :

```sql
select cron.schedule(
  'sync-football-data-daily',
  '0 5 * * *',
  $$
  select net.http_post(
    url := 'https://TON-PROJET.supabase.co/functions/v1/sync-football-data',
    headers := jsonb_build_object(
      'Authorization', 'Bearer TA_CLE_SERVICE_ROLE_PRIVEE',
      'Content-Type', 'application/json'
    ),
    body := jsonb_build_object('source', 'cron')
  );
  $$
);
```

Limites connues :

- les quotas et formats varient selon l'API football choisie ;
- la fonction `sync-football-data` fait des upserts et ne supprime jamais brutalement une entité absente de l'API ;
- `update-entity-profiles` recalcule uniquement les entités modifiées récemment, puis remplit `entity_profiles` pour la recherche IA ;
- `search-entity-profiles` prépare la recherche pgvector pour enrichir ensuite les réponses du Coach.

### 4. Tester en ligne

Une fois déployé, ouvre l’URL Render.

- Le dashboard doit s’afficher sur `/`.
- Le tchat utilise `/api/messages` et `/api/community`.
- Les pronostics utilisent `/api/predictions` et `/api/community`.
- La Watch Party utilise `/watch-party` et `/api/livekit-token` si les variables LiveKit sont configurées.

## Watch Party LiveKit

La Watch Party permet à l'administrateur de partager son écran et son audio via LiveKit. Les spectateurs peuvent seulement regarder, écouter et écrire dans le tchat.

Crée une room LiveKit Cloud ou utilise ton serveur LiveKit, puis configure ces variables avant de lancer le serveur :

```bash
export LIVEKIT_URL="wss://TON-PROJET.livekit.cloud"
export LIVEKIT_API_KEY="TA_CLE_API"
export LIVEKIT_API_SECRET="TON_SECRET_API"
export WATCH_PARTY_ADMIN_KEY="une-cle-admin-privee"
python app.py
```

Ouvre ensuite :

```bash
http://localhost:5000/watch-party
```

Pour rejoindre en admin, choisis le rôle `Admin` et saisis `WATCH_PARTY_ADMIN_KEY`. Pour rejoindre en spectateur, choisis `Spectateur` : le token est en lecture seule, sans droit de partage d'écran.

Pour partager le son, sélectionne un onglet Chrome au moment du partage d'écran et coche `Partager l'audio de l'onglet`.

Pour partager sur ton réseau local, récupère l'adresse IP du Mac :

```bash
ipconfig getifaddr en0
```

Puis partage l'adresse :

```bash
http://ADRESSE_IP:5000
```

Pour une mise en ligne publique, il faut héberger l'application Flask sur un service web. Ne partage pas le serveur local directement sur Internet sans protection.

## Automatisation horaire

### Render

Le `Procfile` active la mise à jour horaire côté serveur avec `AKRO_BACKGROUND_UPDATES=1`. L’intervalle par défaut est de 3600 secondes ; il peut être ajusté avec `AKRO_UPDATE_INTERVAL_SECONDS`.

### GitHub Actions

Le workflow `.github/workflows/update-dashboard.yml` lance la génération toutes les heures à `HH:15` et commit les fichiers générés si le dépôt est sur GitHub.

### macOS local

```bash
chmod +x scripts/install_daily_update.sh
./scripts/install_daily_update.sh
```

Le LaunchAgent lance `update_dashboard.py` toutes les heures. Les logs sont écrits dans :

- `data/launchd.out.log`
- `data/launchd.err.log`

Si macOS bloque l’accès au dossier `Documents` dans les logs, donne `Accès complet au disque` à Terminal dans `Réglages Système > Confidentialité et sécurité`, puis relance l’installation.

## Application

La page commence par le header général `Akro du Foot`.

Il contient :

- choix du pseudo global ;
- accès au tchat ;
- accès aux pronostics fictifs ;
- partage de page ;
- bouton Watch Party.

Le pseudo choisi est mémorisé dans le navigateur et utilisé pour le tchat, les pronostics et le classement.

## Communauté globale

Le tchat et les pronostics sont indépendants des onglets. Ils restent visibles et actifs quand tu changes de compétition.

- Tchat : pseudo, message et heure, stockés dans `data/community.json`.
- Pronostics fictifs : matchs de Coupe du Monde et de Ligue des Champions dans le même module.
- Filtre pronostics : `Tous les matchs`, `Coupe du Monde`, `Ligue des Champions`.
- Classement : total global des points entre participants.
- Barème : 1 point pour le bon résultat, 3 points pour le score exact.

## Onglets et sections

La page contient deux onglets de compétition, sans rechargement :

- `Coupe du Monde 2026`
- `Ligue des Champions`

### Coupe du Monde 2026

- Header Coupe du Monde : ambiance stade, trophée stylisé CSS, badge France et date de mise à jour.
- Match du jour : rencontres du jour avec drapeaux, score si disponible, heure, stade et statut.
- Meilleurs buteurs : top 5, photo si disponible, pays et nombre de buts.
- Meilleurs passeurs : top 5, photo si disponible, pays et nombre de passes.
- Top 10 all-time : badge cliquable près des buteurs Coupe du Monde et Ligue des Champions, alimenté par StatBunker/UEFA quand les sources répondent.
- Actualité Coupe du Monde : 3 dernières actualités générales.
- Actualité Équipe de France : 3 dernières actualités dédiées aux Bleus.
- Fiches équipes interactives : clic sur une équipe dans les classements, matchs du jour, calendrier ou bracket pour ouvrir une fiche avec drapeau, sélectionneur, formation et effectif quand ces données sont publiées.
- Classements des groupes : 12 groupes avec drapeaux, J, G, N, P, différence et points.
- Résultats et calendrier des poules : tous les matchs groupés par journée.
- Arbre à élimination directe : bracket horizontal moderne avec 16es, 8es, quarts, demies, 3e place et finale.

### Ligue des Champions

- Header Ligue des Champions : thème bleu nuit, focus PSG, prochain match PSG si disponible, suivi de la phase actuelle et des volumes de matchs.
- Matchs du jour : rencontres du jour avec clubs, score ou heure et statut.
- Meilleurs buteurs et passeurs : top 5 si les sources publient les données.
- Actualité Ligue des Champions : 3 dernières actualités filtrées.
- Phase finale : bracket affiché dès que les matchs sont disponibles.
- Classement de la phase de ligue : clubs, J, G, N, P, différence et points.
- Résultats et calendrier : matchs groupés par journée.
- Fiches clubs : clic sur un club pour ouvrir sa fiche avec logo, coach et effectif si disponibles.

## Structure

- `update_dashboard.py` : point d'entrée principal.
- `app.py` : serveur Flask pour la version communautaire.
- `src/config.py` : chemins, URLs et flux.
- `src/fetchers.py` : récupération, normalisation et cache des données.
- `src/render.py` : génération HTML/CSS responsive.
- `data/community.json` : messages, pronostics amicaux, classement calculé à partir des scores réels.
- `data/worldcup_dashboard.json` : cache JSON complet, dont `teams_details`, `all_time_top_scorers` et `all_time_top_assisters`.
- `data/champions_league_dashboard.json` : cache JSON complet de la Ligue des Champions.
- `index.html` : dashboard généré.

## Notes

Le projet n'invente pas de score, photo, classement historique, équipe qualifiée, sélectionneur, formation ou effectif. Si une donnée n'est pas publiée par les sources, la page affiche un état vide, un avatar neutre, `À déterminer` ou `Formation non disponible`.
