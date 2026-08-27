from __future__ import annotations

import re
from typing import Any


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"^\*\*([^*]+)\*\*([：:])", r"\1\2", text)


def _start_date(value: str) -> tuple[int, int]:
    match = re.search(r"(\d{4})[./-](\d{1,2})", value)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def classify_section_type(section: dict[str, Any]) -> str:
    """根据条目结构确定性判断板块类型。
    - experience: 有条目且带日期+副标题（如实习经历 日期|单位|岗位）
    - compact: 有条目带日期但无副标题（如在校经历 日期+文本）
    - labeled_list: 无日期条目或纯段落（如技能/AI工作流模块）
    """
    items = section.get("items", [])
    if not items:
        return "labeled_list"
    has_date = any(str(it.get("date", "")).strip() for it in items)
    has_sub = any(str(it.get("subheading", "")).strip() for it in items)
    if has_date and has_sub:
        return "experience"
    if has_date:
        return "compact"
    return "labeled_list"


def normalize_resume_content(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("简历内容必须是对象。")
    raw_header = value.get("header") if isinstance(value.get("header"), dict) else {}
    header = {"name": _text(raw_header.get("name")), "contact": _text(raw_header.get("contact"))}
    sections: list[dict[str, Any]] = []
    for raw_section in value.get("sections", []):
        if not isinstance(raw_section, dict):
            continue
        paragraphs = [_text(item) for item in raw_section.get("paragraphs", []) if _text(item)]
        items: list[dict[str, Any]] = []
        for raw_item in raw_section.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            items.append({
                "date": _text(raw_item.get("date")),
                "heading": _text(raw_item.get("heading")),
                "subheading": _text(raw_item.get("subheading")),
                "body": [_text(line) for line in raw_item.get("body", []) if _text(line)],
            })
        title = _text(raw_section.get("title"))
        if title or paragraphs or items:
            sec = {"title": title or "其他信息", "paragraphs": paragraphs, "items": items}
            sec["section_type"] = classify_section_type(sec)
            sec["style_ref"] = _text(raw_section.get("style_ref"))
            sections.append(sec)
    return {"header": header, "sections": sections}


def _section_key(title: str) -> str:
    for key in ("教育", "实习", "工作", "项目", "在校", "技能"):
        if key in title:
            return key
    return title.strip()


def apply_structure_mode(content: dict[str, Any], baseline: dict[str, Any], mode: str) -> dict[str, Any]:
    """结构模式控制板块的排序与是否补回基线，但绝不静默丢弃内容。
    - rebuild: 完全信任模型返回的板块（允许增删、合并、移动）。
    - preserve: 保持基线顺序，新增板块追加到末尾；不删除基线板块。
    - reorder: 保持模型顺序，新增板块保留，被删除的基线板块补回（只允许移动与新增，不允许删基线）。
    """
    normalized = normalize_resume_content(content)
    if mode == "rebuild":
        return normalized
    base = normalize_resume_content(baseline)
    base_keys = [_section_key(section["title"]) for section in base["sections"]]
    base_by_key = {_section_key(section["title"]): section for section in base["sections"]}
    gen_by_key = {_section_key(section["title"]): section for section in normalized["sections"]}
    new_sections = [section for section in normalized["sections"] if _section_key(section["title"]) not in base_by_key]
    missing_base = [base_by_key[key] for key in base_keys if key not in gen_by_key]
    if mode == "preserve":
        ordered = [gen_by_key[key] if key in gen_by_key else base_by_key[key] for key in base_keys]
        ordered += new_sections
        normalized["sections"] = ordered
    else:
        normalized["sections"] = [section for section in normalized["sections"]] + missing_base
    return normalized


def structure_conflict_notes(content: dict[str, Any], baseline: dict[str, Any], mode: str) -> list[str]:
    if mode == "rebuild":
        return []
    base_keys = {_section_key(section["title"]) for section in normalize_resume_content(baseline)["sections"]}
    gen_keys = {_section_key(section["title"]) for section in normalize_resume_content(content)["sections"]}
    notes: list[str] = []
    added = gen_keys - base_keys
    removed = base_keys - gen_keys
    if added:
        notes.append(f"本次在“{mode}”偏好下新增了板块，已按你的明确要求保留。")
    if removed:
        notes.append(f"本次在“{mode}”偏好下未包含原板块，已保留。")
    return notes


def apply_date_order(content: dict[str, Any], order: str = "desc") -> dict[str, Any]:
    normalized = normalize_resume_content(content)
    if order not in {"asc", "desc"}:
        return normalized
    reverse = order == "desc"
    for section in normalized["sections"]:
        dated = [item for item in section["items"] if _start_date(item["date"]) != (0, 0)]
        if len(dated) >= 2:
            undated = [item for item in section["items"] if _start_date(item["date"]) == (0, 0)]
            section["items"] = sorted(dated, key=lambda item: _start_date(item["date"]), reverse=reverse) + undated
    return normalized


def resume_to_text(content: dict[str, Any]) -> str:
    normalized = normalize_resume_content(content)
    lines = [normalized["header"]["name"], normalized["header"]["contact"]]
    for section in normalized["sections"]:
        lines.append(section["title"])
        lines.extend(section["paragraphs"])
        for item in section["items"]:
            lines.extend([item["date"], item["heading"], item["subheading"], *item["body"]])
    return "\n".join(line for line in lines if line)


def safe_output_name(name: str, fallback: str = "resume") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", _text(name))
    cleaned = re.sub(r"\s+", "-", cleaned).strip(" .-")
    return cleaned[:100] or fallback
