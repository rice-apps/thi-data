from supabase import create_client
from core.config import storage_settings

_client = None

def get_supabase_client():
    global _client
    if _client is None:
        if not storage_settings.STORAGE_URL or not storage_settings.STORAGE_KEY:
            raise RuntimeError("Storage credentials are not set.")
        _client = create_client(storage_settings.STORAGE_URL, storage_settings.STORAGE_KEY)
    return _client