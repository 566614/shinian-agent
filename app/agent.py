import re
import difflib
from typing import Any, Optional, List, Set, Dict, Tuple
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Settings
from .llm import extract_with_llm
from .store import Store

TYPES = {"灵感", "待办", "决策", "引用", "素材", "人脉", "其他"}

TODO_MARKERS = (
    "待办", "要", "得", "记得", "需要", "明天", "后天", "下周", "之后",
    "安排", "联系", "发给", "确认", "提醒", "约", "跟进", "去做", "开发", "写个", "做个", "整理"
)
DECISION_MARKERS = ("决定", "定了", "确定用", "就选", "选它", "不改了", "敲定", "通过", "采用", "不再更改")
QUOTE_MARKERS = ("原话", "说过", "他说", "她说", "“", "”", "写道", "写过", "提到")


def _tokens(text: str) -> Set[str]:
    """高精度切词，提取中文双字特征与英文单词，建立无摩擦词袋。"""
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9#]+", " ", text)
    out: Set[str] = set()
    for part in cleaned.split():
        if not part:
            continue
        if re.search(r"[\u4e00-\u9fa5]", part):
            out.add(part)
            out.update(part[i : i + 2] for i in range(max(0, len(part) - 1)))
        else:
            out.add(part.lower())
    return out


