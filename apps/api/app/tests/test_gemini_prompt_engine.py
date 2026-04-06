import asyncio

from app.services.smart.gemini_prompt_engine import GeminiPromptEngine


def test_build_params_uses_design_chain_output_for_typography() -> None:
    engine = GeminiPromptEngine()
    brief = {
        "background_prompt": "Moody luxury product scene with deep shadows.",
        "negative_prompt": "text, words, letters, watermark",
        "_img_parameters": {"steps": 24, "guidance": 3.2},
        "_model_preference": "flux_pro",
        "_img_translation_notes": "Used the image prompter output directly.",
        "_img_recommendation": "Design chain already chose the model.",
        "_img_draft_variant": {"model": "flux_schnell", "prompt": "draft"},
        "mood": "luxury",
    }

    result = asyncio.run(engine.build_params(brief, "Flux 2 Pro", "typography"))

    assert result["prompt"] == brief["background_prompt"]
    assert result["negative_prompt"] == brief["negative_prompt"]
    assert result["recommended_model"] == "flux_2_pro"
    assert result["parameters"] == {"steps": 24, "guidance": 3.2}
    assert result["draft_variant"] == brief["_img_draft_variant"]
    assert result["_source"] == "design_chain"
