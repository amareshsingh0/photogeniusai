"""
Cultural Intelligence Layer — 2025-2026 Aesthetic Zeitgeist

Encodes current aesthetic codes, generational signals, platform contracts.
Provides cultural fluency to all agents.

Philosophy:
- "Cultural fluency is not optional" — Senior Creative Director
- "The same asset must mean different things to different eyes while being one image"
- "Trends serve you. You don't serve trends."

Updated: April 7, 2026
Version: 2026-Q2
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Literal

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Aesthetic Zeitgeist 2026 (Active Aesthetic Codes)
# ══════════════════════════════════════════════════════════════════════════════

AESTHETIC_ZEITGEIST_2026 = {
    "brutalism_luxury": {
        "keywords": ["raw concrete", "premium materials", "unfinished edges", "honest construction", "industrial refinement"],
        "signal": "I'm so confident I don't need to try",
        "when_to_use": "Tech, architecture, design-forward brands, challenger brands",
        "avoid_with": "Beauty, food, wellness (too cold), traditional brands",
        "color_palette": ["#2B2B2B", "#F5F5F5", "#8B8B8B", "#1A1A1A"],
        "typography": "Bold sans-serif, heavy weights, intentional awkwardness",
        "composition": "Asymmetric grids, negative space as power move",
        "2026_trend_strength": 8.5  # 0-10 scale
    },

    "ai_native": {
        "keywords": ["procedural patterns", "generative textures", "algorithmic beauty", "glitch aesthetic", "parametric forms"],
        "signal": "I understand the tools of the future",
        "when_to_use": "Tech, AI tools, crypto, digital-first brands, innovation plays",
        "avoid_with": "Traditional finance, healthcare (trust signals needed), legacy brands",
        "color_palette": ["#00D4FF", "#FF00FF", "#00FF94", "#1A1A2E"],
        "typography": "Mono fonts, glitch effects, digital natives",
        "composition": "Grid-logic made visible, data-as-design",
        "2026_trend_strength": 9.2
    },

    "bio_organic_geometry": {
        "keywords": ["grown shapes", "organic curves", "natural patterns", "living forms", "biomimicry"],
        "signal": "Premium. Natural. Inevitable.",
        "when_to_use": "Wellness, sustainability, natural products, eco-brands",
        "avoid_with": "Tech, industrial (wrong material language), aggressive brands",
        "color_palette": ["#8B7355", "#C4A57B", "#2C5F2D", "#E8DCC4"],
        "typography": "Rounded sans, organic serifs, flowing forms",
        "composition": "Asymmetric but balanced, natural rhythm",
        "2026_trend_strength": 8.0
    },

    "post_ironic_sincerity": {
        "keywords": ["meaning it", "constructed authenticity", "self-aware earnestness", "radical honesty"],
        "signal": "We actually mean this",
        "when_to_use": "Gen Z brands, cultural movements, social causes, anti-corporate",
        "avoid_with": "Corporate B2B (too risky), traditional marketing",
        "color_palette": ["#FF6B6B", "#4ECDC4", "#FFE66D", "#1A535C"],
        "typography": "Handwritten, imperfect, human",
        "composition": "Intentional imperfection, authentic mistakes",
        "2026_trend_strength": 7.8
    },

    "retro_futures": {
        "keywords": ["Y2K chrome", "90s rave", "70s sci-fi", "analog remixed with digital", "VHS grain on 4K"],
        "signal": "I'm nostalgic for a future that never happened",
        "when_to_use": "Fashion, music, youth brands, nostalgia plays, Gen Z",
        "avoid_with": "Finance, healthcare (dated perception), B2B",
        "color_palette": ["#FF00FF", "#00FFFF", "#FFFF00", "#000000"],
        "typography": "Chrome effects, outline fonts, retro-futuristic",
        "composition": "Layered, dimensional, nostalgic depth",
        "2026_trend_strength": 8.8
    },

    "quiet_luxury_loud": {
        "keywords": ["understated until it isn't", "subtle flex", "know-you-know", "stealth wealth", "whispered premium"],
        "signal": "This doesn't need to explain itself",
        "when_to_use": "Premium fashion, luxury goods, high-end services, insider brands",
        "avoid_with": "Mass market (misses the point), youth brands",
        "color_palette": ["#F5F5DC", "#8B7355", "#2C2C2C", "#D4C5B9"],
        "typography": "Refined serifs, minimal sans, generous spacing",
        "composition": "White space as status signal, restrained hierarchy",
        "2026_trend_strength": 9.0
    },

    "cultural_maximalism": {
        "keywords": ["hyper-local", "regional pride", "specific over generic", "layered visual density", "festival color psychology"],
        "signal": "I know who I am. I'm proud of it. Come with me.",
        "when_to_use": "Local businesses, cultural campaigns, regional brands, India market",
        "avoid_with": "Global brands (too narrow), minimal aesthetics",
        "color_palette": ["#FF6B00", "#FFD700", "#8B0000", "#4B0082"],
        "typography": "Bold display, cultural scripts, layered text",
        "composition": "Dense but readable, richness not clutter",
        "2026_trend_strength": 7.5,
        "regional": "india"
    },

    "anti_aesthetic": {
        "keywords": ["deliberately ugly", "wrong choices done right", "calculated awkwardness", "post-perfect"],
        "signal": "Perfection reads as fake. Calculated imperfection reads as real.",
        "when_to_use": "Challenger brands, Gen Z, anti-establishment, disruptive plays",
        "avoid_with": "Luxury, professional services, trust-dependent brands",
        "color_palette": ["#FF69B4", "#32CD32", "#FFD700", "#8B008B"],
        "typography": "Clashing fonts, intentional misalignment",
        "composition": "Break all rules intentionally",
        "2026_trend_strength": 6.5
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Generational Signals (Target Audience Aesthetics)
# ══════════════════════════════════════════════════════════════════════════════

GENERATIONAL_SIGNALS = {
    "gen_z": {
        "born": "1997-2012",
        "aesthetic": "Texture, noise, lo-fi authenticity, anti-polish, layered chaos that makes sense",
        "values": ["authenticity", "transparency", "mental health", "climate", "diversity"],
        "color_preference": "High contrast, saturated, nostalgic (Y2K revival)",
        "typography": "Bold sans, mono fonts, glitch effects, handwritten",
        "anti_patterns": [
            "Stock photos (can smell it from a mile away)",
            "Corporate speak (sounds fake)",
            "Try-hard cool (cringe)",
            "Boomer aesthetics (dated)",
            "Overly polished (not real)"
        ],
        "attention_span": "0.5-1.5s",
        "platform_native": ["tiktok", "instagram", "snapchat"],
        "trust_signals": "Behind-the-scenes, real people, mistakes left in"
    },

    "millennials": {
        "born": "1981-1996",
        "aesthetic": "Clean, purposeful, sustainable-signaling, Instagram-worthy, curated",
        "values": ["sustainability", "experiences", "social justice", "wellness", "authenticity"],
        "color_preference": "Earthy tones, pastels, sage green, terracotta",
        "typography": "Clean sans, elegant serifs, generous spacing",
        "anti_patterns": [
            "Clutter (Marie Kondo exists)",
            "Irony without sincerity (post-ironic)",
            "Corporate ladder imagery (burned out)",
            "McMansion style (tacky)"
        ],
        "attention_span": "1.5-3s",
        "platform_native": ["instagram", "facebook", "linkedin"],
        "trust_signals": "Sustainability badges, founder stories, purpose-driven"
    },

    "gen_alpha": {
        "born": "2013+",
        "aesthetic": "Dimensional, interactive-feeling, maximalist but curated, AI-native, gamified",
        "values": ["digital-first", "gamified everything", "creator economy", "AI tools", "virtual worlds"],
        "color_preference": "Hyper-saturated, neon, holographic, RGB",
        "typography": "3D text, animated feels, futuristic",
        "anti_patterns": [
            "Flat design (boring)",
            "Static imagery (not engaging)",
            "Analog nostalgia (what's a VHS?)",
            "2D thinking (we live in 3D)"
        ],
        "attention_span": "0.3-0.8s",
        "platform_native": ["roblox", "youtube", "tiktok"],
        "trust_signals": "Gamification, creator collab, interactive elements"
    },

    "gen_x": {
        "born": "1965-1980",
        "aesthetic": "Straightforward, skeptical of hype, values function, pragmatic",
        "values": ["independence", "work-life balance", "skepticism", "pragmatism"],
        "color_preference": "Muted, practical, not flashy",
        "typography": "Readable, no-nonsense, classic",
        "anti_patterns": [
            "Hype without substance",
            "Fake authenticity",
            "Over-the-top enthusiasm"
        ],
        "attention_span": "3-5s",
        "platform_native": ["facebook", "linkedin", "email"],
        "trust_signals": "Proof, testimonials, track record"
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Platform Aesthetic Contracts (What Each Platform Expects)
# ══════════════════════════════════════════════════════════════════════════════

PLATFORM_AESTHETIC_CONTRACTS = {
    "tiktok": {
        "format": "vertical 9:16",
        "attention_window": "0.5s",
        "aesthetic": "text-forward, meme-fluent, movement-implied, raw edges, lo-fi authenticity",
        "forbidden": [
            "Horizontal layouts",
            "Small text (must be HUGE)",
            "Silent-first design (TikTok is sound-on)",
            "Corporate polish (reads as ad, gets skipped)"
        ],
        "success_pattern": "Hook in first 0.3s, text overlay, trending sounds, raw aesthetic",
        "color_strategy": "High contrast, saturated, thumb-stopping",
        "typography": "Bold, oversized, overlapping, animated feel"
    },

    "instagram": {
        "format": "square 1:1 or portrait 4:5",
        "attention_window": "1.5s",
        "aesthetic": "editorial quality, color story, curated grids, aspirational, polished but not perfect",
        "forbidden": [
            "Low-res imagery",
            "Text-heavy (keep it visual)",
            "Pixelated or blurry",
            "Off-brand color (breaks grid)"
        ],
        "success_pattern": "Strong color palette, clear subject, save-worthy, grid-aware",
        "color_strategy": "Cohesive palette, 60-30-10 rule, brand consistency",
        "typography": "Minimal text, clean sans, elegant serifs"
    },

    "facebook": {
        "format": "landscape 1.91:1 or square 1:1",
        "attention_window": "2s",
        "aesthetic": "clean, family-friendly, readable, warm, community-focused",
        "forbidden": [
            "Aggressive sales language",
            "Clickbait tactics",
            "Too edgy (audience skews older)"
        ],
        "success_pattern": "Clear benefit, warm visuals, community feel",
        "color_strategy": "Warm tones, approachable, not aggressive",
        "typography": "Readable, friendly, classic"
    },

    "linkedin": {
        "format": "landscape 1.91:1 or 1:1",
        "attention_window": "3s",
        "aesthetic": "authority signals, restraint, no-try-hard professionalism, data-driven, thought leadership",
        "forbidden": [
            "Memes (unless industry-specific humor)",
            "Casual slang",
            "Emoji overload",
            "Party photos or unprofessional"
        ],
        "success_pattern": "Professional but human, data viz, insights, expertise",
        "color_strategy": "Corporate blues, grays, restrained palette",
        "typography": "Professional sans, readable, hierarchy clear"
    },

    "pinterest": {
        "format": "portrait 2:3",
        "attention_window": "2s",
        "aesthetic": "aspirational, high-craft, lifestyle integration, saveable, tutorial-friendly",
        "forbidden": [
            "Text-only (must have visual)",
            "Ads that look like ads",
            "Low-effort screenshots",
            "Stock photos without context"
        ],
        "success_pattern": "DIY-able, aspirational but achievable, step-by-step visual",
        "color_strategy": "Lifestyle palettes, Pinterest-core pastels",
        "typography": "Overlay text, step numbers, clear labels"
    },

    "youtube": {
        "format": "landscape 16:9",
        "attention_window": "2s (thumbnail critical)",
        "aesthetic": "face + text combo, emotion-first, high contrast, scroll-stop thumbnails",
        "forbidden": [
            "No face (thumbnails with faces perform 40% better)",
            "Small text (won't read on mobile)",
            "Low emotion (boring = skip)",
            "Generic stock imagery"
        ],
        "success_pattern": "Expressive face, bold text, intrigue, high contrast",
        "color_strategy": "Bold primaries, high contrast, readable at small size",
        "typography": "Bold, impact fonts, outlined text"
    },

    "billboard": {
        "format": "wide landscape 3:1 or wider",
        "attention_window": "3s at 80mph",
        "aesthetic": "single idea, readable at distance, 3-7 words max, bold color, minimal elements",
        "forbidden": [
            "Small text (must be MASSIVE)",
            "Multiple messages (pick ONE)",
            "Complex visuals (won't read at speed)",
            "QR codes (dangerous at 80mph)"
        ],
        "success_pattern": "One image, one message, one color, maximum contrast",
        "color_strategy": "High contrast, single bold color, legible from 500ft",
        "typography": "Ultra bold, sans serif, maximum size"
    },

    "twitter_x": {
        "format": "landscape 2:1 or 16:9",
        "attention_window": "0.8s",
        "aesthetic": "punchy, meme-aware, text-forward, cultural commentary",
        "forbidden": [
            "Corporate speak (gets ratio'd)",
            "Out-of-touch references",
            "Overly promotional"
        ],
        "success_pattern": "Witty, cultural moment, shareable, quote-tweet worthy",
        "color_strategy": "Bold, meme-adjacent, high contrast",
        "typography": "Bold text overlay, screenshot aesthetic"
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Cultural Intelligence API
# ══════════════════════════════════════════════════════════════════════════════

class CulturalIntelligence:
    """
    Cultural Intelligence Layer — provides aesthetic guidance to agents.
    """

    @staticmethod
    def detect_aesthetic(
        industry: str,
        audience: str,
        goal: str,
        platform: str
    ) -> Dict:
        """
        Auto-detect best aesthetic for this brief.

        Returns:
        {
            "primary_aesthetic": "brutalism_luxury",
            "aesthetic_data": {...},
            "confidence": 0.87,
            "rationale": "Tech industry + Gen Z audience = AI-native aesthetic"
        }
        """
        industry_lower = industry.lower()
        audience_lower = audience.lower()
        platform_lower = platform.lower()

        # Tech + Modern → AI Native or Brutalism Luxury
        if any(kw in industry_lower for kw in ["tech", "saas", "ai", "crypto", "digital"]):
            if "gen z" in audience_lower or "youth" in audience_lower:
                return {
                    "primary_aesthetic": "ai_native",
                    "aesthetic_data": AESTHETIC_ZEITGEIST_2026["ai_native"],
                    "confidence": 0.9,
                    "rationale": "Tech industry + Gen Z audience → AI-native aesthetic (2026 trend strength 9.2)"
                }
            else:
                return {
                    "primary_aesthetic": "brutalism_luxury",
                    "aesthetic_data": AESTHETIC_ZEITGEIST_2026["brutalism_luxury"],
                    "confidence": 0.85,
                    "rationale": "Tech industry + mature audience → Brutalism luxury (confident minimalism)"
                }

        # Luxury / Fashion → Quiet Luxury Loud
        if any(kw in industry_lower for kw in ["luxury", "fashion", "premium", "high-end"]):
            return {
                "primary_aesthetic": "quiet_luxury_loud",
                "aesthetic_data": AESTHETIC_ZEITGEIST_2026["quiet_luxury_loud"],
                "confidence": 0.92,
                "rationale": "Luxury/fashion industry → Quiet luxury loud (2026 trend strength 9.0)"
            }

        # Wellness / Natural → Bio Organic
        if any(kw in industry_lower for kw in ["wellness", "health", "organic", "natural", "eco"]):
            return {
                "primary_aesthetic": "bio_organic_geometry",
                "aesthetic_data": AESTHETIC_ZEITGEIST_2026["bio_organic_geometry"],
                "confidence": 0.88,
                "rationale": "Wellness/natural industry → Bio-organic geometry"
            }

        # Youth / Music / Fashion → Retro Futures
        if "gen z" in audience_lower and any(kw in industry_lower for kw in ["music", "fashion", "youth", "streetwear"]):
            return {
                "primary_aesthetic": "retro_futures",
                "aesthetic_data": AESTHETIC_ZEITGEIST_2026["retro_futures"],
                "confidence": 0.89,
                "rationale": "Gen Z + fashion/music → Retro futures (Y2K revival, trend strength 8.8)"
            }

        # India / Cultural → Cultural Maximalism
        if "india" in audience_lower or "indian" in industry_lower:
            return {
                "primary_aesthetic": "cultural_maximalism",
                "aesthetic_data": AESTHETIC_ZEITGEIST_2026["cultural_maximalism"],
                "confidence": 0.80,
                "rationale": "India market → Cultural maximalism (regional pride, Modern Masala)"
            }

        # Default: Platform-aware fallback
        if platform_lower == "tiktok":
            return {
                "primary_aesthetic": "post_ironic_sincerity",
                "aesthetic_data": AESTHETIC_ZEITGEIST_2026["post_ironic_sincerity"],
                "confidence": 0.70,
                "rationale": "TikTok platform → Post-ironic sincerity (Gen Z native)"
            }

        # Generic fallback
        return {
            "primary_aesthetic": "brutalism_luxury",
            "aesthetic_data": AESTHETIC_ZEITGEIST_2026["brutalism_luxury"],
            "confidence": 0.60,
            "rationale": "Default: Brutalism luxury (safe modern aesthetic)"
        }

    @staticmethod
    def get_generational_signals(audience: str) -> Dict:
        """Get aesthetic signals for target generation."""
        audience_lower = audience.lower()

        if "gen z" in audience_lower or "18-24" in audience_lower:
            return GENERATIONAL_SIGNALS["gen_z"]
        elif "millennial" in audience_lower or "25-40" in audience_lower:
            return GENERATIONAL_SIGNALS["millennials"]
        elif "gen alpha" in audience_lower or "under 18" in audience_lower:
            return GENERATIONAL_SIGNALS["gen_alpha"]
        elif "gen x" in audience_lower or "40-55" in audience_lower:
            return GENERATIONAL_SIGNALS["gen_x"]
        else:
            return GENERATIONAL_SIGNALS["millennials"]  # Default

    @staticmethod
    def get_platform_contract(platform: str) -> Dict:
        """Get aesthetic contract for platform."""
        platform_lower = platform.lower()

        for key in PLATFORM_AESTHETIC_CONTRACTS.keys():
            if key in platform_lower:
                return PLATFORM_AESTHETIC_CONTRACTS[key]

        # Default fallback
        return {
            "format": "4:5",
            "attention_window": "2s",
            "aesthetic": "balanced, clear hierarchy",
            "forbidden": ["clutter", "low-res"],
            "success_pattern": "clear message, good design",
            "color_strategy": "cohesive palette",
            "typography": "readable hierarchy"
        }

    @staticmethod
    def enrich_with_cultural_context(
        creative_bible: Dict,
        industry: str,
        audience: str,
        platform: str
    ) -> Dict:
        """
        Enrich Creative Bible with cultural intelligence.

        Adds:
        - Detected aesthetic
        - Generational signals
        - Platform contract
        - Cultural keywords
        """
        aesthetic_result = CulturalIntelligence.detect_aesthetic(industry, audience, "", platform)
        gen_signals = CulturalIntelligence.get_generational_signals(audience)
        platform_contract = CulturalIntelligence.get_platform_contract(platform)

        return {
            **creative_bible,
            "cultural_intelligence": {
                "aesthetic_direction": aesthetic_result["primary_aesthetic"],
                "aesthetic_confidence": aesthetic_result["confidence"],
                "aesthetic_rationale": aesthetic_result["rationale"],
                "aesthetic_keywords": aesthetic_result["aesthetic_data"]["keywords"],
                "generation_target": audience,
                "generation_values": gen_signals["values"],
                "generation_anti_patterns": gen_signals["anti_patterns"],
                "platform_aesthetic_contract": platform_contract["aesthetic"],
                "platform_forbidden": platform_contract["forbidden"],
                "platform_attention_window": platform_contract["attention_window"],
                "color_strategy_hint": aesthetic_result["aesthetic_data"]["color_palette"],
                "typography_hint": aesthetic_result["aesthetic_data"]["typography"]
            }
        }


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def get_cultural_intelligence(
    industry: str,
    audience: str,
    goal: str,
    platform: str
) -> Dict:
    """
    Public API: Get cultural intelligence for this brief.
    """
    ci = CulturalIntelligence()
    aesthetic = ci.detect_aesthetic(industry, audience, goal, platform)
    gen_signals = ci.get_generational_signals(audience)
    platform_contract = ci.get_platform_contract(platform)

    return {
        "aesthetic": aesthetic,
        "generational_signals": gen_signals,
        "platform_contract": platform_contract,
        "version": "2026-Q2",
        "last_updated": "2026-04-07"
    }
