"""
Simple Prompt Engine — One-shot Haiku 4.5 prompt enrichment.

Replaces the multi-stage agent chain (Master Strategist + Copy Writer + Image
Prompter + Layout Planner + Claude Stage A/B/Validator) with a single Claude
Haiku 4.5 call that:

  1. Detects what the user is asking for (ad / poster / hoarding / wishes /
     product shot / portrait / etc).
  2. Expands a short prompt into a richly detailed image-generation prompt
     with subject, scene, lighting, composition, mood, style, palette, and
     copy text where relevant.
  3. Re-details / cleans up long, messy prompts so the model receives a
     well-structured instruction.

Output is consumed directly by the model — no Stage B params engine, no
agent chain, no validator. The enriched prompt IS the final prompt.

Usage:
    from app.services.smart.simple_prompt_engine import simple_engine
    result = await simple_engine.enrich(
        user_prompt="birthday wishes for my sister",
        bucket="typography",
        tier="2k",
    )
    # result = {
    #     "prompt": "...rich detailed prompt...",
    #     "negative_prompt": "...",
    #     "intent": "birthday_card",
    #     "aspect_hint": "portrait_4_3",
    #     "ad_copy": {"headline": "...", "subhead": "..."} or None,
    # }

Toggle with feature flag USE_SIMPLE_ENGINE=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = os.getenv("SIMPLE_ENGINE_MODEL", "claude-haiku-4-5-20251001")
_MAX_TOKENS   = int(os.getenv("SIMPLE_ENGINE_MAX_TOKENS", "2200"))
_TEMPERATURE  = float(os.getenv("SIMPLE_ENGINE_TEMPERATURE", "0.7"))
_USE_CACHING  = os.getenv("USE_PROMPT_CACHING", "true").lower() != "false"
# Instructor auto-retries up to N times when Haiku violates the schema
# (each retry appends the validation error to the conversation, so the model
# self-corrects). 2 retries = 3 total attempts which is plenty.
_INSTRUCTOR_MAX_RETRIES = int(os.getenv("SIMPLE_ENGINE_MAX_RETRIES", "2"))


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic schema — Haiku output shape (Priority 1: structured output validation)
# ─────────────────────────────────────────────────────────────────────────────
# Replaces the old loose-JSON parsing. Instructor wraps the Anthropic client
# with tool-calling-based schema enforcement. If Haiku returns malformed JSON,
# missing fields, or wrong types, Instructor auto-retries with the validation
# error injected into the conversation — Haiku self-corrects within max_retries.
#
# This eliminates the entire "Haiku silently dropped ad_copy / returned bad
# JSON" failure category. Typography generations with missing headlines: gone.

# Aspect hints supported by generate_stream's _ASPECT_DIMS map.
AspectHint = Literal[
    "square_hd",
    "portrait_4_3",
    "landscape_4_3",
    "portrait_9_16",
    "landscape_16_9",
]


class AdCopy(BaseModel):
    """On-image text rendered by the model. Empty strings when not relevant."""

    # Core fields — backward-compatible with existing generate_stream.py consumers
    headline: str = Field(default="", max_length=200,
        description="Primary attention hook — the main large text on the image.")
    subhead:  str = Field(default="", max_length=400,
        description="Secondary line adding context below the headline.")
    cta:      str = Field(default="", max_length=120,
        description="Call-to-action (Shop Now / Register / Learn More). Empty for non-ad content.")

    # Extended fields — Art Director Brain additions
    benefit_lines: list[str] = Field(default_factory=list,
        description="0–5 feature labels for icon badge rendering. MUST be 2–3 words each (e.g. 'Lightweight Feel', 'Oil Control', 'Long-Lasting Wear', 'Blurs Imperfections'). These render as circular icon badges in the layout — do NOT write full sentences here. Empty for minimal posters.")
    trust_signals: list[str] = Field(default_factory=list,
        description="0–3 credibility lines (e.g. '10,000+ customers', 'Dermatologist tested'). Empty if not applicable.")
    emotional_tagline: Optional[str] = Field(default=None, max_length=200,
        description="Aspirational closing line — the feeling the viewer should carry away.")
    brand_name: Optional[str] = Field(default=None, max_length=100,
        description="Exact brand name to render in the image, if provided by the user.")


class VisualDirection(BaseModel):
    """Art director's visual brief — mood, palette, light, layout."""

    mood:             str = Field(default="", description="Emotional register: celebratory, intimate, punchy, serene, aspirational, gritty, dreamy, bold.")
    color_palette:    str = Field(default="", description="Primary + secondary + accent colors. Use craft vocabulary: 'warm cream 60%, deep olive 30%, brushed brass 10%'.")
    lighting:         str = Field(default="", description="Light direction, quality, temperature: 'golden-hour backlight rim-lighting', 'overhead softbox with bounce'.")
    background:       str = Field(default="", description="Background environment or backdrop description.")
    composition:      str = Field(default="", description="Layout zones: where the hero sits, where text locks, negative space placement.")
    typography_style: str = Field(default="", description="Font style guidance: 'bold condensed sans', 'elegant hand-lettered script', 'vintage slab serif'.")


class SimpleEngineOutput(BaseModel):
    """Strict schema for Haiku's output. Enforced via Instructor + Pydantic."""

    intent: str = Field(
        default="general",
        max_length=80,
        description=(
            "Short label classifying the image — e.g. birthday_wishes, "
            "diwali_wishes, product_ad, social_post, hoarding, poster, "
            "portrait, scene, logo, sale_ad, event_poster, movie_poster, "
            "food_ad, real_estate_ad, sale_ad, educational_ad."
        ),
    )
    prompt: str = Field(
        ...,
        min_length=20,
        max_length=4000,
        description=(
            "One flowing image-generation prompt, 80-200 words for typography, "
            "60-140 for photoreal. NO Option/Version labels, NO bracketed "
            "placeholders. For typography bucket, layout markers like "
            "'Headline:' may appear only inside quoted text strings."
        ),
    )
    negative_prompt: str = Field(
        default="",
        max_length=1000,
        description="Comma-separated negatives tailored to the image.",
    )
    aspect_hint: AspectHint = Field(
        default="square_hd",
        description="Best aspect for this image. Inferred from intent and platform.",
    )

    # Art Director Brain — campaign intelligence fields
    campaign_type: str = Field(
        default="general",
        description=(
            "Type of campaign: product_launch | sale | event | awareness | "
            "seasonal | announcement | wishes | general"
        ),
    )
    subject_category: str = Field(
        default="general",
        description=(
            "Industry/subject category: beauty | food | tech | fashion | "
            "event | education | health | real_estate | entertainment | general"
        ),
    )
    platform: str = Field(
        default="general",
        description=(
            "Target platform: instagram_feed | story | youtube_thumbnail | "
            "print_poster | hoarding | general"
        ),
    )
    copywriting_formula: str = Field(
        default="simple",
        description=(
            "Copywriting structure used: AIDA (product launch/ads) | "
            "PAS (problem-solution) | BAB (before-after) | simple (wishes/events/minimal)"
        ),
    )

    # Structured copy and visual brief
    ad_copy: Optional[AdCopy] = Field(
        default=None,
        description=(
            "Populated when the image has on-image text (ads, posters, "
            "wishes, hoardings, events). Null for pure scenes/portraits without text."
        ),
    )
    visual: Optional[VisualDirection] = Field(
        default=None,
        description=(
            "Art director's visual brief. Populate for typography/poster/ad buckets. "
            "Null for simple photoreal or portrait requests."
        ),
    )

# ─────────────────────────────────────────────────────────────────────────────
# Static system prompt — placed BEFORE dynamic user input so it can be cached.
# Keep wording stable across calls; the cache key is the exact text.
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a world-class creative director AND art director. You've led campaigns for Apple, Nike, Coca-Cola, Airbnb. Your Behance is on the front page. When someone sends you four rushed words, you don't repeat those words back — you SEE the finished image in your head, and you describe it.

# 5-LAYER ART DIRECTOR PROCESS — RUN THIS FOR EVERY REQUEST

Before writing a single word, run all 5 layers silently in your head:

## LAYER 1 — STRATEGIC: What is this?
Identify the content type precisely. It matters because each type has different rules:
- **Product launch** → AIDA formula, hero product, strong benefit headline, CTA
- **Sale/offer ad** → Giant number (% OFF), urgency word (ENDS SUNDAY), high-energy palette
- **Event poster** (concert, festival, conference, wedding) → Date + Venue + Title treatment, information hierarchy
- **Social media post** (awareness, engagement) → One scroll-stopping visual + minimal copy
- **Birthday/wishes card** → Warm specific message, culturally appropriate motifs, high-low typography
- **Restaurant/food** → Hero food shot, atmosphere, occasion copy
- **Movie/show announcement** → Title treatment, tagline, cast/date, dramatic visual
- **Real estate** → Property visual, location, price anchor, trust signals
- **Educational institute** → Course/program benefit, credibility, enrollment CTA
- **NGO/cause** → Emotional hook, impact number, donation CTA
- **General poster** → Identify closest type from above and apply its rules

Set `campaign_type`, `subject_category`, `platform` in your output based on this analysis.

## LAYER 2 — COPYWRITING: Which formula?
Apply the right structure to the on-image copy:

**AIDA** (for product ads, launches, services):
- **A**ttention → Hero headline that stops the scroll (≤8 words, emotional benefit)
- **I**nterest → Subhead that adds proof or context (≤14 words)
- **D**esire → 1–2 benefit lines (feature → feeling)
- **A**ction → CTA verb ("Shop Now", "Register Today", "Claim Offer")

**PAS** (for problem-solution ads):
- **P**roblem → Headline names the pain ("Tired of dull skin?")
- **A**gitate → Subhead makes it vivid ("You've tried everything…")
- **S**olve → CTA presents the solution ("Discover [Product]")

**BAB** (for before-after transformations):
- **B**efore → Show the old state
- **A**fter → Show the new state
- **B**ridge → Product/service is the bridge

**SIMPLE** (for event posters, wishes, minimal):
- Just a great headline + optional subline. No funnel structure needed.
- "Sunday Sessions" + "Brunch + Live Acoustic" is perfect for a café poster.

Set `copywriting_formula` = AIDA | PAS | BAB | simple.

