"""
Brand Intelligence Agent — The DNA Keeper

Comprehensive brand DNA extraction, color science, visual equity protection.
Reference: Agent Skill/BrandIntelligenceAgent.md

Phases:
1. Brand Signal Extraction (from explicit inputs, contextual signals, or zero-brand mode)
2. Color Science (full palette system with 60-30-10, cultural psychology, accessibility)
3. Typography DNA (font classification, personality mapping, size scales)
4. Visual Equity Mapping (recognizable elements without logo)
5. Competitive Landscape Palette (category conventions vs disruption)
6. Seasonal/Festival Color Injection (Indian festivals + global moments)
7. Brand Intelligence Output Package (structured JSON for downstream agents)
"""
from __future__ import annotations

import logging
import re
import colorsys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Import brand intelligence service for database operations
try:
    from app.services.brand_intelligence_service import (
        get_brand_by_name,
        save_brand_intelligence,
        increment_brand_usage,
    )
    _DB_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning("[brand_intel_agent] Database service not available: %s", e)
    _DB_SERVICE_AVAILABLE = False

# ── Color Psychology Database ────────────────────────────────────────────────

COLOR_PSYCHOLOGY = {
    "red": {
        "emotion": "urgency, appetite, passion, danger, power, stop-and-look",
        "cultural": {
            "india": "auspicious, celebration, marriage, Sindoor",
            "west": "danger, passion, excitement, Valentine's Day",
            "middle_east": "strength, courage, danger",
            "china": "luck, prosperity, celebration"
        }
    },
    "orange": {
        "emotion": "warmth, energy, enthusiasm, harvest, affordability, friendliness",
        "cultural": {
            "india": "saffron, spirituality, courage, sacrifice",
            "west": "autumn, creativity, enthusiasm",
            "middle_east": "mourning (in some regions)",
        }
    },
    "yellow": {
        "emotion": "optimism, clarity, warning, sunshine, intellect, attention",
        "cultural": {
            "india": "learning, turmeric, auspicious (Vasant Panchami)",
            "west": "caution, happiness, energy",
            "china": "imperial, prosperity",
        }
    },
    "green": {
        "emotion": "growth, health, money, nature, permission, calm, safety",
        "cultural": {
            "india": "life, nature, harvest, prosperity",
            "west": "environment, money, go signal",
            "middle_east": "Islam, paradise, fertility",
        }
    },
    "blue": {
        "emotion": "trust, reliability, calm, technology, authority, depth, loyalty",
        "cultural": {
            "india": "Krishna, divinity, calmness",
            "west": "corporate, trust, stability",
            "middle_east": "protection, spirituality",
        }
    },
    "purple": {
        "emotion": "luxury, mystery, creativity, spirituality, ambition, exclusivity",
        "cultural": {
            "india": "royalty, spirituality, mourning",
            "west": "luxury, creativity, royalty",
            "middle_east": "wealth, sophistication",
        }
    },
    "pink": {
        "emotion": "warmth, softness, romance, playfulness, modernity (Gen Z coding)",
        "cultural": {
            "india": "youth, romance, modern femininity",
            "west": "femininity, playfulness, millennial/Gen Z",
            "middle_east": "modernity, femininity",
        }
    },
    "black": {
        "emotion": "sophistication, power, elegance, mystery, premium, authority",
        "cultural": {
            "india": "Kali, protection, sometimes mourning",
            "west": "luxury, formality, sophistication",
            "middle_east": "authority, formality",
        }
    },
    "white": {
        "emotion": "purity, simplicity, minimalism, space, clean, medical, peace",
        "cultural": {
            "india": "purity, mourning, simplicity",
            "west": "purity, weddings, cleanliness",
            "middle_east": "purity, peace",
        }
    },
    "gold": {
        "emotion": "premium, success, achievement, heritage, warmth, aspiration",
        "cultural": {
            "india": "wealth, divinity, auspiciousness (Lakshmi)",
            "west": "luxury, achievement, wealth",
            "middle_east": "wealth, hospitality",
        }
    },
}

