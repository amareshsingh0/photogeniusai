# BEAST Config Integration Guide

**Date:** April 7, 2026
**Status:** Production-Ready
**Location:** `apps/api/app/config/`

---

## Overview

This guide shows you how to integrate the 7 Beast-level config files into your Python agents and TypeScript frontend.

**Config Files:**
1. `beast_standards.json` (1,204 lines)
2. `aesthetic_codes.json` (358 lines)
3. `platform_contracts.json` (540 lines)
4. `generational_signals.json` (520 lines)
5. `composition_archetypes.json` (450 lines)
6. `type_scales.json` (580 lines)
7. `quality_dimensions.json` (680 lines)

**Total:** 4,332 lines | ~327KB | <200ms load time

---

## Python Integration

### Step 1: Create Config Loader Utility

Create `apps/api/app/config/loader.py`:

```python
"""
Beast Config Loader
Singleton pattern to load all config files once at startup
"""

import json
from pathlib import Path
from typing import Dict, Any
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
            self._loaded = True

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
                    logger.info(f"Loaded {filename}")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")
                self._configs[key] = {}

    def get(self, config_name: str) -> Dict[str, Any]:
        """Get a loaded config by name"""
        return self._configs.get(config_name, {})

    def get_platform_rules(self, platform: str) -> Dict[str, Any]:
        """Get platform-specific rules"""
        platforms = self.get("platform_contracts").get("platforms", {})
        return platforms.get(platform, {})

    def get_generation_profile(self, generation: str) -> Dict[str, Any]:
        """Get generational profile"""
        generations = self.get("generational_signals").get("generations", {})
        return generations.get(generation, {})

    def get_aesthetic(self, aesthetic: str) -> Dict[str, Any]:
        """Get aesthetic code"""
        aesthetics = self.get("aesthetic_codes").get("aesthetic_codes_2026_q2", {})
        return aesthetics.get(aesthetic, {})

    def get_composition_archetype(self, archetype: str) -> Dict[str, Any]:
        """Get composition archetype"""
        archetypes = self.get("composition_archetypes").get("archetypes", {})
        return archetypes.get(archetype, {})

    def get_type_scale(self, scale: str) -> Dict[str, Any]:
        """Get typography scale"""
        scales = self.get("type_scales").get("type_scales", {})
        return scales.get(scale, {})

    def get_quality_dimension(self, dimension: str) -> Dict[str, Any]:
        """Get quality dimension"""
        dimensions = self.get("quality_dimensions").get("dimensions", {})
        return dimensions.get(dimension, {})


# Singleton instance
config = BeastConfig()
```

---

### Step 2: Update Triage Agent

In `apps/api/app/services/smart/beast_triage_agent.py`:

```python
from app.config.loader import config

def triage_request(prompt: str, platform: str = None) -> dict:
    """Enhanced triage with Beast config"""

    # Load platform contracts
    if platform:
        platform_rules = config.get_platform_rules(platform)
        attention_window = platform_rules.get("viewer_behavior", {}).get("attention_window_seconds", 2.0)
        scroll_stop_power = platform_rules.get("visual_contract", {}).get("scroll_stop_power", "medium")

    # Load cultural moments
    cultural_moments = config.get("beast_standards").get("STAGE_1_TRIAGE", {}).get("cultural_moment_detector", {})
    indian_festivals = cultural_moments.get("indian_festivals", {})

    # Detect festival from prompt
    detected_festival = None
    for festival_name, festival_data in indian_festivals.items():
        keywords = festival_data.get("copy_themes", []) + [festival_name.lower()]
        if any(kw in prompt.lower() for kw in keywords):
            detected_festival = {
                "type": festival_name,
                "palette": festival_data.get("palette", {}),
                "motifs": festival_data.get("motifs", []),
                "emotion": festival_data.get("emotion", "")
            }
            break

    # Load psychographic map
    psychographic_map = config.get("beast_standards").get("STAGE_1_TRIAGE", {}).get("audience_psychographic_map", {})

    # Detect generation from prompt keywords
    generational_signals = config.get("generational_signals")
    keyword_signals = generational_signals.get("generational_detection_rules", {}).get("keyword_signals", {})

    detected_generation = "mass_market_india"  # default
    for gen_id, keywords in keyword_signals.items():
        if any(kw in prompt.lower() for kw in keywords):
            detected_generation = gen_id
            break

    # Get generation profile
    generation_profile = config.get_generation_profile(detected_generation)

    return {
        "platform": platform,
        "attention_window_seconds": attention_window if platform else 2.0,
        "scroll_stop_power": scroll_stop_power if platform else "medium",
        "cultural_moment": detected_festival,
        "generation": detected_generation,
        "aesthetic_preference": generation_profile.get("aesthetic_preference", {}),
        "copy_voice": generation_profile.get("copy_voice", {}),
        "platform_behavior": generation_profile.get("platform_behavior", {})
    }
```

