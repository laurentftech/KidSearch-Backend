import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dashboard.src.auth import check_authentication, show_user_widget
from dashboard.src.config import CRAWLER_SCRIPT, INDEX_NAME, SCHEDULER_FILE
from dashboard.src.i18n import get_translator
from dashboard.src.state import (
    clear_cache,
    is_crawler_running,
    start_crawler,
    stop_crawler,
)
from dashboard.src.typesense_client import check_collection_exists, get_typesense_client
from dashboard.src.utils import (
    load_cache_stats,
    load_sites_config,
    parse_logs_for_errors,
)

# =======================
#  Auth
# =======================
check_authentication()

if "lang" not in st.session_state:
    st.session_state.lang = "fr"
t = get_translator(st.session_state.lang)

show_user_widget(t)


# =======================
#  Dialogs de confirmation
# =======================
@st.dialog(t("controls.dialog_stop_title"))
def confirm_stop_dialog():
    st.write(t("controls.dialog_stop_body"))
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            t("controls.dialog_confirm"),
            type="primary",
            use_container_width=True,
            icon=":material/check:",
        ):
            if stop_crawler():
                st.toast(t("controls.toast_stop_signal_sent"), icon="🛑")
            st.rerun()
    with col2:
        if st.button(
            t("controls.dialog_cancel"),
            use_container_width=True,
            icon=":material/close:",
        ):
            st.rerun()


@st.dialog(t("controls.dialog_clear_title"))
def confirm_clear_dialog():
    st.write(t("controls.dialog_clear_body"))
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            t("controls.dialog_confirm"),
            type="primary",
            use_container_width=True,
            icon=":material/check:",
        ):
            if clear_cache():
                st.toast(t("controls.toast_cache_cleared"), icon="🗑️")
            else:
                st.toast(t("controls.toast_cache_empty"), icon="ℹ️")
            st.rerun()
    with col2:
        if st.button(
            t("controls.dialog_cancel"),
            use_container_width=True,
            icon=":material/close:",
        ):
            st.rerun()


# =======================
#  Header & checks
# =======================
st.header(t("controls.title"))

client = get_typesense_client()
index_exists = False
if client:
    index_exists = check_collection_exists(client, INDEX_NAME)
    if not index_exists:
        st.error(f"⚠️ La collection '{INDEX_NAME}' n'existe pas.")
        st.info("Veuillez la créer avant de lancer un crawl.")
        st.page_link(
            "pages/17_⚙️_System_Status.py",
            label="Aller à la configuration du serveur",
            icon="⚙️",
        )
else:
    st.error(
        "La connexion à Typesense n'est pas configurée. Vérifiez votre fichier .env."
    )

running = is_crawler_running()
controls_disabled = running or not index_exists

if running:
    st.info(t("controls.crawler_is_running_info"))
    st.page_link(
        "pages/10_🏠️_Overview.py", label=t("controls.go_to_overview_button"), icon="🏠"
    )

# =======================
#  Navigation segmentée
# =======================
mode = (
    st.segmented_control(
        "Mode",
        options=["manual", "schedule"],
        format_func=lambda x: t(f"controls.tab_{x}"),
        default="manual",
        label_visibility="collapsed",
        key="controls_mode",
    )
    or "manual"
)

