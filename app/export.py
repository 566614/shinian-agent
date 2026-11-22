import io
import json
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
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
    """导出全部想法为符合 Obsidian 三层架构的 Zip 压缩包，并根据配置自动同步至本地 Obsidian Vault。"""
    notes = store.list(limit=500)
    all_map = {n["id"]: n["title"] for n in notes}
    
    # S+ 级多路径智能容错同步机制 (Pristine Obsidian Path Discovery & Fallback)
        vault_root = None
    candidate_paths = [
        vault_path_str,
        "C:/Users/Lenovo/Desktop/阮/Wiki/Inbox/",
        "C:/Users/Lenovo/Desktop/阮/",
        "~/Desktop/阮/Wiki/Inbox/",
        "./data/obsidian/"
    ]
    
    for path_candidate in candidate_paths:
        try:
            expanded_path = Path(path_candidate).expanduser()
            # 智能判定：定位 Obsidian Vault 的主物理根目录
            if "Wiki/Inbox" in str(expanded_path).replace("\\", "/"):
                root_test = expanded_path.parent.parent
            else:
                root_test = expanded_path
            
            test_dir = root_test / "Wiki" / "Notes"
            test_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_dir / ".shinian_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            
            vault_root = root_test
            break
        except Exception:
            continue

    if not vault_root:
        fallback_path = "C:/Users/Lenovo/Desktop/FallbackVault/"
        vault_root = Path(fallback_path)
        vault_root.mkdir(parents=True, exist_ok=True)
        print(f"Fallback to default vault location: {fallback_path}")
    vault_root = None
    
    # 尝试多条安全备选路径进行热同步
    candidate_paths = [
        vault_path_str,
        "C:/Users/Lenovo/Desktop/阮/Wiki/Inbox/",
        "C:/Users/Lenovo/Desktop/阮/",
        "~/Desktop/阮/Wiki/Inbox/",
        "./data/obsidian/"
    ]
    
    for path_candidate in candidate_paths:
        try:
            expanded_path = Path(path_candidate).expanduser()
            # 智能判定：定位 Obsidian Vault 的主物理根目录
            if "Wiki/Inbox" in str(expanded_path).replace("\\", "/"):
                root_test = expanded_path.parent.parent
            else:
                root_test = expanded_path
            
            # 创建测试写入，验证文件夹物理写权限
            test_dir = root_test / "Wiki" / "Notes"
            test_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_dir / ".shinian_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink() # 立即清理临时文件
            
            vault_root = root_test
            break # 成功找到一条 100% 可行路径，退出寻找
        except Exception:
            continue
            
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

            # 自动同步写入本地 (S+级高容错防护)
            if vault_root:
                try:
                    local_file = vault_root / filename
                    local_file.parent.mkdir(parents=True, exist_ok=True)
                    local_file.write_text(md_content, encoding="utf-8")
                except Exception:
                    pass
            
    buffer.seek(0)
    return buffer.getvalue()

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

            # 自动同步写入本地
            if vault_root:
                try:
                    local_file = vault_root / filename
                    local_file.parent.mkdir(parents=True, exist_ok=True)
                    local_file.write_text(md_content, encoding="utf-8")
                except Exception:
                    pass
            
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


