# 🚀 PHOTOGENIUS AI → BEAST MODE UPGRADE ROADMAP
**Goal:** Transform current 6-agent chain into world-class 10-agent Creative Studio
**Timeline:** 4 Sprints (8-12 weeks)
**Philosophy:** Future-native. Culturally fluent. Emotionally engineered.

---

## CURRENT STATE vs BEAST STANDARD (Gap Analysis)

### ✅ What We Already Have (Strong Foundation)

| Agent | Status | Quality |
|-------|--------|---------|
| Triage Agent | ✅ **EXISTS** | Good — detects platform, industry, explicit text |
| Brand Intel Agent | ✅ **EXISTS** | Good — color/tone inference, brand_kit override |
| Creative Director | ✅ **EXISTS** | Strong — produces Creative Bible with emotional_territory |
| Copy Writer | ✅ **EXISTS** | Strong — smart retries, char guard, explicit text lock |
| Image Prompter | ✅ **EXISTS** | Strong — per-model templates, 600-line KB |
| Layout Planner | ✅ **EXISTS** | Good — Fabric.js elements, fallback logic |
| Quality Gate | ✅ **EXISTS** | Basic — Gemini Vision 0-100 vs Creative Bible |

### ❌ What We're Missing (Beast Components)

| Agent | Status | Priority |
|-------|--------|----------|
| **Senior Design Director** | ❌ MISSING | **P0** — Visual System Decree (composition law, grid, type scale) |
| **Multiple Designer Variants** | ❌ MISSING | **P1** — 3 layout variants (safe/bold/disruptive) |
| **Motion Designer** | ❌ MISSING | **P2** — Animation brief, kinetic notes |
| **12-Dimension Quality Critic** | ⚠️ BASIC | **P0** — Current: 1-score. Need: 12-dimension review |
| **Learning Engine** | ❌ MISSING | **P1** — Logs decisions, model performance, feeds back |
| **Cultural Intelligence Layer** | ⚠️ IMPLICIT | **P1** — Need explicit 2025-2026 aesthetic encoding |
| **Structured JSON Handoffs** | ⚠️ PARTIAL | **P1** — locked_decisions + open_decisions protocol |
| **10 Beast Standards Tests** | ❌ MISSING | **P0** — Stranger Test, Scroll-Stop Test, etc. |
| **Revision Protocol** | ⚠️ BASIC | **P1** — Max 3 cycles, dimension-specific routing |

---

## SPRINT 1: BEAST QUALITY GATE (Weeks 1-3)
**Goal:** Transform basic quality gate into 12-dimension critic that rivals $10M agency QA

### New Agent: 12-Dimension Quality Critic

**File:** `apps/api/app/services/smart/quality_critic.py`

