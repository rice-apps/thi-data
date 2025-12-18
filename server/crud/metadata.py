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
    - Checks size individually (Graceful fallback if not Postgres).
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
                # Fetch all updates for these tables, ordered by date desc
                stmt = (
                    select(updates_model)
                    .where(updates_model.foreign_key.in_(creation_ids))
                    .order_by(desc(updates_model.updated_at))
                )
                all_updates = db.execute(stmt).scalars().all()
                
                # Deduplicate: first one seen is latest
                for u in all_updates:
                    fk = getattr(u, 'foreign_key', None)
                    if fk and fk not in updates_map:
                        updates_map[fk] = u
        except Exception as e:
            logging.warning(f"Failed to fetch update metadata: {e}")

    # 3. Assemble Results
    results = []
    for name in table_names:
        info = {
            "name": name,
            "uploadedBy": None,
            "dateUploaded": None,
            "dateModified": None,
            "size": None
        }
        
        # Get Size (Safe / Individual Check)
        size_data = get_database_size(name, db)
        if size_data:
            info["size"] = size_data.get("size")
        
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



