"""
Security utilities.

Currently a placeholder — extend with API-key auth or OAuth2 as needed.
Example usage with FastAPI:

    from fastapi.security import APIKeyHeader
    from fastapi import Security, HTTPException, status

    API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

    async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
        if api_key != settings.API_KEY:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
"""
