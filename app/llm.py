import json
from typing import Any

from .config import Settings

SYSTEM_PROMPT = """你是「拾念」的整理助手，负责把用户随口说出的想法整理成一张结构化卡片。
只输出 JSON，不要输出任何解释。字段如下：
{
  "title": "不超过 12 个字的标题",
  "summary": "不超过 50 个字的摘要，保留用户原意",
  "type": "灵感|待办|决策|引用|素材|人脉|其他",
  "tags": ["1-4 个中文标签"],
  "action_items": ["可执行的行动项，没有则空数组"],
  "people": ["提到的人名，没有则空数组"],
  "project": "关联的项目或主题，没有则 null"
}
判断规则：带有明确动作或时间要求的是待办；做出选择的是决策；转述他人原话的是引用；
需要长期收集的材料是素材；提到具体人物关系的是人脉；其余归为灵感。"""


def extract_with_llm(text: str, settings: Settings) -> dict[str, Any]:
    """调用 OpenAI 兼容接口做结构化。调用方负责异常兜底。"""
    from openai import OpenAI

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=25)
    resp = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("LLM 返回的不是 JSON 对象")
    return data