def parse_relative_time_to_iso(text: str, base_time: datetime) -> Optional[str]:
    """高精度解析中文和中英混合输入中的相对时间词，转换为 ISO-8601 格式时间字符串。"""
    offset_days = None
    matched_date = False

    week_map = {
        "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
        "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6
    }

    # 1. 相对日期匹配
    if "大后天" in text:
        offset_days = 3
        matched_date = True
    elif "后天" in text:
        offset_days = 2
        matched_date = True
    elif "明天" in text or "明日" in text:
        offset_days = 1
        matched_date = True
    elif "今天" in text or "今日" in text or "今晚" in text:
        offset_days = 0
        matched_date = True
    elif "昨天" in text or "昨日" in text:
        offset_days = -1
        matched_date = True
    elif "前天" in text:
        offset_days = -2
        matched_date = True

    # 2. 星期匹配
    # "下下周一/二..."
    next_next_week_match = re.search(r"下下周([一二三四五六日天1-7])", text)
    if next_next_week_match:
        w = week_map[next_next_week_match.group(1)]
        base_weekday = base_time.weekday()
        offset_days = 14 - base_weekday + w
        matched_date = True
    else:
        # "下周一/二..."
        next_week_match = re.search(r"下周([一二三四五六日天1-7])", text)
        if next_week_match:
            w = week_map[next_week_match.group(1)]
            base_weekday = base_time.weekday()
            offset_days = 7 - base_weekday + w
            matched_date = True
        else:
            # "这周一/二..." / "本周一/二..."
            this_week_match = re.search(r"(这周|本周|当前周)([一二三四五六日天1-7])", text)
            if this_week_match:
                w = week_map[this_week_match.group(2)]
                base_weekday = base_time.weekday()
                offset_days = w - base_weekday
                matched_date = True
            else:
                # "周一/二..." 或 "星期一/二..."
                week_match = re.search(r"(周|星期)([一二三四五六日天1-7])", text)
                if week_match:
                    w = week_map[week_match.group(2)]
                    base_weekday = base_time.weekday()
                    # 如果说的星期 <= 今天，通常指下周的那个星期几，除非有今天、明天修饰
                    if w > base_weekday:
                        offset_days = w - base_weekday
                    else:
                        offset_days = 7 - base_weekday + w
                    matched_date = True

    # 3. "N天后" / "N天之后"
    if not matched_date:
        after_day_match = re.search(r"(\d+)\s*天(之)?后", text)
        if after_day_match:
            offset_days = int(after_day_match.group(1))
            matched_date = True

    # 计算基准目标日期
    if offset_days is not None:
        target_date = base_time + timedelta(days=offset_days)
    else:
        target_date = base_time

    # 4. 时刻匹配
    # 默认时刻：如果只指定了日期没有指定时刻，默认早上 9 点
    hour, minute, second = 9, 0, 0
    matched_time = False

    # 相对小时/分钟（如 3小时后，30分钟后）优先
    after_hour_match = re.search(r"(\d+)\s*(个)?小时(之)?后", text)
    after_minute_match = re.search(r"(\d+)\s*分钟(之)?后", text)
    if after_hour_match or after_minute_match:
        delta = timedelta()
        if after_hour_match:
            delta += timedelta(hours=int(after_hour_match.group(1)))
        if after_minute_match:
            delta += timedelta(minutes=int(after_minute_match.group(1)))
        target_time = base_time + delta
        return target_time.isoformat(timespec="seconds")

    # 上下午修饰
    is_pm = False
    if any(w in text for w in ["下午", "晚上", "傍晚", "深夜", "下班后", "pm", "PM"]):
        is_pm = True
    elif "中午" in text:
        # 中午12点算12点
        hour = 12

    # 匹配 "15:30", "15点30" 等
    time_pattern = re.search(r"(\d{1,2})[:：](\d{2})", text)
    if time_pattern:
        hour = int(time_pattern.group(1))
        minute = int(time_pattern.group(2))
        matched_time = True
    else:
        # 匹配中文或数字时间：如 "三点半", "3点", "六点整"
        num_map = {
            "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
            "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18,
            "十九": 19, "二十": 20, "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24
        }
        chinese_time_match = re.search(r"([一二两三四五六七八九十]+|\d{1,2})\s*点\s*(([一二三四五六七八九十\d]+)分|半|一刻|三刻|整)?", text)
        if chinese_time_match:
            h_str = chinese_time_match.group(1)
            if h_str.isdigit():
                hour = int(h_str)
            else:
                hour = num_map.get(h_str, 9)
            matched_time = True

            m_str = chinese_time_match.group(2)
            if m_str:
                if "半" in m_str:
                    minute = 30
                elif "一刻" in m_str:
                    minute = 15
                elif "三刻" in m_str:
                    minute = 45
                elif "整" in m_str:
                    minute = 0
                else:
                    # 解析分钟：如 "三十分", "30分"
                    min_num_match = re.search(r"([原一二三四五六七八九十\d]+)", m_str)
                    if min_num_match:
                        min_val_str = min_num_match.group(1)
                        if min_val_str.isdigit():
                            minute = int(min_val_str)
                        else:
                            if min_val_str in num_map:
                                minute = num_map[min_val_str]
                            elif "十" in min_val_str:
                                parts = min_val_str.split("十")
                                temp_min = 0
                                if parts[0] == "":
                                    temp_min += 10
                                else:
                                    temp_min += num_map.get(parts[0], 0) * 10
                                if parts[1] != "":
                                    temp_min += num_map.get(parts[1], 0)
                                minute = temp_min

    if is_pm and hour < 12:
        hour += 12

    if matched_date or matched_time:
        final_time = target_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return final_time.isoformat(timespec="seconds")

    return None


def smart_truncate(title_str: str, max_len: int = 12) -> str:
    """智能截断标题，防止中英混合导致英文单词被硬生生切成两半。"""
    if len(title_str) <= max_len:
        return title_str
    truncated = title_str[:max_len]
    if re.match(r"[A-Za-z0-9]", title_str[max_len - 1]) and re.match(r"[A-Za-z0-9]", title_str[max_len]):
        idx = max_len - 1
        while idx > max_len - 6 and idx > 0:
            if not re.match(r"[A-Za-z0-9]", title_str[idx]):
                truncated = title_str[:idx]
                break
            idx -= 1
    return truncated.strip() + "…"


