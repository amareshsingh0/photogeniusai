"""
Smart Generation API - v2 endpoint with AI-powered automation

User Controls:
- Prompt (required)
- Quality (FAST, STANDARD, PREMIUM)
- Dimensions (preset or custom)

AI Decides:
- Mode detection (REALISM, CINEMATIC, etc.)
- Category detection (portrait, landscape, etc.)
- Prompt enhancement
- Technical settings optimization
"""

import logging
from typing import Dict, Optional, Union
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, Field, validator

from app.services.smart import (
    mode_detector,
    category_detector,
    prompt_enhancer,
    generation_router,
    intent_analyzer,
    creative_graph,
    poster_jury,
    ctr_predictor,
    brand_checker,
    variant_generator,
)
from app.core.security import get_current_user
from app.services.smart.text_overlay import text_overlay, TEXT_NEGATIVE_PROMPT
from app.services.smart.creative_director import creative_director
from app.services.smart.design_effects import design_effects

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v2-generation"])


# ==================== Request Models ====================

class DimensionPreset(BaseModel):
    """Preset dimension configuration"""
    preset: str = Field(..., description="Preset name: square, portrait, landscape, story, banner, poster")


class CustomDimensions(BaseModel):
    """Custom dimension configuration"""
    width: int = Field(..., ge=512, le=2048, description="Image width (512-2048px, multiple of 8)")
    height: int = Field(..., ge=512, le=2048, description="Image height (512-2048px, multiple of 8)")

    @validator('width', 'height')
    def must_be_multiple_of_8(cls, v):
        """Ensure dimensions are multiples of 8 (SDXL requirement)"""
        if v % 8 != 0:
            return (v // 8) * 8
        return v


class GenerateRequest(BaseModel):
    """Smart generation request"""
    prompt: str = Field(..., min_length=1, max_length=2000, description="What you want to create")
    quality: str = Field('STANDARD', description="Quality tier: FAST, STANDARD, or PREMIUM")
    dimensions: Union[DimensionPreset, CustomDimensions] = Field(
        default=DimensionPreset(preset='square'),
        description="Image dimensions - preset or custom"
    )
    user_id: Optional[str] = Field(None, description="User ID for tracking")

    @validator('quality')
    def validate_quality(cls, v):
        """Validate quality tier"""
        v = v.upper()
        if v not in ['FAST', 'STANDARD', 'PREMIUM']:
            raise ValueError('Quality must be FAST, STANDARD, or PREMIUM')
        return v


# ==================== Response Models ====================

class AIAnalysis(BaseModel):
    """AI detection and enhancement details"""
    detected_mode: str
    detected_category: str
    original_prompt: str
    enhanced_prompt: str
    negative_prompt: str
    mode_confidence: float
    category_confidence: float
    matched_mode_keywords: list
    matched_category_keywords: list


class GenerationMetadata(BaseModel):
    """Generation metadata"""
    quality_tier: str
    backend: str
    dimensions: str
    generation_time: float
    model_used: Optional[str] = None


class GenerateResponse(BaseModel):
    """Smart generation response"""
    success: bool
    image_url: Optional[str]
    preview_url: Optional[str] = None
    ai_analysis: AIAnalysis
    metadata: GenerationMetadata
    error: Optional[str] = None


# ==================== Dimension Presets ====================

DIMENSION_PRESETS = {
    'square': {'width': 1024, 'height': 1024},        # 1:1
    'portrait': {'width': 768, 'height': 1024},       # 3:4
    'landscape': {'width': 1920, 'height': 1080},     # 16:9
    'story': {'width': 1080, 'height': 1920},         # 9:16
    'banner': {'width': 1920, 'height': 512},         # 15:4
    'poster': {'width': 768, 'height': 1366},         # 9:16 poster
    'wide': {'width': 1920, 'height': 1080},          # 16:9
}


# ==================== Helper Functions ====================

def get_dimensions(dimensions: Union[DimensionPreset, CustomDimensions]) -> tuple:
    """
    Get width and height from dimensions config

    Args:
        dimensions: Preset or custom dimensions

    Returns:
        tuple: (width, height)
    """
    if isinstance(dimensions, DimensionPreset):
        if dimensions.preset not in DIMENSION_PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preset: {dimensions.preset}. Valid presets: {list(DIMENSION_PRESETS.keys())}"
            )
        dims = DIMENSION_PRESETS[dimensions.preset]
        return dims['width'], dims['height']
    else:
        return dimensions.width, dimensions.height


# ==================== API Endpoint ====================

