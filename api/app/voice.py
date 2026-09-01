from dataclasses import dataclass
from .config import Settings, get_settings


ORBIT_VOICE_PROMPT = """You are ORBIT, the voice participant in a technical incident room.
Speak briefly and only when asked, when a material conflict appears, when an action is overdue, or when a status briefing is requested.
Clearly separate confirmed facts from hypotheses. Never declare a root cause unless an authorized human has confirmed it.
Ask for human approval before any critical operational action. Preserve uncertainty and unresolved risks."""


@dataclass(frozen=True)
class StartedVoiceAgent:
    session_id: str


class AgoraVoiceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sessions: dict[str, object] = {}

    def configured(self) -> bool:
        return bool(self.settings.agora_app_id and self.settings.agora_app_certificate)

    async def start(self, local_session_id: str, channel: str, remote_uids: list[str], language: str) -> StartedVoiceAgent:
        if not self.configured():
            raise RuntimeError("Agora credentials are not configured")
        from agora_agent import Agent, Agora, Area, DeepgramSTT, MiniMaxTTS, OpenAI

        area = getattr(Area, self.settings.agora_area.upper(), Area.US)
        client = Agora(area=area, app_id=self.settings.agora_app_id, app_certificate=self.settings.agora_app_certificate)
        agent = (
            Agent(client=client, turn_detection={"language": language})
            .with_stt(DeepgramSTT(model="nova-3", language=language.split("-")[0]))
            .with_llm(OpenAI(model="gpt-4o-mini", system_messages=[{"role": "system", "content": ORBIT_VOICE_PROMPT}], greeting_message="ORBIT has joined the incident room.", max_history=30))
            .with_tts(MiniMaxTTS(model="speech_2_6_turbo", voice_id="English_captivating_female1"))
        )
        session = agent.create_session(channel=channel, agent_uid=self.settings.agora_agent_uid, remote_uids=remote_uids, name=f"orbit-{local_session_id}", idle_timeout=1800)
        agora_session_id = session.start()
        self._sessions[local_session_id] = session
        return StartedVoiceAgent(session_id=agora_session_id)

    async def say(self, local_session_id: str, message: str) -> None:
        session = self._sessions.get(local_session_id)
        if session is None:
            raise RuntimeError("Voice session is not active on this server instance")
        session.say(message)

    async def stop(self, local_session_id: str) -> None:
        session = self._sessions.pop(local_session_id, None)
        if session is not None:
            session.stop()


voice_service = AgoraVoiceService(get_settings())
