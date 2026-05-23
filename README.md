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
