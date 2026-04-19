"""Infer frictionless schema from an uploaded file and persist to file_registry."""

from __future__ import annotations

import logging
from typing import Any, List

from sqlalchemy.orm import Session

from core.enums import FileStatus
from core.storage import StorageProvider
from crud.base import BaseRepository
from services.schema_inferencer import infer_from_file

logger = logging.getLogger(__name__)


class FileSchemaService:
    def __init__(
        self,
        db: Session,
        storage: StorageProvider,
        repo: BaseRepository,
    ):
        self._db = db
        self._storage = storage
        self._repo = repo

    def infer_and_persist(self, file_id: str) -> dict:
        """
        Load file from storage, infer columns, update registry to SCHEMA_INFERRED.
        Raises LookupError if registry or storage object is missing.
        On inference failure, sets FRICTIONLESS_FAILED and raises RuntimeError.
        """
        logger.info("Starting schema validation for file_id: %s", file_id)
        records = self._repo.get_by_field(
            db=self._db, field_name="file_id", value=file_id
        )
        if not records:
            logger.warning("File ID not found in registry: %s", file_id)
            raise LookupError("File ID not found in registry")

        record = records[0]
        object_key = record.object_key
        logger.debug("Retrieved file record with object_key: %s", object_key)

        file_path = self._storage.get_file_path(object_key)
        if not file_path:
            logger.error("File object not found in storage: %s", object_key)
            raise LookupError("File object not found in storage")

        logger.info("Inferring schema from file: %s", file_path)
        try:
            result = infer_from_file(str(file_path))
            fields = result["schema"]["fields"]
            columns: List[dict[str, Any]] = [
                {"name": f["name"], "type": f["type"]}
                for f in fields
                if not (f["name"].startswith("field") and f["name"][5:].isdigit())
            ]
            logger.info("Schema inferred successfully with %s columns", len(columns))

            self._repo.update_by_field(
                db=self._db,
                search_field="file_id",
                search_value=file_id,
                update_data={
                    "file_schema": {"fields": columns},
                    "status": FileStatus.SCHEMA_INFERRED,
                },
            )
            logger.info("File registry updated with inferred schema for file_id: %s", file_id)
            return {"file_id": file_id, "columns": columns}

        except Exception as e:
            logger.error(
                "Schema inference failed for file_id %s: %s",
                file_id,
                e,
                exc_info=True,
            )
            try:
                self._repo.update_by_field(
                    db=self._db,
                    search_field="file_id",
                    search_value=file_id,
                    update_data={"status": FileStatus.FRICTIONLESS_FAILED},
                )
                logger.info("File status updated to FRICTIONLESS_FAILED for file_id: %s", file_id)
            except Exception:
                logger.error("Failed to update file status for file_id %s", file_id)

            raise RuntimeError(
                "Could not detect columns automatically. Please check the file format."
            ) from e
