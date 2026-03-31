# Multi-Modal Prompt Understanding

**NEXT-LEVEL prompt understanding that nobody else has.**

The orchestrator now accepts multiple input modalities and intelligently synthesizes them into comprehensive photo generation prompts.

## Features

- ✅ **Text Prompts** - "beach sunset", "like this but different"
- ✅ **Reference Images** - Upload photos for style/composition/lighting extraction
- ✅ **Voice Input** - Speak your prompt, get transcribed and analyzed
- ✅ **Intelligent Synthesis** - Claude combines all inputs into perfect prompts

## Architecture

```
┌─────────────────────────────────────────────┐
│      MULTI-MODAL PROMPT PROCESSING          │
│                                             │
│  Text → Direct processing                   │
│  Image → Claude Vision Analysis             │
│  Voice → Whisper Transcription              │
│                                             │
│  ↓                                          │
│  Claude Synthesis → Comprehensive Prompt    │
│  ↓                                          │
│  Standard Orchestration Pipeline            │
└─────────────────────────────────────────────┘
```

## Usage

### Python API

```python
import modal

orchestrator = modal.Cls.from_name("photogenius-orchestrator", "Orchestrator")

# 1. Text + Reference Image (Most Common)
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="like this but different",
    reference_images=[image_bytes],  # List of image bytes
    mode="REALISM"
)

# 2. Text Only
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="beach sunset",
    mode="REALISM"
)

# 3. Voice Input
with open("voice_prompt.wav", "rb") as f:
    voice_bytes = f.read()

result = orchestrator.orchestrate_multimodal.remote(
    voice_prompt=voice_bytes,
    mode="CREATIVE"
)

# 4. All Modalities Combined
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="professional headshot",
    reference_images=[reference1_bytes, reference2_bytes],
    voice_prompt=voice_bytes,
    mode="REALISM",
    identity_id="user_123",
    num_candidates=4
)
```

### Web API

#### POST `/orchestrate_multimodal_web`

**Request Body:**
```json
{
    "text_prompt": "like this but different",  // Optional
    "reference_images": [                      // Optional, base64 encoded
        "iVBORw0KGgoAAAANS...",
        "iVBORw0KGgoAAAANS..."
    ],
    "voice_prompt": "UklGRiQAAABXQVZF...",    // Optional, base64 encoded audio
    "mode": "REALISM",                         // Optional, default: "REALISM"
    "identity_id": "user_123",                // Optional
    "user_id": "user_456",                    // Optional
    "num_candidates": 4,                       // Optional, default: 4
    "seed": 42                                 // Optional
}
```

**Response:**
```json
{
    "images": [
        {
            "image_base64": "...",
            "seed": 12345,
            "prompt": "...",
            "scores": {...}
        }
    ],
    "parsed_prompt": {
        "subject": "...",
        "action": "...",
        ...
    },
    "execution_plan": {...},
    "rerank_used": false
}
```

## How It Works

### 1. Text Processing
- Direct pass-through to prompt parsing
- Works exactly like standard `orchestrate()`

### 2. Reference Image Analysis
- Uses **Claude Vision** (Sonnet 4) to analyze images
- Extracts:
  - **Composition**: Rule of thirds, framing, camera angle, shot type
  - **Lighting**: Direction, quality, mood, time of day
  - **Color Palette**: Dominant colors, grading, saturation, contrast
  - **Style**: Photography style, aesthetic, mood
  - **Camera Settings**: Implied focal length, aperture, depth of field
  - **Visual Elements**: Main subject, background, foreground details

**Example Analysis:**
```
"Composition: Medium shot, rule of thirds framing, subject positioned 
at left intersection point. Camera angle: eye-level, slight low angle 
for authority. Shot type: portrait orientation.

Lighting: Golden hour backlighting from camera-left, rim lighting on 
subject's right side, soft fill from sky. Warm golden quality, 
suggesting 20 minutes before sunset.

Color palette: Warm orange and gold tones (RGB 255, 200, 100) 
dominant, cool blue shadows (RGB 100, 150, 200). High saturation, 
moderate contrast. Color grading suggests Kodak Portra 400 aesthetic.

Style: Editorial fashion photography, inspired by Peter Lindbergh. 
Mood: Confident, natural, timeless.

Camera settings: Implied 85mm lens, f/2.0 aperture, shallow depth of 
field. Background slightly blurred, subject sharp.

Key visual elements: Professional model in business attire, urban 
background with architectural elements, natural expression, wind 
movement in hair."
```

