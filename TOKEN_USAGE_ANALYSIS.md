# Token Usage Analysis — 1 Image Generation

## Agent Chain Token Usage (Typography Bucket)

### Design Agent Chain (6 Agents - Gemini 2.5 Flash)

| Agent | Temperature | Max Output Tokens | Avg Input Tokens | Total Tokens/Call | Cost/Call (Gemini Flash) |
|-------|-------------|-------------------|------------------|-------------------|--------------------------|
| **1. Triage** | 0.3 | 1,000 | ~800 | ~1,800 | $0.000027 |
| **2. Brand Intel** | 0.5 | 1,200 | ~900 | ~2,100 | $0.000032 |
| **3. Creative Director** | 0.82 | 4,000 | ~3,500 | ~7,500 | $0.000113 |
| **4. Copy Writer** | 0.85 | 3,000 | ~2,800 | ~5,800 | $0.000087 |
| **4b. Char Guard** (conditional) | 0.2 | 600 | ~400 | ~1,000 | $0.000015 |
| **5. Image Prompter** | 0.72 | 3,500 | ~4,200 | ~7,700 | $0.000116 |
| **6. Layout Planner** | 0.3 | 2,500 | ~1,800 | ~4,300 | $0.000065 |
| **TOTAL (Agent Chain)** | - | **15,800** | **~14,400** | **~30,200** | **$0.000455** |

### Gemini Prompt Engine (Non-Typography Buckets)

| Stage | Temperature | Max Output Tokens | Avg Input Tokens | Total Tokens/Call | Cost/Call |
|-------|-------------|-------------------|------------------|-------------------|-----------|
| **Stage A: Brief** | 0.90 | 1,500 | ~1,200 | ~2,700 | $0.000041 |
| **Stage B: CDI** | 0.85 | 2,000 | ~2,500 | ~4,500 | $0.000068 |
| **Stage B2: Critic** (Premium only) | 0.25 | 400 | ~800 | ~1,200 | $0.000018 |
| **TOTAL (Non-Typography)** | - | **3,900** | **~4,500** | **~8,400** | **$0.000127** |

### Quality Critic (Gemini Vision - PREMIUM/ULTRA only)

| Component | Temperature | Max Output Tokens | Avg Input Tokens | Total Tokens/Call | Cost/Call |
|-----------|-------------|-------------------|------------------|-------------------|-----------|
| **Dimension Scoring** (6 batches × 2 dims) | 0.3 | 2,000 per batch | ~500 per batch | 6 × ~2,500 = ~15,000 | $0.000225 |
| **Beast Gates Validation** | 0.3 | 3,000 | ~800 | ~3,800 | $0.000057 |
| **TOTAL (Quality Critic)** | - | **15,000** | **~3,800** | **~18,800** | **$0.000282** |

---

## COMPLETE TOKEN BREAKDOWN (1 Image Generation)

### Scenario 1: FAST Tier (Typography Bucket)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Flux 2 Pro): N/A (API cost separate)
Quality Critic:        0 tokens (FAST skips quality gate)
──────────────────────────────────────────────────
TOTAL TOKENS:          ~30,200 tokens
TOTAL AI COST:         $0.000455 (prompting only)
GENERATION COST:       $0.025 (Flux 2 Pro)
GRAND TOTAL:           $0.025455
```

### Scenario 2: STANDARD Tier (Typography Bucket)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Flux 2 Pro): N/A
Quality Critic:        0 tokens (STANDARD skips quality gate)
──────────────────────────────────────────────────
TOTAL TOKENS:          ~30,200 tokens
TOTAL AI COST:         $0.000455
GENERATION COST:       $0.025
GRAND TOTAL:           $0.025455
```

### Scenario 3: PREMIUM Tier (Typography Bucket)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Flux 2 Pro): N/A
Quality Critic:        18,800 tokens ($0.000282)
──────────────────────────────────────────────────
TOTAL TOKENS:          ~49,000 tokens
TOTAL AI COST:         $0.000737
GENERATION COST:       $0.025
GRAND TOTAL:           $0.025737
```

### Scenario 4: ULTRA Tier (Typography Bucket)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Flux 2 Pro 2×): N/A
Quality Critic:        18,800 tokens ($0.000282)
──────────────────────────────────────────────────
TOTAL TOKENS:          ~49,000 tokens
TOTAL AI COST:         $0.000737
GENERATION COST:       $0.050 (2 images)
GRAND TOTAL:           $0.050737
```

### Scenario 5: FAST Tier (Non-Typography - Photorealism)
```
Gemini Prompt Engine:  8,400 tokens ($0.000127)
Generation (Flux 2 Pro): N/A
Quality Critic:        0 tokens
──────────────────────────────────────────────────
TOTAL TOKENS:          ~8,400 tokens
TOTAL AI COST:         $0.000127
GENERATION COST:       $0.025
GRAND TOTAL:           $0.025127
```

### Scenario 6: PREMIUM Tier (Non-Typography - Photorealism)
```
Gemini Prompt Engine:  8,400 tokens ($0.000127)
Generation (Flux 2 Pro): N/A
Quality Critic:        18,800 tokens ($0.000282)
──────────────────────────────────────────────────
TOTAL TOKENS:          ~27,200 tokens
TOTAL AI COST:         $0.000409
GENERATION COST:       $0.025
GRAND TOTAL:           $0.025409
```

---

## Cost Comparison: OLD vs NEW (Typography)