**12 Scoring Dimensions:**
```python
QUALITY_DIMENSIONS = {
    # Visual Execution (40%)
    "composition": {
        "weight": 0.12,
        "criteria": "Rule of thirds, visual hierarchy, balance, negative space mastery"
    },
    "color_authority": {
        "weight": 0.10,
        "criteria": "60-30-10 rule, palette sophistication, color psychology accuracy"
    },
    "typography": {
        "weight": 0.10,
        "criteria": "Hierarchy clarity, readability, font pairing, scale correctness"
    },
    "polish": {
        "weight": 0.08,
        "criteria": "Edge precision, texture refinement, lighting coherence"
    },

    # Strategic Alignment (30%)
    "concept_clarity": {
        "weight": 0.12,
        "criteria": "Single idea clarity, message-visual alignment, Creative Bible adherence"
    },
    "brand_fit": {
        "weight": 0.10,
        "criteria": "Brand equity preservation, tone consistency, logo integration"
    },
    "platform_native": {
        "weight": 0.08,
        "criteria": "Platform aesthetic contract, safe zones, aspect ratio optimization"
    },

    # Emotional Impact (20%)
    "scroll_stop_power": {
        "weight": 0.10,
        "criteria": "Attention capture in <1.5s, thumb-stopping quality"
    },
    "emotion_precision": {
        "weight": 0.10,
        "criteria": "Single emotion clarity, emotional_territory match"
    },

    # Technical Excellence (10%)
    "resolution_quality": {
        "weight": 0.05,
        "criteria": "Sharpness, artifact-free, proper exposure"
    },
    "text_legibility": {
        "weight": 0.05,
        "criteria": "Contrast sufficiency, size appropriateness, hierarchy execution"
    },

    # The Beast Standards (Pass/Fail Gates)
    "beast_gates": {
        "weight": 0.0,  # Not scored, but blocking
        "tests": [
            "stranger_test",      # Understand in 1.5s
            "scroll_stop_test",   # Stops thumb in feed
            "remove_color_test",  # Works in B&W
            "10pct_size_test",    # Communicates at 10% size
            "tomorrow_test",      # Doesn't feel dated
            "brand_remove_test",  # Feels like brand without logo
            "emotion_test",       # Single emotion nameable
            "competitor_test",    # Beats top 3 competitors
            "context_test",       # Fits where it lives
            "memory_test"         # Describable 24hrs later
        ]
    }
}
```

**Implementation:**
```python
class QualityCritic:
    """
    12-Dimension Quality Critic — The Beast Standard Enforcer

    Scores on 12 dimensions, enforces 10 Beast Standard gates.
    Minimum threshold: 8.5/10 overall + all Beast gates pass.
    Any dimension < 7.0 → automatic REVISE with targeted feedback.
    """

    async def critique(
        self,
        image_url: str,
        creative_bible: Dict,
        design_brief: Dict,
        platform: str,
    ) -> Dict:
        """
        Returns:
        {
            "overall_score": 8.7,
            "verdict": "APPROVED" | "REVISE" | "ESCALATE",
            "dimensions": {
                "composition": 9.2,
                "color_authority": 8.5,
                ...
            },
            "beast_gates": {
                "stranger_test": "PASS",
                "scroll_stop_test": "PASS",
                ...
            },
            "revision_notes": "Strengthen CTA contrast (+2 points readability)",
            "revision_route_to": "senior_designer",  # Dimension-specific routing
            "revision_cycle": 1  # Max 3
        }
        """
```

**Prompt Engineering:**
- Use **Gemini 2.0 Flash Thinking** for multi-step reasoning
- Separate system prompt per dimension (12 specialized critics)
- Final aggregator prompt combines scores + enforces Beast gates
- Revision notes use chain-of-thought to explain WHY score is low

**Integration Points:**
1. Replace current `gemini_vision_score()` in [poster_jury.py](apps/api/app/services/smart/poster_jury.py)
2. Add revision routing logic to [generate_stream.py](apps/api/app/api/v1/endpoints/generate_stream.py) Stage D
3. SSE events: `quality_checking` → `quality_scored` → `revision_triggered` (if needed)
4. Max 3 revision cycles before human escalation flag

**Deliverables:**
- [ ] `quality_critic.py` — 12-dimension scorer
- [ ] 12 dimension-specific Gemini prompts
- [ ] Beast Standard gate validators
- [ ] Revision routing logic
- [ ] SSE event updates
- [ ] Testing suite (100 test images × 12 dimensions)

---

## SPRINT 2: DESIGN DIRECTOR + MULTI-VARIANT (Weeks 4-6)
**Goal:** Add Visual System Decree + 3 designer variants (safe/bold/disruptive)

### New Agent: Senior Design Director

**File:** `apps/api/app/services/smart/design_director.py`

**Role:** Issues Visual System Decree — composition law, grid, type scale, color authority
**Position:** Between Creative Director and downstream agents (Copy Writer, Layout Planner)

