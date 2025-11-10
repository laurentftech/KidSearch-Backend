"""
Module d'authentification pour le Dashboard Streamlit.
Supporte Authentik (OpenID Connect), Google OAuth, GitHub OAuth et authentification simple.
"""

import streamlit as st
import os
import hashlib
import requests
import logging
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlparse
from typing import Optional, Dict, Any
from dashboard.src.i18n import get_translator
from dashboard.src.session_manager import get_session_manager
from meilisearchcrawler.auth_config import get_auth_config, AuthProvider
from streamlit_local_storage import LocalStorage

# Configuration du logging pour l'authentification
os.makedirs("data/logs", exist_ok=True)
auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.DEBUG)  # Niveau DEBUG pour diagnostiquer les problèmes de session

# Handler pour fichier
if not auth_logger.handlers:
    file_handler = logging.FileHandler("data/logs/auth.log")
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    auth_logger.addHandler(file_handler)


def get_local_storage():
    """Retourne l'instance de localStorage.

    localStorage est persistant et survit aux rafraîchissements de page,
    contrairement aux cookies qui ont des problèmes de timing avec Streamlit.
    """
    if 'local_storage' not in st.session_state:
        st.session_state.local_storage = LocalStorage()
    return st.session_state.local_storage


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def _check_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return _hash_password(password) == hashed


def _simple_auth(t):
    """
    Authentification simple par mot de passe.
    Utilise DASHBOARD_PASSWORD depuis .env
    """
    auth_config = get_auth_config()
    dashboard_password = auth_config.get_simple_password()

    if not dashboard_password:
        st.error(t('simple_auth_not_configured'))
        st.info(t('simple_auth_help'))
        st.stop()

    st.title(f"🔒 {t('auth_required')}")
    st.markdown(t('please_log_in'))

    with st.form("login_form"):
        password = st.text_input(t('password_label'), type="password", key="password_input")
        submit = st.form_submit_button(t('login_button'), width='stretch')

        if submit:
            if password == dashboard_password:
                auth_logger.info("Password login SUCCESS")

                # Créer une session persistante
                session_manager = get_session_manager()
                user_info = {"name": "Dashboard User", "email": ""}
                session_id = session_manager.create_session(
                    email="",
                    user_info=user_info,
                    auth_method=AuthProvider.SIMPLE.value
                )

                # Sauvegarder dans la session Streamlit
                st.session_state.authenticated = True
                st.session_state.auth_method = AuthProvider.SIMPLE.value
                st.session_state.user_info = user_info
                st.session_state.persistent_session_id = session_id

                # Sauvegarder le session_id dans localStorage
                local_storage = get_local_storage()
                local_storage.setItem('auth_session_id', session_id)
                auth_logger.debug(f"localStorage 'auth_session_id' set with session_id: {session_id}")

                st.success(f"✅ {t('login_success_redirect')}")
                st.rerun()
            else:
                auth_logger.warning("Password login FAILED - incorrect password")
                st.error(t('incorrect_password'))

    st.stop()


