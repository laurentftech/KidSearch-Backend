"""
Gestionnaire de sessions persistantes pour l'authentification.
Stocke les sessions utilisateur avec expiration automatique.
"""

import os
import time
import secrets
from typing import Dict, Optional
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Gère les sessions utilisateur persistantes avec expiration."""

    def __init__(self, expiration_minutes: int = 1440):
        """
        Initialise le gestionnaire de sessions.

        Args:
            expiration_minutes: Durée de vie d'une session en minutes (par défaut 24h)
        """
        self._sessions: Dict[str, Dict] = {}
        self._lock = Lock()
        self.expiration_seconds = expiration_minutes * 60
        logger.info(f"SessionManager initialized with {expiration_minutes} minutes expiration")

    def create_session(
        self,
        email: str,
        user_info: Dict,
        auth_method: str,
        token: Optional[str] = None
    ) -> str:
        """
        Crée une nouvelle session utilisateur.

        Args:
            email: Email de l'utilisateur
            user_info: Informations utilisateur (dict avec 'name', 'email', 'sub', etc.)
            auth_method: Méthode d'authentification utilisée ('proxy', 'oidc', 'google', etc.)
            token: Token JWT optionnel

        Returns:
            session_id: Identifiant unique de la session
        """
        session_id = secrets.token_urlsafe(32)

        with self._lock:
            self._sessions[session_id] = {
                'email': email,
                'user_info': user_info,
                'auth_method': auth_method,
                'token': token,
                'created_at': time.time(),
                'expires_at': time.time() + self.expiration_seconds
            }

        logger.info(f"Session created for {email} (method: {auth_method}, id: {session_id[:8]}...)")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Récupère les données d'une session.

        Args:
            session_id: Identifiant de la session

        Returns:
            Session data dict ou None si la session n'existe pas ou a expiré
        """
        with self._lock:
            session = self._sessions.get(session_id)

            if not session:
                logger.debug(f"Session not found: {session_id[:8]}...")
                return None

            # Vérifier l'expiration
            if time.time() > session['expires_at']:
                logger.info(f"Session expired for {session.get('email')} (id: {session_id[:8]}...)")
                del self._sessions[session_id]
                return None

            logger.debug(f"Session retrieved for {session.get('email')} (id: {session_id[:8]}...)")
            return session

    def delete_session(self, session_id: str) -> bool:
        """
        Supprime une session.

        Args:
            session_id: Identifiant de la session

        Returns:
            True si la session a été supprimée, False si elle n'existait pas
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)

        if session:
            logger.info(f"Session deleted for {session.get('email')} (id: {session_id[:8]}...)")
            return True

        logger.debug(f"Session not found for deletion: {session_id[:8]}...")
        return False

    def cleanup_expired_sessions(self):
        """Nettoie les sessions expirées (appelé périodiquement)."""
        now = time.time()
        expired_count = 0

        with self._lock:
            expired_ids = [
                sid for sid, session in self._sessions.items()
                if now > session['expires_at']
            ]

            for sid in expired_ids:
                del self._sessions[sid]
                expired_count += 1

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired sessions")

        return expired_count

    def get_active_sessions_count(self) -> int:
        """Retourne le nombre de sessions actives."""
        self.cleanup_expired_sessions()
        with self._lock:
            return len(self._sessions)


# Instance globale du gestionnaire de sessions
_session_manager: Optional[SessionManager] = None
_manager_lock = Lock()


def get_session_manager() -> SessionManager:
    """
    Retourne l'instance globale du gestionnaire de sessions (singleton).
    Initialise le gestionnaire avec la configuration JWT si ce n'est pas déjà fait.
    """
    global _session_manager

    if _session_manager is None:
        with _manager_lock:
            if _session_manager is None:
                # Récupérer l'expiration depuis les variables d'environnement
                expiration_minutes = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))
                _session_manager = SessionManager(expiration_minutes=expiration_minutes)

    return _session_manager
