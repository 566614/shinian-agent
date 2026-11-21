from app.export import to_obsidian_markdown, to_share_card_html
from app.store import Store


def test_to_obsidian_markdown():
    note = {
        "id": 1,
        "created_at": "2026-11-21T10:00:00",
        "title": "包装方案讨论",
        "summary": "明天发给阿哲",
        "type": "待办",
        "tags": ["选品", "待办"],
        "action_items": ["把包装方案发给阿哲"],
        "people": ["阿哲"],
        "project": "拾念",
        "raw_text": "明天把包装方案发给阿哲 #选品",
        "related_ids": [2],
    }
    all_notes = {2: "上周包装讨论"}
    md = to_obsidian_markdown(note, all_notes)
    
    assert "title: \"包装方案讨论\"" in md
    assert "type: 待办" in md
    assert "- [ ] 把包装方案发给阿哲" in md
    assert "[[上周包装讨论]]" in md
    assert "[[拾念]]" in md


def test_to_share_card_html():
    note = {
        "id": 1,
        "created_at": "2026-11-21T10:00:00",
        "title": "灵感火花",
        "summary": "眼镜端的短语音即时结构化卡片",
        "type": "灵感",
        "tags": ["AR眼镜", "AIUI"],
        "action_items": [],
        "raw_text": "做个戴在眼镜上的灵感记录智能体",
    }
    html = to_share_card_html(note)
    assert "<title>灵感火花 - 拾念卡片</title>" in html
    assert "#AR眼镜" in html
    assert "Rokid Glasses" in html


def test_export_obsidian_endpoint(tmp_path):
    from app.main import create_app
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    app = create_app(db_path)
    client = TestClient(app)

    # 插入数据
    client.post("/api/notes", json={"text": "测试Obsidian导出 #测试"})
    
    res = client.get("/api/export/obsidian")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert len(res.content) > 0
