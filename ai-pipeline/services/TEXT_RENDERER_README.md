# Text Renderer Service

Perfect text rendering for generated images. Solves SDXL's biggest weakness (garbled text) with a hybrid approach.

## Architecture

```
┌──────────────────────────────────────────┐
│         TEXT RENDERER                    │
│                                          │
│  1. Generate image without text (SDXL)  │
│  2. Detect text placement (Claude LLM)  │
│  3. Render text (PIL + custom fonts)   │
│  4. Blend naturally                     │
│  5. Style matching (color/shadows)       │
└──────────────────────────────────────────┘
```

## Features

- ✅ **Perfect text rendering** - No garbled characters
- ✅ **Intelligent placement** - Claude analyzes image composition
- ✅ **Multiple font styles** - Sans, serif, display, mono
- ✅ **Style presets** - Minimal, bold, elegant, modern, poster, watermark
- ✅ **Multi-line support** - Use `\n` for line breaks
- ✅ **Effects** - Shadows, strokes, opacity control
- ✅ **Color matching** - Auto-detects optimal text colors

## Quick Start

### Deploy to Modal

```bash
cd ai-pipeline/services
modal deploy text_renderer.py
```

### Basic Usage

```python
import modal

# Get the text renderer
text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")

# Add text to an image
result_bytes = text_renderer.add_text.remote(
    image=image_bytes,  # Bytes from SDXL generation
    text="SUMMER 2026",
    style="bold",  # auto, minimal, bold, elegant, modern, poster, watermark
    placement="center"  # auto, top, center, bottom
)
```

### Integration with Identity Engine

```python
import modal
import io
from PIL import Image

# 1. Generate image with Identity Engine
identity_engine = modal.Cls.from_name("photogenius-identity-engine", "IdentityEngine")
result = identity_engine.generate.remote(
    prompt="professional headshot",
    identity_id="user_123",
    mode="REALISM"
)

# 2. Extract image bytes
image_base64 = result["images"][0]["image_base64"]
image_bytes = base64.b64decode(image_base64)

# 3. Add text
text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
image_with_text = text_renderer.add_text.remote(
    image=image_bytes,
    text="PROFESSIONAL\nHEADSHOT",
    style="bold",
    placement="top"
)

# 4. Save result
with open("output.jpg", "wb") as f:
    f.write(image_with_text)
```

### Integration with Orchestrator

```python
# In orchestrator.py, add text rendering as post-processing step:

from modal import Cls

# After image generation
if add_text_request:
    text_renderer = Cls.from_name("photogenius-text-renderer", "TextRenderer")
    for img_data in result["images"]:
        img_bytes = base64.b64decode(img_data["image_base64"])
        img_with_text = text_renderer.add_text.remote(
            image=img_bytes,
            text=add_text_request["text"],
            style=add_text_request.get("style", "auto"),
            placement=add_text_request.get("placement", "auto")
        )
        img_data["image_base64"] = base64.b64encode(img_with_text).decode()
```

## API Reference

### `add_text()`

Add text to an image with automatic placement detection.

**Parameters:**
- `image` (bytes): Input image as bytes (PNG/JPEG)
- `text` (str): Text to add (supports `\n` for multi-line)
- `style` (str): Style preset - `auto`, `minimal`, `bold`, `elegant`, `modern`, `poster`, `watermark`
- `placement` (str): Placement hint - `auto`, `top`, `center`, `bottom`
- `custom_config` (dict, optional): Override any config values

**Returns:**
- `bytes`: Image with text as JPEG bytes

**Example:**
```python
result = text_renderer.add_text.remote(
    image=image_bytes,
    text="SUMMER 2026\nCollection",
    style="bold",
    placement="center"
)
```

### `add_text_with_config()`

Add text with explicit configuration (no auto-detection).

**Parameters:**
- `image` (bytes): Input image as bytes
- `text` (str): Text to add
- `config` (dict): Full configuration dict

**Config structure:**
```python
{
    "placement": {"x": 0.5, "y": 0.1},  # 0-1 normalized
    "font_style": "sans_bold",  # sans, sans_bold, serif, serif_bold, display, mono
    "font_size_ratio": 0.08,  # Relative to image width (0.02-0.3)
    "text_color": [255, 255, 255],  # RGB
    "stroke_color": [0, 0, 0],  # RGB
    "stroke_width": 2,  # 0-10
    "shadow": True,  # Enable shadow
    "alignment": "center",  # left, center, right
    "opacity": 1.0  # 0-1
}
```

