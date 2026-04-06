"""
MOTION DESIGNER — The Time Architect

Designs in the dimension nobody accounts for: TIME.
A static image exists in a moment. Motion exists in a story.

Even static assets must IMPLY motion — the frozen moment that suggests
what was before and what comes next.

Phase: Sprint 4 (Animation Brief Generation)
Currently: Generates motion briefs for future video/animation export
Future: Will power Lottie JSON generation, After Effects integration

Philosophy:
- Motion Serves Meaning (every movement has purpose)
- Timing Is Personality (fast=tech, slow=luxury)
- Easing Is Emotion (spring=playful, ease-out=settled)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Literal

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Motion Principles & Constants
# ══════════════════════════════════════════════════════════════════════════════

MOTION_MEANINGS = {
    "fade_in": "arrival, birth, emergence",
    "scale_up": "growth, importance, approach",
    "slide_left": "past, history, progress",
    "slide_right": "future, new, next",
    "rotate": "transformation, change, time",
    "shake": "urgency, alert, discomfort",
    "drift": "organic, slow time, calm",
    "snap": "precision, confidence, decisiveness",
}

TIMING_PERSONALITY = {
    "fast": {"range_ms": (100, 200), "vibe": "Precision, technology, responsiveness"},
    "medium": {"range_ms": (300, 500), "vibe": "Friendly, confident, settled"},
    "slow": {"range_ms": (600, 1000), "vibe": "Premium, considered, luxury"},
    "very_slow": {"range_ms": (1000, 2000), "vibe": "Cinematic, dramatic, reverent"},
}

EASING_EMOTION = {
    "linear": "Mechanical, robotic — almost never use",
    "ease_in": "Building energy — something is starting",
    "ease_out": "Settling, landing — something is arriving",
    "ease_in_out": "Natural, conversational — most human motion",
    "spring": "Playful, energetic, young brand",
    "elastic": "Quirky, unexpected, attention-grabbing",
}

PLATFORM_MOTION_RULES = {
    "tiktok": {
        "hook_window_ms": 800,
        "loop_design": "seamless",
        "text_timing": "text appears before spoken OR in beat with music",
        "physics": "snap cuts, not dissolves",
    },
    "instagram_reel": {
        "opener": "editorial, can breathe slightly longer",
        "visual_quality": "polished",
        "aspect_ratio": "9:16 vertical",
        "save_worthy": "design for saves",
        "trending_audio": "beat-sync dramatically outperforms",
    },
    "youtube_preroll": {
        "skip_threshold_s": 5,
        "sound_off_assumption": "design for silence first",
        "brand_reveal_timing_s": (3, 4),
        "bumper_6s": "hook AND message coexist",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# Motion Designer Class
# ══════════════════════════════════════════════════════════════════════════════

class MotionDesigner:
    """
    Generates animation briefs for static and animated assets.

    Two modes:
    1. MD-A (Narrative Motion): Full animation briefs for reels/stories/video
    2. MD-B (Micro-Interaction): Platform-native motion hints for static assets

    Output: JSON motion brief that future video/animation system will execute
    """

    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _get_gemini_client(self):
        if self.gemini_client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set for Motion Designer")
            self.gemini_client = genai.Client(api_key=api_key)
        return self.gemini_client

    # ══════════════════════════════════════════════════════════════════════════
    # MD-A: Narrative Motion (Full Animation Briefs)
    # ══════════════════════════════════════════════════════════════════════════

    async def generate_animation_brief(
        self,
        triage: Dict,
        creative_bible: Dict,
        copy: Dict,
        layout: Dict,
        duration_seconds: int = 6,
        loop: bool = True,
    ) -> Dict:
        """
        Generate full animation brief for video/reel/story.

        Args:
            triage: Triage output (platform, goal, etc.)
            creative_bible: Creative Director output
            copy: Copy Writer output
            layout: Layout Planner output
            duration_seconds: Total animation duration
            loop: Whether animation should loop seamlessly

        Returns:
        {
            "motion_brief": {
                "asset_type": "reel",
                "duration_seconds": 6,
                "loop": true,
                "platform": "instagram_reel",
                "act_1": {...},  # Hook (0-0.3s)
                "act_2": {...},  # Story (0.3-5.5s)
                "act_3": {...},  # Close (5.5-6.0s)
                "loop_design": {...},
                "sound_design_note": "..."
            }
        }
        """
        platform = triage.get("platform", "instagram")
        goal = triage.get("goal", "brand_awareness")
        emotion_target = triage.get("emotion_target", "aspiration")

        # Determine asset type from platform
        asset_type = self._infer_asset_type(platform)

        # Get platform-specific motion rules
        platform_rules = PLATFORM_MOTION_RULES.get(
            "tiktok" if "tiktok" in platform.lower() else
            "instagram_reel" if "reel" in platform.lower() or "story" in platform.lower() else
            "youtube_preroll"
        )

        # Build motion brief via Gemini
        system_prompt = self._build_animation_system_prompt(
            platform, asset_type, duration_seconds, platform_rules, creative_bible
        )

        user_prompt = f"""
