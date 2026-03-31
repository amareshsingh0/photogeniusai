"""
Semantic Prompt Enhancer - Context-intelligent prompt enhancement.

Uses sentence-transformers (all-MiniLM-L6-v2, ~66MB) for semantic similarity.
- Encodes user prompt and matches to pattern categories
- Adds contextually relevant patterns; removes contradictions
- Mode-specific enhancements; cached category embeddings

Performance: < 500ms enhancement, model loaded once (singleton), < 200MB memory.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Singleton model instance (load once)
_model: Any = None


def _get_model():
    """Lazy-load SentenceTransformer once (singleton). ~66MB model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


# Pattern database: 20+ categories with patterns, keywords, and lazy embedding
pattern_db: Dict[str, Dict[str, Any]] = {
    "portraits": {
        "patterns": [
            "professional headshot, sharp focus on eyes",
            "elegant pose with confident expression",
            "soft studio lighting with gentle shadows",
            "natural skin texture, detailed facial features",
            "Rembrandt lighting, three-quarter view",
        ],
        "keywords": ["person", "portrait", "headshot", "face", "woman", "man", "model"],
        "embedding": None,
    },
    "nature_scenes": {
        "patterns": [
            "natural lighting with atmospheric depth",
            "rich environmental textures, organic details",
            "authentic outdoor ambiance",
            "lush foliage, dappled light",
            "dramatic sky, sense of scale",
        ],
        "keywords": [
            "forest",
            "mountain",
            "nature",
            "outdoor",
            "tree",
            "landscape",
            "green",
        ],
        "embedding": None,
    },
    "architecture": {
        "patterns": [
            "clean lines, strong composition",
            "architectural detail, perspective",
            "structural symmetry, geometric precision",
            "natural light on surfaces",
            "minimalist urban design",
        ],
        "keywords": [
            "building",
            "architecture",
            "house",
            "tower",
            "bridge",
            "structure",
            "interior",
        ],
        "embedding": None,
    },
    "food": {
        "patterns": [
            "appetizing presentation, fresh ingredients",
            "warm lighting, shallow depth of field",
            "texture and color contrast",
            "editorial food styling",
            "natural shadows, rustic setting",
        ],
        "keywords": [
            "food",
            "meal",
            "dish",
            "recipe",
            "cooking",
            "restaurant",
            "breakfast",
        ],
        "embedding": None,
    },
    "animals": {
        "patterns": [
            "sharp focus on eyes, natural fur texture",
            "animal in natural habitat",
            "expressive pose, environmental context",
            "soft bokeh background",
            "wildlife moment, candid",
        ],
        "keywords": ["animal", "dog", "cat", "bird", "horse", "wildlife", "pet"],
        "embedding": None,
    },
    "vehicles": {
        "patterns": [
            "reflective surfaces, dramatic angles",
            "motion blur or clean static shot",
            "automotive detail, lighting highlights",
            "urban or road context",
            "polished finish, premium feel",
        ],
        "keywords": ["car", "vehicle", "auto", "motorcycle", "bike", "street", "road"],
        "embedding": None,
    },
    "abstract": {
        "patterns": [
            "bold shapes and color relationships",
            "texture and form over literal subject",
            "conceptual composition",
            "experimental lighting",
            "artistic interpretation of space",
        ],
        "keywords": ["abstract", "shape", "form", "concept", "art", "pattern"],
        "embedding": None,
    },
    "artistic": {
        "patterns": [
            "painterly quality, artistic vision",
            "masterpiece, gallery worthy",
            "creative interpretation, unique style",
            "award winning, trending on artstation",
            "fine art composition",
        ],
        "keywords": ["art", "painting", "artistic", "creative", "style", "masterpiece"],
        "embedding": None,
    },
    "fantasy": {
        "patterns": [
            "ethereal lighting, otherworldly atmosphere",
            "magical elements, dreamlike quality",
            "rich fantasy detail, immersive",
            "dramatic scale, epic scope",
            "surreal composition",
        ],
        "keywords": [
            "fantasy",
            "magic",
            "dragon",
            "castle",
            "mythical",
            "dream",
            "surreal",
        ],
        "embedding": None,
    },
    "action": {
        "patterns": [
            "dynamic motion, sense of movement",
            "frozen moment, high energy",
            "sports or physical intensity",
            "dramatic angle, impact",
            "motion blur or sharp action",
        ],
        "keywords": ["action", "running", "sport", "movement", "dynamic", "motion"],
        "embedding": None,
    },
    "emotion": {
        "patterns": [
            "emotional depth, expressive moment",
            "human connection, intimate mood",
            "contemplative or joyful",
            "storytelling through expression",
            "atmospheric mood",
        ],
        "keywords": [
            "emotion",
            "feeling",
            "mood",
            "sad",
            "happy",
            "love",
            "expression",
        ],
        "embedding": None,
    },
    "atmosphere": {
        "patterns": [
            "moody atmosphere, cinematic feel",
            "volumetric lighting, haze",
            "color grading, film look",
            "dramatic shadows, depth",
            "atmospheric perspective",
        ],
        "keywords": ["atmosphere", "moody", "cinematic", "fog", "mist", "dusk", "dawn"],
        "embedding": None,
    },
    "urban": {
        "patterns": [
            "street photography, candid moment",
            "urban texture, graffiti or architecture",
            "city lights, night or day",
            "human element in cityscape",
            "gritty or polished urban",
        ],
        "keywords": ["city", "urban", "street", "downtown", "building", "street"],
        "embedding": None,
    },
    "fashion": {
        "patterns": [
            "editorial quality, professional styling",
            "high fashion, magazine cover",
            "dramatic pose, clothing detail",
            "studio or location fashion",
            "luxury aesthetic",
        ],
        "keywords": ["fashion", "style", "outfit", "model", "clothing", "editorial"],
        "embedding": None,
    },
    "cinematic": {
        "patterns": [
            "dramatic lighting, film grain, color graded",
            "anamorphic look, widescreen",
            "movie still, blockbuster quality",
            "volumetric light, lens flare",
            "epic composition",
        ],
        "keywords": ["cinematic", "film", "movie", "dramatic", "scene", "epic"],
        "embedding": None,
    },
    "romantic": {
        "patterns": [
            "soft dreamy atmosphere, warm tones",
            "intimate moment, golden hour",
            "gentle bokeh, soft focus",
            "romantic mood, tender",
            "pastel or warm palette",
        ],
        "keywords": ["romantic", "love", "couple", "intimate", "dreamy", "soft"],
        "embedding": None,
    },
    "product": {
        "patterns": [
            "clean product shot, reflective surfaces",
            "commercial quality, studio lighting",
            "minimal background, focus on product",
            "premium finish, detail",
            "lifestyle or pure white",
        ],
        "keywords": ["product", "object", "item", "commercial", "brand", "packaging"],
        "embedding": None,
    },
    "still_life": {
        "patterns": [
            "arranged composition, careful lighting",
            "texture and material detail",
            "classical still life feel",
            "shadow and form",
            "natural or studio",
        ],
        "keywords": [
            "still life",
            "arrangement",
            "objects",
            "table",
            "vase",
            "flowers",
        ],
        "embedding": None,
    },
    "wildlife": {
        "patterns": [
            "animal in natural environment",
            "wildlife behavior, undisturbed",
            "habitat context, ecosystem",
            "sharp focus, environmental story",
            "nature documentary quality",
        ],
        "keywords": ["wildlife", "wild", "nature", "animal", "habitat", "safari"],
        "embedding": None,
    },
    "landscape": {
        "patterns": [
            "sweeping vista, horizon",
            "layers of depth, atmospheric",
            "golden or blue hour",
            "grand scale, epic view",
            "natural or cultivated land",
        ],
        "keywords": [
            "landscape",
            "view",
            "vista",
            "horizon",
            "valley",
            "mountain",
            "sea",
        ],
        "embedding": None,
    },
    "landscape_architecture": {
        "patterns": [
            "volumetric god rays through autumn trees",
            "still water mirror reflection, calm lake",
            "warm interior light glowing through cabin windows",
            "subtle chimney smoke, wispy plume",
            "atmospheric mist over water",
            "hyper-detailed autumn foliage, rich fall colors",
            "golden hour lighting, warm golden glow",
            "photorealistic texture, DSLR quality",
        ],
        "keywords": [
            "cabin",
            "lake",
            "autumn",
            "forest",
            "cottage",
            "a-frame",
            "waterfront",
            "reflection",
            "foliage",
        ],
        "embedding": None,
    },
    "fantasy_concept_art": {
        "patterns": [
            "trending on artstation, fantasy concept art, award winning",
            "intricate steampunk architecture, dense city on creature back",
            "dramatic sky, volumetric god rays, lightning bolts",
            "epic scale, airships in distance, smokestacks, chimneys emitting smoke",
            "fine texture on creature, realistic scales and skin, ancient majestic creature",
            "coherent imaginative concept, 8k concept art, highly detailed",
            "multiple layers of depth, atmospheric perspective, cinematic composition",
        ],
        "keywords": [
            "flying",
            "turtle",
            "tortoise",
            "dragon",
            "creature",
            "city on back",
            "steampunk",
            "airship",
            "concept art",
            "fantasy",
            "artstation",
        ],
        "embedding": None,
    },
    "surrealism_fine_art": {
        "patterns": [
            "melting clock, clock melting over tree branch, pocket watch draped over branch",
            "Salvador Dalí surrealism, Persistence of Memory style",
            "Van Gogh Starry Night sky, swirling night sky, thick impasto brushstrokes",
            "dreamscape, dreamlike desert landscape, gnarled dead tree, cracked desert ground",
            "vivid blues and golds, swirling celestial patterns, bold impasto strokes",
            "oil painting masterpiece, gallery worthy fine art, artistic masterpiece",
        ],
        "keywords": [
            "melting",
            "clock",
            "watch",
            "dali",
            "dalí",
            "salvador",
            "van gogh",
            "starry night",
            "oil painting",
            "surrealism",
            "dreamscape",
            "impasto",
            "desert",
            "tree branch",
            "persistence of memory",
            "surreal",
            "dreamlike",
        ],
        "embedding": None,
    },
    "cosmic_surreal_art": {
        "patterns": [
            "swirling nebulae, star clusters, explosive colors, thick impasto brushstrokes",
            "cinematic lighting, ethereal glow, high energy, 8k resolution, artistic masterpiece",
            "dreamlike, unbelievable detail, surprising composition, vibrant cosmic fusion",
            "body composed of galaxies, jersey number clearly visible, deep space background",
            "glowing galaxies, mid-air dynamism, trending on artstation, award winning",
        ],
        "keywords": [
            "cosmic",
            "surrealist",
            "digital painting",
            "nebulae",
            "star clusters",
            "slam dunk",
            "basketball",
            "jersey",
            "deep space",
            "galaxies",
            "mid-air",
            "explosive colors",
            "impasto",
            "ethereal glow",
            "8k resolution",
            "artistic and dreamlike",
            "body composed of",
            "player mid-air",
        ],
        "embedding": None,
    },
    "props_in_hands": {
        "patterns": [
            "correct perspective, coherent structure, physically accurate alignment",
            "proper object placement, structural integrity, realistic proportions",
            "handle and canopy aligned, natural grip, consistent angles",
        ],
        "keywords": [
            "holding",
            "umbrella",
            "in hand",
            "with umbrella",
            "raincoat",
            "holding a",
            "holding an",
            "carrying",
            "gripping",
            "panda",
            "animal holding",
        ],
        "embedding": None,
    },
    "interior": {
        "patterns": [
            "interior design, space and light",
            "furniture and decor detail",
            "natural light through windows",
            "cozy or minimalist space",
            "architectural interior",
        ],
        "keywords": ["interior", "room", "house", "furniture", "design", "home"],
        "embedding": None,
    },
    "street": {
        "patterns": [
            "street scene, candid or posed",
            "urban life, pavement and people",
            "reflections, puddles, lights",
            "documentary or stylistic",
            "moment in time",
        ],
        "keywords": ["street", "pavement", "city", "walking", "crowd", "alley"],
        "embedding": None,
    },
    "sports": {
        "patterns": [
            "athletic moment, peak action",
            "stadium or field context",
            "sweat, effort, determination",
            "dynamic angle, speed",
            "team or solo",
        ],
        "keywords": ["sport", "athlete", "game", "stadium", "running", "ball"],
        "embedding": None,
    },
    "technology": {
        "patterns": [
            "sleek tech aesthetic, screens and light",
            "futuristic or contemporary",
            "circuit, data, digital feel",
            "clean lines, minimal",
            "sci-fi or product",
        ],
        "keywords": ["tech", "computer", "robot", "digital", "screen", "future"],
        "embedding": None,
    },
    "vintage": {
        "patterns": [
            "retro aesthetic, film look",
            "nostalgic, period feel",
            "soft contrast, faded or warm",
            "classic composition",
            "analog texture",
        ],
        "keywords": ["vintage", "retro", "old", "classic", "nostalgic", "film"],
        "embedding": None,
    },
    "luxury": {
        "patterns": [
            "premium materials, refined lighting",
            "luxury aesthetic, high end",
            "elegant detail, craftsmanship",
            "exclusive, aspirational",
            "rich tones, subtle shadows",
        ],
        "keywords": ["luxury", "premium", "elegant", "rich", "exclusive", "high end"],
        "embedding": None,
    },
    "minimalist": {
        "patterns": [
            "clean composition, negative space",
            "simple shapes, limited palette",
            "quiet, restrained",
            "focus on one element",
            "modern minimal",
        ],
        "keywords": ["minimal", "simple", "clean", "bare", "modern", "quiet"],
        "embedding": None,
    },
    "dramatic": {
        "patterns": [
            "high contrast, chiaroscuro",
            "dramatic shadows, bold light",
            "theatrical or cinematic",
            "strong mood, impact",
            "volumetric light rays",
        ],
        "keywords": ["dramatic", "contrast", "shadow", "noir", "intense", "bold"],
        "embedding": None,
    },
    "peaceful": {
        "patterns": [
            "calm, serene atmosphere",
            "soft light, gentle tones",
            "tranquil composition",
            "zen, meditative",
            "quiet moment",
        ],
        "keywords": ["peaceful", "calm", "serene", "tranquil", "zen", "quiet"],
        "embedding": None,
    },
}

