from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, text
from typing import Any, List, Dict, Optional
import logging

def get_database_size(name: str, db: Session, dlt_schema: str = "clinical_data") -> Optional[Dict[str, str]]:
    """
    Get the total size of a table including indexes.
    Returns None if the table doesn't exist or sizing is unsupported.
    """
    try:
        stmt = text("""
            SELECT pg_size_pretty(pg_total_relation_size(
                COALESCE(to_regclass(quote_ident(:name)), to_regclass(:dlt_schema || '.' || quote_ident(:name)))
            ))
        """)
        size = db.execute(stmt, {"name": name, "dlt_schema": dlt_schema}).scalar()
        return {"table": name, "size": size} if size else None
    except Exception:
        return None

def get_tables_metadata(
    db: Session,
    table_names: List[str],
    creation_model: Any,
    updates_model: Any,
    dlt_schema: str = "clinical_data",
) -> List[Dict[str, Any]]:
    """
    Fetch comprehensive metadata for a list of tables in a single operation.
    """
    if not table_names:
        return []

    # 1. Bulk fetch creation records for all requested tables
    creation_map = {}
    if creation_model:
        try:
            stmt = select(creation_model).where(creation_model.table_name.in_(table_names))
            records = db.execute(stmt).scalars().all()
            creation_map = {r.table_name: r for r in records}
        except Exception as e:
            logging.error(f"Metadata creation fetch failed: {e}")

    # 2. Bulk fetch only the *latest* update record per table using Postgres DISTINCT ON
    updates_map = {}
    if updates_model and creation_map:
        try:
            creation_ids = [r.id for r in creation_map.values() if hasattr(r, 'id')]
            if creation_ids:
                stmt = (
                    select(updates_model)
                    .distinct(updates_model.foreign_key)
                    .where(updates_model.foreign_key.in_(creation_ids))
                    .order_by(updates_model.foreign_key, desc(updates_model.updated_at))
                )
                records = db.execute(stmt).scalars().all()
                updates_map = {r.foreign_key: r for r in records}
        except Exception as e:
            logging.error(f"Metadata updates fetch failed: {e}")

    # 3. Bulk fetch all table sizes in a single query to eliminate N+1 roundtrips.
    # Use to_regclass() which returns NULL for non-existent tables instead of throwing.
    # Try public schema first, then fall back to DLT schema for cross-schema tables.
    size_map = {}
    try:
        size_query = text("""
            SELECT name, pg_size_pretty(pg_total_relation_size(
                COALESCE(to_regclass(name), to_regclass(:dlt_schema || '.' || name))
            ))
            FROM unnest(CAST(:names AS text[])) AS name
        """)
        size_results = db.execute(size_query, {"names": table_names, "dlt_schema": dlt_schema}).all()
        size_map = {row[0]: row[1] for row in size_results if row[1]}
    except Exception as e:
        logging.warning(f"Bulk size fetch failed: {e}")

    # 4. Assemble final metadata list
    results = []
    for name in table_names:
        info = {
            "name": name,
            "uploadedBy": None,
            "dateUploaded": None,
            "dateModified": None,
            "size": size_map.get(name)
        }
        
        c_rec = creation_map.get(name)
        if c_rec:
            info["uploadedBy"] = getattr(c_rec, "created_by", None)
            if c_at := getattr(c_rec, "created_at", None):
                info["dateUploaded"] = c_at.strftime("%m-%d-%Y")
            
            u_rec = updates_map.get(getattr(c_rec, "id", None))
            if u_rec and (u_at := getattr(u_rec, "updated_at", None)):
                info["dateModified"] = u_at.strftime("%m-%d-%Y")
        
        # Fallback to upload date if no explicit modification is recorded
        if not info["dateModified"] and info["dateUploaded"]:
             info["dateModified"] = info["dateUploaded"]
             
        results.append(info)
        
    return results