def _sso_auth(provider: str, t):
    """
    Unified authentication for all SSO providers (OIDC, Google, GitHub).

    Args:
        provider: "oidc", "google", or "github"
        t: Translator for messages
    """
    try:
        from streamlit_oauth import OAuth2Component
    except ImportError:
        st.error("streamlit-oauth is not installed. Run: pip install streamlit-oauth")
        st.stop()

    auth_config = get_auth_config()

    # --- 1. Provider-specific configuration ---
    if provider == "oidc":
        config = auth_config.get_oidc_config()
        button_text = t('login_with_oidc')
        icon = None
        scope = " ".join(config.get("scopes", ["openid", "profile", "email"])) if config else ""
        # Discover endpoints if not manually set
        if config and config.get("discovery_url") and not config.get("authorize_url"):
            try:
                discovery_response = requests.get(config["discovery_url"], timeout=5)
                discovery_response.raise_for_status()
                discovery_data = discovery_response.json()
                config["authorize_url"] = discovery_data.get("authorization_endpoint", "")
                config["token_url"] = discovery_data.get("token_endpoint", "")
                config["userinfo_url"] = discovery_data.get("userinfo_endpoint", "")
                auth_logger.debug(f"OIDC endpoints discovered from {config['discovery_url']}")
            except Exception as e:
                st.error(t('oidc_discovery_error', error=str(e)))
                st.info(t('oidc_manual_config_help'))
                st.stop()
    elif provider == "google":
        config = auth_config.get_google_config()
        button_text = t('login_with_google')
        icon = "https://www.google.com/favicon.ico"
        scope = "openid profile email"
    elif provider == "github":
        config = auth_config.get_github_config()
        button_text = t('login_with_github')
        icon = "https://github.com/favicon.ico"
        scope = "read:user user:email"
    else:
        st.error(t('unknown_sso_provider', provider=provider))
        st.stop()

    # --- 2. Check if provider is configured ---
    if not config:
        st.error(t('oauth_not_configured').format(provider=provider.title()))
        st.info(t('oauth_config_help').format(provider=provider.upper()))
        return False

    # Create the authentication component
    oauth2 = OAuth2Component(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        authorize_endpoint=config["authorize_url"],
        token_endpoint=config["token_url"],
        refresh_token_endpoint=config.get("token_url"),
        revoke_token_endpoint=None  # Not all providers have a revoke endpoint
    )

    # --- 3. Display login button ---
    result = oauth2.authorize_button(
        name=button_text,
        icon=icon,
        scope=scope,
        key=provider,
        redirect_uri=config["redirect_uri"],
        width='stretch',
        pkce='S256'  # Enable PKCE for enhanced security (S256 = SHA-256 challenge method)
    )

    # --- 4. Handle authentication result ---
    if result:
        token = result.get("token")
        access_token = token.get("access_token") if token else None
        user_info = result.get('user', {})

        # Essayer plusieurs façons de récupérer l'email
        user_email = (
            user_info.get('email') or
            result.get('email') or
            result.get('userinfo', {}).get('email') or
            ''
        )

        # If email is missing, fetch it from the provider's userinfo endpoint
        if not user_email and access_token:
            try:
                if provider == "oidc":
                    userinfo_url = config.get("userinfo_url")
                    if userinfo_url:
                        response = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
                        if response.ok:
                            user_info.update(response.json())
                            user_email = user_info.get('email', '')
                elif provider == "google":
                    response = requests.get(
                        "https://www.googleapis.com/oauth2/v2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if response.ok:
                        google_info = response.json()
                        user_email = google_info.get('email', '')
                        # Mettre à jour user_info avec toutes les données
                        user_info.update(google_info)
                elif provider == "github":
                    # Récupérer les infos via l'API GitHub
                    response = requests.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"token {access_token}"}
                    )
                    if response.ok:
                        github_info = response.json()
                        user_email = github_info.get('email', '')
                        # Si l'email principal est privé, essayer de récupérer les emails publics
                        if not user_email:
                            emails_response = requests.get(
                                "https://api.github.com/user/emails",
                                headers={"Authorization": f"token {access_token}"}
                            )
                            if emails_response.status_code == 200:
                                emails = emails_response.json()
                                # Trouver l'email principal ou le premier vérifié
                                for email_obj in emails:
                                    if email_obj.get('primary') and email_obj.get('verified'):
                                        user_email = email_obj.get('email', '')
                                        break
                        user_info.update(github_info)
            except Exception as e:
                auth_logger.error(f"Error fetching email via API for {provider}: {e}")
        
        auth_logger.info(f"{provider.upper()} OAuth login attempt - email: {user_email}")

        # Vérifier si l'email est autorisé
        if not auth_config.is_email_allowed(user_email):
            auth_logger.warning(f"{provider.upper()} OAuth access DENIED - email: {user_email} - not in ALLOWED_EMAILS")
            st.error(f"🚫 {t('access_denied')}")
            st.warning(f"{t('email_not_authorized')}: {user_email}")
            st.info(t('contact_admin'))
            st.stop()

        auth_logger.info(f"{provider.upper()} OAuth login SUCCESS - email: {user_email}")

        # Créer une session persistante
        session_manager = get_session_manager()
        session_id = session_manager.create_session(
            email=user_email,
            user_info=user_info,
            auth_method=provider, # 'oidc', 'google', 'github'
            token=token
        )

        # Sauvegarder les informations d'authentification dans la session
        st.session_state.authenticated = True
        st.session_state.auth_method = provider
        st.session_state.oauth_token = token
        st.session_state.user_info = user_info
        st.session_state.persistent_session_id = session_id
        if token:
            st.session_state.id_token = token.get("id_token")

        # Save session_id to localStorage
        local_storage = get_local_storage()
        local_storage.setItem('auth_session_id', session_id)
        auth_logger.debug(f"localStorage 'auth_session_id' set with session_id: {session_id}")

        # Sauvegarder le résultat OAuth complet pour persistance
        st.session_state[f"{provider}_oauth_result"] = result

        # Utiliser une redirection HTML au lieu de st.rerun() pour laisser le temps à localStorage
        redirect_uri = config.get("redirect_uri", "http://localhost:8501/")
        st.markdown(
            f"""
            <meta http-equiv="refresh" content="0; url={redirect_uri}">
            <script>window.location.href = "{redirect_uri}";</script>
            """,
            unsafe_allow_html=True
        )
        st.success(f"✅ {t('login_success_redirect')}")
        st.stop()

    return False