**Visual System Decree:**
```json
{
  "composition_law": "asymmetric_grid_thirds",  // 7 archetypes from Creative Director
  "grid_system": {
    "columns": 12,
    "gutter": "16px",
    "margins": "5%",
    "safe_zones": {
      "top": "7%",
      "bottom": "10%",
      "sides": "5%"
    }
  },
  "type_scale": {
    "h1": "0.12 canvas_width",  // 123px at 1024
    "h2": "0.08 canvas_width",
    "h3": "0.05 canvas_width",
    "body": "0.03 canvas_width",
    "caption": "0.02 canvas_width"
  },
  "color_usage_rules": {
    "dominant": "60%",    // primary color
    "secondary": "30%",   // secondary color
    "accent": "10%",      // accent for CTA/highlights
    "rule": "Never exceed 3 colors + neutrals"
  },
  "hierarchy_enforcement": [
    "Hero image occupies {hero_occupies} (from Creative Director)",
    "Headline always largest text element",
    "CTA must be visually dominant button with accent color",
    "Body copy never competes with headline for attention"
  ],
  "forbidden_violations": [
    "Centered everything (must use asymmetry)",
    "Equal-sized text (must show hierarchy)",
    "Rainbow colors (max 3 + neutrals)",
    "Text over busy areas (preserve copy space)"
  ]
}
```

**Implementation:**
```python
class DesignDirector:
    """
    Senior Design Director — Visual System Authority

    Receives: Creative Director's concept + Creative Bible
    Outputs: Visual System Decree (NON-NEGOTIABLE for all downstream)
    """

    async def issue_decree(
        self,
        creative_bible: Dict,
        brand_palette: Dict,
        platform: str,
        aspect_ratio: float,
    ) -> Dict:
        """
        LLM: Gemini 2.5 Flash (temp=0.65, max_tokens=2000)
        Knowledge Base: Grid systems, type scales, composition laws
        """
```

### Enhanced Agent: Multi-Variant Layout Planner

**Upgrade:** `apps/api/app/services/smart/design_agent_chain.py` → Layout Planner now produces **3 variants**

**3 Variants:**
1. **Safe Variant** — Proven composition, minimal risk, commercial-first
2. **Bold Variant** — Strong execution, branded distinctiveness, confident
3. **Disruptive Variant** — Breaks conventions intentionally, attention-maximizing

**Selection Logic:**
- FAST tier → Safe variant only
- STANDARD tier → Safe + Bold (jury picks winner)
- PREMIUM tier → All 3 variants (jury picks winner)
- ULTRA tier → All 3 variants (user sees all 3, can pick)

**Implementation:**
```python
async def _agent_layout_planner(
    triage: Dict,
    creative: Dict,
    copy: Dict,
    design_decree: Dict,  # NEW: from Design Director
    aspect_ratio: float,
    variant: str = "safe",  # "safe" | "bold" | "disruptive"
) -> List[Dict]:
    """
    Now produces 3 layout variants per decree.
    Each variant respects decree's grid/hierarchy but takes different risk levels.
    """
```

**Deliverables:**
- [ ] `design_director.py` — Visual System Decree agent
- [ ] Grid system KB (12-column, 16-column, modular grids)
- [ ] Type scale calculator (responsive to canvas size)
- [ ] Multi-variant layout logic in Layout Planner
- [ ] Variant jury scorer (safe vs bold vs disruptive)
- [ ] UI update: variant selector for ULTRA tier

---

## SPRINT 3: CULTURAL INTELLIGENCE + LEARNING ENGINE (Weeks 7-9)
**Goal:** Encode 2025-2026 aesthetics + build feedback loop

### New Module: Cultural Intelligence Layer

**File:** `apps/api/app/services/smart/cultural_intelligence.py`

