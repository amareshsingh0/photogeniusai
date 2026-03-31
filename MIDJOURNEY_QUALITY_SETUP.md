# 🎨 Midjourney-Quality Setup

## Getting Midjourney-like results on current ml.g5.2xlarge

---

## Current Setup

**GPU**: ml.g5.2xlarge (24GB, $1.21/hr)
**Strategy**: Memory-optimized handler with maximum quality settings

---

## Key Optimizations for Midjourney Quality

### 1. **Two-Pass Generation** (Base + Refiner)
```json
{
  "quality_tier": "PREMIUM",
  "prompt": "your prompt here"
}
```
- PREMIUM tier uses SDXL Base (30 steps) + Refiner (20 steps)
- Total 50 steps = professional quality
- Refiner adds fine details like Midjourney

### 2. **High-Quality Prompts** (Midjourney-style)

**Before** (basic):
```
"a woman on beach"
```

**After** (Midjourney-style):
```
"professional photography of an elegant woman on beach at golden hour,
cinematic lighting, dreamy atmosphere, shallow depth of field,
beautiful bokeh, sunset warm tones, RAW photo, 8k uhd, highly detailed,
sharp focus, photorealistic, masterpiece, best quality"
```

**Prompt Template**:
```
[subject] + [style keywords] + [lighting] + [quality boosters] + [technical specs]
```

### 3. **Comprehensive Negative Prompts**

```json
{
  "negative_prompt": "ugly, tiling, poorly drawn hands, poorly drawn feet,
  poorly drawn face, out of frame, mutation, mutated, extra limbs,
  disfigured, deformed, blurry, bad art, bad anatomy, worst quality,
  low quality, jpeg artifacts, signature, watermark, text,
  semi-realistic, cgi, 3d, render, sketch, cartoon, drawing, anime"
}
```

### 4. **Optimal Parameters**

```json
{
  "quality_tier": "PREMIUM",
  "width": 1024,
  "height": 1024,
  "guidance_scale": 7.5,
  "num_inference_steps": 50  // Handled by PREMIUM tier
}
```

---

## Midjourney-Style Prompt Examples

### Portrait
```
cinematic portrait of a beautiful woman with flowing hair,
golden hour lighting, professional photography, shallow depth of field,
beautiful bokeh, warm tones, highly detailed face, natural skin texture,
RAW photo, 8k uhd, sharp focus, photorealistic, masterpiece
```

### Landscape
```
breathtaking mountain landscape at sunset, dramatic clouds,
golden hour lighting, sweeping composition, rich depth of field,
vibrant natural colors, atmospheric perspective, cinematic framing,
professional photography, RAW photo, 8k uhd, highly detailed, masterpiece
```

### Product
```
professional product photography of luxury watch on marble surface,
studio lighting, clean background, sharp product detail,
attractive color grading, commercial quality, macro photography,
RAW photo, 8k uhd, highly detailed, photorealistic, masterpiece
```

### Romantic
```
romantic couple on beach at sunset, golden hour lighting,
dreamy soft atmosphere, elegant pose, intimate moment, beautiful bokeh,
sunset warm tones, professional romantic photography, cinematic mood,
RAW photo, 8k uhd, highly detailed, sharp focus, photorealistic, masterpiece
```

### Fantasy/Artistic
```
ethereal fantasy portrait in enchanted forest, magical atmosphere,
volumetric lighting, mystical glow, intricate details, dreamy colors,
cinematic composition, artistic masterpiece, highly detailed,
digital art, concept art style, RAW photo quality, 8k uhd
```

---

## Quality Tiers Comparison

### FAST (4 steps, ~3-5s)
- Model: SDXL-Turbo only
- Quality: Good for preview
- ❌ Not Midjourney-quality

### STANDARD (30 steps, ~25s)
- Model: SDXL Base
- Quality: Very good
- ✅ Near Midjourney-quality

### PREMIUM (50 steps, ~40s) ⭐ MIDJOURNEY-QUALITY
- Model: SDXL Base + Refiner
- Quality: Excellent
- ✅✅ **True Midjourney-quality**
- Two-pass: Base generates, Refiner enhances details
- Best for final output

---

## Advanced Features

### Aspect Ratios (like Midjourney)

**Portrait** (9:16):
```json
{"width": 768, "height": 1344}
```

**Landscape** (16:9):
```json
{"width": 1344, "height": 768}
```

**Square** (1:1):
```json
{"width": 1024, "height": 1024}
```

**Cinematic** (2.39:1):
```json
{"width": 1216, "height": 512}
```

### Style Weights (like --stylize in Midjourney)

Adjust `guidance_scale`:
- **Low stylization** (realistic): `guidance_scale: 5.0`
- **Medium** (balanced): `guidance_scale: 7.5` (default)
- **High stylization** (artistic): `guidance_scale: 10.0`

---

## Testing Midjourney-Quality

### Test Script:

```bash
cd "c:\desktop\PhotoGenius AI\aws\sagemaker"
python test_endpoint.py
```

### Expected Results:

**PREMIUM Tier Output**:
- Time: 40-50 seconds
- Steps: 50 (30 Base + 20 Refiner)
- Quality: Professional/Midjourney-like
- Details: Sharp, well-defined
- No artifacts: No extra fingers, blurry faces