# ── Festival Palette Library (India + Global) ────────────────────────────────

FESTIVAL_PALETTES = {
    "diwali": {
        "primary": {"hex": "#F4A62A", "name": "Diya gold"},
        "secondary": {"hex": "#E05B0E", "name": "Deep amber flame"},
        "accent": [
            {"hex": "#1A1035", "name": "Night sky deep navy"},
            {"hex": "#8B1A4A", "name": "Rani pink"},
            {"hex": "#FFE57A", "name": "Champagne gold"},
            {"hex": "#FF6B35", "name": "Firecrackers orange"}
        ],
        "photography_filter": "warm golden, +15 saturation, deep shadows",
        "keywords": ["celebration", "lights", "prosperity", "family", "sweets"]
    },
    "holi": {
        "primary": None,  # Rotating — no fixed dominant
        "accent": [
            {"hex": "#E91E63", "name": "Hot magenta"},
            {"hex": "#FFEB3B", "name": "Electric yellow"},
            {"hex": "#00BCD4", "name": "Electric blue"},
            {"hex": "#FF5722", "name": "Vibrant orange"},
        ],
        "background": {"hex": "#FFFFFF", "name": "Clean white"},
        "photography_filter": "motion blur, powder mid-air, joy-expression faces",
        "keywords": ["colors", "joy", "playfulness", "spring", "unity"]
    },
    "navratri": {
        "primary": {"hex": "#E63946", "name": "Celebration red"},
        "secondary": {"hex": "#F4D03F", "name": "Marigold gold"},
        "accent": [
            {"hex": "#2E86AB", "name": "Royal blue"},
            {"hex": "#6B4226", "name": "Earth ochre"},
            {"hex": "#FF7F50", "name": "Coral"},
        ],
        "keywords": ["garba", "dance", "energy", "tradition", "devotion"]
    },
    "eid": {
        "primary": {"hex": "#1D6B48", "name": "Deep mosque green"},
        "secondary": {"hex": "#C9A84C", "name": "Gold crescent"},
        "accent": [
            {"hex": "#FFFFFF", "name": "Purity white"},
            {"hex": "#8B4513", "name": "Henna earth"},
        ],
        "keywords": ["family", "togetherness", "prayer", "celebration", "charity"]
    },
    "christmas": {
        "primary": {"hex": "#CC0000", "name": "Traditional red"},
        "secondary": {"hex": "#1A5C38", "name": "Forest green"},
        "accent": [
            {"hex": "#FFFFFF", "name": "Snow white"},
            {"hex": "#FFD700", "name": "Champagne gold"},
        ],
        "photography_filter": "fairy lights bokeh, warm interior, gift unwrapping moment",
        "keywords": ["gifts", "family", "warmth", "lights", "joy"]
    },
    "christmas_luxury": {
        "primary": {"hex": "#0F3D2E", "name": "Deep forest green"},
        "secondary": {"hex": "#C9B037", "name": "Champagne gold"},
        "accent": [
            {"hex": "#1A1A1A", "name": "Obsidian"},
        ],
        "keywords": ["elegance", "premium", "sophistication", "luxury"]
    },
}

# ── Category Palette Conventions ─────────────────────────────────────────────

