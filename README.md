# KidSearch API & Meilisearch Crawler

This project provides a complete backend solution for a safe search engine like [KidSearch](https://github.com/laurentftech/kidsearch). It consists of two main components:

1.  A **KidSearch API Server**: A FastAPI-based server that performs federated searches across multiple sources (local Meilisearch, Google, Wikipedia) and uses a local model to semantically rerank results.
2.  A **Meilisearch Crawler**: A high-performance, asynchronous web crawler that populates the local Meilisearch instance with content from websites, JSON APIs, and MediaWiki sites.

This combination creates a powerful and flexible search backend, capable of delivering relevant and safe results.

## ✨ Features

### KidSearch API Server
- **FastAPI Backend**: A lightweight, high-performance API server to expose search functionalities.
- **Federated Search**: Aggregates results from multiple sources in real-time: the local Meilisearch index, Google Custom Search (GSE), and Wikipedia/Vikidia APIs.
- **Optimized Hybrid Reranking**: Fetches results from all sources, computes missing embeddings on-the-fly, and then uses a local cross-encoder model to intelligently rerank the combined list based on semantic relevance. This ensures the best content is always prioritized with minimal latency.
- **Ready for Production**: Can be easily deployed as a Docker container.

### Core Crawler
- **Asynchronous & Parallel**: Built with `asyncio` and `aiohttp` for high-speed, concurrent crawling.
- **Flexible Sources**: Natively supports crawling standard HTML websites, JSON APIs, and MediaWiki-powered sites (like Wikipedia or Vikidia).
- **Incremental Crawling**: Uses a local cache to only re-index pages that have changed since the last crawl, saving time and resources.
- **Crawl Resumption**: If a crawl is interrupted, it can be seamlessly resumed later.
- **Smart Content Extraction**: Uses `trafilatura` for robust main content detection from HTML.
- **Respects `robots.txt`**: Follows standard exclusion protocols.
- **Depth-First Crawling**: Prioritizes exploring newly discovered links to dig deeper into a site's structure first.

### Search & Indexing
- **Semantic Search Ready**: Can generate and index vector embeddings using Google Gemini or a local HuggingFace model.
- **Graceful Quota Management**: Automatically detects when the Gemini API quota is exceeded and safely stops the crawl.

### Monitoring & Control
- **Interactive Dashboard**: A Streamlit-based web UI to monitor, control, and configure the crawler in real-time.
- **Advanced CLI**: Powerful command-line options for fine-grained control.

![screenshot_dashboard.png](media/screenshot_dashboard_en.png)

## Prerequisites

- Python 3.8+
- A running Meilisearch instance (v1.0 or higher).
- A Google Gemini API key (if using the embeddings feature).

## 1. Setting up Meilisearch

This crawler needs a Meilisearch instance to send its data to. The easiest way to get one running is with Docker.

1.  **Install Meilisearch**: Follow the official [Meilisearch Quick Start guide](https://www.meilisearch.com/docs/learn/getting_started/quick_start).
2.  **Run Meilisearch with a Master Key**:
    ```bash
    docker run -it --rm \
      -p 7700:7700 \
      -e MEILI_MASTER_KEY='a_master_key_that_is_long_and_secure' \
      -v $(pwd)/meili_data:/meili_data \
      ghcr.io/meilisearch/meilisearch:latest
    ```
3.  **Get your URL and API Key**:
    -   **URL**: `http://localhost:7700`
    -   **API Key**: The `MEILI_MASTER_KEY` you defined.

## 2. Setting up the Crawler

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/laurentftech/MeilisearchCrawler.git
    cd MeilisearchCrawler
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure environment variables**:
    Copy the example file and edit it with your credentials.
    ```bash
    cp .env.example .env
    ```
    Now, open `.env` and fill in:
    - `MEILI_URL`: Your Meilisearch instance URL.
    - `MEILI_KEY`: Your Meilisearch master key.
    - `GEMINI_API_KEY`: Your Google Gemini API key (optional, but required for the `--embeddings` feature).

5.  **Configure sites to crawl**:
    Copy the example sites file.
    ```bash
    cp config/sites.yml.example config/sites.yml
    ```
    You can now edit `config/sites.yml` to add the sites you want to index.

## 3. Running the Application

The project can be run in different modes: crawler, API server, or dashboard.

> 📖 **Complete API documentation available here:** [API_README.md](API_README.md)

### Crawler (Command-Line)

Run the `crawler.py` script to start indexing content.

```sh
python crawler.py # Runs an incremental crawl on all sites
```

**Common Options:**

-   `--force`: Forces a full re-crawl of all pages, ignoring the cache.
-   `--site "Site Name"`: Crawls only the specified site.
-   `--embeddings`: Activates the generation of Gemini embeddings for semantic search.
-   `--workers N`: Sets the number of parallel requests (e.g., `--workers 10`).
-   `--stats-only`: Displays cache statistics without running a crawl.

**Example:**
```sh
# Force a re-crawl of "Vikidia" with embeddings enabled
python crawler.py --force --site "Vikidia" --embeddings
```

### KidSearch API Server

Run the `api.py` script to start the FastAPI server, which exposes the search endpoint.

```sh
python api.py
```

The API will be available at `http://localhost:8000`. You can access the interactive documentation at `http://localhost:8000/docs`.

### Interactive Dashboard

The project includes a web-based dashboard to monitor and control the crawler in real-time.

**How to Run:**

1.  From the project root, run the following command:
    ```bash
    streamlit run dashboard/dashboard.py
    ```
2.  Open your web browser to the local URL provided by Streamlit (usually `http://localhost:8501`).

**Features:**

-   **🏠 Overview**: A real-time summary of the current crawl.
-   **🔧 Controls**: Start or stop the crawler, select sites, force re-crawls, and manage embeddings.
-   **🔍 Search**: A live search interface to test queries directly against your Meilisearch index.
-   **📊 Statistics**: Detailed statistics about your Meilisearch index.
-   **🌳 Page Tree**: An interactive visualization of your site's structure.
-   **⚙️ Configuration**: An interactive editor for the `sites.yml` file.
-   **🪵 Logs**: A live view of the crawler's log file.
-   **📈 API Metrics**: A dashboard to monitor API performance and metrics.

## 4. Configuration of `sites.yml`

The `config/sites.yml` file allows you to define a list of sites to crawl. Each site is an object with the following properties:

- `name`: (String) The name of the site, used for filtering in Meilisearch.
- `crawl`: (String) The starting URL for the crawl.
- `type`: (String) The type of content. Can be `html`, `json`, ou `mediawiki`.
- `max_pages`: (Integer) The maximum number of pages to crawl. Set to `0` or omit for no limit.
- `depth`: (Integer) For `html` sites, the maximum depth to follow links from the starting URL.
- `delay`: (Float, optional) A specific delay in seconds between requests for this site, overriding the default. Useful for sensitive servers.
- `selector`: (String, optional) For `html` sites, a specific CSS selector (e.g., `.main-article`) to pinpoint the main content area.
- `lang`: (String, optional) For `json` sources, specifies the language of the content (e.g., "en", "fr").
- `exclude`: (List of strings) A list of URL patterns to completely ignore.
- `no_index`: (List of strings) A list of URL patterns to visit for link discovery but not to index.

### `html` Type
This is the standard type for crawling regular websites. It will start at the `crawl` URL and follow links up to the specified `depth`.

### `json` Type
For this type, you must also provide a `json` object with the following mapping:
- `root`: The key in the JSON response that contains the list of items.
- `title`: The key for the item's title.
- `url`: A template for the item's URL. You can use `{{key_name}}` to substitute a value from the item.
- `content`: A comma-separated list of keys for the content.
- `image`: The key for the item's main image URL.

### `mediawiki` Type
This type is optimized for sites running on MediaWiki software (like Wikipedia, Vikidia). It uses the MediaWiki API to efficiently fetch all pages, avoiding the need for traditional link-by-link crawling.
- The `crawl` URL should be the base URL of the wiki (e.g., `https://fr.vikidia.org`).
- `depth` and `selector` are not used for this type.

## 5. Dashboard Authentication

The dashboard supports multiple authentication methods. You can enable one or more.

### Choosing Authentication Providers

The `AUTH_PROVIDERS` environment variable controls which authentication methods are enabled.

-   **Explicit Configuration (Recommended)**: To avoid ambiguity, explicitly list the providers you want to use.
    ```bash
    # Example: Enable Proxy and Simple Password
    AUTH_PROVIDERS=proxy,simple
    ```
    -   To use **only one method** (like proxy), set it as the only provider:
        ```bash
        # Force ONLY proxy authentication
        AUTH_PROVIDERS=proxy
        ```

-   **Automatic Detection**: If `AUTH_PROVIDERS` is left empty, the application will automatically enable any provider that has its corresponding environment variables set. This can be useful for testing but is not recommended for production, as it might enable more methods than you intend.

### 🛡️ Proxy Authentication (Recommended for Production)

This is the most secure and flexible method. It delegates authentication to a reverse proxy (like Caddy with AuthCrunch) that handles user authentication.

**How it Works:**
1. The proxy (Caddy with AuthCrunch) authenticates the user via OIDC.
2. AuthCrunch automatically injects user information into HTTP headers using the `inject headers with claims` directive.
3. The dashboard reads these headers to identify the authenticated user.
4. The dashboard calls the API to generate a JWT token for subsequent API requests.

This method is highly secure as it prevents direct access to the dashboard and leverages the proxy's authentication mechanisms.

**Configuration (`.env`):**
```bash
# Force proxy as the only authentication method
AUTH_PROVIDERS=proxy

# Enable proxy authentication
AUTH_PROXY_ENABLED=true

# URL to redirect to on logout (e.g., the proxy's logout endpoint)
AUTH_PROXY_LOGOUT_URL=/

# JWT secret for API authentication (generate with command below)
JWT_SECRET_KEY=your_jwt_secret_here

# API URL for Dashboard to communicate with API
API_URL=http://kidsearch-all:8080/api
```

**How to Generate JWT Secret:**
```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Or use the provided script:
```sh
python scripts/generate_secrets.py
```

**Example with Caddy & AuthCrunch:**
```caddy
{
    security {
        authorization policy admin_only {
            set auth url https://auth.example.com
            allow roles authp/admin
            crypto key verify {env.JWT_SECRET_KEY}

            # IMPORTANT: This directive injects user claims into HTTP headers
            inject headers with claims
        }
    }
}

# === KIDSEARCH DASHBOARD ===
https://kidsearch-admin.example.com {
    # 1. Authorize the user with AuthCrunch
    authorize with admin_only

    # 2. Configure logging
    log {
        output file /data/logs/kidsearch-dashboard-access.log
    }

    # 3. Reverse proxy to the dashboard
    # AuthCrunch automatically injects these headers:
    # - X-Token-User-Email
    # - X-Token-User-Name
    # - X-Token-Subject
    # - X-Token-User-Roles
    reverse_proxy kidsearch-all:8501 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}

        # WebSocket support for Streamlit
        header_up Connection {>Connection}
        header_up Upgrade {>Upgrade}
    }
}
```

**Documentation:**
- Full Caddyfile example: `docs/Caddyfile`
- Complete guide: `docs/AUTHENTICATION_FINAL.md`
- Deployment checklist: `docs/DEPLOYMENT_CHECKLIST.md`

### 🧩 OIDC, Google, GitHub & Simple Password

You can also enable other providers. If multiple are enabled via `AUTH_PROVIDERS`, users will see a selection screen.

- **OIDC**: `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`
- **Google**: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
- **GitHub**: `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`
- **Simple Password**: `DASHBOARD_PASSWORD`

### Email Whitelist

The `ALLOWED_EMAILS` variable restricts access for OAuth and Proxy methods:
- If empty: all authenticated users can access.
- If set: only listed emails can access the dashboard.
```bash
ALLOWED_EMAILS=user1@gmail.com,user2@example.com
```

### Diagnosing Authentication Issues

If you're having trouble with login, use the diagnostic tools:

**1. Check your configuration:**
```bash
python3 check_auth_config.py
```

**2. Test a specific email:**
```bash
python3 check_auth_config.py user@example.com
```

**3. Monitor authentication logs:**
```bash
tail -f data/logs/auth.log
```
The logs will show ✅ successful logins and ❌ failed logins with detailed reasons.

## 6. Running Tests

To run the test suite, first install the development dependencies:

```bash
pip install pytest
```

Then, run the tests:
```bash
pytest
```
