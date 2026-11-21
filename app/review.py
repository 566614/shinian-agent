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

    # 本地轻量级关键字/标签聚类分组 (Weekly Clusterization)
    # 把想法根据主要的 tag (即 tags 中的第一个或者高频的 tag) 进行分组聚类，并命名为 "关于 #Tag 的思考"
    clusters: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        # 寻找本条笔记的主要 tag，如果有 tags，则使用第一个作为主要分类基础
        note_tags = note.get("tags") or []
        if note_tags:
            primary_tag = note_tags[0]
            cluster_name = f"关于 #{primary_tag} 的思考"
        else:
            cluster_name = "未分类的想法"
        
        if cluster_name not in clusters:
            clusters[cluster_name] = []
        clusters[cluster_name].append(note)

    lines = ["📮 拾念 · 本周想法周报", f"共记录 {len(notes)} 条想法"]
    
    if clusters:
        lines.append("")
        lines.append("🧩 主题聚类 (Topic Clusters)")
        for cluster_title, cluster_notes in clusters.items():
            lines.append(f"### {cluster_title}")
            for cn in cluster_notes[:5]: # 每个聚类最多展示5条
                lines.append(f"- {cn['title']}——{cn['summary']}")
            if len(cluster_notes) > 5:
                lines.append(f"  *等共 {len(cluster_notes)} 条想法*")

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

    # 序列化 clusters
    serialized_clusters = {
        name: [
            {"id": n["id"], "title": n["title"], "summary": n["summary"], "created_at": n["created_at"]}
            for n in c_notes
        ]
        for name, c_notes in clusters.items()
    }

    return {
        "start": _week_start(store)[:10],
        "total": len(notes),
        "tags": dict(tags.most_common(10)),
        "open_todos": open_todos,
        "notes": notes,
        "clusters": serialized_clusters,
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
