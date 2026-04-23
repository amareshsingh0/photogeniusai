"""
Multi-Provider Client — Automatic cheapest provider routing with failover.

Strategy:
  Same model → always use cheapest available provider.
  If primary fails → auto-failover to next provider.
  User never sees provider errors.

Provider priority (cheapest first per model):
  Flux Schnell:   Fireworks ($0.0014) → fal.ai ($0.003) → Replicate ($0.003)
  Flux 2 Dev:     fal.ai ($0.012) → Together AI ($0.015) → Replicate ($0.025)
  Flux 2 Pro:     fal.ai ($0.03) → Together AI ($0.03) → Replicate ($0.04)
  Flux Kontext:   fal.ai ($0.04) → Together AI ($0.04) → BFL Direct ($0.04)
  Ideogram v3:    fal.ai ($0.03-0.09) → Replicate ($0.03-0.09)
  Recraft v4:     fal.ai ($0.04-0.08) → Replicate ($0.04-0.08)

Requires (in .env.local):
  FAL_KEY              — fal.ai (primary for most models)
  FIREWORKS_API_KEY    — cheapest Schnell ($0.0014)
  TOGETHER_API_KEY     — Flux 2 Pro/Dev fallback
  REPLICATE_API_TOKEN  — last resort fallback

Cost per model (approx, 1024×1024):
  flux_schnell   → $0.0014 = ₹0.12  (Fireworks primary)
  flux_2_dev     → $0.012  = ₹1.01  (fal.ai primary)
  flux_2_pro     → $0.030  = ₹2.52  (fal.ai primary)
  flux_2_max     → $0.070  = ₹5.88  (fal.ai only)
  flux_kontext   → $0.040  = ₹3.36  (fal.ai primary)
  ideogram_turbo → $0.030  = ₹2.52  (fal.ai primary)
  ideogram_qual  → $0.090  = ₹7.56  (fal.ai primary)
  recraft_svg    → $0.080  = ₹6.72  (fal.ai primary)
  real_esrgan    → $0.002  = ₹0.17  (fal.ai only)
"""

from __future__ import annotations

import logging
import os
import time
import json
from typing import Dict, List, Optional

import re

import httpx

logger = logging.getLogger(__name__)


# ─── Imagen prompt distillation ──────────────────────────────────────────────
# Google Imagen 3/4 + Gemini Imagen interpret long art-direction prompts as
# "creative brief documents" and render literal multi-panel layouts with
# "Option 1/2/3", "Body:", "CTA:", "[Website]", hashtags etc. Adding anti-
# collage instructions DOESN'T help (Imagen's parser reads "Not a collage"
# as a positive trigger) and the `negativePrompt` parameter was DROPPED from
# Imagen 4. The only thing that works: STRIP all designer-brief vocabulary
# from the prompt before sending, keeping only (a) the scene, (b) the literal
# text to render. Done deterministically with regex — no extra LLM call.

# Words/phrases that signal "this is a creative brief, render it as one"
_IMAGEN_BRIEF_VOCAB = re.compile(
    r"\b(?:"
    r"headline|sub-?head|sub-?title|tagline|caption|body\s+(?:copy|text|paragraph)|"
    r"call[\s-]to[\s-]action|cta|pill\s+button|button|badge|chip|ribbon\s+band|"
    r"hierarchy|anchor(?:s|ed|ing)?|locked|occupy(?:ing|ies)?|"
    r"dominant|secondary|tracking\s+(?:tight|loose|wide|normal)|leading\s+\w+|"
    r"left[\s-]aligned|right[\s-]aligned|center[\s-]aligned|alignment|"
    r"layout|composition\s+(?:features|anchors|locks)|poster\s+height|"
    r"upper\s+third|lower\s+third|middle\s+third|"
    r"top\s+(?:third|left|right|center|edge)|bottom\s+(?:third|left|right|center|edge)|"
    r"center[\s-]?left|center[\s-]?right|center[\s-]?top|center[\s-]?bottom|"
    r"center[\s-]?aligned|"
    r"display\s+sans-?serif|condensed\s+sans-?serif|elegant\s+serif|"
    r"sans-?serif|serif\b|font\s+(?:size|weight|family|hierarchy)|"
    r"oversized|all\s+caps|tracking|leading|kerning|"
    r"option\s*\d+|version\s*\d+|concept\s*\d+|variant\s*\d+|design\s*\d+|"
    r"draft\s*\d+|"
    r"palette:?|color\s+(?:palette|breakdown|harmony|hierarchy)|"
    r"safe\s+margins?|negative\s+space|breathing\s+room|"
    r"drop\s+shadow|specular\s+highlight|rim[\s-]?light|backlight|backlit|"
    r"key\s+light|fill\s+light|three[\s-]?point\s+lighting|"
    r"film\s+grain|85mm|portrait[\s-]?lens|depth\s+of\s+field|bokeh|"
    r"editorial\s+polish|premium\s+\w+\s+aesthetic|aspirational\s+mood|"
    r"high\s+legibility|read(?:ability|ing\s+distance)|"
    r"set\s+at\s+\d+%|at\s+\d+%\s+of\s+(?:poster|image|frame)|"
    r"\d{1,3}%\s+of\s+(?:poster|image|frame|height|width)"
    r")\b",
    re.IGNORECASE,
)

# Bracketed placeholders that get rendered as text in Imagen output
_IMAGEN_BRACKETS = re.compile(r"\[[^\]\n]{1,80}\]")
# Curly placeholders too
_IMAGEN_BRACES = re.compile(r"\{{1,2}[^}\n]{1,80}\}{1,2}")

# Color percentage breakdowns: "warm cream 60%, turquoise 25%, coral 10%"
_IMAGEN_COLOR_PERCENT = re.compile(
    r"\b[\w-]+(?:\s+[\w-]+){0,3}\s+\d{1,3}\s*%(?:\s*[,&;]?)",
    re.IGNORECASE,
)