**HERO HEADLINE RULE — ALL PRODUCT/COMMERCIAL ADS:**
The `ad_copy.headline` for any product ad, launch, or commercial poster MUST be 2–4 words MAXIMUM. Non-negotiable. More words = weaker punch. Think Nike-level:
-  GOOD: "LIGHT AS AIR." · "SKIN PERFECTED." · "GLOW UNLOCKED." · "BLUR THE LINE." · "BARE FLAWLESS." · "SILENCE, ENGINEERED."
-  BAD: "Glow Redefined Every Day" (5 words) · "Experience Beautiful Radiant Skin Now" (6 words, forgettable)
If you write more than 4 words in the hero headline, rewrite it until it's 4 or fewer.
The `ad_copy.subhead` can be 5–12 words — that's where context goes.

**BENEFIT LINES RULE — ICON BADGE FORMAT:**
`ad_copy.benefit_lines` entries will be rendered as CIRCULAR ICON BADGES in the final image — each must be 2–3 words maximum (like "Lightweight Feel" · "Oil Control" · "Long Lasting Wear" · "Blurs Imperfections"). NEVER write full sentences in benefit_lines. Think: what would fit on a tiny label under a circular icon?

## LAYER 3 — VISUAL DIRECTION: How does it look?
Fill the `visual` field:
- **mood**: one emotional register (celebratory, intimate, punchy, aspirational, gritty, dreamy)
- **color_palette**: dominant (60%) + secondary (30%) + accent (10%) — craft vocabulary
- **lighting**: direction + quality + temperature (golden-hour rim light, overhead softbox, candle-lit)
- **background**: what sits behind the hero
- **composition**: where hero sits, where text locks, negative space
- **typography_style**: bold condensed sans | elegant script | vintage slab | modern clean sans

## LAYER 4 — TYPOGRAPHY: Exact text in quotes
All on-image text goes in `ad_copy`. In the prompt, quote every text string exactly:
- `the headline "Silence, Engineered." locked across the top third`
- `a CTA pill reading "Pre-order Now" in electric blue`
- NEVER leave empty quotes `""` — every quoted block must contain real copy

For PRODUCT LAUNCH ads, the prompt must describe ALL of these layout elements:
- Brand logo (top-left), "NEW LAUNCH" badge above the headline
- Hero headline large (bold, uppercase sans), subheadline in elegant italic/script
- 3–5 feature icon badges arranged horizontally in a row (circular, line-art icons)
- CTA text in script style, emotional tagline in small elegant type
- Bottom trust strip (full-width, cream band, 4 pipe-separated items)

## LAYER 5 — TECHNICAL: Build the image_prompt
Construct the `prompt` field using construction order (back to front):
1. Background plate (environment, sky, backdrop, palette)
2. Hero subject (the ONE thing the eye lands on — product, face, visual motif)
3. Supporting props (2–3 authenticity details that make the scene real)
4. Text layer (lockup positions, hierarchy, style — use EXACT quoted copy for EVERY text element)
5. Polish pass (grain, lens, DoF, atmosphere, color grade)

For product ads: the text layer MUST name every element by position — brand logo top-left, headline middle-left, icon badges row below headline, CTA and tagline lower-left, trust strip at bottom. Don't let any text element be vague — name it, position it, quote it.

# HOW YOU THINK (THE SKILL, NOT THE RULES)

Before you write a single word of the final prompt, you have a silent 10-second conversation with yourself. Something like:

> "Okay, 'birthday wishes for my sister.' What am I really looking at?
> — Not a generic card. A SISTER. That's warm, nostalgic, slightly playful, not corporate. Probably 20s–30s woman, close bond.
> — Where would she see this? Instagram story or WhatsApp status. So portrait 9:16 is smart. Mobile-first.
> — What's the ONE image that makes her smile? Soft bokeh fairy lights, a delicate florals, pastel palette — rose-gold, blush pink, cream. NOT generic balloons-and-confetti stock look.
> — The message shouldn't be 'Happy Birthday'. It should be something SHE would say to her sister. Maybe: 'To my forever partner-in-crime — happy birthday.' That has story.
> — Typography: elegant hand-lettered script for the main line, small clean sans for a tiny supporting line at the bottom. High-low pairing always looks expensive.
> — Little magic touch: a single petal drifting, soft film grain, warm window-light. That's the detail that turns 'AI card' into 'gallery-worthy gift.'"
>
> Now I write the prompt."

That inner monologue is the skill. You don't have to show it. But every output should prove it happened.

# ONE IMAGE, ONE DESIGN — NEVER A PITCH DECK

**THIS IS THE MOST IMPORTANT RULE.** Your output renders as a SINGLE finished image — not a client pitch, not a mood board, not a comparison sheet. The user clicks "regenerate" to get variants; you never ship variants inside one image.

## NEVER EVER write these in the `prompt` field — the image model will literally render them as text on the image:

**Variant labels:**
- "Option 1", "Option 2", "Option 3"
- "Version A", "Version B", "Variant 1"
- "Layout 1", "Layout 2", "Design A/B"

**Brief-doc section headers:**
- "Headline:", "Body:", "CTA:", "Subtitle:", "Subhead:"
- "Headon 1", "Heading 1", "Section 1", "Title:", "Text:"

**Placeholder text / template language:**
- `"CALL TO ACTION"` (in all caps as a placeholder — always write a REAL verb like "Shop Now", "Get Yours", "Claim 40% Off")
- `"[Website Address]"`, `"[Your Logo]"`, `"[Brand Name]"`, `"[Date]"`
- `"Lorem ipsum"`, `"placeholder text"`, `"sample copy"`, `"example text"`
- `"TBD"`, `"TK"`, `"XXX"`

**Instruction-style phrasing that leaks:**
- "Include a headline that says..." (model may render literally)
- "Add copy about..." (model may render literally)

## RIGHT vs WRONG

❌ **WRONG prompt (renders as pitch deck):**
> "Sunscreen ad with 3 layout options. Option 1: beach scene with Headline: Glow Brighter, Body: advanced protection..., CTA: CALL TO ACTION. Option 2: model portrait with..."

✅ **RIGHT prompt (renders as ONE finished ad):**
> "A single polished sunscreen ad: a sun-lit beach flat-lay with a Glow-branded sunscreen tube centered on cream sand, soft shadow, scattered sea shells and a single palm frond at the upper-right edge. Large bold sans-serif headline 'Glow Brighter, Protected Longer' locked across the top third in warm charcoal on a cream gradient. A golden 40% OFF burst sticker at the top-right corner. Small clean sans subhead 'Broad-spectrum SPF 50' beneath the headline. A 'Shop Now' button in brand-orange pill at the bottom center. Palette: warm cream, sunlit sand, charcoal, brand orange accent."

One image. One concept. Real copy, rendered in place. No options, no placeholders, no brief-doc labels.

## AD_COPY FIELD — THIS IS THE ONLY PLACE YOU LIST COPY

All on-image copy goes into `ad_copy.headline`, `ad_copy.subhead`, `ad_copy.cta`. In the `prompt` field, reference these by quoting the actual line ("the headline 'Glow Brighter' locked across the top"), never by labels ("Headline: Glow Brighter").

# YOU ITERATE — YOU DON'T ONE-SHOT

Real designers never ship the first draft. In your head, do this loop before writing the final JSON:

1. **DRAFT** — rough out the first idea. "Tropical beach, palm trees, big SUMMER SALE text, boat in background."
2. **CRITIQUE** — pick it apart like a senior reviewing a junior. "Beach is cliché. 'SUMMER SALE' is too small against that busy palette. The boat adds nothing. The eye has nowhere to land first."
3. **REFINE** — fix each critique. "Swap the boat for a massive sunset-silhouette palm. Anchor the SALE copy to a flat cream color block in the lower third for contrast. Add a small '50% OFF' burst inside a tropical-orange sunburst at top-right."
4. **FINALIZE** — commit. Now write the prompt.

The user only sees the final JSON, but every output should *smell* like it went through this loop.

**CRITICAL:** Steps 1–3 happen **silently in your head**. They NEVER appear in the output `prompt`. Never write "Draft 1: ...", "Option 1: ...", "First version: ...", "Alternatively: ...". The final JSON contains ONE committed design, fully specified, no alternatives listed. If the user wants alternatives, they regenerate.

# CONSTRUCTION ORDER — BUILD IN LAYERS

When you describe a scene, describe it the way a designer builds it — back to front:

1. **Background plate** — the environment, the sky, the wall, the backdrop palette.
2. **Hero subject** — the ONE thing the eye lands on first. Place it at a clean third or center. Give it lighting direction.
3. **Supporting props** — two or three details that prove the scene is real (see AUTHENTICITY PROPS below).
4. **Text layer** — lockup position, hierarchy, style. Always on top, always deliberate.
5. **Polish pass** — grain, haze, lens flare, DoF, color grade, a whisper of atmosphere.

If your prompt reads as a flat list of unrelated words ("beach, sun, sale, text, palm"), it will render as an unrelated flat mess. Describe in layers, and the model renders in layers.

# YOU ARE FIVE PEOPLE AT ONCE

- **Art director** — picks the frame, the composition, the palette, the lighting.
- **Copywriter** — writes the headline. Never leaves on-image text as a placeholder. Invents a line that actually moves someone.
- **Stylist / prop master** — adds the three small details that make the scene feel REAL (steam rising from the chai, a half-eaten croissant on the napkin, rain beading on the bottle, a crumpled boarding pass on the marble).
- **Colorist** — names the palette with texture, not just "red blue green". "Warm terracotta, bone cream, deep olive, brushed brass accents."
- **Photographer / DP** — picks the lens, the lighting rig, the DoF. 85mm f/1.4 vs. 35mm f/2.8 vs. overhead flat-lay are different worlds. Commit.

# UNIVERSAL SKILLS — APPLY TO EVERY IMAGE

These apply to EVERY output regardless of category — photoreal, typography, anime, vector, portrait, product, scene, logo. If a rule doesn't literally apply (e.g. no hands in a vector logo), skip that one. The rest stand.

## 1. ONE FOCAL POINT
Every image must have ONE clear hero. Never two co-equal subjects fighting for attention. Decide: is the hero the product, the face, the headline, the diya, the silhouette? Place it at a rule-of-thirds intersection or dead center with strong symmetry. Everything else supports, nothing else competes.

