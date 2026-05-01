"""
12-Dimension Quality Critic — The Beast Standard Enforcer

Scores generated images on 12 dimensions + enforces 10 Beast Standard gates.
Minimum threshold: 8.5/10 overall + all Beast gates pass.
Any dimension < 7.0 → automatic REVISE with targeted feedback.

Philosophy: "The first 95% is strategy, psychology, culture, hierarchy, intention."
Standard: "I don't know how they made this, but I want one." — Covetable. Memorable. Emotionally precise.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from app.config.loader import config as beast_config

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Quality Dimensions Loading (from BeastConfig or legacy fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _load_quality_dimensions() -> Dict:
    """Load quality dimensions from BeastConfig or use legacy fallback."""
    beast_dimensions = beast_config.get_all_quality_dimensions()

    if beast_dimensions:
        # BeastConfig has dimensions - adapt to internal format
        adapted = {}
        for dim_id, dim_data in beast_dimensions.items():
            criteria_text = dim_data.get("criteria", "Quality assessment")
            questions = dim_data.get("evaluation_questions", [])

            # Get weight (normalized or raw)
            weight = dim_data.get("normalized_weight") or dim_data.get("weight", 0.08)

            # Get floor from scoring rubric (assume 7.0 default)
            floor = 7.0
            rubric = dim_data.get("scoring_rubric", {})
            if "7_solid" in rubric or "7_good" in rubric:
                floor = 7.0
            elif "6_acceptable" in rubric:
                floor = 6.0

            adapted[dim_id] = {
                "weight": weight,
                "floor": floor,
                "criteria": criteria_text,
                "questions": questions
            }

        logger.info(f"[quality_critic] Loaded {len(adapted)} dimensions from BeastConfig")
        return adapted

    # Fallback to legacy if BeastConfig not available
    logger.warning("[quality_critic] BeastConfig dimensions not available, using legacy")
    return _LEGACY_QUALITY_DIMENSIONS

# Legacy fallback (original hardcoded dimensions)
_LEGACY_QUALITY_DIMENSIONS = {
    # ── Visual Execution (40%) ────────────────────────────────────────────────
    "composition": {
        "weight": 0.12,
        "floor": 7.0,
        "criteria": "Rule of thirds, visual hierarchy, balance, negative space mastery",
        "questions": [
            "Does the image follow rule of thirds or intentional compositional grid?",
            "Is there clear visual hierarchy (one dominant element)?",
            "Is negative space used strategically or is the frame cluttered?",
            "Does the composition guide the eye naturally?"
        ]
    },
    "color_authority": {
        "weight": 0.10,
        "floor": 7.0,
        "criteria": "60-30-10 rule, palette sophistication, color psychology accuracy",
        "questions": [
            "Does the color palette follow 60-30-10 rule (max 3 colors + neutrals)?",
            "Are colors sophisticated and intentional (not rainbow chaos)?",
            "Does color psychology match the brand/goal (blue=trust, red=urgency)?",
            "Is there a clear dominant color story?"
        ]
    },
    "typography": {
        "weight": 0.10,
        "floor": 7.0,
        "criteria": "Hierarchy clarity, readability, font pairing, scale correctness",
        "questions": [
            "Is there clear typographic hierarchy (headline > subheadline > body)?",
            "Are fonts paired well (max 2-3 typefaces)?",
            "Is text readable at intended viewing distance/size?",
            "Are font sizes proportional to canvas (not too small, not overwhelming)?"
        ]
    },
    "polish": {
        "weight": 0.08,
        "floor": 7.0,
        "criteria": "Edge precision, texture refinement, lighting coherence",
        "questions": [
            "Are edges clean and intentional (not sloppy cutouts)?",
            "Is lighting coherent and realistic (not flat or over-lit)?",
            "Are textures refined (not muddy or over-processed)?",
            "Does it feel finished, not rushed?"
        ]
    },

    # ── Strategic Alignment (30%) ──────────────────────────────────────────────
    "concept_clarity": {
        "weight": 0.12,
        "floor": 7.0,
        "criteria": "Single idea clarity, message-visual alignment, Creative Bible adherence",
        "questions": [
            "Is there ONE clear idea (not multiple competing messages)?",
            "Does the visual serve the concept (not generic stock imagery)?",
            "If Creative Bible exists, does it follow emotional_territory?",
            "Can a stranger understand the message in 1.5 seconds?"
        ]
    },
    "brand_fit": {
        "weight": 0.10,
        "floor": 7.0,
        "criteria": "Brand equity preservation, tone consistency, logo integration",
        "questions": [
            "Does the visual feel consistent with brand identity?",
            "Is the tone appropriate (luxury feels luxury, playful feels playful)?",
            "If logo present, is it integrated naturally (not slapped on)?",
            "Would this pass brand guidelines review?"
        ]
    },
    "platform_native": {
        "weight": 0.08,
        "floor": 6.5,  # Slightly lower floor (platform is context-dependent)
        "criteria": "Platform aesthetic contract, safe zones, aspect ratio optimization",
        "questions": [
            "Does it respect platform aesthetic (TikTok ≠ LinkedIn)?",
            "Are safe zones preserved (text not in Instagram crop zone)?",
            "Is aspect ratio optimized for platform (not letterboxed)?",
            "Would this look native in the intended feed/context?"
        ]
    },

    # ── Emotional Impact (20%) ─────────────────────────────────────────────────
    "scroll_stop_power": {
        "weight": 0.10,
        "floor": 7.0,
        "criteria": "Attention capture in <1.5s, thumb-stopping quality",
        "questions": [
            "In a feed of 100 posts, does this stop the scroll?",
            "Is there immediate visual interest (not bland)?",
            "Does it hook attention in first 1.5 seconds?",
            "Is there a 'scroll-stop' element (contrast, scale, emotion)?"
        ]
    },
    "emotion_precision": {
        "weight": 0.10,
        "floor": 7.0,
        "criteria": "Single emotion clarity, emotional_territory match",
        "questions": [
            "Can you name the emotion in 2 words (joy, urgency, aspiration)?",
            "Is it ONE emotion (not confused mix)?",
            "If Creative Bible has emotional_territory, does it match?",
            "Does the emotion serve the goal (awareness vs conversion)?"
        ]
    },

    # ── Technical Excellence (10%) ─────────────────────────────────────────────
    "resolution_quality": {
        "weight": 0.05,
        "floor": 6.0,  # Lower floor (technical issues less critical than strategy)
        "criteria": "Sharpness, artifact-free, proper exposure",
        "questions": [
            "Is the image sharp and free of blur artifacts?",
            "Are there AI generation artifacts (weird hands, faces)?",
            "Is exposure correct (not over/underexposed)?",
            "Is resolution sufficient for intended use?"
        ]
    },
    "text_legibility": {
        "weight": 0.05,
        "floor": 6.0,
        "criteria": "Contrast sufficiency, size appropriateness, hierarchy execution",
        "questions": [
            "Is text readable against background (sufficient contrast)?",
            "Are text sizes appropriate (not too small)?",
            "Is typographic hierarchy executed correctly?",
            "Does text overlay preserve image composition?"
        ]
    },
}

# Load actual quality dimensions (BeastConfig or legacy)
QUALITY_DIMENSIONS = _load_quality_dimensions()

# ══════════════════════════════════════════════════════════════════════════════
# The 10 Beast Standards (Pass/Fail Gates)
# ══════════════════════════════════════════════════════════════════════════════

def _load_beast_gates() -> Dict:
    """Load Beast Standard gates from BeastConfig or use legacy fallback."""
    beast_gates = beast_config.get_beast_gates()

    if beast_gates:
        # BeastConfig has gates - adapt to internal format
        adapted = {}
        for gate_id, gate_data in beast_gates.items():
            adapted[gate_id] = {
                "name": gate_data.get("gate_name", gate_id.replace("_", " ").title()),
                "criteria": gate_data.get("criteria", "Quality gate"),
                "pass_threshold": 7.0,  # Default threshold
            }

        logger.info(f"[quality_critic] Loaded {len(adapted)} Beast gates from BeastConfig")
        return adapted

    # Fallback to legacy
    logger.warning("[quality_critic] BeastConfig gates not available, using legacy")
    return _LEGACY_BEAST_STANDARDS

# Legacy fallback (original hardcoded gates)
_LEGACY_BEAST_STANDARDS = {
    "stranger_test": {
        "name": "Stranger Test",
        "criteria": "A stranger with zero context understands the core message in 1.5 seconds",
        "pass_threshold": 7.5,  # Out of 10
    },
    "scroll_stop_test": {
        "name": "Scroll-Stop Test",
        "criteria": "In a feed of 100 posts, this one stops the thumb",
        "pass_threshold": 7.5,
    },
    "remove_color_test": {
        "name": "Remove-Color Test",
        "criteria": "The composition works in pure black and white (not color-dependent)",
        "pass_threshold": 7.0,
    },
    "size_10pct_test": {
        "name": "10% Size Test",
        "criteria": "The design still communicates at 10% of intended size (thumbnail test)",
        "pass_threshold": 7.0,
    },
    "tomorrow_test": {
        "name": "Tomorrow Test",
        "criteria": "Does not feel dated within 6 months (current aesthetic, not trendy)",
        "pass_threshold": 7.5,
    },
    "brand_remove_test": {
        "name": "Brand-Remove Test",
        "criteria": "Remove the logo — it still feels like the brand (brand equity beyond logo)",
        "pass_threshold": 7.0,
    },
    "emotion_test": {
        "name": "Emotion Test",
        "criteria": "Can name the SINGLE emotion this triggers in 2 words (emotion precision)",
        "pass_threshold": 7.5,
    },
    "competitor_test": {
        "name": "Competitor Test",
        "criteria": "Looks better than what the top 3 competitors produce (commercial standard)",
        "pass_threshold": 8.0,
    },
    "context_test": {
        "name": "Context Test",
        "criteria": "Fits where it will live — feed, wall, screen, print (context-native)",
        "pass_threshold": 7.5,
    },
    "memory_test": {
        "name": "Memory Test",
        "criteria": "24 hours later, someone can describe this from memory (memorable)",
        "pass_threshold": 7.5,
    },
}

# Load actual Beast gates (BeastConfig or legacy)
BEAST_STANDARDS = _load_beast_gates()

# ══════════════════════════════════════════════════════════════════════════════
# Environment Configuration (with BeastConfig fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _load_quality_thresholds():
    """Load quality thresholds from BeastConfig or environment variables."""
    thresholds = beast_config.get_scoring_thresholds()

    if thresholds:
        return {
            "quality_threshold": thresholds.get("minimum_to_ship", 8.5),
            "dimension_floor": thresholds.get("dimension_floor", 7.0),
            "max_revision_cycles": thresholds.get("max_revision_cycles", 3),
            "beast_gates_min_pass": thresholds.get("gates_minimum_pass", 9),
        }

    # Fallback to environment variables
    return {
        "quality_threshold": float(os.getenv("QUALITY_CRITIC_THRESHOLD", "8.5")),
        "dimension_floor": float(os.getenv("QUALITY_DIMENSION_FLOOR", "7.0")),
        "max_revision_cycles": int(os.getenv("QUALITY_REVISION_MAX_CYCLES", "3")),
        "beast_gates_min_pass": int(os.getenv("QUALITY_BEAST_GATES_MIN", "9")),
    }

_THRESHOLDS = _load_quality_thresholds()

QUALITY_THRESHOLD = _THRESHOLDS["quality_threshold"]
DIMENSION_FLOOR = _THRESHOLDS["dimension_floor"]
MAX_REVISION_CYCLES = _THRESHOLDS["max_revision_cycles"]
BEAST_GATES_MIN_PASS = _THRESHOLDS["beast_gates_min_pass"]

# Tier-specific config helper
def _get_tier_config(tier: str) -> dict:
    """Get tier-specific quality config from .env (with fallback to global)."""
    tier_upper = tier.upper()
    return {
        "threshold": float(os.getenv(f"QUALITY_CRITIC_THRESHOLD_{tier_upper}", QUALITY_THRESHOLD)),
        "dimension_floor": float(os.getenv(f"QUALITY_DIMENSION_FLOOR_{tier_upper}", DIMENSION_FLOOR)),
        "max_cycles": int(os.getenv(f"QUALITY_REVISION_MAX_CYCLES_{tier_upper}", MAX_REVISION_CYCLES)),
        "beast_gates_min": int(os.getenv(f"QUALITY_BEAST_GATES_MIN_{tier_upper}", BEAST_GATES_MIN_PASS)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Quality Critic Agent
# ══════════════════════════════════════════════════════════════════════════════

class QualityCritic:
    """
    12-Dimension Quality Critic — The Beast Standard Enforcer

    Scores on 12 dimensions, enforces 10 Beast Standard gates.
    Returns APPROVED / REVISE / ESCALATE based on quality thresholds.
    Supports tier-specific configuration via .env.
    """

    def __init__(self, tier: str = "premium"):
        self.gemini_client = None
        self.groq_client = None
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.tier = tier.lower()
        self.config = _get_tier_config(self.tier)
        # Quality Critic provider: "gemini" (default) or "groq" (optional, requires groq package)
        self.provider = os.getenv("QUALITY_CRITIC_PROVIDER", "gemini").lower()

    def _get_gemini_client(self):
        """Get Gemini client from shared pool (round-robin across multiple API keys)."""
        from app.services.smart.design_agent_chain import _get_gemini_client as get_pooled_client
        # Use the shared client pool for automatic key rotation and fallback
        return get_pooled_client()

    def _get_groq_client(self):
        """Get Groq client for Llama 3.2 Vision."""
        if self.groq_client is None:
            from groq import AsyncGroq
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY not set for Quality Critic")
            self.groq_client = AsyncGroq(api_key=api_key)
        return self.groq_client

    async def critique(
        self,
        image_url: str,
        creative_bible: Dict,
        design_brief: Dict,
        platform: str,
        revision_cycle: int = 0,
    ) -> Dict:
        """
        Full quality critique — 12 dimensions + 10 Beast gates.

        Returns:
        {
            "overall_score": 8.7,
            "verdict": "APPROVED" | "REVISE" | "ESCALATE",
            "dimensions": {
                "composition": {"score": 9.2, "reasoning": "..."},
                "color_authority": {"score": 8.5, "reasoning": "..."},
                ...
            },
            "beast_gates": {
                "stranger_test": {"pass": True, "score": 8.0},
                "scroll_stop_test": {"pass": True, "score": 8.5},
                ...
            },
            "gates_passed": 9,
            "revision_notes": "Strengthen CTA contrast (+2 points text_legibility)",
            "revision_route_to": "layout_planner",  # Which agent to fix
            "revision_cycle": 1,
            "critique_summary": "Strong composition and concept, but text legibility needs work"
        }
        """
        try:
            logger.info("[quality_critic] Starting critique for image_url=%s cycle=%d", image_url[:60], revision_cycle)

            # ── Run 12-dimension scoring (parallel for speed) ────────────────────
            dimension_scores = await self._score_all_dimensions(
                image_url, creative_bible, design_brief, platform
            )

            # ── Calculate weighted overall score ──────────────────────────────────
            overall_score = sum(
                dimension_scores[dim]["score"] * QUALITY_DIMENSIONS[dim]["weight"]
                for dim in QUALITY_DIMENSIONS
            )
            overall_score = round(overall_score, 2)

            # ── Run 10 Beast Standard gates ───────────────────────────────────────
            beast_gates = await self._validate_beast_gates(
                image_url, creative_bible, design_brief, dimension_scores
            )
            gates_passed = sum(1 for gate in beast_gates.values() if gate["pass"])

            # ── Determine verdict ──────────────────────────────────────────────────
            verdict, revision_notes, route_to = self._determine_verdict(
                overall_score, dimension_scores, gates_passed, revision_cycle
            )

            # ── Generate critique summary ──────────────────────────────────────────
            critique_summary = self._generate_summary(dimension_scores, beast_gates, verdict)

            result = {
                "overall_score": overall_score,
                "verdict": verdict,
                "dimensions": dimension_scores,
                "beast_gates": beast_gates,
                "gates_passed": gates_passed,
                "revision_notes": revision_notes,
                "revision_route_to": route_to,
                "revision_cycle": revision_cycle,
                "critique_summary": critique_summary,
                "timestamp": self._timestamp(),
            }

            logger.info(
                "[quality_critic] Verdict=%s score=%.2f gates=%d/10 cycle=%d",
                verdict, overall_score, gates_passed, revision_cycle
            )
            return result

        except Exception as e:
            logger.exception("[quality_critic] Critique failed: %s", e)
            return {
                "overall_score": 0.0,
                "verdict": "ESCALATE",
                "dimensions": {},
                "beast_gates": {},
                "gates_passed": 0,
                "revision_notes": f"Quality Critic failed: {e}",
                "revision_route_to": "human",
                "revision_cycle": revision_cycle,
                "critique_summary": "Error during quality critique",
                "error": str(e),
            }

    async def validate_rendered_text(
        self,
        image_url: str,
        expected_texts: List[str],
        model_key: str = "",
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """Log-only Gemini Vision check for expected ad text.

        This method never retries generation and never changes the returned
        image. It exists only to produce telemetry for typography/ad prompts.
        """
        expected: List[str] = []
        for item in expected_texts or []:
            text = str(item or "").strip()
            if text and text not in expected:
                expected.append(text[:120])

        result: Dict[str, Any] = {
            "checked": False,
            "model_key": model_key,
            "expected": expected,
            "items": [],
            "all_rendered": None,
            "error": None,
        }
        if not image_url or not expected:
            return result

        try:
            image_b64 = await self._fetch_image_base64(image_url)
            system_prompt = (
                "You are a strict OCR and advertising QA inspector. "
                "Check only whether the requested text strings are visibly "
                "rendered in the image. Return JSON only."
            )
            user_prompt = (
                "For each expected string, decide if it appears as readable "
                "text in the image. Minor case differences are acceptable, but "
                "misspellings, missing words, or garbled letters are failures. "
                "Return exactly this JSON shape: "
                "{\"items\":[{\"expected\":\"...\",\"rendered\":true,"
                "\"confidence\":0.0,\"observed_text\":\"...\"}],"
                "\"all_rendered\":true}.\n\n"
                f"Expected strings: {json.dumps(expected, ensure_ascii=True)}"
            )
            raw_text = await self._call_vision_model(
                system_prompt,
                user_prompt,
                image_b64,
                max_tokens=1200,
            )
            parsed = self._extract_json(raw_text)
            raw_items = parsed.get("items") if isinstance(parsed, dict) else []
            if not isinstance(raw_items, list):
                raw_items = []

            by_expected = {
                str(item.get("expected", "")).strip().lower(): item
                for item in raw_items
                if isinstance(item, dict)
            }

            items: List[Dict[str, Any]] = []
            for expected_text in expected:
                item = by_expected.get(expected_text.lower(), {})
                rendered = bool(item.get("rendered", False))
                try:
                    confidence = float(item.get("confidence", 0.0) or 0.0)
                except (TypeError, ValueError):
                    confidence = 0.0
                confidence = max(0.0, min(1.0, confidence))
                observed = str(item.get("observed_text", "") or "")[:160]
                row = {
                    "expected": expected_text,
                    "rendered": rendered,
                    "confidence": round(confidence, 3),
                    "observed_text": observed,
                }
                items.append(row)
                logger.info(
                    '[text-validation] trace=%s model=%s expected="%s" rendered=%s confidence=%.2f observed="%s"',
                    trace_id,
                    model_key,
                    expected_text,
                    rendered,
                    confidence,
                    observed,
                )
                print(
                    f'[text-validation] expected="{expected_text}" rendered={rendered} confidence={confidence:.2f}',
                    flush=True,
                )

            result["checked"] = True
            result["items"] = items
            result["all_rendered"] = all(item["rendered"] for item in items)
            return result
        except Exception as e:
            logger.warning(
                "[text-validation] trace=%s model=%s failed: %s",
                trace_id,
                model_key,
                e,
            )
            result["error"] = str(e)
            return result

    async def _call_vision_model(self, system_prompt: str, user_prompt: str, image_b64: str, max_tokens: int = 4000) -> str:
        """Call vision model (Gemini default, Groq optional) for image analysis with automatic fallback."""
        if self.provider == "groq":
            # Try Groq Llama 3.2 Vision (free tier, generous limits) - only if explicitly requested
            try:
                client = self._get_groq_client()
                import base64

                response = await client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",  # Llama 3.2 90B with vision (11B deprecated)
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_b64}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": user_prompt
                                }
                            ]
                        }
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                raw_text = response.choices[0].message.content
                logger.info(f"[quality_critic] Groq response: {len(raw_text)} chars, finish_reason={response.choices[0].finish_reason}")
                return raw_text
            except Exception as e:
                # Silently fall back to Gemini (no warning needed - Groq is optional)
                pass

        # Gemini (default provider)
        client = self._get_gemini_client()
        from google.genai import types

        response = await client.aio.models.generate_content(
            model=self.gemini_model,
            contents=[{
                "role": "user",
                "parts": [
                    {"text": user_prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
                ]
            }],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        raw_text = response.text or "{}"
        finish_reason = response.candidates[0].finish_reason if response.candidates else "N/A"
        logger.info(f"[quality_critic] Gemini response: {len(raw_text)} chars, finish_reason={finish_reason}")
        return raw_text

    async def _score_all_dimensions(
        self,
        image_url: str,
        creative_bible: Dict,
        design_brief: Dict,
        platform: str,
    ) -> Dict:
        """Score all 12 dimensions using vision model with smart batching for free tier."""
        # For Gemini free tier: split into 3 batches to avoid MAX_TOKENS truncation
        # Each batch gets 4 dimensions, fits within ~150 token limit

        try:
            # Fetch image first
            image_b64 = await self._fetch_image_base64(image_url)
            logger.info(f"[quality_critic] Image fetched, size: {len(image_b64)} bytes, provider={self.provider}")

            # Split dimensions into 6 batches (2 dims each) to fit Gemini free tier token limits
            all_dims = list(QUALITY_DIMENSIONS.keys())
            batch_size = 2
            batches = [all_dims[i:i + batch_size] for i in range(0, len(all_dims), batch_size)]

            logger.info(f"[quality_critic] Splitting {len(all_dims)} dimensions into {len(batches)} batches for parallel scoring")

            # Build MINIMAL system prompt (dimension details go in user prompt per batch)
            bible_context = ""
            if creative_bible:
                bible_context = f"Creative Bible: {creative_bible.get('emotional_territory', 'N/A')}"

            system_base = f"Senior Creative Director. Score image quality dimensions 0-10. {bible_context} Platform: {platform}"

            # Call each batch in parallel
            async def score_batch(batch_dims: List[str], batch_num: int) -> Dict:
                # Ultra-concise dimension spec for token efficiency
                dims_spec = "\n".join([
                    f"{dim}: {QUALITY_DIMENSIONS[dim]['criteria'][:80]}"
                    for dim in batch_dims
                ])

                prompt = f"Score each 0-10. Return ONLY valid JSON: {{\"dim_name\": {{\"score\": 8.0, \"reasoning\": \"brief text\"}}}}\n\nIMPORTANT: Keep reasoning under 50 chars. Use double quotes only, escape any quotes in text.\n\n{dims_spec}"

                raw_text = await self._call_vision_model(system_base, prompt, image_b64, max_tokens=2000)
                logger.info(f"[quality_critic] Batch {batch_num+1}/{len(batches)}: {len(raw_text)} chars")
                return self._extract_json(raw_text)

            # Execute all batches in parallel
            batch_results = await asyncio.gather(*[
                score_batch(batch, i) for i, batch in enumerate(batches)
            ])

            # Merge results from all batches
            scores_json = {}
            for batch_result in batch_results:
                scores_json.update(batch_result)

            logger.info(f"[quality_critic] Merged {len(scores_json)} dimension scores from {len(batches)} batches")

            # Parse and validate scores
            dimension_scores = {}
            for dim_name, dim_config in QUALITY_DIMENSIONS.items():
                dim_data = scores_json.get(dim_name, {})
                score = float(dim_data.get("score", 5.0))
                score = max(0.0, min(10.0, score))  # Clamp 0-10
                reasoning = str(dim_data.get("reasoning", "No reasoning provided"))

                dimension_scores[dim_name] = {
                    "score": round(score, 1),
                    "reasoning": reasoning,
                    "weight": dim_config["weight"],
                    "floor": dim_config["floor"],
                    "below_floor": score < dim_config["floor"],
                }

            return dimension_scores

        except Exception as e:
            logger.error("[quality_critic] Dimension scoring failed: %s", e, exc_info=True)
            # Fallback: return neutral scores
            return {
                dim: {"score": 7.0, "reasoning": f"Error: {e}", "weight": cfg["weight"], "floor": cfg["floor"], "below_floor": False}
                for dim, cfg in QUALITY_DIMENSIONS.items()
            }

    def _build_dimension_system_prompt(self, creative_bible: Dict, design_brief: Dict, platform: str) -> str:
        """Build system prompt with all 12 dimensions + context."""
        bible_context = ""
        if creative_bible:
            bible_context = f"""
