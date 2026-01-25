import streamlit as st
import sys
from pathlib import Path
import subprocess
import time
import os
import re

from dashboard.src.i18n import get_translator
from dashboard.src.typesense_client import get_typesense_client
from dashboard.src.config import INDEX_NAME, BASE_DIR
from typesense.exceptions import TypesenseClientError

# This is a hack to make sure the app is launched from the root of the project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# =======================
#  Vérification de l'accès
# =======================
from dashboard.src.auth import check_authentication, show_user_widget
check_authentication()

# Initialiser le traducteur
if 'lang' not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

# Afficher le widget utilisateur avec bouton de déconnexion
show_user_widget(t)

st.title(t("embeddings.title"))
st.markdown(t("embeddings.subtitle"))
st.info(t("embeddings.info_what_are_embeddings"), icon="🧠")

# --- Typesense Collection Check ---
from dashboard.src.typesense_client import check_collection_exists

client = get_typesense_client()
if client:
    if not check_collection_exists(client, INDEX_NAME):
        st.warning(f"⚠️ La collection '{INDEX_NAME}' n'existe pas.")
        st.info("Veuillez la créer pour gérer les embeddings.")
        st.page_link("pages/17_⚙️_System_Status.py", label="Aller à la configuration du serveur", icon="⚙️")
        st.stop()
else:
    st.error("La connexion à Typesense n'est pas configurée. Vérifiez votre fichier .env.")
    st.stop()

# Chemin vers le script à exécuter
EMBEDDING_SCRIPT_PATH = os.path.join(BASE_DIR, "meilisearchcrawler", "typesense_gemini.py")


# --- Fonctions de la page ---
@st.cache_data(ttl=10, show_spinner=t("embeddings.loading_stats_spinner"))
def get_embedding_stats(force_refresh_key=None):
    """Récupère les statistiques sur les embeddings depuis Typesense."""
    from dashboard.src.typesense_client import get_collection_stats, get_collection_schema

    client = get_typesense_client()
    if not client:
        return None
    try:
        # Get collection schema to check for vector fields
        schema = get_collection_schema(client, INDEX_NAME)
        if not schema:
            return None

        # Check if collection has vector fields configured
        fields = schema.get('fields', [])
        vector_fields = [f for f in fields if f.get('type') == 'float[]']
        has_vectors_configured = len(vector_fields) > 0
        config_ok = has_vectors_configured

        # Get total document count
        stats = get_collection_stats(client, INDEX_NAME)
        if not stats:
            return None
        total_docs = stats.get('number_of_documents', 0)

        if total_docs == 0:
            # Return configuration info even if collection is empty
            return {"total": 0, "with_vectors": 0, "without_vectors": 0, "config_ok": config_ok}

        # In Typesense, we assume all documents should have embeddings if the field is configured.
        # A more complex logic would be needed to count documents with/without embeddings.
        # For now, we'll assume all documents have embeddings if the configuration is correct.
        with_vectors = total_docs if config_ok else 0
        without_vectors = total_docs - with_vectors

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

def run_embedding_process():
    """Lance le script de génération d'embeddings en arrière-plan."""
    if "embedding_process" in st.session_state and st.session_state.embedding_process.poll() is None:
        st.toast(t("embeddings.process_running"), icon="⚠️")
        return

    st.toast(t("embeddings.process_starting"), icon="🚀")
    python_executable = sys.executable

    process = subprocess.Popen(
        [python_executable, "-u", EMBEDDING_SCRIPT_PATH],  # -u pour unbuffered
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1,
        universal_newlines=True
    )
    st.session_state.embedding_process = process
    st.session_state.embedding_output = []
    st.session_state.last_update_time = time.time()


def parse_progress_from_output(output_lines):
    """Extrait les informations de progression depuis la sortie."""
    processed = 0
    total = 0
    successful = 0

    for line in reversed(output_lines):
        if "Documents traités:" in line:
            match = re.search(r'Documents traités:\s*(\d+)', line)
            if match:
                processed = int(match.group(1))

        if "Trouvé:" in line and "documents sans embeddings" in line:
            match = re.search(r'Trouvé:\s*(\d+)', line)
            if match:
                total = int(match.group(1))

        if "Embeddings ajoutés:" in line:
            match = re.search(r'Embeddings ajoutés:\s*(\d+)', line)
            if match:
                successful = int(match.group(1))

        if total > 0 and processed > 0:
            break

    return processed, total, successful


# --- Affichage de la page ---
st.markdown("***")
st.subheader(t("embeddings.stats_title"))

col_btn_1, col_btn_2 = st.columns([4, 1])
with col_btn_2:
    if st.button(f"🔄 {t('embeddings.refresh_button')}"):
        st.cache_data.clear()
        st.rerun()