Platform: {platform}
Asset Type: {asset_type}
Duration: {duration_seconds}s
Loop: {loop}

Creative Bible:
- Emotional Territory: {creative_bible.get('emotional_territory', 'N/A')}
- Visual Metaphors: {', '.join(creative_bible.get('visual_metaphors', [])[:2])}

Copy:
- Headline: {copy.get('headline', '')}
- Subheadline: {copy.get('subheadline', '')}
- CTA: {copy.get('cta', '')}

Generate a 3-act animation brief (Hook → Story → Close).
"""

        try:
            client = self._get_gemini_client()
            from google.genai import types

            response = await client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=2000,
                ),
            )

            raw_text = response.text or "{}"
            motion_brief = self._extract_json(raw_text)

            # Add fallback structure if Gemini fails
            if not motion_brief or "_parse_error" in motion_brief:
                motion_brief = self._fallback_animation_brief(
                    platform, asset_type, duration_seconds, loop, copy
                )

            logger.info(
                "[MotionDesigner] Generated animation brief: %s, %ds, loop=%s",
                asset_type, duration_seconds, loop
            )

            return {"motion_brief": motion_brief}

        except Exception as e:
            logger.exception("[MotionDesigner] Animation brief generation failed: %s", e)
            return {
                "motion_brief": self._fallback_animation_brief(
                    platform, asset_type, duration_seconds, loop, copy
                )
            }

    # ══════════════════════════════════════════════════════════════════════════
    # MD-B: Motion for Static Assets (Implied Movement)
    # ══════════════════════════════════════════════════════════════════════════

    async def generate_static_motion_hints(
        self,
        triage: Dict,
        creative_bible: Dict,
        layout: Dict,
    ) -> Dict:
        """
        Generate motion implication notes for static images.

        Even static posters should IMPLY motion — frozen-in-action moments
        that suggest what was before and what comes next.

        Returns:
        {
            "motion_hints": {
                "primary_technique": "diagonal_composition_motion_blur",
                "motion_direction": "forward_right",
                "implied_speed": "fast",
                "freeze_frame_moment": "peak_action",
                "prompt_notes": [
                    "slight motion blur on subject edges, rest sharp",
                    "subject angled toward right, suggesting forward movement",
                    "hair/fabric mid-movement, caught in wind"
                ],
                "micro_interactions": {
                    "hover_cta": "scale 1.0 → 1.05, ease-out 150ms",
                    "entry_headline": "fade + slide up 20px, ease-out 400ms"
                }
            }
        }
        """
        platform = triage.get("platform", "instagram")
        emotion_target = triage.get("emotion_target", "aspiration")
        goal = triage.get("goal", "brand_awareness")

        # Determine motion implication technique based on context
        technique = self._select_motion_technique(emotion_target, goal, platform)

        # Build motion hints
        motion_hints = {
            "primary_technique": technique["id"],
            "motion_direction": technique["direction"],
            "implied_speed": technique["speed"],
            "freeze_frame_moment": technique["moment"],
            "prompt_notes": technique["prompt_notes"],
            "micro_interactions": self._generate_micro_interactions(platform, layout),
        }

        logger.info(
            "[MotionDesigner] Generated static motion hints: technique=%s",
            technique["id"]
        )

        return {"motion_hints": motion_hints}

    # ══════════════════════════════════════════════════════════════════════════
    # Internal Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _infer_asset_type(self, platform: str) -> str:
        """Infer animation asset type from platform."""
        platform_lower = platform.lower()
        if "story" in platform_lower or "reel" in platform_lower:
            return "reel"
        elif "youtube" in platform_lower:
            return "pre-roll"
        elif "tiktok" in platform_lower:
            return "reel"
        else:
            return "display-rich"

    def _build_animation_system_prompt(
        self,
        platform: str,
        asset_type: str,
        duration_s: int,
        platform_rules: Dict,
        creative_bible: Dict,
    ) -> str:
        """Build system prompt for animation brief generation."""
        return f"""You are MD-A — Senior Motion Designer from Google Material Design, GSAP campaigns, After Effects.

