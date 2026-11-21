from app.agent import NoteAgent
from app.config import Settings
from app.store import Store


def build(tmp_path):
    settings = Settings()
    settings.api_key = ""  # 强制使用本地规则，保证离线可测
    store = Store(str(tmp_path / "notes.db"))
    return NoteAgent(settings, store), store


def test_todo_is_structured(tmp_path):
    agent, _ = build(tmp_path)
    note = agent.process("明天把包装方案发给阿哲 #选品")
    assert note["type"] == "待办"
    assert "选品" in note["tags"]
    assert note["action_items"]
    assert note["title"]


def test_decision_is_detected(tmp_path):
    agent, _ = build(tmp_path)
    note = agent.process("定了，就用木纹那版包装，不改了")
    assert note["type"] == "决策"


def test_related_notes_are_linked(tmp_path):
    agent, _ = build(tmp_path)
    first = agent.process("做一个记录灵感的眼镜应用，重点是实时转写")
    second = agent.process("记录灵感的眼镜应用，实时转写要做得更轻")
    assert first["id"] in second["related_ids"]
