import os
from pathlib import Path


def _load_dotenv() -> None:
    """读取项目根目录的 .env；真实环境变量优先，不会被覆盖。"""
    path = Path(os.getenv("SHINIAN_ENV_FILE", "")).expanduser() if os.getenv("SHINIAN_ENV_FILE") else Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


class Settings:
    """运行时配置，全部来自环境变量，未配置时自动降级为本地规则模式。"""

    def __init__(self) -> None:
        self.db_path = os.getenv("SHINIAN_DB", "data/shinian.db").strip() or "data/shinian.db"
        self.timezone = os.getenv("SHINIAN_TZ", "Asia/Shanghai").strip() or "Asia/Shanghai"
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        self.llm_model = os.getenv("SHINIAN_LLM_MODEL", "gpt-4o-mini").strip()
        self.asr_model = os.getenv("SHINIAN_ASR_MODEL", "whisper-1").strip()
        self.audio_dir = os.getenv("SHINIAN_AUDIO_DIR", "data/audio").strip() or "data/audio"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def asr_enabled(self) -> bool:
        return bool(self.api_key)