TASK: Generate a 3-act animation brief for {asset_type} on {platform}.

MOTION PHILOSOPHY:
- Motion Serves Meaning (every movement has purpose)
- Timing Is Personality (fast=tech, slow=luxury)
- Easing Is Emotion (spring=playful, ease-out=settled)

PLATFORM RULES ({platform}):
{json.dumps(platform_rules, indent=2)}

3-ACT STRUCTURE:
ACT 1 (0.0s - 0.3s): THE HOOK
  - What stops the thumb? First frame creates a question.
  - Motion: Quick reveal, unexpected entry, or counter-intuitive start

ACT 2 (0.3s - {duration_s - 0.5}s): THE STORY
  - Core message delivered through motion
  - Motion: Main animation that communicates the concept

ACT 3 (last 0.5s): THE CLOSE
  - CTA or brand moment
  - Motion: Confident landing, clean hold, or elegant loop point

RETURN JSON FORMAT:
{{
  "asset_type": "{asset_type}",
  "duration_seconds": {duration_s},
  "platform": "{platform}",
  "act_1": {{
    "duration_ms": 300,
    "visual": "What appears first and how",
    "animation": "Specific movement with timing and easing",
    "purpose": "Create this specific question/curiosity"
  }},
  "act_2": {{
    "duration_ms": {(duration_s - 0.8) * 1000},
    "sequence": [
      {{
        "timestamp_ms": 300,
        "element": "headline",
        "animation": "transform: scale(1.0) to scale(1.4), ease-out, 400ms",
        "purpose": "Amplify headline impact"
      }}
    ]
  }},
  "act_3": {{
    "duration_ms": 500,
    "visual": "Final frame or loop point",
    "animation": "Landing motion",
    "cta_treatment": "How CTA enters and holds"
  }},
  "loop_design": {{
    "loop_point": "timestamp_ms where loop connects back",
    "seamless": true,
    "loop_emotion": "What the loop feel creates"
  }},
  "sound_design_note": "Rhythm suggestion if applicable"
}}
"""

    def _fallback_animation_brief(
        self,
        platform: str,
        asset_type: str,
        duration_s: int,
        loop: bool,
        copy: Dict,
    ) -> Dict:
        """Fallback animation brief if Gemini fails."""
        return {
            "asset_type": asset_type,
            "duration_seconds": duration_s,
            "loop": loop,
            "platform": platform,

            "act_1": {
                "duration_ms": 300,
                "visual": "Hero image fades in with scale 0.97 → 1.0",
                "animation": "Fade in + subtle scale, ease-out, 300ms",
                "purpose": "Establish presence without shock"
            },

            "act_2": {
                "duration_ms": (duration_s - 0.8) * 1000,
                "sequence": [
                    {
                        "timestamp_ms": 300,
                        "element": "headline",
                        "animation": "Slide up 20px + fade in, ease-out, 400ms",
                        "purpose": "Draw eye to headline"
                    },
                    {
                        "timestamp_ms": 800,
                        "element": "subheadline",
                        "animation": "Fade in, ease-out, 300ms",
                        "purpose": "Support headline message"
                    }
                ]
            },

            "act_3": {
                "duration_ms": 500,
                "visual": "CTA button appears with pulse glow",
                "animation": "Slide up 15px + fade in, ease-out, 300ms",
                "cta_treatment": "Pulse glow effect to draw attention"
            },

            "loop_design": {
                "loop_point": duration_s * 1000,
                "seamless": loop,
                "loop_emotion": "Confident, settled, no jarring restart"
            },

            "sound_design_note": "Subtle whoosh on headline entry, soft click on CTA"
        }

    def _select_motion_technique(
        self,
        emotion_target: str,
        goal: str,
        platform: str,
    ) -> Dict:
        """Select motion implication technique for static assets."""
        # Map emotion → motion technique
        if emotion_target == "urgency":
            return {
                "id": "diagonal_motion_blur",
                "direction": "forward_right",
                "speed": "fast",
                "moment": "peak_action",
                "prompt_notes": [
                    "slight motion blur on product edges, rest sharp",
                    "product angled toward right, suggesting forward movement",
                    "dynamic composition with implied velocity"
                ]
            }
        elif emotion_target == "aspiration":
            return {
                "id": "freeze_frame_elegance",
                "direction": "upward",
                "speed": "medium",
                "moment": "pre-action_stance",
                "prompt_notes": [
                    "subject in pre-action stance, coiled energy",
                    "fabric/hair mid-movement, caught in gentle wind",
                    "frozen-in-action, millisecond-capture photography"
                ]
            }
        elif emotion_target == "curiosity":
            return {
                "id": "implied_trajectory",
                "direction": "toward_viewer",
                "speed": "medium",
                "moment": "approach",
                "prompt_notes": [
                    "subject angled toward camera, approaching",
                    "shallow depth of field with bokeh suggesting distance",
                    "anticipation pose, about to reveal something"
                ]
            }
        else:
            # Default: subtle_motion
            return {
                "id": "wind_motion",
                "direction": "natural",
                "speed": "slow",
                "moment": "gentle_movement",
                "prompt_notes": [
                    "hair/fabric mid-movement, natural physics",
                    "soft motion blur on lightweight elements",
                    "frozen moment that suggests calm motion"
                ]
            }

    def _generate_micro_interactions(
        self,
        platform: str,
        layout: Dict,
    ) -> Dict:
        """Generate micro-interaction specs for digital assets."""
        return {
            "hover_cta": "scale 1.0 → 1.05, ease-out 150ms, subtle color shift",
            "hover_image": "scale 1.0 → 1.02, ease-out 200ms",
            "entry_hero": "fade + scale 0.97 → 1.0, ease-out 600ms",
            "entry_headline": "slide up 20px + fade in, stagger words 50ms, ease-out 400ms",
            "entry_cta": "slide up 15px + fade in, ease-out 300ms, delay 800ms",
            "scroll_trigger": "fade in at 80% viewport intersection",
        }

    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from Gemini response."""
        import re
        text = text.strip()
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return {"_parse_error": True}


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

