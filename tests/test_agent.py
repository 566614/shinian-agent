from datetime import datetime
from zoneinfo import ZoneInfo
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


def test_time_resolution(tmp_path):
    agent, store = build(tmp_path)
    
    # 注入一个固定的当前时间，用以测试相对时间解析
    # 2026-11-21T10:00:00 是周六
    base_time_str = "2026-11-21T10:00:00+08:00"
    
    # 测试“明天”
    note = agent.process("明天下午3点半把包装方案发给阿哲", created_at=base_time_str)
    action_item = note["action_items"][0]
    # 2026-11-21 的明天是 2026-11-22，下午3点半是 15:30:00
    assert "2026-11-22T15:30:00" in action_item

    # 测试“下周一”
    # 周六的下周一是 11-23
    note2 = agent.process("下周一早上9点开会讨论 React 设计模式", created_at=base_time_str)
    action_item2 = note2["action_items"][0]
    assert "2026-11-23T09:00:00" in action_item2

    # 测试“3小时后”
    # 10:00:00 过了 3 小时是 13:00:00
    note3 = agent.process("记得3小时后跟进包装设计的进展", created_at=base_time_str)
    action_item3 = note3["action_items"][0]
    assert "2026-11-21T13:00:00" in action_item3


def test_chinese_english_mixed_extraction(tmp_path):
    agent, _ = build(tmp_path)
    note = agent.process("用 React 做个 Network OS #开发")
    assert note["type"] == "待办"
    assert "开发" in note["tags"]
    assert "React" in note["tags"]
    # 智能中英混合截断：标题应该优雅，不被硬生生切成两半
    assert note["title"] == "用 React 做个…"