class NoteAgent:
    """戴在眼镜上的灵感记录智能体内核。"""

    def __init__(self, settings: Settings, store: Store) -> None:
        self.settings = settings
        self.store = store

    async def process(
        self,
        text: str,
        scene: Optional[str] = None,
        location: Optional[str] = None,
        source: str = "glasses",
        audio_path: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        text = text.strip()
        data = await self._extract(text)
        data = self._normalize(data, text)

        # 100分级 Time Resolution 核心时间解析与注入
        base_time_str = created_at or data.get("created_at") or self.store.now()
        try:
            base_time = datetime.fromisoformat(base_time_str)
        except Exception:
            base_time = datetime.now(ZoneInfo("Asia/Shanghai"))

        resolved_actions = []
        for act in data.get("action_items") or []:
            iso_time = parse_relative_time_to_iso(act, base_time)
            if not iso_time:
                # 容错：若行动项被精简而丢失了相对时间词，扫描 raw_text
                iso_time = parse_relative_time_to_iso(text, base_time)

            if iso_time:
                if not re.search(r"\(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", act):
                    act = f"{act} ({iso_time})"
            resolved_actions.append(act)

        data["action_items"] = resolved_actions

        data.update(
            {
                "created_at": base_time_str,
                "raw_text": text,
                "scene": scene,
                "location": location,
                "source": source,
                "related_ids": self._related(text, data),
                "audio_path": audio_path,
            }
        )
        return self.store.create(data)

    async def _extract(self, text: str) -> Dict[str, Any]:
        if self.settings.llm_enabled:
            try:
                return await extract_with_llm(text, self.settings)
            except Exception:
                pass
        return self._heuristic(text)

    def _heuristic(self, text: str) -> Dict[str, Any]:
        # 100分级离线启发式分类系统 (打分制精准认知抽取)
        scores = {
            "待办": 0.0,
            "决策": 0.0,
            "引用": 0.0,
            "人脉": 0.0,
            "素材": 0.0,
            "灵感": 0.0
        }
        
        # 待办权重
        todo_strong = ["发给", "记得", "需要", "跟进", "通知", "准备", "约", "讨论", "去做", "开发", "写个", "做个", "整理"]
        todo_weak = ["要", "得", "去", "联系", "提醒", "安排"]
        time_words = ["明天", "后天", "下周", "星期", "周一", "周二", "周三", "周四", "周五", "周六", "周日", "今天下午", "今天上午"]
        
        for w in todo_strong:
            if w in text: scores["待办"] += 2.0
        for w in todo_weak:
            if w in text: scores["待办"] += 1.0
        for w in time_words:
            if w in text: scores["待办"] += 1.5
            
        # 决策权重
        decision_strong = ["定了", "敲定", "不改了", "就选", "选它", "确定用", "决定用", "不再更改", "最终决定"]
        decision_weak = ["决定", "确定", "选择", "采纳", "通过"]
        for w in decision_strong:
            if w in text: scores["决策"] += 2.5
        for w in decision_weak:
            if w in text: scores["决策"] += 1.0
            
        # 引用权重
        quote_strong = ["“", "”", "写道", "写过", "语录", "名言"]
        quote_weak = ["说", "说过", "提到", "指出"]
        for w in quote_strong:
            if w in text: scores["引用"] += 2.0
        for w in quote_weak:
            if w in text: scores["引用"] += 0.8
            
        # 人脉权重
        people_strong = ["认识了", "联系方式", "微信号", "加了微信", "新名片"]
        people_weak = ["微信", "电话", "邮箱", "联系", "备注"]
        for w in people_strong:
            if w in text: scores["人脉"] += 2.5
        for w in people_weak:
            if w in text: scores["人脉"] += 0.8
            
        # 素材权重
        material_strong = ["大纲", "草稿", "素材", "搜集", "片段", "备忘录"]
        material_weak = ["资料", "参考", "图片", "配图"]
        for w in material_strong:
            if w in text: scores["素材"] += 2.5
        for w in material_weak:
            if w in text: scores["素材"] += 0.8
            
        # 灵感权重
        idea_strong = ["灵感", "点子", "脑洞", "奇思妙想", "突然想到"]
        idea_weak = ["想法", "觉得", "要是", "如果"]
        for w in idea_strong:
            if w in text: scores["灵感"] += 2.0
        for w in idea_weak:
            if w in text: scores["灵感"] += 0.5
            
        scores["灵感"] += 0.1
        type_ = max(scores, key=scores.get)

        # 100分级离线人名和项目提取
        people = re.findall(r"@([_a-zA-Z0-9\u4e00-\u9fa5]{2,10})", text)
        known_names = ["阿哲", "小林", "老张", "小张", "老周", "老王", "小王", "罗伯特", "格林"]
        for name in known_names:
            if name in text and name not in people and len(people) < 3:
                people.append(name)

        project = None
        project_match = re.search(r"关于\s*([_a-zA-Z0-9\u4e00-\u9fa5]{2,12})", text)
        if project_match:
            project = project_match.group(1)
        else:
            project_patterns = [
                r"([A-Za-z0-9\s_\-]{2,12})\s*项目",
                r"([A-Za-z0-9\s_\-]{2,12})\s*系统",
                r"开发\s*([A-Za-z0-9\s_\-]{2,12})",
                r"做个\s*([A-Za-z0-9\s_\-]{2,12})"
            ]
            for pat in project_patterns:
                match = re.search(pat, text)
                if match:
                    project = match.group(1).strip()
                    break

        # 标签生成
        tags = re.findall(r"#([_a-zA-Z0-9\u4e00-\u9fa5]+)", text)
        tags = [t for t in tags if t]
        keywords_map = {
            "React": ["React", "react", "前端"],
            "开发": ["开发", "代码", "写代码", "编程", "系统", "Network OS", "backend", "前端", "后端"],
            "设计": ["包装", "木纹", "封面", "雕塑", "视觉", "插画", "设计", "体素", "UI", "UX"],
            "会议": ["讨论", "讨论完", "会议", "沟通", "开会"],
            "选品": ["选品", "采购", "商品"],
            "人际": ["约了", "跟进", "联系", "微信"],
            "学习": ["定律", "阅读", "读了", "写过", "名言"]
        }
        for tag_name, keywords in keywords_map.items():
            if len(tags) >= 4:
                break
            if tag_name in tags:
                continue
            if any(kw.lower() in text.lower() for kw in keywords):
                tags.append(tag_name)
        if type_ not in tags and len(tags) < 4:
            tags.append(type_)

        # 行动项深度提取
        actions: List[str] = []
        segments = re.split(r"[。；;！!\n\r]", text)
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            segment = re.sub(r"^[\s，。,.!?！？、；;：:#]+", "", segment)
            if any(k in segment for k in TODO_MARKERS) or type_ == "待办":
                cleaned_act = re.sub(r"#[_a-zA-Z0-9\u4e00-\u9fa5]+", "", segment)
                cleaned_act = cleaned_act.strip(" ，。,.!?！？、；;：:")
                if cleaned_act and cleaned_act not in actions:
                    actions.append(cleaned_act[:60])

        # 100分级离线实体网建链提取 (key_entities)
        entities = []
        english_terms = re.findall(r"\b[A-Za-z0-9][A-Za-z0-9\s_\-]{0,15}[A-Za-z0-9]\b|\b[A-Za-z0-9]\b", text)
        english_terms = [t.strip() for t in english_terms if t.lower().strip() not in {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of"
        }]
        for term in english_terms:
            if term not in entities and len(entities) < 5:
                entities.append(term)
        for p in people:
            if p not in entities and len(entities) < 5:
                entities.append(p)
        if project and project not in entities and len(entities) < 5:
            entities.append(project)
        quotes_content = re.findall(r"“([^”]+)”|\"([^\"]+)\"", text)
        for qc in quotes_content:
            val = qc[0] or qc[1]
            if val and val not in entities and len(entities) < 5:
                entities.append(val[:15])

        return {
            "title": self._title(text),
            "summary": text[:50] + ("…" if len(text) > 50 else ""),
            "type": type_,
            "tags": tags,
            "action_items": actions[:3],
            "people": people,
            "project": project,
            "key_entities": entities,
        }

    @staticmethod
    def _title(text: str) -> str:
        # 1. 过滤开头特殊符号
        title = re.sub(r"^[\s，。,.!?！？、；;：:#]+", "", text)
        # 2. 智能垫话清洗
        title = re.sub(r"^(今天想到|突然想到|我觉得|我想说|要不|我们|大家都|突然发现|刚刚|之前|跟\w+讨论完了[，,]?|讨论完了[，,]?)", "", title)
        title = re.sub(r"^(明天|后天|今天|下周|周一|周二|周三|周四|周五|周六|周日|昨天|前天)\s*", "", title)
        title = re.sub(r"^(关于|对于|至于)", "", title)
        # 3. 清理首尾空格与标点
        title = re.sub(r"\s+", " ", title).strip(" ，。,.!?！？、；;：:#@")
        # 4. 智能中英混合截断
        return smart_truncate(title, 12)

    def _normalize(self, data: Dict[str, Any], text: str) -> Dict[str, Any]:
        title = str(data.get("title") or "").strip() or self._title(text)
        summary = str(data.get("summary") or "").strip() or text[:50]
        type_ = str(data.get("type") or "").strip()
        if type_ not in TYPES:
            type_ = self._heuristic(text)["type"]

        def str_list(value: Any, limit: int) -> List[str]:
            if not isinstance(value, list):
                return []
            result: List[str] = []
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

    def _related(self, text: str, current_extraction: Dict[str, Any], limit: int = 3) -> List[int]:
        """
        100分级混合权重相似想法关联匹配（记忆回声 Memory Echo 核心实现）。
        融合切词匹配度、高价值 Tag 重合度与 Fuzzy 内容匹配度。
        """
        current_tokens = _tokens(text)
        if not current_tokens:
            return []

        curr_tags = set(current_extraction.get("tags") or [])
        curr_people = set(current_extraction.get("people") or [])
        
        scored: List[Tuple[float, int]] = []
        
        # 遍历最近 200 条想法，检索高度关联的内容
        for note in self.store.recent(200):
            score = 0.0
            other_tokens = _tokens(note["raw_text"])
            if not other_tokens:
                continue

            # 1. 词特征和交集比例 (权重: 0.40)
            overlap_tokens = current_tokens & other_tokens
            if len(overlap_tokens) >= 2:
                jaccard = len(overlap_tokens) / len(current_tokens | other_tokens)
                score += jaccard * 0.40

            # 2. 高价值 Tag 重合度 (权重: 0.35)
            other_tags = set(note.get("tags") or [])
            overlap_tags = curr_tags & other_tags
            if overlap_tags:
                tag_score = len(overlap_tags) / max(len(curr_tags | other_tags), 1)
                score += tag_score * 0.35

            # 3. Fuzzy 文本相似度 (权重: 0.25)
            fuzzy_ratio = difflib.SequenceMatcher(None, text.lower(), note["raw_text"].lower()).ratio()
            if fuzzy_ratio > 0.15:
                score += fuzzy_ratio * 0.25

            # 4. 人物关联额外 Boost 奖励分
            other_people = set(note.get("people") or [])
            if curr_people & other_people:
                score += 0.05

            # 相似度达到阀值，视为触发“记忆回声”
            if score >= 0.20:
                scored.append((score, note["id"]))

        scored.sort(reverse=True)
        return [note_id for _, note_id in scored[:limit]]
