"""
Shift Handoff Management for Knowledge Agent.
Handles recording and retrieving warehouse shift transition logs, incidents, and pending tasks.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.connection import SessionLocal
from database.models import ShiftHandoff
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


def record_shift_handoff(
    shift_type: str,
    supervisor: str,
    summary: str,
    incidents: Optional[str] = None,
    pending_tasks: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Records a new shift handoff log in the database.
    
    Args:
        shift_type: "morning", "afternoon", "evening", or "night"
        supervisor: Name or staff ID of the outgoing supervisor
        summary: Operational overview of the shift
        incidents: Any safety issues, equipment faults, or spills
        pending_tasks: Tasks remaining for the next crew
        db: Optional SQLAlchemy database session
        
    Returns:
        Dict containing success status and formatted message.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        clean_shift = shift_type.strip().lower()
        handoff_entry = ShiftHandoff(
            shift_type=clean_shift,
            supervisor=supervisor.strip(),
            summary=summary.strip(),
            incidents=incidents.strip() if incidents else None,
            pending_tasks=pending_tasks.strip() if pending_tasks else None
        )
        db.add(handoff_entry)
        db.commit()
        db.refresh(handoff_entry)

        logger.log_event("SHIFT_HANDOFF_RECORDED", {
            "id": handoff_entry.id,
            "shift_type": clean_shift,
            "supervisor": supervisor,
            "has_incidents": bool(incidents)
        })

        msg = (
            f"✅ Shift handoff successfully logged for the {clean_shift.upper()} shift "
            f"(Supervisor: {supervisor}). Record ID: #{handoff_entry.id}."
        )

        return {
            "success": True,
            "id": handoff_entry.id,
            "shift_type": clean_shift,
            "supervisor": supervisor,
            "summary": summary,
            "incidents": incidents,
            "pending_tasks": pending_tasks,
            "created_at": handoff_entry.created_at.isoformat() if handoff_entry.created_at else datetime.utcnow().isoformat(),
            "formatted_message": msg
        }
    except Exception as e:
        if own_session:
            db.rollback()
        logger.log_event("SHIFT_HANDOFF_RECORD_ERROR", {"error": str(e)})
        return {
            "success": False,
            "error": str(e),
            "formatted_message": f"Failed to record shift handoff: {str(e)}"
        }
    finally:
        if own_session:
            db.close()


def get_latest_shift_handoff(
    shift_type: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Retrieves the most recent shift handoff report.
    
    Args:
        shift_type: Optional filter (e.g., 'morning', 'night')
        db: Optional SQLAlchemy session
        
    Returns:
        Dict with record details and an executive operational briefing.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        query = db.query(ShiftHandoff)
        if shift_type and shift_type.strip():
            clean_shift = shift_type.strip().lower()
            query = query.filter(ShiftHandoff.shift_type.ilike(f"%{clean_shift}%"))

        latest = query.order_by(desc(ShiftHandoff.created_at)).first()

        if not latest:
            msg = (
                f"No previous shift handoff logs found"
                f"{f' for {shift_type} shift' if shift_type else ''} in the system."
            )
            return {
                "found": False,
                "formatted_message": msg
            }

        # Build executive operational briefing
        created_str = latest.created_at.strftime("%Y-%m-%d %H:%M UTC") if latest.created_at else "Recently"
        briefing = [
            f"📋 **Shift Handoff Briefing: {latest.shift_type.upper()} Shift**",
            f"• **Supervisor:** {latest.supervisor}",
            f"• **Logged:** {created_str}",
            f"• **Operational Summary:** {latest.summary}"
        ]

        if latest.incidents:
            briefing.append(f"• ⚠️ **Reported Incidents:** {latest.incidents}")
        else:
            briefing.append("• ⚠️ **Reported Incidents:** None reported (all clear)")

        if latest.pending_tasks:
            briefing.append(f"• 📌 **Pending Actions for Next Crew:** {latest.pending_tasks}")

        formatted_msg = "\n".join(briefing)

        logger.log_event("SHIFT_HANDOFF_RETRIEVED", {
            "id": latest.id,
            "shift_type": latest.shift_type,
            "supervisor": latest.supervisor
        })

        return {
            "found": True,
            "id": latest.id,
            "shift_type": latest.shift_type,
            "supervisor": latest.supervisor,
            "summary": latest.summary,
            "incidents": latest.incidents,
            "pending_tasks": latest.pending_tasks,
            "created_at": latest.created_at.isoformat() if latest.created_at else None,
            "formatted_message": formatted_msg
        }
    finally:
        if own_session:
            db.close()


def list_recent_shift_handoffs(limit: int = 5, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Retrieves the last N shift handoff entries for operational review."""
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        entries = (
            db.query(ShiftHandoff)
            .order_by(desc(ShiftHandoff.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "shift_type": e.shift_type,
                "supervisor": e.supervisor,
                "summary": e.summary,
                "incidents": e.incidents,
                "pending_tasks": e.pending_tasks,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in entries
        ]
    finally:
        if own_session:
            db.close()
