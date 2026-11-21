from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from .store import Store


def _day_start(store: Store) -> str:
    now = datetime.now(store.tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")


def _week_start(store: Store) -> str:
    now = datetime.now(store.tz)
    start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(timespec="seconds")


def daily(store: Store) -> dict[str, Any]:
    notes = store.list(since=_day_start(store), limit=200)
    counts = Counter(note["type"] for note in notes)
    open_todos = [n for n in notes if n["type"] == "待办" and n["status"] != "done"]
    focus = [n for n in notes if n["type"] in ("待办", "决策", "灵感")][:3]

    lines = ["🌿 拾念 · 今日回顾", f"共记录 {len(notes)} 条"]
    if counts:
        lines.append("类型：" + "、".join(f"{k} {v}" for k, v in counts.most_common()))
    if focus:
        lines.append("")
        lines.append("今日重点")
        for index, note in enumerate(focus, 1):
            lines.append(f"{index}. {note['title']}")
    if open_todos:
        lines.append("")
        lines.append("待办")
        for note in open_todos:
            lines.append(f"- [ ] {note['title']}")

    return {
        "date": datetime.now(store.tz).date().isoformat(),
        "total": len(notes),
        "counts": dict(counts),
        "notes": notes,
        "open_todos": open_todos,
        "markdown": "\n".join(lines),
    }


def weekly(store: Store) -> dict[str, Any]:
    notes = store.list(since=_week_start(store), limit=500)
    tags = Counter(tag for note in notes for tag in note["tags"])
    open_todos = [n for n in notes if n["type"] == "待办" and n["status"] != "done"]
    ideas = [n for n in notes if n["type"] == "灵感"][:3]

    lines = ["📮 拾念 · 本周想法周报", f"共记录 {len(notes)} 条想法"]
    if tags:
        lines.append("")
        lines.append("本周高频主题")
        for tag, count in tags.most_common(5):
            lines.append(f"- {tag}（{count} 条）")
    if ideas:
        lines.append("")
        lines.append("值得回看的灵感")
        for index, note in enumerate(ideas, 1):
            lines.append(f"{index}. {note['title']}——{note['summary']}")
    if open_todos:
        lines.append("")
        lines.append("还没做的待办")
        for note in open_todos:
            lines.append(f"- [ ] {note['title']}")

    return {
        "start": _week_start(store)[:10],
        "total": len(notes),
        "tags": dict(tags.most_common(10)),
        "open_todos": open_todos,
        "notes": notes,
        "markdown": "\n".join(lines),
    }


def stats(store: Store) -> dict[str, Any]:
    today = store.list(since=_day_start(store), limit=500)
    recent = store.list(limit=400)
    days = {note["created_at"][:10] for note in recent}
    streak = 0
    cursor = datetime.now(store.tz).date()
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return {
        "total": store.count(),
        "today": len(today),
        "open_todos": sum(
            1
            for note in store.list(limit=500)
            if note["type"] == "待办" and note["status"] != "done"
        ),
        "streak": streak,
    }