def check_authentication():
    """
    Vérifie si l'utilisateur est authentifié.
    Supporte 4 méthodes d'authentification :
    1. Authentik (OpenID Connect)
    2. Google OAuth
    3. Github OAuth
    4. Authentification simple par mot de passe

    Affiche l'interface de connexion si nécessaire et arrête l'exécution de la page.
    Retourne les informations utilisateur si authentifié.
    """
    # Utiliser le traducteur
    lang = st.session_state.get('lang', 'fr')
    t = get_translator(lang)

    # Récupérer le gestionnaire de sessions et localStorage
    session_manager = get_session_manager()
    local_storage = get_local_storage()

    # Récupérer le session_id depuis localStorage
    # localStorage est synchrone et toujours disponible immédiatement
    # Pas besoin de cache - localStorage survit aux rafraîchissements de page (F5)
    session_id = local_storage.getItem('auth_session_id')
    auth_logger.debug(f"localStorage session_id récupéré: {session_id}")

    if session_id:
        # Tenter de restaurer la session depuis le cache
        session_data = session_manager.get_session(session_id)

        if session_data:
            # Restaurer l'authentification depuis la session persistante
            auth_logger.info(f"Session restaurée depuis cookie - email: {session_data.get('email', 'N/A')}")
            st.session_state.authenticated = True
            st.session_state.auth_method = session_data['auth_method']
            st.session_state.user_info = session_data['user_info']
            st.session_state.oauth_token = session_data.get('token')
            st.session_state.persistent_session_id = session_id
            return session_data['user_info']
        else:
            # Session expirée, supprimer de localStorage
            auth_logger.warning(f"Session expirée pour session_id: {session_id}")
            local_storage.deleteItem('auth_session_id')

    # Vérifier si déjà authentifié dans la session Streamlit courante
    if st.session_state.get('authenticated', False):
        return st.session_state.get('user_info', {})

    # Charger la configuration d'authentification
    auth_config = get_auth_config()

    # Si l'authentification est désactivée, laisser passer
    if not auth_config.is_enabled:
        st.session_state.authenticated = True
        st.session_state.auth_method = "none"
        st.session_state.user_info = {"name": "Anonymous", "email": ""}
        return st.session_state.user_info

    # Déterminer les méthodes d'authentification disponibles
    providers = auth_config.providers

    # Si aucune méthode configurée, afficher une erreur
    if not providers or AuthProvider.NONE in providers:
        st.error(t('no_auth_configured'))
        st.info(t('auth_config_help'))
        st.stop()

    # Si une seule méthode disponible, l'utiliser directement
    if len(providers) == 1:
        provider = providers[0]
        if provider == AuthProvider.SIMPLE:
            _simple_auth(t)
        else: # OIDC, Google, GitHub
            _sso_auth(provider.value, t)
        st.stop()

    # Afficher la page de connexion
    st.title(f"🔒 {t('auth_required')}")
    st.markdown(t('please_log_in'))

    # Sinon, afficher un sélecteur de méthode
    st.markdown("---")
    st.subheader(t('choose_auth_method'))

    # Créer des colonnes pour les boutons
    cols = st.columns(len(providers))

    for idx, provider in enumerate(providers):
        with cols[idx]:
            if provider == AuthProvider.OIDC:
                if st.button(
                    f"🔐 {t('login_with_oidc')}",
                    key="btn_oidc",
                    width='stretch',
                    help=t('login_with_oidc_help')
                ):
                    st.session_state.selected_auth_method = "oidc"
                    st.rerun()

            elif provider == AuthProvider.GOOGLE:
                if st.button(
                    "🔵 Google",
                    key="btn_google",
                    width='stretch',
                    help=t('login_with_google_help')
                ):
                    st.session_state.selected_auth_method = "google"
                    st.rerun()

            elif provider == AuthProvider.GITHUB:
                if st.button(
                    "⚫ GitHub",
                    key="btn_github",
                    width='stretch',
                    help=t('login_with_github_help')
                ):
                    st.session_state.selected_auth_method = "github"
                    st.rerun()

            elif provider == AuthProvider.SIMPLE:
                if st.button(
                    "🔑 " + t('simple_password'),
                    key="btn_password",
                    width='stretch',
                    help=t('login_with_password_help')
                ):
                    st.session_state.selected_auth_method = "password"
                    st.rerun()

    # Afficher le formulaire selon la méthode choisie
    selected_method = st.session_state.get('selected_auth_method')

    if selected_method:
        st.markdown("---")

        # Bouton retour
        if st.button("← " + t('back_to_methods'), key="back_button"):
            st.session_state.selected_auth_method = None
            st.rerun()

        if selected_method == "password":
            _simple_auth(t)
        elif selected_method in ["oidc", "google", "github"]:
            _sso_auth(selected_method, t)
            
    st.stop()


