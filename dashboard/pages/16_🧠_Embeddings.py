import streamlit as st
import sys
from pathlib import Path
import time

from dashboard.src.i18n import get_translator
from dashboard.src.typesense_client import (
    get_typesense_client,
    count_documents,
    check_collection_exists,
)
from dashboard.src.config import INDEX_NAME
from typesense.exceptions import TypesenseClientError

# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget

check_authentication()

# Initialiser le traducteur
if "lang" not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

st.title(t("embeddings.title"))
st.markdown(t("embeddings.subtitle"))
st.info(t("embeddings.info_what_are_embeddings"), icon="🧠")

# --- Typesense Collection Check ---
client = get_typesense_client()
if client:
    if not check_collection_exists(client, INDEX_NAME):
        st.warning(f"⚠️ La collection '{INDEX_NAME}' n'existe pas.")
        st.info("Veuillez la créer pour gérer les embeddings.")
        st.page_link(
            "pages/17_⚙️_System_Status.py",
            label="Aller à la configuration du serveur",
            icon="⚙️",
        )
        st.stop()
else:
    st.error(
        "La connexion à Typesense n'est pas configurée. Vérifiez votre fichier .env."
    )
    st.stop()


# --- Fonctions de la page ---
@st.cache_data(ttl=10, show_spinner=t("embeddings.loading_stats_spinner"))
def get_embedding_stats(force_refresh_key=None):
    """Récupère les statistiques sur les embeddings depuis Typesense."""
    from dashboard.src.typesense_client import (
        get_collection_stats,
        get_collection_schema,
    )

    client = get_typesense_client()
    if not client:
        return None
    try:
        # Get collection schema to check for vector fields
        schema = get_collection_schema(client, INDEX_NAME)
        if not schema:
            return None

        # Check if collection has vector fields configured
        fields = schema.get("fields", [])
        vector_fields = [f for f in fields if f.get("type") == "float[]"]
        has_vectors_configured = len(vector_fields) > 0
        config_ok = has_vectors_configured

        # Get total document count
        stats = get_collection_stats(client, INDEX_NAME)
        if not stats:
            return None
        total_docs = stats.get("number_of_documents", 0)

        if total_docs == 0:
            # Return configuration info even if collection is empty
            return {
                "total": 0,
                "with_vectors": 0,
                "without_vectors": 0,
                "config_ok": config_ok,
            }

        # Note: Typesense does not support filtering on vector fields (float[]).
        # We cannot directly count documents with/without embeddings using filter_by.
        # Instead, we check if a 'has_embedding' boolean field exists, or fall back to
        # showing that accurate counts are unavailable.

        # Look for a 'has_embedding' boolean field that can be filtered
        has_embedding_field = next(
            (
                f
                for f in fields
                if f.get("name") == "has_embedding" and f.get("type") == "bool"
            ),
            None,
        )

        with_vectors = 0
        without_vectors = 0

        if has_embedding_field:
            # Use the boolean flag field to count documents with embeddings
            with_vectors = count_documents(
                client, INDEX_NAME, filter_by="has_embedding:true"
            )
            without_vectors = count_documents(
                client, INDEX_NAME, filter_by="has_embedding:false"
            )
        else:
            # Cannot accurately count - vector fields cannot be filtered in Typesense
            # We'll estimate based on whether vector fields are configured
            # Set to -1 to indicate "unknown" status
            with_vectors = -1
            without_vectors = -1

        return {
            "total": total_docs,
            "with_vectors": with_vectors,
            "without_vectors": without_vectors,
            "config_ok": config_ok,
        }
    except TypesenseClientError as e:
        st.error(f"{t('embeddings.error_stats')}: TypesenseClientError - {e}")
        return None
    except Exception as e:
        st.error(f"{t('embeddings.error_stats')}: {e}")
        return None


# --- Affichage de la page ---
st.markdown("***")
st.subheader(t("embeddings.stats_title"))

col_btn_1, col_btn_2 = st.columns([4, 1])
with col_btn_2:
    if st.button(f"🔄 {t('embeddings.refresh_button')}"):
        st.cache_data.clear()
        st.rerun()

stats = get_embedding_stats(force_refresh_key=time.time())

if stats:
    total = stats["total"]
    with_vectors = stats["with_vectors"]
    without_vectors = stats["without_vectors"]
    config_ok = stats["config_ok"]

    if not config_ok:
        st.error(
            "⚠️ La configuration des embeddings est manquante dans le schéma de la collection.",
            icon="🚨",
        )
        st.info(
            "Veuillez mettre à jour le schéma de la collection pour inclure un champ de vecteur (par exemple, 'embedding_vec' de type float[])."
        )
        st.stop()

    # Check if we have accurate counts (with_vectors == -1 means unknown)
    counts_available = with_vectors >= 0 and without_vectors >= 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("embeddings.total_docs"), f"{total:,}")

    if counts_available:
        col2.metric(t("embeddings.docs_with_vectors"), f"{with_vectors:,}")
        col3.metric(
            t("embeddings.docs_without_vectors"),
            f"{without_vectors:,}",
            delta_color="inverse",
        )
    else:
        col2.metric(t("embeddings.docs_with_vectors"), "N/A")
        col3.metric(t("embeddings.docs_without_vectors"), "N/A")
        st.info(
            "ℹ️ Le champ `has_embedding` n'existe pas dans cette collection. Les nouvelles collections l'incluent automatiquement lors du crawl."
        )

    if total > 0 and counts_available:
        completion_rate = with_vectors / total
        col4.metric(t("embeddings.completion_rate"), f"{completion_rate:.1%}")
        st.progress(completion_rate, text=f"{with_vectors:,} / {total:,} documents")
    else:
        col4.metric(t("embeddings.completion_rate"), "N/A")
        st.progress(0.0)

    if counts_available and without_vectors == 0 and total > 0:
        st.success(t("embeddings.all_docs_processed"), icon="🎉")
else:
    st.warning(
        "⚠️ Impossible de charger les statistiques. Le client Typesense est-il disponible ?"
    )
