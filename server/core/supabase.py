from supabase import create_client
from core.config import settings

_client = None

def get_supabase_client():
    global _client
    if _client is None:
        if not settings.STORAGE_URL or not settings.STORAGE_SERVICE_KEY:
            raise RuntimeError("Storage credentials are not set.")
        _client = create_client(settings.STORAGE_URL, settings.STORAGE_SERVICE_KEY)
    return _client