**Encodes:**
```python
AESTHETIC_ZEITGEIST_2026 = {
    "brutalism_luxury": {
        "keywords": ["raw concrete", "premium materials", "unfinished edges", "honest construction"],
        "when_to_use": "Tech, architecture, design-forward brands",
        "avoid_with": "Beauty, food, wellness (too cold)"
    },
    "ai_native": {
        "keywords": ["procedural patterns", "generative textures", "algorithmic beauty", "glitch aesthetic"],
        "when_to_use": "Tech, AI tools, crypto, digital-first brands",
        "avoid_with": "Traditional finance, healthcare (trust signals)"
    },
    "post_ironic_sincerity": {
        "keywords": ["meaning it", "constructed authenticity", "self-aware earnestness"],
        "when_to_use": "Gen Z brands, cultural movements, social causes",
        "avoid_with": "Corporate B2B (too risky)"
    },
    "retro_futures": {
        "keywords": ["Y2K", "90s rave", "70s sci-fi", "analog remixed with digital"],
        "when_to_use": "Fashion, music, youth brands, nostalgia plays",
        "avoid_with": "Finance, healthcare (dated perception)"
    },
    "bio_organic_geometry": {
        "keywords": ["grown shapes", "organic curves", "natural patterns", "living forms"],
        "when_to_use": "Wellness, sustainability, natural products",
        "avoid_with": "Tech, industrial (wrong material language)"
    },
    "quiet_luxury_loud": {
        "keywords": ["understated until it isn't", "subtle flex", "know-you-know", "stealth wealth"],
        "when_to_use": "Premium fashion, luxury goods, high-end services",
        "avoid_with": "Mass market (misses the point)"
    },
    "cultural_specificity": {
        "keywords": ["hyper-local", "regional pride", "specific over generic", "place-rooted"],
        "when_to_use": "Local businesses, cultural campaigns, regional brands",
        "avoid_with": "Global brands (too narrow)"
    }
}

GENERATIONAL_SIGNALS = {
    "gen_z": {
        "aesthetic": "texture, noise, lo-fi authenticity, anti-polish",
        "values": ["authenticity", "transparency", "mental health", "climate"],
        "anti_patterns": ["stock photos", "corporate speak", "try-hard cool", "boomer aesthetics"]
    },
    "millennials": {
        "aesthetic": "clean, purposeful, sustainable-signaling, Instagram-worthy",
        "values": ["sustainability", "experiences", "social justice", "wellness"],
        "anti_patterns": ["clutter", "irony", "corporate ladder", "McMansion style"]
    },
    "gen_alpha": {
        "aesthetic": "dimensional, interactive-feeling, maximalist but curated, AI-native",
        "values": ["digital-first", "gamified", "creator economy", "AI tools"],
        "anti_patterns": ["flat design", "static", "analog nostalgia", "2D thinking"]
    }
}

PLATFORM_AESTHETIC_CONTRACTS = {
    "tiktok": {
        "format": "vertical 9:16",
        "attention_window": "0.5s",
        "aesthetic": "text-forward, meme-fluent, movement-implied, raw edges",
        "forbidden": ["horizontal layouts", "small text", "silent-first design", "corporate polish"]
    },
    "instagram": {
        "format": "square 1:1 or portrait 4:5",
        "attention_window": "1.5s",
        "aesthetic": "editorial quality, color story, curated grids, aspirational",
        "forbidden": ["low-res", "text-heavy", "pixelated", "off-brand color"]
    },
    "youtube": {
        "format": "16:9 landscape",
        "attention_window": "2s",
        "aesthetic": "face + text, emotion-first, high contrast, scroll-stop thumbnails",
        "forbidden": ["no face", "small text", "low emotion", "generic stock"]
    },
    "linkedin": {
        "format": "1.91:1 landscape or 1:1",
        "attention_window": "3s",
        "aesthetic": "authority signals, restraint, no-try-hard professionalism, data-driven",
        "forbidden": ["memes", "casual slang", "emoji overload", "party photos"]
    },
    "pinterest": {
        "format": "2:3 portrait",
        "attention_window": "2s",
        "aesthetic": "aspirational, high-craft, lifestyle integration, saveable",
        "forbidden": ["text-only", "ads that look like ads", "low-effort", "stock photos"]
    },
    "ooh_billboard": {
        "format": "wide landscape",
        "attention_window": "3s at 80mph",
        "aesthetic": "single idea, readable at distance, 3 words max, bold color",
        "forbidden": ["small text", "multiple messages", "complex visuals", "QR codes"]
    }
}
```

