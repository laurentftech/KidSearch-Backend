# Environment Variables Reference

All variables are set in `.env`. Values in brackets are the Docker defaults.

## Required

| Variable | Description |
|---|---|
| `JWT_SECRET_KEY` | JWT signing key — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `TYPESENSE_API_KEY` | Typesense access key (shared across services) |

## Authentication

| Variable | Default | Description |
|---|---|---|
| `AUTH_DISABLED` | `false` | Disable all auth (dev only) |
| `AUTH_PROVIDERS` | _(auto)_ | Force a method: `simple`, `oidc`, `proxy`, `google`, `github` |
| `DASHBOARD_PASSWORD` | — | Simple password |
| `ALLOWED_EMAILS` | — | Restrict access by email (comma-separated) |
| `AUTH_PROXY_ENABLED` | `false` | Enable proxy authentication |
| `AUTH_PROXY_LOGOUT_URL` | `/` | Proxy logout URL |
| `AUTH_PROXY_EMAIL_HEADER` | `X-Token-User-Email` | Header injected by the proxy |
| `AUTH_PROXY_NAME_HEADER` | `X-Token-User-Name` | Header injected by the proxy |
| `OIDC_ISSUER` | — | OIDC provider URL |
| `OIDC_CLIENT_ID` | — | OIDC client ID |
| `OIDC_CLIENT_SECRET` | — | OIDC client secret |
| `OIDC_REDIRECT_URI` | `http://localhost:8501/` | OIDC redirect URI |
| `OIDC_SCOPES` | `openid profile email` | Requested scopes |
| `GOOGLE_OAUTH_CLIENT_ID` | — | Google OAuth |
| `GOOGLE_OAUTH_CLIENT_SECRET` | — | Google OAuth |
| `GITHUB_OAUTH_CLIENT_ID` | — | GitHub OAuth |
| `GITHUB_OAUTH_CLIENT_SECRET` | — | GitHub OAuth |

## JWT

| Variable | Default | Description |
|---|---|---|
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_EXPIRATION_MINUTES` | `1440` | Token lifetime (24h) |

## API

| Variable | Docker default | Description |
|---|---|---|
| `API_URL` | `http://kidsearch-all:8080/api` | Internal URL used by the Dashboard |
| `API_ENABLED` | `true` | Enable the API backend |
| `API_WORKERS` | `2` | Number of Uvicorn workers |

## Typesense

| Variable | Docker default | Description |
|---|---|---|
| `TYPESENSE_URL` | `http://typesense:8108` | Typesense service URL |
| `INDEX_NAME` | `kidsearch` | Index name |

## Embeddings

| Variable | Docker default | Description |
|---|---|---|
| `EMBEDDING_PROVIDER` | `huggingface` | Provider: `huggingface` or `gemini` |
| `HUGGINGFACE_API_URL` | `http://embeddings_small:80/embed` | ⚠️ Do not change in Docker |
| `HUGGINGFACE_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Model used |
| `EMBEDDING_BATCH_DELAY` | `2` | Delay between batches (seconds) |
| `GEMINI_API_KEY` | — | Google Gemini API key (alternative provider) |
| `GEMINI_EMBEDDING_BATCH_SIZE` | `20` | Gemini batch size |

## Reranking

| Variable | Default | Description |
|---|---|---|
| `RERANKING_ENABLED` | `true` | Enable semantic reranking |
| `RERANKER_API_URL` | `http://embeddings_small:80/embed` | ⚠️ Do not change in Docker |
| `RERANKER_MODEL` | _(same as HF)_ | Reranking model |
| `RERANKER_BATCH_SIZE` | `3` | Batch size |
| `RERANKER_MAX_CHARS` | `200` | Max length of text excerpts |
| `RERANKER_CACHE_SIZE` | `4096` | LRU cache size |
| `RERANKER_TIMEOUT` | `12` | Timeout in seconds |

## Search

| Variable | Default | Description |
|---|---|---|
| `MEILISEARCH_WEIGHT` | `0.7` | Weight of local results |
| `CSE_WEIGHT` | `0.3` | Weight of Google CSE results |
| `GOOGLE_CSE_API_KEY` | — | Google Custom Search API key |
| `GOOGLE_CSE_ID` | — | Google Custom Search Engine ID |

## Integrated Wiki

| Variable | Default | Description |
|---|---|---|
| `WIKI_API_URL` | `https://fr.vikidia.org/w/api.php` | Primary MediaWiki API URL |
| `WIKI_SITE_URL` | `https://fr.vikidia.org/wiki/` | Article base URL |
| `WIKI_SITE_NAME` | `Vikidia` | Display name |
| `WIKI_2_API_URL` | `https://en.vikidia.org/w/api.php` | Secondary wiki |
| `WIKI_2_SITE_URL` | `https://en.vikidia.org/wiki/` | |
| `WIKI_2_SITE_NAME` | `Vikidia EN` | |

## Production URLs

| Variable | Description |
|---|---|
| `FRONTEND_URL` | Public URL of the frontend (for CORS headers) |
| `DISPLAY_HOST` | Host shown in the UI |
| `DASHBOARD_DISPLAY_HOST` | Host shown for the dashboard |
| `API_DISPLAY_HOST` | Host shown for the API |

## Logs

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warning`, `error` |