CREATIVE BIBLE (Locked Contract):
- Emotional Territory: {creative_bible.get("emotional_territory", "N/A")}
- Visual Metaphors: {", ".join(creative_bible.get("visual_metaphors", []))}
- Forbidden Elements: {", ".join(creative_bible.get("forbidden_elements", []))}
- Color Story: {creative_bible.get("dominant_color_story", "N/A")}
- Composition Archetype: {creative_bible.get("composition_archetype", "N/A")}
"""

        platform_context = f"Platform: {platform} (respect platform aesthetic contracts)"

        dimensions_spec = "\n".join([
            f"{i+1}. **{dim_name}** (weight {cfg['weight']:.0%}, floor {cfg['floor']}):\n"
            f"   Criteria: {cfg['criteria']}\n"
            f"   Questions: {'; '.join(cfg['questions'])}"
            for i, (dim_name, cfg) in enumerate(QUALITY_DIMENSIONS.items())
        ])

        return f"""You are a Senior Creative Director and Quality Critic at a world-class advertising agency.

{bible_context}
{platform_context}

TASK: Score this image on 12 quality dimensions (0-10 scale).
For each dimension:
- Score 0-10 (10 = perfection, 0 = failure)
- Provide 1-2 sentence reasoning
- Be CRITICAL but FAIR (8+ is rare, deserves praise; <7 needs fixing)

