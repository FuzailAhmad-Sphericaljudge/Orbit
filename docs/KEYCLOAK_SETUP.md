# Free local OIDC login with Keycloak

ORBIT uses Keycloak as a local, open-source OIDC provider. The browser uses Authorization Code with PKCE and never receives a client secret.

1. In PowerShell, choose an administrator password only for this local Keycloak instance:

```powershell
$env:KEYCLOAK_ADMIN_PASSWORD = "choose-a-long-local-password"
docker compose -f docker-compose.yml -f docker-compose.keycloak.yml up -d keycloak
```

2. Open `http://localhost:8081`, sign in as `orbit-admin`, select the `orbit` realm, create a user, set a non-temporary password, and assign one realm role: `commander`, `operator`, or `observer`.

3. Add these values to the local `api/.env`, then rebuild the API and worker:

```text
OIDC_JWKS_URL=http://keycloak:8080/realms/orbit/protocol/openid-connect/certs
OIDC_ISSUER=http://localhost:8081/realms/orbit
OIDC_AUDIENCE=orbit-spatial
OIDC_ROLES_CLAIM=realm_access.roles
```

```powershell
docker compose -f docker-compose.yml -f docker-compose.keycloak.yml up -d --build --force-recreate api worker
```

4. Copy `spatial-web/.env.local.example` to `spatial-web/.env.local`, restart the Vite server, and select **SIGN IN** in ORBIT.

For a public deployment, replace every localhost URL with the HTTPS hostname of the deployed ORBIT and Keycloak services. Keep Keycloak administrator credentials out of Git and rotate them before public use.