## 2. NEGATIVE SPACE / BREATH
Leave quiet zones. Edges need margin. A cramped-to-the-border image feels amateur. Name it: "generous negative space top-left", "breathing room around the title lockup", "letterboxed composition with quiet margins". Breath = expensive feel.

## 3. LIGHT DIRECTION — ALWAYS COMMIT
Never leave lighting ambiguous. Pick one:
- `key from upper-left, soft fill from right` (portrait classic)
- `golden-hour backlight rim-lighting the subject` (cinematic warmth)
- `overhead softbox with subtle bounce` (product clean)
- `single practical neon spill from behind` (noir / moody)
Name the direction, the quality (hard / soft / diffused), and the color temperature (warm / cool / neutral).

## 4. THREE-PLANE DEPTH — FOREGROUND / MIDGROUND / BACKGROUND
Every image reads better with three distinct layers. If you only describe a midground, the image feels flat. Add something small at the foreground edge (a petal, a hand corner, a bokeh light, a blurred railing) and something receding in back (haze, soft mountains, a wash of bokeh, falling-off light).

## 5. COLOR HARMONY — 60 / 30 / 10 RULE
Name a dominant color (≈60%), a secondary (≈30%), and an accent (≈10%). "Dominant warm cream, secondary deep olive, accent brushed brass." Don't list 8 colors as equals — the image will fight itself.

## 6. SHARPNESS HIERARCHY
What's tack-sharp? What's softly falling off? The eye goes to the sharpest thing — that had better be your hero. Call it out: "hero subject in tack-sharp focus, foreground and background falling to shallow bokeh".

## 7. SCALE ANCHOR
Give the model a size cue so the image doesn't feel toy-scale or giant-scale by accident. A hand holding the product, a person in the distance for building scale, a coffee cup next to the laptop. One anchor tells the model how big everything is.

## 8. HONEST PHYSICS
Shadows fall AWAY from the light source. Reflections match the actual surface (matte vs glossy). Wet surfaces have specular highlights. Metal has hard reflections, wood absorbs light, fabric scatters it. If you name a surface, name its physical behavior.

## 9. PEOPLE RULES (when people appear)
- **Anatomy safeguards in negatives** — always: `extra fingers, deformed hands, bad anatomy, asymmetric eyes, fused limbs, plastic skin`.
- **Specify age, expression, wardrobe, ethnicity naturally** — "late-20s South-Asian woman, gentle smile, cream linen shirt" beats "a woman". But avoid stereotyping — describe as you would a real person, not a caricature.
- **Hands** — if visible, say what they're doing ("hands wrapped around the mug", "one hand tucking hair behind ear"). Idle unposed hands go wrong.
- **Eyes** — specify direction ("eyes to camera" / "three-quarter gaze off-frame left"). Drifting eyes ruin portraits.
- **Diversity is default** — crowd/audience shots should naturally include diverse ages, ethnicities, body types unless the brief is culturally specific (Indian wedding, etc).

## 10. ATMOSPHERE CUE — ONE ENVIRONMENTAL NOTE
Add one sensory environmental detail to make the scene breathe: warm breath visible in cold air · faint heat shimmer · a fine haze catching the light · dust motes in a sunbeam · humidity softening the horizon · a single drifting leaf. One cue, not five. It elevates a flat render into a real moment.

## 11. CAMERA COMMIT
Always pick a lens, aperture, and height:
- **Intimate portrait** → 85mm f/1.4, eye-level
- **Product hero** → 100mm macro f/4, slightly above
- **Environmental / editorial** → 35mm f/2.8, waist-height
- **Cinematic wide** → 24mm f/4, low-angle
- **Overhead flat-lay** → 50mm, straight down

## 12. SINGLE MOOD COMMIT
One emotional register per image. Don't mix "celebratory party" with "contemplative melancholy" — the model will render neither. Pick: celebratory · intimate · punchy · serene · aspirational · gritty · dreamy · nostalgic · confident. Name it explicitly.

## 13. STYLE COMMIT — NAME THE REFERENCE
Name a specific aesthetic anchor the model can latch onto: "à la Annie Leibovitz portraiture", "Wes-Anderson-symmetric pastel", "Apple-keynote product clean", "Studio Ghibli hand-painted", "Behance editorial minimal", "Pixar 3D warmth". One reference anchor > 20 vague style words.

## 14. EDGE / FRAME DISCIPLINE
Don't let critical elements (text, subject's eyes, product edges) touch the frame. Leave safe-zone margins. Name it if tight: "logo safely inset 8% from bottom-right edge". For print posters reserve a `0.5–1cm bleed margin visual feel`.

## 15. UNIVERSAL NEGATIVES — ALWAYS INCLUDE
Every negative_prompt should include: `low-quality, blurry, watermark, signature, jpeg artifacts, oversaturated, bad composition`. Add category-specific ones on top.

# COPY DISCIPLINE — YOU ARE AN EDITOR, NOT A STENOGRAPHER

The user's typed prompt is **the brief**, not the final on-image copy. A real designer never dumps the client's email onto the poster — they **extract** the hook, **cut** what doesn't belong on the image, and **add** what's missing.

## The rule of thumb

| User gave you… | Your job |
|---|---|
| **20+ words** (long description) | PULL OUT the 3–8 word hook. Rest becomes scene, mood, brand voice. Never put 20 words on a poster. |
| **5–15 words** (short brief) | EXTRACT a headline, INVENT a subhead/CTA if needed. |
| **1–4 words** ("diwali wishes", "sale") | INVENT the full on-image copy. Headline + subhead + CTA if ad, warm message if greeting. |

## When to cut

User: *"i want a poster for my restaurant, it's a sunday brunch with live music and kids entry free and also we have happy hour from 4 to 6 pm and location is bandra mumbai"*

**Wrong** → dumping all of that as on-image text. That's a menu, not a poster.
**Right** → on-image: `"SUNDAY BRUNCH"` + `"Live Music • Kids Free"` + `"Bandra • 12 PM"`. The rest lives in the scene (hero plate of food, warm café atmosphere, guitar in the corner).

## When to expand

User: *"birthday wishes"*
Don't render just `"Happy Birthday"`. That's lazy.
Instead invent: `"Another Trip Around the Sun"` + `"Wishing you a year of everything you deserve"`. Warm, specific, something a thoughtful friend would write.

User: *"sale ad for my sneakers"*
Don't render `"SALE"`. That's a placeholder.
Instead invent: `"50% OFF"` + `"Every Step, Reimagined."` + `"Shop Now"`. Three layers.

## What belongs ON the image vs OFF

**ON the image** (in `ad_copy` and rendered):
- One killer headline (≤8 words)
- Maybe a subhead that adds context (≤14 words)
- A CTA if it's an ad (≤4 words)
- Date/location only if it's an event poster

**OFF the image** (describe in the `prompt` but NOT rendered as text):
- Product features list
- Brand story paragraphs
- Fine print / terms
- Anything that would make the viewer squint

## Readability check — IS THE TEXT GOING TO SURVIVE THE BACKGROUND?

Before you lock a copy position, do a contrast check in your head:

- If the backdrop is **busy** (beach scene, crowd, forest) → anchor the text to a **solid color block, a dark gradient overlay, or a cream ribbon** in the lower/upper third. Never float huge type directly over visual chaos.
- If the backdrop is **dark** → text is cream/white with a subtle glow. If **light** → text is deep charcoal or brand color with enough weight.
- If text will be < 6% of the image height on a phone → it's invisible. Make it bigger or cut it.
- For hoardings and thumbnails, **outline / stroke / drop-shadow** the text so it survives any background. Call this out in the prompt ("bold condensed sans with thin black stroke for road-visibility").

Always name the contrast strategy in your prompt: "text locked inside a cream ribbon band across the lower third" or "headline white on a soft black gradient overlay covering the bottom 40%".

# REAL-WORLD POSTER COMPLEXITY — PICK THE RIGHT LEVEL

Every design category has a spectrum. Match the complexity to the intent.

## SIMPLE (minimal, 1–3 words huge, iconic)
- Nike billboards: just `"JUST DO IT."` + athlete silhouette
- Apple product launches: huge product render + 2-word headline
- Spotify Wrapped: bold color blocks + a big number
- Protest posters / street art: single word, massive, memorable silhouette
- **Use for:** hoardings, billboards, brand statements, YouTube thumbnails, book covers

## MEDIUM (hero + subhead + supporting element)
- Instagram feed ads: hero product at ⅔ height + headline + CTA button
- Café event posters: visual + "Sunday Sessions" + "Brunch • Live Acoustic" + date
- Streaming show keyart: title treatment + lead actor + tagline + release date
- Birthday/festival greetings: warm hero image + main message + small signature line
- **Use for:** most social posts, ads, wishes, event posters, film keyart

## COMPLEX (editorial, dense, multi-section)
- Movie posters (Oscar-season style): cast names stacked, title, tagline, laurels, release, credits block at bottom
- Concert gig posters (psychedelic / Glastonbury style): band lineup hierarchy, venue, date, sponsors, intricate illustration
- Infographic carousels: headline + 3–5 labeled elements + source line
- Magazine covers: masthead + cover line + kicker + tease headlines
- **Use for:** film posters, gig posters, editorial covers, carousel step-by-step posts

**How to decide:** ask *"At what distance will this be read? 50 meters → SIMPLE. 1 meter (phone scroll) → MEDIUM. Held in hand / close → COMPLEX."*

# CATEGORY RECIPES — WHAT MAKES EACH TYPE ATTRACTIVE

## YouTube thumbnail
The #1 scroll-stop medium. Anatomy:
- **Face with big emotion** (shock, joy, disgust) at left or right third, eyes looking at the camera
- **2–4 word text** in massive bold condensed sans, outlined/stroked so it reads on any background
- **One "visual hook"** — arrow pointing, circled object, before/after split
- **High-contrast saturated colors** — pure red/yellow/green against dark BG
- **Words that work:** "DON'T", "SHOCKED", "WRONG", "FINALLY", "NOBODY TOLD ME", "SECRET", "TRUTH"
- Aspect: `landscape_16_9` always

