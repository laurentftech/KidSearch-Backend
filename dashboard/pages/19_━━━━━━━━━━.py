"""
Visual separator between Crawler and API sections
"""

import streamlit as st
import sys
from pathlib import Path
import os


# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget
from dashboard.src.i18n import get_translator

check_authentication()

# Initialize translator
if 'lang' not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

# API Configuration
API_DISPLAY_HOST = os.getenv("API_DISPLAY_HOST") or os.getenv("API_HOST", "localhost")
API_PORT = os.getenv("API_PORT", "8080")

# Build base URL: include port only if not using a reverse proxy (i.e., DISPLAY_HOST == HOST)
if API_DISPLAY_HOST == os.getenv("API_HOST", "localhost"):
    API_BASE_URL = f"http://{API_DISPLAY_HOST}:{API_PORT}/api"
else:
    # Behind reverse proxy: no port in URL
    API_BASE_URL = f"http://{API_DISPLAY_HOST}/api"

st.set_page_config(
    page_title="Section Separator",
    page_icon="━",
    layout="wide"
)

st.title("🚀 API Section")
st.markdown("---")

st.info("👈 Select an API page from the sidebar:")
st.markdown("- **📚 Documentation** : Complete API documentation")
st.markdown("- **📊 Monitor** : Real-time API monitoring")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📖 Interactive Docs")
    st.markdown("Access the FastAPI interactive documentation:")
    st.link_button("Open Swagger UI", f"{API_BASE_URL}/docs", width='stretch')
    st.link_button("Open ReDoc", f"{API_BASE_URL}/redoc", width='stretch')

with col2:
    st.markdown("### 🔍 Quick Test")
    st.markdown("Test the API directly from your terminal:")
    st.code(f'curl "{API_BASE_URL}/search?q=dinosaures"', language="bash")