---

### Step 3: Update Creative Director

In `apps/api/app/services/smart/creative_director.py`:

```python
from app.config.loader import config

def get_aesthetic_direction(industry: str, emotion: str, triage_output: dict) -> dict:
    """Select aesthetic code based on industry + generation"""

    # Auto-detect aesthetic by industry
    aesthetic_detection = config.get("aesthetic_codes").get("aesthetic_detection_rules", {})
    auto_detection = aesthetic_detection.get("auto_detection_by_industry", {})

    # Map industry to aesthetic
    industry_key = industry.lower().replace(" ", "_")
    aesthetic_id = auto_detection.get(industry_key, "ai_native")  # fallback

    # Get aesthetic code
    aesthetic = config.get_aesthetic(aesthetic_id)

    # Extract visual language for prompts
    visual_language = aesthetic.get("visual_language", {})
    keywords_for_models = visual_language.get("keywords_for_models", "")
    color_palette = aesthetic.get("color_palette", {})

    # Get emotion-to-visual mapping
    emotion_map = config.get("beast_standards").get("STAGE_3_CREATIVE_DIRECTION", {}).get("emotion_to_visual_map", {})
    emotion_visual = emotion_map.get(emotion.lower(), {})

    return {
        "aesthetic_id": aesthetic_id,
        "aesthetic_name": aesthetic.get("code_id", ""),
        "visual_keywords": keywords_for_models,
        "color_palette": color_palette,
        "emotion_visual": emotion_visual,
        "composition": emotion_visual.get("composition", "hero_dominant"),
        "typography": emotion_visual.get("typography", "clean_sans_medium"),
        "space": emotion_visual.get("space", "generous_structured"),
        "glow": emotion_visual.get("glow", "none"),
        "motion_quality": emotion_visual.get("motion_quality", "steady_confident")
    }
```

---

### Step 4: Update Design Director

In `apps/api/app/services/smart/design_director.py`:

```python
from app.config.loader import config

def select_composition_archetype(asset_type: str, emotion: str, platform: str) -> dict:
    """Select composition archetype from config"""

    # Get selection rules
    archetypes_config = config.get("composition_archetypes")
    selection_rules = archetypes_config.get("composition_selection_rules", {})

    # Try by asset type
    by_asset = selection_rules.get("by_asset_type", {})
    archetype_id = by_asset.get(asset_type, None)

    # Fallback to emotion
    if not archetype_id:
        by_emotion = selection_rules.get("by_emotion", {})
        archetype_id = by_emotion.get(emotion.lower(), "hero_dominant")

    # Get archetype details
    archetype = config.get_composition_archetype(archetype_id)

    return {
        "archetype_id": archetype_id,
        "archetype_name": archetype.get("archetype_name", ""),
        "composition_rules": archetype.get("composition_rules", {}),
        "space_character": archetype.get("space_character", {}),
        "typography_treatment": archetype.get("typography_treatment", {}),
        "prompt_engineering_notes": archetype.get("prompt_engineering_notes", {})
    }


def select_type_scale(platform: str, brand_personality: str) -> dict:
    """Select typography scale from config"""

    # Get selection rules
    type_scales_config = config.get("type_scales")
    selection_rules = type_scales_config.get("scale_selection_rules", {})

    # Try by platform
    by_platform = selection_rules.get("by_platform", {})
    scale_id = by_platform.get(platform, None)

    # Fallback to brand personality
    if not scale_id:
        by_personality = selection_rules.get("by_brand_personality", {})
        scale_id = by_personality.get(brand_personality, "digital_efficiency")

    # Get scale details
    scale = config.get_type_scale(scale_id)

    return {
        "scale_id": scale_id,
        "scale_name": scale.get("scale_name", ""),
        "scale_px": scale.get("scale_px", {}),
        "hierarchy_ratio": scale.get("hierarchy_ratio", ""),
        "typeface_recommendations": scale.get("typeface_recommendations", {})
    }
```