DIMENSIONS TO SCORE:
{dimensions_spec}

RETURN JSON FORMAT (this exact structure):
{{
  "composition": {{"score": 8.5, "reasoning": "..."}},
  "color_authority": {{"score": 7.0, "reasoning": "..."}},
  "typography": {{"score": 9.0, "reasoning": "..."}},
  "polish": {{"score": 8.0, "reasoning": "..."}},
  "concept_clarity": {{"score": 9.5, "reasoning": "..."}},
  "brand_fit": {{"score": 8.5, "reasoning": "..."}},
  "platform_native": {{"score": 7.5, "reasoning": "..."}},
  "scroll_stop_power": {{"score": 8.0, "reasoning": "..."}},
  "emotion_precision": {{"score": 9.0, "reasoning": "..."}},
  "resolution_quality": {{"score": 9.5, "reasoning": "..."}},
  "text_legibility": {{"score": 7.0, "reasoning": "..."}}
}}

CRITICAL REMINDER:
- If Creative Bible exists, validate adherence (concept_clarity, emotion_precision, brand_fit)
- Platform aesthetic matters (TikTok ≠ LinkedIn)
- Commercial standard, not art gallery (scroll_stop_power, brand_fit critical)
"""

    async def _validate_beast_gates(
        self,
        image_url: str,
        creative_bible: Dict,
        design_brief: Dict,
        dimension_scores: Dict,
    ) -> Dict:
        """Validate 10 Beast Standard gates (Pass/Fail)."""
        # For speed, batch all 10 gates into ONE Gemini call
        system_prompt = self._build_beast_gates_system_prompt(creative_bible, design_brief)
        user_prompt = "Score 10 Beast gates (0-10). Brief reason per gate. JSON only, start with {."

        try:
            # Fetch image
            image_b64 = await self._fetch_image_base64(image_url)

            # Call vision model
            raw_text = await self._call_vision_model(system_prompt, user_prompt, image_b64, max_tokens=3000)
            gates_json = self._extract_json(raw_text)

            # Parse and validate gates
            beast_gates = {}
            for gate_id, gate_config in BEAST_STANDARDS.items():
                gate_data = gates_json.get(gate_id, {})
                score = float(gate_data.get("score", 5.0))
                score = max(0.0, min(10.0, score))
                passed = score >= gate_config["pass_threshold"]

                beast_gates[gate_id] = {
                    "name": gate_config["name"],
                    "pass": passed,
                    "score": round(score, 1),
                    "threshold": gate_config["pass_threshold"],
                    "reasoning": str(gate_data.get("reasoning", "No reasoning")),
                }

            return beast_gates

        except Exception as e:
            logger.error("[quality_critic] Beast gates validation failed: %s", e, exc_info=True)
            # Fallback: all gates fail
            return {
                gate_id: {
                    "name": cfg["name"],
                    "pass": False,
                    "score": 5.0,
                    "threshold": cfg["pass_threshold"],
                    "reasoning": f"Error: {e}",
                }
                for gate_id, cfg in BEAST_STANDARDS.items()
            }

    def _build_beast_gates_system_prompt(self, creative_bible: Dict, design_brief: Dict) -> str:
        """Build system prompt for Beast Standard gates."""
        gates_spec = "\n".join([
            f"{i+1}. **{cfg['name']}** (threshold {cfg['pass_threshold']}):\n"
            f"   {cfg['criteria']}"
            for i, (gate_id, cfg) in enumerate(BEAST_STANDARDS.items())
        ])

        return f"""You are evaluating whether this image meets THE BEAST STANDARDS — the highest commercial creative bar.

