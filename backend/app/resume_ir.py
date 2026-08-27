from __future__ import annotations

import re
from typing import Any

SECTION_TITLES = {"教育经历", "教育背景", "实习经历", "在校经历", "相关技能", "专业技能", "技能及其他", "项目经历", "工作经历"}
DATE_RE = re.compile(r"^\d{4}\.\d{2}\s*(?:-|—|至|到)\s*(?:\d{4}\.\d{2}|至今|现在)")
LABEL_RE = re.compile(r"^[A-Za-z0-9\u4e00-\u9fff /&]{2,10}[：:]")


def _header(lines: list[str]) -> tuple[dict[str, str], int]:
    contact_index = next((i for i, line in enumerate(lines[:5]) if "@" in line or re.search(r"1\d{10}", line)), 1 if len(lines) > 1 else 0)
    name_index = next((i for i, line in enumerate(lines[:5]) if i != contact_index and 2 <= len(line.replace(" ", "")) <= 6), 0)
    return {"name": lines[name_index].strip(), "contact": lines[contact_index].strip()}, max(name_index, contact_index) + 1


def _split_entry_head(line: str) -> tuple[str, str, str]:
    columns = [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]
    if len(columns) >= 3:
        return columns[0], columns[1], " ".join(columns[2:])
    match = DATE_RE.match(line.strip())
    date = match.group(0).strip() if match else line.strip()
    remainder = line.strip()[len(match.group(0)):].strip() if match else ""
    return date, remainder, ""


def _merge_body(lines: list[str]) -> list[str]:
    body: list[str] = []
    for line in lines:
        if not body or LABEL_RE.match(line):
            body.append(line)
        else:
            body[-1] += line
    return body


def build_resume_ir(parsed: dict[str, Any]) -> dict[str, Any]:
    lines = [line.strip() for line in parsed.get("text", "").splitlines() if line.strip()]
    if not lines:
        return {"header": {}, "sections": [], "warnings": ["没有提取到文字。"]}

    header, i = _header(lines)
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    while i < len(lines):
        line = lines[i]
        if line in SECTION_TITLES:
            current = {"title": line, "items": [], "paragraphs": []}
            sections.append(current)
            i += 1
            continue
        if current is None:
            current = {"title": "其他信息", "items": [], "paragraphs": []}
            sections.append(current)
        if DATE_RE.match(line):
            date, heading, subheading = _split_entry_head(line)
            i += 1
            item_lines: list[str] = []
            while i < len(lines) and not DATE_RE.match(lines[i]) and lines[i] not in SECTION_TITLES:
                item_lines.append(lines[i])
                i += 1
            current["items"].append({"date": date, "heading": heading, "subheading": subheading, "body": _merge_body(item_lines)})
        else:
            if current["paragraphs"] and not LABEL_RE.match(line):
                current["paragraphs"][-1] += line
            else:
                current["paragraphs"].append(line)
            i += 1
    return {
        "header": header,
        "sections": sections,
        "source_format": parsed.get("format"),
        "page_count": parsed.get("page_count"),
        "layout_profile": parsed.get("layout_profile", {}),
        "warnings": parsed.get("warnings", []),
    }
