from typing import List

# Define what each role can do
PERMISSION_MATRIX = {
    "staff": [
        "query_location",           # "Where is SKU-4521?"
        "track_order",              # "What's the status of order #4521?"
        "report_damage",            # "This item arrived broken"
        "view_sop",                 # Read safety procedures
        "view_shift_notes",         # Read what the previous shift left
    ],
    "manager": [
        # All staff permissions plus:
        "query_location",
        "track_order",
        "report_damage",
        "view_sop",
        "view_shift_notes",
        "approve_restock",          # "OK, order 200 more units of SKU-4521"
        "view_analytics",           # See warehouse statistics
        "view_vendor_performance",  # Check supplier data
    ],
    "admin": [
        # All permissions (for testing/admin only)
        "query_location",
        "track_order",
        "report_damage",
        "view_sop",
        "view_shift_notes",
        "approve_restock",
        "view_analytics",
        "view_vendor_performance",
        "delete_records",           # Remove old data
        "change_settings",          # Admin-only actions
    ]
}

class RBACManager:
    """Role-Based Access Control — checks if a user can do something."""
    
    def __init__(self):
        self.permissions = PERMISSION_MATRIX
    
    def get_permissions(self, role: str) -> List[str]:
        """Get all permissions for a role."""
        return self.permissions.get(role, [])
    
    def check_permission(self, role: str, action: str) -> bool:
        """Check if a role is allowed to perform an action."""
        allowed_actions = self.permissions.get(role, [])
        return action in allowed_actions
    
    def require_permission(self, role: str, action: str, user_id: str = None) -> None:
        """
        Check permission and raise PermissionError if denied.
        Used by the /query endpoint to enforce access control.
        """
        if not self.check_permission(role, action):
            try:
                from security.audit_logger import audit_logger
                audit_logger.log_event(
                    event_type="PERMISSION_DENIED",
                    severity="WARNING",
                    user_id=user_id,
                    role=role,
                    details={"attempted_action": action, "allowed_actions": self.get_permissions(role)}
                )
            except Exception:
                pass
            raise PermissionError(
                f"Role '{role}' is not allowed to '{action}'. "
                f"Allowed actions: {self.get_permissions(role)}"
            )

# Singleton instance
rbac_manager = RBACManager()