**Integration:**
- Creative Director consults Cultural Intelligence before issuing concept
- Design Director enforces platform aesthetic contracts in decree
- Prompt Engineer injects zeitgeist keywords per aesthetic chosen

### New Agent: Learning Engine

**File:** `apps/api/app/services/smart/learning_engine.py`

**What It Learns:**
1. **Decision Quality:** Which Creative Director concepts led to high Quality Critic scores?
2. **Model Performance:** Which fal.ai models perform best per bucket × aesthetic?
3. **User Preferences:** Which variants do users pick (safe vs bold vs disruptive)?
4. **Platform Winners:** Which designs perform best per platform (tracked via Style DNA feedback)?
5. **Cultural Drift:** Which aesthetics are trending up/down over time?

**Storage:**
```python
# PostgreSQL schema (add to Prisma)
model LearningLog {
  id              String   @id @default(cuid())
  timestamp       DateTime @default(now())

  // Input fingerprint
  user_prompt     String
  bucket          String
  platform        String
  aesthetic       String?

  // Agent decisions
  creative_concept     String
  visual_decree_id     String
  layout_variant       String  // safe | bold | disruptive
  model_used           String

  // Output quality
  quality_score        Float
  dimension_scores     Json    // 12-dimension breakdown
  beast_gates_passed   Int     // 0-10
  user_feedback        String? // thumbs_up | thumbs_down | neutral

  // Performance tracking
  generation_time_ms   Int
  cost_usd             Float
  revision_cycles      Int

  @@index([bucket, platform, aesthetic])
  @@index([quality_score])
  @@index([user_feedback])
}
```

**Feedback Loop:**
- Triage Agent: "For tech + Gen Z + TikTok, ai_native aesthetic has 9.2 avg quality score (10k samples)"
- Prompt Engineer: "flux_2_pro + retro_futures aesthetic has 15% higher scroll-stop scores than ideogram"
- Quality Critic: "When color_authority dimension is weak, 80% caused by palette too complex (>3 colors)"

**Implementation:**
```python
class LearningEngine:
    """
    Continuous learning system that improves agent decisions over time.

    Logs every generation + decision + outcome.
    Provides real-time recommendations to agents via learned patterns.
    """

    async def log_generation(self, full_brief: Dict, quality_result: Dict, user_feedback: str):
        """Store complete decision trail + outcomes"""

    async def get_recommendation(self, context: Dict) -> Dict:
        """
        Query learned patterns for this context.

        Returns:
        {
            "aesthetic_recommendation": "ai_native",
            "confidence": 0.87,
            "rationale": "Tech + Gen Z + Instagram: ai_native has 9.2 avg score (2.3k samples)",
            "model_preference": "flux_2_pro",
            "expected_quality": 8.9
        }
        """
```

**Deliverables:**
- [ ] `cultural_intelligence.py` — 2025-2026 aesthetic encoding
- [ ] Generational signals + platform contracts
- [ ] `learning_engine.py` — logging + feedback loop
- [ ] PostgreSQL schema update (LearningLog table)
- [ ] Recommendation API for agents
- [ ] Analytics dashboard (top aesthetics, model performance, quality trends)

---

## SPRINT 4: STRUCTURED HANDOFFS + MOTION BRIEF (Weeks 10-12)
**Goal:** Enforce JSON protocol + add motion designer for future animation

### Upgrade: Structured JSON Handoffs

**Current:** Agents pass Python dicts (loose structure, implicit contracts)
**Beast:** Agents pass typed JSON with locked_decisions + open_decisions + constraints