if "embedding_process" in st.session_state and st.session_state.embedding_process.poll() is None:
    time.sleep(0.5)
    st.rerun()

stats = get_embedding_stats(force_refresh_key=time.time())

if stats:
    total = stats['total']
    with_vectors = stats['with_vectors']
    without_vectors = stats['without_vectors']
    config_ok = stats['config_ok']

    if not config_ok:
        st.error("⚠️ La configuration des embeddings est manquante dans le schéma de la collection.", icon="🚨")
        st.info("Veuillez mettre à jour le schéma de la collection pour inclure un champ de vecteur (par exemple, 'embedding' de type float[]).")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("embeddings.total_docs"), f"{total:,}")
    col2.metric(t("embeddings.docs_with_vectors"), f"{with_vectors:,}")
    col3.metric(t("embeddings.docs_without_vectors"), f"{without_vectors:,}", delta_color="inverse")

    if total > 0:
        completion_rate = with_vectors / total
        col4.metric(t("embeddings.completion_rate"), f"{completion_rate:.1%}")
        st.progress(completion_rate, text=f"{with_vectors:,} / {total:,} documents")
    else:
        col4.metric(t("embeddings.completion_rate"), "N/A")
        st.progress(0.0)

    st.markdown("***")
    st.subheader(t("embeddings.actions_title"))

    if without_vectors > 0:
        estimated_batches = (without_vectors // 50) + 1
        estimated_time_min = estimated_batches * 10 / 60
        st.info(f"""
        📊 **Estimation pour {without_vectors:,} documents manquants:**
        - Nombre de requêtes API: ~{estimated_batches:,}
        - Temps estimé: ~{estimated_time_min:.0f} minutes
        - Batch size: 50 documents par requête
        """)

    process_running = "embedding_process" in st.session_state and st.session_state.embedding_process.poll() is None

    if without_vectors == 0 and total > 0:
        st.success(t("embeddings.all_docs_processed"), icon="🎉")
    else:
        col_btn1, col_btn2 = st.columns([3, 1])
        with col_btn1:
            st.button(
                t("embeddings.generate_button") + f" ({without_vectors:,} documents)",
                on_click=run_embedding_process,
                disabled=process_running or without_vectors == 0,
                type="primary",
                width='stretch'
            )
        with col_btn2:
            if process_running:
                st.markdown("**🔄 En cours...**")
else:
    st.warning("⚠️ Impossible de charger les statistiques. Le client Typesense est-il disponible ?")

if "embedding_process" in st.session_state:
    process = st.session_state.embedding_process
    st.markdown("***")
    st.subheader("📊 Processus en cours")
    progress_cols = st.columns(3)
    with st.expander(t("embeddings.process_output"), expanded=True):
        output_container = st.empty()
        if process.poll() is None:
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                clean_line = line.strip()
                if clean_line:
                    st.session_state.embedding_output.append(clean_line)
                    if len(st.session_state.embedding_output) > 100:
                        st.session_state.embedding_output = st.session_state.embedding_output[-100:]
                if time.time() - st.session_state.last_update_time > 0.5:
                    output_container.code("\n".join(st.session_state.embedding_output), language="log")
                    st.session_state.last_update_time = time.time()
                    processed, total_to_process, successful = parse_progress_from_output(st.session_state.embedding_output)
                    if total_to_process > 0:
                        progress_cols[0].metric("Traités", f"{processed:,}")
                        progress_cols[1].metric("Réussis", f"{successful:,}")
                        progress_rate = processed / total_to_process if total_to_process > 0 else 0
                        progress_cols[2].metric("Progression", f"{progress_rate:.1%}")
                    time.sleep(0.5)
        else:
            remaining_output = process.stdout.read()
            if remaining_output:
                for line in remaining_output.split('\n'):
                    if line.strip():
                        st.session_state.embedding_output.append(line.strip())
            output_container.code("\n".join(st.session_state.embedding_output), language="log")
            processed, total_to_process, successful = parse_progress_from_output(st.session_state.embedding_output)
            if total_to_process > 0:
                progress_cols[0].metric("✅ Traités", f"{processed:,}")
                progress_cols[1].metric("✅ Réussis", f"{successful:,}")
                progress_rate = processed / total_to_process if total_to_process > 0 else 0
                progress_cols[2].metric("✅ Progression", f"{progress_rate:.1%}")
            if process.returncode == 0:
                st.success("✅ " + t("embeddings.process_finished"), icon="🎉")
            else:
                st.error(f"❌ Le processus s'est terminé avec une erreur (code: {process.returncode})")
            del st.session_state.embedding_process
            del st.session_state.embedding_output
            st.cache_data.clear()
            time.sleep(2)
            st.rerun()
