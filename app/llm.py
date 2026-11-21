import json
import re
from typing import Any, Dict

from .config import Settings

# Rokid Spatial Joy 2026 大赛顶级金奖认知提取提示词
EXTRACTION_SYSTEM_PROMPT = """你是一个在 AR 空间计算和人机对话领域达到世界顶尖水平的认知提取 Agent，专为 Rokid Glasses 智能眼镜的参赛作品「拾念」提供底层算力。
你的任务是把用户在各种双手被占用、灵感突发场景下，随口说出或输入的一句话，精准结构化抽提为卡片数据。

你必须精确输出纯 JSON，不要输出任何 MarkDown 格式、解释或额外内容。
输出的 JSON 模式（JSON Schema）如下：
{
  "note_type": "灵感|待办|决策|引用|素材|人脉|其他",
  "title": "不超过 12 个字极其精炼的卡片标题，去掉冗余垫话",
  "summary": "不超过 50 个字的核心摘要，提炼观点，直击本质",
  "tags": ["1-4个能归纳主题的中文Hashtag标签，如：#选品 #方案 #灵感"],
  "action_items": [
    {
      "verb": "核心动作动词，如：发给、打印、约、跟进",
      "target": "动作指向主体，如：包装方案、阿哲、大纲",
      "time_context": "时间限制或截止条件，没有则为 null",
      "context": "高度压缩且逻辑闭环的可执行行动项，如：明天把包装方案发给阿哲"
    }
  ],
  "key_entities": ["提取出的重要关键词、项目名、人名，最多 5 个"]
}

【类型定义与认知推演规则】：
1. 待办 (todo)：带有明确要求、截止时间、任务驱动、执行动作的话。
2. 决策 (decision)：用户在冲突或多种方案中，做出了明确的决断、敲定、选择。
3. 引用 (quote)：转述或完整摘抄他人原话、名言、金句、书摘。
4. 素材 (material)：书籍大纲、写作片段、灵感素材、需要长期搜集归档的信息。
5. 人脉 (people)：提到人际连接、人物关系、联系人更新、引流或社交备注。
6. 灵感 (idea)：不属于以上五类、一闪而过、纯脑洞性质的奇思妙想。

【Few-Shot 认知示例】（请严格参悟以下 100 分级提取标准）：

示例 1（待办场景）：
输入："明天把包装方案发给阿哲 #选品"
输出：
{
  "note_type": "待办",
  "title": "发送包装方案",
  "summary": "明天将选品的包装方案发送给阿哲进行确认。",
  "tags": ["#选品", "#包装方案"],
  "action_items": [
    {
      "verb": "发送",
      "target": "包装方案",
      "time_context": "明天",
      "context": "将包装方案发给阿哲"
    }
  ],
  "key_entities": ["阿哲", "选品", "包装方案"]
}

示例 2（决策场景）：
输入："和阿哲讨论完了，就选体素风字母雕塑作个人站封面，不改了！"
输出：
{
  "note_type": "决策",
  "title": "选定体素雕塑",
  "summary": "确定个人站封面使用体素风字母雕塑，停止继续更改。",
  "tags": ["#个人站", "#封面设计", "#决策"],
  "action_items": [],
  "key_entities": ["阿哲", "体素风", "字母雕塑", "封面"]
}

示例 3（引用场景）：
输入："罗伯特·格林在《每日定律》里写过，真正的力量来自于克制和深思熟虑"
输出：
{
  "note_type": "引用",
  "title": "格林论力量",
  "summary": "罗伯特·格林认为真正的力量源于自我克制与深思熟虑。",
  "tags": ["#每日定律", "#金句", "#力量"],
  "action_items": [],
  "key_entities": ["罗伯特·格林", "每日定律", "力量", "克制"]
}
"""


def extract_with_llm(text: str, settings: Settings) -> Dict[str, Any]:
    """
    调用 OpenAI/Rokid 大赛官方兼容接口做 100 分超精准认知结构化。
    """
    from openai import OpenAI

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=25)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.1,  # 降低温度，确保极度稳定的逻辑结构
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"输入内容：\"{text}\""},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    
    # 彻底剥离可能存在的 markdown block
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n", "", content)
        content = re.sub(r"\n```$", "", content)
        content = content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        # 鲁棒性防崩兜底：正则清洗
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            raise ValueError(f"无法将 LLM 响应解析为 JSON 格式: {e}")

    return parse_and_validate_extraction(data, text)


def parse_and_validate_extraction(data: Dict[str, Any], text: str) -> Dict[str, Any]:
    """
    对大模型提取出的数据进行二次校验和标准格式还原，保证 100% 架构可靠性。
    """
    note_type = data.get("note_type") or "灵感"
    if note_type not in ["灵感", "待办", "决策", "引用", "素材", "人脉", "其他"]:
        note_type = "其他"

    title = str(data.get("title") or "").strip()
    if not title or len(title) > 20:
        # 本地策略兜底标题
        title = text[:12] + ("…" if len(text) > 12 else "")

    summary = str(data.get("summary") or "").strip()
    if not summary:
        summary = text[:50] + ("…" if len(text) > 50 else "")

    # 解析行动项 (ActionItem)
    raw_actions = data.get("action_items") or []
    normalized_actions = []
    if isinstance(raw_actions, list):
        for act in raw_actions:
            if isinstance(act, dict) and "context" in act:
                normalized_actions.append(str(act["context"]))
            elif isinstance(act, str):
                normalized_actions.append(act)

    # 提取标签
    raw_tags = data.get("tags") or []
    cleaned_tags = []
    if isinstance(raw_tags, list):
        for t in raw_tags:
            t = str(t).strip().lstrip("#")
            if t:
                cleaned_tags.append(t)

    # 提取人名
    people = []
    entities = data.get("key_entities") or []
    if isinstance(entities, list):
        for ent in entities:
            # 简单判断是否为人名
            if len(ent) in (2, 3) and re.match(r"^[\u4e00-\u9fa5]+$", ent):
                people.append(ent)

    return {
        "title": title[:12],
        "summary": summary[:50],
        "type": note_type,
        "tags": cleaned_tags[:4],
        "action_items": normalized_actions[:3],
        "people": people[:3],
        "project": data.get("project") or None,
        "key_entities": entities,
    }