**Protocol:**
```python
from pydantic import BaseModel
from typing import List, Dict, Literal

class AgentHandoff(BaseModel):
    """
    Structured communication between agents.
    Enforces locked decisions (non-negotiable) vs open decisions (to be solved).
    """
    from_agent: str
    to_agent: str
    phase: int  # 1-6 (matches pipeline phases)
    timestamp: str

    locked_decisions: Dict[str, any]  # NON-NEGOTIABLE (e.g., creative_concept, palette)
    open_decisions: Dict[str, str]    # TO BE SOLVED (e.g., "layout": "pending")
    constraints: List[str]            # HARD RULES (e.g., "headline <= 40 chars")
    quality_flags: List[str]          # WARNINGS (e.g., "low contrast detected")

    # For revision loops
    revision_notes: str = ""
    revision_target_dimension: str = ""  # Which dimension to fix
    revision_cycle: int = 0              # Max 3

# Example: Creative Director → Design Director
handoff = AgentHandoff(
    from_agent="creative_director",
    to_agent="design_director",
    phase=2,
    timestamp="2026-04-07T10:23:45Z",
    locked_decisions={
        "creative_concept": "Rebellious confidence with premium restraint",
        "emotional_territory": "aspirational defiance",
        "palette": {
            "primary": "#0A0A1A",      # deep midnight navy
            "secondary": "#FFD700",    # bright gold
            "accent": "#00D4FF"        # electric cyan
        },
        "composition_archetype": "asymmetric_grid"
    },
    open_decisions={
        "grid_columns": "pending",
        "type_scale_ratio": "pending",
        "safe_zone_margins": "pending"
    },
    constraints=[
        "Platform: Instagram portrait 4:5",
        "Max 3 colors + neutrals",
        "Hero image must occupy center_50 or full_bleed"
    ],
    quality_flags=[
        "Warning: asymmetric_grid requires strong hierarchy to avoid chaos"
    ]
)
```

**Enforcement:**
- Each agent validates incoming handoff schema
- Downstream agents CANNOT override locked_decisions (code-level validation)
- Open decisions MUST be resolved before passing to next agent
- Quality Critic validates final output against ALL locked_decisions

**Deliverables:**
- [ ] `agent_protocol.py` — Pydantic schemas for all handoffs
- [ ] Validation logic in each agent (reject invalid handoffs)
- [ ] locked_decisions enforcement (immutable once set)
- [ ] Update all 10 agents to use structured handoffs

### New Agent: Motion Designer (Phase 2 — Future Animation)

**File:** `apps/api/app/services/smart/motion_designer.py`

**Role:** Produces animation brief + kinetic notes for future video/motion exports
**Note:** NOT generating animations yet — just the brief for future implementation

**Output:**
```json
{
  "animation_style": "subtle_kinetic",  // or bold_movement, static_elegant
  "entry_animation": {
    "headline": "fade_up_stagger",
    "duration_ms": 800,
    "delay_ms": 200
  },
  "attention_cues": [
    {
      "element": "cta_button",
      "effect": "pulse_glow",
      "frequency": "2s interval",
      "intensity": "subtle"
    }
  ],
  "exit_animation": null,  // static poster, no exit
  "temporal_hierarchy": [
    "1. Hero image loads",
    "2. Brand bar fades in (200ms delay)",
    "3. Headline staggers up word-by-word (100ms each)",
    "4. CTA button pulses glow (after 1.5s)"
  ],
  "kinetic_notes": "Keep movement subtle — this is editorial, not TikTok. Stagger creates sophistication."
}
```

**Integration:**
- Runs in parallel with Copy Writer + Layout Planner (Phase 3)
- Consulted by future video export pipeline (Fabric.js → Lottie JSON)
- For now: logs animation brief, doesn't execute