### `add_watermark()`

Add a subtle watermark to an image.

**Parameters:**
- `image` (bytes): Input image as bytes
- `text` (str): Watermark text
- `position` (str): `bottom_right`, `bottom_left`, `center`
- `opacity` (float): Watermark opacity (0-1)

**Example:**
```python
result = text_renderer.add_watermark.remote(
    image=image_bytes,
    text="© PhotoGenius AI",
    position="bottom_right",
    opacity=0.3
)
```

### `analyze_for_text()`

Analyze image and return recommended text configuration (does not modify image).

**Parameters:**
- `image` (bytes): Input image as bytes
- `text` (str): Text that will be added

**Returns:**
- `dict`: Configuration dict with recommended settings

## Style Presets

| Style | Font | Stroke | Shadow | Use Case |
|-------|------|--------|--------|----------|
| `minimal` | Sans | None | No | Subtle branding |
| `bold` | Sans Bold | 3px | Yes | Headlines, posters |
| `elegant` | Serif | 1px | Yes | Luxury branding |
| `modern` | Display | None | Yes | Tech, startups |
| `poster` | Display | 4px | Yes | Event posters |
| `watermark` | Sans | None | No | Copyright notices |

## Font Styles

Available font styles:
- `sans` - Clean sans-serif
- `sans_bold` - Bold sans-serif
- `serif` - Classic serif
- `serif_bold` - Bold serif
- `display` - Large display font
- `mono` - Monospace

## Web Endpoints

After deployment, the service exposes FastAPI endpoints:

### POST `/add_text_web`

Add text to image via web API.

**Request:**
```json
{
    "image_base64": "...",
    "text": "SUMMER 2026",
    "style": "bold",
    "placement": "center"
}
```

**Response:**
```json
{
    "image_base64": "...",
    "text_added": "SUMMER 2026"
}
```

### POST `/add_watermark_web`

Add watermark via web API.

**Request:**
```json
{
    "image_base64": "...",
    "text": "© PhotoGenius",
    "position": "bottom_right",
    "opacity": 0.3
}
```

### GET `/list_text_styles_web`

List available styles and fonts.

## Use Cases

### 1. Social Media Posts
```python
text_renderer.add_text.remote(
    image=image_bytes,
    text="NEW COLLECTION\nNOW AVAILABLE",
    style="modern",
    placement="center"
)
```

### 2. Event Posters
```python
text_renderer.add_text.remote(
    image=image_bytes,
    text="SUMMER FESTIVAL 2026\nJULY 15-17",
    style="poster",
    placement="top"
)
```

### 3. Professional Headshots
```python
text_renderer.add_text.remote(
    image=image_bytes,
    text="JOHN DOE\nSENIOR ENGINEER",
    style="minimal",
    placement="bottom"
)
```

### 4. Watermarks
```python
text_renderer.add_watermark.remote(
    image=image_bytes,
    text="© Your Company",
    position="bottom_right",
    opacity=0.3
)
```

## Testing

Run local tests:

```bash
modal run ai-pipeline/services/text_renderer.py::test_text_renderer
```

This will:
1. Create a test gradient image
2. Add text with different styles
3. Save output images to verify results

## Requirements

- Modal account with Anthropic API key (optional, for intelligent placement)
- T4 GPU (sufficient for text rendering)
- Fonts are automatically installed in Modal image

## Notes

- **Claude Analysis**: Requires `ANTHROPIC_API_KEY` in Modal secrets. Falls back to heuristic analysis if unavailable.
- **Fonts**: Uses system fonts from Debian repositories. Montserrat and Dancing Script may not be available - falls back to similar fonts.
- **Performance**: ~1-2 seconds per image on T4 GPU.
- **Quality**: JPEG output at 95% quality for optimal size/quality balance.

## Troubleshooting

### Fonts not loading
- Check Modal logs: `modal app logs photogenius-text-renderer`
- Fonts fall back to PIL default if system fonts unavailable

### Claude analysis failing
- Check Anthropic API key: `modal secret list`
- Service falls back to heuristic analysis automatically

### Text placement not optimal
- Use `custom_config` to override placement
- Try different `placement` hints (top, center, bottom)
- Use `analyze_for_text()` to preview recommended config
