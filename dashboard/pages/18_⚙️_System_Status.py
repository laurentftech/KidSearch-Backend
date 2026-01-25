import streamlit as st
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.src.config import TYPESENSE_URL, TYPESENSE_API_KEY, INDEX_NAME
from dashboard.src.typesense_client import get_typesense_client

st.set_page_config(page_title="System Status", page_icon="⚙️", layout="wide")

st.title("⚙️ System Status")

# Typesense Status
st.header("🔍 Typesense Search Engine")

client = get_typesense_client()

if client:
    try:
        # Get health status (using collections retrieval as a proxy for health check)
        # This avoids issues with client.operations.perform() in some versions
        client.collections.retrieve()
        st.success("✅ Typesense is running and healthy")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Server URL", TYPESENSE_URL)
        with col2:
            st.metric("Status", "OK", delta="Healthy")

        # Check collection
        st.subheader("📊 Collection Status")
        try:
            collection = client.collections[INDEX_NAME].retrieve()
            st.success(f"✅ Collection '{INDEX_NAME}' exists and is ready")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Documents", f"{collection.get('num_documents', 0):,}")
            with col2:
                st.metric("Fields", len(collection.get('fields', [])))
            with col3:
                # Check if vector search is enabled
                has_vectors = any(f.get('name') == 'embedding_vec' for f in collection.get('fields', []))
                st.metric("Vector Search", "Enabled" if has_vectors else "Disabled")

            # Show schema details
            with st.expander("📋 View Collection Schema"):
                st.json(collection)

            # Recreate collection option
            st.subheader("🔄 Collection Management")

            # Check if embeddings are configured but not in collection
            embedding_provider = os.getenv("EMBEDDING_PROVIDER", "none").lower()
            embeddings_configured = embedding_provider in ["gemini", "huggingface", "sentence_transformer"]

            if not has_vectors and embeddings_configured:
                st.warning("🚨 La configuration des embeddings est manquante dans le schéma de la collection.")
                st.info("Pour activer la recherche vectorielle hybride, vous devez recréer la collection avec les embeddings activés.")

            with st.expander("⚠️ Recréer la collection (DANGER)"):
                st.warning("⚠️ **ATTENTION**: Cette action va supprimer tous les documents existants!")
                st.info("💡 La collection sera recréée avec les embeddings si EMBEDDING_PROVIDER est configuré dans .env")

                st.caption("Les caches et statistiques suivants seront aussi supprimés:")
                st.code("""
• data/crawler_cache.db
• data/api_stats.db
• data/cse_cache.db
• data/crawl_history.json
• data/status.json
                """)

                # Ask for confirmation
                confirm_text = st.text_input(
                    "Tapez 'RECREER' pour confirmer:",
                    key="confirm_recreate"
                )

                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("🗑️ Recréer la collection", type="primary", disabled=(confirm_text != "RECREER")):
                        try:
                            # Clear all caches and stats
                            import os
                            cache_files = [
                                "data/crawler_cache.db",
                                "data/api_stats.db",
                                "data/cse_cache.db",
                                "data/crawl_history.json",
                                "data/status.json"
                            ]

                            files_deleted = []
                            for cache_file in cache_files:
                                try:
                                    if os.path.exists(cache_file):
                                        os.remove(cache_file)
                                        files_deleted.append(cache_file)
                                except Exception as e:
                                    st.warning(f"⚠️ Impossible de supprimer {cache_file}: {e}")

                            if files_deleted:
                                st.info(f"✓ {len(files_deleted)} fichier(s) de cache supprimé(s)")

                            # Drop existing collection
                            client.collections[INDEX_NAME].delete()
                            st.info(f"✓ Collection '{INDEX_NAME}' supprimée")

                            # Get embedding dimensions from the API
                            embedding_dimensions = 384  # Default for paraphrase-multilingual-MiniLM-L12-v2

                            # Define new schema
                            schema = {
                                'name': INDEX_NAME,
                                'enable_nested_fields': True,
                                'fields': [
                                    {'name': 'id', 'type': 'string'},
                                    {'name': 'site', 'type': 'string', 'facet': True},
                                    {'name': 'url', 'type': 'string'},
                                    {'name': 'title', 'type': 'string'},
                                    {'name': 'excerpt', 'type': 'string'},
                                    {'name': 'content', 'type': 'string'},
                                    {'name': 'images', 'type': 'object[]'},
                                    {'name': 'lang', 'type': 'string', 'facet': True},
                                    {'name': 'timestamp', 'type': 'int64'},
                                    {'name': 'indexed_at', 'type': 'string'},
                                    {'name': 'last_crawled_at', 'type': 'string'},
                                    {'name': 'content_hash', 'type': 'string'},
                                    {'name': 'has_embedding', 'type': 'bool', 'optional': True},
                                ]
                            }

                            # Add vector fields if embeddings enabled
                            if embeddings_configured:
                                schema['fields'].extend([
                                    {'name': 'embedding_vec', 'type': 'float[]', 'num_dim': embedding_dimensions},
                                    {'name': 'embedding_provider', 'type': 'string', 'optional': True},
                                    {'name': 'embedding_model', 'type': 'string', 'optional': True},
                                    {'name': 'embedding_dimensions', 'type': 'int32', 'optional': True},
                                ])

                            # Create new collection
                            client.collections.create(schema)
                            st.success(f"✅ Collection '{INDEX_NAME}' recréée avec succès!")
                            if embeddings_configured:
                                st.success("✅ Les embeddings sont maintenant activés!")
                                st.info("💡 Relancez le crawler pour indexer les pages avec les embeddings.")

                            # Show cache cleanup summary
                            if files_deleted:
                                st.success(f"✅ Caches et statistiques nettoyés ({len(files_deleted)} fichiers)")

                            st.rerun()

                        except Exception as recreate_error:
                            st.error(f"❌ Erreur lors de la recréation: {recreate_error}")

                with col2:
                    if confirm_text and confirm_text != "RECREER":
                        st.caption("❌ Texte de confirmation incorrect")

        except Exception:
            st.warning(f"⚠️ Collection '{INDEX_NAME}' does not exist")
            st.info("The collection will be created automatically when you start the crawler or API server.")

            if st.button("🔨 Create Collection Now"):
                try:

                    # Get embedding settings
                    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "none").lower()
                    embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))

                    # Define schema
                    schema = {
                        'name': INDEX_NAME,
                        'enable_nested_fields': True,
                        'fields': [
                            {'name': 'id', 'type': 'string'},
                            {'name': 'site', 'type': 'string', 'facet': True},
                            {'name': 'url', 'type': 'string'},
                            {'name': 'title', 'type': 'string'},
                            {'name': 'excerpt', 'type': 'string'},
                            {'name': 'content', 'type': 'string'},
                            {'name': 'images', 'type': 'object[]'},
                            {'name': 'lang', 'type': 'string', 'facet': True},
                            {'name': 'timestamp', 'type': 'int64'},
                            {'name': 'indexed_at', 'type': 'string'},
                            {'name': 'last_crawled_at', 'type': 'string'},
                            {'name': 'content_hash', 'type': 'string'},
                            {'name': 'has_embedding', 'type': 'bool', 'optional': True},
                        ]
                    }

                    # Add vector fields if embeddings enabled
                    if embedding_provider in ["gemini", "huggingface", "sentence_transformer"]:
                        schema['fields'].extend([
                            {'name': 'embedding_vec', 'type': 'float[]', 'num_dim': embedding_dimensions},
                            {'name': 'embedding_provider', 'type': 'string', 'optional': True},
                            {'name': 'embedding_model', 'type': 'string', 'optional': True},
                            {'name': 'embedding_dimensions', 'type': 'int32', 'optional': True},
                        ])

                    # Create collection
                    client.collections.create(schema)
                    st.success(f"✅ Collection '{INDEX_NAME}' created successfully!")
                    st.rerun()

                except Exception as create_error:
                    st.error(f"❌ Failed to create collection: {create_error}")

    except Exception as e:
        st.error(f"❌ Failed to connect to Typesense: {e}")
        st.info("Please check that Typesense is running and the connection settings are correct.")