async def generate_motion_brief(
    triage: Dict,
    creative_bible: Dict,
    copy: Dict,
    layout: Dict,
    duration_seconds: int = 6,
    loop: bool = True,
) -> Dict:
    """
    Public API for motion brief generation.

    Usage:
    ```python
    motion_brief = await generate_motion_brief(
        triage=triage_output,
        creative_bible=creative_director_output,
        copy=copy_writer_output,
        layout=layout_planner_output,
        duration_seconds=6,
        loop=True,
    )

    print(motion_brief["motion_brief"]["act_1"])
    print(motion_brief["motion_brief"]["loop_design"])
    ```
    """
    designer = MotionDesigner()
    return await designer.generate_animation_brief(
        triage, creative_bible, copy, layout, duration_seconds, loop
    )


async def generate_static_motion_hints(
    triage: Dict,
    creative_bible: Dict,
    layout: Dict,
) -> Dict:
    """
    Public API for static motion hints generation.

    Usage:
    ```python
    motion_hints = await generate_static_motion_hints(
        triage=triage_output,
        creative_bible=creative_director_output,
        layout=layout_planner_output,
    )

    print(motion_hints["motion_hints"]["prompt_notes"])
    print(motion_hints["motion_hints"]["micro_interactions"])
    ```
    """
    designer = MotionDesigner()
    return await designer.generate_static_motion_hints(triage, creative_bible, layout)


# Singleton
motion_designer = MotionDesigner()
