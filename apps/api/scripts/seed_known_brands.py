"""
Seed Known Brands — Populate brand_intelligence table with global brands

Run: python -m scripts.seed_known_brands
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.brand_intelligence_service import save_brand_intelligence

# Known Global Brands Database
KNOWN_BRANDS = [
    {
        "brand_name": "Nike",
        "industry": "fitness",
        "is_global": True,
        "primary_color": "#FF0000",  # Nike Red
        "secondary_color": "#000000",  # Black
        "logo_url": "",
        "tagline": "Just Do It",
        "font_style": "street_energy",
        "tone": "bold",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#FF0000", "rgb": [255, 0, 0], "hsl": [0, 100, 50]},
            "secondary": {"hex": "#000000", "rgb": [0, 0, 0], "hsl": [0, 0, 0]},
            "accent": {"hex": "#FFFFFF", "rgb": [255, 255, 255], "hsl": [0, 0, 100]},
        },
        "typography": {
            "personality": "street_energy",
            "display": {"font_family": "Futura Bold", "weight_options": [700, 900]},
        },
        "competitive_position": {
            "category": "fitness",
            "brand_differentiation": "Bold energy, athletic performance",
            "direction": "disrupt_category",
        },
    },
    {
        "brand_name": "Apple",
        "industry": "tech",
        "is_global": True,
        "primary_color": "#000000",  # Apple Black
        "secondary_color": "#FFFFFF",  # White
        "logo_url": "",
        "tagline": "Think Different",
        "font_style": "clean_sans",
        "tone": "minimal",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#000000", "rgb": [0, 0, 0], "hsl": [0, 0, 0]},
            "secondary": {"hex": "#FFFFFF", "rgb": [255, 255, 255], "hsl": [0, 0, 100]},
            "accent": {"hex": "#007AFF", "rgb": [0, 122, 255], "hsl": [211, 100, 50]},
        },
        "typography": {
            "personality": "authoritative_modern",
            "display": {"font_family": "SF Pro Display", "weight_options": [400, 600]},
        },
        "competitive_position": {
            "category": "saas",
            "brand_differentiation": "Minimalist premium design",
            "direction": "disrupt_category",
        },
    },
    {
        "brand_name": "Coca-Cola",
        "industry": "food",
        "is_global": True,
        "primary_color": "#F40009",  # Coca-Cola Red
        "secondary_color": "#FFFFFF",  # White
        "logo_url": "",
        "tagline": "Open Happiness",
        "font_style": "expressive_display",
        "tone": "playful",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#F40009", "rgb": [244, 0, 9], "hsl": [358, 100, 48]},
            "secondary": {"hex": "#FFFFFF", "rgb": [255, 255, 255], "hsl": [0, 0, 100]},
            "accent": {"hex": "#000000", "rgb": [0, 0, 0], "hsl": [0, 0, 0]},
        },
        "typography": {
            "personality": "playful_warm",
            "display": {"font_family": "Spencerian Script", "weight_options": [400]},
        },
        "competitive_position": {
            "category": "food",
            "brand_differentiation": "Classic red, nostalgic happiness",
            "direction": "align_with_category",
        },
    },
    {
        "brand_name": "Starbucks",
        "industry": "food",
        "is_global": True,
        "primary_color": "#00704A",  # Starbucks Green
        "secondary_color": "#FFFFFF",  # White
        "logo_url": "",
        "tagline": "Inspire and nurture the human spirit",
        "font_style": "organic_natural",
        "tone": "warm",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#00704A", "rgb": [0, 112, 74], "hsl": [160, 100, 22]},
            "secondary": {"hex": "#FFFFFF", "rgb": [255, 255, 255], "hsl": [0, 0, 100]},
            "accent": {"hex": "#000000", "rgb": [0, 0, 0], "hsl": [0, 0, 0]},
        },
        "typography": {
            "personality": "organic_natural",
            "display": {"font_family": "Sodo Sans", "weight_options": [400, 700]},
        },
        "competitive_position": {
            "category": "food",
            "brand_differentiation": "Green premium coffee experience",
            "direction": "disrupt_category",
        },
    },
    {
        "brand_name": "McDonald's",
        "industry": "food",
        "is_global": True,
        "primary_color": "#FFC72C",  # Golden Arches Yellow
        "secondary_color": "#DA291C",  # McDonald's Red
        "logo_url": "",
        "tagline": "I'm Lovin' It",
        "font_style": "playful_young",
        "tone": "playful",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#FFC72C", "rgb": [255, 199, 44], "hsl": [44, 100, 59]},
            "secondary": {"hex": "#DA291C", "rgb": [218, 41, 28], "hsl": [4, 77, 48]},
            "accent": {"hex": "#FFFFFF", "rgb": [255, 255, 255], "hsl": [0, 0, 100]},
        },
        "typography": {
            "personality": "playful_young",
            "display": {"font_family": "Speedee", "weight_options": [700]},
        },
        "competitive_position": {
            "category": "food",
            "brand_differentiation": "Bright yellow-red fast food classic",
            "direction": "align_with_category",
        },
    },
    {
        "brand_name": "Google",
        "industry": "saas",
        "is_global": True,
        "primary_color": "#4285F4",  # Google Blue
        "secondary_color": "#EA4335",  # Google Red
        "logo_url": "",
        "tagline": "Don't be evil",
        "font_style": "clean_sans",
        "tone": "playful",
        "confidence_level": "high",
        "source_type": "known_brand",
        "palette": {
            "primary": {"hex": "#4285F4", "rgb": [66, 133, 244], "hsl": [217, 89, 61]},
            "secondary": {"hex": "#EA4335", "rgb": [234, 67, 53], "hsl": [5, 82, 56]},
            "accent": {"hex": "#34A853", "rgb": [52, 168, 83], "hsl": [136, 52, 43]},
        },
        "typography": {
            "personality": "authoritative_modern",
            "display": {"font_family": "Product Sans", "weight_options": [400, 700]},
        },
        "competitive_position": {
            "category": "saas",
            "brand_differentiation": "Multi-color playful tech giant",
            "direction": "disrupt_category",
        },
    },
]


async def seed_brands():
    """Seed known global brands into database."""
    print("🌱 Seeding known brands...")

    success_count = 0
    fail_count = 0

    for brand_data in KNOWN_BRANDS:
        try:
            brand_id = await save_brand_intelligence(**brand_data)
            if brand_id:
                print(f"✅ {brand_data['brand_name']}")
                success_count += 1
            else:
                print(f"❌ {brand_data['brand_name']} - Failed")
                fail_count += 1
        except Exception as e:
            print(f"❌ {brand_data['brand_name']} - Error: {e}")
            fail_count += 1

    print(f"\n🎯 Summary: {success_count} success, {fail_count} failed")


if __name__ == "__main__":
    asyncio.run(seed_brands())
