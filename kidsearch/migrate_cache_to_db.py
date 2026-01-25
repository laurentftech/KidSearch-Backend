# meilisearchcrawler/migrate_cache_to_db.py
import json
import os
import sqlite3
from urllib.parse import urlparse
import yaml
import time
from datetime import datetime

def find_site_name(domain, sites_config):
    """Trouve le nom du site correspondant à un domaine."""
    domain = domain.replace('www.', '')
    for site in sites_config:
        site_domain = urlparse(site['crawl']).netloc.replace('www.', '')
        if site_domain == domain:
            return site['name']
    return domain  # Fallback to domain

def migrate_json_to_db():
    """
    Script de migration unique pour transférer les données de l'ancien cache
    JSON (crawler_cache.json) vers la nouvelle base de données SQLite.
    """
    print("🔄 Migration du cache JSON vers SQLite...")

    # --- Configuration des chemins ---
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_file = os.path.join(project_root, 'data', 'crawler_cache.json')
        db_file = os.path.join(project_root, 'data', 'crawler_cache.db')
        sites_yml = os.path.join(project_root, 'config', 'sites.yml')
    except NameError: # __file__ is not defined in some environments
        print("❌ Impossible de déterminer les chemins des fichiers. Exécutez ce script directement.")
        return

    if not os.path.exists(cache_file):
        print(f"✅ Le fichier cache JSON '{os.path.basename(cache_file)}' n'existe pas. Aucune migration nécessaire.")
        return

    # --- Charger la configuration des sites ---
    sites_config = []
    try:
        with open(sites_yml, 'r', encoding='utf-8') as f:
            sites_data = yaml.safe_load(f)
            sites_config = sites_data.get("sites", sites_data)
        print(f"✓ Configuration de {len(sites_config)} sites chargée depuis '{os.path.basename(sites_yml)}'.")
    except FileNotFoundError:
        print(f"⚠️  Fichier '{os.path.basename(sites_yml)}' introuvable. Le 'site_name' sera déduit du domaine.")
    except Exception as e:
        print(f"❌ Erreur de lecture de '{os.path.basename(sites_yml)}': {e}")
        return

    # --- Connexion et initialisation de la DB ---
    from kidsearch.cache_db import CacheDB
    print(f"Initialisation de la base de données SQLite : {os.path.basename(db_file)}")
    db = CacheDB(db_path=db_file)
    db.clear_all() # On part d'une base propre pour la migration

    # --- Lecture de l'ancien cache ---
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            old_cache = json.load(f)
        print(f"✓ Ancien cache '{os.path.basename(cache_file)}' chargé.")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ Erreur lors de la lecture de l'ancien cache: {e}")
        return

    urls_to_migrate = []
    sessions_to_migrate = []

    # --- Préparation des données ---
    # 1. URLs
    for url, data in old_cache.items():
        if url == '_meta' or not isinstance(data, dict):
            continue

        domain = urlparse(url).netloc
        site_name = find_site_name(domain, sites_config)
        
        urls_to_migrate.append((
            url,
            data.get('content_hash', ''),
            data.get('doc_id', ''),
            data.get('last_crawl', time.time()),
            data.get('crawl_date', datetime.now().isoformat()),
            data.get('etag'),
            data.get('last_modified'),
            site_name,
            data.get('crawl_date', datetime.now().isoformat()) # indexed_at
        ))

    # 2. Sessions
    if '_meta' in old_cache and 'crawls' in old_cache['_meta']:
        for site_name, session_data in old_cache['_meta']['crawls'].items():
            sessions_to_migrate.append((
                site_name,
                session_data.get('started', datetime.now().isoformat()),
                1 if session_data.get('completed', False) else 0,
                session_data.get('finished'),
                session_data.get('domain'),
                json.dumps(session_data.get('resume_from')) if session_data.get('resume_from') else None
            ))

    # --- Insertion en masse ---
    try:
        with sqlite3.connect(db_file) as conn:
            print(f"Migrating {len(urls_to_migrate)} URLs...")
            conn.executemany("""
                INSERT OR REPLACE INTO cache 
                (url, content_hash, doc_id, last_crawl, crawl_date, etag, last_modified, site_name, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, urls_to_migrate)

            print(f"Migrating {len(sessions_to_migrate)} crawl sessions...")
            conn.executemany("""
                INSERT OR REPLACE INTO crawl_sessions 
                (site_name, started, completed, finished, domain, resume_urls)
                VALUES (?, ?, ?, ?, ?, ?)
            """, sessions_to_migrate)
            
            conn.commit()
    except Exception as e:
        print(f"❌ Erreur lors de l'écriture dans la base de données: {e}")
        return

    print("\n" + "="*40)
    print("✅ Migration terminée avec succès !")
    print(f"   - {len(urls_to_migrate)} URLs migrées.")
    print(f"   - {len(sessions_to_migrate)} sessions de crawl migrées.")
    print(f"   - Nouvelle DB: {db_file}")
    print(f"⚠️  Vous pouvez maintenant archiver ou supprimer le fichier : {cache_file}")
    print("="*40)

if __name__ == "__main__":
    migrate_json_to_db()
