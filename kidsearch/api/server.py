"""
FastAPI server for KidSearch backend.
Provides unified search API combining Meilisearch and Google CSE with reranking.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from .routes import auth, health, metrics, search
from .services.crawler_status import get_crawl_status
from .services.cse_client import CSEClient
from .services.merger import SearchMerger
from .services.reranker import HuggingFaceAPIReranker
from .services.safety import SafetyFilter
from .services.stats_db import StatsDatabase
from .services.typesense_client import TypesenseClient
from .services.wiki_client import WikiClient
from .state import AppState
from ..embeddings import create_embedding_provider

logger = logging.getLogger(__name__)


def get_crawler_avg_embedding_time_per_page() -> float:
    """Calculate average embedding time per page from crawler status."""
    status = get_crawl_status()
    total_time = status.get("total_embedding_time_ms", 0)
    pages = status.get("pages_indexed", 0)
    return total_time / pages if pages > 0 else 0


def get_crawler_avg_indexing_time_per_page() -> float:
    """Calculate average indexing time per page from crawler status."""
    status = get_crawl_status()
    total_time = status.get("total_indexing_time_ms", 0)
    pages = status.get("pages_indexed", 0)
    return total_time / pages if pages > 0 else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app."""
    app.state = AppState()

    # Configure logging for worker processes
    # Each worker is a separate process, so we need to configure logging here
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Get or create the kidsearch logger
    app_logger = logging.getLogger("kidsearch")
    app_logger.setLevel(log_level)

    # Add a console handler if not already present
    if not app_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        formatter = logging.Formatter(
            "%(asctime)s - [API] - %(levelname)s:%(filename)s:%(lineno)d:%(funcName)s: %(message)s"
        )
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

    logger.info("Starting KidSearch API backend...")

    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    # Initialize services
    try:
        typesense_url = os.getenv("TYPESENSE_URL", "http://localhost:8108")
        typesense_api_key = os.getenv("TYPESENSE_API_KEY", "masterKey")
        index_name = os.getenv("INDEX_NAME", "kidsearch")
        app.state.typesense_client = TypesenseClient(typesense_url, typesense_api_key, index_name)
        await app.state.typesense_client.connect()
        logger.info("✓ Typesense client initialized")
    except Exception as e:
        logger.critical(f"✗✗✗ CRITICAL: Typesense initialization failed: {e}")

    # Initialize multiple wiki clients (support WIKI_1_*, WIKI_2_*, etc.)
    app.state.wiki_clients = []
    wiki_index = 1
    while True:
        prefix = f"WIKI_{wiki_index}_" if wiki_index > 1 else "WIKI_"
        api_url = os.getenv(f"{prefix}API_URL")
        site_url = os.getenv(f"{prefix}SITE_URL")
        site_name = os.getenv(f"{prefix}SITE_NAME")

        if api_url and site_url and site_name:
            # Clean values (remove quotes if present)
            api_url = api_url.strip().strip('"').strip("'")
            site_url = site_url.strip().strip('"').strip("'")
            site_name = site_name.strip().strip('"').strip("'")

            try:
                wiki_client = WikiClient(api_url=api_url, site_url=site_url, site_name=site_name)
                app.state.wiki_clients.append(wiki_client)
                logger.info(f"✓ Wiki client #{wiki_index} initialized: {site_name}")
            except Exception as e:
                logger.error(f"✗ Failed to initialize wiki client #{wiki_index}: {e}", exc_info=True)
        elif wiki_index == 1:
            # No wiki configured at all
            logger.info("No wiki clients configured")
            break
        else:
            # No more wikis to configure
            logger.info(f"✓ Total wiki clients initialized: {len(app.state.wiki_clients)}")
            break

        wiki_index += 1

    app.state.safety_filter = SafetyFilter()
    app.state.merger = SearchMerger(float(os.getenv("MEILISEARCH_WEIGHT", "0.7")), float(os.getenv("CSE_WEIGHT", "0.3")))
    app.state.cse_client = CSEClient(api_key=os.getenv("GOOGLE_CSE_API_KEY"), search_engine_id=os.getenv("GOOGLE_CSE_ID")) if os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_API_KEY") != "your_google_api_key_here" else None

    if os.getenv("RERANKING_ENABLED", "false").lower() == "true":
        try:
            app.state.embedding_provider = create_embedding_provider()
            app.state.reranker = HuggingFaceAPIReranker()
            logger.info("✓ Reranker and embedding provider initialized.")
        except Exception as e:
            logger.error(f"✗ Reranker/embedding setup failed: {e}", exc_info=True)
    else:
        logger.info("Reranking is disabled.")

    try:
        app.state.stats_db = StatsDatabase()
        logger.info("✓ Stats database initialized")
        # --- Custom Prometheus Metrics ---
        Gauge("avg_search_time_ms", "Average search time in ms").set_function(lambda: app.state.stats_db.get_avg_search_time())
        Gauge("avg_typesense_time_ms", "Average Typesense query time in ms").set_function(lambda: app.state.stats_db.get_avg_typesense_time())
        Gauge("avg_cse_time_ms", "Average Google CSE query time in ms").set_function(lambda: app.state.stats_db.get_avg_cse_time())
        Gauge("avg_wiki_time_ms", "Average MediaWiki query time in ms").set_function(lambda: app.state.stats_db.get_avg_wiki_time())
        Gauge("avg_reranking_time_ms", "Average reranking time in ms").set_function(lambda: app.state.stats_db.get_avg_reranking_time())
        Gauge("crawler_running", "Indicates if the crawler is running").set_function(lambda: get_crawl_status().get("running", 0))
        Gauge("crawler_avg_embedding_time_per_page_ms", "Average crawler embedding time per page in ms").set_function(get_crawler_avg_embedding_time_per_page)
        Gauge("crawler_avg_indexing_time_per_page_ms", "Average crawler indexing time per page in ms").set_function(get_crawler_avg_indexing_time_per_page)
        logger.info("✓ Custom Prometheus metrics initialized")
    except Exception as e:
        logger.warning(f"✗ Failed to initialize stats database or metrics: {e}")

    logger.info("KidSearch API backend started successfully")
    yield
    logger.info("Shutting down KidSearch API backend...")
    # --- Clean shutdown of HTTP clients ---
    try:
        tasks = []
        # Typesense client
        if hasattr(app.state, "typesense_client") and hasattr(app.state.typesense_client, "close"):
            tasks.append(app.state.typesense_client.close())

        # Google CSE client
        if hasattr(app.state, "cse_client") and app.state.cse_client and hasattr(app.state.cse_client, "close"):
            tasks.append(app.state.cse_client.close())

        # Wiki clients (list)
        if hasattr(app.state, "wiki_clients"):
            for wiki_client in app.state.wiki_clients:
                if hasattr(wiki_client, "close"):
                    tasks.append(wiki_client.close())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("✓ All HTTP clients closed successfully.")
    except Exception as e:
        logger.warning(f"✗ Error during client shutdown: {e}", exc_info=True)

def create_app() -> FastAPI:
    app = FastAPI(
        title="KidSearch API",
        description="Backend API for KidSearch - Safe search engine for children",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    Instrumentator().instrument(app).expose(app, endpoint="/api/metrics")
    
    # For development, allow localhost
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    frontend_urls = os.getenv("FRONTEND_URL")
    if frontend_urls:
        # Split by comma to allow multiple frontend URLs
        origins.extend([url.strip() for url in frontend_urls.split(',')])

    logger.info(f"Configuring CORS with allowed origins: {origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(search.router, prefix="/api", tags=["Search"])
    app.include_router(metrics.router, prefix="/api", tags=["Metrics"])
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return app

app = create_app()
