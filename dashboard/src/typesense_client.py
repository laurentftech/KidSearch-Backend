import streamlit as st
import typesense
import traceback
from typesense.exceptions import TypesenseClientError
from urllib.parse import urlparse
from .config import TYPESENSE_URL, TYPESENSE_API_KEY

@st.cache_resource
def get_typesense_client():
    """Establishes and caches a connection to the Typesense client."""
    if not TYPESENSE_URL or not TYPESENSE_API_KEY:
        st.error("TYPESENSE_URL and TYPESENSE_API_KEY must be set in your .env file.")
        return None

    try:
        # Parse URL using urllib for safety
        parsed = urlparse(TYPESENSE_URL)
        protocol = parsed.scheme or 'http'
        host = parsed.hostname or 'localhost'
        port = parsed.port or (443 if protocol == 'https' else 8108)

        config = {
            'nodes': [{
                'host': host,
                'port': str(port),
                'protocol': protocol
            }],
            'api_key': str(TYPESENSE_API_KEY),
            'connection_timeout_seconds': 10
        }

        client = typesense.Client(config)

        # Test connection by retrieving collections
        # This avoids using operations.perform which seems to have signature issues in the installed version
        client.collections.retrieve()
        return client

    except TypesenseClientError as e:
        st.error(f"Error connecting to Typesense: {e}. Please check if the service is running.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        st.write(f"Debug - Config used: {config if 'config' in locals() else 'Not created'}")
        st.write(f"Debug - Exception type: {type(e)}")
        st.code(traceback.format_exc())
        return None


def check_collection_exists(client, collection_name):
    """Check if a Typesense collection exists."""
    try:
        client.collections[collection_name].retrieve()
        return True
    except TypesenseClientError:
        return False
    except Exception:
        return False


def get_collection_stats(client, collection_name):
    """Get stats for a Typesense collection."""
    try:
        collection = client.collections[collection_name].retrieve()
        return {
            'number_of_documents': collection.get('num_documents', 0),
            'name': collection.get('name', collection_name)
        }
    except Exception as e:
        st.error(f"Error getting collection stats: {e}")
        return None


def get_collection(client, collection_name):
    """Get a Typesense collection object for direct operations."""
    try:
        return client.collections[collection_name]
    except Exception as e:
        st.error(f"Error getting collection: {e}")
        return None


def search_collection(client, collection_name, query="", **params):
    """Search a Typesense collection with given parameters."""
    try:
        collection = client.collections[collection_name]
        return collection.documents.search(params)
    except Exception as e:
        st.error(f"Error searching collection: {e}")
        return None


def get_documents(client, collection_name, **params):
    """Get documents from a Typesense collection."""
    try:
        collection = client.collections[collection_name]
        # Typesense uses export for bulk document retrieval
        # But for compatibility with the page, we'll use search with high limit
        if 'limit' not in params:
            params['limit'] = 250
        params['q'] = params.get('q', '*')  # Wildcard search to get all documents

        result = collection.documents.search(params)
        return result.get('hits', [])
    except Exception as e:
        st.error(f"Error getting documents: {e}")
        return []


def get_collection_schema(client, collection_name):
    """Get the schema/settings for a Typesense collection."""
    try:
        collection = client.collections[collection_name].retrieve()
        return collection
    except Exception as e:
        st.error(f"Error getting collection schema: {e}")
        return None
