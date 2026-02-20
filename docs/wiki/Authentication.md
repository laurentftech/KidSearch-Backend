# Authentication

KidSearch supports several authentication methods for the dashboard. The default setup (`make setup`) configures a simple password.

## Available methods

| Method | Use case | Complexity |
|---|---|---|
| Simple password | Dev / personal use | ⭐ Minimal |
| OIDC | SSO via Keycloak, Authentik, Google... | ⭐⭐ |
| Google / GitHub OAuth | Login with existing account | ⭐⭐ |
| Authcrunch proxy | Production with Caddy | ⭐⭐⭐ |

---

## Simple password

Fastest option. Set during `make setup` or manually in `.env`:

```env
AUTH_PROVIDERS=simple
DASHBOARD_PASSWORD=your_password
```

---

## OIDC (Keycloak, Authentik, Google Workspace...)

```env
AUTH_PROVIDERS=oidc
OIDC_ISSUER=https://auth.example.com
OIDC_CLIENT_ID=kidsearch
OIDC_CLIENT_SECRET=your_client_secret
OIDC_REDIRECT_URI=https://dashboard.example.com/
OIDC_SCOPES=openid profile email
```

The OIDC provider must allow the configured redirect URI.

---

## Google OAuth

1. Create OAuth credentials in the [Google Cloud Console](https://console.cloud.google.com/)
2. Type: **Web Application**, redirect URI: `https://your-dashboard/`

```env
AUTH_PROVIDERS=google
GOOGLE_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=xxx
GOOGLE_OAUTH_REDIRECT_URI=https://dashboard.example.com/
```

---

## GitHub OAuth

1. Create an OAuth App at [github.com/settings/developers](https://github.com/settings/developers)
2. Homepage URL and callback URL point to your dashboard

```env
AUTH_PROVIDERS=github
GITHUB_OAUTH_CLIENT_ID=xxx
GITHUB_OAUTH_CLIENT_SECRET=xxx
GITHUB_OAUTH_REDIRECT_URI=https://dashboard.example.com/
```

---

## Authcrunch proxy (Caddy — Production)

Recommended for production. Caddy with the authcrunch plugin handles OIDC authentication and injects user information into HTTP headers.

```env
AUTH_PROVIDERS=proxy
AUTH_PROXY_ENABLED=true
AUTH_PROXY_LOGOUT_URL=/
AUTH_PROXY_EMAIL_HEADER=X-Token-User-Email
AUTH_PROXY_NAME_HEADER=X-Token-User-Name
```

Minimal Caddyfile example:

```caddy
{
    security {
        authorization policy kidsearch_policy {
            set auth url https://auth.example.com
            allow roles authp/user
            inject headers with claims
        }
    }
}

https://dashboard.example.com {
    authorize with kidsearch_policy
    reverse_proxy kidsearch-all:8501 {
        header_up Connection {>Connection}
        header_up Upgrade {>Upgrade}
    }
}
```

---

## Email whitelist

Regardless of the method, you can restrict access to a list of emails:

```env
ALLOWED_EMAILS=alice@example.com,bob@example.com
```

If empty: all authenticated users have access.

---

## Disable authentication (dev only)

```env
AUTH_DISABLED=true
```

> ⚠️ Never use in production.