CATEGORY_PALETTES = {
    "fintech": {
        "dominant": ["#0066FF", "#00C853"],  # Blue (trust), Green (money/growth)
        "disruption": ["#8B5CF6", "#000000", "#FF6B6B"],  # Purple (Nubank), Black (Robinhood), Coral (Monzo)
        "cliche": "Generic blue gradient + white sans font",
        "notes": "Trust signals mandatory, but differentiation key"
    },
    "beauty": {
        "dominant": ["#FFFFFF", "#F5E6D3", "#FFB6C1"],  # White/beige (clean), Pink (feminine)
        "premium": ["#000000", "#1A237E", "#2E7D32"],  # Black, deep navy, forest green
        "disruption": ["#FF6F00", "#6A1B9A", "#00ACC1"],  # Bold graphic (Ordinary, Glossier, Drunk Elephant)
        "cliche": "Millennial pink + gold = dated",
        "notes": "Clean minimalism for premium, bold graphics for disruptors"
    },
    "food": {
        "dominant": ["#FF5722", "#FF9800", "#FFC107"],  # Red, orange, yellow (appetite triggers)
        "premium": ["#1A1A1A", "#4E342E"],  # Dark backgrounds
        "disruption": "Bold illustration, anti-food-photography",
        "cliche": "Marble + gold = table stake, not premium",
        "notes": "Warm tones trigger appetite, dark = premium positioning"
    },
    "saas": {
        "dominant": ["#2196F3", "#9C27B0"],  # Blue (trust), Purple (innovation)
        "dark_mode": ["#121212", "#1E1E1E"],  # Deep charcoal/navy
        "disruption": ["#635BFF", "#000000", "#FF6F3C"],  # Bright gradients (Stripe), Mono (Linear), Warm (Notion)
        "cliche": "Generic purple-to-blue gradient startup aesthetic",
        "notes": "Blue/purple saturated, modern gradients or monochrome disruption"
    },
    "fashion": {
        "luxury": ["#FFFFFF", "#000000", "#F5F5F5"],  # White space, silence as design
        "streetwear": ["#000000", "#FF0000", "#00FF00"],  # Maximum density, bold color blocking
        "d2c": ["#8B7355", "#E8D5C4"],  # Lifestyle, authentic, story-first
        "cliche": "Helvetica on white = either luxury or laziness",
        "notes": "Luxury = space, streetwear = density, D2C = authenticity"
    },
    "fitness": {
        "dominant": ["#FF5722", "#4CAF50", "#000000"],  # Energy red, growth green, bold black
        "premium": ["#1A1A1A", "#FFD54F"],  # Dark + gold for premium positioning
        "notes": "Energy, movement, transformation signals"
    },
}

# ── Typography Classification Matrix ─────────────────────────────────────────

TYPOGRAPHY_PERSONALITY_MAP = {
    "authoritative_modern": ["Neue Haas Grotesk", "Aktiv Grotesk", "Favorit", "Inter", "Montserrat"],
    "authoritative_heritage": ["Canela", "Editorial New", "Playfair Display", "Baskerville"],
    "playful_young": ["Recoleta", "Roc Grotesk", "Syne", "Poppins"],
    "playful_warm": ["Freight Display", "Tiempos", "Cormorant", "Lora"],
    "premium_quiet": ["Baskerville Nova", "Garamond", "Caslon", "Spectral"],
    "premium_statement": ["Druk", "Acumin Variable", "Styrene", "Bebas Neue"],
    "street_energy": ["Monument Extended", "Cabinet Grotesk", "Plus Jakarta", "Oswald"],
    "technical_precision": ["IBM Plex", "Space Grotesk", "DM Mono", "JetBrains Mono"],
    "organic_natural": ["Söhne", "Libre Baskerville", "Domaine", "Merriweather"],
    "cultural_indian": ["Hind", "Mukta", "Rozha One", "Tiro Devanagari"],
}


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert #RRGGBB to (R, G, B) tuple."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (0, 0, 0)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert (R, G, B) to #RRGGBB."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}".upper()