@router.post("/generate", response_model=GenerateResponse)
async def smart_generate(
    request: GenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    Smart Generation Endpoint

    **User provides:**
    - Prompt (what to create)
    - Quality (FAST/STANDARD/PREMIUM)
    - Dimensions (preset or custom)

    **AI decides:**
    - Mode (REALISM, CINEMATIC, CREATIVE, FANTASY, ANIME)
    - Category (portrait, landscape, product, etc.)
    - Prompt enhancement (quality keywords)
    - Technical settings (steps, guidance, etc.)

    **Example Request:**
    ```json
    {
      "prompt": "professional headshot of businessman",
      "quality": "STANDARD",
      "dimensions": {"preset": "portrait"}
    }
    ```

    **Example Response:**
    ```json
    {
      "success": true,
      "image_url": "https://...",
      "ai_analysis": {
        "detected_mode": "REALISM",
        "detected_category": "portrait",
        "enhanced_prompt": "professional headshot...",
        "mode_confidence": 0.85
      },
      "metadata": {
        "quality_tier": "STANDARD",
        "backend": "Lambda",
        "generation_time": 24.5
      }
    }
    ```
    """
    try:
        logger.info(f"Smart generation request: quality={request.quality}, prompt={request.prompt[:50]}...")

        # Get dimensions early (needed by intent analyzer)
        width, height = get_dimensions(request.dimensions)

        # ══════════════════════════════════════════════════════════════════
        # CREATIVE OS PIPELINE
        # ══════════════════════════════════════════════════════════════════

        # ── STAGE -1: Intent & Platform Analyzer ──────────────────────────
        intent = intent_analyzer.analyze(request.prompt, width, height)

        # ── STAGE 0: Text overlay detection ───────────────────────────────
        text_info = text_overlay.detect(request.prompt)
        generation_prompt = text_info["cleaned_prompt"] if text_info["has_text"] else request.prompt

        # ── STAGE 0.5: Creative Director ──────────────────────────────────
        creative_brief = creative_director.direct(generation_prompt)
        logger.info(f"Creative brief: theme={creative_brief['theme']}, objects={creative_brief['objects'][:3]}")

        # ── STAGE 1: Creative Graph — node-based layout ───────────────────
        graph = creative_graph.build(
            creative_type=intent["creative_type"],
            is_ad=intent["is_ad"],
            text_heavy=intent["text_heavy"],
            has_text_overlay=text_info["has_text"],
            aspect_ratio=width / max(height, 1),
            cta_strength=intent["cta_strength"],
            goal=intent["goal"],
        )

        # ── STAGE 1.5a: Variant Generator ───────────────────────────────
        variant_set = None
        if intent["is_ad"] or intent["creative_type"] in ("ad", "poster", "banner"):
            try:
                variant_set = variant_generator.generate(
                    creative_type=intent["creative_type"],
                    is_ad=intent["is_ad"],
                    template=graph.get("template", "poster_standard"),
                    style="poster",
                    goal=intent["goal"],
                    aspect_ratio=width / max(height, 1),
                    theme_label="",
                )
            except Exception as e:
                logger.warning("Variant generation failed (%s), skipping", e)

        # ── STAGE 1.5b: Mode & category detection ────────────────────────
        detected_mode = mode_detector.detect_mode(generation_prompt)
        detected_category = category_detector.detect_category(request.prompt)
        logger.info(f"AI detected: mode={detected_mode}, category={detected_category}")

        mode_explanation = mode_detector.explain_detection(request.prompt)
        category_explanation = category_detector.explain_detection(request.prompt)

        # ── STAGE 2: AI enhances prompt ───────────────────────────────────
        enhancement = prompt_enhancer.enhance(
            user_prompt=generation_prompt,
            mode=detected_mode,
            category=detected_category,
            quality=request.quality
        )

        # Inject Creative Director's concept
        if creative_brief["concept_prompt"]:
            enhancement['enhanced'] = f"{enhancement['enhanced']}, {creative_brief['concept_prompt']}"

        # Inject intent-based hints
        for hint_val in intent["prompt_hints"].values():
            if hint_val:
                enhancement['enhanced'] = f"{enhancement['enhanced']}, {hint_val}"

        # Text artifact negatives
        if text_info["has_text"]:
            enhancement['negative'] += ", " + TEXT_NEGATIVE_PROMPT

        logger.info(f"Enhanced prompt: {enhancement['enhanced'][:100]}...")
        logger.info(f"Dimensions: {width}x{height}")

        # ── STAGE 3: Smart Router (fal.ai + Gemini prompt engine) ─────────
        from app.services.smart.generation_router import smart_router
        tier_map = {'FAST': 'fast', 'STANDARD': 'standard', 'PREMIUM': 'premium'}
        gen = await smart_router.generate(
            prompt=request.prompt,
            tier=tier_map.get(request.quality, 'standard'),
            style=detected_mode,
            creative_type=intent['creative_type'],
            width=width,
            height=height,
        )
        if not gen['success']:
            raise HTTPException(503, f"Generation service unavailable: {gen.get('metadata', {}).get('error', 'fal.ai error')}")
        result = {
            'image_url': gen['image_url'],
            'success': gen['success'],
            'backend': gen['backend'],
            'generation_time': gen['generation_time'],
            'metadata': {'model': gen['model_used']},
        }
        # Use Gemini-enhanced prompt for downstream stages
        enhancement['enhanced'] = gen['enhanced_prompt']

        # ── STAGE 4: Text overlay ─────────────────────────────────────────
        final_image_url = result.get('image_url')
        if text_info["has_text"] and final_image_url:
            try:
                _mode_to_style = {
                    "REALISM": "photo", "CINEMATIC": "cinematic",
                    "CREATIVE": "poster", "FANTASY": "poster",
                    "ANIME": "poster", "ART": "editorial",
                    "FASHION": "editorial",
                }
                overlay_style = _mode_to_style.get(detected_mode, "poster")
                final_image_url = text_overlay.apply_to_data_url(
                    final_image_url, text_info["texts"], style=overlay_style
                )
                logger.info("Text overlay applied: %s", [t["text"] for t in text_info["texts"]])
            except Exception as e:
                logger.warning("Text overlay failed (%s), returning image without text", e)

        # ── STAGE 4b: Design effects ──────────────────────────────────────
        if final_image_url:
            try:
                _mode_to_style_fx = {
                    "REALISM": "photo", "CINEMATIC": "cinematic",
                    "CREATIVE": "poster", "FANTASY": "poster",
                    "ANIME": "social", "ART": "editorial",
                    "FASHION": "editorial",
                }
                fx_style = _mode_to_style_fx.get(detected_mode, "photo")
                final_image_url = design_effects.apply_to_data_url(
                    final_image_url, style=fx_style
                )
                logger.info("Design effects applied: style=%s", fx_style)
            except Exception as e:
                logger.warning("Design effects failed (%s), returning without effects", e)

        # ── STAGE 5a: Brand Checker ───────────────────────────────────────
        brand_verdict = None
        if intent["is_ad"] or text_info["has_text"]:
            try:
                brand_verdict = brand_checker.check(
                    image_b64=final_image_url if final_image_url and final_image_url.startswith("data:") else None,
                    prompt=request.prompt,
                    has_text=text_info["has_text"],
                    creative_tone=intent.get("audience_tone", ""),
                )
            except Exception as e:
                logger.warning("Brand checker failed (%s), skipping", e)

        # ── STAGE 5b: Poster Jury v2 ─────────────────────────────────────
        jury_verdict = None
        if intent["is_ad"] or text_info["has_text"]:
            try:
                jury_verdict = poster_jury.evaluate(
                    image_b64=final_image_url if final_image_url and final_image_url.startswith("data:") else None,
                    visual_balance=graph["visual_balance"],
                    total_text_area=graph["total_text_area"],
                    has_text=text_info["has_text"],
                    is_ad=intent["is_ad"],
                    brand_verdict=brand_verdict,
                )
            except Exception as e:
                logger.warning("Poster jury failed (%s), skipping", e)

        # ── STAGE 6: CTR Predictor ────────────────────────────────────────
        ctr_prediction = None
        if intent["is_ad"]:
            try:
                ctr_prediction = ctr_predictor.predict(
                    creative_type=intent["creative_type"],
                    is_ad=True,
                    visual_balance=graph["visual_balance"],
                    total_text_area=graph["total_text_area"],
                    cta_strength=intent["cta_strength"],
                    has_text=text_info["has_text"],
                    goal=intent["goal"],
                )
            except Exception as e:
                logger.warning("CTR predictor failed (%s), skipping", e)

        # Build response
        return GenerateResponse(
            success=result.get('success', False),
            image_url=final_image_url,
            preview_url=result.get('preview_url'),
            ai_analysis=AIAnalysis(
                detected_mode=detected_mode,
                detected_category=detected_category,
                original_prompt=request.prompt,
                enhanced_prompt=enhancement['enhanced'],
                negative_prompt=enhancement['negative'],
                mode_confidence=mode_explanation['confidence'],
                category_confidence=category_explanation['confidence'],
                matched_mode_keywords=mode_explanation['matched_keywords'],
                matched_category_keywords=category_explanation['matched_keywords']
            ),
            metadata=GenerationMetadata(
                quality_tier=request.quality,
                backend=result.get('backend', 'Unknown'),
                dimensions=f"{width}x{height}",
                generation_time=result.get('generation_time', 0),
                model_used=result.get('metadata', {}).get('model')
            ),
            error=result.get('error')
        )

    except Exception as e:
        logger.error(f"Smart generation error: {e}", exc_info=True)
        raise HTTPException(500, f"Generation failed: {str(e)}")


@router.post("/preview")
async def preview_enhancement(request: GenerateRequest):
    """
    Preview what AI will detect and enhance (without generating)

    Returns AI analysis + Creative OS intent + graph without image generation.
    """
    try:
        width, height = get_dimensions(request.dimensions)

        # Creative OS: Intent analysis
        intent = intent_analyzer.analyze(request.prompt, width, height)

        # Mode and category detection
        detected_mode = mode_detector.detect_mode(request.prompt)
        detected_category = category_detector.detect_category(request.prompt)
        mode_explanation = mode_detector.explain_detection(request.prompt)
        category_explanation = category_detector.explain_detection(request.prompt)

        # Text overlay detection
        text_info = text_overlay.detect(request.prompt)

        # Creative Graph
        graph = creative_graph.build(
            creative_type=intent["creative_type"],
            is_ad=intent["is_ad"],
            text_heavy=intent["text_heavy"],
            has_text_overlay=text_info["has_text"],
            aspect_ratio=width / max(height, 1),
            cta_strength=intent["cta_strength"],
            goal=intent["goal"],
        )

        # Prompt enhancement preview
        enhancement = prompt_enhancer.enhance(
            user_prompt=request.prompt,
            mode=detected_mode,
            category=detected_category,
            quality=request.quality
        )

        return {
            'ai_analysis': {
                'detected_mode': detected_mode,
                'detected_category': detected_category,
                'mode_confidence': mode_explanation['confidence'],
                'category_confidence': category_explanation['confidence'],
                'matched_mode_keywords': mode_explanation['matched_keywords'],
                'matched_category_keywords': category_explanation['matched_keywords']
            },
            'enhancement': {
                'original_prompt': request.prompt,
                'enhanced_prompt': enhancement['enhanced'],
                'negative_prompt': enhancement['negative'],
                'enhancements_applied': enhancement['enhancements_applied']
            },
            'generation_config': {
                'quality_tier': request.quality,
                'dimensions': f"{width}x{height}",
                'mode': detected_mode,
                'category': detected_category
            },
            'creative_os': {
                'intent': {
                    'creative_type': intent['creative_type'],
                    'platform': intent['platform']['name'],
                    'goal': intent['goal'],
                    'audience_tone': intent['audience_tone'],
                    'cta_strength': intent['cta_strength'],
                    'is_ad': intent['is_ad'],
                    'text_heavy': intent['text_heavy'],
                },
                'graph': {
                    'reading_flow': graph['reading_flow'],
                    'visual_balance': graph['visual_balance'],
                    'total_text_area': graph['total_text_area'],
                    'dominant_quadrant': graph['dominant_quadrant'],
                    'node_count': len(graph['nodes']),
                },
                'text_overlay': {
                    'has_text': text_info['has_text'],
                    'texts': text_info['texts'],
                },
            },
        }

    except Exception as e:
        logger.error(f"Preview error: {e}", exc_info=True)
        raise HTTPException(500, f"Preview failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check for smart generation service"""
    from app.services.smart.ctr_predictor import USE_CTR_MODEL, USE_AB_VARIANT
    from app.services.smart.intent_analyzer import USE_LLM_INTENT
    from app.services.smart.creative_graph import USE_LLM_GRAPH
    from app.services.smart.poster_jury import USE_OCR_ALIGNMENT, USE_BRAND_CHECKER as JURY_BRAND
    from app.services.smart.brand_checker import USE_BRAND_CHECKER
    from app.services.smart.variant_generator import USE_VARIANT_GENERATION

    return {
        'status': 'ok',
        'service': 'smart-generation-v2',
        'pipeline': 'creative-os',
        'features': {
            'mode_detection': True,
            'category_detection': True,
            'prompt_enhancement': True,
            'intent_analyzer': True,
            'creative_graph': True,
            'poster_jury': True,
            'ctr_predictor': True,
            'brand_checker': True,
            'variant_generator': True,
            'quality_tiers': ['FAST', 'STANDARD', 'PREMIUM'],
            'dimension_presets': list(DIMENSION_PRESETS.keys()),
        },
        'feature_flags': {
            'USE_LLM_INTENT': USE_LLM_INTENT,
            'USE_LLM_GRAPH': USE_LLM_GRAPH,
            'USE_CTR_MODEL': USE_CTR_MODEL,
            'USE_AB_VARIANT': USE_AB_VARIANT,
            'USE_OCR_ALIGNMENT': USE_OCR_ALIGNMENT,
            'USE_BRAND_CHECKER': USE_BRAND_CHECKER,
            'USE_VARIANT_GENERATION': USE_VARIANT_GENERATION,
        },
    }
