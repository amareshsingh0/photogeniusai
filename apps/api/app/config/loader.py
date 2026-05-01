"""
Beast Config Loader
Singleton pattern to load all config files once at startup
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BeastConfig:
    """Singleton config loader for Beast Creative Studio"""

    _instance = None
    _configs: Dict[str, Any] = {}
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._load_all()
            BeastConfig._loaded = True

    def _load_all(self):
        """Load all config files once at startup"""
        config_dir = Path(__file__).parent

        config_files = [
            "beast_standards.json",
            "aesthetic_codes.json",
            "platform_contracts.json",
            "generational_signals.json",
            "composition_archetypes.json",
            "type_scales.json",
            "quality_dimensions.json"
        ]

        for filename in config_files:
            try:
                with open(config_dir / filename, encoding='utf-8') as f:
                    key = filename.replace(".json", "")
                    self._configs[key] = json.load(f)
                    logger.debug(f"✅ Loaded {filename}")
            except Exception as e:
                logger.error(f"❌ Failed to load {filename}: {e}")
                self._configs[key] = {}

        logger.debug(f"🎯 Beast Config loaded: {len(self._configs)} files")

    def get(self, config_name: str) -> Dict[str, Any]:
        """Get a loaded config by name"""
        return self._configs.get(config_name, {})

    # ============================================================
    # PLATFORM CONTRACTS
    # ============================================================

    def get_platform_rules(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get platform-specific rules"""
        platforms = self.get("platform_contracts").get("platforms", {})
        return platforms.get(platform)

    def get_platform_attention_window(self, platform: str) -> float:
        """Get platform attention window in seconds"""
        rules = self.get_platform_rules(platform)
        if rules:
            return rules.get("viewer_behavior", {}).get("attention_window_seconds", 2.0)
        return 2.0

    def get_platform_dimensions(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get platform dimensions (first available)"""
        rules = self.get_platform_rules(platform)
        if rules:
            dimensions = rules.get("technical_specs", {}).get("dimensions", {})
            if dimensions:
                first_key = list(dimensions.keys())[0]
                return dimensions[first_key]
        return None

    def get_platform_copy_limits(self, platform: str) -> Dict[str, Any]:
        """Get platform copy character limits"""
        rules = self.get_platform_rules(platform)
        if rules:
            return rules.get("copy_limits", {})
        return {}

    def get_platform_safe_zones(self, platform: str) -> Dict[str, int]:
        """Get platform safe zones in pixels"""
        rules = self.get_platform_rules(platform)
        if rules:
            return rules.get("technical_specs", {}).get("safe_zones", {})
        return {}

    # ============================================================
    # GENERATIONAL SIGNALS
    # ============================================================

    def get_generation_profile(self, generation: str) -> Optional[Dict[str, Any]]:
        """Get generational profile"""
        generations = self.get("generational_signals").get("generations", {})
        return generations.get(generation)

    def detect_generation_from_keywords(self, prompt: str) -> str:
        """Auto-detect generation from prompt keywords"""
        keyword_signals = self.get("generational_signals").get(
            "generational_detection_rules", {}
        ).get("keyword_signals", {})

        prompt_lower = prompt.lower()
        for gen_id, keywords in keyword_signals.items():
            if any(kw in prompt_lower for kw in keywords):
                return gen_id

        return "mass_market_india"  # default fallback

    def get_psychographic_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get psychographic profile"""
        profiles = self.get("generational_signals").get("psychographic_profiles", {})
        return profiles.get(profile_id)

    # ============================================================
    # AESTHETIC CODES
    # ============================================================

    def get_aesthetic(self, aesthetic_id: str) -> Optional[Dict[str, Any]]:
        """Get aesthetic code"""
        aesthetics = self.get("aesthetic_codes").get("aesthetic_codes_2026_q2", {})
        return aesthetics.get(aesthetic_id)

    def detect_aesthetic_by_industry(self, industry: str) -> str:
        """Auto-detect aesthetic by industry"""
        auto_detection = self.get("aesthetic_codes").get(
            "aesthetic_detection_rules", {}
        ).get("auto_detection_by_industry", {})

        industry_key = industry.lower().replace(" ", "_")
        return auto_detection.get(industry_key, "ai_native")

    def detect_aesthetic_by_keywords(self, prompt: str) -> str:
        """Auto-detect aesthetic by keywords"""
        keyword_map = self.get("aesthetic_codes").get(
            "aesthetic_detection_rules", {}
        ).get("auto_detection_by_keywords", {})

        prompt_lower = prompt.lower()
        for keyword_pattern, aesthetic_id in keyword_map.items():
            keywords = keyword_pattern.split("|")
            if any(kw in prompt_lower for kw in keywords):
                return aesthetic_id

        return self.get("aesthetic_codes").get(
            "aesthetic_detection_rules", {}
        ).get("fallback_aesthetic", "ai_native")

    # ============================================================
    # COMPOSITION ARCHETYPES
    # ============================================================

    def get_composition_archetype(self, archetype_id: str) -> Optional[Dict[str, Any]]:
        """Get composition archetype"""
        archetypes = self.get("composition_archetypes").get("archetypes", {})
        return archetypes.get(archetype_id)

    def select_archetype_by_asset_type(self, asset_type: str) -> str:
        """Select archetype by asset type"""
        selection_rules = self.get("composition_archetypes").get(
            "composition_selection_rules", {}
        ).get("by_asset_type", {})

        return selection_rules.get(asset_type, "hero_dominant")

    def select_archetype_by_emotion(self, emotion: str) -> str:
        """Select archetype by emotion"""
        selection_rules = self.get("composition_archetypes").get(
            "composition_selection_rules", {}
        ).get("by_emotion", {})

        return selection_rules.get(emotion.lower(), "hero_dominant")

    def select_archetype_by_platform(self, platform: str) -> list:
        """Get recommended archetypes for platform"""
        selection_rules = self.get("composition_archetypes").get(
            "composition_selection_rules", {}
        ).get("by_platform", {})

        return selection_rules.get(platform, ["hero_dominant"])

    # ============================================================
    # TYPE SCALES
    # ============================================================

    def get_type_scale(self, scale_id: str) -> Optional[Dict[str, Any]]:
        """Get typography scale"""
        scales = self.get("type_scales").get("type_scales", {})
        return scales.get(scale_id)

    def select_scale_by_platform(self, platform: str) -> str:
        """Select type scale by platform"""
        selection_rules = self.get("type_scales").get(
            "scale_selection_rules", {}
        ).get("by_platform", {})

        return selection_rules.get(platform, "digital_efficiency")

    def select_scale_by_brand_personality(self, personality: str) -> str:
        """Select type scale by brand personality"""
        selection_rules = self.get("type_scales").get(
            "scale_selection_rules", {}
        ).get("by_brand_personality", {})

        return selection_rules.get(personality, "digital_efficiency")

    # ============================================================
    # QUALITY DIMENSIONS
    # ============================================================

    def get_quality_dimension(self, dimension_id: str) -> Optional[Dict[str, Any]]:
        """Get quality dimension"""
        dimensions = self.get("quality_dimensions").get("dimensions", {})
        return dimensions.get(dimension_id)

    def get_all_quality_dimensions(self) -> Dict[str, Any]:
        """Get all 12 quality dimensions"""
        return self.get("quality_dimensions").get("dimensions", {})

    def get_beast_gates(self) -> Dict[str, Any]:
        """Get all 10 Beast Standard gates"""
        return self.get("quality_dimensions").get("beast_standard_gates", {})

    def get_scoring_thresholds(self) -> Dict[str, Any]:
        """Get quality scoring thresholds"""
        return self.get("quality_dimensions").get("scoring_system", {})

    def get_revision_routing(self) -> Dict[str, str]:
        """Get revision routing map"""
        return self.get("quality_dimensions").get("revision_routing", {})

    # ============================================================
    # BEAST STANDARDS (LEGACY SUPPORT)
    # ============================================================

    def get_cultural_moments(self) -> Dict[str, Any]:
        """Get cultural moment detector"""
        return self.get("beast_standards").get("STAGE_1_TRIAGE", {}).get(
            "cultural_moment_detector", {}
        )

    def get_indian_festivals(self) -> Dict[str, Any]:
        """Get Indian festival palettes"""
        return self.get_cultural_moments().get("indian_festivals", {})

    def get_emotion_to_visual_map(self) -> Dict[str, Any]:
        """Get emotion to visual mapping"""
        return self.get("beast_standards").get("STAGE_3_CREATIVE_DIRECTION", {}).get(
            "emotion_to_visual_map", {}
        )

    def get_prompt_engineering_kb(self) -> Dict[str, Any]:
        """Get prompt engineering knowledge base"""
        return self.get("beast_standards").get("STAGE_7_PROMPT_ENGINEERING", {})


# Singleton instance - import this in agents
config = BeastConfig()