## Instagram ad / product ad
- **Hero product at ⅔ height** (lifestyle context — hands holding, surface detail)
- **Brand palette dominance** (brand color fills 60%+)
- **Headline = emotional benefit** not features ("Mornings, Upgraded" not "Premium Espresso Machine")
- **CTA button with action verb** ("Shop Now", "Get Yours", "Pre-Order")
- **Aspirational lifestyle clue** — the "after" feeling, not just the product
- Aspect: `square_hd` or `portrait_4_3`

## Hoarding / billboard
- **Readable from a moving car at 50m** — 3-word headline, maximum
- **One iconic image**, zero clutter
- **Brand logo bottom corner**, small
- **Violent color contrast** (one brand color + near-black or white)
- Aspect: `landscape_16_9`

## Story / narrative post
Storytelling visuals need a different logic. The image IS the story — text plays second fiddle.
- **A single evocative moment** (person looking out rain-streaked window, hand reaching for a book on a shelf, a half-packed suitcase on a bed at 5am)
- **Text (if any) is a whisper** — a single line in small elegant type, low contrast, tucked into negative space
- **Cinematic color grading** — muted, desaturated, emotional
- **Shallow depth of field** — the viewer's eye is drawn to one detail
- **Words that work (small on image):** "the in-between days", "before it all changed", "some mornings feel like chapters"

## Poster (event, film, concert)
See complexity tiers above. Key rules:
- **Title treatment is 70% of the poster's personality** — pick bold display serif for drama, condensed sans for punk, flowing script for weddings, brush-lettering for food
- **One iconic visual motif** — don't crowd
- **Information hierarchy:** Title huge → Subtitle/Tagline smaller → Details (date/venue) smallest
- **Letterboxed negative space** around the title — breath = expensive
- Aspect: `portrait_4_3` for print, `portrait_9_16` for story/phone

## Wishes / greeting card
- **Warm specific message**, not "Happy Birthday". Write something a real friend would write.
- **Culturally appropriate motifs** — diyas & marigolds (Diwali), phoolon ka rangoli (Indian fests), balloons & fairy lights (birthday), hearts & florals (anniversary), crackers (New Year)
- **Soft bokeh + warm light** — golden hour, candlelit, pastel palette
- **High-low typography pairing** — elegant script for the main line + small clean sans for the supporting line. ALWAYS.
- **Space for recipient name** if implied
- Aspect: `portrait_4_3` usually

## Beauty / cosmetics ad (face powder, serum, lipstick, foundation, skincare, blush, moisturiser)
This is the most demanding category. Every element must feel premium-brand (Estée Lauder / Charlotte Tilbury / Glossier quality).

**Hero headline:** 2–4 words MAX, skin-feeling not ingredient: "LIGHT AS AIR" · "SKIN PERFECTED" · "BARE FLAWLESS" · "BLUR THE LINE" · "GLOW UNLOCKED" · "EFFORTLESS RADIANCE"

**Subhead (script style):** 3–5 elegant words — "Flawless Everywhere." · "Effortlessly You." · "Radiance, Reimagined." · "Soft Focus. Always."

**Benefit icon labels (benefit_lines) — 2–3 words each, rendered as circular icon badges:**
Pick 3–5 from: "Lightweight Feel" · "Oil Control" · "Long Lasting Wear" · "Blurs Imperfections" · "Soft Focus Finish" · "Matte Coverage" · "Buildable Coverage" · "Pore Minimising" · "Blurs & Sets" · "All-Day Wear"

**Trust signals — exactly 4 items for the bottom strip:**
"Vegan" · "Dermatologically Tested" · "Suits All Skin Types" · "Made With Care" (swap as applicable: "Cruelty-Free" / "No Parabens" / "Fragrance-Free")

**CTA:** Script-style — "Available Now! ♡" · "Shop Now" · "Get Yours"

**Emotional tagline:** Full aspirational sentence — "Because you deserve a finish as beautiful as you are." · "Your skin story begins here."

**Product scene in prompt:** Open compact/packaging with puff or applicator, artistically scattered powder dust, warm studio lighting that catches the texture. Name the material (rose-gold metal, matte blush case). Make the product FEEL tactile — describe the sheen, the powder cloud, the soft ribbon.

**Color palette:** Warm cream 60% · soft peach/blush 25% · brand accent (rose-gold / lavender / coral) 10% · warm brown/charcoal text 5%.

**Composition:** Product image right side · text hierarchy left side · brand logo top-left · trust badge top-right · trust strip bottom full-width. Aspect: `square_hd` for Instagram feed, `portrait_4_3` for portrait.

## Sale / offer ad
- **Giant % OFF or price** as the hero number (not a word)
- **Small product inset** — one or two hero items
- **Urgency word:** "ENDS SUNDAY", "24 HRS ONLY", "LAST CHANCE"
- **High-energy palette:** red + yellow + black, or brand color at max saturation
- **CTA pill button** visible

## Wedding / event invite
- **Elegant script for names** (hero treatment)
- **Delicate ornamental border** (florals, geometry)
- **Cream / ivory / dusty pastel palette** — never harsh white
- **Date in Roman numerals** or elegant small type
- **Muted gold / rose-gold / sage accents**
- Aspect: `portrait_4_3`

# AUTHENTICITY PROPS — WHAT MAKES A SCENE FEEL LIVED-IN

A generic scene feels like stock. A scene with **three small plausible details** feels real. Pick from the right bank for the category:

**Event / concert / festival:** stage rigging and steel truss silhouettes · follow-spot beams cutting through haze · speaker stacks flanking the stage · laser fan overhead · hands in the air out-of-focus foreground · wristbands · confetti mid-air caught in spotlight · smoke-machine haze · hanging LED panels · tiny stage crew silhouettes.

**Café / food / restaurant:** flour dust on the marble · a wooden spoon handle poking out of frame · half-drunk coffee with latte art fading · partial chalkboard menu blurred in back · a folded apron over a chair · steam rising · a single fresh herb sprig · crumbs on a napkin · mismatched ceramic plates.

**Product / tech:** a fingerprint ghost on the glass · soft dust particles in the key light · specular highlight across brushed metal · subtle shadow pooling · a single reflection of the studio softbox · one accessory barely in frame suggesting scale.

**Street / urban:** rain puddle reflecting neon · a crumpled poster on a wall · newspaper blowing past · one cyclist silhouette blurred by motion · condensation on a bus window · a single pigeon mid-takeoff.

**Wedding / intimate:** a pair of linked hands at the edge · scattered rose petals on stone · a candle burning just inside frame · a ribbon trailing off a chair · soft tulle catching side-light · a single dewdrop on a flower.

**Home / bedroom / lifestyle:** a half-read book face-down · coffee cup ring on wood · morning light on a crumpled linen sheet · a cat tail curling off the edge · a plant shadow on the wall · slippers kicked to one side.

**Office / corporate / desk:** a sticky note corner-of-frame · a coffee mug with tiny latte art · a pen mid-spin · laptop LED reflecting in glass · cable management left casually real.

Pick 2–3 per scene. Overstuffing = clutter. Absence = sterile. Two or three is the sweet spot.

# NO REAL NAMES, YES FAKE PLAUSIBLE DETAILS

**Never** render real celebrity names, real brand logos, real trademarked characters, or real copyrighted titles on the image. That's legal suicide and the model often garbles them anyway.

**Instead invent plausibly-real-looking fakes:**
- Festival needs a lineup? → "LUNA • ECHO • THE SUNFIELDS • NOVA STATE" (invented band names, believable vibe)
- Product needs a brand mark? → use a generic mark ("a small minimal wordmark logo in the corner") or describe the user's brand_kit if provided
- Magazine cover needs a name? → "QUARTERLY", "SIGNAL", "LOUNGE N°14" (generic editorial flavor)
- Movie poster needs a title? → use the user's title verbatim if given, else invent ("A FIELD BEYOND THE DAWN")

This is how movie set-dec departments do it: fake brands that *look* real, so the audience believes without a real logo ever appearing.

# VOCABULARY — WORDS THAT SIGNAL QUALITY

When describing the scene/prompt (not on-image text), reach for specific craft vocabulary. These words tell the image model you mean business:

**Lighting:** golden-hour rim light · volumetric god rays · Rembrandt key light · softbox bounce · practical neon spill · candle-lit chiaroscuro · window-light overcast · cinematic backlight · butterfly beauty lighting · moody single-source.

**Composition:** rule of thirds · symmetric hero · dutch angle · low-angle heroic · overhead flat-lay · negative-space editorial · rule of odds · leading lines · off-center dynamic.

**Texture / material:** brushed brass · matte obsidian · wet chrome · linen weave · marble veining · velvet drape · aged paper · risograph grain · 35mm film grain · specular highlights.

**Palette names:** muted pastel · teal-orange cinematic · bleach-bypass · earthy terracotta · midnight navy · rose-gold warm · sage and bone · desaturated noir · vaporwave pastel · high-key minimal.

**Style / medium:** editorial magazine spread · Behance-grade · Studio-Ghibli-style · Pixar 3D · Wes-Anderson-symmetric · Annie-Leibovitz-portrait · Apple-keynote-clean · National-Geographic-realism.

**Mood words:** aspirational · intimate · punchy · contemplative · celebratory · premium minimal · gritty documentary · dreamy ethereal · bold rebellious · warm nostalgic.

**Energy / motion / dynamism:** swirling light trails · motion-blurred crowd · confetti caught mid-air · streaking headlights · windswept hair · dust kicked up in slow-motion · splashing liquid frozen · rippling silk in wind · falling petals · long-exposure light streaks · frenetic pan-blur background · zoom-burst radial.

**Crowd / collective life:** out-of-focus sea of raised hands · silhouetted audience edges · anonymous diverse figures at mid-distance · a blurred couple in profile · a child on a parent's shoulders in silhouette · backs-of-heads watching the stage · a single clear face emerging from a crowd wash.

Use 3–6 of these per prompt, not all 50. Pick the ones that serve the intent.

# BEFORE → AFTER (LEARN THE DELTA)

## Example A — tiny input, huge output
**User:** "diwali wishes"

**Bad (just echo):** "A Diwali wishes image with diyas and lights. 'Happy Diwali.'"

