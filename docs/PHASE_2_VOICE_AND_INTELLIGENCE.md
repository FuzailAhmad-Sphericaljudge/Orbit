# Phase 2: Voice AI and Agentic Intelligence

## Runtime boundary

The browser participant and ORBIT agent join the same Agora RTC channel. The API owns the server-side agent lifecycle and never exposes the App Certificate. Agora transports voice and the configured ASR -> LLM -> TTS pipeline; final transcript turns are ingested into the Incident Engine.

## Implemented workflow

1. Register incident participants with Agora UID, display name, operational role, and language.
2. Start an ORBIT cloud-agent session for an incident channel.
3. Ingest final transcript turns with speaker identity and role.
4. Classify each turn as a confirmed fact, hypothesis, decision, or action.
5. Create evidence with provenance and confidence.
6. Detect missing customer-impact information and likely contradictory claims.
7. Extract directly assigned actions and their owners.
8. Generate a guarded status briefing and optionally speak it into the active channel.
9. Publish transcript, evidence, finding, action, briefing, and timeline events through the incident WebSocket.

## Production safeguards

- Agora credentials remain server-side.
- Voice startup fails closed when credentials are absent.
- Critical operational actions still use the separate approval workflow.
- ORBIT's prompt and generated briefings prohibit unsupported root-cause claims.
- The rule-based classifier is a deterministic fallback. A structured-output LLM classifier will replace it behind the same domain interface in the next intelligence iteration.

## Credential setup

Set `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` in `api/.env`. Configure `AGORA_AREA`, `AGORA_AGENT_UID`, and `ORBIT_DEFAULT_LANGUAGE` as needed. The server uses the official `agora-agents` Python SDK and starts an agent with a chained STT -> LLM -> TTS configuration.
