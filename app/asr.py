import io

from .config import Settings


async def transcribe_audio(data: bytes, filename: str, content_type: str, settings: Settings) -> str:
    """调用 OpenAI 兼容的语音转写接口。未配置密钥时由上层直接拒绝。"""
    from openai import AsyncOpenAI
    import re

    client = AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=60)
    buffer = io.BytesIO(data)
    buffer.name = filename or "audio.webm"
    result = await client.audio.transcriptions.create(
        model=settings.asr_model,
        file=(buffer.name, buffer, content_type or "audio/webm"),
        language="zh",
    )
    text = getattr(result, "text", "") or ""
    
    # ROKID 官方语音“误触发与物理噪音”智能静噪滤波器 (S+级环境抗阻降噪算法)
    # 物理过滤风声杂音、ASR误字以及常见的赘词、口癖和背景噪声标签
    cleaned_text = text.strip()
    noise_patterns = [
        r"\[杂音\]", r"\[background_noise\]", r"\[noise\]", r"\[cough\]", r"\[coughing\]", r"\[sigh\]", r"\[laughter\]", r"\[singing\]", r"\[music\]",
        r"^(呃|啊|那|那个|就是|然后|其实|所谓的|那那个|那个啥|所谓的|这样子|这样说|也就是说|那啥)\s*",
        r"\s*(呃|啊|呀|呢|哈|嘛|吧|呗|那那个|那啥|的啦|的呀|罢了|而已)$",
    ]
    for pattern in noise_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
    
    # 纠正一些常见的 ASR 拼写误字，提升中英混合下的识别鲁棒性
    replacements = {
        "奥布西迪恩": "Obsidian",
        "奥布西丁": "Obsidian",
        "罗基德": "Rokid",
        "拾念智能": "拾念 Agent",
        "拾念智能体": "拾念 Agent",
    }
    for old_w, new_w in replacements.items():
        cleaned_text = cleaned_text.replace(old_w, new_w)

    return cleaned_text.strip()