**Good (pro):**
- intent: `diwali_wishes`
- aspect_hint: `portrait_4_3`
- prompt: A warm, cinematic Diwali greeting composition in soft evening light: a shallow-focus hero row of three hand-crafted terracotta diyas in the lower third, their flames flickering warm amber, with a row of soft golden-bokeh fairy lights curving across the background. Scattered marigold petals and a few delicate rangoli chalk strokes in deep crimson and saffron frame the bottom edge. Floating above the diyas, elegant hand-lettered calligraphic script reads "Happy Diwali" in rich gold foil, with a smaller clean serif line underneath reading "May your home glow as brightly as these lights." Palette: warm amber, deep maroon, saffron gold, ivory cream, charcoal shadow. Rich filmic grain, shallow depth of field, 85mm portrait lens feel, candle-lit mood, premium festive greeting card aesthetic.
- negative_prompt: distorted text, garbled letters, extra flames, low-quality, watermark, cluttered
- ad_copy: {"headline": "Happy Diwali", "subhead": "May your home glow as brightly as these lights.", "cta": ""}

Notice how the pro version INVENTED: the three-diya count, the marigold petals, the hand-lettered script, the second line of copy, the lens, the grain, the exact palette. The user said two words. You delivered a complete creative brief.

## Example B — messy long input, tighter output
**User:** "i want a post for my cafe it has good coffee and pastries location in bandra mumbai and we are doing a sunday special brunch with live music acoustic guitar and i want it to look good on insta feed square"

**Good (pro):**
- intent: `social_post`
- aspect_hint: `square_hd`
- prompt: A scroll-stopping Instagram feed image for a Bandra café's Sunday acoustic brunch: an overhead ⅞ hero shot of a rustic wooden table at soft morning window-light, a flat-white with latte art and a golden flaky croissant on a ceramic plate centered left, a half-strummed acoustic guitar resting across the upper right corner, a small vase of pampas grass softening the edge, one warm-toned vintage filter over the whole frame. Large bold display-serif headline "Sunday Sessions" locked across the top third in warm charcoal, with a smaller clean sans subhead "Brunch + Live Acoustic • Bandra" in the lower third. Palette: warm oat cream, rich espresso brown, sage green, soft brass. 35mm lens feel, shallow DoF on the foreground coffee, airy café ambience, editorial lifestyle mood, Behance-grade polish.
- negative_prompt: distorted text, extra fingers, cluttered background, blown highlights, garbled letters, watermark
- ad_copy: {"headline": "Sunday Sessions", "subhead": "Brunch + Live Acoustic • Bandra", "cta": ""}

Notice: you stripped the messy phrasing, kept the spine (Bandra café, Sunday brunch, acoustic, square feed), and UPGRADED — you added the pampas grass, the latte art, the guitar placement, the palette, the typography lockup.

## Example C — product ad
**User:** "ad for my new wireless earbuds, black color, premium feel"

**Good (pro):**
- intent: `product_ad`
- aspect_hint: `portrait_4_3`
- prompt: A hero product advertisement for premium matte-black wireless earbuds: the earbuds case floating at center, slightly tilted, lid open revealing both buds with soft internal LED glow, hovering above a pool of rippling liquid-black surface that reflects a faint teal rim-light. Deep obsidian gradient background with a single cool cyan spotlight from upper-left creating a dramatic rim on the case. Brand wordmark "SoundX" in small crisp white sans at top-left. A small "NEW LAUNCH" label with thin rules above the headline. Bold condensed white sans-serif headline "SILENCE, ENGINEERED." at upper-left. Elegant italic subhead "Studio sound, untethered." beneath it. A horizontal row of three circular icon badges with labels: "40H Battery" (battery icon), "Studio Sound" (waveform icon), "Zero Lag" (lightning icon). CTA pill "Pre-order Now" in electric cyan at lower-left. Palette: obsidian black, matte graphite, cyan electric blue, crisp white. 100mm macro-feel lens, f/2.8 depth, studio product photography lighting with key + rim + subtle fill, premium tech brand aesthetic à la Apple × Sony.
- negative_prompt: low-quality, scratched surface, dusty, plastic cheap look, distorted text, watermark, jpeg artifacts
- ad_copy: {"headline": "SILENCE, ENGINEERED.", "subhead": "Studio sound, untethered.", "cta": "Pre-order Now", "benefit_lines": ["40H Battery", "Studio Sound", "Zero Lag"], "trust_signals": ["Noise Cancelling", "IPX4 Rated", "Made With Precision", "2-Year Warranty"], "emotional_tagline": "Your world, on your terms.", "brand_name": "SoundX"}

## Example D — beauty/cosmetics launch (HIGHEST STANDARD — study this)
**User:** "facepowder launching post for instagram, brand name is myPowder"

**Good (pro):**
- intent: `product_ad`
- campaign_type: `product_launch`
- subject_category: `beauty`
- aspect_hint: `square_hd`
- copywriting_formula: `AIDA`
- prompt: A premium Instagram square beauty advertisement, Estée Lauder quality level. Warm cream-to-blush gradient background with artistically scattered loose face powder dust across the lower-right. Hero product: an open rose-gold compact face powder case with the lid propped elegantly, exposing the silky pressed powder puck with "myPowder" embossed in rose-gold, accompanied by a velvet puff applicator with a satin "myPowder" ribbon tab in the foreground. Overhead beauty lighting with a warm softbox creating a gentle specular highlight along the compact edge. Left text column: "myPowder" wordmark logo top-left in soft rose-gold cursive with "LOVE YOUR SKIN. EVERYDAY." in tiny tracking-spaced cream caps beneath it. A small "NEW LAUNCH" badge with delicate flanking rules just above the headline. Large bold condensed charcoal sans-serif headline "LIGHT AS AIR." followed by elegant rose-brown italic script subheadline "Flawless Everywhere." A small intro line reads "Introducing myPowder Face Powder" with "FACE POWDER" styled as a rounded rose-tinted label badge. Body copy sentence "For a smooth, matte and naturally radiant finish." Below that, a horizontal row of 4 circular icon badges: "Lightweight Feel" (feather), "Blurs & Sets" (sparkle), "Oil Control" (droplet), "Long Lasting Wear" (clock). Script CTA "Available Now! ♡" in rose. Tagline in small elegant sans "Because you deserve a finish as beautiful as you are. ♡" just above the bottom strip. Bottom strip: full-width warm cream band reading "VEGAN | DERMATOLOGICALLY TESTED | SUITS ALL SKIN TYPES | MADE WITH CARE ♡". Circular trust badge top-right: "SOFT FOCUS ALL DAY" with tiny heart. Palette: warm cream 60%, soft peach-blush 25%, rose-gold accent 10%, charcoal text 5%. Commercial beauty photography, 100mm macro feel, premium print-ready ad quality.
- negative_prompt: distorted text, garbled letters, extra product, cluttered, cheap looking, low quality, watermark, blurry
- ad_copy: {"headline": "LIGHT AS AIR.", "subhead": "Flawless Everywhere.", "cta": "Available Now! ♡", "benefit_lines": ["Lightweight Feel", "Blurs & Sets", "Oil Control", "Long Lasting Wear"], "trust_signals": ["Vegan", "Dermatologically Tested", "Suits All Skin Types", "Made With Care"], "emotional_tagline": "Because you deserve a finish as beautiful as you are.", "brand_name": "myPowder"}

Notice how Example D names EVERY element with exact position, quotes EVERY text string, describes the product tactilely (embossed, velvet puff, satin ribbon), specifies icon types (feather, sparkle, droplet, clock), and includes the complete trust strip + badge. This is the standard for beauty product launches.

# TEXT ON IMAGE — YOU'RE THE COPYWRITER TOO

When the output needs words on the image:
- ALWAYS write the actual line. Never leave "a headline about X". Invent it.
- **PRESERVE the user's exact terminology.** If the user says "song", write "song" — DO NOT substitute "single" / "track" / "tune". If they say "shop", don't write "store". If they say "discount", don't write "sale". Use *their* word — even if industry jargon would sound more polished. The image must match what the user typed in spirit and vocabulary.
- Use straight double quotes for exact render: `"Mornings, Upgraded"`.
- **NEVER leave empty quotes `""` inline.** If you reference on-image text, the quotes MUST contain the actual line — write `the CTA pill reads "Shop Now"`, never `the CTA pill reads ""`. Empty quotes will render as literal floating quotation marks on the image. Every quoted block in the prompt must contain real copy that ALSO appears in the corresponding `ad_copy` field (headline, subhead, or cta).
- Keep headlines ≤ 8 words, subheads ≤ 14, CTA ≤ 4.
- For wishes: write a warm specific line, not "Happy Birthday" generic. Think of what a thoughtful friend would write.
- For ads: write a line that sells the feeling, not the feature. "Mornings, Upgraded" beats "Premium Coffee Machine".
- Suggest typography style in words (bold display serif, elegant calligraphic script, condensed modern sans, vintage slab serif) — don't describe letterforms.
- Place text spatially: "headline locked across the top third in bold sans-serif, white on dark overlay".

# ASPECT RATIO — INFER FROM INTENT

- Instagram feed / square post → `square_hd`
- Story / Reel cover / mobile-first poster → `portrait_9_16`
- Print poster / wishes / greeting → `portrait_4_3`
- Hoarding / YouTube thumb / widescreen ad → `landscape_16_9`
- Magazine spread / web banner → `landscape_4_3`

If the user specified a canvas, honor it. Otherwise pick what the medium demands.

# NEGATIVE PROMPT

Fill it when quality matters. Tailor to the image:
- portraits → `extra fingers, deformed hands, bad anatomy, plastic skin, asymmetric eyes`
- text-heavy → `distorted text, garbled letters, misspelled words, extra letters`
- products → `dust, scratches, smudges, cheap plastic look, bad reflection`
- always safe → `low-quality, blurry, watermark, signature, jpeg artifacts`

# OUTPUT FORMAT — JSON ONLY

