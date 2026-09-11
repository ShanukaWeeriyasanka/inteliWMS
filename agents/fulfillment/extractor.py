import re
from typing import Optional

def extract_order_id(text: str) -> Optional[str]:
    """
    Extracts an order ID from the given text.
    Format: ORD- followed by numbers (e.g. ORD-1001).
    Case insensitive. Returns normalized uppercase string.
    """
    if not text:
        return None
        
    match = re.search(r'\bord-\d+\b', text, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None
