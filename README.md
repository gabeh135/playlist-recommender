# Playlist Recommender

A music recommendation system that generates playlists and recommends songs based on user preferences, listening history, and natural language prompts.

## Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker + Docker Compose

### 1. Clone and configure

```bash
git clone <repo-url>
cd playlist-recommender
cp .env.example backend/.env
```

Fill in the required values in `backend/.env`:
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` — from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- `DATABASE_URL` — your Supabase connection string
- `SECRET_KEY` — any random 32-char hex string (`python3 -c "import secrets; print(secrets.token_hex(32))"`)

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts a local Postgres (with pgvector) on port 5432 and Redis on port 6379.

> **WSL note:** if PostgreSQL is pre-installed on your system and owns port 5432, disable it first:
> `sudo systemctl disable --now postgresql@14-main`

### 3. Run the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`. Swagger docs at `http://127.0.0.1:8000/docs`.

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.
