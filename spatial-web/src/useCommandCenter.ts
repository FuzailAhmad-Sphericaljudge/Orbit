import { useCallback, useEffect, useRef, useState } from "react";
import { incidentSocketUrl, orbitApi } from "./api";
import type { CommandCenterSnapshot, Incident } from "./types";

export function useCommandCenter() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<CommandCenterSnapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refreshTimer = useRef<number | null>(null);

  const refresh = useCallback(async (targetId?: string | null) => {
    const id = targetId ?? incidentId;
    if (!id) return;
    try {
      setSnapshot(await orbitApi.commandCenter(id));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load the command center.");
    }
  }, [incidentId]);

  useEffect(() => {
    orbitApi.listIncidents()
      .then((rows) => {
        setIncidents(rows);
        const first = rows[0]?.id ?? null;
        setIncidentId(first);
        return refresh(first);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load incidents."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!incidentId) return;
    setLoading(true);
    refresh(incidentId).finally(() => setLoading(false));
    const poll = window.setInterval(() => refresh(incidentId), 15_000);
    const socketUrl = incidentSocketUrl(incidentId);
    const socket = socketUrl ? new WebSocket(socketUrl) : null;
    if (socket) {
      socket.onmessage = () => {
        if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
        refreshTimer.current = window.setTimeout(() => refresh(incidentId), 250);
      };
    }
    return () => {
      window.clearInterval(poll);
      if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
      socket?.close();
    };
  }, [incidentId, refresh]);

  return { incidents, incidentId, setIncidentId, snapshot, loading, error, refresh: () => refresh(incidentId) };
}
