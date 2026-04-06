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
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Quality Dimensions (12 total — weighted scoring)
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_DIMENSIONS = {
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

# ══════════════════════════════════════════════════════════════════════════════
# The 10 Beast Standards (Pass/Fail Gates)
# ══════════════════════════════════════════════════════════════════════════════

BEAST_STANDARDS = {
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

# ══════════════════════════════════════════════════════════════════════════════
# Environment Configuration
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_THRESHOLD = float(os.getenv("QUALITY_CRITIC_THRESHOLD", "8.5"))  # Min overall score
DIMENSION_FLOOR = float(os.getenv("QUALITY_DIMENSION_FLOOR", "7.0"))     # Min per dimension
MAX_REVISION_CYCLES = int(os.getenv("QUALITY_REVISION_MAX_CYCLES", "3")) # Max revision loops
BEAST_GATES_MIN_PASS = int(os.getenv("QUALITY_BEAST_GATES_MIN", "9"))    # Min gates to pass (out of 10)

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
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.tier = tier.lower()
        self.config = _get_tier_config(self.tier)

    def _get_gemini_client(self):
        """Lazy init Gemini client."""
        if self.gemini_client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set for Quality Critic")
            self.gemini_client = genai.Client(api_key=api_key)
        return self.gemini_client

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

    async def _score_all_dimensions(
        self,
        image_url: str,
        creative_bible: Dict,
        design_brief: Dict,
        platform: str,
    ) -> Dict:
        """Score all 12 dimensions in parallel using Gemini Vision."""
        # For speed, we batch all dimensions into ONE Gemini call with structured output
        system_prompt = self._build_dimension_system_prompt(creative_bible, design_brief, platform)
        user_prompt = "Analyze this image across all 12 quality dimensions. Score each 0-10 with reasoning."

        try:
            client = self._get_gemini_client()
            from google.genai import types

            # Single call with all 12 dimensions
            response = await client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[
                    {"role": "user", "parts": [
                        {"text": user_prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": await self._fetch_image_base64(image_url)}}
                    ]}
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=3000,
                ),
            )

            raw_text = response.text or "{}"
            scores_json = self._extract_json(raw_text)

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
            logger.warning("[quality_critic] Dimension scoring failed: %s", e)
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
        user_prompt = "Evaluate this image against all 10 Beast Standards. Score each gate 0-10."

        try:
            client = self._get_gemini_client()
            from google.genai import types

            response = await client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[
                    {"role": "user", "parts": [
                        {"text": user_prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": await self._fetch_image_base64(image_url)}}
                    ]}
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,  # Lower temp for pass/fail decisions
                    max_output_tokens=2000,
                ),
            )

            raw_text = response.text or "{}"
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
            logger.warning("[quality_critic] Beast gates validation failed: %s", e)
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
        routing = {
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
        return routing.get(dimension_name, "layout_planner")

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
        """Extract JSON from Gemini response (handles markdown fences)."""
        import re
        text = text.strip()
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find {...} in text
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        logger.warning("[quality_critic] JSON parse failed, returning empty dict")
        return {}

    def _timestamp(self) -> str:
        """ISO-8601 timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# Singleton
# ══════════════════════════════════════════════════════════════════════════════

quality_critic = QualityCritic()
