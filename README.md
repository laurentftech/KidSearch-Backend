# KidSearch Backend

[![Tests](https://github.com/laurentftech/KidSearch-Backend/actions/workflows/tests.yml/badge.svg)](https://github.com/laurentftech/KidSearch-Backend/actions/workflows/tests.yml)
[![Docker Build](https://github.com/laurentftech/KidSearch-Backend/actions/workflows/docker-build.yml/badge.svg)](https://github.com/laurentftech/KidSearch-Backend/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/github/license/laurentftech/KidSearch-Backend)](LICENSE)

Full backend for a safe search engine for children. Combines an async crawler, a federated search API and a monitoring dashboard.

![Dashboard screenshot](media/screenshot_dashboard_en.png)

## Quick install

```bash
curl -fsSL https://raw.githubusercontent.com/laurentftech/KidSearch-Backend/main/scripts/install.sh | bash
```

Or if you already cloned the repo:

```bash
git clone https://github.com/laurentftech/KidSearch-Backend && cd KidSearch-Backend
make setup
```

The script asks **2 questions** (dashboard password + optional Google CSE), generates secrets automatically and offers to start the services.

## Services

| Service | Local URL | Description |
|---|---|---|
| Dashboard | http://localhost:8501 | Monitoring UI (Streamlit) |
| API | http://localhost:8082/api/docs | Search API (FastAPI) |
| Typesense | http://localhost:8108 | Local search engine |

## Common commands

```bash
make setup        # Initial setup or reconfigure
make docker-up    # Start services
make docker-down  # Stop services
make docker-logs  # Follow logs
```

## Documentation

Full documentation is available on the **[project Wiki](https://github.com/laurentftech/KidSearch-Backend/wiki)**:

- [Advanced Authentication](https://github.com/laurentftech/KidSearch-Backend/wiki/Authentication) — OIDC, authcrunch proxy, Google/GitHub OAuth
- [Production Deployment](https://github.com/laurentftech/KidSearch-Backend/wiki/Production-Deployment) — HTTPS, Caddy, custom domain
- [Environment Variables](https://github.com/laurentftech/KidSearch-Backend/wiki/Environment-Variables) — Full configuration reference
- [Sites Configuration](https://github.com/laurentftech/KidSearch-Backend/wiki/Sites-Configuration) — Crawler and sites.yml

## Architecture

```
Caddy (HTTPS) ──► Dashboard  :8501  (Streamlit)
              ──► API         :8080  (FastAPI)
                      │
                      ├── Typesense  :8108  (local index)
                      ├── Embeddings :8090  (HuggingFace TEI)
                      └── Google CSE        (external search, optional)
```

## License

MIT — see [LICENSE](LICENSE)
