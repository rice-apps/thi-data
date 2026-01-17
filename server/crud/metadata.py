from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, text
from typing import Any, List, Dict, Optional
import logging

def get_database_size(name: str, db: Session) -> Optional[Dict[str, str]]:
    """
    Attempts to get table size. Safe for Postgres. 
    Returns None if the DB dialect doesn't support pg_total_relation_size.
    """
    try:
        stmt = select(func.pg_size_pretty(func.pg_total_relation_size(name)))
        size = db.execute(stmt).scalar()
        if size is None:
             return None
        return {"table": name, "size": size}
    except Exception:
        # Gracefully fail for non-Postgres databases (SQLite, MySQL, etc.)
        return None

def get_tables_metadata(
    db: Session, 
    table_names: List[str], 
    creation_model: Any, 
    updates_model: Any
) -> List[Dict[str, Any]]:
    """
    Efficiently fetches metadata for multiple tables.
    - Uses bulk queries for creation/update records (ORM, DB-agnostic).
    - Fetches all table sizes in a single query (Postgres optimized).
    """
    
    # 1. Bulk Fetch Creation Records
    creation_map = {} # table_name -> creation_record
    if creation_model and table_names:
        try:
            stmt = select(creation_model).where(creation_model.table_name.in_(table_names))
            records = db.execute(stmt).scalars().all()
            creation_map = {r.table_name: r for r in records}
        except Exception as e:
            logging.warning(f"Failed to fetch creation metadata: {e}")

    # 2. Bulk Fetch Latest Updates
    updates_map = {} # foreign_key -> update_record
    if updates_model and creation_map:
        try:
            creation_ids = [r.id for r in creation_map.values() if getattr(r, 'id', None)]
            if creation_ids:
                stmt = (
                    select(updates_model)
                    .where(updates_model.foreign_key.in_(creation_ids))
                    .order_by(desc(updates_model.updated_at))
                )
                all_updates = db.execute(stmt).scalars().all()
                for u in all_updates:
                    fk = getattr(u, 'foreign_key', None)
                    if fk and fk not in updates_map:
                        updates_map[fk] = u
        except Exception as e:
            logging.warning(f"Failed to fetch update metadata: {e}")

    # 3. Bulk Fetch All Table Sizes (Postgres optimized)
    size_map = {}
    if table_names:
        try:
            # Construct a single query to get all sizes
            # We use pg_total_relation_size in a subquery or join-like structure
            # A more portable but still bulk way is to union or use a values list
            # For Postgres, we can query pg_class/pg_namespace or just mapping
            
            # Efficient bulk size query for Postgres
            size_query = text("""
                SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
                FROM (
                    SELECT c.oid as relid, c.relname
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relkind
                    WHERE c.relname = ANY(:names)
                    AND c.relkind = 'r'
                ) s
            """)
            # Actually, pg_total_relation_size accepts text as well (table name)
            # Simplest bulk query:
            size_query = text("""
                SELECT t.name, pg_size_pretty(pg_total_relation_size(t.name::regclass))
                FROM unnest(:names::text[]) AS t(name)
            """)
            
            size_results = db.execute(size_query, {"names": table_names}).all()
            size_map = {row[0]: row[1] for row in size_results}
        except Exception as e:
            logging.warning(f"Failed to fetch bulk sizes: {e}. Falling back to individual (or none).")

    # 4. Assemble Results
    results = []
    for name in table_names:
        info = {
            "name": name,
            "uploadedBy": None,
            "dateUploaded": None,
            "dateModified": None,
            "size": size_map.get(name)
        }
        
        # Populate Creation Info
        c_rec = creation_map.get(name)
        if c_rec:
            info["uploadedBy"] = getattr(c_rec, "created_by", None)
            c_at = getattr(c_rec, "created_at", None)
            if c_at:
                info["dateUploaded"] = c_at.strftime("%m-%d-%Y")
            
            # Populate Update Info
            c_id = getattr(c_rec, "id", None)
            u_rec = updates_map.get(c_id)
            if u_rec:
                u_at = getattr(u_rec, "updated_at", None)
                if u_at:
                    info["dateModified"] = u_at.strftime("%m-%d-%Y")
        
        # Fallback
        if not info["dateModified"] and info["dateUploaded"]:
             info["dateModified"] = info["dateUploaded"]
             
        results.append(info)
        
    return results



