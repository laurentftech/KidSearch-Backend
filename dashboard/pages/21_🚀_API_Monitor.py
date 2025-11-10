"""
API Backend Monitoring Page
Displays real-time statistics and health of the KidSearch API backend
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import time
import os
import requests

# Use absolute imports from the project root
from dashboard.src.i18n import get_translator
from dashboard.src.meilisearch_client import get_meili_client

# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget
check_authentication()

INDEX_NAME = os.getenv("INDEX_NAME", "kidsearch")

# Initialize translator
if 'lang' not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

st.title("📊 API Monitor")
st.markdown("*Surveillance du backend de recherche unifiée*")

# API Configuration
API_HOST = os.getenv("API_HOST", "localhost")  # Real URL for direct connection
API_DISPLAY_HOST = os.getenv("API_DISPLAY_HOST", API_HOST)  # URL shown to users (may be behind reverse proxy)
API_PORT = os.getenv("API_PORT", "8000")
API_ENABLED = os.getenv("API_ENABLED", "false").lower() == "true"

# Use real host for making requests from dashboard
API_BASE_URL = f"http://{API_HOST}:{API_PORT}/api"
# URL to display to user (may not include port if behind reverse proxy)
API_DISPLAY_URL = f"http://{API_DISPLAY_HOST}" + (f":{API_PORT}" if API_DISPLAY_HOST == API_HOST else "") + "/api"

@st.cache_data(ttl=15) # Cache for 15 seconds - increased for better performance
def get_api_data():
    """Check API health and get statistics."""
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=5, headers=headers)
        stats_response = requests.get(f"{API_BASE_URL}/stats", timeout=5, headers=headers)

        health_data = health_response.json() if health_response.status_code == 200 else None
        stats_data = stats_response.json() if stats_response.status_code == 200 else None
        
        return health_response.status_code == 200, health_data, stats_data

    except requests.exceptions.RequestException:
        return False, None, None

# --- Main Page --- 

# Check API status
if not API_ENABLED:
    st.warning("⚠️ API backend désactivé dans .env (API_ENABLED=false)")
    st.info("Pour activer: définir `API_ENABLED=true` dans le fichier .env")
    st.stop()

api_running, health_data, stats_data = get_api_data()

if api_running:
    st.success(f"✅ API en ligne - {API_DISPLAY_URL}")
else:
    st.error(f"❌ API hors ligne - {API_DISPLAY_URL}")
    st.info("Démarrer l'API avec: `python api.py`")
    st.stop()

# --- Header --- 
col1, col2, col3, col4 = st.columns(4)

with col1:
    if health_data:
        st.metric("Version", health_data.get("version", "N/A"))

with col2:
    st.metric("Workers", os.getenv("API_WORKERS", "4"))

with col3:
    @st.cache_data(ttl=30, show_spinner=False)
    def get_meilisearch_doc_count():
        meili_client = get_meili_client()
        if meili_client:
            try:
                stats = meili_client.index(INDEX_NAME).get_stats()
                return getattr(stats, 'number_of_documents', 0)
            except Exception:
                return None
        return None

    num_docs = get_meilisearch_doc_count()
    if num_docs is not None:
        st.metric("Documents", f"{num_docs:,}")
    else:
        st.metric("Documents", "N/A")

with col4:
    if st.button("🔄 Rafraîchir", key="refresh_api"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# --- Services Health ---
st.subheader("🏥 État des services")

if health_data:
    services = health_data.get("services", {})

    reranking_enabled = os.getenv("RERANKING_ENABLED", "false").lower() == "true"
    if "reranker" not in services:
        services["reranker"] = reranking_enabled

    num_services = len(services)
    if num_services > 0:
        cols = st.columns(num_services)
        for idx, (service, is_healthy) in enumerate(services.items()):
            with cols[idx]:
                status_icon = "✅" if is_healthy else "❌"
                status_text = "OK" if is_healthy else "Erreur"
                st.metric(
                    f"{status_icon} {service.title()}",
                    status_text,
                )

st.markdown("---")

# --- API Statistics ---
st.subheader("📊 Statistiques d'utilisation")

if stats_data:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Recherches totales",
            f"{stats_data.get('total_searches', 0):,}",
        )

    with col2:
        st.metric(
            "Recherches (dernière heure)",
            stats_data.get('searches_last_hour', 0),
        )

    with col3:
        st.metric(
            "Temps de réponse moyen",
            f"{stats_data.get('avg_response_time_ms', 0):.0f} ms",
        )

    with col4:
        error_rate = stats_data.get('error_rate', 0) * 100
        st.metric(
            "Taux d'erreur",
            f"{error_rate:.1f}%",
            delta_color="inverse"
        )

    # CSE Quota
    st.subheader("🔑 Quota Google CSE")
    col1, col2 = st.columns([3, 1])

    with col1:
        quota_used = stats_data.get('cse_quota_used', 0)
        quota_limit = stats_data.get('cse_quota_limit', 100)
        if quota_limit > 0:
            st.progress(quota_used / quota_limit)
        else:
            st.progress(0)


    with col2:
        st.metric("Utilisé / Limite", f"{quota_used} / {quota_limit}")

    # Cache hit rate
    cache_hit_rate = stats_data.get('cache_hit_rate', 0) * 100
    st.metric(
        "Taux de cache CSE",
        f"{cache_hit_rate:.1f}%",
        help="Pourcentage de requêtes CSE servies depuis le cache"
    )

    # Top queries
    st.subheader("🔝 Requêtes populaires")
    if stats_data.get('top_queries'):
        df_queries = pd.DataFrame(stats_data['top_queries'])

        if not df_queries.empty:
            # Bar chart
            fig = px.bar(
                df_queries.head(10),
                x='count',
                y='query',
                orientation='h',
                title="Top 10 des recherches",
                text='count',
            )
            fig.update_traces(textposition='outside')
            fig.update_layout(
                xaxis_title="Nombre de recherches",
                yaxis_title="",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Voir toutes les requêtes"):
                st.dataframe(df_queries, use_container_width=True)
        else:
            st.info("Aucune requête populaire pour le moment.")
    else:
        st.info("Aucune requête populaire pour le moment.")

else:
    st.info("Aucune statistique disponible pour le moment")

# --- Admin Actions ---
st.markdown("---")
st.subheader("⚙️ Actions Administratives")

if 'confirm_reset' not in st.session_state:
    st.session_state.confirm_reset = False

if st.button("🗑️ Réinitialiser les statistiques", key="reset_stats"):
    st.session_state.confirm_reset = True

if st.session_state.confirm_reset:
    st.warning("Êtes-vous sûr de vouloir supprimer toutes les statistiques de recherche ? Cette action est irréversible.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Oui, tout supprimer", type="primary"):
            try:
                response = requests.post(f"{API_BASE_URL}/stats/reset", timeout=5)
                if response.status_code == 200:
                    st.success("Statistiques réinitialisées avec succès !")
                    st.cache_data.clear()
                    st.session_state.confirm_reset = False
                    time.sleep(1) # Allow user to see the message
                    st.rerun()
                else:
                    st.error(f"Erreur lors de la réinitialisation: {response.text}")
                    st.session_state.confirm_reset = False
            except Exception as e:
                st.error(f"Erreur de connexion à l'API: {e}")
                st.session_state.confirm_reset = False
    with col2:
        if st.button("Annuler"):
            st.session_state.confirm_reset = False
            st.rerun()

st.markdown("---")

# --- Test Search ---
st.subheader("🔍 Tester la recherche")

with st.form("test_search_form"):
    col1, col2 = st.columns([3, 1])

    with col1:
        test_query = st.text_input(
            "Requête de test",
            placeholder="dinosaures",
        )

    with col2:
        test_lang = st.selectbox("Langue", ["fr", "en"])

    col1, col2, col3 = st.columns(3)

    with col1:
        use_cse = st.checkbox("Utiliser Google CSE", value=True)

    with col2:
        use_reranking = st.checkbox("Reranking sémantique", value=True)

    with col3:
        limit = st.number_input("Limite de résultats", 1, 100, 20)

    submit = st.form_submit_button("🚀 Rechercher", type="primary")

if submit and test_query:
    with st.spinner("Recherche en cours..."):
        try:
            params = {
                "q": test_query,
                "lang": test_lang,
                "limit": limit,
                "use_cse": use_cse,
                "use_reranking": use_reranking,
            }

            response = requests.get(f"{API_BASE_URL}/search", params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                st.success(f"✅ {len(data['results'])} résultats trouvés en {data['stats']['processing_time_ms']:.0f}ms")

                # Stats
                stats = data['stats']
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Résultats Meilisearch", stats['meilisearch_results'])

                with col2:
                    st.metric("Résultats Google CSE", stats['cse_results'])

                with col3:
                    reranking_icon = "✅" if stats['reranking_applied'] else "❌"
                    st.metric("Reranking appliqué", reranking_icon)

                # Results
                if data['results']:
                    st.subheader("Résultats")

                    for idx, result in enumerate(data['results'][:5], 1):
                        with st.expander(f"{idx}. {result['title']} ({result['source']})"):
                            st.markdown(f"**URL:** {result['url']}")
                            st.markdown(f"**Score:** {result['score']:.3f}")
                            if result.get('original_score'):
                                st.markdown(f"**Score original:** {result['original_score']:.3f}")
                            st.markdown(f"**Extrait:** {result['excerpt']}")

                    with st.expander("📋 Voir tous les résultats (JSON)"):
                        st.json(data)
                else:
                    st.info("Aucun résultat trouvé")

            else:
                st.error(f"Erreur {response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"Erreur lors de la recherche: {e}")

st.markdown("---")

# --- Auto-refresh ---
if 'pause_api_refresh' not in st.session_state:
    st.session_state.pause_api_refresh = False

col1, col2 = st.columns([3, 1])
with col1:
    refresh_rate = st.slider(
        "Rafraîchissement automatique (secondes)",
        10, 120, 30, # Default to 30s for better performance
        key="api_refresh_slider",
        disabled=st.session_state.pause_api_refresh
    )
with col2:
    st.write("")
    st.write("")
    if st.session_state.pause_api_refresh:
        if st.button("▶️ Reprendre"):
            st.session_state.pause_api_refresh = False
            st.rerun()
    else:
        if st.button("⏸️ Pause"):
            st.session_state.pause_api_refresh = True
            st.rerun()

if not st.session_state.pause_api_refresh:
    time.sleep(refresh_rate)
    st.rerun()