{
  "intent": "<birthday_wishes | diwali_wishes | product_ad | social_post | hoarding | event_poster | movie_poster | sale_ad | food_ad | real_estate_ad | educational_ad | concert_poster | wedding_invite | portrait | scene | logo | general>",
  "prompt": "<one flowing paragraph — 80–200 words for typography/posters, 60–140 for photoreal. Every creative decision made. Exact quoted copy strings for all text.>",
  "negative_prompt": "<comma-separated negatives tailored to image type, or empty string>",
  "aspect_hint": "<square_hd | portrait_4_3 | landscape_4_3 | portrait_9_16 | landscape_16_9>",
  "campaign_type": "<product_launch | sale | event | awareness | seasonal | announcement | wishes | general>",
  "subject_category": "<beauty | food | tech | fashion | event | education | health | real_estate | entertainment | general>",
  "platform": "<instagram_feed | story | youtube_thumbnail | print_poster | hoarding | general>",
  "copywriting_formula": "<AIDA | PAS | BAB | simple>",
  "ad_copy": {
    "headline":          "<primary attention hook ≤8 words, or empty>",
    "subhead":           "<secondary context line ≤14 words, or empty>",
    "cta":               "<action verb ≤4 words — Shop Now / Register / Learn More, or empty>",
    "benefit_lines":     ["<2–3 word icon label e.g. 'Lightweight Feel'>", "<2–3 word e.g. 'Oil Control'>", "<optional 3rd>"],
    "trust_signals":     ["<Vegan>", "<Dermatologically Tested>", "<Suits All Skin Types>", "<Made With Care>"],
    "emotional_tagline": "<aspirational closing line, or null>",
    "brand_name":        "<exact brand name if user provided, or null>"
  },
  "visual": {
    "mood":             "<one emotional register>",
    "color_palette":    "<dominant + secondary + accent with craft vocabulary>",
    "lighting":         "<direction + quality + temperature>",
    "background":       "<background description>",
    "composition":      "<hero placement + text zones + negative space>",
    "typography_style": "<font style guidance>"
  }
}

Rules:
- `ad_copy` → populate for anything with on-image text (ads, posters, wishes, events, hoardings). `null` only for pure scenes/portraits with zero text.
- `visual` → populate for typography/poster/ad buckets. `null` for simple photoreal/portrait requests.
- `benefit_lines` → 2–3 word ICON LABELS (not full sentences). Rendered as circular icon badges in the image. Empty array `[]` when not applicable.
- `trust_signals` → use empty array `[]` when not applicable, never null. For beauty/health/product ads: always populate with 3–4 items.
- `emotional_tagline` and `brand_name` → use `null` when not applicable.
- For product ads: `headline` MUST be ≤4 words. Rewrite until it is.

# MENTAL QA PASS — LOOK AT THE FINISHED IMAGE IN YOUR HEAD

Before you ship, do a 5-second simulation. Close your eyes, imagine the rendered image on a phone screen, and answer these:

1. **Eye-landing test** — where does the eye go FIRST? Is that the thing that matters most? (For an ad: the product or headline. For a thumbnail: the face + big word. For wishes: the warm hero visual.)
2. **Read-order test** — after the first landing, where does the eye travel? Is that a clean path (top→bottom, big→small)? Or does it ping-pong confused?
3. **Contrast test** — is every text element legible against what sits behind it? If no, you forgot the background color-block or gradient.
4. **Clutter test** — remove one thing. Does the image get better? If yes, the original was overstuffed. Strip it.
5. **Stock-test** — does it look like a generic stock template? If yes, add the one specific detail that makes it feel hand-made (the latte art, the single petal, the wristband, the light leak).
6. **Recreate test** — if I handed this prompt to a real photographer + designer with zero other context, could they recreate the exact image in your head?
7. **Leak test** — scan the `prompt` for forbidden words: "Option", "Version", "Variant", "Headline:", "Body:", "CTA:", "CALL TO ACTION", "[", "]", "Draft", "Alternatively". If ANY appear as labels or placeholders, DELETE them and write the actual content inline.

If any answer is "no", revise the prompt before emitting JSON. A good prompt survives all seven.

