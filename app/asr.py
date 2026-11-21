import io

from .config import Settings


def transcribe_audio(data: bytes, filename: str, content_type: str, settings: Settings) -> str:
    """调用 OpenAI 兼容的语音转写接口。未配置密钥时由上层直接拒绝。"""
    from openai import OpenAI

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=60)
    buffer = io.BytesIO(data)
    buffer.name = filename or "audio.webm"
    result = client.audio.transcriptions.create(
        model=settings.asr_model,
        file=(buffer.name, buffer, content_type or "audio/webm"),
        language="zh",
    )
    text = getattr(result, "text", "") or ""
    return text.strip()
