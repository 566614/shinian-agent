import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any

from .store import Store


def to_obsidian_markdown(note: dict[str, Any], all_notes_map: dict[int, str] = None) -> str:
    """把单条想法转为符合 Obsidian Vault 规范的 Markdown（带 YAML Frontmatter 与双链）。"""
    all_notes_map = all_notes_map or {}
    created_at = note.get("created_at", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    title = note.get("title", "未命名想法")
    note_type = note.get("type", "灵感")
    tags = note.get("tags") or []
    if note_type and note_type not in tags:
        tags.insert(0, note_type)

    yaml_lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"type: {note_type}",
        f"created: {created_at}",
        f"status: {note.get('status', 'inbox')}",
        f"tags: [{', '.join(tags)}]",
    ]
    if note.get("project"):
        yaml_lines.append(f"project: {json.dumps(note['project'], ensure_ascii=False)}")
    if note.get("people"):
        yaml_lines.append(f"people: {json.dumps(note['people'], ensure_ascii=False)}")
    if note.get("scene"):
        yaml_lines.append(f"scene: {json.dumps(note['scene'], ensure_ascii=False)}")
    yaml_lines.append("source: \"Rokid Glasses / 拾念 Agent\"")
    yaml_lines.append("---")
    yaml_lines.append("")

    body_lines = [f"# {title}", ""]
    
    if note.get("summary"):
        body_lines.extend([f"> 💡 **摘要**：{note['summary']}", ""])

    body_lines.extend(["## 📝 原始记录", note.get("raw_text", ""), ""])

    action_items = note.get("action_items") or []
    if action_items:
        body_lines.append("## 🎯 行动项 (Action Items)")
        for action in action_items:
            body_lines.append(f"- [ ] {action}")
        body_lines.append("")

    related_ids = note.get("related_ids") or []
    if related_ids:
        body_lines.append("## 🔗 记忆回声 (关联想法)")
        for rel_id in related_ids:
            rel_title = all_notes_map.get(rel_id, f"想法 #{rel_id}")
            body_lines.append(f"- [[{rel_title}]]")
        body_lines.append("")

    if note.get("project"):
        body_lines.append(f"**关联项目**：[[{note['project']}]]")
        body_lines.append("")

    return "\n".join(yaml_lines + body_lines)


def export_obsidian_zip(store: Store) -> bytes:
    """导出全部想法为符合 Obsidian 三层架构的 Zip 压缩包。"""
    notes = store.list(limit=500)
    all_map = {n["id"]: n["title"] for n in notes}
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for note in notes:
            md_content = to_obsidian_markdown(note, all_map)
            title_clean = re.sub(r'[\\/:*?"<>|]', "_", note.get("title", f"note_{note['id']}"))
            
            # 分层目录路由 (Karpathy 3-layer Vault)
            ntype = note.get("type", "灵感")
            if ntype in ("灵感", "素材"):
                folder = "Wiki/Concepts"
            elif ntype in ("待办", "决策"):
                folder = "Wiki/Inbox"
            elif ntype == "人脉":
                folder = "Wiki/People"
            else:
                folder = "Wiki/Notes"
                
            filename = f"{folder}/{note['created_at'][:10]}-{title_clean}.md"
            zf.writestr(filename, md_content.encode("utf-8"))
            
    buffer.seek(0)
    return buffer.getvalue()


def to_share_card_html(note: dict[str, Any]) -> str:
    """生成高保真社交分享卡片 HTML（适合微信/小红书/手机保存）。"""
    title = note.get("title", "拾念想法卡片")
    summary = note.get("summary", note.get("raw_text", ""))
    raw_text = note.get("raw_text", "")
    ntype = note.get("type", "灵感")
    created_at = note.get("created_at", "")[:19].replace("T", " ")
    tags = note.get("tags") or []
    actions = note.get("action_items") or []

    tags_html = "".join([f'<span class="tag">#{t}</span>' for t in tags])
    actions_html = "".join([f'<li><span class="checkbox"></span> {a}</li>' for a in actions])
    actions_section = f'<div class="section"><div class="label">🎯 行动项</div><ul>{actions_html}</ul></div>' if actions else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 拾念卡片</title>
    <style>
        :root {{
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            --card-bg: rgba(30, 41, 59, 0.85);
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent: #6366f1;
            --accent-glow: rgba(99, 102, 241, 0.3);
            --tag-bg: rgba(99, 102, 241, 0.15);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{
            background: var(--bg-gradient);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            color: var(--text-main);
        }}
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            width: 100%;
            max-width: 440px;
            padding: 32px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), 0 0 40px var(--accent-glow);
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .badge {{
            background: var(--accent);
            color: #fff;
            font-size: 12px;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 100px;
            letter-spacing: 1px;
        }}
        .device {{
            font-size: 12px;
            color: var(--text-sub);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .title {{
            font-size: 22px;
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 12px;
            color: #ffffff;
        }}
        .summary {{
            font-size: 15px;
            color: #cbd5e1;
            line-height: 1.6;
            margin-bottom: 20px;
            background: rgba(15, 23, 42, 0.4);
            padding: 16px;
            border-radius: 14px;
            border-left: 3px solid var(--accent);
        }}
        .tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }}
        .tag {{ font-size: 13px; color: #a5b4fc; background: var(--tag-bg); padding: 4px 10px; border-radius: 8px; }}
        .section {{ margin-bottom: 20px; }}
        .label {{ font-size: 13px; font-weight: 600; color: var(--text-sub); margin-bottom: 8px; }}
        ul {{ list-style: none; }}
        li {{ display: flex; align-items: center; gap: 10px; font-size: 14px; color: #e2e8f0; margin-bottom: 6px; }}
        .checkbox {{ width: 14px; height: 14px; border: 2px solid var(--accent); border-radius: 4px; display: inline-block; }}
        .footer {{
            margin-top: 28px;
            padding-top: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: var(--text-sub);
        }}
        .brand {{ font-weight: 600; color: #f1f5f9; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <span class="badge">{ntype}</span>
            <span class="device">👓 Rokid Glasses · 拾念</span>
        </div>
        <div class="title">{title}</div>
        <div class="summary">{summary}</div>
        <div class="tags">{tags_html}</div>
        {actions_section}
        <div class="footer">
            <span class="brand">拾念 ShiNian · 想法卡片</span>
            <span>{created_at}</span>
        </div>
    </div>
</body>
</html>
"""
