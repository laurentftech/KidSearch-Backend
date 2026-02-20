# Production Deployment

This page covers production setup with HTTPS, a custom domain and Caddy as a reverse proxy.

## Prerequisites

- A Linux server with Docker installed
- A domain name pointing to your server
- Ports 80 and 443 open

## 1. Install KidSearch

```bash
curl -fsSL https://raw.githubusercontent.com/laurentftech/KidSearch-Backend/main/scripts/install.sh | bash
```

During setup, configure the production URLs when prompted.

## 2. Configure URLs in .env

```env
FRONTEND_URL=https://search.example.com
API_DISPLAY_HOST=api.example.com
DASHBOARD_DISPLAY_HOST=dashboard.example.com
DISPLAY_HOST=api.example.com
```

## 3. Install Caddy with the authcrunch plugin

If you use proxy authentication (recommended):

```bash
# Build Caddy with xcaddy
xcaddy build --with github.com/greenpau/caddy-security
```

Or use a pre-built Docker image that includes the plugin.

## 4. Full Caddyfile

```caddy
{
    email admin@example.com

    security {
        authentication portal myportal {
            enable identity store localdb
            cookie domain example.com
        }

        authorization policy dashboard_policy {
            set auth url https://auth.example.com
            allow roles authp/admin
            inject headers with claims
        }
    }
}

# Monitoring dashboard
https://dashboard.example.com {
    authorize with dashboard_policy
    reverse_proxy kidsearch-all:8501 {
        header_up Connection {>Connection}
        header_up Upgrade {>Upgrade}
    }
}

# Search API
https://api.example.com {
    reverse_proxy kidsearch-all:8080
    header {
        X-Frame-Options SAMEORIGIN
        X-Content-Type-Options nosniff
    }
}
```

## 5. Cloudflare DNS (optional)

If you use Cloudflare for DNS, add to the Caddyfile global block:

```caddy
{
    acme_dns cloudflare {env.CLOUDFLARE_API_TOKEN}
}
```

## 6. Start

```bash
# Start Caddy
caddy start --config /path/to/Caddyfile

# Start KidSearch
docker compose up -d
```

## On Synology NAS

1. Install Docker via Package Center
2. Use Synology's built-in reverse proxy for HTTPS (Control Panel → Application Portal → Reverse Proxy)
3. Point entries to `localhost:8501` (dashboard) and `localhost:8082` (API)

## Memory requirements

| Service | Reserved | Limit |
|---|---|---|
| Typesense | 1.5 GB | 2.5 GB |
| Embeddings (HF) | 500 MB | 1 GB |
| KidSearch app | 256 MB | 512 MB |
| **Total** | **~2.3 GB** | **~4 GB** |