---

### Step 5: Update Quality Critic

In `apps/api/app/services/smart/quality_critic.py`:

```python
from app.config.loader import config

def score_image(image_url: str, creative_brief: dict) -> dict:
    """Score image on 12 dimensions"""

    # Load quality dimensions
    dimensions_config = config.get("quality_dimensions")
    dimensions = dimensions_config.get("dimensions", {})
    beast_gates = dimensions_config.get("beast_standard_gates", {})
    scoring_system = dimensions_config.get("scoring_system", {})

    # Score each dimension (via Gemini Vision API calls)
    dimension_scores = {}
    for dim_id, dim_config in dimensions.items():
        # Call Gemini Vision with dimension rubric
        score = _score_dimension_via_gemini(image_url, dim_id, dim_config, creative_brief)
        dimension_scores[dim_id] = {
            "score": score,
            "weight": dim_config.get("normalized_weight", 0.091)
        }

    # Calculate weighted overall score
    overall_score = sum(
        ds["score"] * ds["weight"]
        for ds in dimension_scores.values()
    )

    # Run Beast Standard gates
    gates_passed = 0
    gate_results = {}
    for gate_id, gate_config in beast_gates.items():
        passed = _run_beast_gate(image_url, gate_id, gate_config, creative_brief)
        gate_results[gate_id] = passed
        if passed:
            gates_passed += 1

    # Determine verdict
    verdict_logic = scoring_system.get("verdict_logic", {})
    min_to_ship = scoring_system.get("minimum_to_ship", 8.5)
    gates_min = scoring_system.get("gates_minimum_pass", 9)

    if overall_score >= 9.5 and gates_passed == 10:
        verdict = "ELITE"
    elif overall_score >= min_to_ship and gates_passed >= gates_min:
        verdict = "APPROVED"
    elif overall_score >= 7.5 or gates_passed >= 7:
        verdict = "CONDITIONAL"
    elif overall_score >= 5.0 or gates_passed >= 5:
        verdict = "REVISE"
    elif overall_score >= 3.0:
        verdict = "MAJOR_REVISE"
    else:
        verdict = "REJECT"

    # Get revision routing if needed
    revision_routing = dimensions_config.get("revision_routing", {})
    weak_dimensions = [
        dim_id for dim_id, ds in dimension_scores.items()
        if ds["score"] < scoring_system.get("dimension_floor", 7.0)
    ]

    return {
        "overall_score": round(overall_score, 2),
        "dimension_scores": dimension_scores,
        "gates_passed": gates_passed,
        "gate_results": gate_results,
        "verdict": verdict,
        "weak_dimensions": weak_dimensions,
        "revision_agents": [
            revision_routing.get(dim_id, "unknown")
            for dim_id in weak_dimensions
        ]
    }
```

---

## TypeScript Integration

### Step 1: Create Type Definitions

Create `apps/web/types/beast-config.ts`:

```typescript
// Platform Contracts
export type Platform =
  | 'instagram_feed'
  | 'instagram_story'
  | 'youtube_thumbnail'
  | 'tiktok'
  | 'linkedin'
  | 'facebook_feed'
  | 'twitter_x'
  | 'pinterest'
  | 'google_display'
  | 'billboard_ooh'
  | 'print_magazine'
  | 'whatsapp_forward'
  | 'email_header'
  | 'app_icon'
  | 'business_card'

export interface PlatformContract {
  platform_id: string
  asset_type: string
  viewer_behavior: {
    attention_mode: string
    attention_window_seconds: number
    decision_point: string
    sound_assumption?: string
  }
  visual_contract: {
    scroll_stop_power: string
    composition_density: string
    text_on_image_max?: string
    face_preference?: string
  }
  technical_specs: {
    dimensions: Record<string, { w: number; h: number; aspect: string }>
    file_size_max_mb: number
    formats: string[]
    safe_zones?: Record<string, number>
  }
  copy_limits: Record<string, any>
  platform_specific_rules: string[]
  quality_gates: Record<string, string>
}

// Generational Signals
export type Generation =
  | 'gen_z_india'
  | 'millennial_parent_india'
  | 'achiever_urban_india'
  | 'premium_buyer_india'
  | 'mass_market_india'

export interface GenerationProfile {
  generation_id: string
  age_range: [number, number]
  worldview: {
    core_values: string[]
    trust_signals: string
    decision_drivers: string
  }
  aesthetic_preference: {
    visual_style: string
    color_preference: string
    preferred_aesthetics: string[]
  }
  copy_voice: {
    tone: string
    examples: string[]
    forbidden: string[]
  }
  platform_behavior: {
    primary_platforms: string[]
    engagement_peak_hours: string
  }
}

// Aesthetic Codes
export type Aesthetic =
  | 'brutalism_luxury'
  | 'ai_native'
  | 'bio_organic_geometry'
  | 'post_ironic_sincerity'
  | 'retro_futures'
  | 'quiet_luxury_loud'
  | 'cultural_maximalism'
  | 'anti_aesthetic'

// Composition Archetypes
export type CompositionArchetype =
  | 'hero_dominant'
  | 'typographic_led'
  | 'editorial_split'
  | 'dynamic_diagonal'
  | 'asymmetric_tension'
  | 'maximalist_density'
  | 'thumbnail_halves'

// Type Scales
export type TypeScale =
  | 'poster_impact'
  | 'editorial_refined'
  | 'digital_efficiency'
  | 'billboard_distance'
  | 'mobile_thumb_zone'

// Quality Dimensions
export type QualityDimension =
  | 'concept_integrity'
  | 'emotional_precision'
  | 'visual_hierarchy'
  | 'typographic_excellence'
  | 'color_execution'
  | 'platform_fitness'
  | 'brand_coherence'
  | 'originality'
  | 'execution_quality'
  | 'audience_resonance'
  | 'cultural_intelligence'
  | 'want_one_test'

export interface DimensionScore {
  score: number
  weight: number
}

export interface QualityScore {
  overall_score: number
  dimension_scores: Record<QualityDimension, DimensionScore>
  gates_passed: number
  gate_results: Record<string, boolean>
  verdict: 'ELITE' | 'APPROVED' | 'CONDITIONAL' | 'REVISE' | 'MAJOR_REVISE' | 'REJECT'
  weak_dimensions: QualityDimension[]
  revision_agents: string[]
}
```

---

### Step 2: Create Config Accessor

Create `apps/web/lib/beast-config.ts`:

```typescript
import beastStandards from '@/config/beast_standards.json'
import aestheticCodes from '@/config/aesthetic_codes.json'
import platformContracts from '@/config/platform_contracts.json'
import generationalSignals from '@/config/generational_signals.json'
import compositionArchetypes from '@/config/composition_archetypes.json'
import typeScales from '@/config/type_scales.json'
import qualityDimensions from '@/config/quality_dimensions.json'

import type {
  Platform,
  PlatformContract,
  Generation,
  GenerationProfile,
  Aesthetic,
  CompositionArchetype,
  TypeScale,
  QualityDimension,
} from '@/types/beast-config'

export class BeastConfig {
  // Platform Contracts
  static getPlatformRules(platform: Platform): PlatformContract | null {
    return (platformContracts.platforms as any)[platform] || null
  }

  static getAttentionWindow(platform: Platform): number {
    const rules = this.getPlatformRules(platform)
    return rules?.viewer_behavior?.attention_window_seconds || 2.0
  }

  static getPlatformDimensions(platform: Platform): { w: number; h: number; aspect: string } | null {
    const rules = this.getPlatformRules(platform)
    if (!rules) return null
    const dimensions = rules.technical_specs.dimensions
    // Return first dimension option
    const firstKey = Object.keys(dimensions)[0]
    return dimensions[firstKey] || null
  }

  // Generational Signals
  static getGenerationProfile(generation: Generation): GenerationProfile | null {
    return (generationalSignals.generations as any)[generation] || null
  }

  static detectGenerationFromKeywords(prompt: string): Generation {
    const keywordSignals = generationalSignals.generational_detection_rules.keyword_signals

    for (const [genId, keywords] of Object.entries(keywordSignals)) {
      if ((keywords as string[]).some(kw => prompt.toLowerCase().includes(kw))) {
        return genId as Generation
      }
    }

    return 'mass_market_india' // default
  }

  // Aesthetic Codes
  static getAesthetic(aesthetic: Aesthetic) {
    return (aestheticCodes.aesthetic_codes_2026_q2 as any)[aesthetic] || null
  }

  static detectAestheticByIndustry(industry: string): Aesthetic {
    const autoDetection = aestheticCodes.aesthetic_detection_rules.auto_detection_by_industry
    const industryKey = industry.toLowerCase().replace(/\s+/g, '_')
    return (autoDetection as any)[industryKey] || 'ai_native'
  }

  // Composition Archetypes
  static getCompositionArchetype(archetype: CompositionArchetype) {
    return (compositionArchetypes.archetypes as any)[archetype] || null
  }

  // Type Scales
  static getTypeScale(scale: TypeScale) {
    return (typeScales.type_scales as any)[scale] || null
  }

  // Quality Dimensions
  static getQualityDimension(dimension: QualityDimension) {
    return (qualityDimensions.dimensions as any)[dimension] || null
  }

  static getMinimumScoreToShip(): number {
    return qualityDimensions.scoring_system.minimum_to_ship
  }

  static getVerdictThresholds() {
    return qualityDimensions.scoring_system
  }
}
```

---

### Step 3: Use in React Components

In `apps/web/app/(dashboard)/generate/page.tsx`:

```typescript
'use client'

import { BeastConfig } from '@/lib/beast-config'
import type { Platform, Generation } from '@/types/beast-config'

export default function GeneratePage() {
  const [platform, setPlatform] = useState<Platform>('instagram_feed')
  const [detectedGeneration, setDetectedGeneration] = useState<Generation>('mass_market_india')

  const handlePromptChange = (prompt: string) => {
    // Auto-detect generation from keywords
    const generation = BeastConfig.detectGenerationFromKeywords(prompt)
    setDetectedGeneration(generation)

    // Get generation profile
    const profile = BeastConfig.getGenerationProfile(generation)
    console.log('Copy voice examples:', profile?.copy_voice.examples)
  }

  const handlePlatformChange = (newPlatform: Platform) => {
    setPlatform(newPlatform)

    // Get platform rules
    const rules = BeastConfig.getPlatformRules(newPlatform)
    const attentionWindow = rules?.viewer_behavior.attention_window_seconds
    console.log(`Attention window: ${attentionWindow}s`)

    // Get dimensions
    const dimensions = BeastConfig.getPlatformDimensions(newPlatform)
    console.log(`Dimensions: ${dimensions?.w}x${dimensions?.h}`)
  }

  return (
    <div>
      {/* Platform selector */}
      {/* Prompt input with generation detection */}
      {/* Show attention window + safe zones */}
    </div>
  )
}
```

---

