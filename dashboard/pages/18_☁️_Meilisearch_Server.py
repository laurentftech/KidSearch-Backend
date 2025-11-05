import streamlit as st
import sys
from pathlib import Path
import os
import time
import requests
from meilisearch_python_sdk.errors import MeilisearchApiError, MeilisearchTimeoutError
from meilisearch_python_sdk.models.settings import MeilisearchSettings
from dashboard.src.config import MEILI_URL, MEILI_KEY, INDEX_NAME
from dashboard.src.meilisearch_client import get_meili_client
from dashboard.src.i18n import get_translator

# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget
check_authentication()

# Initialize translator
if 'lang' not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

st.set_page_config(page_title="Meilisearch Server", page_icon="☁️", layout="wide")

st.title("☁️ Meilisearch Server Configuration")

# --- Connection Status ---
st.header("📡 Connection Status")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Meilisearch URL", MEILI_URL or "Not configured")
with col2:
    st.metric("Index Name", INDEX_NAME)
with col3:
    api_key_status = "✅ Configured" if MEILI_KEY else "❌ Missing"
    st.metric("API Key", api_key_status)

if not MEILI_URL or not MEILI_KEY:
    st.error("⚠️ MEILI_URL and MEILI_KEY must be set in your .env file.")
    st.code("""
# Add these to your .env file:
MEILI_URL=http://localhost:7700
MEILI_KEY=your_master_key
INDEX_NAME=kidsearch
    """)
    st.stop()

# Get Meilisearch client
client = get_meili_client()
if not client:
    st.error("❌ Failed to connect to Meilisearch. Please check your configuration.")
    st.stop()

try:
    health = client.health()
    st.success(f"✅ Connected to Meilisearch - Status: {health.status}")
except Exception as e:
    st.error(f"❌ Connection error: {e}")
    st.stop()

# --- Current Index Information ---
st.header("📊 Current Index Information")

