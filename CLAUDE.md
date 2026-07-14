# Playlist Recommender — Project Context

## What this is
A music recommendation system built as a portfolio project for entry-level ML/engineering recruiting. Users populate a personal track collection by searching Spotify or importing playlists. Two features operate on that collection:
- **Feature A — Targeted playlist generation**: user writes a natural language prompt → system embeds it and similarity-searches their collection → returns a ranked playlist
- **Feature B — Library auto-sorting**: user imports a large unstructured collection → system clusters embeddings into cohesive playlists, filters outliers, and uses an LLM to name each cluster

## Agreed tech stack
| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + uvicorn | async-first, native OpenAPI docs |
| DB | PostgreSQL + pgvector | relational schema + ANN search in one system |
| Migrations | Alembic | keeps schema in sync with SQLAlchemy models |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | pre-trained, 384-dim, no training required |
| Ranker | LightGBM (impressive) / weighted cosine (MVP) | tree model on feedback features |
| Task queue | Celery + Redis | async preference vector updates after feedback |
| LLM | Claude API | NLP intent extraction from free-text prompts |
| Frontend | React + Vite + Tailwind | fast to build, easy to deploy |
| Hosting | Fly.io / Railway (backend), Supabase (DB), Vercel (frontend) | low ops overhead |
| Track metadata | Spotify API (search + genres) + Last.fm API (tags) | No global catalog — tracks ingested on demand when users search or import playlists |

## Data approach

