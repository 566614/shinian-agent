import re
from typing import Any, Optional

from .config import Settings
from .llm import extract_with_llm
from .store import Store

TYPES = {"灵感", "待办", "决策", "引用", "素材", "人脉", "其他"}

TODO_MARKERS = (
    "待办", "要", "得", "记得", "需要", "明天", "后天", "下周", "之后",
    "安排", "联系", "发给", "确认", "提醒", "约", "跟进",
)
DECISION_MARKERS = ("决定", "定了", "确定用", "就选", "选它", "不改了")
QUOTE_MARKERS = ("原话", "说过", "他说", "她说", "“", "”")


def _tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9#]+", " ", text)
    out: set[str] = set()
    for part in cleaned.split():
        if not part:
            continue
        if re.search(r"[\u4e00-\u9fa5]", part):
            out.add(part)
            out.update(part[i : i + 2] for i in range(max(0, len(part) - 1)))
        else:
            out.add(part.lower())
    return out


class NoteAgent:
    """把一句话变成一张可检索、可执行的想法卡片。"""

    def __init__(self, settings: Settings, store: Store) -> None:
        self.settings = settings
        self.store = store

    def process(
        self,
        text: str,
        scene: Optional[str] = None,
        location: Optional[str] = None,
        source: str = "glasses",
        audio_path: Optional[str] = None,
    ) -> dict[str, Any]:
        text = text.strip()
        data = self._extract(text)
        data = self._normalize(data, text)
        data.update(
            {
                "raw_text": text,
                "scene": scene,
                "location": location,
                "source": source,
                "related_ids": self._related(text),
                "audio_path": audio_path,
            }
        )
        return self.store.create(data)

    def _extract(self, text: str) -> dict[str, Any]:
        if self.settings.llm_enabled:
            try:
                return extract_with_llm(text, self.settings)
            except Exception:
                pass
        return self._heuristic(text)

    def _heuristic(self, text: str) -> dict[str, Any]:
        type_ = "灵感"
        if any(k in text for k in DECISION_MARKERS):
            type_ = "决策"
        elif any(k in text for k in QUOTE_MARKERS):
            type_ = "引用"
        elif any(k in text for k in TODO_MARKERS):
            type_ = "待办"

        tags = re.findall(r"#([\w\u4e00-\u9fa5]+)", text)
        project_match = re.search(r"关于([\u4e00-\u9fa5A-Za-z0-9]{2,12})", text)
        people = re.findall(r"@([\u4e00-\u9fa5A-Za-z0-9_]{2,10})", text)

        actions: list[str] = []
        if type_ == "待办":
            for segment in re.split(r"[。；;\n]", text):
                segment = segment.strip()
                if segment and any(k in segment for k in TODO_MARKERS):
                    actions.append(segment[:60])

        return {
            "title": self._title(text),
            "summary": text[:50] + ("…" if len(text) > 50 else ""),
            "type": type_,
            "tags": tags,
            "action_items": actions[:3],
            "people": people,
            "project": project_match.group(1) if project_match else None,
        }

    @staticmethod
    def _title(text: str) -> str:
        title = re.sub(r"^[\s，。,.!?！？、；;：:#]+", "", text)
        title = re.sub(r"\s+", " ", title).strip(" ，。,.!?！？、；;：:")
        return title[:12] + ("…" if len(title) > 12 else "")

    def _normalize(self, data: dict[str, Any], text: str) -> dict[str, Any]:
        title = str(data.get("title") or "").strip() or self._title(text)
        summary = str(data.get("summary") or "").strip() or text[:50]
        type_ = str(data.get("type") or "").strip()
        if type_ not in TYPES:
            type_ = self._heuristic(text)["type"]

        def str_list(value: Any, limit: int) -> list[str]:
            if not isinstance(value, list):
                return []
            result: list[str] = []
            for item in value:
                item = str(item).strip().lstrip("#")
                if item and item not in result:
                    result.append(item)
            return result[:limit]

        project = data.get("project")
        project = str(project).strip() if project else None

        return {
            "title": title[:20],
            "summary": summary[:80],
            "type": type_,
            "tags": str_list(data.get("tags"), 5),
            "action_items": str_list(data.get("action_items"), 5),
            "people": str_list(data.get("people"), 5),
            "project": project,
        }

    def _related(self, text: str, limit: int = 3) -> list[int]:
        current = _tokens(text)
        if not current:
            return []
        scored: list[tuple[float, int]] = []
        for note in self.store.recent(200):
            other = _tokens(note["raw_text"])
            if not other:
                continue
            overlap = len(current & other)
            if overlap < 2:
                continue
            score = overlap / len(current | other)
            if score >= 0.18:
                scored.append((score, note["id"]))
        scored.sort(reverse=True)
        return [note_id for _, note_id in scored[:limit]]
