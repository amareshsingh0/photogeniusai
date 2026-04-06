"""
BEAST-LEVEL COPY WRITER — Dual-Writer Pattern (Writer A + Writer B)

Writer A: Conceptual thinking, big ideas, 12 headline variants across 6 styles
Writer B: Platform precision, execution speed, character limits

Implements the full SeniorCopywriterAgent.md spec:
- 6 Headline Styles: Provocation, Contrast, Identity Claim, Specific Claim, Cultural Echo, Whisper
- 12 headline generation → cull to 3 finalists → select winner
- Platform-specific character limits enforcement
- Creative Bible alignment
- Psychographic targeting

Philosophy: "Good copy doesn't describe. It provokes."
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 6 Headline Styles (from SeniorCopywriterAgent.md)
# ══════════════════════════════════════════════════════════════════════════════

HEADLINE_STYLES = {
    "provocation": {
        "name": "The Provocation",
        "formula": '[Comfortable belief] is wrong.',
        "description": "Challenge the audience's assumption. Make them argue with you.",
        "examples": [
            "Cheap coffee is expensive.",  # long-term health cost
            "Your skincare routine is doing nothing.",  # bold brand challenger
            "Safety is the most dangerous business strategy.",  # B2B disruption
        ]
    },
    "contrast": {
        "name": "The Contrast",
        "formula": '[Thing A]. [Opposite of Thing A].',
        "description": "Two ideas in tension. The gap between them creates the meaning.",
        "examples": [
            "Less noise. More impact.",
            "Instant. Irreplaceable.",
            "Born local. Built global.",
        ]
    },
    "identity_claim": {
        "name": "The Identity Claim",
        "formula": '[Verb] + [who they become]',
        "description": "Tell the audience who they are (or who they'll become). Identity beats product.",
        "examples": [
            "Dress like you mean it.",
            "Built for the ones who build things.",
            "For the ones who ask why.",
        ]
    },
    "specific_claim": {
        "name": "The Specific Claim",
        "formula": '[Specific number/fact] + [surprising implication]',
        "description": "Specificity is credibility. Vague claims die. Precise claims survive.",
        "examples": [
            "3,000 steps to change your posture. Start at step 1.",
            "₹499. The price of your last bad decision.",
            "47 seconds to checkout. We counted.",
        ]
    },
    "cultural_echo": {
        "name": "The Cultural Echo",
        "formula": '[Familiar cultural reference] — subverted',
        "description": "Reference what the audience already knows and loves. Then twist it.",
        "examples": [
            "Not your mother's savings account.",
            "Ctrl+Z on every bad skincare choice.",
            "Delete the middleman. Not your margins.",
        ]
    },
    "whisper": {
        "name": "The Whisper",
        "formula": 'Simple declarative. Period.',
        "description": "Quiet confidence. No exclamation marks. Just truth.",
        "examples": [
            "The best version of you starts here.",
            "Some things don't need improving.",
            "You know quality when you see it.",
        ]
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Platform Character Limits (from SeniorCopywriterAgent.md)
# ══════════════════════════════════════════════════════════════════════════════

PLATFORM_CHAR_LIMITS = {
    "youtube_thumbnail": {
        "headline": 32,
        "max_words": 6,
        "style_notes": "Shock | Question | Number | 'How' statement. ALL CAPS or nothing. Never mixed."
    },
    "instagram_feed": {
        "headline": 40,  # above fold, before "more"
        "body": 125,  # ideal, max 2200 but nobody reads past 125
        "cta": 20,
        "hashtag_line": 150,
    },
    "instagram_story": {
        "text_per_card": 8,  # max words per card
        "cta": 15,
        "tone": "Conversational. Like talking to a friend, not advertising."
    },
    "tiktok": {
        "caption": 150,  # rest hidden without tap
        "text_overlay": 5,  # max words per beat
        "hook": "First word must be action or question"
    },
    "linkedin": {
        "headline": 50,
        "hook_line": 80,  # before "see more"
        "body": 300,  # scannable, 1-3 lines per paragraph
        "cta": 30,
    },
    "facebook_ad": {
        "primary_text": 125,  # shown before truncation
        "headline": 27,  # shown below image
        "description": 27,  # optional, newsfeed only
        "cta_button": 20,
    },
    "google_display": {
        "headline": 30,  # ×3 headlines, Google combines
        "long_headline": 90,
        "description": 90,  # ×2
    },
    "outdoor_billboard": {
        "max_words": 7,
        "target": 5,
        "rule": "Readable at 70mph while driving. No URLs. No phone numbers. One message."
    },
    "print_magazine": {
        "headline": 80,
        "body": 150,  # 50-150 words, premium reader attention earned
        "cta": 40,  # softer tone
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Platform-Specific CTA Library
# ══════════════════════════════════════════════════════════════════════════════

CTA_LIBRARY = {
    "ecommerce": {
        "high_urgency": ["Shop before midnight", "Only X left", "Sale ends Sunday"],
        "medium_urgency": ["Get yours today", "Add to cart", "Explore the collection"],
        "low_urgency": ["Discover more", "Find your fit", "Start here"],
    },
    "app_saas": {
        "strong": ["Start free", "Try it free", "Get started — it's free"],
        "medium": ["See how it works", "Watch the demo", "Explore features"],
        "soft": ["Learn more", "Find out how", "See the difference"],
    },
    "service": {
        "direct": ["Book a call", "Get a quote", "Schedule free consultation"],
        "softer": ["Let's talk", "Tell us what you need", "We're listening"],
    },
    "content_creator": {
        "engagement": ["Save this for later", "Tag someone who needs this"],
        "growth": ["Follow for more", "Subscribe for weekly X"],
        "community": ["Drop your thoughts below", "Tell me yours 👇"],
    }
}

# ══════════════════════════════════════════════════════════════════════════════
# Copy Writer's Anti-List (Never write these)
# ══════════════════════════════════════════════════════════════════════════════

ANTI_LIST = [
    "Innovative solution",  # everyone says this
    "World-class",  # meaningless without proof
    "We are proud to announce",  # nobody cares about your pride
    "Leading provider of",  # says nothing
    "Quality you can trust",  # trust is earned, not claimed
    "Take your X to the next level",  # vague, overused, forgettable
    "X like never before",  # cliché from 1995
]

# ══════════════════════════════════════════════════════════════════════════════
# Writer A: Conceptual Copy (12 Headlines → 3 Finalists → 1 Winner)
# ══════════════════════════════════════════════════════════════════════════════

class WriterA:
    """
    Writer A — Conceptual Copywriter

    Generates 12 headline options across 6 styles.
    Scores each headline: UNEXPECTED (1-5) + EMOTION HIT (1-5) + BRAND FIT (1-5) + PLATFORM FIT (1-5)
    Minimum 16/20 to advance to finalist round.
    Returns top 3 finalists.
    """

    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _get_gemini_client(self):
        if self.gemini_client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set for Beast Copy Writer")
            self.gemini_client = genai.Client(api_key=api_key)
        return self.gemini_client

    async def generate_headline_variants(
        self,
        triage: Dict,
        brand: Dict,
        creative_bible: Dict,
        psychographic: str,
        emotion_target: str,
        explicit_headline: str = "",
    ) -> List[Dict]:
        """
        Generate 12 headline variants across 6 styles (2 per style).

        Returns list of dicts:
        [{
            "text": "HEADLINE TEXT",
            "style": "provocation",
            "score": {"unexpected": 5, "emotion_hit": 4, "brand_fit": 5, "platform_fit": 4, "total": 18},
            "reasoning": "Why this works..."
        }]
        """
        # If user provided explicit headline, bypass generation
        if explicit_headline:
            return [{
                "text": explicit_headline.upper(),
                "style": "explicit",
                "score": {"unexpected": 5, "emotion_hit": 5, "brand_fit": 5, "platform_fit": 5, "total": 20},
                "reasoning": "User explicitly provided this headline — use EXACTLY as-is."
            }]

        platform = triage.get("platform", "instagram")
        goal = triage.get("goal", "brand_awareness")
        industry = triage.get("industry", "general")
        prompt = triage.get("original_prompt", "")

        # Build knowledge base for Gemini
        styles_kb = "\n\n".join([
            f"**{style_data['name']}**\n"
            f"Formula: {style_data['formula']}\n"
            f"Description: {style_data['description']}\n"
            f"Examples: {', '.join(style_data['examples'][:2])}"
            for style_id, style_data in HEADLINE_STYLES.items()
        ])

        bible_context = ""
        if creative_bible.get("emotional_territory"):
            bible_context = f"""