else:
    st.error("❌ Could not connect to Typesense")
    st.info("Please check your TYPESENSE_URL and TYPESENSE_API_KEY in the .env file")

# Environment Variables
st.header("🌍 Environment Configuration")

with st.expander("View Current Settings"):
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Typesense Settings")
        st.code(f"""
TYPESENSE_URL={TYPESENSE_URL}
TYPESENSE_API_KEY={'*' * len(TYPESENSE_API_KEY) if TYPESENSE_API_KEY else 'Not set'}
INDEX_NAME={INDEX_NAME}
        """)

    with col2:
        st.subheader("Embedding Settings")
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "none")
        embedding_dimensions = os.getenv("EMBEDDING_DIMENSIONS", "768")
        st.code(f"""
EMBEDDING_PROVIDER={embedding_provider}
EMBEDDING_DIMENSIONS={embedding_dimensions}
        """)

# API Status
st.header("🚀 API Server Status")

api_url = os.getenv("API_URL", "http://localhost:8080/api")

try:
    import requests
    # Correctly construct health URL by appending /health to the API base URL
    # Ensure we don't have double slashes
    base_url = api_url.rstrip('/')
    health_url = f"{base_url}/health"
    
    response = requests.get(health_url, timeout=5)
    if response.status_code == 200:
        st.success("✅ API server is running")
        st.metric("API URL", api_url)
    else:
        st.warning(f"⚠️ API returned status code: {response.status_code}")
        st.caption(f"Tried to connect to: {health_url}")
except Exception:
    st.warning("⚠️ API server is not responding")
    st.caption(f"Tried to connect to: {health_url}")
