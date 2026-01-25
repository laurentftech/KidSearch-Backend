import streamlit as st
import os
import yaml
import re
import json
from .config import SITES_CONFIG_FILE, LOG_FILE, STATUS_FILE, HISTORY_FILE
from .typesense_client import get_typesense_client

@st.cache_data(ttl=30)  # Cache for 30 seconds
def load_sites_config():
    try:
        with open(SITES_CONFIG_FILE, "r", encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return None

def save_sites_config(config_data):
    try:
        with open(SITES_CONFIG_FILE, "w", encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde de la configuration des sites: {e}")
        return False

@st.cache_data(ttl=5)  # Cache for 5 seconds - frequently updated during crawling
def load_status():
    try:
        with open(STATUS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

@st.cache_data(ttl=10)  # Cache for 10 seconds
def load_crawl_history():
    try:
        with open(HISTORY_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_crawl_history(status, max_entries=100):
    history = load_crawl_history()
    new_entry = {
        "timestamp": status.get("timestamp"),
        "pages_indexed": status.get("pages_indexed", 0),
        "errors": status.get("errors", 0),
        "duration": status.get("last_crawl_duration_sec", 0)
    }
    if history and history[-1].get("timestamp") == new_entry["timestamp"]:
        return
    history.append(new_entry)
    if len(history) > max_entries:
        history = history[-max_entries:]
    try:
        with open(HISTORY_FILE, "w", encoding='utf-8') as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save crawl history: {e}")

def load_cache_stats():
    # This function is deprecated as cache is now in SQLite
    return {"total_urls": 0, "sites": 0}

@st.cache_data(ttl=30)  # Cache for 30 seconds
def parse_logs_for_errors(limit=100):
    errors = []
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if 'ERROR' in line:
                    match = re.search(r'\[(.*?)\] \[ERROR\] \[.*?\] (.*)', line)
                    if match:
                        errors.append({"timestamp": match.group(1), "message": match.group(2)})
    except FileNotFoundError:
        pass
    return errors[-limit:]