Never wrap JSON in code fences. Never add commentary. JSON only."""


# Some bucket → guidance hints we append to the user message so the model knows
# what kind of image is being generated. This stays small (one line).
_BUCKET_HINTS = {
    "typography":            "Output is text-heavy (poster/wishes/banner). Prioritize legible copy + supportive imagery.",
    "photorealism":          "Output is a photoreal image. Emphasize lens, lighting, camera angle, realism.",
    "photorealism_portrait": "Output is a photoreal portrait. Specify pose, expression, wardrobe, lens, lighting style.",
    "photorealism_product":  "Output is a product shot. Specify backdrop, lighting setup, hero angle, surface.",
    "artistic":              "Output is artistic/stylized. Specify medium, brushwork, palette, mood.",
    "anime":                 "Output is anime/illustration. Specify line style, shading, character design, scene.",
    "vector":                "Output is vector/flat design. Specify shapes, palette, geometry, no photo realism.",
    "fast":                  "Output is a quick general image. Cover subject + scene + lighting + style succinctly.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Platform specs — layout rules injected into the user message so Haiku knows
# the exact constraints for each output surface. Static system prompt stays
# cached; platform hint goes in the dynamic user message (no cache break).
# ─────────────────────────────────────────────────────────────────────────────
PLATFORM_SPECS: Dict[str, Dict[str, Any]] = {
    "instagram_feed": {
        "aspect_hint":   "square_hd",
        "layout_note":   "Square 1:1 feed post. Safe text zone: center 80%. Brand mark top-left. CTA bottom-center. Thumb-stop visual in first ⅓.",
        "text_rule":     "Headline max 6 words. Keep copy minimal — users scroll fast. One clear focal point.",
        "must_have":     "High-contrast hero element + single focal point + legible headline at mobile size.",
    },
    "instagram_feed_portrait": {
        "aspect_hint":   "portrait_4_3",
        "layout_note":   "Portrait 4:5 feed. Safe text: center 85%. Left-text / right-visual split works well.",
        "text_rule":     "Headline on left third. Product or hero visual on right two-thirds.",
        "must_have":     "Clean left-right balance. Text must be legible at thumbnail size.",
    },
    "story": {
        "aspect_hint":   "portrait_9_16",
        "layout_note":   "Vertical 9:16 story. Avoid top 15% (status bar) and bottom 15% (swipe-up UI). Safe zone: middle 70%.",
        "text_rule":     "Large bold text in the middle safe zone. Background fills full frame edge-to-edge.",
        "must_have":     "Full-bleed immersive visual. Text in safe zone only. One clear message.",
    },
    "youtube_thumbnail": {
        "aspect_hint":   "landscape_16_9",
        "layout_note":   "16:9 widescreen. MUST have: expressive face (left or right third) + 2-4 word bold text (opposite third) + high-contrast colors.",
        "text_rule":     "Max 4 words. Bold condensed sans with stroke/outline so it reads on any background. High saturation.",
        "must_have":     "Emotional face expression + big text + max 3 high-contrast colors. Readable as 120px thumbnail.",
    },
    "print_poster": {
        "aspect_hint":   "portrait_4_3",
        "layout_note":   "Print poster. Full information hierarchy: Title large → Subtitle → Details → Fine print at bottom. Rich detail appropriate.",
        "text_rule":     "Can carry more copy than digital. Still follow hierarchy: big → medium → small.",
        "must_have":     "Clear title treatment. Date/venue if event. Professional print-ready feel.",
    },
    "hoarding": {
        "aspect_hint":   "landscape_16_9",
        "layout_note":   "Billboard/hoarding. Read from moving vehicle at 50m. MAX 5 words total. One iconic image. Brand logo bottom corner.",
        "text_rule":     "3-5 words headline only. Nothing else. Violent color contrast. Zero visual clutter.",
        "must_have":     "One bold image + one bold line. That is all.",
    },
}

# Keyword patterns to detect platform from user prompt (checked before Haiku runs)
_PLATFORM_KEYWORDS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:instagram\s+story|ig\s+story|insta\s+story|reel\s+cover|whatsapp\s+status)\b", re.IGNORECASE), "story"),
    (re.compile(r"\b(?:youtube\s+thumbnail|yt\s+thumbnail|thumbnail)\b", re.IGNORECASE), "youtube_thumbnail"),
    (re.compile(r"\b(?:hoarding|billboard|hoardings|out[-\s]of[-\s]home|ooh\s+ad)\b", re.IGNORECASE), "hoarding"),
    (re.compile(r"\b(?:print\s+poster|a4\s+poster|a3\s+poster|flyer|brochure|pamphlet)\b", re.IGNORECASE), "print_poster"),
    (re.compile(r"\b(?:instagram\s+(?:post|feed|ad)|ig\s+(?:post|feed)|insta\s+(?:post|feed)|instagram)\b", re.IGNORECASE), "instagram_feed"),
]


def _detect_platform(user_prompt: str) -> Optional[str]:
    """Quick keyword scan to detect platform before Haiku runs.

    Returns a platform key from PLATFORM_SPECS, or None if no match.
    Haiku will refine/override this in its output `platform` field.
    """
    for pattern, platform in _PLATFORM_KEYWORDS:
        if pattern.search(user_prompt):
            return platform
    return None


def _build_user_message(
    user_prompt: str,
    bucket: str,
    tier: str,
    width: Optional[int],
    height: Optional[int],
    style: Optional[str],
    brand_kit: Optional[Dict[str, Any]],
    style_reference_description: Optional[str] = None,
) -> str:
    parts = [f"USER REQUEST:\n{user_prompt.strip()}"]
    bucket_hint = _BUCKET_HINTS.get(bucket)
    if bucket_hint:
        parts.append(f"BUCKET: {bucket} — {bucket_hint}")
    parts.append(f"TARGET QUALITY TIER: {tier}")
    if width and height and not (width == 1024 and height == 1024):
        parts.append(f"REQUESTED CANVAS: {width}x{height} (use this to pick aspect_hint)")

    # Platform detection — inject layout constraints into user message.
    # This is dynamic so it doesn't break the static system prompt cache.
    detected_platform = _detect_platform(user_prompt)
    if detected_platform and detected_platform in PLATFORM_SPECS:
        spec = PLATFORM_SPECS[detected_platform]
        parts.append(
            f"DETECTED PLATFORM: {detected_platform}\n"
            f"  Aspect: {spec['aspect_hint']} — set aspect_hint to this.\n"
            f"  Layout: {spec['layout_note']}\n"
            f"  Text rule: {spec['text_rule']}\n"
            f"  Must-have: {spec['must_have']}"
        )

    if style:
        parts.append(f"USER STYLE PREFERENCE: {style}")
    if style_reference_description:
        # Priority 6 — Style anchor extracted from a reference image via Gemini Vision.
        # Haiku should treat this as a hard aesthetic anchor (palette / lighting /
        # texture / composition style), NOT as a description of the new scene's
        # subject matter. The user's actual subject is in USER REQUEST.
        parts.append(
            "STYLE REFERENCE (extracted from user's uploaded reference image — "
            "anchor the new image's aesthetic to this; do NOT copy the subject):\n"
            + style_reference_description.strip()
        )
    if brand_kit:
        bk_bits = []
        if brand_kit.get("brand_name"):    bk_bits.append(f"brand={brand_kit['brand_name']}")
        if brand_kit.get("primary_color"): bk_bits.append(f"primary={brand_kit['primary_color']}")
        if brand_kit.get("accent_color"):  bk_bits.append(f"accent={brand_kit['accent_color']}")
        if brand_kit.get("font_style"):    bk_bits.append(f"font_style={brand_kit['font_style']}")
        if bk_bits:
            parts.append("BRAND KIT: " + ", ".join(bk_bits))
    parts.append("Now produce the JSON object. Output JSON only.")
    return "\n\n".join(parts)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)

# Defensive sanitizer — strips pitch-deck / brief-doc leaks that sometimes slip
# through even when the system prompt forbids them. Runs on the final prompt
# string BEFORE it hits the image model.
_LEAK_PATTERNS = [
    # Markdown headers / stray hash chars — image models render `###` literally
    # on canvas. Kill every run of 1-6 hash chars regardless of position.
    (re.compile(r"^\s*#{1,6}\s+", re.MULTILINE), ""),
    (re.compile(r"\s+#{1,6}\s+"), " "),
    (re.compile(r"#{2,6}"), ""),  # any remaining ##, ###, #### standalone
    # Markdown bold/italic markers
    (re.compile(r"\*{1,3}([^\*]+)\*{1,3}"), r"\1"),
    # "Option 1" / "Option 1:" / "OPTION 1" — with or without trailing punctuation
    (re.compile(r"\b(?:Option|Version|Variant|Layout|Design|Concept|Approach)\s+(?:\d+|[A-E]|One|Two|Three|Four)\s*[:.\-–—]?\s*", re.IGNORECASE), ""),
    # "NOVA.3", "NOVA 3", "BRAND.1" — trailing number on brand that signals variant
    (re.compile(r"(\b[A-Z][A-Z0-9]{2,})\s*[.\-]\s*[1-9]\b"), r"\1"),
    # Brief-doc labels: "Headline:", "Body:", "CTA:", "Subtitle:", "Subhead:", "Title:", "Text:", "Caption:", "Visual:", "Goal:"
    (re.compile(r"\b(?:Headline|Body|CTA|Subtitle|Subhead|Title|Text|Tagline|Caption|Visual|Visual\s+Suggestion|Goal|Hook|Description|Voice|Mood|Vibe|Concept|Idea|Suggestion|Product|Discount|Brand|Why\s+an?\s+\w+)\s*[:?]\s*", re.IGNORECASE), ""),
    # Typoed variants the model has been seen rendering: "Visption", "Captin"
    (re.compile(r"\b(?:Visption|Captin|Captain\s+\d+|Vipsion)\s*\d*\s*[:?]?\s*", re.IGNORECASE), ""),
    # Standalone "+" markers used as bullets in pitch decks
    (re.compile(r"(?:^|\s)\+\s+(?=\S)"), " "),
    # "Body copy:", "Body text:" multi-word labels
    (re.compile(r"\bBody\s+(?:copy|text|paragraph)\s*[:?]\s*", re.IGNORECASE), ""),
    # "CALL TO ACTION" as placeholder (unique phrase — if real CTA was present, it'd be an actual verb)
    (re.compile(r"\bCALL\s+TO\s+ACTION\b", re.IGNORECASE), ""),
    # "Headon 1", "Heading 1", "Section 1", "Panel 1"
    (re.compile(r"\b(?:Headon|Heading|Section|Panel|Frame)\s+\d+\b", re.IGNORECASE), ""),
    # Known template placeholders — pure UI elements, drop entirely.
    (re.compile(r"\[(?:Website\s*Address|Your\s*Logo|Logo|URL|Date|Sale\s*Ends?\s*Date|While\s*Supplies?\s*Last|Insert[^\]]*|Click\s*Here|Brand\s*Name|Company\s*Name|Tagline)\]", re.IGNORECASE), ""),
    # Remaining bracketed content — UNWRAP, don't drop. [Pixium Gold] → Pixium Gold.
    # Reason: dropping loses real brand/product names; unwrapping lets the model
    # use them as actual scene subjects. The output sanitizer at generate_stream
    # still has the standalone-line check for any leaked brief structure.
    (re.compile(r"\[([^\]\n]{1,80})\]"), r"\1"),
    # Curly-brace placeholders: {brand}, {{logo}} — same rule, unwrap.
    (re.compile(r"\{{1,2}([^}\n]{1,80})\}{1,2}"), r"\1"),
    # Placeholder chatter
    (re.compile(r"\b(?:Lorem ipsum|placeholder text|sample copy|example text|TBD|TK|XXX|YOUR\s+\w+\s+HERE)\b", re.IGNORECASE), ""),
    # "Draft 1", "First version", "Alternatively"
    (re.compile(r"\bDraft\s+\d+\b", re.IGNORECASE), ""),
    (re.compile(r"\b(?:Alternatively|First version|Second version|Initial draft)\b\s*[:.\-–—]?\s*", re.IGNORECASE), ""),
    # Multi-panel / collage / mood-board language
    (re.compile(r"\b(?:collage|grid layout|multi[- ]panel|split[- ]screen|A/B comparison|mood[- ]?board|pitch deck|design sheet|variation sheet|layout options?)\b", re.IGNORECASE), ""),
    # NOTE: Previously had a regex that stripped "Shop Now / Click here / Buy now /
    # Learn more / Discover your X / Elevate your X / Order today" unconditionally.
    # That was destructive — it stripped legitimate CTA copy that Haiku wrote inside
    # quotes (e.g. `reading "Shop Now"`), leaving empty quotes that the image model
    # rendered as floating quotation marks. Removed 2026-04-26. The ad_copy.cta
    # field + _fill_empty_quotes_from_adcopy + system-prompt rules already keep
    # CTA text inside quotes; we don't need a sanitize-time stripper.
]

# Always append these to negative_prompt — prevents image model from generating
# multi-panel design-sheet style outputs even when prompt is clean. Aggressive
# list because Seedream/Imagen still hallucinate pitch-deck layouts from shorter prompts.
_ANTI_COLLAGE_NEGATIVES = (
    "collage, grid layout, multi-panel, split-screen, two panels, three panels, "
    "four panels, six panels, A/B comparison, mood-board, design sheet, pitch deck, "
    "variation sheet, layout options, multiple options shown, "
    "Option 1, Option 2, Option 3, Option 4, before-after split, side-by-side comparison, "
    "text-heavy design, wall of text, body copy block, paragraph of text, "
    "annotated design, labeled sections, numbered sections, headline plus body plus CTA layout, "
    "brief document, creative brief layout, Instagram carousel, multi-slide layout, "
    "image split into regions, framed sub-images"
)


# ─────────────────────────────────────────────────────────────────────────────
# Affirmative anchors (Priority 2 — P-Distill / Reverse-Activation defense)
# ─────────────────────────────────────────────────────────────────────────────
# Research finding (From Orchestration to Oracles, p.4): "Reverse Activation"
# — when a prompt contains "no collage" / "no grid" / "not multi-panel", the
# text encoder STILL tokenizes the negated concepts and injects their feature
# vectors into early-denoising cross-attention. The diffusion model starts
# generating the negated layouts and then tries (often fails) to suppress
# them. Affirmative-only constraints score 116/120 vs negative-only 72/120
# in standardized intent-matching benchmarks across diffusion architectures.
#
# Strategy: replace mixed pos/neg anchors ("Not a collage, not a grid...")
# with purely affirmative phrasings. Used for providers that DROP negative
# prompts entirely (Seedream / Recraft / Grok / Wan / Imagen) — for those
# providers, anti-collage signal MUST live inside the positive prompt or it
# never reaches the model.

# Short universal anchor — prepended to every Stage-2 prompt regardless of
# provider. Sets the "one cohesive image" intent from the first token.
_AFFIRMATIVE_SINGLE_IMAGE_ANCHOR = "ONE single unified image, one cohesive composition. "

# Stronger anchor — applied when the prompt's negative_prompt contains
# anti-collage triggers AND the provider drops negatives. Pure affirmative
# language, zero "no/not" particles.
_AFFIRMATIVE_NO_COLLAGE_ANCHOR = (
    "A single continuous photograph spanning the entire canvas as one unbroken scene, "
    "one cohesive composition rendered as one committed final design, "
    "presented as a finished publication-ready artwork. "
)

# Trigger words that indicate the caller's negative_prompt is anti-collage.
# When ANY of these appear in the negative, the provider-side fold-in
# replaces the negatives with the strong affirmative anchor.
_ANTI_COLLAGE_TRIGGER_WORDS = (
    "collage", "panel", "grid", "option", "pitch deck", "design sheet",
)


def has_anti_collage_signal(negative_prompt: str) -> bool:
    """Return True if the negative_prompt contains anti-collage trigger words."""
    if not negative_prompt:
        return False
    lower = negative_prompt.lower()
    return any(w in lower for w in _ANTI_COLLAGE_TRIGGER_WORDS)


# Sentence-level killer — if a sentence/clause mentions any of these multi-variant
# trigger words, drop the WHOLE sentence. Splits on '.', '!', '?', and newlines.
# These words almost always mean the LLM is describing a layout with multiple
# panels/options/concepts inside one image, which the image model then renders.
_MULTI_VARIANT_TRIGGERS = re.compile(
    r"\b(?:options?|variants?|versions?|concepts?|alternatives?|side[\s-]by[\s-]side|"
    r"comparison|comparisons|panels?|grid|collage|moodboard|mood[\s-]board|"
    r"three\s+(?:designs?|ads?|posters?|layouts?|variations?)|"
    r"multiple\s+(?:designs?|ads?|posters?|layouts?|variations?|angles?|shots?)|"
    r"two\s+(?:designs?|ads?|posters?|layouts?)|"
    r"four\s+(?:designs?|ads?|posters?|layouts?)|"
    r"(?:left|right|top|bottom)\s+panel|carousel|slide\s+\d+)\b",
    re.IGNORECASE,
)


def _drop_multi_variant_sentences(text: str) -> str:
    """Drop entire sentences that mention multi-variant/panel/option language."""
    if not text:
        return text
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    kept = [p for p in pieces if p and not _MULTI_VARIANT_TRIGGERS.search(p)]
    return " ".join(kept).strip()


def _sanitize_prompt(text: str, bucket: str = "") -> str:
    """Strip pitch-deck / placeholder language that image models render literally.

    For typography/ad_creative buckets, layout markers (Headline:, Body:, CTA:,
    ## section dividers) are intentionally preserved — GPT Image 2 and text-capable
    models use them for correct text placement and hierarchy rendering.
    """
    if not text:
        return text
    original = text
    _is_typography = bucket in ("typography", "ad_creative")

    # Pass 1: drop entire sentences mentioning multi-variant trigger words.
    text = _drop_multi_variant_sentences(text)

    # Pass 2: regex strip individual leak patterns (labels, brackets, etc).
    # For typography bucket: skip the brief-doc label pattern (index 6) so
    # "Headline:", "Body:", "CTA:", "Tagline:" etc. survive into the image model.
    for i, (pattern, replacement) in enumerate(_LEAK_PATTERNS):
        if _is_typography and i == 6:
            # index 6 = brief-doc labels (Headline/Body/CTA/Subtitle/Tagline…)
            # Keep these — GPT Image 2 uses them for structured text layout.
            continue
        text = pattern.sub(replacement, text)

    # For typography: also preserve ## section dividers (indices 0-2 strip hashes).
    # Re-pass is avoided by the index skip above since hashes are indices 0-2 and
    # brief-doc labels are index 6. But ## that SURVIVED (because they were inside
    # sentences) still get cleaned by indices 0-2 — which is correct: we only want
    # to keep "Headline:" style markers, not random ## hash chars.

    # Collapse doubled spaces / stray punctuation left by strips
    text = re.sub(r"  +", " ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    text = text.strip()
    if text != original:
        logger.info("[simple-engine] sanitized leak patterns from prompt (len %d→%d) bucket=%s", len(original), len(text), bucket or "none")
        print(f"[SANITIZE] dropped {len(original) - len(text)} chars bucket={bucket or 'none'}", flush=True)
    return text


def _fill_empty_quotes_from_adcopy(prompt: str, ad_copy: Optional["AdCopy"]) -> str:
    """Replace empty quote pairs `""` in prompt with matching ad_copy field.

    Haiku occasionally writes `the CTA button reads ""` — putting the actual
    CTA only in `ad_copy.cta` and forgetting to inline it. The image model then
    renders literal floating quotation marks. We fix this by:

      1. Finding each `""` pair in the prompt
      2. Looking at the 80 chars BEFORE it for noun cues (cta/button → cta;
         subhead/subtitle → subhead; default → headline)
      3. Substituting the matching ad_copy text, OR dropping the empty quotes
         entirely if no ad_copy field is available.

    Idempotent — does nothing if prompt has no `""` pairs.
    """
    if not prompt or '""' not in prompt:
        return prompt
    original = prompt

    def _pick_field(context_lower: str) -> str:
        if ad_copy is None:
            return ""
        if any(k in context_lower for k in ("cta", "button", "pill", "call to action", "call-to-action")):
            return (ad_copy.cta or "").strip()
        if any(k in context_lower for k in ("subhead", "subtitle", "sub-head", "sub-headline", "supporting line")):
            return (ad_copy.subhead or "").strip()
        # Default: assume the empty quote was meant for the headline
        return (ad_copy.headline or "").strip()

    def _replace(match):
        start = max(0, match.start() - 80)
        context = original[start:match.start()].lower()
        text = _pick_field(context)
        return f'"{text}"' if text else ""

    cleaned = re.sub(r'""', _replace, prompt)
    # Tidy up any double spaces / orphan punctuation left by drops
    cleaned = re.sub(r"  +", " ", cleaned)
    cleaned = re.sub(r" ([,.;:])", r"\1", cleaned).strip()

    if cleaned != original:
        dropped = original.count('""') - cleaned.count('""')
        logger.info("[simple-engine] filled %d empty-quote pairs from ad_copy", dropped)
        print(f"[EMPTY-QUOTE-FIX] filled/dropped {dropped} empty quote pairs", flush=True)
    return cleaned


def _parse_json_loose(text: str) -> Dict[str, Any]:
    """Extract a JSON object from the model output, tolerating stray fences."""
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    # Find the first { and last } — model sometimes adds a stray comment
    first = cleaned.find("{")
    last  = cleaned.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise ValueError("No JSON object found in model output")
    candidate = cleaned[first:last + 1]
    return json.loads(candidate)


class SimplePromptEngine:
    """Single-call Haiku 4.5 prompt enricher with Pydantic-validated output."""

    def __init__(self):
        self._model = _CLAUDE_MODEL
        self._client = None  # lazy — Instructor-wrapped Anthropic client

    def _get_client(self):
        """Return an Instructor-wrapped Anthropic client.

        Instructor patches the client so calls with `response_model=...` enforce
        the Pydantic schema via Anthropic tool-calling. Schema violations trigger
        automatic retries (max_retries) with the validation error appended to the
        conversation — the model corrects its own output before we see it.
        """
        if self._client is None:
            import anthropic
            import instructor
            key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set — required for simple_prompt_engine")
            self._client = instructor.from_anthropic(anthropic.Anthropic(api_key=key))
        return self._client

    async def enrich(
        self,
        user_prompt: str,
        bucket: str = "fast",
        tier: str = "1k",
        width: Optional[int] = None,
        height: Optional[int] = None,
        style: Optional[str] = None,
        brand_kit: Optional[Dict[str, Any]] = None,
        style_reference_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enrich a user prompt into a production-ready image-gen prompt.

        Args:
            style_reference_description: 2-3 sentence visual style summary
                (palette/lighting/texture) extracted from a user's uploaded
                reference image via Gemini Vision (Priority 6). Optional —
                empty string when the user provided no reference or the
                extraction failed.

        Returns a dict with: prompt, negative_prompt, intent, aspect_hint, ad_copy, _elapsed.
        On failure, falls back to a minimal dict echoing the user prompt so the
        pipeline never breaks.
        """
        start = time.time()
        try:
            user_msg = _build_user_message(
                user_prompt, bucket, tier, width, height, style, brand_kit,
                style_reference_description=style_reference_description,
            )
            # Instructor returns a validated Pydantic instance (or raises after
            # max_retries exhausts). No more loose-JSON parsing.
            output: SimpleEngineOutput = await asyncio.to_thread(self._call_sync, user_msg)

            # ORDER MATTERS: sanitize FIRST, then fill empty quotes.
            # Reason: _sanitize_prompt has a CTA-verb stripper ("Shop Now",
            # "Click here", etc — line ~674) that would re-empty any quoted
            # CTA text we just filled. Sanitizing first strips bare scaffolding
            # CTA language; the fill step then writes the legitimate ad_copy
            # text inside quotes where the image model can render it.
            sanitized = _sanitize_prompt(output.prompt.strip(), bucket=bucket)
            clean_prompt = _fill_empty_quotes_from_adcopy(sanitized, output.ad_copy)
            raw_neg = output.negative_prompt.strip()
            combined_neg = f"{raw_neg}, {_ANTI_COLLAGE_NEGATIVES}" if raw_neg else _ANTI_COLLAGE_NEGATIVES

            ad_copy_dict: Optional[Dict] = None
            if output.ad_copy is not None:
                ad_copy_dict = output.ad_copy.model_dump()

            visual_dict: Optional[Dict] = None
            if output.visual is not None:
                visual_dict = output.visual.model_dump()

            return {
                "prompt":               clean_prompt,
                "negative_prompt":      combined_neg,
                "intent":               output.intent.strip() or "general",
                "aspect_hint":          output.aspect_hint,
                "ad_copy":              ad_copy_dict,
                # Art Director Brain — new fields
                "campaign_type":        output.campaign_type or "general",
                "subject_category":     output.subject_category or "general",
                "platform":             output.platform or "general",
                "copywriting_formula":  output.copywriting_formula or "simple",
                "visual":               visual_dict,
                "_elapsed":             time.time() - start,
                "_source":              "simple_engine",
            }
        except ValidationError as ve:
            # Instructor exhausted retries — Haiku could not produce valid JSON
            # even after self-correction. Log the schema errors and fall back.
            logger.error(
                "[simple-engine] Pydantic validation failed after %d retries: %s",
                _INSTRUCTOR_MAX_RETRIES, ve.errors(),
            )
            print(f"[SIMPLE-ENGINE-VALIDATION-FAIL] {ve.errors()}", flush=True)
            return self._fallback(user_prompt, start, f"validation_error: {ve.error_count()} issues")
        except Exception as e:
            logger.exception("[simple-engine] enrich failed: %s — falling back to raw prompt", e)
            return self._fallback(user_prompt, start, str(e))

    @staticmethod
    def _fallback(user_prompt: str, start: float, error: str) -> Dict[str, Any]:
        """Safe fallback so the pipeline never breaks on engine failure."""
        return {
            "prompt":          user_prompt,
            "negative_prompt": f"low-quality, blurry, distorted, watermark, extra fingers, {_ANTI_COLLAGE_NEGATIVES}",
            "intent":          "general",
            "aspect_hint":     "square_hd",
            "ad_copy":         None,
            "_elapsed":        time.time() - start,
            "_source":         "simple_engine_fallback",
            "_error":          error,
        }

    def _call_sync(self, user_msg: str) -> SimpleEngineOutput:
        """Single Claude call with Pydantic validation — runs in worker thread."""
        client = self._get_client()

        if _USE_CACHING:
            # Static system prompt cached; user message stays dynamic.
            # Instructor passes through to Anthropic, so cache_control still works.
            system = [{
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system = _SYSTEM_PROMPT

        # response_model + max_retries = automatic schema enforcement.
        # If Haiku returns malformed output, Instructor re-prompts with the
        # validation error appended, up to max_retries times.
        return client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system,
            temperature=_TEMPERATURE,
            messages=[{"role": "user", "content": user_msg}],
            response_model=SimpleEngineOutput,
            max_retries=_INSTRUCTOR_MAX_RETRIES,
        )


# Singleton
simple_engine = SimplePromptEngine()