CREATIVE BIBLE (Locked Contract):
- Emotional Territory: {creative_bible['emotional_territory']}
- Forbidden Elements: {', '.join(creative_bible.get('forbidden_elements', [])[:3])}
"""

        system_prompt = f"""You are Writer A — a conceptual copywriter from Ogilvy, Wieden+Kennedy, Mother London.

TASK: Generate 12 headline variants across 6 headline styles (2 variants per style).

CONTEXT:
- Platform: {platform}
- Goal: {goal}
- Industry: {industry}
- Target Emotion: {emotion_target.upper()}
- Psychographic: {psychographic}
{bible_context}

THE 6 HEADLINE STYLES:
{styles_kb}

ANTI-LIST (NEVER write these):
{', '.join(ANTI_LIST[:5])}

RETURN JSON FORMAT (exactly 12 headlines):
{{
  "headlines": [
    {{"text": "HEADLINE IN ALL CAPS", "style": "provocation", "reasoning": "Why this works in 1 sentence"}},
    {{"text": "SECOND VARIANT", "style": "provocation", "reasoning": "..."}},
    {{"text": "HEADLINE 3", "style": "contrast", "reasoning": "..."}},
    ... (12 total: 2 per style)
  ]
}}

CRITICAL RULES:
1. Each headline MUST evoke {emotion_target.upper()}
2. Align with emotional territory: {creative_bible.get('emotional_territory', 'N/A')}
3. Industry-relevant (not generic)
4. ALL CAPS
5. Platform-appropriate length
6. NO exclamation marks unless earned (rare!)
7. Start with "You" not "We"
"""

        user_prompt = f"Request: {prompt}\n\nGenerate 12 headline variants that PROVOKE, not describe."

        try:
            client = self._get_gemini_client()
            from google.genai import types

            response = await client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.82,  # High temp for creativity
                    max_output_tokens=2500,
                ),
            )

            raw_text = response.text or "{}"
            result_json = self._extract_json(raw_text)

            headlines = result_json.get("headlines", [])
            if not headlines:
                logger.warning("[WriterA] No headlines generated, using fallback")
                return self._fallback_headlines(triage, emotion_target)

            # Score each headline
            scored_headlines = []
            for hl in headlines[:12]:  # Limit to 12
                text = str(hl.get("text", "")).strip().upper()
                style = str(hl.get("style", "whisper"))
                reasoning = str(hl.get("reasoning", ""))

                # Score on 4 dimensions (1-5 each, total 20)
                scores = self._score_headline(text, triage, brand, creative_bible, emotion_target)
                scored_headlines.append({
                    "text": text,
                    "style": style,
                    "score": scores,
                    "reasoning": reasoning,
                })

            return scored_headlines

        except Exception as e:
            logger.exception("[WriterA] Headline generation failed: %s", e)
            return self._fallback_headlines(triage, emotion_target)

    def _score_headline(
        self,
        headline: str,
        triage: Dict,
        brand: Dict,
        creative_bible: Dict,
        emotion_target: str,
    ) -> Dict:
        """
        Score headline on 4 dimensions (1-5 each):
        1. UNEXPECTED: Different from competitors?
        2. EMOTION HIT: Triggers target emotion on first read?
        3. BRAND FIT: Could only THIS brand say this?
        4. PLATFORM FIT: Works for this specific platform/format?

        Minimum combined score to advance: 16/20
        """
        # Simple heuristic scoring (in production, could use Gemini for scoring too)
        scores = {
            "unexpected": 3,  # Default: somewhat unexpected
            "emotion_hit": 3,  # Default: moderate emotion
            "brand_fit": 3,  # Default: generic brand fit
            "platform_fit": 3,  # Default: platform-appropriate
        }

        # UNEXPECTED: Check for anti-list violations (reduce score)
        headline_lower = headline.lower()
        for anti_term in ANTI_LIST:
            if anti_term.lower() in headline_lower:
                scores["unexpected"] = 1  # Cliché detected
                break

        # UNEXPECTED: Short punchy headlines score higher
        if len(headline) < 25:
            scores["unexpected"] += 1

        # EMOTION HIT: Check if emotion keywords present
        emotion_keywords = {
            "urgency": ["now", "today", "limited", "last", "hurry", "quick"],
            "aspiration": ["transform", "elevate", "become", "achieve", "dream"],
            "curiosity": ["discover", "reveal", "secret", "hidden", "unlock"],
            "trust": ["proven", "guaranteed", "safe", "trusted", "reliable"],
        }
        if emotion_target in emotion_keywords:
            for keyword in emotion_keywords[emotion_target]:
                if keyword in headline_lower:
                    scores["emotion_hit"] += 1
                    break

        # BRAND FIT: Check Creative Bible alignment
        if creative_bible.get("emotional_territory"):
            territory_words = creative_bible["emotional_territory"].lower().split()
            for word in territory_words:
                if word in headline_lower and len(word) > 4:
                    scores["brand_fit"] += 1
                    break

        # PLATFORM FIT: Check character limit
        platform = triage.get("platform", "instagram")
        limits = PLATFORM_CHAR_LIMITS.get(platform, {"headline": 40})
        max_chars = limits.get("headline", 40)
        if len(headline) <= max_chars:
            scores["platform_fit"] += 1
        else:
            scores["platform_fit"] = max(1, scores["platform_fit"] - 1)

        # Clamp scores 1-5
        for key in scores:
            scores[key] = max(1, min(5, scores[key]))

        scores["total"] = sum(scores.values())
        return scores

    def select_finalists(self, scored_headlines: List[Dict], top_n: int = 3) -> List[Dict]:
        """
        From 12 scored headlines, select top 3 finalists.
        Minimum combined score to advance: 16/20
        """
        # Filter by minimum score threshold
        qualified = [hl for hl in scored_headlines if hl["score"]["total"] >= 16]

        if not qualified:
            # None met threshold, take top 3 anyway
            qualified = scored_headlines

        # Sort by total score descending
        qualified.sort(key=lambda x: x["score"]["total"], reverse=True)

        finalists = qualified[:top_n]

        logger.info(
            "[WriterA] Selected %d finalists from %d candidates. Top score: %d/20",
            len(finalists), len(scored_headlines),
            finalists[0]["score"]["total"] if finalists else 0
        )

        return finalists

    def _fallback_headlines(self, triage: Dict, emotion_target: str) -> List[Dict]:
        """Fallback headlines if Gemini fails."""
        goal = triage.get("goal", "brand_awareness")
        fallbacks = {
            "sale_promotion": "SAVE BIG TODAY",
            "product_launch": "THE FUTURE IS HERE",
            "brand_awareness": "MAKE IT HAPPEN",
            "event": "JOIN THE MOVEMENT",
            "lead_gen": "GET STARTED FREE",
        }
        headline = fallbacks.get(goal, "MAKE IT HAPPEN")

        return [{
            "text": headline,
            "style": "whisper",
            "score": {"unexpected": 3, "emotion_hit": 3, "brand_fit": 3, "platform_fit": 3, "total": 12},
            "reasoning": "Fallback headline (Gemini generation failed)"
        }]

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
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Writer B: Platform Precision Copy
# ══════════════════════════════════════════════════════════════════════════════

class WriterB:
    """
    Writer B — Platform Specialist

    Takes Writer A's winning headline + generates supporting copy:
    - Subheadline
    - Body copy
    - CTA (platform-specific)
    - Enforces character limits
    """

    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _get_gemini_client(self):
        if self.gemini_client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set for Beast Copy Writer")
            self.gemini_client = genai.Client(api_key=api_key)
        return self.gemini_client

    async def generate_supporting_copy(
        self,
        headline: str,
        triage: Dict,
        brand: Dict,
        creative_bible: Dict,
        psychographic: str,
        explicit_cta: str = "",
        explicit_subheadline: str = "",
    ) -> Dict:
        """
        Generate subheadline, body, CTA to support the winning headline.

        Returns:
        {
            "subheadline": "...",
            "body": "...",
            "cta": "...",
            "tagline": "...",
            "features": [{...}]
        }
        """
        platform = triage.get("platform", "instagram")
        goal = triage.get("goal", "brand_awareness")
        industry = triage.get("industry", "general")
        prompt = triage.get("original_prompt", "")

        # Get platform limits
        limits = PLATFORM_CHAR_LIMITS.get(platform, PLATFORM_CHAR_LIMITS.get("instagram_feed", {}))

        # Determine CTA urgency based on goal
        cta_urgency = "medium_urgency"
        if goal == "sale_promotion":
            cta_urgency = "high_urgency"
        elif goal in ("brand_awareness", "event"):
            cta_urgency = "low_urgency"

        # Get platform-appropriate CTAs
        cta_category = "ecommerce" if goal == "sale_promotion" else "app_saas" if industry in ("saas", "tech") else "service"
        cta_examples = CTA_LIBRARY.get(cta_category, {}).get(cta_urgency, ["Get Started"])

        bible_context = ""
        if creative_bible.get("emotional_territory"):
            bible_context = f"""
