# Agent & Prompt Token Usage (Image Generation Excluded)

## Pure AI/Agent Token Usage Per Image

### Typography Bucket (6-Agent Chain)

| Scenario | Components | Min Tokens | Max Tokens | Avg Tokens | AI Cost |
|----------|-----------|------------|------------|------------|---------|
| **FAST** | Agent chain only | 28,000 | 32,000 | ~30,200 | $0.000455 |
| **STANDARD** | Agent chain only | 28,000 | 32,000 | ~30,200 | $0.000455 |
| **PREMIUM** | Agent chain + Quality Critic | 46,000 | 52,000 | ~49,000 | $0.000737 |
| **ULTRA** | Agent chain + Quality Critic | 46,000 | 52,000 | ~49,000 | $0.000737 |

### Non-Typography Bucket (Gemini Prompt Engine)

| Scenario | Components | Min Tokens | Max Tokens | Avg Tokens | AI Cost |
|----------|-----------|------------|------------|------------|---------|
| **FAST** | Prompt engine only | 7,500 | 9,500 | ~8,400 | $0.000127 |
| **STANDARD** | Prompt engine only | 7,500 | 9,500 | ~8,400 | $0.000127 |
| **PREMIUM** | Prompt engine + Critic + Quality Critic | 25,000 | 30,000 | ~27,200 | $0.000409 |
| **ULTRA** | Prompt engine + Critic + Quality Critic | 25,000 | 30,000 | ~27,200 | $0.000409 |

---

## Detailed Agent Breakdown (Typography Bucket)

### 6-Agent Chain Token Usage

| Agent | Input Tokens | Output Tokens | Total Tokens | Cost |
|-------|--------------|---------------|--------------|------|
| 1. Triage | 700-900 | 800-1,200 | 1,500-2,100 | $0.000023-$0.000032 |
| 2. Brand Intel | 800-1,000 | 900-1,400 | 1,700-2,400 | $0.000026-$0.000036 |
| 3. Creative Director | 3,000-4,000 | 3,000-5,000 | 6,000-9,000 | $0.000090-$0.000135 |
| 4. Copy Writer | 2,500-3,200 | 2,000-3,800 | 4,500-7,000 | $0.000068-$0.000105 |
| 4b. Char Guard (conditional) | 300-500 | 400-800 | 700-1,300 | $0.000011-$0.000020 |
| 5. Image Prompter | 3,800-4,600 | 2,500-4,500 | 6,300-9,100 | $0.000095-$0.000137 |
| 6. Layout Planner | 1,600-2,000 | 1,800-3,000 | 3,400-5,000 | $0.000051-$0.000075 |
| **TOTAL (without Char Guard)** | **12,400-15,700** | **13,000-19,900** | **25,400-35,600** | **$0.000382-$0.000535** |
| **TOTAL (with Char Guard)** | **12,700-16,200** | **13,400-20,700** | **26,100-36,900** | **$0.000393-$0.000555** |

### Quality Critic Token Usage (PREMIUM/ULTRA only)

| Component | Input Tokens | Output Tokens | Total Tokens | Cost |
|-----------|--------------|---------------|--------------|------|
| Dimension Scoring (6 batches) | 2,500-3,500 | 10,000-16,000 | 12,500-19,500 | $0.000188-$0.000293 |
| Beast Gates Validation | 600-1,000 | 2,000-4,000 | 2,600-5,000 | $0.000039-$0.000075 |
| **TOTAL Quality Critic** | **3,100-4,500** | **12,000-20,000** | **15,100-24,500** | **$0.000227-$0.000368** |

---

## Gemini Prompt Engine Breakdown (Non-Typography)

### Stage A + B Token Usage

| Stage | Input Tokens | Output Tokens | Total Tokens | Cost |
|-------|--------------|---------------|--------------|------|
| Stage A: Brief | 1,000-1,400 | 1,200-1,800 | 2,200-3,200 | $0.000033-$0.000048 |
| Stage B: CDI | 2,200-2,800 | 1,500-2,500 | 3,700-5,300 | $0.000056-$0.000080 |
| Stage B2: Critic (Premium only) | 700-900 | 300-500 | 1,000-1,400 | $0.000015-$0.000021 |
| **TOTAL Prompt Engine** | **3,900-5,100** | **3,000-4,800** | **6,900-9,900** | **$0.000104-$0.000149** |

