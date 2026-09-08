
import re
from typing import Tuple

# Common prompt injection and system override triggers
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"system prompt",
    r"you are now (a|an|in)",
    r"bypass (security|rules|guardrails)",
    r"drop table|delete from|update users",
    r"jailbreak|dan mode",
]

def sanitize_input(user_message: str) -> Tuple[bool, str]:
    """
    Scans input for prompt injection patterns.
    Returns:
        (is_safe: bool, sanitized_or_reason: str)
    """
    if not user_message or not user_message.strip():
        return False, "Empty query received."

    lower_msg = user_message.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower_msg):
            return False, f"Security Alert: Suspicious query pattern detected ('{pattern}'). Request blocked."

    # Return safe message (strip whitespace)
    return True, user_message.strip()
