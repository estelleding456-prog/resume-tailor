import pytest

from .resume_content import apply_date_order, apply_structure_mode, normalize_resume_content, resume_to_text, safe_output_name
from .main import _clip_sentence


def test_normalize_resume_content_keeps_supported_structure():
    content = normalize_resume_content({
        "header": {"name": " 张三 ", "contact": "mail@example.com"},
        "sections": [{
            "title": "实习经历",
            "paragraphs": [],
            "items": [{"date": "2026.05—至今", "heading": "公司", "subheading": "法务", "body": [" 合同审查 "]}],
        }],
    })
    assert content["header"]["name"] == "张三"
    assert content["sections"][0]["items"][0]["body"] == ["合同审查"]
    assert "实习经历" in resume_to_text(content)


def test_normalize_resume_content_rejects_non_object():
    with pytest.raises(ValueError):
        normalize_resume_content([])


def test_safe_output_name_removes_windows_invalid_characters():
    assert safe_output_name("张三/公司:岗位") == "张三-公司-岗位"


def test_date_order_is_deterministic_and_markdown_labels_are_normalized():
    content = normalize_resume_content({"header": {}, "sections": [{"title": "实习经历", "paragraphs": [], "items": [
        {"date": "2025.04 - 2025.08", "heading": "B", "subheading": "", "body": ["**尽职调查**：内容"]},
        {"date": "2026.05 - 至今", "heading": "A", "subheading": "", "body": []},
    ]}]})
    ordered = apply_date_order(content, "desc")
    assert [item["heading"] for item in ordered["sections"][0]["items"]] == ["A", "B"]
    assert ordered["sections"][0]["items"][1]["body"][0] == "尽职调查：内容"


def test_preserve_structure_keeps_new_sections_and_baseline_order():
    baseline = {"header": {}, "sections": [{"title": "教育经历", "paragraphs": [], "items": []}, {"title": "实习经历", "paragraphs": [], "items": []}]}
    generated = {"header": {}, "sections": [{"title": "实习经历", "paragraphs": ["x"], "items": []}, {"title": "教育背景", "paragraphs": ["y"], "items": []}, {"title": "新增板块", "paragraphs": [], "items": []}]}
    result = apply_structure_mode(generated, baseline, "preserve")
    assert [section["title"] for section in result["sections"]] == ["教育背景", "实习经历", "新增板块"]


def test_reorder_keeps_new_sections_not_dropped():
    baseline = {"header": {}, "sections": [{"title": "教育经历", "paragraphs": [], "items": []}, {"title": "相关技能", "paragraphs": [], "items": []}]}
    generated = {"header": {}, "sections": [{"title": "教育经历", "paragraphs": [], "items": []}, {"title": "AI与法律工作流", "paragraphs": ["搭建Agent技能库"], "items": []}, {"title": "相关技能", "paragraphs": [], "items": []}]}
    result = apply_structure_mode(generated, baseline, "reorder")
    titles = [section["title"] for section in result["sections"]]
    assert "AI与法律工作流" in titles  # 新增板块必须保留，不得静默丢弃
    assert any("Agent技能库" in p for s in result["sections"] for p in s["paragraphs"])


def test_clip_sentence_breaks_at_sentence_boundary_not_mid_word():
    long_text = "真实材料显示候选人具备科技公司法务、律所金融资管与知产诉讼等多元实习，且有AI技能库搭建与工作流自动化实践，与JD要求的高度契合。"
    clipped = _clip_sentence(long_text, 40)
    assert len(clipped) <= 40
    assert clipped.endswith("。") or clipped.endswith("，") or clipped.endswith("、")
    assert "高度契合" not in clipped  # 不应硬截断到单词中间