CREATIVE BIBLE:
- Emotional Territory: {creative_bible['emotional_territory']}
- Every word must evoke this feeling.
"""

        system_prompt = f"""You are Writer B — platform copy specialist, expert in character limits and platform behavior.

CONTEXT:
- Platform: {platform}
- Headline (already locked): {headline}
- Goal: {goal}
- Industry: {industry}
- Psychographic: {psychographic}
{bible_context}

CHARACTER LIMITS (STRICT):
- Subheadline: {limits.get('subheadline', limits.get('body', 100))} chars max
- Body: {limits.get('body', 160)} chars max
- CTA: {limits.get('cta', 20)} chars max

CTA EXAMPLES (pick or adapt):
{', '.join(cta_examples[:3])}

RETURN JSON:
{{
  "subheadline": "Supports headline, adds specificity or proof",
  "body": "1-2 punchy sentences (optional, can be empty)",
  "cta": "ACTION VERB + BENEFIT",
  "tagline": "Brand tagline if applicable",
  "features": [
    {{"icon": "emoji", "title": "Specific benefit", "desc": "One concrete line"}},
    {{"icon": "emoji", "title": "Specific benefit", "desc": "One concrete line"}},
    {{"icon": "emoji", "title": "Specific benefit", "desc": "One concrete line"}},
    {{"icon": "emoji", "title": "Specific benefit", "desc": "One concrete line"}}
  ]
}}

