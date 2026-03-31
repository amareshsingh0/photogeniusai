# Refinement Engine - Iterative Image Improvement

**Chat-based refinement: "make it brighter", "change background", "more smile"**

Enables users to iteratively refine generated images through natural language requests. The system understands context from generation history and applies appropriate changes using img2img.

## Features

- ✅ **Natural Language Refinement** - "make it brighter", "change background to beach"
- ✅ **Context-Aware** - Uses generation history for better understanding
- ✅ **Multiple Refinement Types** - Lighting, color, composition, expression, background, style, details
- ✅ **Adjustable Strength** - Subtle (0.2) to significant (0.7) changes
- ✅ **Iterative Chain** - Multiple refinements in sequence
- ✅ **Claude Analysis** - Intelligent understanding of refinement requests

## Architecture

```
┌─────────────────────────────────────────────┐
│      REFINEMENT ENGINE                      │
│                                             │
│  1. User: "make it brighter"               │
│  2. Claude: Analyzes request                │
│  3. img2img: Refines image                  │
│  4. History: Maintains context              │
│                                             │
└─────────────────────────────────────────────┘
```

## Quick Start

### Deploy to Modal

```bash
cd ai-pipeline/services
modal deploy refinement_engine.py
```

### Basic Usage

```python
import modal

# Get refinement engine
refinement = modal.Cls.from_name("photogenius-refinement-engine", "RefinementEngine")

# Refine an image
result = refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="make it brighter",
    generation_history=[
        {"prompt": "professional headshot, office background"}
    ],
    mode="REALISM"
)

# Refined image is in result["image_base64"]
```

## Usage Flow

### 1. Initial Generation

```python
# Generate initial image
orchestrator = modal.Cls.from_name("photogenius-orchestrator", "Orchestrator")
result = orchestrator.orchestrate.remote(
    user_prompt="professional headshot",
    mode="REALISM",
    identity_id="user_123"
)

# Extract image and build history
image_bytes = base64.b64decode(result["images"][0]["image_base64"])
history = [{"prompt": result["parsed_prompt"]["full_prompt"]}]
```

### 2. First Refinement

```python
refinement = modal.Cls.from_name("photogenius-refinement-engine", "RefinementEngine")

refined1 = refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="make it brighter",
    generation_history=history,
    mode="REALISM"
)

# Update history
history.append({
    "request": "make it brighter",
    "result": refined1
})
```

### 3. Second Refinement

```python
# Refine again with updated history
refined2 = refinement.refine.remote(
    original_image=refined1["image_bytes"],
    refinement_request="change background to beach",
    generation_history=history,
    mode="REALISM"
)

history.append({
    "request": "change background to beach",
    "result": refined2
})
```

### 4. Batch Refinement

```python
# Apply multiple refinements in sequence
results = refinement.refine_batch.remote(
    original_image=image_bytes,
    refinement_requests=[
        "make it brighter",
        "change background to beach",
        "more smile"
    ],
    generation_history=history,
    mode="REALISM"
)
```

## API Reference

### `refine()`

Refine a single image based on natural language request.

**Parameters:**
- `original_image` (bytes): Original image as bytes (JPEG/PNG)
- `refinement_request` (str): Natural language request
- `generation_history` (List[Dict]): Generation/refinement history
- `mode` (str): Generation mode (default: "REALISM")
- `seed` (int, optional): Random seed for reproducibility

**Returns:**
```python
{
    "image_base64": "...",
    "image_bytes": b"...",
    "change_description": "increase brightness and warmth",
    "strength_used": 0.4,
    "prompt_used": "refined prompt",
    "negative_prompt_used": "negative prompt",
    "aspect": "lighting",
    "guidance_scale": 7.5,
    "num_inference_steps": 30
}
```

### `refine_batch()`

Apply multiple refinements in sequence.

**Parameters:**
- `original_image` (bytes): Original image
- `refinement_requests` (List[str]): List of refinement requests
- `generation_history` (List[Dict]): Generation history
- `mode` (str): Generation mode

**Returns:**
- List of refinement results (one per request)

## Refinement Types

The engine supports these refinement aspects:

| Aspect | Keywords | Default Strength |
|--------|----------|------------------|
| **Lighting** | bright, dark, light, shadow, glow | 0.4 |
| **Color** | warm, cool, saturated, vibrant, tone | 0.35 |
| **Composition** | crop, zoom, angle, framing, position | 0.5 |
| **Expression** | smile, serious, emotion, mood | 0.45 |
| **Background** | background, backdrop, scene, setting | 0.6 |
| **Style** | style, aesthetic, look, feel, vibe | 0.5 |
| **Details** | sharp, blur, detail, texture, quality | 0.3 |

## Example Requests

### Lighting
- "make it brighter"
- "add more light"
- "darker mood"
- "golden hour lighting"

### Color
- "warmer colors"
- "more vibrant"
- "cooler tones"
- "desaturate a bit"

### Background
- "change background to beach"
- "office background"
- "blur the background"
- "remove background"

### Expression
- "more smile"
- "serious expression"
- "happier"
- "neutral expression"

