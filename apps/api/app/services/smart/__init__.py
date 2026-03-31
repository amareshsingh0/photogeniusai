"""
Smart AI Services — Creative OS Pipeline

Core modules:
    mode_detector       — Detect generation mode (REALISM, CINEMATIC, etc.)
    category_detector   — Detect content category (portrait, landscape, etc.)
    prompt_enhancer     — Enhance prompts with quality keywords
    generation_router   — Route to GPU1 generation backends

Creative OS modules:
    intent_analyzer     — STAGE -1: Classify creative intent, platform, goal
    creative_graph      — STAGE 1:  Node-based layout graph for ad/poster
    layout_planner      — STAGE 2:  Design plan with rule-of-thirds math
    creative_director   — Concept extraction (theme, objects, colors)
    text_overlay        — PIL text rendering
    design_effects      — PIL post-processing
    poster_jury         — Ad/poster quality scoring (v2: OCR, WCAG, composition, brand)
    ctr_predictor       — Engagement potential prediction (stub)
    brand_checker       — Brand guideline compliance
    variant_generator   — Auto-generate layout/color variants for ads
"""

from .mode_detector import ModeDetector, mode_detector
from .category_detector import CategoryDetector, category_detector
from .prompt_enhancer import SmartPromptEnhancer, prompt_enhancer
from .generation_router import GenerationRouter, generation_router
from .intent_analyzer import IntentAnalyzer, intent_analyzer
from .creative_graph import CreativeGraphBuilder, creative_graph
from .ctr_predictor import CTRPredictor, ctr_predictor
from .poster_jury import PosterJury, poster_jury
from .brand_checker import BrandChecker, brand_checker
from .variant_generator import VariantGenerator, variant_generator

__all__ = [
    'ModeDetector',
    'mode_detector',
    'CategoryDetector',
    'category_detector',
    'SmartPromptEnhancer',
    'prompt_enhancer',
    'GenerationRouter',
    'generation_router',
    'IntentAnalyzer',
    'intent_analyzer',
    'CreativeGraphBuilder',
    'creative_graph',
    'CTRPredictor',
    'ctr_predictor',
    'PosterJury',
    'poster_jury',
    'BrandChecker',
    'brand_checker',
    'VariantGenerator',
    'variant_generator',
]
