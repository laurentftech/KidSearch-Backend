import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from dashboard.src.auth import check_authentication  # noqa: E402
from dashboard.src.i18n import get_translator  # noqa: E402
from dashboard.src.state import is_crawler_running  # noqa: E402
from dashboard.src.typesense_client import get_collection_stats, get_typesense_client  # noqa: E402
from dashboard.src.utils import load_cache_stats  # noqa: E402
from kidsearch.config import INDEX_NAME  # noqa: E402

# =======================
#  Configuration
# =======================
st.set_page_config(
    page_title="KidSearch Dashboard",
    page_icon="🕸️",
    layout="wide",
)

if "lang" not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

check_authentication()

# =======================
#  Custom CSS
# =======================
st.markdown(
    """
<style>
    .error-box, .success-box, .warning-box {
        padding: 12px; margin: 8px 0; border-radius: 6px; color: inherit;
    }
    .error-box { background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; }
    .success-box { background-color: rgba(34, 197, 94, 0.1); border-left: 4px solid #22c55e; }
    .warning-box { background-color: rgba(251, 191, 36, 0.1); border-left: 4px solid #fbbf24; }
</style>
""",
    unsafe_allow_html=True,
)

# =======================
#  Navigation avec sections
# =======================
api_enabled = os.getenv("API_ENABLED", "false").lower() == "true"

sections = {
    f"🕸️ {t('section_crawler')}": [
        st.Page(
            "pages/10_🏠️_Overview.py",
            title=t("nav.overview"),
            icon=":material/monitoring:",
            default=True,
        ),
        st.Page(
            "pages/11_🔧️_Crawler_Controls.py",
            title=t("nav.controls"),
            icon=":material/settings:",
        ),
        st.Page(
            "pages/12_⚙️️_Crawler_Configuration.py",
            title=t("nav.config"),
            icon=":material/tune:",
        ),
    ],
    f"🔍 {t('nav.section_content')}": [
        st.Page(
            "pages/13_🔍️_Search.py", title=t("nav.search"), icon=":material/search:"
        ),
        st.Page(
            "pages/14_📊_Statistics.py",
            title=t("nav.stats"),
            icon=":material/bar_chart:",
        ),
        st.Page(
            "pages/15_🌳_Page_Tree.py",
            title=t("nav.tree"),
            icon=":material/account_tree:",
        ),
        st.Page(
            "pages/16_🧠_Embeddings.py",
            title=t("nav.embeddings"),
            icon=":material/psychology:",
        ),
    ],
    f"📋 {t('nav.section_system')}": [
        st.Page("pages/17_🪵️_Logs.py", title=t("nav.logs"), icon=":material/article:"),
        st.Page(
            "pages/18_⚙️_System_Status.py",
            title=t("nav.system"),
            icon=":material/health_and_safety:",
        ),
    ],
}

if api_enabled:
    sections[f"🚀 {t('section_api')}"] = [
        st.Page(
            "pages/20_🚀_API_Documentation.py",
            title=t("nav.api_docs"),
            icon=":material/description:",
        ),
        st.Page(
            "pages/21_🚀_API_Monitor.py",
            title=t("nav.api_monitor"),
            icon=":material/monitor_heart:",
        ),
        st.Page(
            "pages/22_📈_API_Metrics.py",
            title=t("nav.api_metrics"),
            icon=":material/analytics:",
        ),
    ]

pg = st.navigation(sections)

# =======================
#  Sidebar — métriques & langue
# =======================
with st.sidebar:
    # Sélecteur de langue
    lang_options = {"fr": "🇫🇷 Français", "en": "🇬🇧 English"}
    selected_lang = st.selectbox(
        "Language",
        options=list(lang_options.keys()),
        format_func=lambda code: lang_options[code],
        index=list(lang_options.keys()).index(st.session_state.lang),
        label_visibility="collapsed",
    )
    if selected_lang != st.session_state.lang:
        st.session_state.lang = selected_lang
        st.rerun()

    st.markdown("---")

    # Statut crawler
    running = is_crawler_running()
    st.metric(
        t("crawler_status"), f"🟢 {t('active')}" if running else f"🔴 {t('stopped')}"
    )

    cache_stats = load_cache_stats()
    if cache_stats:
        st.metric(t("cached_urls"), f"{cache_stats['total_urls']:,}")

    # Statut API + Typesense
    if api_enabled:
        st.metric(t("api_status"), f"🟢 {t('active')}")

        @st.cache_data(ttl=30, show_spinner=False)
        def get_typesense_doc_count():
            client = get_typesense_client()
            if client:
                try:
                    stats = get_collection_stats(client, INDEX_NAME)
                    return stats.get("number_of_documents", 0) if stats else None
                except Exception:
                    return None
            return None

        num_docs = get_typesense_doc_count()
        st.metric(
            t("typesense_docs"), f"{num_docs:,}" if num_docs is not None else "N/A"
        )

# =======================
#  Lancement de la page sélectionnée
# =======================
pg.run()
