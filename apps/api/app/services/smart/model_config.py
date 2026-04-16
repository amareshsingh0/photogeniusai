"""
Next-Gen Model Configuration for PhotoGenius AI
Updated: April 11, 2026

Selected Model Stack (Best Results - User Verified):
- Flux 2 Flex → General photoreal + fast customization (fal.ai cheapest)
- Gemini 3/3.1 → Speed + text king, Google ecosystem (Google AI routing)
- Google Imagen 4 (base/fast/ultra) → Enterprise photoreal, top quality (Google AI routing)
- Grok 2 Imagine → Creative, uncensored, fun styles (fal.ai runtime)
- Hunyuan Image → Best Chinese/Asian text support (fal.ai runtime)
- Ideogram v3.0 → Text rendering undisputed king for posters/logos
- Seedream 4.5 → Top versatility 2026, cheapest high-quality (fal.ai)
- Wan 2.7 → Fast Chinese-style, excellent for bulk Asian aesthetics (fal.ai runtime)
- Recraft v4 Pro → Vector/SVG king for logos/design assets

Reference: Models\modal_list.md (rows 2,6,7,8,11,12,16,19,21)
"""

from typing import Dict, List, Optional
from enum import Enum

class ModelProvider(str, Enum):
    """Only 3 providers: fal.ai (aggregator), Google Vertex AI, WaveSpeed."""
    FAL = "fal"
    GOOGLE = "google"
    WAVESPEED = "wavespeed"

class QualityTier(str, Enum):
    RES_1K = "1k"
    RES_2K = "2k"
    RES_4K = "4k"


_LEGACY_TIER_MAP = {
    "fast": QualityTier.RES_1K,
    "standard": QualityTier.RES_2K,
    "balanced": QualityTier.RES_2K,
    "premium": QualityTier.RES_2K,
    "quality": QualityTier.RES_2K,
    "ultra": QualityTier.RES_4K,
}


def normalize_quality_tier(tier: Optional[str]) -> str:
    """Normalize modern and legacy tier names to 1k/2k/4k."""
    normalized = (tier or "").strip().lower()
    if not normalized:
        return QualityTier.RES_1K.value
    if normalized in QualityTier._value2member_map_:
        return normalized
    legacy = _LEGACY_TIER_MAP.get(normalized)
    if legacy:
        return legacy.value
    return QualityTier.RES_1K.value

# ─────────────────────────────────────────────────────────────────────────────
# MODEL REGISTRY - Next-Gen Models (April 2026)
# ─────────────────────────────────────────────────────────────────────────────

