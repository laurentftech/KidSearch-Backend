# KidSearch Backend — Wiki

Welcome to the full documentation for KidSearch Backend.

## Pages

| Page | Content |
|---|---|
| [Authentication](Authentication) | OIDC, authcrunch proxy, Google/GitHub OAuth, password |
| [Production Deployment](Production-Deployment) | HTTPS, Caddy, custom domain, Synology |
| [Environment Variables](Environment-Variables) | Full configuration reference |
| [Sites Configuration](Sites-Configuration) | Crawler configuration (sites.yml) |

## Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/laurentftech/KidSearch-Backend/main/scripts/install.sh | bash
```

Asks 2 questions, generates secrets, starts everything.

## Architecture

```
Caddy (HTTPS) ──► Dashboard  :8501  (Streamlit)
              ──► API         :8080  (FastAPI)
                      │
                      ├── Typesense  :8108  (local index)
                      ├── Embeddings :8090  (HuggingFace TEI)
                      └── Google CSE        (external search, optional)
```

## Basic commands

```bash
make setup        # Initial setup or reconfigure
make docker-up    # Start services
make docker-down  # Stop services
make docker-logs  # Follow logs
```