try:
    index = client.index(INDEX_NAME)
    stats = index.get_stats()
    settings = index.get_settings()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Documents", f"{stats.number_of_documents:,}")
    with col2:
        st.metric("Index Size", f"{stats.field_distribution}")
    with col3:
        st.metric("Is Indexing", "Yes" if stats.is_indexing else "No")
    with col4:
        # Count embedders
        embedder_count = len(settings.embedders) if settings.embedders else 0
        st.metric("Embedders", embedder_count)

    # Show current embedders configuration
    if settings.embedders:
        with st.expander("🔍 View Current Embedders Configuration", expanded=False):
            for embedder_name, embedder_config in settings.embedders.items():
                st.write(f"**{embedder_name}:**")
                st.json(embedder_config.model_dump() if hasattr(embedder_config, 'model_dump') else embedder_config)

    # Show ranking rules
    with st.expander("📏 View Current Ranking Rules", expanded=False):
        if settings.ranking_rules:
            st.write(settings.ranking_rules)
        else:
            st.info("No custom ranking rules configured")

    # Show filterable/sortable attributes
    with st.expander("🔧 View Filterable & Sortable Attributes", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Filterable Attributes:**")
            st.write(settings.filterable_attributes if settings.filterable_attributes else "All attributes")
        with col2:
            st.write("**Sortable Attributes:**")
            st.write(settings.sortable_attributes if settings.sortable_attributes else "None")

except MeilisearchApiError as e:
    if e.code == "index_not_found":
        st.warning(f"⚠️ Index '{INDEX_NAME}' does not exist yet. You can create it below.")
    else:
        st.error(f"Error accessing index: {e}")

# --- Index Configuration ---
st.header("⚙️ Index Configuration")

tab1, tab2, tab3, tab4 = st.tabs(["📝 Create/Configure Index", "🧠 Embeddings", "📏 Ranking Rules", "🔧 Attributes"])

with tab1:
    st.subheader("Create and Configure Index")

    col1, col2 = st.columns(2)
    with col1:
        create_index_name = st.text_input("Index Name", value=INDEX_NAME, key="create_index_name")
        primary_key = st.text_input("Primary Key", value="id", help="The primary key field for documents")

    if st.button("🔨 Create Index", type="primary"):
        if not create_index_name:
            st.error("Index name is required.")
        else:
            with st.spinner("Creating index..."):
                try:
                    # Check if index already exists
                    try:
                        client.get_index(create_index_name)
                        st.info(f"Index '{create_index_name}' already exists.")
                    except MeilisearchApiError as e:
                        if e.code == "index_not_found":
                            st.info(f"Creating index '{create_index_name}'...")

                            # Use direct HTTP request for reliability
                            headers = {"Authorization": f"Bearer {MEILI_KEY}"}
                            response = requests.post(
                                f"{MEILI_URL}/indexes",
                                headers=headers,
                                json={"uid": create_index_name, "primaryKey": primary_key}
                            )
                            response.raise_for_status()

                            # Wait a moment for index creation to complete
                            time.sleep(1)

                            st.success(f"✅ Index '{create_index_name}' created successfully!")
                        else:
                            raise e
                except requests.exceptions.RequestException as e:
                    st.error(f"Error creating index: {e}")
                except Exception as e:
                    st.error(f"Error creating index: {e}")

with tab2:
    st.subheader("Configure Embeddings")

    # Read current embedding provider from env
    current_provider = os.getenv("EMBEDDING_PROVIDER", "none").lower()
    gemini_api_key_env = os.getenv("GEMINI_API_KEY", "")

    st.info(f"Current embedding provider from .env: **{current_provider.upper()}**")

    embedding_provider = st.selectbox(
        "Embedding Provider",
        ["None", "Gemini", "HuggingFace"],
        index={"none": 0, "gemini": 1, "huggingface": 2}.get(current_provider, 0)
    )

    embedding_dimensions = 768  # Default

    if embedding_provider == "Gemini":
        st.info("Gemini uses 768 dimensions with text-embedding-004 model")
        gemini_api_key = st.text_input(
            "Gemini API Key",
            value=gemini_api_key_env,
            type="password",
            help="Required for the 'query' embedder. Will use value from .env if available."
        )
    elif embedding_provider == "HuggingFace":
        st.info("HuggingFace embeddings are calculated by the crawler or API backend")
        huggingface_model = os.getenv("HUGGINGFACE_MODEL", "intfloat/multilingual-e5-small")
        st.code(f"Model: {huggingface_model}")
        # For multilingual-e5-small, dimensions are 384
        embedding_dimensions = st.number_input("Embedding Dimensions", value=384, min_value=1, max_value=4096)

    if st.button("🧠 Configure Embeddings", type="primary"):
        with st.spinner("Configuring embeddings..."):
            try:
                # 1. Try to enable multimodal feature (required for vector search), but don't fail if it's deprecated
                if embedding_provider != "None":
                    st.info("Enabling multimodal feature (required for vector search)...")
                    try:
                        headers = {
                            "Authorization": f"Bearer {MEILI_KEY}",
                            "Content-Type": "application/json"
                        }
                        # Enable multimodal and vectorStoreSetting for vector search support
                        payload = {"multimodal": True, "vectorStoreSetting": True}
                        r = requests.patch(f"{MEILI_URL}/experimental-features", json=payload, headers=headers)
                        r.raise_for_status()
                        st.success("✅ Multimodal feature enabled.")
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code in [400, 404]:
                            st.warning(f"⚠️ Could not enable experimental features (status: {e.response.status_code}). This is expected on recent Meilisearch versions. Continuing...")
                        else:
                            raise e # Re-raise other HTTP errors

                # 2. Configure embedders
                index = client.index(INDEX_NAME)

                if embedding_provider == "None":
                    settings_payload = {"embedders": {}}
                    st.info("Removing all embedders (text search only)")

                elif embedding_provider == "Gemini":
                    if not gemini_api_key:
                        st.error("Gemini API Key is required!")
                        st.stop()

                    settings_payload = {
                        "embedders": {
                            "default": {"source": "userProvided", "dimensions": 768},
                            "query": {
                                "source": "rest",
                                "url": "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent",
                                "apiKey": gemini_api_key,
                                "request": {
                                    "model": "models/text-embedding-004",
                                    "content": {"parts": [{"text": "{{text}}"}]}
                                },
                                "response": {"embedding": "embedding.values"},
                                "dimensions": 768
                            }
                        }
                    }
                    st.info("Configuring Gemini embedders (default: userProvided, query: REST API)")

                elif embedding_provider == "HuggingFace":
                    settings_payload = {
                        "embedders": {
                            "default": {"source": "userProvided", "dimensions": embedding_dimensions}
                        }
                    }
                    st.info(f"Configuring HuggingFace embedder with {embedding_dimensions} dimensions")

                # Apply settings
                settings_model = MeilisearchSettings.model_validate(settings_payload)
                task = index.update_settings(settings_model)

                st.info(f"Task submitted (UID: {task.task_uid}), waiting for completion...")

                timeout = 120000 if embedding_provider == "Gemini" else 30000
                try:
                    final_task = client.wait_for_task(task.task_uid, timeout_in_ms=timeout)

                    if final_task.status == "succeeded":
                        st.success("✅ Embeddings configured successfully!")
                        st.balloons()
                    else:
                        st.error(f"Configuration failed: {final_task.status}")
                        if final_task.error:
                            st.error(f"Error: {final_task.error}")

                except MeilisearchTimeoutError:
                    st.warning("⏱️ Timeout exceeded, checking task status...")
                    task_status = client.get_task(task.task_uid)
                    st.info(f"Current status: {task_status.status}")

            except Exception as e:
                st.error(f"Error configuring embeddings: {e}")
                import traceback
                st.code(traceback.format_exc())

with tab3:
    st.subheader("Configure Ranking Rules")

    st.info("Ranking rules determine the order in which search results are ranked. For hybrid search, 'vector' should be at the end.")

    default_ranking_rules = ["words", "typo", "proximity", "attribute", "sort", "exactness", "vector"]

    # Allow customization
    enable_hybrid = st.checkbox("Enable Hybrid Search (include 'vector' rule)", value=True)

    if enable_hybrid:
        ranking_rules = default_ranking_rules
    else:
        ranking_rules = [r for r in default_ranking_rules if r != "vector"]

    st.code("\n".join(ranking_rules))

    if st.button("📏 Update Ranking Rules", type="primary"):
        with st.spinner("Updating ranking rules..."):
            try:
                index = client.index(INDEX_NAME)
                task = index.update_ranking_rules(ranking_rules)
                client.wait_for_task(task.task_uid)
                st.success("✅ Ranking rules updated successfully!")
            except Exception as e:
                st.error(f"Error updating ranking rules: {e}")

with tab4:
    st.subheader("Configure Filterable and Sortable Attributes")

    st.warning("⚠️ **Performance Warning**: Never include long text fields (title, content) in filterable attributes. This severely impacts search performance!")

    st.info("Configure which attributes can be used for filtering and sorting in search queries.")

    # Quick performance fix button
    if st.button("⚡ Apply Performance Optimization", type="primary"):
        with st.spinner("Optimizing filterable attributes..."):
            try:
                index = client.index(INDEX_NAME)

                # Optimal filterable attributes (exclude title and content)
                optimal_filterable = [
                    "site",
                    "timestamp",
                    "lang",
                    "indexed_at",
                    "last_crawled_at",
                    "embedding_provider",
                    "embedding_model",
                    "embedding_dimensions",
                    "_vectors.default"
                ]

                task = index.update_filterable_attributes(optimal_filterable)
                client.wait_for_task(task.task_uid)

                st.success("✅ Filterable attributes optimized! Search performance should improve significantly.")
                st.info("Removed: title, content (long text fields that slow down filtering)")
                st.balloons()
                time.sleep(2)
                st.rerun()

            except Exception as e:
                st.error(f"Error optimizing attributes: {e}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Filterable Attributes**")
        # Optimized default (without title and content)
        default_filterable = [
            "site",
            "timestamp",
            "lang",
            "indexed_at",
            "last_crawled_at",
            "embedding_provider",
            "embedding_model",
            "embedding_dimensions",
            "_vectors.default"
        ]
        filterable_attrs = st.text_area(
            "Filterable Attributes (one per line)",
            value="\n".join(default_filterable),
            height=200,
            help="⚠️ Do NOT include 'title' or 'content' - they severely impact performance!"
        )

    with col2:
        st.write("**Sortable Attributes**")
        default_sortable = ["timestamp", "indexed_at", "last_crawled_at"]
        sortable_attrs = st.text_area(
            "Sortable Attributes (one per line)",
            value="\n".join(default_sortable),
            height=200
        )

    if st.button("🔧 Update Attributes", type="primary"):
        with st.spinner("Updating attributes..."):
            try:
                index = client.index(INDEX_NAME)

                # Update filterable attributes
                filterable_list = [attr.strip() for attr in filterable_attrs.split("\n") if attr.strip()]
                task1 = index.update_filterable_attributes(filterable_list)

                # Update sortable attributes
                sortable_list = [attr.strip() for attr in sortable_attrs.split("\n") if attr.strip()]
                task2 = index.update_sortable_attributes(sortable_list)

                # Wait for both tasks
                client.wait_for_task(task1.task_uid)
                client.wait_for_task(task2.task_uid)

                st.success("✅ Attributes updated successfully!")

            except Exception as e:
                st.error(f"Error updating attributes: {e}")

# --- Advanced Operations ---
st.header("⚡ Advanced Operations")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🗑️ Delete Index")
    st.warning("This will permanently delete the index and all its documents!")

    confirm_delete = st.text_input("Type index name to confirm deletion:", key="confirm_delete")

    if st.button("Delete Index", type="secondary"):
        if confirm_delete == INDEX_NAME:
            with st.spinner("Deleting index..."):
                try:
                    index = client.index(INDEX_NAME)
                    task = index.delete()
                    client.wait_for_task(task.task_uid)
                    st.success(f"✅ Index '{INDEX_NAME}' deleted successfully!")
                except Exception as e:
                    st.error(f"Error deleting index: {e}")
        else:
            st.error("Index name doesn't match. Deletion cancelled.")

with col2:
    st.subheader("🔄 Reset Settings")
    st.warning("This will reset all index settings to defaults!")

    if st.button("Reset Settings", type="secondary"):
        with st.spinner("Resetting settings..."):
            try:
                index = client.index(INDEX_NAME)
                task = index.reset_settings()
                client.wait_for_task(task.task_uid)
                st.success("✅ Settings reset successfully!")
            except Exception as e:
                st.error(f"Error resetting settings: {e}")