No global catalog. Tracks are ingested on demand:
- **Search**: user searches Spotify → selects a track → backend fetches metadata + Last.fm tags → embeds → stores in `tracks` (globally deduplicated by `spotify_id`) + `collection_tracks` (user's library)
- **Playlist import**: user provides a public Spotify playlist URL → backend fetches all tracks via client credentials → same enrich/embed/store flow per track
- **Liked Songs / private playlists**: requires Spotify OAuth (user connects their account) — this is a core planned feature, not an afterthought. The schema is designed for it from day one.

Embedding input: `"{title} by {artist}. Genres: {genres}. Tags: {tags}"` via `all-MiniLM-L6-v2` (384-dim).

### Anonymous sessions (Phase 1) vs Spotify OAuth (later phases)
Phase 1 uses an anonymous user UUID stored in localStorage — no login required. A `User` row is created on first visit. When Spotify OAuth is added, the same row gets `spotify_user_id` + tokens populated; the user's existing collection stays intact.

Spotify refresh tokens expire after **6 months** (policy introduced June 2026). Store `spotify_authorized_at` on the User row (Spotify doesn't expose token issuance timestamps) to detect expiry and prompt re-auth. Tokens stored as plaintext in Supabase; Supabase at-rest encryption is sufficient for portfolio scale.

## Spotify API notes
- `GET /artists` (batch) was removed; `get_artist_genres()` calls the single-artist endpoint per ID
- Search limit is capped at 10 results per request
- Playlist item field is `item["item"]`, not `item["track"]`
- `popularity` field no longer available on Track or Artist objects
- Shared client-credentials token can get rate-limited for extended periods (hit a 16+ hour `Retry-After` once); `spotify_client.py` uses bounded retry/backoff instead of honoring it verbatim

## Infrastructure
- **Docker Compose** runs local Postgres (pgvector/pgvector:pg16) + Redis for development
- **Supabase** is production Postgres — `DATABASE_URL` in `.env` points there
- `LOCAL_DATABASE_URL` points to Docker Postgres; `config.py` picks the right one based on `ENVIRONMENT`
- **WSL gotcha**: system PostgreSQL 14 was pre-installed and claimed port 5432. Disabled via `sudo systemctl disable postgresql@14-main`. Docker now owns 5432.
- **Docker Desktop WSL integration**: must be enabled in Docker Desktop → Settings → Resources → WSL Integration. Gets reset on some reboots/reinstalls — re-enable and restart Docker Desktop if `docker` command disappears from WSL.
- **Supabase IPv6**: Supabase's direct DB host (`db.xxx.supabase.co`) resolves to IPv6 only. WSL2 has no IPv6 routing by default. Use Docker local DB for development; Supabase for production only.
- Docker Compose project name is `playlist-recommender` (set explicitly to avoid collisions)

## Environment
- `.env` lives in `backend/` (uvicorn runs from there)
- `ENVIRONMENT=development` → uses `LOCAL_DATABASE_URL`
- `ENVIRONMENT=production` → uses `DATABASE_URL` (Supabase)

## Current file state
```
backend/
  app/
    core/
      config.py           ✓ done — pydantic-settings, active_database_url property
      database.py         ✓ done — async SQLAlchemy engine, Base, get_db dependency
      deps.py             ✓ done — get_current_user dependency (X-User-ID header → User row)
    services/
      spotify_client.py   ✓ done — search_tracks, get_artist_genres, get_playlist_tracks, get_track (with retry)
      lastfm_client.py    ✓ done — get_track_tags, get_track_tags_batch
    models.py             ✓ done — redesigned schema (see data model section below)
    api/
      routes/
        users.py          ✓ done — POST /users
        tracks.py         ✓ done — GET /tracks/search (returns album_art_url)
        collection.py     ✓ done — POST /collection/tracks, POST /collection/import/playlist, GET /collection/tracks
        playlists.py      ✓ done — POST /playlists/generate, GET /playlists/{id} (both return album_art_url)
        cluster.py        ✓ done — POST /cluster (sync K-Means, returns ClusteringRun + Playlists)
    ml/
      encoders/embed.py        ✓ done — embed_text() via all-MiniLM-L6-v2
      retrieval.py             ✓ done — search_collection() pgvector cosine similarity
      clustering/clustering.py ✓ done — cluster_collection(), load_embeddings(), silhouette k-selection, outlier detection
    main.py               ✓ done — FastAPI app, CORS, /health endpoint with DB check
  alembic/                ✓ done — env.py wired to async engine + models
  alembic/versions/       ✓ done — migrations up to date (album_art_url added)
  requirements.txt        ✓ done
docker-compose.yml        ✓ done
.env / .env.example       ✓ done
frontend/
  src/
    App.tsx                        ✓ done — BrowserRouter, layout route, 3 page routes (Collection, Generate, Sort Library); gated on useUser() with LoadingScreen until resolved
    components/LoadingScreen.tsx   ✓ done — full-screen spinner shown until useUser() resolves (cold-start gate)
    components/Layout/Layout.tsx   ✓ done — top nav (Collection / Generate / Sort Library)
    components/ui/                 ✓ done — shadcn/radix-nova: button, input, slider, spinner
    hooks/useUser.ts               ✓ done — anonymous UUID from localStorage, POST /users on first visit
    lib/api.ts                     ✓ done — apiFetch() with X-User-ID header
    lib/utils.ts                   ✓ done — shadcn cn() utility
    pages/Collection.tsx           ✓ done — search, import playlist, track list with album art
    pages/Generate.tsx             ✓ done — prompt input, track count slider, ranked results with album art
    pages/SortLibrary.tsx          ✓ done — playlist count (auto/manual), completeness slider, loading state, results as playlist cards
    index.css                      ✓ done — Tailwind v4 + shadcn CSS vars (slate/indigo dark theme)
  components.json                  ✓ done — shadcn config (radix-nova preset)
  vite.config.ts                   ✓ done — @tailwindcss/vite plugin, @/ alias
  tsconfig.app.json / tsconfig.json ✓ done — path aliases for shadcn
  package.json                     ✓ done — Tailwind v4, shadcn, react-router-dom, Geist font
```

## Node version
nvm installed, Node 22.23.0 active. nvm loads automatically in new terminals via ~/.bashrc.
In existing terminals: `export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh"`

## Phase checklist
### Phase 0 — Setup ✓
- [x] Repo, .gitignore, .env
- [x] Spotify developer app registered
- [x] Supabase project created, pgvector enabled
- [x] docker-compose.yml (postgres + redis)
- [x] FastAPI scaffold (config, database, main, health check)
- [x] React scaffold (Vite + Tailwind + React Router, Node 22 via nvm)

### Phase 1 — Data Foundation ✓
- [x] SQLAlchemy models: redesigned schema (Track, User, CollectionTrack, IntentSession, ClusteringRun, Playlist, PlaylistTrack, FeedbackEvent)
- [x] Alembic setup
- [x] spotify_client.py service (search_tracks, get_artist_genres, get_playlist_tracks)
- [x] lastfm_client.py service (get_track_tags, get_track_tags_batch)
- [x] Drop DB, delete old alembic versions, run fresh migration
- [x] Anonymous user creation endpoint (POST /users → returns UUID stored in localStorage)
- [x] Track search endpoint (GET /tracks/search?q=... → Spotify search, returns candidates)
- [x] Add-to-collection endpoint (POST /collection/tracks — dedup, enrich with Last.fm, embed, store)
- [x] Playlist import endpoint (POST /collection/import/playlist — batch version of above)
- [x] GET /collection — returns user's current track list (for frontend display)

### Phase 2 — Feature A: Targeted Playlist Generation ✓
- [x] embed.py service (sentence-transformers, all-MiniLM-L6-v2)
- [x] retrieval.py (pgvector cosine similarity search scoped to user's collection)
- [x] POST /playlists/generate — embed prompt, ANN search, create Playlist + PlaylistTrack rows
- [x] GET /playlists/{id} — return playlist with tracks
- [x] Documentation/comment pass (hard gate before Phase 3)

### Phase 3 — Feature B: Library Clustering ✓
- [x] clustering.py (K-Means via sklearn, silhouette score for k estimation, outlier detection)
- [x] POST /cluster — run clustering, write ClusteringRun + Playlists + PlaylistTracks

### Phase 4 — Frontend MVP ✓
- [x] Collection view (search + import UI, track list with album art)
- [x] Targeted generation UI (prompt input, track count slider, ranked results with album art)
- [x] Sort Library UI (see design decisions below)
- [x] Deploy backend to Fly.io, frontend to Vercel

#### Sort Library UI — design decisions
Two inputs before triggering:
- **Number of playlists**: "Auto" (default, silhouette-score k-selection) or manual override. Manual range is 2 to `floor(collection_size / 8)` — enforces at least ~8 tracks per playlist. Show a warning if the chosen k would produce very small playlists. Update clustering code: current `max_k = min(10, n // 5)` is too conservative; change to `min(n // 8, user_supplied_max)` so large collections can produce more playlists.
- **Completeness**: slider (Loose → Strict) — maps to `outlier_threshold`; loose = more tracks included even if weakly fitting; strict = only core cluster members. Default: somewhere in the middle.

#### Known issues / loose ends (not blocking, revisit when convenient)
- Small-playlist warning only shows at the slider's max value, not across the whole range where it'd still apply
- `tracks.py` search-result parsing and `collection.py`'s `add_track` → `spotify.get_track` call aren't wrapped in try/except; an unhandled exception there 500s without CORS headers, which shows up in the browser as a misleading CORS error
- `useUser.ts` has no retry on a failed `/users` call — if it fails once (e.g. mid cold-start), the loading screen hangs with no recovery
- **Confirmed still broken**: Collection.tsx's "Your tracks" list has no working loading indicator on first load — blank space until the list appears, cold start or not. The page-wide `LoadingScreen` ("Connecting...") works, but it only gates on `useUser()`, which resolves instantly from localStorage for a returning visitor with no network call at all — so it provides zero cold-start protection for anyone except a brand-new user, and the Collection page's own fetch (`fetchPage` / the `total === 0 && loadingMore` spinner branch) is left to cover that gap on its own and isn't doing so in practice. Root cause not yet pinned down (candidates: the initial fetch failing fast on a cold connection and falling through to the wrong branch with no retry, vs. the loading state never getting a chance to paint) — needs to be actually debugged, not just reasoned about statically.
- Two real (and separate) sources of slow, inconsistent latency, independent of Fly cold-start, that make the missing-spinner problem worse:
  - `spotify_client.py`'s `get_artist_genres` calls the single-artist endpoint in a plain sequential loop (Spotify removed the batch `/artists` endpoint). Playlist import latency scales linearly with unique artist count with no concurrency — a 50-artist playlist means ~50 sequential HTTP round-trips before any tracks are enriched.
  - `/playlists/generate` now makes two sequential blocking Claude calls per request (`analyze_prompt` on Haiku for query expansion, then `select_best_tracks` on Sonnet judging up to `limit * 3` candidates), no client-side timeout, stacked on top of the embed + pgvector search. New since the query-expansion feature landed; meaningfully slower than before.
- No shared loading affordance across the app — every page/button reinvents its own text-only state (Collection: "Searching…"/"Adding…"/"Importing…"; Generate: "Generating…"; SortLibrary: cycling messages, the nicest of the three). The `Spinner` icon component is only actually used by `LoadingScreen` and Collection's first-page-load branch — no button composes it, so "in progress" mostly just means a disabled button with different text.
- SortLibrary's cycling loading messages ("Analyzing your collection...", "Building playlists...", etc.) vary in length, so the trigger button visibly resizes/reflows as the text cycles instead of staying a fixed size — needs a fixed-width/min-width (or truncation) on the button so cycling text doesn't shift layout.
- `SortLibrary`'s background collection-size fetch swallows errors (`.catch(() => {})`) and silently defaults to 0, disabling Sort with no explanation — same failure pattern as the `useUser.ts` issue above, just in a different spot.
- `ClusterResponse` now returns `silhouette_score` and `outlier_tracks` (backend done) but neither is surfaced in `SortLibrary.tsx` yet — deferred, these are diagnostic/metrics-only, not algorithm quality. Revisit once the sorter itself is in a good place.

**TODO (necessary, not yet scheduled)**: make it obvious when something is loading, everywhere. Fix the Collection initial-load indicator for real (debug it, don't just re-reason about it), then standardize: a spinner icon variant on `Button` (not just swapped text) for every in-flight action — search, add, import, generate, sort — and stop conflating "request failed" with "nothing here" in any of the three pages.

After triggering:
- Descriptive loading state ("Analyzing your collection...", "Building playlists...") — clustering is synchronous and can take several seconds for large collections.
- Results: playlist cards each with a name and a ranked track list with album art.
- Each track appears in exactly one playlist (hard K-Means assignment). Soft assignment (tracks near two centroids in both) deferred to Phase 6+.

LLM naming is a minimal afterthought: after clustering, pass the top 5 track titles per cluster to Claude Haiku and get a short playlist name back. If it fails, fall back to "Playlist 1", "Playlist 2", etc. No user inputs feed into it. No description needed — name only.

### Phase 5 — Spotify OAuth
- [ ] Authorization code flow (connect Spotify account)
- [ ] Token storage + silent refresh (check expiry before every API call)
- [ ] Liked Songs import (POST /collection/import/liked-songs)
- [ ] Private playlist import

### Phase 6+
- pgvector HNSW index tuning
- Feedback loop (FeedbackEvent → preference signal)
- LightGBM ranker — fixes lexical overlap issues in cosine similarity (e.g. a country song matching a "rap" prompt due to title word overlap)
- Soft cluster assignment — tracks near two centroids can appear in both playlists
- **Natural language clustering input**: user describes how they want their library split — potential vibes per playlist, themes, moods, etc. This is the intended long-term direction for Sort Library; the current slider-based UI is a proof of concept. The NL input feeds a global pre-filter step (era, genre include/exclude, popularity tier) that scopes the collection before clustering runs, plus informs LLM playlist naming. Scope is intentionally limited to *global* filters — per-playlist constraints (e.g. "put hip-hop in playlist 1") defeat the auto-discovery value prop and require constrained K-Means to implement reliably. Do the algorithm upgrade (HDBSCAN) before wiring this up.
  - **Future research (out of scope for now)**: LLM extracts a richer JSON schema from the prompt — per-playlist artist/genre include/exclude lists, not just global filters. Could enable power-user control over the sort. Open questions: does constrained clustering produce meaningfully better results than post-hoc filtering? What does the schema look like? Does the added UX complexity pay off vs. just letting the algorithm work? Worth revisiting after HDBSCAN is in place and we can measure baseline cluster quality.
- LLM playlist naming (Claude Haiku — minimal, uses top 5 track titles per cluster)
- Rate limiting, pagination, tests, README, demo video

## Data model

### Track (global dedup by spotify_id)
- id (UUID PK), spotify_id (str, unique), title, artist, album, release_year
- album_art_url (str, nullable — largest image from Spotify album object)
- genres (ARRAY str — from Spotify artist endpoint), tags (ARRAY str — from Last.fm)
- embedding (Vector(384) — from "{title} by {artist}. Genres: {genres}. Tags: {tags}")
- enriched_at (datetime — when Last.fm tags were fetched)

### User
- id (UUID PK), created_at
- spotify_user_id (str, nullable), spotify_access_token, spotify_refresh_token, spotify_token_expires_at
- spotify_authorized_at — stored because Spotify tokens don't expose issuance timestamp; needed to detect 6-month expiry

### CollectionTrack (user's personal library)
- id, user_id (FK), track_id (FK) — UNIQUE(user_id, track_id)
- added_at, source (enum: SEARCH | PLAYLIST_IMPORT | LIKED_SONGS)
- source_spotify_playlist_id (nullable — which playlist it came from)

### IntentSession (Feature A)
- id, user_id (FK), raw_prompt (str), intent_embedding (Vector(384)), created_at

### ClusteringRun (Feature B)
- id, user_id (FK), n_clusters, algorithm (str), outlier_threshold (float), run_at

### Playlist
- id, user_id (FK), name, generation_mode (enum: TARGETED | CLUSTERED), created_at
- intent_session_id (FK nullable — Feature A), clustering_run_id (FK nullable — Feature B)

### PlaylistTrack (ordered membership — replaces ARRAY on Playlist)
- id, playlist_id (FK), track_id (FK) — UNIQUE(playlist_id, track_id)
- position (int)

### FeedbackEvent
- id, user_id (FK), track_id (FK nullable), playlist_id (FK nullable)
- type (enum: LIKE | DISLIKE | SKIP | SAVE_PLAYLIST | DISMISS)
- position (int nullable), created_at

## User preferences
- Explain design decisions before writing code, not after
- Walk through pieces one at a time; user wants to understand each step
- Short concise responses preferred

## Documentation philosophy
A documentation pass is planned at the end of each phase — do not add comments during active development.

Style standard: personal/professional, not AI-generated. Specifically:
- Consistent, neutral tone throughout — no dramatic phrasing, no over-emphasis
- Explaining non-obvious library calls or API behavior is fine (e.g. what `scalar_one_or_none()` does, or why Last.fm returns a bare object instead of a list for single-tag results)
- Do not narrate control flow or restate what readable code already shows
- Do not comment every function — only where the intent, constraint, or tradeoff isn't obvious from the signature and body
- Docstrings should be terse; no boilerplate param/return blocks unless types are genuinely ambiguous
