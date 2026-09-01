import httpx

from .config import get_settings
from .investigation import analyze_artifact_text
from .models import EvidenceArtifact


class MultimodalAnalyzer:
    def __init__(self):
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.vision_analysis_url)

    async def analyze(self, artifact: EvidenceArtifact) -> dict:
        if not self.configured or not artifact.storage_uri:
            return analyze_artifact_text(artifact.artifact_type.value, artifact.extracted_text)
        headers = {"Authorization": f"Bearer {self.settings.vision_analysis_token}"} if self.settings.vision_analysis_token else {}
        try:
            async with httpx.AsyncClient(timeout=self.settings.integration_timeout_seconds) as client:
                response = await client.post(self.settings.vision_analysis_url, headers=headers, json={
                    "artifact_type": artifact.artifact_type.value,
                    "title": artifact.title,
                    "mime_type": artifact.mime_type,
                    "storage_uri": artifact.storage_uri,
                    "sha256": artifact.content_sha256,
                })
                response.raise_for_status()
                raw = response.json()
        except (httpx.HTTPError, ValueError):
            fallback = analyze_artifact_text(artifact.artifact_type.value, artifact.extracted_text)
            fallback["status"] = "partial"
            fallback["limitations"].append("Configured multimodal processor was unavailable; local text analysis was used")
            return fallback
        observations = raw.get("observations", [])
        if not isinstance(observations, list):
            observations = []
        limitations = raw.get("limitations", [])
        if not isinstance(limitations, list):
            limitations = [limitations] if limitations else []
        return {
            "status": "analyzed",
            "artifact_type": artifact.artifact_type.value,
            "summary": str(raw.get("summary", ""))[:4000],
            "observations": observations[:100],
            "limitations": [str(item)[:500] for item in limitations[:20]] + ["Human review of the original artifact is required"],
            "processor": "configured_multimodal_service",
        }


multimodal_analyzer = MultimodalAnalyzer()