These are PASS/FAIL gates. An image must pass 9/10 to be approved.

THE 10 BEAST STANDARDS:
{gates_spec}

RETURN JSON FORMAT (this exact structure):
{{
  "stranger_test": {{"score": 8.0, "reasoning": "..."}},
  "scroll_stop_test": {{"score": 7.5, "reasoning": "..."}},
  "remove_color_test": {{"score": 7.0, "reasoning": "..."}},
  "size_10pct_test": {{"score": 8.5, "reasoning": "..."}},
  "tomorrow_test": {{"score": 7.5, "reasoning": "..."}},
  "brand_remove_test": {{"score": 7.0, "reasoning": "..."}},
  "emotion_test": {{"score": 9.0, "reasoning": "..."}},
  "competitor_test": {{"score": 8.0, "reasoning": "..."}},
  "context_test": {{"score": 8.5, "reasoning": "..."}},
  "memory_test": {{"score": 7.5, "reasoning": "..."}}
}}

Score 0-10 for each gate. Be CRITICAL — these are the world's highest standards.
"""

    def _determine_verdict(
        self,
        overall_score: float,
        dimension_scores: Dict,
        gates_passed: int,
        revision_cycle: int,
    ) -> tuple[Literal["APPROVED", "REVISE", "ESCALATE"], str, str]:
        """
        Determine verdict based on scores + gates.

        Returns: (verdict, revision_notes, route_to_agent)
        """
        # Use tier-specific config
        max_cycles = self.config["max_cycles"]
        beast_gates_min = self.config["beast_gates_min"]
        threshold = self.config["threshold"]

        # ── ESCALATE: Max revision cycles reached ─────────────────────────────────
        if revision_cycle >= max_cycles:
            return (
                "ESCALATE",
                f"Max revision cycles ({max_cycles}) reached. Human review required.",
                "human"
            )

        # ── ESCALATE: Too many Beast gates failed ─────────────────────────────────
        if gates_passed < beast_gates_min:
            return (
                "ESCALATE",
                f"Only {gates_passed}/10 Beast gates passed (min {beast_gates_min}). Fundamental issues.",
                "creative_director"  # Start over
            )

        # ── REVISE: Overall score too low ──────────────────────────────────────────
        if overall_score < threshold:
            # Find lowest-scoring dimension below floor
            weak_dims = [
                (dim, data["score"])
                for dim, data in dimension_scores.items()
                if data["below_floor"]
            ]
            if weak_dims:
                weak_dims.sort(key=lambda x: x[1])  # Lowest first
                weakest_dim, weakest_score = weak_dims[0]
                route_to = self._dimension_to_agent(weakest_dim)
                notes = f"Overall score {overall_score:.1f} < {QUALITY_THRESHOLD}. Weakest: {weakest_dim} ({weakest_score:.1f}). {dimension_scores[weakest_dim]['reasoning']}"
                return ("REVISE", notes, route_to)
            else:
                notes = f"Overall score {overall_score:.1f} < {threshold}. Minor improvements needed across dimensions."
                return ("REVISE", notes, "layout_planner")

        # ── REVISE: Specific dimension below floor ────────────────────────────────
        for dim_name, dim_data in dimension_scores.items():
            if dim_data["below_floor"]:
                route_to = self._dimension_to_agent(dim_name)
                notes = f"{dim_name} score {dim_data['score']:.1f} < floor {dim_data['floor']}. {dim_data['reasoning']}"
                return ("REVISE", notes, route_to)

        # ── APPROVED ───────────────────────────────────────────────────────────────
        return ("APPROVED", f"Score {overall_score:.1f}/10, {gates_passed}/10 gates passed. Beast Standard achieved.", "")

    def _dimension_to_agent(self, dimension_name: str) -> str:
        """Map dimension to responsible agent for revision routing."""
        # Try to load from BeastConfig first
        beast_routing = beast_config.get_revision_routing()

        if beast_routing and dimension_name in beast_routing:
            agent = beast_routing[dimension_name]
            logger.info(f"[quality_critic] BeastConfig routing: {dimension_name} → {agent}")
            return agent

        # Fallback to legacy routing
        legacy_routing = {
            "composition": "layout_planner",
            "color_authority": "creative_director",  # Palette issue
            "typography": "layout_planner",
            "polish": "image_prompter",  # Re-generate with refinement notes
            "concept_clarity": "creative_director",  # Concept issue
            "brand_fit": "brand_intel",
            "platform_native": "layout_planner",
            "scroll_stop_power": "creative_director",  # Weak concept
            "emotion_precision": "creative_director",  # Emotion issue
            "resolution_quality": "image_prompter",  # Re-generate
            "text_legibility": "layout_planner",
        }
        return legacy_routing.get(dimension_name, "layout_planner")

    def _generate_summary(self, dimension_scores: Dict, beast_gates: Dict, verdict: str) -> str:
        """Generate human-readable critique summary."""
        # Top 3 strengths
        sorted_dims = sorted(dimension_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        strengths = [f"{dim} ({data['score']:.1f})" for dim, data in sorted_dims[:3]]

        # Top 3 weaknesses
        weaknesses = [f"{dim} ({data['score']:.1f})" for dim, data in sorted_dims[-3:]]

        # Failed gates
        failed_gates = [gate["name"] for gate in beast_gates.values() if not gate["pass"]]

        summary_parts = []
        if verdict == "APPROVED":
            summary_parts.append("✅ BEAST STANDARD ACHIEVED")
        elif verdict == "REVISE":
            summary_parts.append("⚠️ REVISION NEEDED")
        else:
            summary_parts.append("🚨 ESCALATE TO HUMAN")

        summary_parts.append(f"Strengths: {', '.join(strengths)}")
        if weaknesses:
            summary_parts.append(f"Needs work: {', '.join(weaknesses)}")
        if failed_gates:
            summary_parts.append(f"Failed gates: {', '.join(failed_gates)}")

        return " | ".join(summary_parts)

    async def _fetch_image_base64(self, image_url: str) -> str:
        """Fetch image and convert to base64 for Gemini Vision."""
        import httpx
        import base64

        try:
            if image_url.startswith("data:image"):
                # Already base64 data URL
                return image_url.split(",")[1]

            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=30.0)
                response.raise_for_status()
                return base64.b64encode(response.content).decode("ascii")
        except Exception as e:
            logger.error("[quality_critic] Failed to fetch image %s: %s", image_url[:60], e)
            raise

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from Gemini response (handles markdown fences, partial JSON, common issues)."""
        import re
        text = text.strip()

        # Log raw response for debugging
        logger.info(f"[quality_critic] Raw Gemini response length: {len(text)} chars")
        if len(text) < 500:
            logger.info(f"[quality_critic] Raw response: {text}")
        else:
            logger.info(f"[quality_critic] Raw response (first 500): {text[:500]}")

        # Remove markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()

        # Try direct parse first
        try:
            parsed = json.loads(text)
            logger.info(f"[quality_critic] Successfully parsed JSON with {len(parsed)} keys")
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"[quality_critic] Initial JSON parse failed: {e}")

            # Try to find and extract {...} block
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_text = match.group()

                # Fix common issues:
                # 1. Trailing comma before closing brace
                json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
                # 2. Incomplete JSON - add closing brace if missing
                if json_text.count('{') > json_text.count('}'):
                    json_text += '}'
                # 3. Unescaped quotes in strings (rough fix)
                # json_text = re.sub(r'(?<!\\)"([^"]*)"([^"]*)"', r'"\1\"\2"', json_text)

                try:
                    parsed = json.loads(json_text)
                    logger.info(f"[quality_critic] Extracted and fixed JSON with {len(parsed)} keys")
                    return parsed
                except Exception as e2:
                    logger.error(f"[quality_critic] Fixed JSON parse also failed: {e2}")
                    # Last resort - try to salvage partial data
                    try:
                        # Extract individual key-value pairs
                        partial = {}
                        pairs = re.findall(r'"(\w+)":\s*\{[^}]*"score":\s*([\d.]+)[^}]*\}', json_text)
                        for key, score in pairs:
                            partial[key] = {"score": float(score), "reasoning": "Partial parse"}
                        if partial:
                            logger.warning(f"[quality_critic] Salvaged {len(partial)} partial scores")
                            return partial
                    except:
                        pass

        logger.error(f"[quality_critic] JSON parse failed completely. Text was: {text[:1000]}")
        return {}

    def _timestamp(self) -> str:
        """ISO-8601 timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════════════

quality_critic = QualityCritic()
