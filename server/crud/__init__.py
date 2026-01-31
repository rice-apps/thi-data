# Expose functions to maintain API compatibility
from .generic import (
    model_to_dict, get_all_items, filter_text, get_one_item, 
    create_item, delete_item, update_item, get_items_by_field, get_items_by_date_range
)
from .metadata import get_database_size, get_tables_metadata
from .validation import infer_from_file 
