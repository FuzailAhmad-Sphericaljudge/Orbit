from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient

from .config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    roles: frozenset[str]


bearer = HTTPBearer(auto_error=False)
settings = get_settings()
jwks_client = PyJWKClient(settings.oidc_jwks_url, cache_keys=True) if settings.oidc_jwks_url else None


def decode_access_token(token: str) -> CurrentUser:
    try:
        if jwks_client:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"], issuer=settings.oidc_issuer, audience=settings.oidc_audience)
        else:
            claims = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"], issuer=settings.auth_jwt_issuer, audience=settings.auth_jwt_audience)
    except InvalidTokenError as exc:
        raise HTTPException(401, "Invalid access token") from exc
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(401, "Access token has no subject")
    raw_roles = claims.get(settings.oidc_roles_claim, [])
    roles = {raw_roles} if isinstance(raw_roles, str) else set(raw_roles)
    return CurrentUser(user_id=str(subject), roles=frozenset(str(role) for role in roles))


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_user_id: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
) -> CurrentUser:
    if credentials:
        return decode_access_token(credentials.credentials)

    if settings.environment == "development" and x_user_id:
        roles = {role.strip() for role in (x_user_role or "observer").split(",") if role.strip()}
        return CurrentUser(user_id=x_user_id, roles=frozenset(roles))

    raise HTTPException(401, "Authentication required")


def require_roles(*allowed: str):
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not user.roles.intersection(allowed):
            raise HTTPException(403, f"Requires one of these roles: {', '.join(allowed)}")
        return user

    return dependency