**Compare Images**:
1. `test_fast.png` - Preview quality
2. `test_standard.png` - Good quality
3. `test_premium.png` - **Midjourney quality** ⭐

---

## Frontend Integration

Update smart prompt enhancer to add Midjourney-style keywords:

```typescript
// apps/web/lib/smart-prompt.ts

const qualityKeywords = [
  "RAW photo",
  "professional photography",
  "8k uhd",
  "highly detailed",
  "sharp focus",
  "photorealistic",
  "masterpiece",
  "best quality",
  "cinematic",
  "dramatic lighting"
];

// Auto-enhance user prompts
function enhancePrompt(userPrompt: string, mode: string): string {
  let enhanced = userPrompt;

  // Add quality keywords
  enhanced += ", " + qualityKeywords.join(", ");

  // Add mode-specific keywords
  if (mode === "ROMANTIC") {
    enhanced += ", golden hour lighting, dreamy atmosphere, beautiful bokeh";
  } else if (mode === "CINEMATIC") {
    enhanced += ", dramatic composition, volumetric lighting, film grain";
  }

  return enhanced;
}
```

---

## Cost Comparison

### Current Setup (ml.g5.2xlarge)
- Cost: **$1.21/hour**
- PREMIUM generation: ~40s = **$0.0134 per image**
- 1000 images: **$13.40**
- ✅ Cost-effective

### vs Midjourney
- Basic plan: **$10/month** (200 images)
- = **$0.05 per image**
- Standard plan: **$30/month** (unlimited, 15hr GPU)

### PhotoGenius Advantage
- No monthly limit
- Full control over models
- Can fine-tune for your style
- API access for automation

---

## Tips for Best Quality

### 1. **Use PREMIUM Tier Always**
```json
{"quality_tier": "PREMIUM"}
```

### 2. **Detailed Prompts**
- Be specific about subject
- Add lighting details
- Specify style/mood
- Include quality keywords

### 3. **Strong Negative Prompts**
- List unwanted elements
- Add common artifacts
- Specify style to avoid

### 4. **Optimal Resolution**
- 1024x1024 for best quality
- Higher res uses more memory
- Stay within 1024-1344 range

### 5. **Patience**
- PREMIUM takes ~40s
- Quality worth the wait
- Don't use FAST for final output

---

## Troubleshooting

### Issue: Images still look AI-generated

**Fix**:
1. Use PREMIUM tier (not FAST)
2. Add more quality keywords
3. Strengthen negative prompts
4. Increase guidance_scale to 8.0-8.5

### Issue: Blurry or low detail

**Fix**:
1. Ensure using PREMIUM (50 steps)
2. Add "sharp focus, highly detailed, 8k uhd"
3. Check resolution (1024x1024 minimum)

### Issue: Wrong colors/lighting

**Fix**:
1. Specify lighting in prompt
2. Add color keywords ("warm tones", "vibrant colors")
3. Try different guidance_scale (7.0-9.0)

### Issue: Anatomical errors (extra fingers, etc.)

**Fix**:
1. Add to negative prompt: "poorly drawn hands, extra fingers, mutated hands"
2. Use "professional photography, RAW photo" in prompt
3. Increase inference steps (PREMIUM tier)

---

## Example API Call

```python
import boto3
import json
import base64

runtime = boto3.client("sagemaker-runtime", region_name="us-east-1")

payload = {
    "inputs": "cinematic portrait of elegant woman, golden hour lighting, professional photography, RAW photo, 8k uhd, highly detailed, masterpiece",
    "quality_tier": "PREMIUM",
    "parameters": {
        "width": 1024,
        "height": 1024,
        "negative_prompt": "ugly, blurry, low quality, distorted, deformed, bad anatomy, poorly drawn, cartoon, anime, extra limbs, worst quality",
    }
}

response = runtime.invoke_endpoint(
    EndpointName="photogenius-generation-dev",
    ContentType="application/json",
    Body=json.dumps(payload),
)

result = json.loads(response["Body"].read())
image_b64 = result["image_base64"]

# Save image
with open("midjourney_quality.png", "wb") as f:
    f.write(base64.b64decode(image_b64))

print("✓ Midjourney-quality image saved!")
```

---

## Quota Increase (For Future)

Agar larger GPU chahiye:

```bash
# Request quota increase
aws service-quotas request-service-quota-increase \
  --service-code sagemaker \
  --quota-code L-5B9F4C3E \
  --desired-value 1 \
  --region us-east-1

# For ml.g5.12xlarge (96GB GPU)
# Approval takes 24-48 hours
```

---

## Summary

### Current Capabilities:
- ✅ Midjourney-quality achievable on ml.g5.2xlarge
- ✅ PREMIUM tier = 50 steps (Base + Refiner)
- ✅ Memory-optimized handler (loads models sequentially)
- ✅ Cost-effective ($1.21/hr = $0.0134 per image)

### Quality Factors:
1. **PREMIUM tier** (mandatory)
2. **Detailed prompts** (Midjourney-style)
3. **Strong negative prompts**
4. **Optimal parameters** (50 steps, guidance 7.5)

### Result:
**Professional, Midjourney-like image quality** without expensive hardware!

---

**Test karo aur compare karo Midjourney se!** 🎨
