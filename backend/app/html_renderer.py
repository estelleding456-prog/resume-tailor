from __future__ import annotations

from html import escape
import re
from typing import Any

DEFAULT_TEMPLATE = {"font_size": 10.5, "name_font_size": 18, "section_font_size": 12, "font_family": "Microsoft YaHei", "line_height": 1.55, "margin_top": 14, "margin_right": 16, "margin_bottom": 14, "margin_left": 16, "section_margin": 1.0, "item_margin": 0.55, "para_margin": 0.35, "photo_width_mm": 22, "photo_height_mm": 29}


def _rich_line(value: Any) -> str:
    text = re.sub(r"^\*\*([^*]+)\*\*([：:])", r"\1\2", str(value or "").strip())
    match = re.match(r"^([^：:]{2,10})([：:])(.*)$", text)
    if not match:
        return escape(text)
    return f"<strong>{escape(match.group(1) + match.group(2))}</strong>{escape(match.group(3))}"


def _render_para(value: Any) -> str:
    """渲染一个正文段落。短且无标点结尾的独立行视为小标题并加粗；其余按“标签：正文”加粗标签。"""
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 16 and "：" not in text and ":" not in text and not re.search(r"[。；！？，、]", text):
        return f"<p class='subhead'><strong>{escape(text)}</strong></p>"
    return f"<p>{_rich_line(text)}</p>"


def render_resume_html(content: dict[str, Any], template: dict[str, Any] | None = None, assets: list[dict[str, Any]] | None = None) -> str:
    template = {**DEFAULT_TEMPLATE, **(template or {})}
    header = content.get("header", {})
    sections = content.get("sections", [])
    assets = assets or []
    pw, ph = template.get("photo_width_mm", 22), template.get("photo_height_mm", 29)
    photo_html = f"<img class='resume-photo' style='width:{pw}mm;height:{ph}mm' src='{escape(str(assets[0].get('data_url', '')))}' alt='简历照片'>" if assets and assets[0].get("data_url") else ""
    section_html: list[str] = []
    for section in sections:
        chunks = [f"<section class='resume-section'><h3>{escape(str(section.get('title', '')))}</h3>"]
        for paragraph in section.get("paragraphs", []):
            chunks.append(_render_para(paragraph))
        for item in section.get("items", []):
            chunks.append("<div class='resume-item'>")
            date = str(item.get("date", "")).strip()
            heading = str(item.get("heading", "")).strip()
            subheading = str(item.get("subheading", "")).strip()
            body = item.get("body", [])
            if heading and not subheading and not date and body:
                # 子标题 + 正文（如 AI 模块），小标题加粗、无日期
                chunks.append(f"<p class='subhead'><strong>{escape(heading)}</strong></p>")
                for line in body:
                    chunks.append(_render_para(line))
            elif heading and not subheading and date:
                # 日期 + 文本 紧凑行（在校经历）
                chunks.append(f"<div class='resume-item-head compact'><strong>{escape(date)}</strong><span>{escape(heading)}</span></div>")
                for line in body:
                    chunks.append(_render_para(line))
            else:
                chunks.append(f"<div class='resume-item-head'><strong>{escape(date)}</strong><strong>{escape(heading)}</strong><strong>{escape(subheading)}</strong></div>")
                for line in body:
                    chunks.append(_render_para(line))
            chunks.append("</div>")
        chunks.append("</section>")
        section_html.append("".join(chunks))
    font_size = template["font_size"]
    name_font_size = template.get("name_font_size", 18)
    section_font_size = template.get("section_font_size", 12)
    font_family = str(template.get("font_family", "Microsoft YaHei")).replace("MicrosoftYaHei", "Microsoft YaHei")
    line_height = template["line_height"]
    mt, mr, mb, ml = (template[key] for key in ("margin_top", "margin_right", "margin_bottom", "margin_left"))
    sm, im, pm = (template[key] for key in ("section_margin", "item_margin", "para_margin"))
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>简历</title><style>
@page {{ size: A4; margin: 0; }} * {{ box-sizing: border-box; }} body {{ margin: 0; background: #e9e9e6; color: #171717; font-family: Arial, 'Microsoft YaHei', sans-serif; }}
.resume-paper {{ position: relative; width: 210mm; min-height: 297mm; margin: 0 auto; padding: {mt}mm {mr}mm {mb}mm {ml}mm; background: #fff; font-family: '{font_family}', Arial, sans-serif; font-size: {font_size}pt; line-height: {line_height}; letter-spacing: -0.08pt; }}
.resume-header {{ display: flex; align-items: center; justify-content: center; margin-bottom: 1mm; }} .resume-header .resume-text {{ flex: 1; text-align: center; }} .resume-header h2 {{ margin: 0 0 1mm; font-size: {name_font_size}pt; letter-spacing: .08em; }} .resume-header p {{ margin: 0; color: #555; }} .resume-photo {{ object-fit: cover; margin-left: 3mm; flex: 0 0 auto; border-radius: 1mm; }}
.resume-section {{ margin-top: {sm}mm; }} .resume-header + .resume-section {{ margin-top: 0; }} .resume-section h3 {{ margin: 0 0 .7mm; padding-bottom: .4mm; border-bottom: 1.5px solid #222; font-size: {section_font_size}pt; }} .resume-section p {{ margin: {pm}mm 0; text-wrap: pretty; }} .resume-section p.subhead {{ margin: 1mm 0 .2mm; font-weight: 700; }} .resume-item {{ margin: {im}mm 0; }} .resume-item-head {{ display: grid; grid-template-columns: 27% 46% 27%; gap: 1mm; }} .resume-item-head strong:nth-child(2) {{ text-align: center; }} .resume-item-head strong:nth-child(3) {{ text-align: right; }} .resume-item-head.compact {{ display: flex; align-items: baseline; gap: 2mm; }} .resume-item-head.compact strong {{ white-space: nowrap; flex: 0 0 auto; }} .resume-item-head.compact span {{ text-align: left; }}
</style></head><body><article class='resume-paper'><header class='resume-header'><div class='resume-text'><h2>{escape(str(header.get('name', '')))}</h2><p>{escape(str(header.get('contact', '')))}</p></div>{photo_html}</header>{''.join(section_html)}</article></body></html>"""
