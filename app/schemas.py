from typing import List, Literal, Optional

from pydantic import BaseModel, Field

NoteType = Literal["灵感", "待办", "决策", "引用", "素材", "人脉", "其他"]
NoteStatus = Literal["inbox", "confirmed", "done"]


class ActionItem(BaseModel):
    verb: str = Field(description="核心执行动词，例如：发送、确认、约、撰写")
    target: str = Field(description="核心动作接收体，例如：包装方案、阿哲")
    time_context: Optional[str] = Field(default=None, description="动作关联的时间点或截止时间，如：明天、下周一")
    context: str = Field(description="完整的行动上下文，高度压缩")


class ExtractionResult(BaseModel):
    note_type: NoteType = Field(description="想法卡片分类类型")
    title: str = Field(max_length=12, description="极简精炼的卡片标题，不超过12个字")
    summary: str = Field(max_length=50, description="卡片主内容摘要，不超过50个字")
    tags: List[str] = Field(max_length=5, description="高价值关联标签列表，最多5个")
    action_items: List[ActionItem] = Field(default=[], description="抽取的行动项，仅在待办类型时深入提取")
    key_entities: List[str] = Field(default=[], description="核心实体/人名/项目名称，方便关系网建链")


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="用户口述或输入的原话")
    scene: Optional[str] = Field(default=None, description="通勤 / 会议 / 运动 等场景标签")
    location: Optional[str] = Field(default=None, description="地点标签")
    source: str = Field(default="glasses", description="glasses | web | cli")


class NotePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=40)
    summary: Optional[str] = Field(default=None, max_length=200)
    type: Optional[NoteType] = None
    tags: Optional[List[str]] = None
    action_items: Optional[List[str]] = None
    status: Optional[NoteStatus] = None
    scene: Optional[str] = None
    location: Optional[str] = None


class Note(BaseModel):
    id: int
    created_at: str
    raw_text: str
    title: str
    summary: str
    type: str
    tags: List[str] = []
    action_items: List[str] = []
    people: List[str] = []
    project: Optional[str] = None
    scene: Optional[str] = None
    location: Optional[str] = None
    status: str = "inbox"
    related_ids: List[int] = []
    audio_path: Optional[str] = None
