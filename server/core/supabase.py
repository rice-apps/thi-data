from supabase import create_client
from core.config import settings

supabase = create_client(
    settings.STORAGE_URL,
    settings.STORAGE_SERVICE_KEY,
)