### 3. Voice Transcription
- Uses **OpenAI Whisper** (base model) for transcription
- Supports: WAV, MP3, M4A, and other common audio formats
- Transcribed text is analyzed alongside other inputs

**Example:**
```
Voice: "I want a professional headshot like the reference photo, 
but with a more modern background and brighter lighting"

→ Transcribed and included in synthesis
```

### 4. Multi-Modal Synthesis
- **Claude Sonnet 4** synthesizes all inputs
- Resolves conflicts intelligently (prioritizes user text intent)
- Creates comprehensive prompt that honors all modalities
- Adds professional photographic detail based on reference images

**Synthesis Process:**
1. Combines all input descriptions
2. Extracts key elements from reference images
3. Resolves conflicts (e.g., if text says "bright" but image is dark)
4. Adds mode-specific enhancements
5. Returns comprehensive professional photography specification

## Use Cases

### 1. "Like This But Different"
```python
# User uploads reference photo + says "like this but different"
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="like this but different",
    reference_images=[reference_photo_bytes],
    mode="REALISM"
)
```

### 2. Style Transfer
```python
# Extract style from reference, apply to new subject
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="professional headshot of me",
    reference_images=[style_reference_bytes],
    mode="FASHION",
    identity_id="user_123"
)
```

### 3. Voice-Only Generation
```python
# Speak your prompt
result = orchestrator.orchestrate_multimodal.remote(
    voice_prompt=voice_recording_bytes,
    mode="CREATIVE"
)
```

### 4. Complex Multi-Modal
```python
# Combine everything for perfect understanding
result = orchestrator.orchestrate_multimodal.remote(
    text_prompt="professional headshot",
    reference_images=[composition_ref, lighting_ref],
    voice_prompt=voice_bytes,
    mode="REALISM",
    identity_id="user_123"
)
```

## Competitive Edge

**This is NEXT-LEVEL prompt understanding that nobody else has:**

1. **Visual Understanding** - Extract style/composition/lighting from reference photos
2. **Voice Input** - Natural language via voice recording
3. **Intelligent Synthesis** - Claude combines all inputs intelligently
4. **Conflict Resolution** - Handles conflicting inputs gracefully
5. **Professional Detail** - Adds photographic expertise automatically

## Requirements

### Required
- Modal account
- Deployed orchestrator service

### Recommended (for best results)
- Anthropic API key (for Claude vision + synthesis)
  ```bash
  modal secret create anthropic ANTHROPIC_API_KEY=sk-ant-...
  ```

### Optional
- Whisper works without API keys (runs locally in Modal)

## Performance

- **Text-only**: ~2-5 seconds (same as standard orchestrate)
- **Text + Image**: ~5-10 seconds (includes vision analysis)
- **Text + Image + Voice**: ~10-15 seconds (includes transcription)
- **All modalities**: ~15-20 seconds (full synthesis)

## Limitations

1. **Reference Images**: 
   - Max recommended: 3 images per request
   - Format: JPEG, PNG (auto-converted)
   - Size: Auto-resized if too large

2. **Voice Input**:
   - Max length: ~60 seconds recommended
   - Formats: WAV, MP3, M4A, OGG
   - Quality: Better quality = better transcription

3. **Claude Availability**:
   - Falls back to text-only if Claude unavailable
   - Image analysis skipped without Claude
   - Synthesis uses simple concatenation fallback

## Troubleshooting

### "No inputs provided"
- At least one of text_prompt, reference_images, or voice_prompt must be provided

### Image analysis fails
- Check Anthropic API key: `modal secret list`
- Verify image format (JPEG/PNG)
- Check image size (not too large)

### Voice transcription fails
- Verify audio format (WAV recommended)
- Check audio quality (clear speech)
- Ensure ffmpeg is installed (handled automatically)

### Synthesis not working
- Check Anthropic API key
- Falls back to text-only if Claude unavailable
- Check logs: `modal app logs photogenius-orchestrator`

## Examples

See `test_multimodal()` in `orchestrator.py` for example usage.

## Future Enhancements

- [ ] Video reference support (extract frames)
- [ ] Real-time voice streaming
- [ ] Multi-image style blending
- [ ] Reference image pose extraction
- [ ] Style transfer from multiple references