# Bare percentages: "35%", "60 %"
_IMAGEN_BARE_PERCENT = re.compile(r"\b\d{1,3}\s*%")

# Markdown-ish leftovers
_IMAGEN_MD = re.compile(r"[#*`_]{1,3}")

# "reads 'X'" / "reading 'X'" / "text 'X'" — extract the quoted X but drop the framing words later
_IMAGEN_QUOTED = re.compile(r"['\"‘’“”]([^'\"‘’“”\n]{2,80})['\"‘’“”]")

# Hashtag patterns Imagen renders literally
_IMAGEN_HASHTAGS = re.compile(r"#\w+(?:\s+#\w+)*")


def _distill_for_imagen(prompt: str) -> str:
    """Transform a designer-brief prompt into a direct image-gen prompt for Imagen.

    Strips all art-direction vocabulary that triggers Imagen's "render this as
    a creative brief document" bias. Keeps the scene + literal text only.
    Output is capped at ~60 words and wrapped with explicit single-image framing.
    """
    if not prompt:
        return prompt
    original = prompt

    # 1) Extract literal text-to-render BEFORE stripping anything (we need
    #    the quotes intact). Take up to 3 distinct quoted strings.
    seen = set()
    literals: list[str] = []
    for match in _IMAGEN_QUOTED.finditer(prompt):
        text = match.group(1).strip()
        # Skip noise: percentages, very short fragments, brief-doc labels
        if not text or len(text) < 2:
            continue
        if text.lower() in seen:
            continue
        if re.fullmatch(r"\d{1,3}%?", text):
            continue
        if text.lower() in {"option 1", "option 2", "option 3", "body", "cta", "headline"}:
            continue
        seen.add(text.lower())
        literals.append(text)
        if len(literals) >= 3:
            break

    # 2) Strip placeholders (Imagen renders [Website Address] as visible text)
    cleaned = _IMAGEN_BRACKETS.sub("", prompt)
    cleaned = _IMAGEN_BRACES.sub("", cleaned)

    # 3) Strip hashtags (rendered literally as #GlowSunscreen etc.)
    cleaned = _IMAGEN_HASHTAGS.sub("", cleaned)

    # 4) Strip color-percentage palette breakdowns: "warm cream 60%, turquoise 25%"
    cleaned = _IMAGEN_COLOR_PERCENT.sub("", cleaned)
    cleaned = _IMAGEN_BARE_PERCENT.sub("", cleaned)

    # 5) Strip designer-brief vocabulary
    cleaned = _IMAGEN_BRIEF_VOCAB.sub("", cleaned)

    # 6) Strip markdown leftovers
    cleaned = _IMAGEN_MD.sub("", cleaned)

    # 7) Drop entire sentences that still mention multi-variant trigger words
    pieces = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    BAD_SENTENCE = re.compile(
        r"\b(?:option|variant|version|concept|panel|grid|collage|moodboard|"
        r"mood-board|carousel|slide\s+\d+|comparison|side[\s-]by[\s-]side)\b",
        re.IGNORECASE,
    )
    pieces = [p for p in pieces if p and not BAD_SENTENCE.search(p)]
    cleaned = " ".join(pieces)

    # 8) Collapse whitespace, stray punctuation
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:])(?:\s*\1)+", r"\1", cleaned)
    cleaned = re.sub(r"^[\s,;:.]+|[\s,;:]+$", "", cleaned)

    # 9) Cap at 60 words (sentence-aware) — Imagen does best with concise scenes
    words = cleaned.split()
    if len(words) > 60:
        truncated = " ".join(words[:60])
        last_term = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        if last_term > 80:
            truncated = truncated[: last_term + 1]
        cleaned = truncated

    # 10) Build final prompt — photography-forward framing.
    # AVOID leading with "poster" — Imagen has a strong "poster template" bias
    # that overrides scene description. Lead with "commercial advertising
    # photograph" instead, which pulls Imagen toward photographic output.
    # Also: strip the upstream "ONE single unified image" anchor (added by
    # generate_stream.py) to avoid double-anchoring that confuses the model.
    cleaned = re.sub(
        r"^\s*ONE single unified (?:image|photograph)[^.]*\.\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^\s*one cohesive composition[^.]*\.\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Some Haiku outputs literally start with "A bold ... poster: ..." — strip
    # the "poster" framing word so it doesn't double up with our anchor below.
    cleaned = re.sub(
        r"^[Aa]\s+\w+[\w,\s-]*?\s+(?:poster|advertisement|ad)\s*[:.\-—]?\s*",
        "",
        cleaned,
    )

    parts: list[str] = []
    if literals:
        # This is an ad/poster (has quoted text to render) — anchor with
        # photographic framing to override Imagen's "minimalist poster
        # template" default. Without this, Imagen renders cartoon/illustration
        # styles even when the brief specified photo.
        parts.append(
            "A single high-quality commercial advertising photograph, "
            "photorealistic, professional studio photography style."
        )
        if cleaned:
            parts.append(cleaned)
        text_parts = []
        for i, t in enumerate(literals):
            if i == 0:
                text_parts.append(f'"{t}" as the main headline in large bold letters')
            elif i == 1:
                text_parts.append(f'"{t}" as a smaller subtext line')
            else:
                text_parts.append(f'"{t}" as small caption text')
        parts.append(
            "The photograph displays this visible text overlaid on the image: "
            + ", ".join(text_parts) + "."
        )
    else:
        # No quoted text → pure scene (portrait, photoreal, anime, etc).
        # Just send the cleaned scene without ad-photography framing.
        if cleaned:
            parts.append(cleaned)
        else:
            parts.append(prompt)  # safety: never send empty prompt

    result = " ".join(parts).strip()
    if result != original:
        logger.info("[imagen-distill] %d→%d chars (kept %d literals)",
                    len(original), len(result), len(literals))
    return result


def _safe_json(payload) -> str:
    """Serialise a provider payload for logging.

    Truncates any inline base64 data: URLs (reference images, masks) so a single
    log line stays readable even when the caller passed a 1-MB image. Returns a
    compact one-line string suitable for grepping in pm2 logs.
    """
    def _truncate(value):
        if isinstance(value, str) and value.startswith("data:") and len(value) > 80:
            return f"{value[:60]}...<{len(value)} chars>"
        if isinstance(value, list):
            return [_truncate(v) for v in value]
        if isinstance(value, dict):
            return {k: _truncate(v) for k, v in value.items()}
        return value
    try:
        return json.dumps(_truncate(payload), ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return repr(payload)[:500]


# ── Provider API configs ───────────────────────────────────────────────────────

_FAL_BASE       = "https://fal.run"
_WAVESPEED_BASE = "https://api.wavespeed.ai/api/v3"

# WaveSpeed model UUID paths (official v3 docs, Apr 2026)
_WAVESPEED_MODEL_PATHS = {
    "grok_2_imagine": "x-ai/grok-imagine-image/text-to-image",
    "wan_2_7":        "alibaba/wan-2.7/text-to-image",
    "hunyuan_image":  "wavespeed-ai/hunyuan-image-3",
}

# Provider → env var
_PROVIDER_KEYS = {
    "fal":       "FAL_KEY",              # fal.ai — Primary aggregator (Flux, Ideogram, Recraft, Seedream)
    "google":    "GEMINI_API_KEY",       # Google AI Studio — Imagen models
    "wavespeed": "WAVESPEED_API_KEY",    # WaveSpeed — Grok 2, Wan 2.7, Hunyuan
}

# ── Model routing table — ordered by cheapest provider ────────────────────────
# Format: model_key → list of (provider, provider_model_id, cost_usd)
# First entry = cheapest / primary. Rest = ordered fallbacks.

MODEL_PROVIDER_CHAIN: Dict[str, List[tuple]] = {
    # ── Next-gen models used by smart model routing ───────────────────────────
    "flux_2_flex": [
        ("fal",      "fal-ai/flux-2-flex",                          0.015),
    ],
    "gemini_3_imagen": [
        ("google",   "gemini_3_imagen",                             0.035),
    ],
    "gemini_3_1_imagen": [
        ("google",   "gemini_3_1_imagen",                           0.070),
    ],
    "imagen_4_base": [
        ("google",   "imagen_4_base",                               0.020),
    ],
    "imagen_4_fast": [
        ("google",   "imagen_4_fast",                               0.020),
    ],
    "imagen_4_ultra": [
        ("google",   "imagen_4_ultra",                              0.060),
    ],
    "grok_2_imagine": [
        ("wavespeed", "grok_2_imagine",                              0.020),
    ],
    "ideogram_v3": [
        ("fal",      "fal-ai/ideogram/v3",                          0.030),
    ],
    "seedream_4_5": [
        ("fal",      "fal-ai/bytedance/seedream/v4.5/text-to-image", 0.030),
    ],
    "wan_2_7": [
        ("wavespeed", "wan_2_7",                                     0.030),
    ],
    "recraft_v4_pro": [
        ("fal",      "fal-ai/recraft/v4/pro/text-to-image",         0.030),
    ],
    # ── Flux Schnell — pixazo cheapest ($0.0012) + 100 free/day, Fireworks fallback
    "flux_schnell": [
        ("pixazo",   "flux-schnell",                              0.0012),
        ("fireworks","accounts/fireworks/models/flux-1-schnell-fp8", 0.0014),
        ("fal",      "fal-ai/flux/schnell",                       0.003),
        ("replicate","black-forest-labs/flux-schnell",            0.003),
    ],
    # ── Flux 2 Dev — Together AI primary ($0.010)
    "flux_2_dev": [
        ("together", "black-forest-labs/FLUX.1-dev",  0.010),
        ("fal",      "fal-ai/flux-2",                 0.012),
        ("replicate","black-forest-labs/flux-dev",    0.025),
    ],
    # ── Flux 2 Turbo — fal.ai only
    "flux_2_turbo": [
        ("fal",      "fal-ai/flux-2/turbo",  0.008),
        ("fal",      "fal-ai/flux-2",        0.012),   # fallback to dev if turbo fails
    ],
    # ── Flux 2 Pro — kie.ai cheapest ($0.025), fal.ai fallback ($0.030)
    "flux_2_pro": [
        ("kie",      "flux-2/pro-text-to-image",       0.025),
        ("fal",      "fal-ai/flux-2-pro",              0.030),
        ("together", "black-forest-labs/FLUX.1.1-pro", 0.040),
        ("replicate","black-forest-labs/flux-1.1-pro", 0.040),
    ],
    # ── Flux 2 Max — BFL official primary ($0.060), fal.ai fallback ($0.070)
    "flux_2_max": [
        ("bfl",      "flux-1.1-ultra",    0.060),   # api.bfl.ai official
        ("fal",      "fal-ai/flux-2-max", 0.070),
    ],
    # ── Flux Kontext Pro — fal.ai primary
    "flux_kontext": [
        ("fal",      "fal-ai/flux-pro/kontext",              0.040),
        ("together", "black-forest-labs/FLUX.1-kontext-pro", 0.040),
    ],
    "flux_kontext_max": [
        ("fal",      "fal-ai/flux-pro/kontext/max",    0.080),
        ("bfl",      "flux-kontext-max",               0.080),
    ],
    # ── Flux Fill (inpainting) — fal.ai
    "flux_fill": [
        ("fal",      "fal-ai/flux-pro/fill",           0.050),
    ],
    # ── Ideogram v3 — fal.ai
    "ideogram_turbo": [
        ("fal",      "fal-ai/ideogram/v3",             0.030),
    ],
    "ideogram_quality": [
        ("fal",      "fal-ai/ideogram/v3",             0.090),
    ],
    # ── Recraft v4 — fal.ai
    "recraft_v4": [
        ("fal",      "fal-ai/recraft/v4/text-to-image",     0.040),
    ],
    "recraft_v4_svg": [
        ("fal",      "fal-ai/recraft/v4/text-to-vector",    0.080),
    ],
    # ── Hunyuan Image — anime/Asian styles — WaveSpeed
    "hunyuan_image": [
        ("wavespeed", "hunyuan_image",                  0.030),
    ],
    # ── Google Imagen 3 — Google AI Studio (best text rendering)
    "imagen_3": [
        ("google",   "imagen_3",                        0.020),  # $0.02/image (1024x1024)
    ],
    # ── Real-ESRGAN upscale — fal.ai
    "real_esrgan": [
        ("fal",      "fal-ai/real-esrgan",             0.002),
        ("replicate","nightmareai/real-esrgan",        0.001),
    ],
}

_MODEL_KEY_ALIASES = {
    "flux_pro": "flux_2_pro",
    "flux_dev": "flux_2_dev",
    "flux_schnell_fal": "flux_schnell",
    "flux_schnell_pixazo": "flux_schnell",
    "imagen_4_standard": "imagen_4_base",
    "gemini_flash_image": "gemini_3_imagen",
    "xai_grok_imagine_image": "grok_2_imagine",
    "fal_ai_ideogram_v3": "ideogram_v3",
    "fal_ai_recraft_v4_pro_text_to_image": "recraft_v4_pro",
}

# Models that need special payload handling
_SCHNELL_IDS  = {"fal-ai/flux/schnell", "accounts/fireworks/models/flux-1-schnell-fp8"}
_IDEOGRAM_IDS = {"fal-ai/ideogram/v3"}
_IDEOGRAM_REMIX_IDS = {"fal-ai/ideogram/v3/remix"}            # img2img variant
_RECRAFT_IDS  = {
    "fal-ai/recraft/v4/text-to-image",
    "fal-ai/recraft/v4/text-to-vector",
    "fal-ai/recraft/v4/pro/text-to-image",
}
_KONTEXT_IDS  = {"fal-ai/flux-pro/kontext", "fal-ai/flux-pro/kontext/max"}
_SEEDREAM_IDS = {"fal-ai/bytedance/seedream/v4.5/text-to-image"}
_SEEDREAM_EDIT_IDS = {"fal-ai/bytedance/seedream/v4/edit"}    # img2img variant
_WAN_IDS      = {"fal-ai/wan/v2.7/text-to-image"}
_GROK_IDS     = {"xai/grok-imagine-image"}

# Img2Img endpoint swap — when reference_image_url is provided, _call_fal
# rewrites the model_id to the model's edit/remix variant (which actually
# accepts an input image). Text-to-image payloads silently drop image_url.
_FAL_I2I_ENDPOINT_MAP = {
    "fal-ai/bytedance/seedream/v4.5/text-to-image": "fal-ai/bytedance/seedream/v4/edit",
    "fal-ai/ideogram/v3":                           "fal-ai/ideogram/v3/remix",
}
_KIE_ASPECT_RATIO_MAP = {
    "square_hd": "1:1",
    "landscape_16_9": "16:9",
    "portrait_9_16": "9:16",
    "landscape_4_3": "4:3",
    "portrait_4_3": "3:4",
}


def _normalize_model_key(model_key: str) -> str:
    normalized = (model_key or "").strip().lower().replace(" ", "_").replace(".", "_").replace("-", "_")
    return _MODEL_KEY_ALIASES.get(normalized, normalized)


def _kie_aspect_ratio_for_size(image_size: str) -> str:
    return _KIE_ASPECT_RATIO_MAP.get(image_size, "1:1")


def _extract_kie_urls(data: Dict) -> List[str]:
    result_json = data.get("resultJson")
    parsed = result_json
    if isinstance(result_json, str):
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError:
            parsed = {}

    if isinstance(parsed, dict):
        urls = parsed.get("resultUrls") or parsed.get("urls") or parsed.get("output") or []
    else:
        urls = parsed or []

    if not isinstance(urls, list):
        urls = [urls] if urls else []
    return [u for u in urls if isinstance(u, str) and u]


class MultiProviderClient:
    """
    Auto-routing image generation client.

    Picks the cheapest provider for each model.
    Falls back to next provider on failure.
    Unified response contract regardless of provider.

    Usage:
        result = await multi_client.generate("flux_schnell", prompt="...")
        result = await multi_client.upscale(image_url="...")
    """

    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._keys = {p: os.getenv(env, "") for p, env in _PROVIDER_KEYS.items()}
        self._log_missing_keys()

    def _log_missing_keys(self):
        for provider, key in self._keys.items():
            if not key:
                logger.debug("[multi] %s key not set — that provider will be skipped", provider)

    def _provider_enabled(self, provider: str) -> bool:
        """Check feature flag for provider. Missing flag = enabled by default."""
        flag_map = {
            "together":  "USE_TOGETHER",
            "bfl":       "USE_BFL",
            "kie":       "USE_KIE",
            "pixazo":    "USE_PIXAZO",
            "fireworks": "USE_FIREWORKS",
        }
        env_var = flag_map.get(provider)
        if env_var is None:
            return True   # fal, replicate — always on
        return os.getenv(env_var, "true").lower() not in ("false", "0", "off")

    def _get_client(self, provider: str) -> httpx.AsyncClient:
        if provider not in self._clients or self._clients[provider].is_closed:
            key = self._keys.get(provider, "")
            auth_header = (
                f"Key {key}"       if provider == "fal"       else
                f"Bearer {key}"    if provider in ("fireworks", "together", "kie") else
                f"Token {key}"     if provider == "replicate"  else
                ""
            )
            self._clients[provider] = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10, read=300, write=30, pool=5),
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
            )
        return self._clients[provider]

    # ── Main generate with auto-failover ──────────────────────────────────────

    async def generate(
        self,
        model_key: str,
        prompt: str,
        negative_prompt: str = "",
        num_images: int = 1,
        image_size: str = "square_hd",
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        seed: Optional[int] = None,
        reference_image_url: Optional[str] = None,
        extra_image_urls: Optional[List[str]] = None,
        rendering_speed: str = "BALANCED",
        style: Optional[str] = None,
    ) -> Dict:
        """
        Generate image with automatic cheapest provider + failover.
        model_key = key from MODEL_PROVIDER_CHAIN (e.g. "flux_schnell", "flux_2_pro")
        """
        requested_model_key = model_key
        model_key = _normalize_model_key(model_key)
        chain = MODEL_PROVIDER_CHAIN.get(model_key)
        if not chain:
            return self._error(requested_model_key, f"Unknown model_key: {requested_model_key}", 0.0)

        last_error = "No providers available"
        for provider, model_id, cost_usd in chain:
            if not self._provider_enabled(provider):
                logger.debug("[multi] skip %s — disabled via flag", provider)
                continue
            key = self._keys.get(provider, "")
            if not key:
                logger.debug("[multi] skip %s — no API key", provider)
                continue

            logger.info("[multi] trying %s / %s (cost=$%.4f)", provider, model_id, cost_usd)
            result = await self._call_provider(
                provider=provider,
                model_id=model_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                num_images=num_images,
                image_size=image_size,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                seed=seed,
                reference_image_url=reference_image_url,
                extra_image_urls=extra_image_urls,
                rendering_speed=rendering_speed,
                style=style,
            )
            if result["success"]:
                result["provider"] = provider
                result["cost_usd"] = cost_usd
                result["cost_inr"] = round(cost_usd * 84, 2)
                result["model_key"] = model_key
                result["requested_model_key"] = requested_model_key
                logger.info("[multi] OK provider=%s model=%s cost=$%.4f",
                            provider, model_id, cost_usd)
                return result

            last_error = result.get("metadata", {}).get("error", "unknown")
            logger.warning("[multi] %s failed (%s), trying next provider", provider, last_error)

        return self._error(model_key, f"All providers failed. Last: {last_error}", 0.0)

    # ── Upscale (ESRGAN) ──────────────────────────────────────────────────────

    async def upscale(self, image_url: str, scale: int = 4) -> Dict:
        """4x upscale — fal.ai ESRGAN primary, Replicate fallback."""
        chain = MODEL_PROVIDER_CHAIN.get("real_esrgan", [])
        last_error = "No providers"
        for provider, model_id, cost_usd in chain:
            key = self._keys.get(provider, "")
            if not key:
                continue
            result = await self._upscale_fal(image_url, scale) if provider == "fal" \
                else await self._upscale_replicate(image_url, scale)
            if result["success"]:
                result["provider"] = provider
                result["cost_usd"] = cost_usd
                return result
            last_error = result.get("metadata", {}).get("error", "unknown")
        return self._error("real_esrgan", f"Upscale failed: {last_error}", 0.0)

    # ── Provider-specific callers ─────────────────────────────────────────────

    async def _call_provider(self, provider: str, model_id: str, **kwargs) -> Dict:
        """Route to appropriate provider client (fal.ai, Google Vertex, WaveSpeed only)."""
        if provider == "fal":
            return await self._call_fal(model_id, **kwargs)
        elif provider == "google":
            return await self._call_google(model_id, **kwargs)
        elif provider == "wavespeed":
            return await self._call_wavespeed(model_id, **kwargs)
        return self._error(model_id, f"Unknown provider: {provider}", 0.0)

    async def _call_fal(self, model_id: str, prompt: str, negative_prompt: str,
                        num_images: int, image_size: str, num_inference_steps: int,
                        guidance_scale: float, seed, reference_image_url,
                        extra_image_urls: Optional[List[str]] = None,
                        rendering_speed: str = "BALANCED", style=None) -> Dict:
        start = time.time()
        client = self._get_client("fal")

        # Img2Img endpoint swap — text-to-image endpoints silently drop image_url,
        # so route to the model's edit/remix variant when a reference is supplied.
        if reference_image_url and model_id in _FAL_I2I_ENDPOINT_MAP:
            original_id = model_id
            model_id = _FAL_I2I_ENDPOINT_MAP[model_id]
            logger.info("[fal] Img2Img endpoint swap: %s → %s", original_id, model_id)

        payload = self._build_fal_payload(
            model_id, prompt, negative_prompt, num_images, image_size,
            num_inference_steps, guidance_scale, seed, reference_image_url,
            rendering_speed, style, extra_image_urls
        )
        logger.info("[PAYLOAD][fal] model=%s body=%s", model_id, _safe_json(payload))
        try:
            resp = await client.post(f"https://fal.run/{model_id}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            urls = self._extract_fal_urls(data)
            if not urls:
                raise ValueError(f"No images returned: {list(data.keys())}")
            return self._ok(urls, model_id, "fal.ai", time.time() - start)
        except Exception as e:
            return self._error(model_id, str(e), time.time() - start)

    async def _call_google(self, model_id: str, prompt: str, negative_prompt: str,
                           num_images: int, image_size: str, num_inference_steps: int,
                           guidance_scale: float, seed, reference_image_url: Optional[str] = None,
                           **kwargs) -> Dict:
        """Single entry point for ALL Google models — Imagen 3, Imagen 4
        (base/fast/ultra), Gemini 3/3.1 Imagen — via Google AI Studio REST API
        (`:predict`). Same anti-collage fold-in applies to every endpoint."""
        import asyncio
        start = time.time()

        if reference_image_url:
            logger.warning(
                "[google] reference_image_url dropped: Imagen text-to-image REST path "
                "does not accept image input. Route to flux_kontext for img2img."
            )

        api_key = self._keys.get("google", "")
        if not api_key:
            logger.error("[google] GEMINI_API_KEY not set")
            return self._error(model_id, "GEMINI_API_KEY not set", 0.0)

        # Get the correct endpoint from model registry
        try:
            from app.services.smart.model_config import MODEL_REGISTRY
            endpoint = MODEL_REGISTRY.get(model_id, {}).get("endpoint", model_id)
        except Exception as e:
            logger.error("[google] Failed to load MODEL_REGISTRY: %s", e)
            endpoint = model_id

        # Map image_size to aspect ratio
        aspect_map = {
            "square_hd": "1:1",
            "landscape_16_9": "16:9",
            "portrait_9_16": "9:16",
            "landscape_4_3": "4:3",
        }
        aspect_ratio = aspect_map.get(image_size, "1:1")

        # CRITICAL: Imagen 3 + Imagen 4 + Gemini Imagen all interpret long
        # designer-brief prompts as "render this as a creative brief document"
        # → produce multi-panel pitch-decks with Option 1/2/3, Body:, [Website]
        # labels, hashtags, etc.
        # Anti-collage instructions DON'T help (parser reads "Not a collage" as
        # a positive trigger) and `negativePrompt` was DROPPED in Imagen 4.
        # Solution: distill the prompt — strip ALL designer-brief vocabulary,
        # placeholders, percentages, hashtags. Keep only scene + literal text.
        full_prompt = _distill_for_imagen(prompt)

        try:
            # Google AI Studio REST API endpoint for Imagen (uses :predict)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{endpoint}:predict"

            params: Dict = {
                "sampleCount":       min(num_images, 4),  # Max 4 per API call
                "aspectRatio":       aspect_ratio,
                "safetyFilterLevel": "BLOCK_ONLY_HIGH",
                "personGeneration":  "ALLOW_ADULT",
            }
            # NOTE: do NOT send `negativePrompt` to Imagen 4 — parameter is
            # silently ignored. Anti-collage signal is folded into positive
            # prompt above instead.

            payload = {
                "instances":  [{"prompt": full_prompt}],
                "parameters": params,
            }

            headers = {
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            }
            client = self._get_client("google")
            logger.info("[PAYLOAD][google] model=%s endpoint=%s body=%s", model_id, endpoint, _safe_json(payload))
            resp = await client.post(url, json=payload, headers=headers, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()

            # Extract image URLs or base64 data from :predict response
            urls = []
            if "predictions" in data:
                for prediction in data["predictions"]:
                    # Imagen returns base64 encoded images
                    b64_data = prediction.get("bytesBase64Encoded", "")
                    if b64_data:
                        # Convert base64 to data URI for immediate use
                        data_uri = f"data:image/png;base64,{b64_data}"
                        urls.append(data_uri)
                        logger.info("[google] Got base64 image (%d chars)", len(b64_data))

            if not urls:
                raise ValueError(f"No images from Imagen: {list(data.keys())}")

            return self._ok(urls, model_id, "google.ai", time.time() - start)

        except Exception as e:
            logger.error("[google] Imagen 3 API error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    async def _call_wavespeed(self, model_id: str, prompt: str, negative_prompt: str,
                              num_images: int, image_size: str, num_inference_steps: int,
                              guidance_scale: float, seed, reference_image_url: Optional[str] = None,
                              **kwargs) -> Dict:
        """WaveSpeed v3 async API — Grok Imagine, Wan 2.7, Hunyuan Image.

        Flow: POST /api/v3/{model_path} → task id → poll /predictions/{id}/result
        until status=completed (or failed/error).
        """
        import asyncio
        start = time.time()

        if reference_image_url:
            logger.warning(
                "[wavespeed] reference_image_url dropped: text-to-image paths for "
                "Grok/Wan/Hunyuan don't accept image input. Route to flux_kontext for img2img."
            )

        api_key = self._keys.get("wavespeed", "")
        if not api_key:
            logger.error("[wavespeed] WAVESPEED_API_KEY not set")
            return self._error(model_id, "WAVESPEED_API_KEY not set", 0.0)

        model_path = _WAVESPEED_MODEL_PATHS.get(model_id)
        if not model_path:
            logger.error("[wavespeed] Unknown model: %s", model_id)
            return self._error(model_id, f"Unknown WaveSpeed model: {model_id}", 0.0)

        # Map image_size → WaveSpeed "WIDTH*HEIGHT" string (Wan/Hunyuan format)
        size_map = {
            "square_hd":       "1024*1024",
            "landscape_16_9":  "1344*768",
            "portrait_9_16":   "768*1344",
            "landscape_4_3":   "1152*896",
        }
        size_str = size_map.get(image_size, "1024*1024")

        # Aspect ratio for Grok (different param shape)
        aspect_map = {
            "square_hd": "1:1",
            "landscape_16_9": "16:9",
            "portrait_9_16": "9:16",
            "landscape_4_3": "4:3",
        }
        aspect_ratio = aspect_map.get(image_size, "1:1")

        # WaveSpeed endpoints drop negative_prompt entirely. If the caller
        # passed anti-collage negatives, fold them into the positive prompt
        # as a hard imperative so the model still gets the signal.
        if negative_prompt:
            _neg_lower = negative_prompt.lower()
            if any(k in _neg_lower for k in ("collage", "panel", "grid", "option", "pitch deck", "design sheet")):
                prompt = (
                    "ONE single unified image, one cohesive composition. "
                    "Not a collage, not a grid, not multi-panel, not a design sheet, "
                    "not layout options A/B, not a brief document. "
                    + prompt
                )

        # Per-model payload (each endpoint accepts different params)
        if model_id == "grok_2_imagine":
            payload = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "num_images": max(1, min(num_images, 4)),
                "output_format": "jpeg",
            }
        else:  # wan_2_7, hunyuan_image
            payload = {
                "prompt": prompt,
                "size": size_str,
                "seed": seed if seed is not None else -1,
            }

        submit_url = f"{_WAVESPEED_BASE}/{model_path}"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        logger.info("[PAYLOAD][wavespeed] model=%s path=%s body=%s", model_id, model_path, _safe_json(payload))
        try:
            client = self._get_client("wavespeed")

            # 1) Submit task
            resp = await client.post(submit_url, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            submit_data = resp.json()
            task = submit_data.get("data") or {}
            task_id = task.get("id")
            if not task_id:
                raise ValueError(f"No task id from submit: {submit_data}")

            # Some models may return output immediately
            if task.get("status") in ("completed", "succeeded"):
                urls = self._extract_wavespeed_urls(task)
                if urls:
                    return self._ok(urls, model_id, "wavespeed.ai", time.time() - start)

            # 2) Poll result
            poll_url = f"{_WAVESPEED_BASE}/predictions/{task_id}/result"
            poll_headers = {"Authorization": f"Bearer {api_key}"}
            max_polls = 60  # ~120s ceiling @ 2s interval
            for _ in range(max_polls):
                await asyncio.sleep(2.0)
                poll_resp = await client.get(poll_url, headers=poll_headers, timeout=30.0)
                poll_resp.raise_for_status()
                result = (poll_resp.json() or {}).get("data") or {}
                status = (result.get("status") or "").lower()
                if status in ("completed", "succeeded"):
                    urls = self._extract_wavespeed_urls(result)
                    if not urls:
                        raise ValueError(f"No images from WaveSpeed: {list(result.keys())}")
                    return self._ok(urls, model_id, "wavespeed.ai", time.time() - start)
                if status in ("failed", "error"):
                    raise ValueError(f"WaveSpeed task failed: {result.get('error') or result}")

            raise TimeoutError(f"WaveSpeed task {task_id} timed out after {max_polls * 2}s")

        except Exception as e:
            logger.error("[wavespeed] API error: %s", e)
            return self._error(model_id, str(e), time.time() - start)

    def _extract_wavespeed_urls(self, task: Dict) -> List[str]:
        """Pull image URLs out of a WaveSpeed task result (shape varies by model)."""
        urls: List[str] = []
        outputs = task.get("outputs") or task.get("output") or []
        if isinstance(outputs, list):
            for item in outputs:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    u = item.get("url") or item.get("image_url")
                    if u:
                        urls.append(u)
        elif isinstance(outputs, dict):
            u = outputs.get("url") or outputs.get("image_url")
            if u:
                urls.append(u)
        # Some models put it under data.images
        for img in (task.get("images") or []):
            if isinstance(img, dict) and img.get("url"):
                urls.append(img["url"])
            elif isinstance(img, str):
                urls.append(img)
        return urls

    async def _upscale_fal(self, image_url: str, scale: int) -> Dict:
        start = time.time()
        client = self._get_client("fal")
        try:
            resp = await client.post(
                "https://fal.run/fal-ai/real-esrgan",
                json={"image_url": image_url, "scale": scale, "face_enhance": True},
            )
            resp.raise_for_status()
            data = resp.json()
            url = (data.get("image") or {}).get("url") or data.get("output_url")
            return self._ok([url] if url else [], "fal-ai/real-esrgan", "fal.ai", time.time() - start)
        except Exception as e:
            return self._error("fal-ai/real-esrgan", str(e), time.time() - start)

    # ── Payload builder (fal.ai specific) ─────────────────────────────────────

    @staticmethod
    def _build_fal_payload(model_id, prompt, negative_prompt, num_images, image_size,
                           steps, guidance, seed, reference_image_url,
                           rendering_speed, style, extra_image_urls=None) -> Dict:
        # Seedream / Recraft / Grok text-to-image payloads silently drop
        # `negative_prompt`. For those, fold an anti-collage imperative into
        # the positive prompt so the model still gets the "one unified image"
        # signal. Typography bucket defaults to Seedream at 1K — without this,
        # the Claude-authored negatives never reach the model and the output
        # keeps coming back as a pitch-deck.
        _NO_NEG_PROMPT_MODELS = (
            _SEEDREAM_IDS | _SEEDREAM_EDIT_IDS | _RECRAFT_IDS | _GROK_IDS
        )
        if model_id in _NO_NEG_PROMPT_MODELS and negative_prompt:
            _neg_lower = negative_prompt.lower()
            if any(k in _neg_lower for k in ("collage", "panel", "grid", "option", "pitch deck", "design sheet")):
                prompt = (
                    "ONE single unified image, one cohesive composition. "
                    "Not a collage, not a grid, not multi-panel, not a design sheet, "
                    "not layout options A/B, not a brief document. "
                    + prompt
                )

        # Set of model IDs that DO honor reference_image_url (either natively
        # in their t2i payload, or via the i2i endpoint swap above).
        _i2i_ok = (
            _KONTEXT_IDS
            | _SEEDREAM_EDIT_IDS
            | _IDEOGRAM_REMIX_IDS
            | {"fal-ai/flux-2-flex", "fal-ai/flux-2", "fal-ai/flux-2-pro",
               "fal-ai/flux-2-max", "fal-ai/flux-2/turbo", "fal-ai/flux/schnell"}
        )
        if reference_image_url and model_id not in _i2i_ok:
            logger.warning(
                "[fal] reference_image_url dropped: model=%s has no img2img path. "
                "Route to flux_kontext / flux_kontext_max for reference-guided gen.",
                model_id,
            )

        # ── Img2Img variants ──────────────────────────────────────────────
        if model_id in _SEEDREAM_EDIT_IDS:
            refs = [reference_image_url] if reference_image_url else []
            if extra_image_urls:
                refs.extend([u for u in extra_image_urls if u])
            p = {
                "prompt": prompt,
                "image_urls": refs,
                "image_size": image_size,
                "num_images": num_images,
                "max_images": num_images,
                "enable_safety_checker": True,
            }
            return p

        if model_id in _IDEOGRAM_REMIX_IDS:
            p = {
                "prompt": prompt,
                "image_url": reference_image_url,
                "image_size": image_size,
                "num_images": num_images,
                "rendering_speed": rendering_speed,
                "image_weight": 60,  # 1-100; 60 = balanced (preserve ref structure, allow prompt influence)
                "style_type": "REALISTIC",
            }
            if negative_prompt:
                p["negative_prompt"] = negative_prompt
            return p

        if model_id in _IDEOGRAM_IDS:
            p: Dict = {
                "prompt": prompt, "image_size": image_size,
                "num_images": num_images, "rendering_speed": rendering_speed,
                "style_type": "REALISTIC",  # prevents text/signage generation in background
            }
            if negative_prompt:
                p["negative_prompt"] = negative_prompt
            return p

        if model_id in _RECRAFT_IDS:
            p = {"prompt": prompt, "image_size": image_size, "n": num_images}
            if style:
                p["style"] = style
            return p

        if model_id in _SEEDREAM_IDS:
            return {
                "prompt": prompt,
                "image_size": image_size,
                "num_images": num_images,
                "max_images": num_images,
                "enable_safety_checker": True,
            }

        if model_id in _WAN_IDS:
            p = {
                "prompt": prompt,
                "image_size": image_size,
                "max_images": num_images,
                "num_inference_steps": steps,
                "guidance_scale": guidance,
                "enable_safety_checker": True,
                "image_format": "jpeg",
            }
            if negative_prompt:
                p["negative_prompt"] = negative_prompt
            if seed is not None:
                p["seed"] = seed
            return p

        if model_id in _GROK_IDS:
            return {
                "prompt": prompt,
                "num_images": num_images,
                "aspect_ratio": _kie_aspect_ratio_for_size(image_size),
                "resolution": "1k",
                "output_format": "jpeg",
            }

        if model_id in _KONTEXT_IDS:
            # Kontext API: aspect_ratio (NOT image_size), image_url required, output_format optional.
            # Sending image_size triggers fal 422 Unprocessable Entity.
            p = {
                "prompt":           prompt,
                "aspect_ratio":     _kie_aspect_ratio_for_size(image_size),
                "num_images":       num_images,
                "output_format":    "jpeg",
                "safety_tolerance": "2",
            }
            if guidance and guidance != 3.5:
                p["guidance_scale"] = guidance
            if seed is not None:
                p["seed"] = seed
            # Kontext Max supports multi-image compose via image_urls; Kontext Pro uses image_url.
            if extra_image_urls and model_id == "fal-ai/flux-pro/kontext/max":
                urls = [reference_image_url] if reference_image_url else []
                urls.extend([u for u in extra_image_urls if u])
                p["image_urls"] = urls
            elif reference_image_url:
                p["image_url"] = reference_image_url
            return p

        # Standard Flux payload
        if model_id in _SCHNELL_IDS:
            steps = min(steps, 12)
        p = {
            "prompt": prompt, "image_size": image_size,
            "num_inference_steps": steps, "num_images": num_images,
            "enable_safety_checker": False, "output_format": "jpeg",
        }
        if model_id not in _SCHNELL_IDS:
            p["guidance_scale"] = guidance
        if negative_prompt:
            p["negative_prompt"] = negative_prompt
        if seed is not None:
            p["seed"] = seed
        if reference_image_url:
            p["image_url"] = reference_image_url
        return p

    # ── Response helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_fal_urls(data: Dict) -> List[str]:
        images = data.get("images") or data.get("output") or []
        if isinstance(images, list):
            urls = []
            for img in images:
                url = img.get("url") if isinstance(img, dict) else img
                if url:
                    urls.append(url)
            return urls
        single = data.get("image")
        if isinstance(single, dict):
            url = single.get("url")
            return [url] if url else []
        return []

    @staticmethod
    def _ok(urls: List[str], model: str, backend: str, elapsed: float) -> Dict:
        return {
            "image_url": urls[0] if urls else None,
            "all_urls": urls, "image_b64": None,
            "metadata": {}, "success": bool(urls),
            "backend": backend, "model": model,
            "generation_time": elapsed,
        }

    @staticmethod
    def _error(model: str, msg: str, elapsed: float) -> Dict:
        return {
            "image_url": None, "all_urls": [], "image_b64": None,
            "metadata": {"error": msg}, "success": False,
            "backend": "multi_provider", "model": model,
            "generation_time": elapsed,
        }

    async def close(self):
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()

    def get_cheapest_cost(self, model_key: str) -> Optional[float]:
        """Returns cheapest available cost in USD for a model_key (based on available keys)."""
        model_key = _normalize_model_key(model_key)
        chain = MODEL_PROVIDER_CHAIN.get(model_key, [])
        for provider, _, cost in chain:
            if self._keys.get(provider):
                return cost
        return None


# Singleton
multi_client = MultiProviderClient()