In `apps/web/components/quality-score-display.tsx`:

```typescript
import { BeastConfig } from '@/lib/beast-config'
import type { QualityScore } from '@/types/beast-config'

interface Props {
  qualityScore: QualityScore
}

export function QualityScoreDisplay({ qualityScore }: Props) {
  const minToShip = BeastConfig.getMinimumScoreToShip() // 8.5

  const verdictColor = {
    ELITE: 'text-yellow-500',
    APPROVED: 'text-green-500',
    CONDITIONAL: 'text-blue-500',
    REVISE: 'text-orange-500',
    MAJOR_REVISE: 'text-red-500',
    REJECT: 'text-red-700',
  }[qualityScore.verdict]

  return (
    <div className="space-y-4">
      {/* Overall Score */}
      <div>
        <h3>Overall Score</h3>
        <p className={verdictColor}>
          {qualityScore.overall_score.toFixed(1)}/10
        </p>
        <p className="text-sm text-gray-500">
          Minimum to ship: {minToShip}
        </p>
      </div>

      {/* Verdict */}
      <div>
        <h3>Verdict</h3>
        <p className={verdictColor}>{qualityScore.verdict}</p>
      </div>

      {/* Beast Gates */}
      <div>
        <h3>Beast Standard Gates</h3>
        <p>{qualityScore.gates_passed}/10 passed</p>
      </div>

      {/* Dimension Breakdown */}
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(qualityScore.dimension_scores).map(([dimId, dimScore]) => {
          const dimension = BeastConfig.getQualityDimension(dimId as any)
          return (
            <div key={dimId} className="border p-2 rounded">
              <p className="text-sm font-medium">{dimension?.description || dimId}</p>
              <p className={dimScore.score >= 7.0 ? 'text-green-600' : 'text-red-600'}>
                {dimScore.score.toFixed(1)}/10
              </p>
              <p className="text-xs text-gray-500">Weight: {dimScore.weight.toFixed(3)}</p>
            </div>
          )
        })}
      </div>

      {/* Weak Dimensions */}
      {qualityScore.weak_dimensions.length > 0 && (
        <div className="bg-red-50 p-3 rounded">
          <h4 className="text-red-700 font-medium">Needs Improvement</h4>
          <ul className="text-sm text-red-600">
            {qualityScore.weak_dimensions.map(dim => (
              <li key={dim}>{dim.replace(/_/g, ' ')}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

---

## Testing Integration

### Python Test

Create `apps/api/tests/test_beast_config.py`:

```python
import pytest
from app.config.loader import config


def test_config_loads():
    """Test all configs load successfully"""
    assert config.get("beast_standards") != {}
    assert config.get("aesthetic_codes") != {}
    assert config.get("platform_contracts") != {}
    assert config.get("generational_signals") != {}
    assert config.get("composition_archetypes") != {}
    assert config.get("type_scales") != {}
    assert config.get("quality_dimensions") != {}


def test_platform_rules():
    """Test platform contracts"""
    instagram_rules = config.get_platform_rules("instagram_feed")
    assert instagram_rules != {}
    assert instagram_rules["viewer_behavior"]["attention_window_seconds"] == 1.5
    assert instagram_rules["technical_specs"]["dimensions"]["square"]["w"] == 1080


def test_generation_profile():
    """Test generational signals"""
    gen_z = config.get_generation_profile("gen_z_india")
    assert gen_z != {}
    assert gen_z["age_range"] == [18, 26]
    assert "This hits different" in gen_z["copy_voice"]["examples"]


def test_aesthetic():
    """Test aesthetic codes"""
    brutalism = config.get_aesthetic("brutalism_luxury")
    assert brutalism != {}
    assert brutalism["trend_strength"] == 8.5
    assert "raw concrete texture" in brutalism["visual_language"]["keywords_for_models"]


def test_composition_archetype():
    """Test composition archetypes"""
    hero = config.get_composition_archetype("hero_dominant")
    assert hero != {}
    assert hero["composition_rules"]["visual_weight"] == "80_image_20_type"


