import re
from typing import Tuple

from config.settings import settings


class InputSanitizer:
    """Detects and blocks prompt injection attempts."""

    # (rule name shown to users, pattern). The pattern itself is never shown: it would teach
    # an attacker how to word around the filter.
    INJECTION_RULES = [
        ("ignore_instructions", r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions?"),
        ("system_prompt", r"system\s+prompt"),
        ("dump_database", r"dump\s+(?:the\s+)?database"),
        ("reveal_system_prompt", r"reveal\s+(?:your\s+)?system\s+prompt"),
        ("show_instructions", r"show\s+me\s+your\s+instructions?"),
        ("bypass_security", r"bypass\s+(?:security|rules|guardrails)"),
        ("unauthorized_access", r"unauthorized\s+access"),
        ("admin_mode", r"admin\s+mode"),
        ("forget_everything", r"forget\s+everything"),
        ("override_rules", r"override\s+(?:all\s+)?rules?"),
        ("role_override", r"you\s+are\s+now\s+(?:a|an|in)"),
        # SQL statements, not everyday words ("please update users on the restock" is a normal request)
        ("sql_statement", r"\bdrop\s+table\b|\bdelete\s+from\s+\w+\s*(?:;|\bwhere\b|$)|"
                          r"\bupdate\s+\w+\s+set\s+\w+\s*=|\btruncate\s+table\b|;\s*--"),
        ("jailbreak", r"jailbreak|dan\s+mode"),
    ]
    INJECTION_PATTERNS = [pattern for _, pattern in INJECTION_RULES]

    def __init__(self):
        self.compiled_rules = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in self.INJECTION_RULES]
        self.compiled_patterns = [pattern for _, pattern in self.compiled_rules]

    def matched_rule(self, text: str) -> str:
        """Name of the first injection rule the text matches ('' when none)."""
        for name, pattern in self.compiled_rules:
            if pattern.search(text or ""):
                return name
        return ""

    def is_injection_attempt(self, text: str) -> Tuple[bool, str]:
        """
        Detect if text contains a prompt injection attempt.

        Returns:
            (is_injection: bool, reason: str) — the reason names the rule, never its pattern
        """
        rule = self.matched_rule(text)
        if rule:
            return True, f"the request matched the security filter (rule: {rule})"
        return False, ""
    
    def sanitize_input(self, text: str) -> Tuple[str, bool]:
        """
        Clean and validate user input.
        
        Returns:
            (cleaned_text: str, is_safe: bool)
        """
        if not text or not text.strip():
            return "", False
        
        # Check for injection
        is_injection, reason = self.is_injection_attempt(text)
        if is_injection:
            return "", False
        
        # Clean the text
        cleaned = text.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)  # collapse whitespace
        
        # Same limit as the API (QueryRequest), so accepted text is never cut silently
        max_length = settings.CHAT_MAX_MESSAGE_CHARS
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]

        return cleaned, True

    def log_suspicious_attempt(self, text: str, reason: str, user_id: str = None, role: str = None) -> None:
        """Log suspicious input for audit trail (Responsible AI compliance)."""
        try:
            from security.audit_logger import audit_logger
            audit_logger.log_event(
                event_type="INJECTION_BLOCKED",
                severity="HIGH",
                user_id=user_id,
                role=role,
                details={"reason": reason, "rule": self.matched_rule(text), "snippet": text[:150]}
            )
        except Exception as e:
            print(f"[SECURITY WARNING] Failed to log audit event: {e}")

# Singleton instance
sanitizer = InputSanitizer()

EMPTY_QUERY_MESSAGE = "Type a question before sending."


def is_empty_query(user_message) -> bool:
    return not isinstance(user_message, str) or not user_message.strip()

# Backward-compatible function (used by backend/main.py)
def sanitize_input(user_message: str, user_id: str = None, role: str = None) -> Tuple[bool, str]:
    """
    Wrapper that keeps the same interface backend/main.py expects:
    Returns (is_safe: bool, sanitized_or_reason: str)
    """
    if not user_message or not user_message.strip():
        return False, EMPTY_QUERY_MESSAGE

    is_injection, reason = sanitizer.is_injection_attempt(user_message)
    if is_injection:
        sanitizer.log_suspicious_attempt(user_message, reason, user_id=user_id, role=role)
        return False, f"Security Alert: {reason}. Request blocked."
    
    cleaned, _ = sanitizer.sanitize_input(user_message)
    return True, cleaned
