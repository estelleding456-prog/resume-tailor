from contextlib import asynccontextmanager

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ai import AiConfigError, chat_completion, parse_json_object
from .db import connection, init_db
from .documents import parse_document, parse_text_file, safe_filename, to_json
from .html_renderer import render_resume_html
from .prompts import CHAT_SYSTEM, EDIT_SYSTEM, GENERATE_SYSTEM, REVIEW_SYSTEM
from .resume_content import apply_date_order, apply_structure_mode, normalize_resume_content, safe_output_name
from .resume_ir import build_resume_ir
from .settings import DATA_DIR

class ModelConfigIn(BaseModel):
    base_url: str = ""
    model_name: str = ""
    api_key: str = ""

class ModelConfigOut(BaseModel):
    base_url: str
    model_name: str
    has_api_key: bool

class JdTextIn(BaseModel):
    text: str

class ChatIn(BaseModel):
    jd_text: str = ""
    message: str
    history: list[dict[str, str]] = []
    version_id: str = ""

class GenerateIn(BaseModel):
    jd_text: str
    history: list[dict[str, str]] = []

class VersionUpdateIn(BaseModel):
    content: dict[str, Any]

class PreferenceSuggestIn(BaseModel):
    version_id: str

class PreferencesIn(BaseModel):
    page_limit: str = "one"
    structure_mode: str = "reorder"
    layout_mode: str = "adaptive"
    date_order: str = "desc"
    profile_text: str = ""
    calibrated: bool = False

class TemplateConfigIn(BaseModel):
    config: dict[str, Any]

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app = FastAPI(title="Local Resume Tailor API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "resume-tailor-api"}

@app.get("/api/model-config", response_model=ModelConfigOut)
def get_model_config() -> ModelConfigOut:
    with connection() as conn:
        row = conn.execute("SELECT base_url, model_name, api_key FROM model_config WHERE id = 1").fetchone()
    return ModelConfigOut(
        base_url=row["base_url"],
        model_name=row["model_name"],
        has_api_key=bool(row["api_key"]),
    )

@app.put("/api/model-config", response_model=ModelConfigOut)
def save_model_config(config: ModelConfigIn) -> ModelConfigOut:
    with connection() as conn:
        existing = conn.execute("SELECT api_key FROM model_config WHERE id = 1").fetchone()
        api_key = config.api_key or (existing["api_key"] if existing else "")
        conn.execute(
            """UPDATE model_config
               SET base_url = ?, model_name = ?, api_key = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = 1""",
            (config.base_url.strip(), config.model_name.strip(), api_key),
        )
    return ModelConfigOut(
        base_url=config.base_url.strip(),
        model_name=config.model_name.strip(),
        has_api_key=bool(api_key),
    )

def _model_config() -> dict[str, str]:
    with connection() as conn:
        row = conn.execute("SELECT base_url, model_name, api_key FROM model_config WHERE id = 1").fetchone()
    return {"base_url": row["base_url"], "model_name": row["model_name"], "api_key": row["api_key"]}

def _template_config() -> dict:
    with connection() as conn:
        row = conn.execute("SELECT config_json FROM template WHERE id = 1").fetchone()
    return json.loads(row["config_json"])

def _experience_text() -> str:
    with connection() as conn:
        row = conn.execute("SELECT content_text FROM experience_library WHERE id = 1").fetchone()
    return row["content_text"] if row else ""

def _master_resume() -> dict:
    with connection() as conn:
        row = conn.execute("SELECT parsed_json FROM master_resume WHERE id = 1").fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="请先上传主简历。")
    return json.loads(row["parsed_json"])


def _render_version(content: dict[str, Any]) -> str:
    resume = _master_resume()
    return render_resume_html(content, _template_config(), resume.get("assets", []))


def _clip_sentence(text: str, limit: int = 100) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "！", "？", "；", "!", "?", ";", "，", ",", "、", " "):
        idx = cut.rfind(sep)
        if idx > 0:
            return cut[: idx + 1]
    return cut


def _preferences() -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT page_limit, structure_mode, layout_mode, date_order, profile_text, calibrated FROM resume_preferences WHERE id = 1").fetchone()
    return {**dict(row), "calibrated": bool(row["calibrated"])}