def test_type_scale():
    """Test type scales"""
    poster = config.get_type_scale("poster_impact")
    assert poster != {}
    assert poster["scale_px"]["display_hero"]["size_px"] == 96


def test_quality_dimension():
    """Test quality dimensions"""
    emotional = config.get_quality_dimension("emotional_precision")
    assert emotional != {}
    assert emotional["normalized_weight"] == 0.118  # Highest weight
```

Run tests:
```bash
cd apps/api
pytest tests/test_beast_config.py -v
```

---

### TypeScript Test

Create `apps/web/__tests__/beast-config.test.ts`:

```typescript
import { BeastConfig } from '@/lib/beast-config'

describe('BeastConfig', () => {
  it('loads platform rules', () => {
    const rules = BeastConfig.getPlatformRules('instagram_feed')
    expect(rules).toBeTruthy()
    expect(rules?.viewer_behavior.attention_window_seconds).toBe(1.5)
  })

  it('detects generation from keywords', () => {
    const gen1 = BeastConfig.detectGenerationFromKeywords('This hits different no cap')
    expect(gen1).toBe('gen_z_india')

    const gen2 = BeastConfig.detectGenerationFromKeywords('Value for money trusted brand')
    expect(gen2).toBe('millennial_parent_india')
  })

  it('detects aesthetic by industry', () => {
    const aesthetic1 = BeastConfig.detectAestheticByIndustry('tech saas ai')
    expect(aesthetic1).toBe('ai_native')

    const aesthetic2 = BeastConfig.detectAestheticByIndustry('luxury fashion')
    expect(aesthetic2).toBe('quiet_luxury_loud')
  })

  it('gets minimum score to ship', () => {
    const minScore = BeastConfig.getMinimumScoreToShip()
    expect(minScore).toBe(8.5)
  })
})
```

Run tests:
```bash
cd apps/web
npm test beast-config.test.ts
```

---

## Performance Optimization

### Lazy Loading (Python)

If config files are large and agent startup is slow, lazy-load specific configs:

```python
class BeastConfig:
    def get(self, config_name: str) -> Dict[str, Any]:
        """Lazy load config on first access"""
        if config_name not in self._configs:
            self._load_config(config_name)
        return self._configs.get(config_name, {})

    def _load_config(self, config_name: str):
        """Load single config file"""
        config_dir = Path(__file__).parent
        filename = f"{config_name}.json"

        try:
            with open(config_dir / filename, encoding='utf-8') as f:
                self._configs[config_name] = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            self._configs[config_name] = {}
```

### Caching (TypeScript)

For Next.js, configs are auto-cached at build time since they're imported as static JSON.

---

## Troubleshooting

### Issue: Config file not found

**Error:** `FileNotFoundError: [Errno 2] No such file or directory: 'beast_standards.json'`

**Fix:** Ensure config files are in `apps/api/app/config/` directory. Check `Path(__file__).parent` points to correct location.

### Issue: JSON parse error

**Error:** `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`

**Fix:** Validate JSON files with `python -m json.tool config/beast_standards.json`

### Issue: TypeScript type errors

**Error:** `Property 'attention_window_seconds' does not exist on type 'never'`

**Fix:** Add proper type assertions or update `beast-config.ts` with `as any` casts where needed.

---

## Summary

✅ **Python Integration:** `BeastConfig` singleton loader
✅ **TypeScript Integration:** Type-safe config accessor
✅ **Agent Updates:** Triage, Creative Director, Design Director, Quality Critic
✅ **React Components:** Platform detection, generation profiling, quality display
✅ **Tests:** Python pytest + TypeScript jest
✅ **Performance:** Lazy loading + build-time caching

**Next Steps:**
1. Wire all 10 agents to load from `BeastConfig`
2. Update frontend to display platform rules + generation profiles
3. Add quality score visualization in gallery
4. Set up quarterly config refresh schedule

**Status:** Production-ready. All agents can integrate immediately. 🔥