CRITICAL RULES:
1. Subheadline MUST support headline (provide proof, specificity, or context)
2. Body copy optional (can be "" if headline+sub complete the message)
3. CTA must be ACTION-oriented ("Shop Now", "Start Free", "Get Offer")
4. Features must be REAL, industry-specific benefits (not placeholders!)
5. ALL text must fit character limits
"""

        user_prompt = f"Request: {prompt}\n\nGenerate supporting copy for headline: {headline}"

        try:
            client = self._get_gemini_client()
            from google.genai import types

            response = await client.aio.models.generate_content(
                model=self.gemini_model,
                contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,  # Moderate creativity
                    max_output_tokens=2000,
                ),
            )

            raw_text = response.text or "{}"
            result = self._extract_json(raw_text)

            # Explicit text overrides
            if explicit_subheadline:
                result["subheadline"] = explicit_subheadline
            if explicit_cta:
                result["cta"] = explicit_cta.upper()

            # Validate features (no placeholders)
            features = result.get("features", [])
            if not isinstance(features, list):
                features = []

            features = [
                f for f in features
                if isinstance(f, dict)
                and f.get("title")
                and "Feature" not in f.get("title", "")
                and "benefit" not in f.get("desc", "").lower()[:15]
            ][:4]

            # Pad with fallback features if needed
            while len(features) < 4:
                features.append({
                    "icon": "⭐",
                    "title": f"Benefit {len(features) + 1}",
                    "desc": "Key advantage for you"
                })

            result["features"] = features

            # Enforce character limits
            result = self._enforce_char_limits(result, limits)

            logger.info("[WriterB] Generated supporting copy for headline: %s", headline[:40])
            return result

        except Exception as e:
            logger.exception("[WriterB] Supporting copy generation failed: %s", e)
            return self._fallback_copy(headline, triage, brand)

    def _enforce_char_limits(self, copy_blocks: Dict, limits: Dict) -> Dict:
        """Hard-truncate any fields exceeding platform limits."""
        result = dict(copy_blocks)

        for field in ("subheadline", "body", "cta"):
            text = str(result.get(field, "")).strip()
            limit = limits.get(field, 200)
            if len(text) > limit:
                # Truncate at word boundary
                result[field] = text[:limit].rsplit(" ", 1)[0]
                logger.warning("[WriterB] Truncated %s: %d → %d chars", field, len(text), len(result[field]))

        return result

    def _fallback_copy(self, headline: str, triage: Dict, brand: Dict) -> Dict:
        """Fallback copy if Gemini fails."""
        goal = triage.get("goal", "brand_awareness")
        ctas = {
            "sale_promotion": "SHOP NOW",
            "product_launch": "LEARN MORE",
            "brand_awareness": "DISCOVER",
            "event": "JOIN US",
            "lead_gen": "GET STARTED",
        }

        return {
            "subheadline": "The future of excellence",
            "body": "Experience the difference today.",
            "cta": ctas.get(goal, "LEARN MORE"),
            "tagline": brand.get("tagline", ""),
            "features": [
                {"icon": "✓", "title": "Quality", "desc": "Premium excellence"},
                {"icon": "⚡", "title": "Speed", "desc": "Fast delivery"},
                {"icon": "🎯", "title": "Precision", "desc": "Exact results"},
                {"icon": "🚀", "title": "Innovation", "desc": "Cutting edge"},
            ]
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
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Beast Copy Writer Orchestrator (Writer A + Writer B)
# ══════════════════════════════════════════════════════════════════════════════

class BeastCopyWriter:
    """
    Orchestrates Writer A (conceptual) + Writer B (platform precision).

    Flow:
    1. Writer A generates 12 headline variants → selects top 3 finalists
    2. User/System picks winner (or Writer A auto-picks #1)
    3. Writer B generates supporting copy for winner
    4. Return complete copy package
    """

    def __init__(self):
        self.writer_a = WriterA()
        self.writer_b = WriterB()

    async def generate_beast_copy(
        self,
        triage: Dict,
        brand: Dict,
        creative_bible: Dict,
        explicit_headline: str = "",
        explicit_subheadline: str = "",
        explicit_cta: str = "",
    ) -> Dict:
        """
        Generate Beast-level copy (dual-writer pattern).

        Returns:
        {
            "headline": "WINNING HEADLINE",
            "headline_finalists": [3 finalist dicts],
            "subheadline": "...",
            "body": "...",
            "cta": "...",
            "tagline": "...",
            "features": [{...}],
            "copy_metadata": {
                "writer_a_variants": 12,
                "finalists_count": 3,
                "winner_score": 18,
                "winner_style": "provocation"
            }
        }
        """
        # Audience intelligence
        psychographic = triage.get("audience_intelligence", {}).get("psychographic", "general")
        emotion_target = triage.get("emotion_target", "aspiration")

        # ── PHASE 1: Writer A — Generate headline variants ───────────────────────
        logger.info("[BeastCopyWriter] Phase 1: Writer A generating 12 headline variants")

        variants = await self.writer_a.generate_headline_variants(
            triage=triage,
            brand=brand,
            creative_bible=creative_bible,
            psychographic=psychographic,
            emotion_target=emotion_target,
            explicit_headline=explicit_headline,
        )

        # ── PHASE 2: Select top 3 finalists ──────────────────────────────────────
        finalists = self.writer_a.select_finalists(variants, top_n=3)

        # Pick winner (top scorer)
        winner = finalists[0] if finalists else variants[0]
        winning_headline = winner["text"]

        logger.info(
            "[BeastCopyWriter] Winner: '%s' (style=%s, score=%d/20)",
            winning_headline[:50], winner["style"], winner["score"]["total"]
        )

        # ── PHASE 3: Writer B — Generate supporting copy ─────────────────────────
        logger.info("[BeastCopyWriter] Phase 2: Writer B generating supporting copy")

        supporting_copy = await self.writer_b.generate_supporting_copy(
            headline=winning_headline,
            triage=triage,
            brand=brand,
            creative_bible=creative_bible,
            psychographic=psychographic,
            explicit_cta=explicit_cta,
            explicit_subheadline=explicit_subheadline,
        )

        # ── PHASE 4: Assemble final copy package ─────────────────────────────────
        copy_package = {
            "brand_name": brand.get("brand_name", ""),
            "headline": winning_headline,
            "headline_finalists": finalists,  # For UI variant picker (future)
            "subheadline": supporting_copy.get("subheadline", ""),
            "body": supporting_copy.get("body", ""),
            "cta": supporting_copy.get("cta", "GET STARTED"),
            "cta_url": "",
            "tagline": supporting_copy.get("tagline", brand.get("tagline", "")),
            "features": supporting_copy.get("features", []),
            "copy_metadata": {
                "writer_a_variants": len(variants),
                "finalists_count": len(finalists),
                "winner_score": winner["score"]["total"],
                "winner_style": winner["style"],
                "winner_reasoning": winner.get("reasoning", ""),
                "timestamp": self._timestamp(),
            }
        }

        logger.info("[BeastCopyWriter] Complete. Final headline: %s", winning_headline[:60])
        return copy_package

    def _timestamp(self) -> str:
        """ISO-8601 timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

async def generate_beast_copy(
    triage: Dict,
    brand: Dict,
    creative_bible: Dict,
    explicit_headline: str = "",
    explicit_subheadline: str = "",
    explicit_cta: str = "",
) -> Dict:
    """
    Public API for Beast-level copywriting.

    Usage:
    ```python
    copy_package = await generate_beast_copy(
        triage=triage_output,
        brand=brand_intel_output,
        creative_bible=creative_director_output,
        explicit_headline="70% OFF",  # Optional: user-provided headline
    )

    print(copy_package["headline"])  # "70% OFF"
    print(copy_package["headline_finalists"])  # Top 3 variants
    print(copy_package["copy_metadata"])  # Metadata about selection
    ```
    """
    beast = BeastCopyWriter()
    return await beast.generate_beast_copy(
        triage=triage,
        brand=brand,
        creative_bible=creative_bible,
        explicit_headline=explicit_headline,
        explicit_subheadline=explicit_subheadline,
        explicit_cta=explicit_cta,
    )