def _rgb_to_hsl(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Convert RGB to HSL (H in degrees 0-360, S/L as 0-100 percentages)."""
    r, g, b = [x / 255.0 for x in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (int(h * 360), int(s * 100), int(l * 100))


def _get_dominant_color_name(hex_str: str) -> str:
    """Map hex to color psychology category."""
    rgb = _hex_to_rgb(hex_str)
    h, s, l = _rgb_to_hsl(rgb)

    # Low saturation = grayscale
    if s < 10:
        if l > 90:
            return "white"
        elif l < 10:
            return "black"
        else:
            return "gray"

    # High luminosity + high saturation
    if l > 70 and s > 40:
        if 30 <= h < 90:
            return "yellow"
        elif 280 <= h < 330:
            return "pink"

    # Color hue mapping
    if 345 <= h or h < 15:
        return "red"
    elif 15 <= h < 45:
        return "orange"
    elif 45 <= h < 80:
        return "yellow"
    elif 80 <= h < 165:
        return "green"
    elif 165 <= h < 250:
        return "blue"
    elif 250 <= h < 280:
        return "purple"
    elif 280 <= h < 345:
        return "pink"

    return "unknown"


def _get_color_psychology(hex_str: str, region: str = "india") -> Dict:
    """Get psychological + cultural meaning of color."""
    color_name = _get_dominant_color_name(hex_str)
    psych = COLOR_PSYCHOLOGY.get(color_name, {})

    return {
        "color_name": color_name,
        "emotion": psych.get("emotion", "neutral"),
        "cultural_meaning": psych.get("cultural", {}).get(region, "context-dependent"),
    }


def _get_contrast_safe_text(hex_bg: str) -> str:
    """Return #FFFFFF or #000000 based on WCAG contrast."""
    rgb = _hex_to_rgb(hex_bg)

    # Calculate relative luminance (WCAG formula)
    def _lin(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])

    # White text on dark bg, black text on light bg
    return "#FFFFFF" if lum < 0.5 else "#000000"


def _expand_palette_60_30_10(primary_hex: str, secondary_hex: str, accent_hex: str) -> Dict:
    """Expand to 60-30-10 usage ratio."""
    return {
        "dominant_60": {
            "hex": primary_hex,
            "usage": "backgrounds, large shapes, hero sections",
            "percentage": 60,
        },
        "secondary_30": {
            "hex": secondary_hex,
            "usage": "supporting elements, containers, cards",
            "percentage": 30,
        },
        "accent_10": {
            "hex": accent_hex,
            "usage": "CTAs, highlights, focal points, links",
            "percentage": 10,
        },
    }


def _detect_category(industry: str, tone: str) -> str:
    """Map industry to category palette conventions."""
    industry_lower = industry.lower()

    if any(kw in industry_lower for kw in ["fintech", "finance", "banking", "payment"]):
        return "fintech"
    elif any(kw in industry_lower for kw in ["beauty", "skincare", "cosmetics", "makeup"]):
        return "beauty"
    elif any(kw in industry_lower for kw in ["food", "restaurant", "cafe", "beverage"]):
        return "food"
    elif any(kw in industry_lower for kw in ["saas", "software", "tech", "app"]):
        return "saas"
    elif any(kw in industry_lower for kw in ["fashion", "clothing", "apparel"]):
        if tone in ["luxury", "elegant", "premium"]:
            return "fashion"  # Will use luxury sub-category
        elif tone in ["bold", "energetic", "playful"]:
            return "fashion"  # Will use streetwear sub-category
        return "fashion"
    elif any(kw in industry_lower for kw in ["fitness", "gym", "wellness", "health"]):
        return "fitness"

    return "general"


def _detect_festival(prompt: str, is_festival: bool, festival_name: str) -> Optional[Dict]:
    """Detect if generation is for a festival and return palette."""
    if not is_festival and not festival_name:
        # Auto-detect from prompt keywords
        prompt_lower = prompt.lower()

        if any(kw in prompt_lower for kw in ["diwali", "deepavali", "diya"]):
            festival_name = "diwali"
        elif any(kw in prompt_lower for kw in ["holi", "color festival"]):
            festival_name = "holi"
        elif any(kw in prompt_lower for kw in ["navratri", "garba", "dandiya"]):
            festival_name = "navratri"
        elif any(kw in prompt_lower for kw in ["eid", "ramadan"]):
            festival_name = "eid"
        elif any(kw in prompt_lower for kw in ["christmas", "xmas"]):
            if any(kw in prompt_lower for kw in ["luxury", "premium", "elegant"]):
                festival_name = "christmas_luxury"
            else:
                festival_name = "christmas"

    if festival_name:
        festival_palette = FESTIVAL_PALETTES.get(festival_name.lower())
        if festival_palette:
            return {
                "active": True,
                "occasion": festival_name,
                "palette": festival_palette,
                "integration_rule": "Brand primary + festival accent (not brand replaced)",
            }

    return None


