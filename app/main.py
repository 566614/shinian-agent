import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent import NoteAgent
from .asr import transcribe_audio
from .config import Settings
from .export import export_obsidian_zip, to_obsidian_markdown, to_share_card_html, to_share_poster_html
from .review import daily, stats, weekly
from .schemas import NoteCreate, NotePatch
from .store import Store

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


def create_app(db_path: Optional[str] = None) -> FastAPI:
    settings = Settings()
    store = Store(db_path or settings.db_path, settings.timezone)
    agent = NoteAgent(settings, store)

    app = FastAPI(
        title="拾念 ShiNian",
        version="1.0.0",
        description="把随口说出的想法，变成可检索、可执行的想法卡片。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "llm": settings.llm_enabled,
            "asr": settings.asr_enabled,
            "mode": "llm" if settings.llm_enabled else "local-rules",
            "model": settings.llm_model,
        }

    @app.post("/api/notes")
    async def create_note(payload: NoteCreate) -> dict:
        return await agent.process(payload.text, payload.scene, payload.location, payload.source)

    @app.post("/api/notes/audio")
    async def create_audio_note(
        file: UploadFile = File(...),
        scene: Optional[str] = Form(None),
        location: Optional[str] = Form(None),
    ) -> dict:
        data = file.file.read()
        if not data:
            raise HTTPException(status_code=400, detail="音频为空")
        if not settings.asr_enabled:
            raise HTTPException(
                status_code=503,
                detail="未配置语音转写服务（OPENAI_API_KEY），请先用文字记录",
            )
        try:
            text = await transcribe_audio(
                data, file.filename or "audio.webm", file.content_type or "audio/webm", settings
            )
        except Exception as exc:  # 外部服务失败时给出可读提示
            raise HTTPException(status_code=502, detail=f"语音转写失败：{exc}") from exc
        if not text:
            raise HTTPException(status_code=422, detail="没有识别到内容，请再说一次")

        os.makedirs(settings.audio_dir, exist_ok=True)
        audio_path = os.path.join(settings.audio_dir, f"{uuid.uuid4().hex}.webm")
        with open(audio_path, "wb") as fh:
            fh.write(data)
        return await agent.process(text, scene, location, "glasses", audio_path=audio_path)

    @app.get("/api/notes")
    def list_notes(
        q: str = "",
        type: str = "",
        status: str = "",
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> dict:
        notes = store.list(q=q, type=type, status=status, limit=limit, offset=offset)
        return {"items": notes, "total": len(notes)}

    @app.get("/api/notes/{note_id}")
    def get_note(note_id: int) -> dict:
        note = store.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="想法不存在")
        return note

    @app.patch("/api/notes/{note_id}")
    def update_note(note_id: int, payload: NotePatch) -> dict:
        if not store.get(note_id):
            raise HTTPException(status_code=404, detail="想法不存在")
        return store.update(note_id, payload.model_dump(exclude_none=True))

    @app.delete("/api/notes/{note_id}")
    def delete_note(note_id: int) -> dict:
        if not store.delete(note_id):
            raise HTTPException(status_code=404, detail="想法不存在")
        return {"ok": True}

    @app.get("/api/review/daily")
    def review_daily() -> dict:
        return daily(store)

    @app.get("/api/review/weekly")
    def review_weekly() -> dict:
        return weekly(store)

    @app.get("/api/stats")
    def get_stats() -> dict:
        return stats(store)

    @app.get("/api/export/obsidian")
    def export_obsidian() -> Response:
        zip_bytes = export_obsidian_zip(store)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="shinian-obsidian-vault.zip"'},
        )

    @app.get("/api/export/card/{note_id}", response_class=HTMLResponse)
    def export_card(note_id: int) -> HTMLResponse:
        note = store.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="想法不存在")
        html = to_share_card_html(note)
        return HTMLResponse(content=html)

    @app.get("/api/export/poster/{note_id}", response_class=HTMLResponse)
    def export_poster(note_id: int) -> HTMLResponse:
        note = store.get(note_id)
        if not note:
            raise HTTPException(status_code=404, detail="想法不存在")
        html = to_share_poster_html(note)
        return HTMLResponse(content=html)

    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

    return app


app = create_app()
