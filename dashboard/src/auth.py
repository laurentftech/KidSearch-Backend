"""
Module d'authentification pour le Dashboard Streamlit.
Supporte l'authentification par proxy (forward-auth), OIDC, Google, GitHub et mot de passe simple.
"""

import streamlit as st
import os
from argon2 import PasswordHasher
import requests
import logging
from typing import Optional, Dict
from meilisearchcrawler.auth_config import get_auth_config, AuthProvider
from streamlit_local_storage import LocalStorage
import jwt
from dashboard.src.i18n import get_translator

# --- Configuration du Logging ---
os.makedirs("data/logs", exist_ok=True)
auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.DEBUG)
if not auth_logger.handlers:
    file_handler = logging.FileHandler("data/logs/auth.log")
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    auth_logger.addHandler(file_handler)

# --- Initialisation ---
ph = PasswordHasher()
auth_config = get_auth_config()

def get_local_storage():
    if 'local_storage' not in st.session_state:
        st.session_state.local_storage = LocalStorage()
    return st.session_state.local_storage


def _verify_jwt_token(token: str) -> Optional[Dict]:
    """Verify and decode a JWT token."""
    api_config = auth_config.get_api_config()
    try:
        payload = jwt.decode(
            token,
            api_config["jwt_secret"],
            algorithms=[api_config["jwt_algorithm"]]
        )
        return payload
    except jwt.ExpiredSignatureError:
        auth_logger.warning("JWT token expired.")
        return None
    except jwt.InvalidTokenError as e:
        auth_logger.warning(f"Invalid JWT token: {e}")
        return None


def _create_session(user_info, auth_method, t, token=None):
    """Crée et sauvegarde une session utilisateur."""
    from meilisearchcrawler.session_manager import get_session_manager
    session_manager = get_session_manager()
    session_id = session_manager.create_session(
        email=user_info.get("email", ""),
        user_info=user_info,
        auth_method=auth_method,
        token=token
    )
    st.session_state.update({
        'authenticated': True,
        'auth_method': auth_method,
        'user_info': user_info,
        'persistent_session_id': session_id
    })
    if token: st.session_state.oauth_token = token
    get_local_storage().setItem('auth_session_id', session_id)
    get_local_storage().setItem('auth_token', token) # Store JWT in local storage
    st.rerun()


