from typing import Literal, Optional

from pydantic import BaseModel, Field

NoteType = Literal["灵感", "待办", "决策", "引用", "素材", "人脉", "其他"]
NoteStatus = Literal["inbox", "confirmed", "done"]


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000, description="用户口述或输入的原话")
    scene: Optional[str] = Field(default=None, description="通勤 / 会议 / 运动 等场景标签")
    location: Optional[str] = Field(default=None, description="地点标签")
    source: str = Field(default="glasses", description="glasses | web | cli")


class NotePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=40)
    summary: Optional[str] = Field(default=None, max_length=200)
    type: Optional[NoteType] = None
    tags: Optional[list[str]] = None
    action_items: Optional[list[str]] = None
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
    tags: list[str] = []
    action_items: list[str] = []
    people: list[str] = []
    project: Optional[str] = None
    scene: Optional[str] = None
    location: Optional[str] = None
    status: str = "inbox"
    related_ids: list[int] = []
    audio_path: Optional[str] = None