def _version_content(version_id: str) -> tuple[dict[str, Any], str]:
    with connection() as conn:
        row = conn.execute("SELECT content_json, display_name FROM resume_version WHERE id = ?", (version_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="简历版本不存在。")
    return normalize_resume_content(json.loads(row["content_json"])), row["display_name"]


@app.get("/api/preferences")
def get_preferences() -> dict:
    return _preferences()


@app.put("/api/preferences")
def save_preferences(payload: PreferencesIn) -> dict:
    allowed = {
        "page_limit": {"one", "two", "unlimited"},
        "structure_mode": {"preserve", "reorder", "rebuild"},
        "layout_mode": {"preserve", "adaptive"},
        "date_order": {"desc", "asc", "relevance"},
    }
    values = payload.model_dump()
    for field, choices in allowed.items():
        if values[field] not in choices:
            raise HTTPException(status_code=400, detail=f"无效的偏好设置：{field}")
    profile_text = payload.profile_text.strip()[:500]
    with connection() as conn:
        conn.execute("""UPDATE resume_preferences SET page_limit = ?, structure_mode = ?, layout_mode = ?, date_order = ?, profile_text = ?, calibrated = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1""",
                     (payload.page_limit, payload.structure_mode, payload.layout_mode, payload.date_order, profile_text, int(payload.calibrated)))
    return _preferences()


@app.post("/api/preferences/suggest")
def suggest_preferences(payload: PreferenceSuggestIn) -> dict:
    with connection() as conn:
        row = conn.execute("""SELECT rv.initial_content_json, rv.content_json, js.messages_json FROM resume_version rv JOIN job_session js ON js.id = rv.job_session_id WHERE rv.id = ?""", (payload.version_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="简历版本不存在。")
    context = {
        "fixed_choices": _preferences(),
        "initial_version": json.loads(row["initial_content_json"] or row["content_json"]),
        "final_version": json.loads(row["content_json"]),
        "conversation": json.loads(row["messages_json"] or "[]"),
    }
    messages = [
        {"role": "system", "content": "根据用户首次真实简历修改过程，提炼跨JD仍稳定成立的简历写作偏好。只允许输出适用于每一份简历的一般性写作/表达规则（如内容密度、概括标签风格、重点强调方式、删冗程度）。严格禁止写入：具体公司名、岗位名、板块改名、具体某条经历的内容或删留、本次岗位相关的针对性措辞；禁止写入过程记录、一次性决定、自相矛盾的表述；不要重复页数、结构、版式等固定选项。若修改过程中没有跨JD稳定的写作偏好，输出一句‘本次为岗位针对性修改，无跨JD稳定偏好’。输出不超过300字纯文本，不要标题。"}, 
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]
    try:
        suggestion = chat_completion(_model_config(), messages).strip()[:500]
    except AiConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"suggestion": suggestion}

@app.get("/api/template")
def get_template() -> dict:
    with connection() as conn:
        row = conn.execute("SELECT config_json, updated_at FROM template WHERE id = 1").fetchone()
    return {"config": json.loads(row["config_json"]), "updated_at": row["updated_at"]}

@app.put("/api/template")
def save_template(payload: TemplateConfigIn) -> dict:
    with connection() as conn:
        conn.execute("UPDATE template SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (json.dumps(payload.config, ensure_ascii=False),))
    return {"config": payload.config, "saved": True}

@app.get("/api/versions")
def list_versions() -> list[dict]:
    with connection() as conn:
        rows = conn.execute("SELECT id, job_session_id, display_name, created_at, updated_at, pdf_path FROM resume_version ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]

@app.post("/api/chat")
def chat(payload: ChatIn) -> dict:
    resume = _master_resume()
    context: dict[str, Any] = {
        "master_resume": resume.get("text", ""),
        "experience_library": _experience_text(),
        "preferences": _preferences(),
        "job_description": payload.jd_text,
    }
    system = CHAT_SYSTEM
    if payload.version_id:
        current, _ = _version_content(payload.version_id)
        context["current_version"] = current
        system = EDIT_SYSTEM
    messages = [
        {"role": "system", "content": system},
        {"role": "system", "content": json.dumps(context, ensure_ascii=False)},
        *payload.history,
        {"role": "user", "content": payload.message},
    ]
    try:
        raw = chat_completion(_model_config(), messages, json_mode=bool(payload.version_id))
        if not payload.version_id:
            return {"role": "assistant", "content": raw, "mode": "answer"}
        result = parse_json_object(raw)
    except AiConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    mode = result.get("mode") if result.get("mode") in {"answer", "edit", "clarify"} else "clarify"
    message = str(result.get("message") or "请再明确希望修改的内容。")
    with connection() as conn:
        conn.execute("""UPDATE job_session SET messages_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = (SELECT job_session_id FROM resume_version WHERE id = ?)""",
                     (json.dumps([*payload.history, {"role": "user", "content": payload.message}, {"role": "assistant", "content": message}], ensure_ascii=False), payload.version_id))
    if mode != "edit":
        return {"role": "assistant", "content": message, "mode": mode}
    previous, _ = _version_content(payload.version_id)
    prefs = _preferences()
    try:
        updated = apply_structure_mode(result.get("content"), previous, prefs["structure_mode"])
        updated = apply_date_order(updated, prefs["date_order"])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"AI修改结果无效：{exc}") from exc
    html = _render_version(updated)
    with connection() as conn:
        conn.execute("""UPDATE resume_version SET previous_content_json = content_json, content_json = ?, html = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                     (json.dumps(updated, ensure_ascii=False), html, payload.version_id))
    return {"role": "assistant", "content": message, "mode": "edit", "resume_content": updated, "can_undo": previous != updated}

@app.post("/api/generate")
def generate(payload: GenerateIn) -> dict:
    if not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="请先输入 JD。")
    resume = _master_resume()
    structured = resume.get("structured", {})
    prompt = {
        "master_content": {"header": structured.get("header", {}), "sections": structured.get("sections", [])},
        "master_source_text": resume.get("text", ""),
        "experience_library": _experience_text(),
        "preferences": _preferences(),
        "job_description": payload.jd_text,
        "conversation": payload.history,
        "max_total_chars": len(resume.get("text", "") or ""),
    }
    try:
        generated = parse_json_object(chat_completion(_model_config(), [
            {"role": "system", "content": GENERATE_SYSTEM},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ], json_mode=True))
        content = normalize_resume_content(generated.get("content"))
    except AiConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    review_notes: list[str] = []
    try:
        reviewed = parse_json_object(chat_completion(_model_config(), [
            {"role": "system", "content": REVIEW_SYSTEM},
            {"role": "user", "content": json.dumps({"sources": prompt, "draft": content}, ensure_ascii=False)},
        ], json_mode=True))
        content = normalize_resume_content(reviewed.get("content"))
        review_notes = [str(note) for note in reviewed.get("notes", []) if str(note).strip()]
    except (RuntimeError, ValueError):
        review_notes = ["自动复核未完成，已保留可用初稿。"]
    prefs = _preferences()
    content = apply_structure_mode(content, structured, prefs["structure_mode"])
    content = apply_date_order(content, prefs["date_order"])
    raw_analysis = generated.get("match_analysis") if isinstance(generated.get("match_analysis"), dict) else {}
    match_analysis = {key: _clip_sentence(str(raw_analysis.get(key) or "").strip(), 100) for key in ("actual_match", "resume_match", "changes", "gaps")}
    company = str(generated.get("company") or "目标公司").strip()
    role = str(generated.get("role") or "目标岗位").strip()
    person = content.get("header", {}).get("name") or "简历"
    display_name = safe_output_name(f"{person}-{company}-{role}-{date.today().isoformat()}")
    session_id = uuid.uuid4().hex
    version_id = uuid.uuid4().hex
    html = _render_version(content)
    with connection() as conn:
        conn.execute("""INSERT INTO job_session (id, jd_text, messages_json, company, role, display_name, analysis_json) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                     (session_id, payload.jd_text, json.dumps(payload.history, ensure_ascii=False), company, role, display_name, json.dumps(match_analysis, ensure_ascii=False)))
        content_json = json.dumps(content, ensure_ascii=False)
        conn.execute("""INSERT INTO resume_version (id, job_session_id, content_json, initial_content_json, html, display_name, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                     (version_id, session_id, content_json, content_json, html, display_name))
    return {"version_id": version_id, "session_id": session_id, "display_name": display_name, "content": content, "html": html, "review_notes": review_notes, "match_analysis": match_analysis}

@app.get("/api/versions/{version_id}")
def get_version(version_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT id, job_session_id, content_json, html, display_name, previous_content_json, pdf_path, created_at, updated_at FROM resume_version WHERE id = ?", (version_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="简历版本不存在。")
    return {"id": row["id"], "job_session_id": row["job_session_id"], "content": json.loads(row["content_json"]), "html": row["html"], "display_name": row["display_name"], "can_undo": bool(row["previous_content_json"]), "pdf_path": row["pdf_path"], "created_at": row["created_at"], "updated_at": row["updated_at"]}

@app.put("/api/versions/{version_id}")
def update_version(version_id: str, payload: VersionUpdateIn) -> dict:
    try:
        content = normalize_resume_content(payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    html = _render_version(content)
    with connection() as conn:
        cursor = conn.execute("""UPDATE resume_version SET previous_content_json = content_json, content_json = ?, html = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                              (json.dumps(content, ensure_ascii=False), html, version_id))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="简历版本不存在。")
    return {"version_id": version_id, "saved": True, "content": content, "html": html, "can_undo": True}

@app.post("/api/versions/{version_id}/undo")
def undo_version(version_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT content_json, previous_content_json FROM resume_version WHERE id = ?", (version_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="简历版本不存在。")
        if not row["previous_content_json"]:
            raise HTTPException(status_code=400, detail="没有可撤销的修改。")
        restored = normalize_resume_content(json.loads(row["previous_content_json"]))
        html = _render_version(restored)
        conn.execute("""UPDATE resume_version SET content_json = ?, previous_content_json = '', html = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                     (json.dumps(restored, ensure_ascii=False), html, version_id))
    return {"version_id": version_id, "content": restored, "html": html, "can_undo": False}

def _render_pdf_and_count(html: str, pdf_path: Path) -> int:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(pdf_path), format="A4", print_background=True)
        browser.close()
    import fitz
    with fitz.open(pdf_path) as document:
        return document.page_count


def _fit_template(content: dict[str, Any], template: dict[str, Any], assets: list[dict[str, Any]], target: int, pdf_path: Path) -> tuple[dict[str, Any], int]:
    """两遍式版式闭环：首遍渲染后若超页，按压缩阶梯逐步收紧行距/间距/字号，直到页数达标。"""
    steps = [
        {"line_height": round(max(1.15, float(template.get("line_height", 1.55)) - 0.12), 2), "section_margin": 0.6, "item_margin": 0.3, "para_margin": 0.18},
        {"line_height": round(max(1.05, float(template.get("line_height", 1.55)) - 0.24), 2), "section_margin": 0.3, "item_margin": 0.15, "para_margin": 0.08},
        {"line_height": round(max(1.0, float(template.get("line_height", 1.55)) - 0.35), 2), "section_margin": 0.1, "item_margin": 0.05, "para_margin": 0.03, "font_size": round(float(template.get("font_size", 10.5)) - 0.5, 2)},
    ]
    current = template
    page_count = _render_pdf_and_count(render_resume_html(content, current, assets), pdf_path)
    for over in steps:
        if page_count <= target:
            break
        candidate = {**current, **over}
        page_count = _render_pdf_and_count(render_resume_html(content, candidate, assets), pdf_path)
        current = candidate
    return current, page_count


@app.post("/api/versions/{version_id}/export")
def export_version(version_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT content_json, display_name FROM resume_version WHERE id = ?", (version_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="简历版本不存在。")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="尚未安装 Playwright，请按 README 安装 PDF 导出依赖。") from exc
    output_dir = DATA_DIR / "versions" / version_id
    output_dir.mkdir(parents=True, exist_ok=True)
    display_name = safe_output_name(row["display_name"] or "resume")
    pdf_path = output_dir / f"{display_name}.pdf"
    resume = _master_resume()
    content = json.loads(row["content_json"])
    assets = resume.get("assets", [])
    page_limit = _preferences()["page_limit"]
    target = 1 if page_limit == "one" else (2 if page_limit == "two" else 999)
    template = _template_config()
    try:
        if target < 999:
            fitted, page_count = _fit_template(content, template, assets, target, pdf_path)
            if page_count > target:
                template = {**template, **fitted}
                page_count = _render_pdf_and_count(render_resume_html(content, template, assets), pdf_path)
        else:
            page_count = _render_pdf_and_count(render_resume_html(content, template, assets), pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PDF 导出失败：{exc}") from exc
    html = render_resume_html(content, template, assets)
    with connection() as conn:
        conn.execute("UPDATE resume_version SET pdf_path = ?, html = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (str(pdf_path), html, version_id))
    return {"version_id": version_id, "pdf_path": str(pdf_path), "filename": f"{display_name}.pdf", "page_count": page_count}

@app.get("/api/versions/{version_id}/pdf")
def download_version_pdf(version_id: str):
    with connection() as conn:
        row = conn.execute("SELECT pdf_path FROM resume_version WHERE id = ?", (version_id,)).fetchone()
    if not row or not row["pdf_path"] or not Path(row["pdf_path"]).exists():
        raise HTTPException(status_code=404, detail="请先导出 PDF。")
    return FileResponse(row["pdf_path"], media_type="application/pdf", filename=Path(row["pdf_path"]).name)

@app.post("/api/import/resume")
async def import_resume(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名。")
    data = await file.read()
    try:
        parsed = parse_document(file.filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    parsed["structured"] = build_resume_ir(parsed)
    layout_profile = parsed.get("layout_profile", {})
    if layout_profile:
        template = _template_config()
        for key in ("font_size", "name_font_size", "section_font_size", "font_family", "margin_left", "margin_right", "margin_top", "margin_bottom", "photo_rect_pct"):
            if key in layout_profile:
                template[key] = layout_profile[key]
        with connection() as conn:
            conn.execute("UPDATE template SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (json.dumps(template, ensure_ascii=False),))
    uploads_dir = DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:12]}-{safe_filename(file.filename)}"
    stored_path = uploads_dir / stored_name
    stored_path.write_bytes(data)
    with connection() as conn:
        conn.execute(
            """INSERT INTO master_resume (id, original_filename, stored_path, file_type, parsed_json, updated_at)
               VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                 original_filename = excluded.original_filename,
                 stored_path = excluded.stored_path,
                 file_type = excluded.file_type,
                 parsed_json = excluded.parsed_json,
                 updated_at = CURRENT_TIMESTAMP""",
            (file.filename, str(stored_path), parsed["format"], to_json(parsed)),
        )
    return {
        "filename": file.filename,
        "format": parsed["format"],
        "stored": True,
        "parsed": parsed,
    }

@app.get("/api/resume/file")
def download_master_resume():
    with connection() as conn:
        row = conn.execute("SELECT original_filename, stored_path FROM master_resume WHERE id = 1").fetchone()
    if not row or not Path(row["stored_path"]).exists():
        raise HTTPException(status_code=404, detail="尚未上传主简历。")
    suffix = Path(row["stored_path"]).suffix.lower()
    media_type = "application/pdf" if suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(row["stored_path"], media_type=media_type, headers={"Content-Disposition": "inline"})

@app.get("/api/resume")
def get_resume() -> dict:
    with connection() as conn:
        row = conn.execute(
            "SELECT original_filename, stored_path, file_type, parsed_json, updated_at FROM master_resume WHERE id = 1"
        ).fetchone()
    if not row:
        return {"exists": False}
    return {
        "exists": True,
        "filename": row["original_filename"],
        "format": row["file_type"],
        "updated_at": row["updated_at"],
        "parsed": json.loads(row["parsed_json"]),
    }

@app.post("/api/import/experiences-text")
def import_experiences_text(payload: JdTextIn) -> dict:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="备用经历不能为空。")
    init_db()
    with connection() as conn:
        conn.execute("UPDATE experience_library SET original_filename = ?, content_text = ?, source_format = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", ("粘贴内容", text, "text"))
    return {"format": "text", "text": text, "character_count": len(text)}

@app.post("/api/import/experiences")
async def import_experiences(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名。")
    data = await file.read()
    suffix = Path(file.filename).suffix.lower()
    try:
        parsed = parse_text_file(file.filename, data) if suffix in {".txt", ".md"} else parse_document(file.filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    text = parsed.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="文件中没有可读取的文字。")
    with connection() as conn:
        conn.execute("UPDATE experience_library SET original_filename = ?, content_text = ?, source_format = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (file.filename, text, parsed.get("format", suffix.lstrip("."))))
    return {"filename": file.filename, "format": parsed.get("format"), "text": text, "character_count": len(text)}

@app.get("/api/experiences")
def get_experiences() -> dict:
    with connection() as conn:
        row = conn.execute("SELECT original_filename, content_text, source_format, updated_at FROM experience_library WHERE id = 1").fetchone()
    return {"exists": bool(row and row["content_text"]), "filename": row["original_filename"] if row else "", "text": row["content_text"] if row else "", "format": row["source_format"] if row else "text"}

@app.post("/api/import/jd-text")
def import_jd_text(payload: JdTextIn) -> dict:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="JD 文字不能为空。")
    return {"format": "text", "text": text, "character_count": len(text)}

@app.post("/api/import/jd")
async def import_jd(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名。")
    data = await file.read()
    try:
        parsed = parse_document(file.filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return {
        "filename": file.filename,
        "format": parsed["format"],
        "text": parsed["text"],
        "warnings": parsed.get("warnings", []),
        "character_count": len(parsed["text"]),
    }