def check_authentication():
    """
    Vérifie si l'utilisateur est authentifié et gère le flux de connexion.
    """
    from meilisearchcrawler.session_manager import get_session_manager
    t = get_translator(st.session_state.get('lang', 'fr'))

    # 1. Check for existing Streamlit session state
    if st.session_state.get('authenticated'):
        return st.session_state.get('user_info')

    # 2. Check for proxy authentication headers from Caddy
    # Caddy forward les headers après avoir vérifié l'authentification avec authcrunch
    if auth_config.has_provider(AuthProvider.PROXY):
        # Streamlit >= 1.30 expose les headers via st.context
        headers = {}
        try:
            headers = st.context.headers or {}
        except Exception as e:
            auth_logger.debug(f"Failed to get headers from st.context: {e}")

        # Log all headers for debugging (in lowercase)
        auth_logger.debug(f"Received headers: {headers}")

        # authcrunch injecte automatiquement ces headers avec "inject headers with claims"
        # Try both lowercase and proper case
        auth_email = headers.get('x-token-user-email') or headers.get('X-Token-User-Email')
        auth_name = headers.get('x-token-user-name') or headers.get('X-Token-User-Name')

        auth_logger.debug(f"Proxy auth check: email={auth_email}, name={auth_name}")

        if auth_email:
            # Caddy a déjà vérifié l'authentification avec authcrunch
            # Pas besoin de vérifier une signature - on fait confiance à Caddy
            try:
                # Obtenir un JWT depuis l'API
                api_url = os.getenv("API_URL", "http://localhost:8080/api")
                response = requests.post(
                    f"{api_url}/auth/token/headers",
                    headers={
                        "X-Token-User-Email": auth_email,
                        "X-Token-User-Name": auth_name or auth_email
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    token_data = response.json()
                    jwt_token = token_data.get("access_token")

                    # Stocker le JWT dans localStorage
                    get_local_storage().setItem('auth_token', jwt_token)

                    # Créer la session
                    user_info = {
                        "sub": auth_email,
                        "name": auth_name or auth_email,
                        "email": auth_email
                    }

                    session_manager = get_session_manager()
                    session_id = session_manager.create_session(
                        email=auth_email,
                        user_info=user_info,
                        auth_method="proxy",
                        token=jwt_token
                    )

                    st.session_state.update({
                        'authenticated': True,
                        'auth_method': 'proxy',
                        'user_info': user_info,
                        'oauth_token': jwt_token,
                        'persistent_session_id': session_id
                    })

                    auth_logger.info(f"Authenticated via proxy for {auth_email}")
                    st.rerun()
                else:
                    auth_logger.error(f"Failed to get JWT from API: {response.status_code}")
            except Exception as e:
                auth_logger.error(f"Error getting JWT from API: {e}")

    # 3. Check for JWT in localStorage
    auth_token = get_local_storage().getItem('auth_token')
    if auth_token:
        payload = _verify_jwt_token(auth_token)
        if payload:
            # Recreate session from JWT payload
            user_info = {
                "sub": payload.get("sub"),
                "name": payload.get("name", "User"),
                "email": payload.get("email", "")
            }
            auth_method = payload.get("auth_method", "jwt")

            # Create a persistent session in the backend
            session_manager = get_session_manager()
            session_id = session_manager.create_session(
                email=user_info.get("email", ""),
                user_info=user_info,
                auth_method=auth_method,
                token=auth_token # Store the JWT itself as the token
            )

            st.session_state.update({
                'authenticated': True,
                'auth_method': auth_method,
                'user_info': user_info,
                'oauth_token': auth_token, # Store the JWT here
                'persistent_session_id': session_id
            })
            auth_logger.info(f"Authenticated via JWT for {user_info.get('email')}")
            return user_info
        else:
            auth_logger.warning("Invalid or expired JWT found in localStorage. Clearing.")
            get_local_storage().deleteItem('auth_token')
            get_local_storage().deleteItem('auth_session_id') # Also clear session ID if token is bad

    # 4. Check for existing persistent session ID in localStorage (fallback/legacy)
    session_id = get_local_storage().getItem('auth_session_id')
    if session_id:
        session_data = get_session_manager().get_session(session_id)
        if session_data:
            st.session_state.update({
                'authenticated': True,
                'auth_method': session_data['auth_method'],
                'user_info': session_data['user_info'],
                'oauth_token': session_data.get('token'),
                'persistent_session_id': session_id
            })
            auth_logger.info(f"Authenticated via persistent session for {session_data.get('email')}")
            return st.session_state.user_info
        else:
            auth_logger.warning(f"Persistent session expired for session_id: {session_id}. Clearing.")
            get_local_storage().deleteItem('auth_session_id')

    # 5. If authentication is disabled, allow anonymous access
    if not auth_config.is_enabled:
        st.session_state.authenticated = True
        return {"name": "Anonymous", "email": ""}

    # 6. If no authentication found, display login options
    auth_logger.warning(f"No authentication found. Configured providers: {auth_config.providers}")

    st.title(f"🔒 {t('auth_required')}")
    st.markdown(t('please_log_in'))
    st.markdown("---")
    st.subheader(t('choose_auth_method'))

    form_providers = [p for p in auth_config.providers if p != AuthProvider.PROXY]

    if not form_providers:
        auth_logger.error(f"No form providers available. All providers: {auth_config.providers}, Proxy configured: {auth_config.has_provider(AuthProvider.PROXY)}")
        st.error(t('no_auth_configured'))
        st.info(t('auth_config_help'))
        st.warning("⚠️ Si vous utilisez l'authentification par proxy (Caddy), cette page ne devrait jamais s'afficher. Vérifiez votre configuration Caddy.")
        st.code(f"AUTH_PROVIDERS={os.getenv('AUTH_PROVIDERS')}\nAUTH_PROXY_ENABLED={os.getenv('AUTH_PROXY_ENABLED')}", language="bash")
        st.stop()

    if len(form_providers) == 1:
        provider = form_providers[0]
        if provider == AuthProvider.SIMPLE: _simple_auth(t)
        else: _sso_auth(provider.value, t)
    else:
        _show_auth_choices(form_providers, t)

    st.stop()

def _show_auth_choices(providers, t):
    """Affiche les boutons pour choisir une méthode d'authentification."""
    cols = st.columns(len(providers))
    for idx, provider in enumerate(providers):
        with cols[idx]:
            if provider == AuthProvider.OIDC:
                if st.button(f"🔐 {t('login_with_oidc')}", key="btn_oidc", width='stretch', help=t('login_with_oidc_help')):
                    st.session_state.selected_auth_method = "oidc"
                    st.rerun()
            elif provider == AuthProvider.GOOGLE:
                if st.button("🔵 Google", key="btn_google", width='stretch', help=t('login_with_google_help')):
                    st.session_state.selected_auth_method = "google"
                    st.rerun()
            elif provider == AuthProvider.GITHUB:
                if st.button("⚫ GitHub", key="btn_github", width='stretch', help=t('login_with_github_help')):
                    st.session_state.selected_auth_method = "github"
                    st.rerun()
            elif provider == AuthProvider.SIMPLE:
                if st.button(f"🔑 {t('simple_password')}", key="btn_password", width='stretch', help=t('login_with_password_help')):
                    st.session_state.selected_auth_method = "password"
                    st.rerun()

    selected_method = st.session_state.get('selected_auth_method')
    if selected_method:
        st.markdown("---")
        if st.button(f"← {t('back_to_methods')}", key="back_button"):
            st.session_state.selected_auth_method = None
            st.rerun()
        if selected_method == "password": _simple_auth(t)
        else: _sso_auth(selected_method, t)

def logout():
    """Déconnecte l'utilisateur."""
    from meilisearchcrawler.session_manager import get_session_manager
    if 'persistent_session_id' in st.session_state:
        get_session_manager().delete_session(st.session_state['persistent_session_id'])
    
    get_local_storage().deleteItem('auth_session_id')
    get_local_storage().deleteItem('auth_token') # Clear JWT from local storage
    
    # Nettoyer la session Streamlit
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    # Redirection après déconnexion
    proxy_config = auth_config.get_proxy_config()
    if auth_config.has_provider(AuthProvider.PROXY) and proxy_config:
        logout_url = proxy_config.get("logout_url", "/")
        st.markdown(f'<meta http-equiv="refresh" content="0; url={logout_url}">', unsafe_allow_html=True)
        st.stop()
    else:
        st.rerun()

def show_user_widget(t):
    """Affiche le widget utilisateur dans la barre latérale."""
    if st.session_state.get('authenticated'):
        user_info = st.session_state.get('user_info', {})
        auth_method = st.session_state.get('auth_method', 'unknown')
        
        with st.sidebar:
            st.markdown("---")
            st.markdown(f"**👤 {user_info.get('name', 'User')}**")
            if user_info.get('email'): st.caption(f"📧 {user_info['email']}")

            method_map = {
                "oidc": f"🔐 {t('connected_via_oidc')}",
                "google": f"🔵 {t('connected_via_google')}",
                "github": f"⚫ {t('connected_via_github')}",
                "simple": f"🔑 {t('connected_via_password')}",
                "proxy": f"🛡️ {t('connected_via_proxy')}"
            }
            st.caption(method_map.get(auth_method, ""))

            if st.button(t('logout_button'), key="logout_btn", width='stretch'):
                logout()


def _simple_auth(t):
    """Authentification par mot de passe simple."""
    with st.form("password_form"):
        st.markdown(f"### {t('simple_password')}")
        password = st.text_input(t('password'), type="password", key="simple_password_input")
        submit = st.form_submit_button(t('login'))

        if submit:
            dashboard_password = os.getenv("DASHBOARD_PASSWORD")
            if not dashboard_password:
                st.error("Mot de passe non configuré dans .env (DASHBOARD_PASSWORD)")
                auth_logger.error("DASHBOARD_PASSWORD not set in environment")
                return

            try:
                # Verify password
                if password == dashboard_password:
                    user_info = {
                        "sub": "dashboard_user",
                        "name": "Dashboard User",
                        "email": "dashboard@local"
                    }
                    _create_session(user_info, "simple", t)
                else:
                    st.error(t('invalid_password'))
                    auth_logger.warning("Invalid password attempt")
            except Exception as e:
                st.error(f"Erreur: {e}")
                auth_logger.error(f"Simple auth error: {e}")


def _sso_auth(provider, t):
    """Authentification SSO (OIDC, Google, GitHub)."""
    st.info(f"🔄 L'authentification {provider.upper()} n'est pas encore implémentée dans cette version.")
    st.markdown("Pour utiliser l'authentification SSO, configurez l'authentification par proxy avec Caddy + authcrunch.")
    auth_logger.info(f"SSO auth requested for provider: {provider}")