**Deliverables:**
- [ ] `motion_designer.py` — animation brief generator
- [ ] Animation style KB (subtle vs bold vs static)
- [ ] Temporal hierarchy logic
- [ ] JSON schema for animation brief
- [ ] Future: Lottie JSON export (Sprint 5+)

---

## IMPLEMENTATION PRIORITY ORDER

### P0 (Critical — Sprint 1)
1. ✅ 12-Dimension Quality Critic
2. ✅ 10 Beast Standard gates
3. ✅ Revision routing logic

### P1 (High — Sprint 2)
4. ✅ Senior Design Director
5. ✅ Multi-variant Layout Planner (3 variants)
6. ✅ Cultural Intelligence Layer
7. ✅ Learning Engine

### P2 (Medium — Sprint 3-4)
8. ✅ Structured JSON handoffs
9. ✅ Motion Designer (brief only)
10. ⏳ Analytics dashboard (Learning Engine insights)

### P3 (Nice-to-have — Sprint 5+)
11. ⏳ Multiple Copy Writer variants (2 writers per brand tone)
12. ⏳ Lottie JSON animation export
13. ⏳ A/B testing framework (track variant performance)

---

## TECHNICAL ARCHITECTURE UPDATES

### New Files to Create

```
apps/api/app/services/smart/
├── quality_critic.py          # 12-dimension critic (NEW)
├── design_director.py         # Visual System Decree (NEW)
├── cultural_intelligence.py   # 2026 aesthetics (NEW)
├── learning_engine.py         # Feedback loop (NEW)
├── motion_designer.py         # Animation brief (NEW)
└── agent_protocol.py          # Pydantic schemas (NEW)

apps/api/app/api/v1/endpoints/
├── learning/
│   ├── log.py                 # POST /learning/log
│   ├── recommend.py           # GET /learning/recommend
│   └── analytics.py           # GET /learning/analytics

apps/web/app/(dashboard)/
├── quality-insights/          # Quality Critic breakdown UI
└── learning-dashboard/        # Learning Engine analytics
```

### Database Schema Updates

```prisma
// Add to schema.prisma

model LearningLog {
  id                    String   @id @default(cuid())
  timestamp             DateTime @default(now())

  // Input
  user_prompt           String
  bucket                String
  platform              String
  aesthetic             String?

  // Decisions
  creative_concept      String
  visual_decree_id      String
  layout_variant        String
  model_used            String

  // Quality
  quality_score         Float
  dimension_scores      Json
  beast_gates_passed    Int
  user_feedback         String?

  // Performance
  generation_time_ms    Int
  cost_usd              Float
  revision_cycles       Int

  @@index([bucket, platform, aesthetic])
  @@index([quality_score])
  @@index([user_feedback])
}

model VisualDecree {
  id                    String   @id @default(cuid())
  created_at            DateTime @default(now())

  composition_law       String
  grid_system           Json
  type_scale            Json
  color_usage_rules     Json
  hierarchy_enforcement Json
  forbidden_violations  Json

  // Links to generations
  learning_logs         LearningLog[]
}
```

### Environment Variables

```bash
# Add to .env

# Quality Critic
QUALITY_CRITIC_THRESHOLD=8.5              # Min overall score to pass
QUALITY_DIMENSION_FLOOR=7.0               # Min per-dimension score
QUALITY_REVISION_MAX_CYCLES=3             # Max revision loops

# Learning Engine
LEARNING_ENGINE_ENABLED=true
LEARNING_MIN_SAMPLES=100                  # Min samples before recommendations
LEARNING_CONFIDENCE_THRESHOLD=0.75        # Min confidence to recommend

# Cultural Intelligence
CULTURAL_ZEITGEIST_VERSION="2026-Q2"      # Update quarterly
AESTHETIC_AUTO_DETECT=true                # Auto-detect aesthetic from prompt
```

---

## TESTING STRATEGY