### Composition
- "zoom in a bit"
- "move subject to the right"
- "wider shot"
- "closer crop"

## Web Endpoints

### POST `/refine_web`

Refine image via web API.

**Request:**
```json
{
    "image_base64": "...",
    "refinement_request": "make it brighter",
    "generation_history": [
        {"prompt": "original prompt"},
        {"request": "previous request", "result": {...}}
    ],
    "mode": "REALISM",
    "seed": 42
}
```

**Response:**
```json
{
    "image_base64": "...",
    "change_description": "increase brightness and warmth",
    "strength_used": 0.4,
    "prompt_used": "...",
    "aspect": "lighting"
}
```

### POST `/refine_batch_web`

Apply multiple refinements in sequence.

**Request:**
```json
{
    "image_base64": "...",
    "refinement_requests": ["make it brighter", "change background"],
    "generation_history": [...],
    "mode": "REALISM"
}
```

## Frontend Integration

### React Component

See `apps/web/components/generate/refinement-chat.tsx` for a complete React component.

**Usage:**
```tsx
import { RefinementChat } from "@/components/generate/refinement-chat"

<RefinementChat
  initialImage={generatedImageUrl}
  initialPrompt={generatedPrompt}
  mode="REALISM"
  onRefined={(refinedImage, history) => {
    console.log("Image refined:", refinedImage)
  }}
/>
```

### API Route Example

Create `apps/web/app/api/refine/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Call Modal refinement endpoint
    const response = await fetch(
      "https://YOUR_MODAL_URL--refine-web.modal.run",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    )
    
    if (!response.ok) {
      throw new Error("Refinement failed")
    }
    
    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Refinement failed" },
      { status: 500 }
    )
  }
}
```

## How It Works

### 1. Request Analysis

Claude analyzes the refinement request:
- Determines aspect (lighting, color, etc.)
- Calculates strength (0.2-0.7)
- Extracts prompt modifications

**Example:**
```
Request: "make it brighter"
→ Aspect: lighting
→ Strength: 0.4
→ Add: ["brighter lighting", "well-lit"]
→ Remove: ["dark", "dim"]
```

### 2. Prompt Building

Original prompt + modifications:
```
Original: "professional headshot, office background"
Refined: "professional headshot, office background, brighter lighting, well-lit"
Negative: "dark, dim, low light, low quality, blurry"
```

### 3. Image Refinement

img2img pipeline:
- Loads original image
- Applies refinement with calculated strength
- Generates refined version

### 4. History Management

Maintains context:
```python
history = [
    {"prompt": "original prompt"},
    {"request": "make it brighter", "result": {...}},
    {"request": "change background", "result": {...}}
]
```

## Performance

- **Single refinement**: ~5-10 seconds (A10G GPU)
- **Batch refinement**: ~15-30 seconds (3 refinements)
- **Warm containers**: 2 containers kept warm for faster response

## Requirements

### Required
- Modal account
- Deployed refinement engine
- A10G GPU (or compatible)

### Recommended
- Anthropic API key (for intelligent analysis)
  ```bash
  modal secret create anthropic ANTHROPIC_API_KEY=sk-ant-...
  ```
- HuggingFace token (for model access)
  ```bash
  modal secret create huggingface HUGGINGFACE_TOKEN=hf_...
  ```

## Limitations

1. **Image Size**: Auto-resized to 1024x1024 (maintains aspect ratio)
2. **Refinement Strength**: Limited to 0.2-0.7 (prevents complete image replacement)
3. **History Length**: Recommended max 10 refinements (context window)
4. **Claude Availability**: Falls back to heuristic analysis if unavailable

## Troubleshooting

### "Refinement pipeline not loaded"
- Check GPU availability
- Verify model download completed
- Check Modal logs: `modal app logs photogenius-refinement-engine`

### Refinement too subtle/strong
- Adjust strength manually (not exposed in API, modify code)
- Use more specific requests ("much brighter" vs "brighter")

### Claude analysis fails
- Check Anthropic API key: `modal secret list`
- Falls back to heuristic analysis automatically
- Check logs for specific error

### Image quality degrades
- Reduce refinement strength
- Limit number of refinements (3-5 recommended)
- Use higher quality original image

## Best Practices

1. **Start with subtle changes** - Build up gradually
2. **Be specific** - "make it brighter" > "change it"
3. **Use history** - System learns from previous refinements
4. **Limit iterations** - 3-5 refinements recommended
5. **Save originals** - Keep original image for reset

## Use Cases

### 1. Lighting Adjustments
```python
refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="add golden hour lighting",
    generation_history=history
)
```

### 2. Background Changes
```python
refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="change background to modern office",
    generation_history=history
)
```

### 3. Expression Tweaks
```python
refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="more natural smile",
    generation_history=history
)
```

### 4. Style Refinement
```python
refinement.refine.remote(
    original_image=image_bytes,
    refinement_request="more professional look",
    generation_history=history
)
```

## Future Enhancements

- [ ] Inpainting support (refine specific regions)
- [ ] Face-specific refinements (smile, expression)
- [ ] Style transfer refinements
- [ ] Real-time preview
- [ ] Undo/redo functionality
