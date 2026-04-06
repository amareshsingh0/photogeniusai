from app.services.smart.design_agent_chain import (
    _agent_reconcile_outputs,
    _extract_explicit_texts,
)


def test_extract_explicit_texts_preserves_quoted_poster_copy() -> None:
    result = _extract_explicit_texts(
        "restaurant promotion poster with text 'GRAND OPENING' and 'Free Desser'"
    )

    assert result["explicit_headline"] == "GRAND OPENING"
    assert result["explicit_subheadline"] == "Free Desser"
    assert result["explicit_cta"] == ""


def test_reconcile_outputs_syncs_copy_prompt_and_layout() -> None:
    triage = {
        "explicit_headline": "GRAND OPENING",
        "explicit_subheadline": "Free Desser",
        "explicit_cta": "",
        "recommended_width": 1080,
        "recommended_height": 1350,
    }
    creative = {
        "palette": {
            "primary": "#FF0033",
            "text_primary": "#FFFFFF",
            "text_secondary": "#CCCCDD",
        }
    }
    copy = {
        "brand_name": "Cafe Nova",
        "headline": "WRONG HEADLINE",
        "subheadline": "",
        "body": "",
        "cta": "VISIT NOW",
        "cta_url": "",
        "tagline": "",
        "features": [],
    }
    img = {
        "background_prompt": 'hero dessert scene with "GRAND OPENING" signage in frame',
        "negative_prompt": "blurry, low quality",
        "parameters": {},
        "draft_variant": {"parameters": {}},
    }
    elements = [
        {
            "id": "headline",
            "type": "text",
            "bounds": {"x": 0.05, "y": 0.20, "w": 0.45, "h": 0.10},
            "style": {"font": "bebas_neue"},
            "content": "OLD",
            "locked": False,
        }
    ]

    result = _agent_reconcile_outputs(triage, creative, copy, img, elements, aspect_ratio=1080 / 1350)

    assert result["copy"]["headline"] == "GRAND OPENING"
    assert result["copy"]["subheadline"] == "Free Desser"
    assert "GRAND OPENING" not in result["image"]["background_prompt"]
    assert "upper third" in result["image"]["background_prompt"]
    assert result["image"]["parameters"]["aspect_ratio"] == "4:5"
    assert "text" in result["image"]["negative_prompt"]
    synced_headline = next(el for el in result["elements"] if el["id"] == "headline")
    assert synced_headline["content"] == "GRAND OPENING"