### Quality Critic Testing
- 100 test images across all buckets
- Manual ground truth scoring (12 dimensions each)
- Gemini scoring vs human scoring correlation > 0.85
- Beast gate validators (10 tests each)

### Multi-Variant Testing
- Generate 3 variants for 50 test prompts
- Jury scores: safe < bold < disruptive (risk ordering)
- User preference survey (which variant would you pick?)

### Learning Engine Testing
- Seed with 1000 historical generations
- Validate recommendation accuracy (precision > 0.80)
- A/B test: with learning vs without learning (quality improvement)

### Cultural Intelligence Testing
- Aesthetic classification accuracy (human vs AI agreement > 0.90)
- Platform contract enforcement (reject non-compliant designs)
- Generational signal decoding (Gen Z vs Millennial style separation)

---

## SUCCESS METRICS

### Sprint 1 (Quality Critic)
- ✅ 12-dimension scoring implemented
- ✅ Overall quality score avg > 8.5 (up from 7.2 baseline)
- ✅ Revision rate < 15% (down from 35% baseline)
- ✅ All 10 Beast gates pass rate > 90%

### Sprint 2 (Design Director + Multi-Variant)
- ✅ Visual System Decree in 100% of typography generations
- ✅ 3 layout variants generated in < 5s
- ✅ Bold variant selected > 40% in STANDARD tier (vs 100% safe baseline)
- ✅ Disruptive variant selected > 20% in PREMIUM tier

### Sprint 3 (Cultural Intelligence + Learning)
- ✅ Aesthetic auto-detection accuracy > 85%
- ✅ Learning recommendations improve quality score by +0.5 avg
- ✅ Model selection from Learning Engine beats router by +10% quality
- ✅ 10,000 learning logs collected in first month

### Sprint 4 (Structured Handoffs + Motion)
- ✅ 100% of agent communication via typed JSON
- ✅ Zero locked_decision violations (enforced by code)
- ✅ Motion brief generated for 100% of typography bucket
- ✅ Future-ready: animation export blueprint documented

---

## THE NORTH STAR

By end of Sprint 4, every PhotoGenius AI output should make people think:

> **"I don't know how they made this, but I want one."**

Not good. Not impressive. **Covetable. Memorable. Emotionally precise.**

The future of advertising is not louder. It's more true.

---

## MIGRATION NOTES

### Backward Compatibility
- All new agents are ADD-ON (don't break existing flow)
- Quality Critic replaces basic quality gate (seamless swap)
- Design Director inserts between Creative Director and Layout Planner
- Learning Engine runs async (doesn't block generation)

### Feature Flags
```python
# Add to config.py
ENABLE_QUALITY_CRITIC = os.getenv("ENABLE_QUALITY_CRITIC", "true") == "true"
ENABLE_DESIGN_DIRECTOR = os.getenv("ENABLE_DESIGN_DIRECTOR", "true") == "true"
ENABLE_MULTI_VARIANT = os.getenv("ENABLE_MULTI_VARIANT", "true") == "true"
ENABLE_LEARNING_ENGINE = os.getenv("ENABLE_LEARNING_ENGINE", "false") == "true"
ENABLE_MOTION_DESIGNER = os.getenv("ENABLE_MOTION_DESIGNER", "false") == "true"
```

### Rollout Plan
1. **Week 1-3:** Quality Critic (shadow mode — log scores, don't block)
2. **Week 4:** Quality Critic (enforce mode — block < 8.5 scores)
3. **Week 5-6:** Design Director + Multi-Variant (STANDARD tier only)
4. **Week 7:** Multi-Variant (all tiers)
5. **Week 8-9:** Cultural Intelligence + Learning Engine (logging only)
6. **Week 10:** Learning Engine recommendations live
7. **Week 11-12:** Structured handoffs + Motion Designer

---

**END OF ROADMAP**

*"The image is the last 5% of the work. The first 95% is strategy, psychology, culture, hierarchy, and intention."*

Let's build the Beast. 🚀
