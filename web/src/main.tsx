import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
type Incident = { id: string; title: string; severity: string; status: string; service: string; customer_impact?: string };

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const token = localStorage.getItem("orbit_access_token");
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const devUser = import.meta.env.VITE_DEV_USER_ID;
    if (!token && devUser) {
      headers["X-User-Id"] = devUser;
      headers["X-User-Role"] = import.meta.env.VITE_DEV_USER_ROLE ?? "observer";
    }
    fetch(`${API}/api/incidents`, { headers }).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(setIncidents).catch((status) => setError(status === 401 ? "Authentication is required to load incident data." : "Incident Engine is offline. Start the API to load live incidents."));
  }, []);
  return <main>
    <header><div><span className="eyebrow">ORBIT COMMAND CENTER</span><h1>Shared truth for every incident.</h1></div><span className="live">● LIVE ENGINE</span></header>
    {error && <p className="notice">{error}</p>}
    <section className="grid">
      <article className="hero"><span className="eyebrow">INCIDENT DIGITAL TWIN</span><h2>{incidents[0]?.title ?? "No active incident"}</h2><p>{incidents[0]?.customer_impact ?? "Create an incident through the API to begin the live response."}</p><div className="meta"><b>{incidents[0]?.severity ?? "—"}</b><span>{incidents[0]?.service ?? "Waiting for service"}</span><span>{incidents[0]?.status ?? "idle"}</span></div></article>
      <article><span className="eyebrow">REAL-TIME TIMELINE</span><h3>Event stream</h3><p>Voice, evidence, task, approval, and monitoring events appear here through incident-scoped WebSockets.</p></article>
      <article><span className="eyebrow">HUMAN CONTROL</span><h3>Approval queue</h3><p>Critical actions remain blocked until an authorized incident leader approves them.</p></article>
    </section>
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
