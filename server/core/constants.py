# System tables blocked from CRUD API access
HIDDEN_TABLES = ["alembic_version", "metadata_creation", "metadata_updates", "file_registry", "users"]

# Tables hidden from the frontend table listing (superset of HIDDEN_TABLES)
UNLISTED_TABLES = [*HIDDEN_TABLES, "corrupted_rows", "test_database", "thi_database", "test_data", "test_data_corrupted"]

# Suffixes that mark internal DLT tables (e.g., owls__corrupted)
HIDDEN_TABLE_SUFFIXES = ["__corrupted"]
