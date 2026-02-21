"""
Client API centralisé pour le Dashboard.
Gère automatiquement l'ajout du JWT dans les headers.
"""

import os
import requests
import streamlit as st
from typing import Optional, Dict, Any
from streamlit_local_storage import LocalStorage


class APIClient:
    """Client HTTP pour communiquer avec l'API backend avec support JWT."""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialise le client API.

        Args:
            base_url: URL de base de l'API. Si None, utilise API_URL depuis l'environnement.
        """
        self.base_url = base_url or os.getenv("API_URL", "http://localhost:8080/api")
        self.local_storage = None

    def _get_local_storage(self):
        """Récupère l'instance LocalStorage."""
        if self.local_storage is None:
            if "local_storage" not in st.session_state:
                st.session_state.local_storage = LocalStorage()
            self.local_storage = st.session_state.local_storage
        return self.local_storage

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Récupère les headers d'authentification avec le JWT.

        Returns:
            Dictionnaire avec le header Authorization si un JWT est disponible.
        """
        headers = {}

        # Essayer de récupérer le JWT depuis session_state
        jwt_token = st.session_state.get("oauth_token")

        # Si pas dans session_state, essayer localStorage
        if not jwt_token:
            try:
                jwt_token = self._get_local_storage().getItem("auth_token")
            except Exception:
                pass

        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        return headers

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs
    ) -> requests.Response:
        """
        Effectue une requête GET avec authentification JWT.

        Args:
            endpoint: Endpoint de l'API (ex: "/search", "/health")
            params: Paramètres de requête (query string)
            **kwargs: Arguments supplémentaires pour requests.get()

        Returns:
            Response object de requests
        """
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_headers())

        return requests.get(url, params=params, headers=headers, **kwargs)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Effectue une requête POST avec authentification JWT.

        Args:
            endpoint: Endpoint de l'API (ex: "/stats/reset")
            data: Données du formulaire
            json: Données JSON
            **kwargs: Arguments supplémentaires pour requests.post()

        Returns:
            Response object de requests
        """
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_headers())

        return requests.post(url, data=data, json=json, headers=headers, **kwargs)

    def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Effectue une requête PUT avec authentification JWT.

        Args:
            endpoint: Endpoint de l'API
            data: Données du formulaire
            json: Données JSON
            **kwargs: Arguments supplémentaires pour requests.put()

        Returns:
            Response object de requests
        """
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_headers())

        return requests.put(url, data=data, json=json, headers=headers, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """
        Effectue une requête DELETE avec authentification JWT.

        Args:
            endpoint: Endpoint de l'API
            **kwargs: Arguments supplémentaires pour requests.delete()

        Returns:
            Response object de requests
        """
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_headers())

        return requests.delete(url, headers=headers, **kwargs)


# Instance globale du client API
_api_client: Optional[APIClient] = None


def get_api_client() -> APIClient:
    """
    Retourne l'instance globale du client API.

    Returns:
        Instance d'APIClient configurée.
    """
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
