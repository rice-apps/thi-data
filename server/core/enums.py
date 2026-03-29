from enum import Enum

class FileStatus(str, Enum):
    """Enum for file processing status in the registry."""
    UPLOADED = "UPLOADED"
    SCHEMA_INFERRED = "SCHEMA_INFERRED"
    FRICTIONLESS_FAILED = "FRICTIONLESS_FAILED"
    SCHEMA_CONFIRMED = "SCHEMA_CONFIRMED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DELETED = "DELETED"