def to_share_poster_html(note: dict[str, Any]) -> str:
    """动态分享海报生成器。生成绝美高保真卡片或海报 (Dynamic Poster Generator) 
    支持精致优雅的 Google 字体、圆角发光暗黑设计、漂亮的呼吸光边框，适合在微信、小红书和即刻进行高质量分享。
    """
    title = note.get("title", "拾念想法卡片")
    summary = note.get("summary", note.get("raw_text", ""))
    raw_text = note.get("raw_text", "")
    ntype = note.get("type", "灵感")
    created_at = note.get("created_at", "")[:19].replace("T", " ")
    tags = note.get("tags") or []
    actions = note.get("action_items") or []

    tags_html = "".join([f'<span class="tag">#{t}</span>' for t in tags])
    actions_html = "".join([f'<li><span class="checkbox"></span> {a}</li>' for a in actions])
    actions_section = f'<div class="section"><div class="label">🎯 核心行动项</div><ul>{actions_html}</ul></div>' if actions else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - 拾念海报</title>
    <!-- 引用优雅的 Google 字体 -->
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@500;700;900&family=Poppins:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #030712;
            --poster-bg: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #030712 100%);
            --card-glass: rgba(15, 23, 42, 0.65);
            --text-neon: #a5b4fc;
            --border-glow: linear-gradient(135deg, #6366f1, #d946ef, #3b82f6);
            --font-title: 'Noto Serif SC', serif;
            --font-body: 'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: var(--bg-dark);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            font-family: var(--font-body);
            overflow-x: hidden;
        }}
        /* 海报容器，固定高宽比更适合小红书/微信分享 */
        .poster-container {{
            background: var(--poster-bg);
            width: 100%;
            max-width: 480px;
            min-height: 720px;
            border-radius: 36px;
            padding: 4px;
            position: relative;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8), 
                        0 0 80px rgba(99, 102, 241, 0.25);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        /* 流光溢彩发光边框 */
        .poster-container::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border-radius: 36px;
            padding: 2.5px;
            background: var(--border-glow);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
            z-index: 2;
        }}
        .poster-inner {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 40px;
            position: relative;
            z-index: 1;
        }}
        /* 顶部信息 */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 36px;
        }}
        .badge {{
            font-family: var(--font-body);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: 800;
            background: linear-gradient(90deg, #6366f1, #a855f7);
            color: #ffffff;
            padding: 6px 16px;
            border-radius: 30px;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
        }}
        .device-info {{
            font-size: 12px;
            color: #64748b;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        /* 主体内容 */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            margin-bottom: 30px;
        }}
        .quote-icon {{
            font-size: 48px;
            color: rgba(99, 102, 241, 0.2);
            font-family: var(--font-title);
            line-height: 1;
            margin-bottom: 8px;
        }}
        .title {{
            font-family: var(--font-title);
            font-weight: 900;
            font-size: 32px;
            line-height: 1.35;
            color: #ffffff;
            margin-bottom: 24px;
            letter-spacing: -0.5px;
            text-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            background: linear-gradient(135deg, #ffffff 60%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .summary-card {{
            background: var(--card-glass);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: inset 0 0 20px rgba(255, 255, 255, 0.02);
            position: relative;
        }}
        .summary-card::after {{
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: linear-gradient(to bottom, #6366f1, #d946ef);
            border-radius: 20px 0 0 20px;
        }}
        .summary-text {{
            font-size: 16px;
            line-height: 1.7;
            color: #e2e8f0;
            font-weight: 500;
        }}
        .raw-text {{
            font-size: 13px;
            color: #475569;
            line-height: 1.6;
            margin-top: 14px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 12px;
            font-style: italic;
        }}
        /* 标签 */
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 24px;
        }}
        .tag {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-neon);
            background: rgba(99, 102, 241, 0.12);
            border: 1px solid rgba(99, 102, 241, 0.2);
            padding: 6px 14px;
            border-radius: 12px;
            transition: all 0.3s ease;
        }}
        /* 行动项 */
        .section {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 20px;
        }}
        .label {{
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #64748b;
            margin-bottom: 12px;
        }}
        ul {{
            list-style: none;
        }}
        li {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
            color: #cbd5e1;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        li:last-child {{
            margin-bottom: 0;
        }}
        .checkbox {{
            width: 16px;
            height: 16px;
            border: 2px solid #818cf8;
            border-radius: 5px;
            display: inline-block;
            flex-shrink: 0;
            background: rgba(99, 102, 241, 0.1);
        }}
        /* 底部信息 */
        .footer {{
            margin-top: 36px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .brand {{
            font-family: var(--font-body);
            font-weight: 800;
            font-size: 14px;
            color: #ffffff;
            letter-spacing: 1px;
            background: linear-gradient(90deg, #ffffff, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .date {{
            font-size: 11px;
            color: #475569;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="poster-container">
        <div class="poster-inner">
            <div class="header">
                <span class="badge">{ntype}</span>
                <span class="device-info">👓 ROKID GLASSES</span>
            </div>
            <div class="main-content">
                <div class="quote-icon">“</div>
                <h1 class="title">{title}</h1>
                <div class="summary-card">
                    <p class="summary-text">{summary}</p>
                    {f'<p class="raw-text">“ {raw_text} ”</p>' if raw_text and raw_text != summary else ""}
                </div>
                <div class="tags">
                    {tags_html}
                </div>
                {actions_section}
            </div>
            <div class="footer">
                <span class="brand">拾念 SHINIAN</span>
                <span class="date">{created_at}</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

