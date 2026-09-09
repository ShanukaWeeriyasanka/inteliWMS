from datetime import datetime, timezone
from typing import List, Dict, Optional
import uuid
import json
from database.connection import SessionLocal, engine, Base
from database.models import SecurityAuditLog

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

class SecurityAuditLogger:
    """
    Production-grade Security & Threat Audit Logger for Task 1.
    Persists all security incidents, injection blocks, and access denials into the SQLite database.
    """
    
    def __init__(self, max_memory_cache: int = 100):
        self.max_memory_cache = max_memory_cache

    def log_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> Dict:
        """
        Record a security event into the database and audit trail.
        """
        evt_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        details_dict = details or {}
        details_json = json.dumps(details_dict)

        event_dict = {
            "id": evt_id,
            "timestamp": now.isoformat(),
            "event_type": event_type,
            "severity": severity.upper(),
            "user_id": user_id or "anonymous",
            "role": role or "unknown",
            "details": details_dict
        }

        # Persist to SQLite Database
        db = SessionLocal()
        try:
            db_log = SecurityAuditLog(
                event_id=evt_id,
                event_type=event_type,
                severity=severity.upper(),
                user_id=user_id or "anonymous",
                role=role or "unknown",
                details=details_json,
                created_at=now
            )
            db.add(db_log)
            db.commit()
            event_dict["db_id"] = db_log.id
        except Exception as e:
            db.rollback()
            print(f"[SECURITY AUDIT WARNING] Could not persist log to DB: {e}")
        finally:
            db.close()

        return event_dict

    def get_logs(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        """Fetch recent security logs from the database."""
        db = SessionLocal()
        try:
            query = db.query(SecurityAuditLog)
            if event_type and event_type != "ALL":
                query = query.filter(SecurityAuditLog.event_type == event_type)
            
            records = query.order_by(SecurityAuditLog.id.desc()).limit(limit).all()
            
            results = []
            for r in records:
                try:
                    parsed_details = json.loads(r.details) if r.details else {}
                except Exception:
                    parsed_details = {"raw": r.details}

                results.append({
                    "id": r.event_id or str(r.id),
                    "timestamp": r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
                    "event_type": r.event_type,
                    "severity": r.severity,
                    "user_id": r.user_id,
                    "role": r.role,
                    "details": parsed_details
                })
            return results
        finally:
            db.close()

    def clear_logs(self) -> None:
        """Clear database logs (primarily used for unit testing)."""
        db = SessionLocal()
        try:
            db.query(SecurityAuditLog).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_summary_stats(self) -> Dict[str, int]:
        """Aggregate security statistics from database."""
        db = SessionLocal()
        try:
            records = db.query(SecurityAuditLog.event_type).all()
            stats = {
                "total_events": len(records),
                "injections_blocked": 0,
                "permissions_denied": 0,
                "logins_success": 0,
                "logins_failed": 0,
                "requests_sanitized": 0
            }
            for (etype,) in records:
                if etype == "INJECTION_BLOCKED":
                    stats["injections_blocked"] += 1
                elif etype == "PERMISSION_DENIED":
                    stats["permissions_denied"] += 1
                elif etype == "LOGIN_SUCCESS":
                    stats["logins_success"] += 1
                elif etype == "LOGIN_FAILED":
                    stats["logins_failed"] += 1
                elif etype == "REQUEST_SANITIZED":
                    stats["requests_sanitized"] += 1
            return stats
        finally:
            db.close()

# Singleton instance
audit_logger = SecurityAuditLogger()