async def brand_intelligence_agent(
    prompt: str,
    triage: Dict,
    brand_kit: Optional[Dict] = None,
) -> Dict:
    """
    PHASE 1-7: Complete Brand Intelligence extraction.

    Returns comprehensive brand DNA package including:
    - Full palette system (60-30-10, cultural psychology, accessibility)
    - Typography classification
    - Visual equity elements
    - Competitive positioning
    - Seasonal/festival injection (if applicable)
    - Prompt engineer notes
    """

    # ── PHASE 1: Brand Signal Extraction ─────────────────────────────────────

    brand_kit = brand_kit or {}
    brand_name = brand_kit.get("brand_name", "")

    # Try to load from database first
    if brand_name and _DB_SERVICE_AVAILABLE:
        try:
            db_brand = await get_brand_by_name(brand_name)
            if db_brand:
                logger.info("[brand_intel_agent] Loaded brand from database: %s", brand_name)
                # Track usage
                await increment_brand_usage(brand_name)
                # Return cached brand intelligence
                return {"brand_intelligence": db_brand}
        except Exception as e:
            logger.warning("[brand_intel_agent] Database load failed: %s", e)

    confidence_level = "high" if brand_kit.get("primary_color") else "inferred"

    # If brand_kit has colors, use them; else infer from industry
    primary_hex = brand_kit.get("primary_color", "#6C63FF")
    secondary_hex = brand_kit.get("secondary_color", "#4FACFE")

    # Auto-generate accent color (complementary to primary)
    primary_rgb = _hex_to_rgb(primary_hex)
    primary_h, primary_s, primary_l = _rgb_to_hsl(primary_rgb)

    # Accent: complementary hue (opposite on color wheel), higher saturation
    accent_h = (primary_h + 180) % 360
    accent_rgb = colorsys.hls_to_rgb(accent_h / 360, 0.5, min(1.0, (primary_s + 20) / 100))
    accent_hex = _rgb_to_hex(tuple(int(c * 255) for c in accent_rgb))

    # ── PHASE 2: Color Science — Full Palette System ────────────────────────

    palette_system = {}

    for role, hex_val in [("primary", primary_hex), ("secondary", secondary_hex), ("accent", accent_hex)]:
        rgb = _hex_to_rgb(hex_val)
        hsl = _rgb_to_hsl(rgb)
        psych = _get_color_psychology(hex_val, region="india")

        palette_system[role] = {
            "hex": hex_val,
            "rgb": list(rgb),
            "hsl": list(hsl),
            "psychological_signal": psych["emotion"],
            "cultural_meaning": {
                "india": psych["cultural_meaning"],
            },
            "contrast_safe_text": _get_contrast_safe_text(hex_val),
        }

    # Neutral colors
    palette_system["neutral_light"] = {
        "hex": "#F5F5F5",
        "usage": "backgrounds, cards, dividers",
    }
    palette_system["neutral_dark"] = {
        "hex": "#1A1A1A",
        "usage": "text, headers, dark mode",
    }

    # 60-30-10 expansion
    usage_ratios = _expand_palette_60_30_10(primary_hex, secondary_hex, accent_hex)

    # ── PHASE 3: Typography DNA ──────────────────────────────────────────────

    tone = triage.get("tone", brand_kit.get("tone", "professional"))
    font_style = brand_kit.get("font_style", "clean_sans")

    # Map tone + industry to typography personality
    typography_personality = "authoritative_modern"  # default

    if tone in ["luxury", "elegant", "premium"]:
        typography_personality = "premium_quiet" if "minimal" in prompt.lower() else "premium_statement"
    elif tone in ["playful", "energetic", "fun"]:
        typography_personality = "playful_young"
    elif tone in ["bold", "street", "edgy"]:
        typography_personality = "street_energy"
    elif tone in ["technical", "precise"]:
        typography_personality = "technical_precision"
    elif "india" in prompt.lower() or triage.get("industry") in ["cultural", "traditional"]:
        typography_personality = "cultural_indian"

    recommended_fonts = TYPOGRAPHY_PERSONALITY_MAP.get(typography_personality, ["Montserrat", "Inter"])

    typography_system = {
        "personality": typography_personality,
        "display": {
            "font_family": recommended_fonts[0],
            "weight_options": [700, 900],
            "case_rule": "ALL CAPS" if tone in ["bold", "energetic"] else "Title Case",
            "tracking": "tight" if typography_personality == "premium_statement" else "normal",
        },
        "headline": {
            "font_family": recommended_fonts[0],
            "weight_options": [600, 700],
            "case_rule": "Title Case",
        },
        "body": {
            "font_family": recommended_fonts[1] if len(recommended_fonts) > 1 else recommended_fonts[0],
            "weight_options": [400, 600],
        },
        "size_scale": {
            "display_min_px": 48,
            "headline_min_px": 24,
            "body_min_px": 14,
            "caption_min_px": 11,
        },
    }

    # ── PHASE 4: Visual Equity Mapping ───────────────────────────────────────

    equity_elements = {
        "must_always": [],
        "must_never": [],
        "logo_placement": brand_kit.get("logo_placement", "top-left"),
    }

    # Add brand-specific equity rules if known brand
    if brand_name:
        equity_elements["must_always"].append(f"Use {brand_name} brand colors consistently")

    # Anti-patterns based on category
    category = _detect_category(triage.get("industry", "general"), tone)
    category_info = CATEGORY_PALETTES.get(category, {})

    if category_info.get("cliche"):
        equity_elements["must_never"].append(f"Avoid category cliché: {category_info['cliche']}")

    # ── PHASE 5: Competitive Landscape Palette ───────────────────────────────

    competitive_position = {
        "category": category,
        "category_look": category_info.get("notes", "Standard industry conventions"),
        "brand_differentiation": "Use unique color combination to stand out",
        "direction": "align_with_category" if not brand_kit else "disrupt_category",
    }

    # ── PHASE 6: Seasonal/Festival Color Injection ───────────────────────────

    seasonal_injection = _detect_festival(
        prompt,
        triage.get("is_festival", False),
        triage.get("festival_name", "")
    )

    # ── PHASE 7: Brand Intelligence Output Package ───────────────────────────

    # Prompt engineer notes (color descriptions in natural language)
    color_descriptions = []
    for role in ["primary", "secondary", "accent"]:
        color_name = _get_dominant_color_name(palette_system[role]["hex"])
        color_descriptions.append(f"{role} {color_name}")

    prompt_engineer_notes = {
        "color_description_for_ai": ", ".join(color_descriptions),
        "style_keywords": [typography_personality.replace("_", " "), tone, category],
        "avoid_keywords": ["generic", "stock photo", "clip art"],
    }

    # Add festival keywords if active
    if seasonal_injection:
        prompt_engineer_notes["festival_keywords"] = seasonal_injection["palette"].get("keywords", [])

    return {
        "brand_intelligence": {
            "brand_name": brand_name,
            "confidence_level": confidence_level,

            "palette": {
                **palette_system,
                "usage_ratios": usage_ratios,
            },

            "typography": typography_system,

            "equity_elements": equity_elements,

            "competitive_position": competitive_position,

            "seasonal_injection": seasonal_injection,

            "prompt_engineer_notes": prompt_engineer_notes,

            # Legacy fields for backward compatibility
            "primary_color": primary_hex,
            "secondary_color": secondary_hex,
            "font_style": font_style,
            "tone": tone,
            "tagline": brand_kit.get("tagline", ""),
            "logo_url": brand_kit.get("logo_url", ""),
        }
    }


# ── Export singleton ──────────────────────────────────────────────────────────

class BrandIntelligenceAgent:
    """Singleton wrapper for brand intelligence agent."""
    extract = staticmethod(brand_intelligence_agent)

brand_intel_agent = BrandIntelligenceAgent()
