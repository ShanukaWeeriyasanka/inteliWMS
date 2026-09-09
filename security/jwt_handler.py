from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import jwt
from config.settings import settings

class JWTHandler:
    """Handles JWT token creation and verification."""
    
    def __init__(self):
        self.secret = settings.JWT_SECRET
        self.algorithm = "HS256"
        self.expiration_hours = 24  # Token valid for 24 hours
    
    def create_token(self, user_id: str, role: str) -> str:
        """
        Create a JWT token for a logged-in user.
        
        Args:
            user_id: unique user identifier (e.g., "user_123")
            role: user's role (e.g., "staff", "manager", "admin")
        
        Returns:
            JWT token string (e.g., "eyJhbGc...")
        """
        expiration = datetime.now(timezone.utc) + timedelta(hours=self.expiration_hours)
        
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": expiration,
            "iat": datetime.now(timezone.utc),
        }
        
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token
    
    def decode_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode a JWT token.
        
        Returns:
            Decoded payload dict if valid
        
        Raises:
            ValueError if token is expired or invalid
        """
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired. Please log in again.")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token. Please log in again.")
    
    def verify_expiration(self, payload: Dict) -> bool:
        """
        Extra safety check — is the token still valid?
        
        Returns:
            True if token is still valid, False if expired
        """
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            return False
        
        expiration_time = datetime.fromtimestamp(exp_timestamp)
        return datetime.now(timezone.utc) < expiration_time.replace(tzinfo=timezone.utc)

# Singleton instance
jwt_handler = JWTHandler()