### OLD SYSTEM (Hardcoded Ideogram v3)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Ideogram): N/A
Quality Critic:        18,800 tokens ($0.000282)
──────────────────────────────────────────────────
TOTAL AI COST:         $0.000737
GENERATION COST:       $0.090 (Ideogram Quality)
GRAND TOTAL:           $0.090737 per image
```

### NEW SYSTEM (Flux 2 Pro Config)
```
Agent Chain:           30,200 tokens ($0.000455)
Generation (Flux 2 Pro): N/A
Quality Critic:        18,800 tokens ($0.000282)
──────────────────────────────────────────────────
TOTAL AI COST:         $0.000737
GENERATION COST:       $0.025 (Flux 2 Pro)
GRAND TOTAL:           $0.025737 per image
```

### **SAVINGS: 72% cost reduction** ($0.090737 → $0.025737)
- Per 1,000 images: **$65,000 saved**
- Per 10,000 images: **$650,000 saved**

---

## Token Range Summary

| Tier | Bucket | Min Tokens | Max Tokens | Avg Tokens | AI Cost Range |
|------|--------|------------|------------|------------|---------------|
| FAST | Typography | 30,000 | 31,000 | ~30,200 | $0.000455 |
| FAST | Photo | 8,000 | 9,000 | ~8,400 | $0.000127 |
| STANDARD | Typography | 30,000 | 31,000 | ~30,200 | $0.000455 |
| STANDARD | Photo | 8,000 | 9,000 | ~8,400 | $0.000127 |
| PREMIUM | Typography | 48,000 | 50,000 | ~49,000 | $0.000737 |
| PREMIUM | Photo | 26,000 | 28,000 | ~27,200 | $0.000409 |
| ULTRA | Typography | 48,000 | 50,000 | ~49,000 | $0.000737 |
| ULTRA | Photo | 26,000 | 28,000 | ~27,200 | $0.000409 |

---

## Pricing Reference (April 2026)

### Gemini 2.5 Flash Pricing
- **Input**: $0.00001 per 1K tokens ($0.01 per 1M)
- **Output**: $0.00003 per 1K tokens ($0.03 per 1M)
- **Blended average**: ~$0.000015 per 1K tokens (mixed input/output)

### Image Generation Models
| Model | Cost/Image (1024×1024) | Use Case |
|-------|------------------------|----------|
| Flux 2 Pro | $0.025 | **Current typography model** (was Ideogram) |
| Flux 2 Dev | $0.015 | Budget alternative |
| Flux 2 Schnell | $0.003 | FAST tier draft |
| Ideogram v3 Quality | $0.090 | **OLD typography model** (3.6× more expensive) |
| Ideogram v3 Turbo | $0.030 | Faster but lower quality |
| Google Imagen 3 | $0.020 | Enterprise alternative |

---

## Key Insights

1. **Agent Chain Dominates Token Usage** (Typography):
   - 6 agents = ~30,200 tokens
   - Simple prompt engine = ~8,400 tokens
   - Typography bucket uses **3.6× more tokens** than photo bucket

2. **Quality Critic is Expensive** (PREMIUM/ULTRA):
   - 6-batch dimension scoring = ~15,000 tokens
   - Beast gates validation = ~3,800 tokens
   - Adds **62% more tokens** to PREMIUM generations

3. **Gemini AI Cost is Negligible**:
   - Even PREMIUM typography with quality critic = **$0.000737** (AI only)
   - Image generation cost dominates: **$0.025 (Flux) vs $0.000737 (AI)**
   - AI prompting is only **2.9% of total cost**

4. **Generation Model is the Real Cost Driver**:
   - Flux 2 Pro: $0.025
   - Ideogram Quality: $0.090 (**3.6× more expensive**)
   - Switching to Flux saves **$0.065 per image** (72% reduction)

5. **Char Guard Adds Minimal Cost**:
   - Only fires when text exceeds platform limits (~20% of cases)
   - ~1,000 tokens when triggered
   - Cost: $0.000015 (negligible)

6. **Beast Copy Writer** (if using):
   - Writer A (12 headlines): ~2,500 tokens
   - Writer B (platform precision): ~2,000 tokens
   - Total: ~4,500 tokens ($0.000068)
   - Currently NOT in active pipeline

---

## Optimization Opportunities

### 🟢 Already Optimized
- ✅ Using Gemini 2.5 Flash (cheapest capable model)
- ✅ Round-robin across 3 API keys (3× rate limit)
- ✅ Switched from Ideogram ($0.09) to Flux 2 Pro ($0.025) — 72% savings

### 🟡 Minor Optimizations Possible
- Reduce Creative Director max_tokens from 4,000 → 3,000 (bible doesn't need 4k)
- Reduce Image Prompter from 3,500 → 2,500 (prompts typically 80-120 words)
- Conditional Quality Critic — only run if user requests "premium quality"

### 🔴 NOT Recommended
- ❌ Don't reduce agent intelligence to save $0.0003 per image
- ❌ Don't skip Quality Critic on PREMIUM — it's the value proposition
- ❌ Don't switch to Haiku — quality drop not worth $0.0001 savings

---

## Monthly Cost Projection (10,000 Images)

### PREMIUM Typography (Current Stack)
```
AI Prompting:     10,000 × $0.000737 = $7.37
Generation:       10,000 × $0.025    = $250.00
────────────────────────────────────────────
TOTAL:            $257.37/month
```

### OLD System (Ideogram)
```
AI Prompting:     10,000 × $0.000737 = $7.37
Generation:       10,000 × $0.090    = $900.00
────────────────────────────────────────────
TOTAL:            $907.37/month
```

### **Monthly Savings: $650** (72% reduction on 10K images)
