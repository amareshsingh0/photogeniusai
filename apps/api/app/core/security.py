from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
import httpx
from .config import get_settings

# Get settings instance
settings = get_settings()

security = HTTPBearer()

# Cache for JWKS (refresh every 5 minutes)
_jwks_cache: Optional[dict] = None
_jwks_cache_time: Optional[float] = None


async def get_clerk_jwks() -> dict:
    """Get Clerk JWKS with caching"""
    global _jwks_cache, _jwks_cache_time
    import time
    
    # Return cached if still valid (5 minutes)
    if _jwks_cache and _jwks_cache_time and time.time() - _jwks_cache_time < 300:
        return _jwks_cache
    
    try:
        async with httpx.AsyncClient() as client:
            jwks_url = "https://api.clerk.com/v1/jwks"
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
            
            _jwks_cache = jwks
            _jwks_cache_time = time.time()
            return jwks
    except Exception as e:
        # Use cached if available
        if _jwks_cache:
            return _jwks_cache
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Clerk JWKS: {str(e)}"
        )


def get_rsa_key(jwks: dict, kid: str) -> Optional[dict]:
    """Find RSA key by kid"""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return {
                "kty": key.get("kty"),
                "kid": key.get("kid"),
                "use": key.get("use"),
                "n": key.get("n"),
                "e": key.get("e")
            }
    return None


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Clerk JWT token
    
    Returns user data from token
    """
    token = credentials.credentials
    
    try:
        # Get Clerk JWKS
        jwks = await get_clerk_jwks()
        
        # Get unverified header to find key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing key ID"
            )
        
        # Find matching key
        rsa_key_dict = get_rsa_key(jwks, kid)
        
        if not rsa_key_dict:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )
        
        # Convert JWK to RSA public key for jose
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import base64
        
        def base64url_decode(data: str) -> bytes:
            padding = 4 - len(data) % 4
            if padding != 4:
                data += "=" * padding
            data = data.replace("-", "+").replace("_", "/")
            return base64.b64decode(data)
        
        n_bytes = base64url_decode(rsa_key_dict["n"])
        e_bytes = base64url_decode(rsa_key_dict["e"])
        n_int = int.from_bytes(n_bytes, "big")
        e_int = int.from_bytes(e_bytes, "big")
        
        public_key = rsa.RSAPublicNumbers(e_int, n_int).public_key(default_backend())
        pem_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Decode and verify
        payload = jwt.decode(
            token,
            pem_key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
            }
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


async def get_current_user(
    token_data: dict = Depends(verify_clerk_token)
) -> str:
    """
    Get current user ID from token
    
    Returns Clerk user ID
    """
    user_id = token_data.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return user_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[str]:
    """
    Get current user ID if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token_data = await verify_clerk_token(credentials)
        return token_data.get("sub")
    except:
        return None


# Alias for compatibility with dependencies.py
get_current_user_id = get_optional_user


def require_auth(user_id: Optional[str]) -> str:
    """
    Require authentication - raises HTTPException if user_id is None
    
    Usage:
        require_auth(user_id)  # Raises 401 if not authenticated
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user_id


# Dependency for routes that require auth
RequireAuth = Depends(get_current_user)
