const issuer = import.meta.env.VITE_OIDC_ISSUER?.replace(/\/$/, "");
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;
const tokenKey = "orbit_access_token";
const verifierKey = "orbit_oidc_verifier";
const stateKey = "orbit_oidc_state";

export const oidcEnabled = Boolean(issuer && clientId);
export const hasAccessToken = () => Boolean(localStorage.getItem(tokenKey));

function encode(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function challenge(verifier: string) {
  return encode(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
}

export async function startLogin() {
  if (!issuer || !clientId) return;
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
  const state = encode(crypto.getRandomValues(new Uint8Array(20)));
  sessionStorage.setItem(verifierKey, verifier);
  sessionStorage.setItem(stateKey, state);
  const params = new URLSearchParams({ client_id: clientId, redirect_uri: window.location.origin, response_type: "code", scope: "openid", state, code_challenge: await challenge(verifier), code_challenge_method: "S256" });
  window.location.assign(`${issuer}/protocol/openid-connect/auth?${params}`);
}

export async function completeLogin() {
  if (!issuer || !clientId) return false;
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (!code) return false;
  const verifier = sessionStorage.getItem(verifierKey);
  if (!verifier || params.get("state") !== sessionStorage.getItem(stateKey)) throw new Error("Invalid sign-in response");
  const response = await fetch(`${issuer}/protocol/openid-connect/token`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ grant_type: "authorization_code", client_id: clientId, code, redirect_uri: window.location.origin, code_verifier: verifier }) });
  if (!response.ok) throw new Error("Token exchange failed");
  const tokens = await response.json() as { access_token: string };
  localStorage.setItem(tokenKey, tokens.access_token);
  sessionStorage.removeItem(verifierKey);
  sessionStorage.removeItem(stateKey);
  window.history.replaceState({}, document.title, window.location.pathname);
  return true;
}

export function logout() {
  localStorage.removeItem(tokenKey);
  window.location.reload();
}