MODEL_REGISTRY = {
    # ═══ FLUX 2 FLEX (fal.ai) ═══
    # General photoreal + customization (modal_list.md row 2-4)
    # Photo Quality: ⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐ | Speed: Fast
    # fal.ai = cheapest platform ($0.015-$0.055)
    "flux_2_flex": {
        "provider": ModelProvider.FAL,
        "endpoint": "fal-ai/flux-2-flex",
        "display_name": "Flux 2 Flex",
        "cost_per_image": 0.015,  # $0.015 (fal.ai cheapest)
        "avg_latency": 5.0,  # Fast
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["general", "photoreal", "fast_prototyping", "customization"],
        "strengths": ["speed", "consistency", "photorealism", "fal_cheapest"],
        "tier": "Mid",
        "rating": 8.5,
    },

    # ═══ GEMINI 3/3.1 IMAGEN (Google AI) ═══
    # Fast iteration, Google ecosystem, Speed + text king (modal_list.md row 6)
    # Photo Quality: ⭐⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Very Fast
    # Batch API 50% off available
    "gemini_3_imagen": {
        "provider": ModelProvider.GOOGLE,
        "endpoint": "gemini-3.0-imagen",
        "display_name": "Gemini 3 Imagen",
        "cost_per_image": 0.035,  # $0.035 (Batch API 50% off = $0.0175)
        "avg_latency": 4.0,  # Very Fast
        "max_resolution": 2048,
        "supports_aspects": True,
        "best_for": ["fast_iteration", "google_ecosystem", "text_generation"],
        "strengths": ["speed", "text_king", "prompt_following", "batch_discount"],
        "tier": "Premium",
        "rating": 9.0,
    },

    "gemini_3_1_imagen": {
        "provider": ModelProvider.GOOGLE,
        "endpoint": "gemini-3.1-imagen",
        "display_name": "Gemini 3.1 Imagen",
        "cost_per_image": 0.070,  # $0.070 (Batch API 50% off = $0.035)
        "avg_latency": 6.0,  # Fast
        "max_resolution": 2048,
        "supports_aspects": True,
        "best_for": ["professional", "editorial", "advertising", "high_quality"],
        "strengths": ["quality", "text_accuracy", "prompt_following", "batch_discount"],
        "tier": "Premium",
        "rating": 9.0,
    },

    # ═══ GOOGLE IMAGEN 4 (Google AI) ═══
    # Enterprise photoreal, high-res, Ultra = top photoreal (modal_list.md row 7)
    # Photo Quality: ⭐⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Fast
    # Bulk discounts on Google AI routing
    "imagen_4_base": {
        "provider": ModelProvider.GOOGLE,
        "endpoint": "imagen-4-base",
        "display_name": "Imagen 4 Base",
        "cost_per_image": 0.020,  # $0.020 (bulk discounts available)
        "avg_latency": 8.0,  # Fast
        "max_resolution": 2048,
        "supports_aspects": True,
        "best_for": ["enterprise", "photoreal", "commercial", "marketing"],
        "strengths": ["photorealism", "high_res", "brand_safety", "bulk_discount"],
        "tier": "Premium",
        "rating": 9.2,
    },

    "imagen_4_fast": {
        "provider": ModelProvider.GOOGLE,
        "endpoint": "imagen-4-fast",
        "display_name": "Imagen 4 Fast",
        "cost_per_image": 0.020,  # $0.020
        "avg_latency": 5.0,  # Fast
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["rapid_iteration", "preview", "testing"],
        "strengths": ["speed", "cost_effective", "reliable"],
        "tier": "Premium",
        "rating": 9.2,
    },

    "imagen_4_ultra": {
        "provider": ModelProvider.GOOGLE,
        "endpoint": "imagen-4-ultra",
        "display_name": "Imagen 4 Ultra",
        "cost_per_image": 0.060,  # $0.060 (top photoreal)
        "avg_latency": 15.0,  # Medium
        "max_resolution": 4096,
        "supports_aspects": True,
        "best_for": ["premium", "print", "billboard", "hero_images"],
        "strengths": ["top_photoreal", "ultra_detail", "4k_resolution", "enterprise"],
        "tier": "Premium",
        "rating": 9.2,
    },

    # ═══ GROK 2 IMAGINE (fal.ai runtime) ═══
    # Creative, uncensored, fun styles - Best value in mid-tier (modal_list.md row 8)
    # Photo Quality: ⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Fast
    # fal.ai runtime path currently used
    "grok_2_imagine": {
        "provider": ModelProvider.WAVESPEED,
        "endpoint": "grok-2-imagine",
        "display_name": "Grok 2 Imagine",
        "cost_per_image": 0.030,  # $0.03-$0.06 (fal.ai runtime)
        "avg_latency": 6.0,  # Fast
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["creative", "uncensored", "fun_styles", "artistic"],
        "strengths": ["creativity", "best_value_midtier", "artistic_freedom", "aggregator_safe"],
        "tier": "Mid",
        "rating": 8.0,
    },

    # ═══ HUNYUAN IMAGE (fal.ai runtime) ═══
    # Asian/CJK text, Best Chinese language support (modal_list.md row 11)
    # Photo Quality: ⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Medium
    # Good for bulk Asian content on the routed fal.ai path
    "hunyuan_image": {
        "provider": ModelProvider.WAVESPEED,
        "endpoint": "hunyuan-image-v1",
        "display_name": "Hunyuan Image",
        "cost_per_image": 0.030,  # $0.03-$0.05 (fal.ai runtime)
        "avg_latency": 8.0,  # Medium
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["asian_cjk_text", "chinese_content", "regional_asia"],
        "strengths": ["best_chinese_support", "cjk_text", "asian_faces", "bulk_asia_safe"],
        "tier": "Mid",
        "rating": 7.8,
    },

    # ═══ IDEOGRAM V3.0 (Ideogram API) ═══
    # Text-heavy: posters, logos - Text rendering undisputed king (modal_list.md row 12)
    # Photo Quality: ⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐⭐ | Speed: Medium
    # Bulk safe on official API
    "ideogram_v3": {
        "provider": ModelProvider.FAL,
        "endpoint": "ideogram-v3",
        "display_name": "Ideogram v3.0",
        "cost_per_image": 0.030,  # $0.03-$0.09 (bulk official)
        "avg_latency": 8.0,  # Medium
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["text_heavy", "posters", "logos", "typography"],
        "strengths": ["text_king_undisputed", "typography_best", "poster_specialist", "bulk_official_safe"],
        "tier": "Premium",
        "rating": 8.8,
    },

    # ═══ SEEDREAM 4.5 (fal.ai) ═══
    # Versatile pro: photoreal + creative - Top versatility 2026 (modal_list.md row 19)
    # Photo Quality: ⭐⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐ | Speed: Fast
    # Cheapest high-quality (fal.ai)
    "seedream_4_5": {
        "provider": ModelProvider.FAL,
        "endpoint": "seedream-4.5",
        "display_name": "Seedream 4.5",
        "cost_per_image": 0.030,  # $0.03-$0.06 (fal.ai cheapest)
        "avg_latency": 5.0,  # Fast
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["versatile_pro", "photoreal", "creative", "bulk"],
        "strengths": ["top_versatility_2026", "cheapest_high_quality", "photoreal_creative", "fal_best_price"],
        "tier": "Premium",
        "rating": 9.0,
    },

    # ═══ WAN 2.7 (fal.ai runtime) ═══
    # Fast Chinese-style, prompt-heavy - Good for bulk/Asian aesthetics (modal_list.md row 21)
    # Photo Quality: ⭐⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Very Fast
    # Excellent for bulk on the routed fal.ai path
    "wan_2_7": {
        "provider": ModelProvider.WAVESPEED,
        "endpoint": "wan-2.7",
        "display_name": "Wan 2.7",
        "cost_per_image": 0.020,  # $0.02-$0.04 (fal.ai runtime)
        "avg_latency": 4.0,  # Very Fast
        "max_resolution": 1024,
        "supports_aspects": True,
        "best_for": ["chinese_style", "prompt_heavy", "bulk_asian", "artistic"],
        "strengths": ["fast_chinese_style", "bulk_excellent", "asian_aesthetics", "prompt_following"],
        "tier": "Budget",
        "rating": 8.0,
    },

    # ═══ RECRAFT V4 PRO (Recraft API) ═══
    # Vector, logos, design assets - Vector/SVG king (modal_list.md row 16)
    # Photo Quality: ⭐⭐⭐ | Text Quality: ⭐⭐⭐⭐ | Speed: Fast
    # Vector safe commercial
    "recraft_v4_pro": {
        "provider": ModelProvider.FAL,
        "endpoint": "recraft-v4-pro",
        "display_name": "Recraft v4 Pro",
        "cost_per_image": 0.030,  # $0.03-$0.05
        "avg_latency": 6.0,  # Fast
        "max_resolution": 2048,
        "supports_aspects": True,
        "best_for": ["vector", "logos", "design_assets", "svg"],
        "strengths": ["vector_svg_king", "scalable", "clean_lines", "commercial_safe"],
        "tier": "Mid",
        "rating": 7.9,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# BUCKET → MODEL MAPPING (Smart Router)
# ─────────────────────────────────────────────────────────────────────────────

BUCKET_MODEL_MAP = {
    # Typography/Poster → Ideogram v3 (best text rendering)
    "typography": {
        QualityTier.RES_1K: "ideogram_v3",
        QualityTier.RES_2K: "gemini_3_1_imagen",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Photorealism → Flux 2 Flex + Imagen 4
    "photorealism": {
        QualityTier.RES_1K: "flux_2_flex",
        QualityTier.RES_2K: "imagen_4_base",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Portrait → Hunyuan (best faces) + Imagen 4
    "photorealism_portrait": {
        QualityTier.RES_1K: "hunyuan_image",
        QualityTier.RES_2K: "gemini_3_1_imagen",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Product → Flux 2 Flex (clean, professional)
    "photorealism_product": {
        QualityTier.RES_1K: "flux_2_flex",
        QualityTier.RES_2K: "imagen_4_base",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Artistic/Creative → Grok 2 + Wan 2.7
    "artistic": {
        QualityTier.RES_1K: "grok_2_imagine",
        QualityTier.RES_2K: "gemini_3_1_imagen",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Anime/Illustration → Wan 2.7 specialist
    "anime": {
        QualityTier.RES_1K: "wan_2_7",
        QualityTier.RES_2K: "gemini_3_1_imagen",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Vector/Logo → Recraft v4 Pro
    "vector": {
        QualityTier.RES_1K: "ideogram_v3",
        QualityTier.RES_2K: "recraft_v4_pro",
        QualityTier.RES_4K: "imagen_4_ultra",
    },

    # Fast generation → Seedream 4.5
    "fast": {
        QualityTier.RES_1K: "seedream_4_5",
        QualityTier.RES_2K: "gemini_3_imagen",
        QualityTier.RES_4K: "imagen_4_ultra",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TIER-BASED MODEL SELECTION (Fallback if no bucket match)
# ─────────────────────────────────────────────────────────────────────────────

TIER_DEFAULT_MODELS = {
    QualityTier.RES_1K: "flux_2_flex",
    QualityTier.RES_2K: "imagen_4_base",
    QualityTier.RES_4K: "imagen_4_ultra",
}

# ─────────────────────────────────────────────────────────────────────────────
# MODEL ROUTER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_model_for_request(
    bucket: str,
    tier: str,
    provider_override: Optional[str] = None
) -> Dict:
    """
    Get best model for request based on bucket + tier.

    Args:
        bucket: Capability bucket (typography, photorealism, etc.)
        tier: Resolution tier (1k, 2k, 4k) or legacy quality tier
        provider_override: Force specific provider (optional)

    Returns:
        Model configuration dict compatible with generate_stream.py format:
        {"model": endpoint, "provider": provider, "num_images": num, ...}
    """
    normalized_tier = normalize_quality_tier(tier)
    tier_enum = QualityTier(normalized_tier)

    # Provider override (force specific model)
    if provider_override and provider_override in MODEL_REGISTRY:
        model_key = provider_override
        model_spec = MODEL_REGISTRY[provider_override]
    # Bucket-specific routing
    elif bucket in BUCKET_MODEL_MAP:
        model_key = BUCKET_MODEL_MAP[bucket].get(tier_enum)
        if model_key:
            model_spec = MODEL_REGISTRY[model_key]
        else:
            # Fallback to tier default
            model_key = TIER_DEFAULT_MODELS[tier_enum]
            model_spec = MODEL_REGISTRY[model_key]
    else:
        # Fallback to tier default
        model_key = TIER_DEFAULT_MODELS[tier_enum]
        model_spec = MODEL_REGISTRY[model_key]

    # Convert to generate_stream.py compatible format
    result = {
        "model_key": model_key,
        "model": model_spec["endpoint"],  # e.g. "fal-ai/flux-2-flex"
        "provider": model_spec["provider"].value,  # e.g. "fal"
        "display_name": model_spec["display_name"],
        "tier_used": normalized_tier,
        "cost_per_image": model_spec["cost_per_image"],
        "avg_latency": model_spec["avg_latency"],
        "max_resolution": model_spec["max_resolution"],
        "num_images": 1,  # Always 1 image per model (admin testing mode handles multiple models)
    }

    return result

def list_available_models(
    provider: Optional[ModelProvider] = None,
    max_cost: Optional[float] = None,
    min_resolution: Optional[int] = None
) -> List[Dict]:
    """
    List available models with optional filters.

    Args:
        provider: Filter by provider
        max_cost: Maximum cost per image
        min_resolution: Minimum resolution

    Returns:
        List of model configs
    """
    models = []

    for key, config in MODEL_REGISTRY.items():
        # Apply filters
        if provider and config["provider"] != provider:
            continue
        if max_cost and config["cost_per_image"] > max_cost:
            continue
        if min_resolution and config["max_resolution"] < min_resolution:
            continue

        models.append({
            "key": key,
            **config
        })

    return models

def get_model_cost(model_key: str, num_images: int = 1) -> float:
    """Calculate total cost for generation."""
    if model_key not in MODEL_REGISTRY:
        return 0.0

    return MODEL_REGISTRY[model_key]["cost_per_image"] * num_images

def get_fastest_models(top_n: int = 5) -> List[Dict]:
    """Get fastest models sorted by latency."""
    models = []
    for key, config in MODEL_REGISTRY.items():
        models.append({
            "key": key,
            "latency": config["avg_latency"],
            **config
        })

    return sorted(models, key=lambda x: x["latency"])[:top_n]

def get_cheapest_models(top_n: int = 5) -> List[Dict]:
    """Get cheapest models sorted by cost."""
    models = []
    for key, config in MODEL_REGISTRY.items():
        models.append({
            "key": key,
            "cost": config["cost_per_image"],
            **config
        })

    return sorted(models, key=lambda x: x["cost"])[:top_n]

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

PROVIDER_ENDPOINTS = {
    ModelProvider.FAL: {
        "base_url": "https://fal.run",
        "api_key_env": "FAL_KEY",
        "auth_header": "Authorization",
        "auth_format": "Key {api_key}",
    },
    ModelProvider.GOOGLE: {
        "base_url": "https://generativelanguage.googleapis.com/v1",
        "api_key_env": "GEMINI_API_KEY",
        "auth_header": "x-goog-api-key",
        "auth_format": "{api_key}",
    },
    ModelProvider.XAI: {
        "base_url": "https://api.x.ai/v1",
        "api_key_env": "XAI_API_KEY",
        "auth_header": "Authorization",
        "auth_format": "Bearer {api_key}",
    },
    ModelProvider.HUNYUAN: {
        "base_url": "https://api.hunyuan.tencent.com/v1",
        "api_key_env": "HUNYUAN_API_KEY",
        "auth_header": "Authorization",
        "auth_format": "Bearer {api_key}",
    },
    ModelProvider.FAL: {
        "base_url": "https://api.ideogram.ai/v1",
        "api_key_env": "IDEOGRAM_API_KEY",
        "auth_header": "Api-Key",
        "auth_format": "{api_key}",
    },
    ModelProvider.FAL: {
        "base_url": "https://api.seedream.ai/v1",
        "api_key_env": "SEEDREAM_API_KEY",
        "auth_header": "Authorization",
        "auth_format": "Bearer {api_key}",
    },
    ModelProvider.WAN: {
        "base_url": "https://api.wan.ai/v1",
        "api_key_env": "WAN_API_KEY",
        "auth_header": "Authorization",
        "auth_format": "Bearer {api_key}",
    },
    ModelProvider.FAL: {
        "base_url": "https://external.api.recraft.ai/v1",
        "api_key_env": "RECRAFT_API_KEY",
        "auth_header": "Authorization",
        "auth_format": "Bearer {api_key}",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: Get model for typography poster
    model = get_model_for_request(bucket="typography", tier="premium")
    print(f"Typography Premium → {model['display_name']}")
    print(f"Cost: ${model['cost_per_image']}")
    print(f"Provider: {model['provider']}")

    # Example: List fastest models
    print("\n5 Fastest Models:")
    for m in get_fastest_models(5):
        print(f"  {m['display_name']}: {m['latency']}s")

    # Example: List cheapest models
    print("\n5 Cheapest Models:")
    for m in get_cheapest_models(5):
        print(f"  {m['display_name']}: ${m['cost']}")
