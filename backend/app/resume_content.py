from __future__ import annotations

import re
from typing import Any


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"^\*\*([^*]+)\*\*([：:])", r"\1\2", text)


def _start_date(value: str) -> tuple[int, int]:
    match = re.search(r"(\d{4})[./-](\d{1,2})", value)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


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
            sections.append({"title": title or "其他信息", "paragraphs": paragraphs, "items": items})
    return {"header": header, "sections": sections}


def _section_key(title: str) -> str:
    for key in ("教育", "实习", "工作", "项目", "在校", "技能"):
        if key in title:
            return key
    return title.strip()


def apply_structure_mode(content: dict[str, Any], baseline: dict[str, Any], mode: str) -> dict[str, Any]:
    normalized = normalize_resume_content(content)
    if mode == "rebuild":
        return normalized
    base = normalize_resume_content(baseline)
    allowed = [_section_key(section["title"]) for section in base["sections"]]
    generated = {_section_key(section["title"]): section for section in normalized["sections"]}
    if mode == "preserve":
        normalized["sections"] = [generated.get(key, base["sections"][index]) for index, key in enumerate(allowed)]
    else:
        kept = [section for section in normalized["sections"] if _section_key(section["title"]) in allowed]
        present = {_section_key(section["title"]) for section in kept}
        normalized["sections"] = kept + [section for section in base["sections"] if _section_key(section["title"]) not in present]
    return normalized


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
