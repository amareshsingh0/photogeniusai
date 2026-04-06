from app.services.smart.design_agent_chain import (
    _agent_reconcile_outputs,
    _build_design_room,
    _build_typography_direction,
    _extract_explicit_texts,
    _request_strategy,
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
        "industry": "fashion",
        "explicit_headline": "GRAND OPENING",
        "explicit_subheadline": "Free Desser",
        "explicit_cta": "",
        "recommended_width": 1080,
        "recommended_height": 1350,
        "original_prompt": "luxury fashion poster with text 'GRAND OPENING' and 'Free Desser'",
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
    assert "45-60%" in result["image"]["background_prompt"]
    assert result["image"]["parameters"]["aspect_ratio"] == "4:5"
    assert "text" in result["image"]["negative_prompt"]
    assert "distant model" in result["image"]["negative_prompt"]
    assert result["poster_design"]["font_style"] in ("elegant_serif", "luxury_display")
    synced_headline = next(el for el in result["elements"] if el["id"] == "headline")
    assert synced_headline["content"] == "GRAND OPENING"


def test_request_strategy_prefers_editorial_defaults_for_luxury_fashion() -> None:
    strategy = _request_strategy(
        {"industry": "fashion", "goal": "brand_awareness"},
        "luxury fashion poster for spring collection",
        {"tone": "luxury"},
    )

    assert strategy["font_style"] == "elegant_serif"
    assert strategy["layout_archetype"] == "hero_dominant"
    assert "45-60%" in strategy["image_guardrails"]


def test_build_design_room_ranks_backdrops_for_luxury_fashion() -> None:
    room = _build_design_room(
        {
            "industry": "fashion",
            "goal": "brand_awareness",
            "platform": "instagram_portrait",
            "original_prompt": "luxury fashion poster with text 'NEW COLLECTION' and 'Spring 2026'",
        },
        {"tone": "luxury", "brand_name": "Aura Solstice"},
        {"mood": "elegant", "visual_style": "editorial"},
        {
            "brand_name": "Aura Solstice",
            "headline": "NEW COLLECTION",
            "subheadline": "Spring 2026",
            "body": "Quiet editorial body copy",
            "cta": "DISCOVER",
            "tagline": "",
            "features": [],
        },
    )

    assert room["winner"]["id"] == "sculptural_studio"
    assert room["copy_space"] == "top"
    assert room["font_style"] == "elegant_serif"
    assert room["body_copy_policy"] == "minimal"
    assert [note["speaker"] for note in room["discussion"]] == [
        "creative_director",
        "copy_writer",
        "layout_planner",
    ]
    assert room["candidates"][0]["score_total"] >= room["candidates"][1]["score_total"]


def test_reconcile_outputs_prefers_design_room_consensus() -> None:
    triage = {
        "industry": "fashion",
        "goal": "brand_awareness",
        "recommended_width": 1080,
        "recommended_height": 1350,
        "original_prompt": "luxury fashion poster with text 'NEW COLLECTION' and 'Spring 2026'",
    }
    creative = {
        "palette": {
            "primary": "#B8860B",
            "text_primary": "#FFFFFF",
            "text_secondary": "#CCCCDD",
        }
    }
    copy = {
        "brand_name": "Aura Solstice",
        "headline": "NEW COLLECTION",
        "subheadline": "Spring 2026",
        "body": "Witness a quiet metamorphosis.",
        "cta": "DISCOVER",
        "cta_url": "",
        "tagline": "",
        "features": [],
    }
    img = {
        "background_prompt": "fashion hero portrait with atmospheric architecture",
        "negative_prompt": "blurry, low quality",
        "parameters": {},
        "draft_variant": {"parameters": {}},
    }
    design_room = {
        "copy_space": "right",
        "font_style": "elegant_serif",
        "body_copy_policy": "minimal",
        "winner": {
            "id": "sculptural_studio",
            "direction": "Use a refined editorial studio with sculptural shadow planes.",
        },
    }

    result = _agent_reconcile_outputs(
        triage,
        creative,
        copy,
        img,
        [],
        aspect_ratio=1080 / 1350,
        design_room=design_room,
    )

    assert result["copy"]["body"] == ""
    assert "right side" in result["image"]["background_prompt"]
    assert result["poster_design"]["font_style"] == "elegant_serif"
    assert "taste_winner:sculptural_studio" in result["notes"]


def test_build_typography_direction_for_event_prefers_display_treatment() -> None:
    direction = _build_typography_direction(
        {
            "industry": "general",
            "goal": "event",
            "original_prompt": "music festival poster with text 'BEAT FEST 2026' and 'March 15'",
        },
        {"font_style": "bold_tech", "tone": "energetic"},
        {"mood": "energetic"},
        {
            "headline": "BEAT FEST 2026",
            "subheadline": "March 15",
            "body": "Feel the pulse of the city.",
            "cta": "CLAIM YOUR RUSH",
        },
        {"copy_space": "top", "font_style": "bold_tech", "body_copy_policy": "supporting"},
    )

    assert direction["headline_font"] == "anton"
    assert direction["headline_effect"] == "glow"
    assert direction["cta_font"] == "anton"
    assert "\n" in direction["headline_wrap_hint"] or len(direction["headline_wrap_hint"]) <= 12
