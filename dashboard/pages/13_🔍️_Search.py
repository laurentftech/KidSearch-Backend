import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
from langdetect import detect, LangDetectException

# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget
check_authentication()

# Corrected imports for the new SDK and proper pathing
from dashboard.src.typesense_client import get_typesense_client
from typesense.exceptions import TypesenseClientError
from dashboard.src.config import INDEX_NAME
from dashboard.src.i18n import get_translator

# Initialize translator
if 'lang' not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

st.set_page_config(
    page_title=t("search.page_title"),
    layout="wide"
)

st.title(t("search.title"))
st.markdown(t("search.subtitle"))

# --- Initialization ---
typesense_client = get_typesense_client()

from dashboard.src.typesense_client import check_collection_exists, get_collection_stats

if not typesense_client:
    st.error(t("search.error_typesense_connection"))
    st.stop()

try:
    if not check_collection_exists(typesense_client, INDEX_NAME):
        st.warning(f"⚠️ La collection '{INDEX_NAME}' n'existe pas.")
        st.info("Veuillez la créer pour pouvoir effectuer une recherche.")
        st.page_link("pages/17_⚙️_System_Status.py", label="Aller à la configuration du serveur", icon="⚙️")
        st.stop()

    stats = get_collection_stats(typesense_client, INDEX_NAME)
    if stats and stats['number_of_documents'] == 0:
        st.warning(t("search.warning_no_documents"))
        st.stop()
except Exception as e:
    st.error(f"{t('search.error_index_access')}: {e}")
    st.stop()

# --- Search bar and filters ---
with st.form(key="search_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(t("search.search_box_label"), "", placeholder=t("search.search_box_placeholder"))
    with col2:
        use_hybrid = st.checkbox(t("search.use_hybrid_search"), value=True, help=t("search.hybrid_search_help"))
        semantic_ratio = st.slider(
            t("search.semantic_ratio_label"),
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.1,
            help=t("search.semantic_ratio_help"),
            disabled=not use_hybrid
        )
    
    submitted = st.form_submit_button(label=t("search.search_button_label"), type="primary")

# --- Search logic ---
if submitted and query:
    with st.spinner(t("search.spinner_searching")):
        search_params = {
            "q": query,
            "query_by": "title,excerpt,content", # Mandatory in Typesense
            "per_page": 20,
            "include_fields": ['title', 'url', 'excerpt', 'site', 'images', 'timestamp'],
            "highlight_full_fields": 'title',
            "highlight_fields": 'excerpt',
            "highlight_start_tag": "**",
            "highlight_end_tag": "**",
        }

        # --- Smart filters ---
        filters = []

        try:
            query_lang = detect(query)
            if query_lang in ['fr', 'en']:
                filters.append(f"lang:={query_lang}") # Typesense syntax for exact match
                st.caption(f"Search language detected: `{query_lang.upper()}`")
            else:
                filters.append(f"lang:={st.session_state.get('lang', 'fr')}")
        except LangDetectException:
            filters.append(f"lang:={st.session_state.get('lang', 'fr')}")

        # Note: Typesense handles keyword matching differently. 
        # We don't need to manually filter by keywords in the filter_by parameter usually.
        # But if we want to enforce it:
        # keywords = [f'"{word}"' for word in query.split() if len(word) > 2]
        # if keywords:
        #    filters.append(f"title:=[{', '.join(keywords)}] || excerpt:=[{', '.join(keywords)}]")

        if filters:
            search_params["filter_by"] = " && ".join(filters) # Typesense uses && for AND

        if use_hybrid:
            # Typesense hybrid search requires vector_query parameter.
            # Since we don't have the vector for the query here (client-side),
            # we can't do true hybrid search directly from Streamlit without an embedding model.
            # For now, we'll fallback to keyword search and warn the user.
            st.warning("⚠️ Hybrid search requires vector generation which is not yet implemented in this dashboard view. Falling back to keyword search.")
            
            # If we had the vector, it would look like this:
            # search_params["vector_query"] = f"embedding_vec:([{vector_values}], k:100, alpha: {semantic_ratio})"

        try:
            collection = typesense_client.collections[INDEX_NAME]
            response = collection.documents.search(search_params)
            hits = response['hits']
            
            st.success(t("search.results_summary").format(
                count=len(hits),
                total=response['found'],
                time=response['search_time_ms']
            ))
            st.markdown("---")

            if not hits:
                st.warning(t("search.no_results_found"))
            else:
                for hit in hits:
                    document = hit.get('document', {})
                    highlight = hit.get('highlight', {})
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        images = document.get('images')
                        if images and isinstance(images, list) and len(images) > 0:
                            st.image(images[0]['url'], width=150)
                        else:
                            st.image("https://via.placeholder.com/150?text=No+Image", width=150)

                    with col2:
                        title = highlight.get('title', {}).get('value', document.get('title', t('search.no_title')))
                        excerpt = highlight.get('excerpt', {}).get('snippet', document.get('excerpt', ''))
                        url = document.get('url', '#')
                        site = document.get('site', t('search.unknown_site'))
                        timestamp = document.get('timestamp')

                        st.markdown(f"#### [{title}]({url})", unsafe_allow_html=True)
                        st.markdown(f"<small>{t('search.site')}: **{site}**</small>", unsafe_allow_html=True)
                        if timestamp:
                            date = datetime.fromtimestamp(timestamp)
                            st.markdown(f"<small>{t('search.published_on')}: {date.strftime('%d/%m/%Y')}</small>", unsafe_allow_html=True)

                        st.markdown(excerpt, unsafe_allow_html=True)

                    st.markdown("---")

        except TypesenseClientError as e:
            st.error(f"{t('search.error_during_search')}: {e}")
        except Exception as e:
            st.error(f"{t('search.error_during_search')}: An unexpected error occurred: {e}")

elif not query:
    st.info(t("search.info_start_searching"))