def logout():
    """Déconnecte l'utilisateur."""
    # Supprimer de localStorage
    local_storage = get_local_storage()
    local_storage.deleteItem('auth_session_id')

    # Supprimer la session persistante
    if 'persistent_session_id' in st.session_state:
        session_manager = get_session_manager()
        session_manager.delete_session(st.session_state['persistent_session_id'])

    # Nettoyer toutes les variables de session liées à l'authentification
    keys_to_remove = ['authenticated', 'auth_method', 'oauth_token', 'user_info', 'selected_auth_method', 'id_token', 'redirect_uri', 'persistent_session_id', '_cached_session_id']
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

    # Nettoyer les résultats OAuth stockés
    keys_to_clean = [k for k in st.session_state.keys() if k.endswith('_oauth_result')]
    for key in keys_to_clean:
        del st.session_state[key]

    st.rerun()


def get_user_info():
    """Retourne les informations de l'utilisateur connecté."""
    if st.session_state.get('authenticated', False):
        return st.session_state.get('user_info', {})
    return None


def show_user_widget(t):
    """
    Affiche un widget utilisateur dans la sidebar avec les infos de connexion.

    Args:
        t: Traducteur pour les messages
    """
    if st.session_state.get('authenticated', False):
        user_info = st.session_state.get('user_info', {})
        auth_method = st.session_state.get('auth_method', 'unknown')

        with st.sidebar:
            st.markdown("---")
            st.markdown(f"**👤 {user_info.get('name', 'User')}**")

            # Afficher l'email si disponible
            if user_info.get('email'):
                st.caption(f"📧 {user_info['email']}")

            if auth_method == "oidc":
                st.caption(f"🔐 {t('connected_via_oidc')}")
            elif auth_method == "google":
                st.caption("🔵 " + t('connected_via_google'))
            elif auth_method == "github":
                st.caption("⚫ " + t('connected_via_github'))
            elif auth_method == "password":
                st.caption("🔑 " + t('connected_via_password'))

            if st.button(t('logout_button'), key="logout_btn", width='stretch'):
                logout()
