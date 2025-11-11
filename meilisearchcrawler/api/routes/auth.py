"""
Routes d'authentification pour l'API FastAPI.
Gère le login via OIDC et la génération de JWT.
"""

import os
import logging
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

from meilisearchcrawler.auth_config import get_auth_config, AuthProvider
from ..auth import jwt_handler, oidc_client

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenResponse(BaseModel):
    """Réponse contenant le JWT."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfoResponse(BaseModel):
    """Informations utilisateur."""
    sub: str
    name: str
    email: str
    auth_method: str


@router.get("/auth/login")
async def login(redirect_uri: Optional[str] = Query(None, description="Optional redirect URI after login")):
    """
    Initie le flux d'authentification OIDC.
    """
    auth_config = get_auth_config()
    if not auth_config.is_enabled or not auth_config.has_provider(AuthProvider.OIDC):
        raise HTTPException(status_code=400, detail="OIDC authentication is not configured")

    config = auth_config.get_oidc_config()
    callback_uri = redirect_uri or os.getenv("OIDC_API_REDIRECT_URI", "http://localhost:8080/api/auth/callback")
    auth_params = {
        "client_id": config["client_id"],
        "redirect_uri": callback_uri,
        "response_type": "code",
        "scope": " ".join(config["scopes"]),
    }
    auth_url = f"{config['authorize_url']}?{urlencode(auth_params)}"
    return RedirectResponse(url=auth_url)


@router.get("/auth/callback")
async def callback(
    code: str = Query(..., description="Authorization code from OIDC provider"),
    redirect_uri: Optional[str] = Query(None, description="Optional redirect URI")
):
    """
    Callback OAuth2 depuis le provider OIDC.
    """
    auth_config = get_auth_config()
    if not auth_config.has_provider(AuthProvider.OIDC):
        raise HTTPException(status_code=400, detail="OIDC authentication is not configured")

    callback_uri = redirect_uri or os.getenv("OIDC_API_REDIRECT_URI", "http://localhost:8080/api/auth/callback")
    token_data = await oidc_client.exchange_code_for_token(code, callback_uri)
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    user_info = await oidc_client.get_user_info(token_data.get("access_token"))
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    jwt_data = {
        "sub": user_info.get("sub"),
        "name": user_info.get("name", user_info.get("preferred_username", "User")),
        "email": user_info.get("email", ""),
        "auth_method": "oidc",
    }
    jwt_token = jwt_handler.create_access_token(jwt_data)
    return TokenResponse(
        access_token=jwt_token,
        token_type="bearer",
        expires_in=auth_config.get_api_config()["jwt_expiration_minutes"] * 60
    )


@router.post("/auth/token/headers")
async def issue_token_for_proxy_headers(request: Request):
    """
    Point de terminaison pour l'authentification par proxy (authcrunch/Caddy).
    Génère un JWT basé sur les headers injectés par authcrunch.

    Headers attendus (injectés automatiquement par authcrunch avec "inject headers with claims"):
    - X-Token-User-Email: Email de l'utilisateur (vérifié par authcrunch)
    - X-Token-User-Name: Nom de l'utilisateur (optionnel)

    Sécurité: Cette route doit UNIQUEMENT être accessible depuis le réseau interne
    ou via Caddy. En production, configurez votre firewall pour bloquer l'accès direct.
    """
    auth_config = get_auth_config()
    proxy_config = auth_config.get_proxy_config()
    if not proxy_config:
        raise HTTPException(status_code=400, detail="Proxy authentication is not configured")

    # Récupérer l'email et le nom depuis les headers authcrunch
    auth_email = request.headers.get("X-Token-User-Email")
    auth_name = request.headers.get("X-Token-User-Name")

    if not auth_email:
        logger.error(f"Proxy auth failed: No email header. Headers: {dict(request.headers)}")
        raise HTTPException(status_code=401, detail="Email header not provided by proxy")

    # Vérifier que l'email est autorisé (si whitelist configurée)
    if not auth_config.is_email_allowed(auth_email):
        logger.warning(f"Proxy auth rejected: Email not in whitelist: {auth_email}")
        raise HTTPException(status_code=403, detail="Access denied: Email not authorized")

    # Générer le JWT
    jwt_data = {
        "sub": auth_email,
        "name": auth_name or auth_email,
        "email": auth_email,
        "auth_method": "proxy",
    }
    jwt_token = jwt_handler.create_access_token(jwt_data)

    logger.info(f"JWT token issued for proxy user: {auth_email}")

    return TokenResponse(
        access_token=jwt_token,
        token_type="bearer",
        expires_in=auth_config.get_api_config()["jwt_expiration_minutes"] * 60
    )


@router.get("/auth/me", response_model=UserInfoResponse)
async def get_current_user_info(request: Request):
    """
    Récupère les informations de l'utilisateur authentifié.
    """
    from ..auth import get_current_user
    user = await get_current_user(request.headers.get("Authorization"))
    return UserInfoResponse(
        sub=user.get("sub", ""),
        name=user.get("name", ""),
        email=user.get("email", ""),
        auth_method=user.get("auth_method", "unknown")
    )


@router.post("/auth/logout")
async def logout():
    """
    Déconnexion (invalide le token côté client).
    """
    return {"message": "Logged out successfully. Please delete your access token."}


import os