st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# Mode : Crawl Manuel
# ──────────────────────────────────────────────────────────────────────────────
if mode == "manual":
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "none").lower()
    embeddings_enabled = embedding_provider != "none"
    help_text = ""
    if not embeddings_enabled:
        help_text = (
            "EMBEDDING_PROVIDER n'est pas configuré ou est sur 'none' dans votre .env"
        )
    elif embedding_provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        help_text = (
            "Le provider Gemini est sélectionné mais GEMINI_API_KEY est manquante."
        )
        embeddings_enabled = False

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(t("controls.crawl_options"))

        sites_config = load_sites_config()
        site_names = [t("controls.all_sites")]
        if sites_config and "sites" in sites_config:
            site_names += [site["name"] for site in sites_config["sites"]]

        selected_site = st.selectbox(
            t("controls.site_to_crawl"), site_names, disabled=controls_disabled
        )
        force_crawl = st.checkbox(
            t("controls.force_crawl"), value=False, disabled=controls_disabled
        )
        generate_embeddings = st.checkbox(
            t("controls.generate_embeddings"),
            value=True,
            disabled=controls_disabled or not embeddings_enabled,
            help=help_text or "Génère un vecteur sémantique pour chaque nouvelle page.",
        )
        persistent_cache = st.checkbox(
            t("controls.persistent_cache"),
            value=True,
            disabled=controls_disabled,
            help="Exploration en profondeur : ne jamais re-crawler les URLs déjà visitées.",
        )
        workers = st.slider(t("controls.workers"), 1, 20, 2, disabled=controls_disabled)

        site_param = None if selected_site == t("controls.all_sites") else selected_site

        if st.button(
            t("controls.launch_crawl"),
            disabled=controls_disabled,
            type="primary",
            use_container_width=True,
            icon=":material/rocket_launch:",
        ):
            success = start_crawler(
                site=site_param,
                force=force_crawl,
                workers=workers,
                embed=generate_embeddings,
                persistent_cache=persistent_cache,
            )
            if success:
                msg = (
                    t("controls.toast_crawler_started_for_site").format(site=site_param)
                    if site_param
                    else t("controls.toast_crawler_started")
                )
                st.toast(msg, icon="🚀")
                time.sleep(2)
                st.rerun()
            else:
                st.toast(t("controls.toast_crawler_already_running"), icon="⚠️")

    with col2:
        st.subheader(t("controls.actions"))

        if st.button(
            t("controls.stop_crawl"),
            disabled=not running,
            type="secondary",
            use_container_width=True,
            icon=":material/stop_circle:",
        ):
            confirm_stop_dialog()

        st.markdown("---")

        if st.button(
            t("controls.clear_cache"),
            disabled=controls_disabled,
            use_container_width=True,
            icon=":material/delete_sweep:",
        ):
            confirm_clear_dialog()

        cache_stats = load_cache_stats()
        if cache_stats and cache_stats["total_urls"] > 0:
            st.info(
                t("controls.current_cache").format(
                    total_urls=f"{cache_stats['total_urls']:,}",
                    sites=cache_stats["sites"],
                )
            )

        st.markdown("---")

        if st.button(
            t("controls.show_cache_stats"),
            use_container_width=True,
            disabled=running,
            icon=":material/bar_chart:",
        ):
            with st.spinner(t("controls.calculating_stats")):
                result = subprocess.run(
                    [sys.executable, CRAWLER_SCRIPT, "--stats-only"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                st.code(result.stdout, language="text")

    # Erreurs récentes
    st.subheader(t("controls.recent_errors"))
    errors = parse_logs_for_errors(50)
    if errors:
        for err in reversed(errors[-10:]):
            st.markdown(
                f"""
            <div class="error-box">
                <small>{err["timestamp"]}</small><br>
                <code style="font-size: 0.85em;">{err["message"]}</code>
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"""
        <div class="success-box">
            {t("controls.no_recent_errors")}
        </div>
        """,
            unsafe_allow_html=True,
        )

# ──────────────────────────────────────────────────────────────────────────────
# Mode : Planification
# ──────────────────────────────────────────────────────────────────────────────
elif mode == "schedule":
    st.subheader(t("controls.schedule_title"))
    st.caption(t("controls.schedule_info"))

    _sched_path = Path(SCHEDULER_FILE)
    _sched_config: dict = {}
    if _sched_path.exists():
        try:
            with open(_sched_path) as _f:
                _sched_config = json.load(_f)
        except Exception:
            pass

    _dow_labels = [
        t("controls.schedule_days_mon"),
        t("controls.schedule_days_tue"),
        t("controls.schedule_days_wed"),
        t("controls.schedule_days_thu"),
        t("controls.schedule_days_fri"),
        t("controls.schedule_days_sat"),
        t("controls.schedule_days_sun"),
    ]

    sched_enabled = st.toggle(
        t("controls.schedule_enabled"),
        value=_sched_config.get("enabled", False),
    )

    # Sélection des jours avec st.pills
    current_day_labels = [
        _dow_labels[i] for i in _sched_config.get("days_of_week", list(range(7)))
    ]
    selected_day_labels = st.pills(
        t("controls.schedule_days"),
        options=_dow_labels,
        selection_mode="multi",
        default=current_day_labels,
        help=t("controls.schedule_days_help"),
        disabled=not sched_enabled,
    )
    selected_days = [_dow_labels.index(d) for d in (selected_day_labels or [])]

    col_h, col_m = st.columns(2)
    with col_h:
        sched_hour = st.number_input(
            t("controls.schedule_hour"),
            min_value=0,
            max_value=23,
            value=_sched_config.get("hour", 3),
            disabled=not sched_enabled,
        )
    with col_m:
        _minutes = [0, 15, 30, 45]
        sched_minute = st.selectbox(
            t("controls.schedule_minute"),
            options=_minutes,
            index=_minutes.index(_sched_config.get("minute", 0))
            if _sched_config.get("minute", 0) in _minutes
            else 0,
            format_func=lambda m: f"{m:02d}",
            disabled=not sched_enabled,
        )

    st.markdown("---")
    st.subheader(t("controls.schedule_options"))

    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "none").lower()
    embeddings_available = embedding_provider != "none"

    _opts = _sched_config.get("options", {})
    sites_config = load_sites_config()
    site_names = [t("controls.all_sites")]
    if sites_config and "sites" in sites_config:
        site_names += [site["name"] for site in sites_config["sites"]]

    current_site = _opts.get("site")
    current_site_idx = (
        site_names.index(current_site) if current_site in site_names else 0
    )

    s_col1, s_col2 = st.columns(2)
    with s_col1:
        sched_site = st.selectbox(
            t("controls.site_to_crawl"),
            site_names,
            index=current_site_idx,
            disabled=not sched_enabled,
            key="sched_site",
        )
        sched_force = st.checkbox(
            t("controls.force_crawl"),
            value=_opts.get("force", False),
            disabled=not sched_enabled,
            key="sched_force",
        )
    with s_col2:
        sched_workers = st.slider(
            t("controls.workers"),
            1,
            20,
            value=_opts.get("workers", 2),
            disabled=not sched_enabled,
            key="sched_workers",
        )
        sched_embeddings = st.checkbox(
            t("controls.generate_embeddings"),
            value=_opts.get("embeddings", True),
            disabled=not sched_enabled or not embeddings_available,
            key="sched_embeddings",
        )
        sched_persistent = st.checkbox(
            t("controls.persistent_cache"),
            value=_opts.get("persistent_cache", False),
            disabled=not sched_enabled,
            key="sched_persistent",
        )

    if st.button(
        t("controls.schedule_save"),
        type="primary",
        use_container_width=True,
        icon=":material/save:",
        icon_position="right",
    ):
        new_config = {
            "enabled": sched_enabled,
            "days_of_week": selected_days,
            "hour": int(sched_hour),
            "minute": int(sched_minute),
            "options": {
                "site": None if sched_site == t("controls.all_sites") else sched_site,
                "force": sched_force,
                "workers": sched_workers,
                "embeddings": sched_embeddings,
                "persistent_cache": sched_persistent,
            },
            "last_run": _sched_config.get("last_run"),
            "next_run": _sched_config.get("next_run"),
        }
        try:
            _sched_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_sched_path, "w") as _f:
                json.dump(new_config, _f, indent=2, ensure_ascii=False)
            st.toast(t("controls.schedule_saved"), icon="✅")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Erreur lors de la sauvegarde : {e}")

    # Statut
    st.markdown("---")
    next_run = _sched_config.get("next_run")
    last_run = _sched_config.get("last_run")

    if next_run:
        try:
            dt = datetime.fromisoformat(next_run)
            st.info(
                t("controls.schedule_next_run").format(
                    dt=dt.strftime("%A %d/%m/%Y à %H:%M")
                )
            )
        except ValueError:
            pass
    else:
        st.caption(t("controls.schedule_no_next_run"))

    if last_run:
        try:
            dt = datetime.fromisoformat(last_run)
            st.caption(
                t("controls.schedule_last_run").format(
                    dt=dt.strftime("%A %d/%m/%Y à %H:%M")
                )
            )
        except ValueError:
            pass

# Auto-refresh
if running:
    st.markdown("---")
    st.caption(t("controls.auto_refresh_caption"))
    time.sleep(10)
    st.rerun()