# Contradiction pairs: if both present, remove the later one
CONTRADICTION_PAIRS: List[Tuple[str, str]] = [
    ("dark", "bright"),
    ("realistic", "cartoon"),
    ("simple", "detailed"),
    ("flat", "depth"),
    ("blurry", "sharp"),
]


class SemanticPromptEnhancer:
    """
    Semantic-aware prompt enhancer using sentence-transformers.
    Model loaded once (singleton); category embeddings cached after first use.
    """

    def __init__(self) -> None:
        self.model = _get_model()
        self.pattern_db = pattern_db

    def _ensure_category_embedding(self, category: str) -> np.ndarray:
        """Compute and cache category embedding from its patterns + keywords."""
        entry = self.pattern_db.get(category)
        if not entry:
            return np.zeros(
                self.model.get_sentence_embedding_dimension(), dtype=np.float32
            )
        if entry.get("embedding") is not None:
            return entry["embedding"]
        text = " ".join(entry["patterns"]) + " " + " ".join(entry["keywords"])
        emb = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        if emb.ndim == 1:
            entry["embedding"] = emb
        else:
            entry["embedding"] = np.mean(emb, axis=0)
            entry["embedding"] = entry["embedding"] / (
                np.linalg.norm(entry["embedding"]) + 1e-9
            )
        return entry["embedding"]

    def _find_similar_categories(
        self,
        prompt_emb: np.ndarray,
        top_k: int = 3,
        min_similarity: float = 0.6,
    ) -> List[Tuple[str, float]]:
        """
        Compute cosine similarity between prompt and each category; return top_k above threshold.
        Category embeddings are computed and cached on first use.
        """
        if prompt_emb.ndim > 1:
            prompt_emb = prompt_emb.flatten()
        prompt_emb = prompt_emb.astype(np.float32)
        norm = np.linalg.norm(prompt_emb)
        if norm < 1e-9:
            return []
        prompt_emb = prompt_emb / norm

        results: List[Tuple[str, float]] = []
        for category in self.pattern_db:
            cat_emb = self._ensure_category_embedding(category)
            if cat_emb.ndim > 1:
                cat_emb = cat_emb.flatten()
            sim = float(np.dot(prompt_emb, cat_emb))
            if sim >= min_similarity:
                results.append((category, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _remove_contradictions(self, prompt: str) -> str:
        """
        If both terms of a contradiction pair appear, remove the one that appears later.
        """
        prompt_lower = prompt.lower()
        tokens = re.findall(r"\b\w+\b", prompt_lower)
        seen: Dict[str, int] = {}
        for i, t in enumerate(tokens):
            if t not in seen:
                seen[t] = i

        to_remove: set = set()
        for a, b in CONTRADICTION_PAIRS:
            pos_a = seen.get(a)
            pos_b = seen.get(b)
            if pos_a is not None and pos_b is not None:
                if pos_a < pos_b:
                    to_remove.add(b)
                else:
                    to_remove.add(a)

        if not to_remove:
            return prompt

        def drop_word(match: re.Match) -> str:
            w = match.group(0)
            if w.lower() in to_remove:
                return ""
            return w

        out = re.sub(r"\b\w+\b", drop_word, prompt)
        out = re.sub(r"\s+,", ",", out)  # no space before comma
        out = re.sub(r",\s*,", ",", out)  # no double commas
        out = re.sub(r"\s+", " ", out).strip()
        out = out.strip(",").strip()
        return out

    def _get_mode_enhancements(self, mode: str) -> str:
        """Return mode-specific quality keywords."""
        enhancements = {
            "REALISM": "photorealistic, ultra detailed, 8k",
            "CREATIVE": "artistic interpretation, unique style",
            "ROMANTIC": "soft dreamy atmosphere, warm tones",
            "FASHION": "editorial quality, professional styling",
            "CINEMATIC": "dramatic lighting, film grain, color graded",
            "COOL_EDGY": "high contrast, moody, edgy aesthetic",
            "ARTISTIC": "masterpiece, gallery worthy, fine art",
            "MAX_SURPRISE": "unconventional, bold, memorable",
        }
        return enhancements.get(mode.upper(), "high quality, detailed")

    def enhance(self, prompt: str, mode: str = "REALISM") -> str:
        """
        Step 1: Encode user prompt
        Step 2: Find top 3 similar pattern categories (cosine similarity > 0.6)
        Step 3: Extract 2 patterns per matching category
        Step 4: Add mode-specific enhancements
        Step 5: Remove contradictory terms
        Step 6: Return enhanced prompt
        """
        prompt = (prompt or "").strip()
        if not prompt:
            return self._get_mode_enhancements(mode)

        # Step 1: Encode prompt
        prompt_emb = self.model.encode(
            prompt, convert_to_numpy=True, normalize_embeddings=True
        )

        # Step 2: Top 3 similar categories
        similar = self._find_similar_categories(prompt_emb, top_k=3, min_similarity=0.6)

        # Step 3: Up to 2 patterns per category
        parts = [prompt]
        used_patterns: set = set()
        for category, _ in similar:
            entry = self.pattern_db.get(category)
            if not entry:
                continue
            patterns = entry.get("patterns", [])
            count = 0
            for p in patterns:
                if count >= 2:
                    break
                if p not in used_patterns:
                    used_patterns.add(p)
                    parts.append(p)
                    count += 1

        # Step 4: Mode enhancements
        mode_enh = self._get_mode_enhancements(mode)
        parts.append(mode_enh)

        combined = ", ".join(parts)

        # Step 5: Remove contradictions
        combined = self._remove_contradictions(combined)

        return combined


# Singleton instance for reuse
_enhancer: Optional[SemanticPromptEnhancer] = None


def get_enhancer() -> SemanticPromptEnhancer:
    """Return singleton SemanticPromptEnhancer (model loaded once)."""
    global _enhancer
    if _enhancer is None:
        _enhancer = SemanticPromptEnhancer()
    return _enhancer


def enhance_prompt(prompt: str, mode: str = "REALISM") -> str:
    """Convenience: enhance prompt using singleton enhancer."""
    return get_enhancer().enhance(prompt, mode)


# ==================== Style LoRA suggestion (keyword → style name) ====================
# Maps prompt keywords to STYLE_DATASETS keys for auto-applying style LoRA in inference.
STYLE_KEYWORDS_TO_LORA: Dict[str, str] = {
    "cinematic": "cinematic",
    "film": "cinematic",
    "movie": "cinematic",
    "anime": "anime",
    "manga": "anime",
    "photorealistic": "photorealistic",
    "8k": "photorealistic",
    "professional photography": "photorealistic",
    "oil painting": "oil_painting",
    "oil paint": "oil_painting",
    "classical art": "oil_painting",
    "watercolor": "watercolor",
    "watercolour": "watercolor",
    "digital art": "digital_art",
    "vector": "digital_art",
    "concept art": "concept_art",
    "game design": "concept_art",
    "pixel art": "pixel_art",
    "pixel": "pixel_art",
    "retro gaming": "pixel_art",
    "3d render": "three_d_render",
    "3d": "three_d_render",
    "cgi": "three_d_render",
    "blender": "three_d_render",
    "sketch": "sketch_pencil",
    "pencil": "sketch_pencil",
    "hand-drawn": "sketch_pencil",
    "comic": "comic_book",
    "comic book": "comic_book",
    "marvel": "comic_book",
    "ukiyo-e": "ukiyo_e",
    "japanese woodblock": "ukiyo_e",
    "art nouveau": "art_nouveau",
    "decorative": "art_nouveau",
    "cyberpunk": "cyberpunk",
    "neon": "cyberpunk",
    "futuristic": "cyberpunk",
    "fantasy": "fantasy_art",
    "magical": "fantasy_art",
    "ethereal": "fantasy_art",
    "minimalist": "minimalist",
    "minimal": "minimalist",
    "clean simple": "minimalist",
    "surrealism": "surrealism",
    "surreal": "surrealism",
    "dreamlike": "surrealism",
    "vintage photo": "vintage_photo",
    "1970s": "vintage_photo",
    "1980s": "vintage_photo",
    "retro": "vintage_photo",
    "gothic": "gothic",
    "dark dramatic": "gothic",
    "pop art": "pop_art",
    "warhol": "pop_art",
    "lichtenstein": "pop_art",
}


def suggest_style_lora(prompt: str) -> Optional[str]:
    """
    Suggest a style LoRA name from prompt keywords (for auto-apply in inference).
    Returns one of STYLE_DATASETS keys (e.g. cinematic, anime) or None.

    Longest matching keyword wins to prefer "oil painting" over "oil".
    """
    if not prompt or not isinstance(prompt, str):
        return None
    prompt_lower = prompt.lower().strip()
    best: Optional[Tuple[int, str]] = None  # (length, style_name)
    for keyword, style_name in STYLE_KEYWORDS_TO_LORA.items():
        if keyword in prompt_lower:
            if best is None or len(keyword) > best[0]:
                best = (len(keyword), style_name)
    return best[1] if best else None


if __name__ == "__main__":
    # Test 1: "woman in a forest" → should add nature + portrait patterns
    # Test 2: "car on street" → should add vehicle + urban patterns
    # Test 3: "dark bright photo" → should remove one of dark/bright
    enhancer = get_enhancer()
    for test_prompt, description in [
        ("woman in a forest", "nature + portrait patterns"),
        ("car on street", "vehicle + urban patterns"),
        ("dark bright photo", "remove one of dark/bright"),
    ]:
        out = enhancer.enhance(test_prompt, "REALISM")
        print(f"[{description}]")
        print(f"  in:  {test_prompt!r}")
        print(f"  out: {out[:200]}{'...' if len(out) > 200 else ''}")
        print()
