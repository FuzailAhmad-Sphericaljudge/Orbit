# ORBIT public-release security checklist

Run this only when moving from local development to a public domain. Do not paste credentials, tokens, backup files, or `.env` contents into chat or Git.

## 1. Harden Keycloak administration

1. In Keycloak, stay in the `master` realm and create a new enabled administrator user.
2. Set a non-temporary, unique password.
3. In that user's **Role mapping**, assign the `realm-management` client role `realm-admin`.
4. Sign out, sign back in with the new administrator, and confirm that the `master` realm administration console opens.
5. Delete the temporary bootstrap user (`orbit-admin`).
6. Remove the bootstrap password from the terminal session and do not use `start-dev` for a public Keycloak deployment.

## 2. Rotate release secrets

Create new values in the real deployment secret manager for:

- Keycloak administrator password.
- `AUTH_JWT_SECRET` (at least 32 random characters).
- `DATA_ENCRYPTION_KEY` (new Fernet key).
- Database and Redis passwords.
- Agora, Slack, Jira, PagerDuty, Grafana, and monitoring tokens.

Update every external integration after rotation, test it, then revoke the old token. Never rotate `DATA_ENCRYPTION_KEY` without a deliberate data-re-encryption plan.

## 3. Bind public origins

Replace localhost and temporary-tunnel values with the final HTTPS hostnames in the production environment:

- `OIDC_ISSUER`
- `OIDC_JWKS_URL`
- `OIDC_AUDIENCE`
- `CORS_ORIGINS`
- `TRUSTED_HOSTS`

## 4. Gate the release

Run the check without printing any secret values:

```powershell
.\scripts\security-preflight.ps1 -ForPublicDeployment -KeycloakAdminHardened
```

Only deploy when it reports `PUBLIC SECURITY PREFLIGHT PASSED`.
