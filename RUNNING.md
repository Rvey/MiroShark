# Running MiroShark

This repo supports two different ways to run the app.

- Local dev mode: frontend and backend run from your checked-out source code.
- Docker mode: the packaged app runs in containers.

Choose one mode and stick to it for a session. Mixing them is possible, but it is also the easiest way to confuse ports, environment variables, and process state.

## Mode 1: Local Dev

Use this when you want to edit code.

In this mode:

- Frontend runs locally on `http://localhost:3000`
- Backend runs locally on `http://localhost:5001`
- Neo4j can run in Docker
- Your LLM and embedding provider can be remote APIs such as OpenAI

### Prerequisites

- Node.js 18+
- Python 3.11+
- `uv`
- Docker Desktop running

### 1. Start Neo4j

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/miroshark \
  neo4j:5.15-community
```

If the container already exists:

```bash
docker start neo4j
```

### 2. Configure `.env`

Copy the example file once:

```bash
cp .env.example .env
```

If you want to use OpenAI directly, use this configuration:

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=your-openai-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miroshark

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BASE_URL=https://api.openai.com
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_DIMENSIONS=768

OPENAI_API_KEY=your-openai-api-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
```

Notes:

- `EMBEDDING_PROVIDER` must be `openai` or `ollama`. It is not a URL path.
- `EMBEDDING_BASE_URL` must be `https://api.openai.com`, not `https://api.openai.com/v1/embeddings`, because the app appends `/v1/embeddings` internally.

### 3. Install dependencies

```bash
npm run setup:all
```

### 4. Start the app

```bash
npm run dev
```

That starts:

- local frontend from `frontend/`
- local backend from `backend/`

### 5. Open the app

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`
- Neo4j browser: `http://localhost:7474`

### Local dev service map

- Frontend: local process
- Backend: local process
- Neo4j: Docker container
- OpenAI: remote API

## Mode 2: All Docker

Use this when you want the packaged stack, not when you want to edit and test source code live.

```bash
docker compose up -d
```

This starts:

- `miroshark-neo4j`
- `miroshark-ollama`
- `miroshark`

Open:

- App: `http://localhost:3000`
- Backend API: `http://localhost:5001`
- Neo4j browser: `http://localhost:7474`

### Important limitation

The provided `docker-compose.yml` is wired for the repo's Docker defaults:

- local Ollama for LLM
- local Ollama for embeddings
- Neo4j by Docker service name

It is not automatically configured for your custom direct OpenAI `.env` setup.

If you want OpenAI direct, local dev mode is the cleanest path unless you also modify the compose environment for the `miroshark` service.

## Which mode am I using?

If you ran:

```bash
npm run dev
```

you are in local dev mode.

If you ran:

```bash
docker compose up -d
```

you are in Docker mode.

## Common Commands

### Stop local frontend or backend

If you started them in terminals, stop them with `Ctrl+C` in those terminals.

### Stop Docker containers

```bash
docker stop neo4j
docker stop miroshark miroshark-neo4j miroshark-ollama
```

### Remove Docker containers

```bash
docker rm neo4j
docker rm miroshark miroshark-neo4j miroshark-ollama
```

### Restart only Neo4j

```bash
docker restart neo4j
```

## Troubleshooting

### `localhost:5001` refused to connect

The backend is not running.

In local dev mode, start it with:

```bash
cd backend
uv run python run.py
```

Or from the repo root:

```bash
npm run dev
```

### `localhost:3000` refused to connect

The frontend is not running.

Start it with:

```bash
cd frontend
npm run dev -- --host
```

Or from the repo root:

```bash
npm run dev
```

### Neo4j retries or Bolt connection errors

Check the container:

```bash
docker ps
docker logs --tail 100 neo4j
```

If Neo4j became unhealthy, restart it:

```bash
docker restart neo4j
```

### Neo4j says `No space left on device`

This is typically Docker disk pressure, not a Python bug.

Useful cleanup commands:

```bash
docker builder prune -af
docker image prune -a
docker system df
```

Then restart Neo4j:

```bash
docker restart neo4j
```

### `vite: command not found`

Frontend packages are not installed.

Run:

```bash
npm install --prefix frontend
```

### `uv: command not found`

Install `uv` first.

On macOS:

```bash
brew install uv
```

## Recommended path for your current setup

If you want:

- local source code edits
- direct OpenAI usage
- Neo4j in Docker

Use local dev mode.

That means:

1. Start Neo4j with Docker
2. Keep your OpenAI config in `.env`
3. Run `npm run dev`

Do not expect the packaged Docker stack to automatically use the same `.env` behavior as your local development setup.