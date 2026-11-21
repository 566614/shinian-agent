import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "api.db")))


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True


def test_create_list_and_search(client):
    created = client.post("/api/notes", json={"text": "下周约小林聊联名款 #联名"}).json()
    assert created["id"] > 0
    assert created["type"] == "待办"

    listed = client.get("/api/notes").json()
    assert listed["total"] == 1

    found = client.get("/api/notes", params={"q": "联名"}).json()
    assert found["total"] == 1

    missing = client.get("/api/notes", params={"q": "不存在的关键词"}).json()
    assert missing["total"] == 0


def test_patch_and_delete(client):
    note = client.post("/api/notes", json={"text": "想到一个包装上的小点子"}).json()
    patched = client.patch(f"/api/notes/{note['id']}", json={"status": "done"}).json()
    assert patched["status"] == "done"

    assert client.delete(f"/api/notes/{note['id']}").json()["ok"] is True
    assert client.get(f"/api/notes/{note['id']}").status_code == 404


def test_reviews(client):
    client.post("/api/notes", json={"text": "今天想到用旧木纹做包装 #选品"})
    daily_res = client.get("/api/review/daily").json()
    weekly_res = client.get("/api/review/weekly").json()
    assert daily_res["total"] >= 1
    assert "今日回顾" in daily_res["markdown"]
    assert "本周想法周报" in weekly_res["markdown"]
    
    # 验证聚类功能在 weekly review 中返回
    assert "clusters" in weekly_res
    assert "关于 #选品 的思考" in weekly_res["clusters"]


def test_share_poster_endpoint(client):
    note = client.post("/api/notes", json={"text": "定稿海报生成功能测试 #测试"}).json()
    res = client.get(f"/api/export/poster/{note['id']}")
    assert res.status_code == 200
    assert "<title>" in res.text
    assert "拾念海报" in res.text
    assert "测试" in res.text