---

## COMPREHENSIVE MIN → MAX RANGE

### Typography Bucket (Full Stack)

```
MIN (FAST):
├─ Agent Chain:        25,400 tokens ($0.000382)
├─ Quality Critic:     0 tokens (skipped)
└─ TOTAL:              25,400 tokens ($0.000382)

MAX (PREMIUM with Char Guard):
├─ Agent Chain:        36,900 tokens ($0.000555)
├─ Quality Critic:     24,500 tokens ($0.000368)
└─ TOTAL:              61,400 tokens ($0.000923)

TYPICAL (PREMIUM):
├─ Agent Chain:        30,200 tokens ($0.000455)
├─ Quality Critic:     18,800 tokens ($0.000282)
└─ TOTAL:              49,000 tokens ($0.000737)
```

### Non-Typography Bucket (Full Stack)

```
MIN (FAST):
├─ Prompt Engine:      6,900 tokens ($0.000104)
├─ Quality Critic:     0 tokens (skipped)
└─ TOTAL:              6,900 tokens ($0.000104)

MAX (PREMIUM):
├─ Prompt Engine:      9,900 tokens ($0.000149)
├─ Quality Critic:     24,500 tokens ($0.000368)
└─ TOTAL:              34,400 tokens ($0.000517)

TYPICAL (PREMIUM):
├─ Prompt Engine:      8,400 tokens ($0.000127)
├─ Quality Critic:     18,800 tokens ($0.000282)
└─ TOTAL:              27,200 tokens ($0.000409)
```

---

## Final Summary

| Bucket | Tier | **MIN Tokens** | **MAX Tokens** | **Typical** | **AI Cost** |
|--------|------|----------------|----------------|-------------|-------------|
| Typography | FAST | **25,400** | **32,000** | 30,200 | $0.000382-$0.000480 |
| Typography | STANDARD | **25,400** | **32,000** | 30,200 | $0.000382-$0.000480 |
| Typography | PREMIUM | **40,500** | **61,400** | 49,000 | $0.000610-$0.000923 |
| Typography | ULTRA | **40,500** | **61,400** | 49,000 | $0.000610-$0.000923 |
| Photo | FAST | **6,900** | **9,500** | 8,400 | $0.000104-$0.000143 |
| Photo | STANDARD | **6,900** | **9,500** | 8,400 | $0.000104-$0.000143 |
| Photo | PREMIUM | **22,000** | **34,400** | 27,200 | $0.000330-$0.000517 |
| Photo | ULTRA | **22,000** | **34,400** | 27,200 | $0.000330-$0.000517 |

### **Absolute Min → Max Across All Scenarios:**
- **MINIMUM**: 6,900 tokens (Photo FAST) — $0.000104
- **MAXIMUM**: 61,400 tokens (Typography PREMIUM with all agents + char guard + quality critic) — $0.000923

### **Most Common Cases:**
- **Typography PREMIUM**: ~49,000 tokens — $0.000737
- **Photo PREMIUM**: ~27,200 tokens — $0.000409
- **Typography FAST**: ~30,200 tokens — $0.000455
- **Photo FAST**: ~8,400 tokens — $0.000127

---

## Cost Impact Analysis

### Per 1,000 Images (PREMIUM Typography)
```
AI Prompting Cost:  1,000 × $0.000737 = $0.74
                    (Less than 1 dollar for 1,000 images!)
```

### Per 10,000 Images (PREMIUM Typography)
```
AI Prompting Cost:  10,000 × $0.000737 = $7.37
                    (Less than $10 for 10,000 images!)
```

### Key Insight
**AI prompting is essentially FREE compared to image generation costs:**
- Typography PREMIUM AI: $0.000737
- Flux 2 Pro generation: $0.025
- **Generation is 34× more expensive than all AI agents combined!**
