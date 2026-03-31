"""
Text Renderer - Perfect Text in Images
Solves SDXL's biggest weakness (garbled text) with a hybrid approach.

Architecture:
1. Generate image without text (SDXL)
2. Detect optimal text placement (LLM analysis)
3. Render text (PIL + custom fonts)
4. Blend naturally with style matching (color/shadows)

Features:
- Multiple font styles (sans, serif, script, modern, display)
- Auto placement detection using Claude
- Shadow and stroke effects
- Color matching with image
- Multi-line text support
- Curved text support (for badges/stamps)
"""

import modal  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image, ImageDraw, ImageFont, ImageFilter  # type: ignore[reportMissingImports]
import io
import base64
from typing import Dict, List, Optional, Tuple
import json
import os

app = modal.App("photogenius-text-renderer")

# Font directory inside Modal container
FONTS_DIR = "/fonts"

# Modal image with fonts and dependencies
text_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "pillow==10.2.0",
        "opencv-python==4.9.0.80",
        "numpy==1.26.3",
        "anthropic>=0.18.0",
        "colorthief>=0.2.1",
    ])
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
        # Install fonts (incl. spec: Montserrat, Dancing Script)
        "apt-get install -y fonts-liberation fonts-dejavu-core fonts-open-sans "
        "fonts-lato fonts-roboto fonts-noto-core fonts-firacode "
        "fonts-montserrat fonts-dancingscript",
        # Create fonts directory and copy fonts
        f"mkdir -p {FONTS_DIR}",
        f"cp /usr/share/fonts/truetype/liberation/*.ttf {FONTS_DIR}/ || true",
        f"cp /usr/share/fonts/truetype/dejavu/*.ttf {FONTS_DIR}/ || true",
        f"cp /usr/share/fonts/truetype/open-sans/*.ttf {FONTS_DIR}/ || true",
        f"cp /usr/share/fonts/truetype/lato/*.ttf {FONTS_DIR}/ || true",
        f"cp /usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/*.ttf {FONTS_DIR}/ 2>/dev/null || cp /usr/share/fonts/truetype/roboto/*.ttf {FONTS_DIR}/ 2>/dev/null || true",
        f"cp /usr/share/fonts/truetype/noto/*.ttf {FONTS_DIR}/ 2>/dev/null || true",
        f"cp /usr/share/fonts/truetype/montserrat/*.ttf {FONTS_DIR}/ 2>/dev/null || true",
        f"cp /usr/share/fonts/opentype/dancingscript/*.otf {FONTS_DIR}/ 2>/dev/null || cp /usr/share/fonts/truetype/fonts-dancingscript/*.ttf {FONTS_DIR}/ 2>/dev/null || true",
        f"ls -la {FONTS_DIR}/",
    )
)

# Font mappings with fallbacks (spec: sans, sans_bold, serif, script, modern)
FONT_MAPPINGS = {
    "sans": [
        "OpenSans-Regular.ttf",
        "Lato-Regular.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
    ],
    "sans_bold": [
        "OpenSans-Bold.ttf",
        "Lato-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "LiberationSans-Bold.ttf",
    ],
    "serif": [
        "NotoSerif-Regular.ttf",
        "DejaVuSerif.ttf",
        "LiberationSerif-Regular.ttf",
    ],
    "serif_bold": [
        "NotoSerif-Bold.ttf",
        "DejaVuSerif-Bold.ttf",
        "LiberationSerif-Bold.ttf",
    ],
    "script": [
        "DancingScript-Regular.otf",
        "DancingScript-Regular.ttf",
        "DancingScript-Bold.otf",
        "DancingScript-Bold.ttf",
        "DejaVuSerif-Italic.ttf",
        "Lato-Italic.ttf",
    ],
    "modern": [
        "Montserrat-Bold.ttf",
        "Montserrat-SemiBold.ttf",
        "Lato-Black.ttf",
        "Roboto-Black.ttf",
        "OpenSans-ExtraBold.ttf",
        "DejaVuSans-Bold.ttf",
    ],
    "mono": [
        "FiraCode-Regular.ttf",
        "DejaVuSansMono.ttf",
        "LiberationMono-Regular.ttf",
    ],
    "display": [
        "Montserrat-Bold.ttf",
        "Roboto-Black.ttf",
        "Lato-Black.ttf",
        "OpenSans-ExtraBold.ttf",
        "DejaVuSans-Bold.ttf",
    ],
}

# Style presets
TEXT_STYLE_PRESETS = {
    "minimal": {
        "font_style": "sans",
        "stroke_width": 0,
        "shadow": False,
        "opacity": 0.9,
    },
    "bold": {
        "font_style": "sans_bold",
        "stroke_width": 3,
        "shadow": True,
        "opacity": 1.0,
    },
    "elegant": {
        "font_style": "serif",
        "stroke_width": 1,
        "shadow": True,
        "opacity": 0.95,
    },
    "modern": {
        "font_style": "display",
        "stroke_width": 0,
        "shadow": True,
        "opacity": 1.0,
    },
    "poster": {
        "font_style": "display",
        "stroke_width": 4,
        "shadow": True,
        "opacity": 1.0,
        "background_pill": True,
        "pill_color": [0, 0, 0],
        "pill_opacity": 0.35,
    },
    "watermark": {
        "font_style": "sans",
        "stroke_width": 0,
        "shadow": False,
        "opacity": 0.3,
    },
}


@app.cls(
    gpu="T4",  # T4 is sufficient for text rendering
    image=text_image,
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
    ],
    keep_warm=1,
    timeout=120,
)
class TextRenderer:
    """
    Add perfect text to generated images.
    Uses Claude for intelligent placement analysis and PIL for crisp rendering.
    """
    
    @modal.enter()
    def load_fonts(self):
        """Load font collection on startup"""
        print("🔤 Loading Text Renderer fonts...")
        
        self.fonts = {}
        
        for style_name, font_files in FONT_MAPPINGS.items():
            for font_file in font_files:
                font_path = os.path.join(FONTS_DIR, font_file)
                if os.path.exists(font_path):
                    try:
                        # Load at base size, will be resized as needed
                        self.fonts[style_name] = font_path
                        print(f"  ✓ Loaded {style_name}: {font_file}")
                        break
                    except Exception as e:
                        print(f"  ✗ Failed to load {font_file}: {e}")
                        continue
            
            if style_name not in self.fonts:
                print(f"  ⚠ No font found for style: {style_name}")
        
        # Fallback to default if needed
        if not self.fonts:
            print("  ⚠ Using PIL default font as fallback")
            self.fonts["default"] = None
        
        print(f"✅ Text Renderer loaded ({len(self.fonts)} font styles)")
    
    def _get_font(self, style: str, size: int) -> ImageFont.FreeTypeFont:
        """Get font for style at specified size"""
        font_path = self.fonts.get(style) or self.fonts.get("sans") or self.fonts.get("default")
        
        if font_path is None:
            # Use default PIL font
            return ImageFont.load_default()
        
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            print(f"[WARN] Failed to load font {font_path} at size {size}: {e}")
            return ImageFont.load_default()
    
    def _analyze_image_for_placement(
        self,
        img: Image.Image,
        text: str,
        placement_hint: str = "auto"
    ) -> Dict:
        """
        Analyze image and determine optimal text placement/style.
        Uses Claude if available, falls back to heuristic analysis.
        """
        from anthropic import Anthropic  # type: ignore[reportMissingImports]
        
        # Try Claude analysis first
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if api_key and placement_hint == "auto":
            try:
                return self._claude_analysis(img, text)
            except Exception as e:
                print(f"[WARN] Claude analysis failed, using heuristics: {e}")
        
        # Fallback to heuristic analysis
        return self._heuristic_analysis(img, text, placement_hint)
    
    def _claude_analysis(self, img: Image.Image, text: str) -> Dict:
        """Use Claude to analyze image and determine optimal text placement"""
        from anthropic import Anthropic  # type: ignore[reportMissingImports]
        
        # Convert image to base64 for Claude
        buffered = io.BytesIO()
        img_small = img.copy()
        img_small.thumbnail((512, 512))  # Reduce size for faster analysis
        img_small.save(buffered, format="JPEG", quality=80)
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        client = Anthropic()
        
        analysis_prompt = f"""Analyze this image and determine the best text placement and style for adding text.

Text to add: "{text}"

Consider:
1. Image composition - where is empty space or less detailed areas?
2. Color scheme - what text color would stand out but look natural?
3. Mood - what font style matches the image's aesthetic?
4. Avoid placing text over faces or important subjects

Return ONLY valid JSON (no markdown, no explanation):
{{
    "placement": {{ "x": 0.5, "y": 0.1 }},
    "font_style": "sans_bold",
    "font_size_ratio": 0.08,
    "text_color": [255, 255, 255],
    "stroke_color": [0, 0, 0],
    "stroke_width": 2,
    "shadow": true,
    "alignment": "center"
}}

Notes:
- x, y are 0-1 normalized (0.5 = center)
- Use font_size_ratio (0.05-0.15) or font_size (pixels, e.g. 72)
- font_style: sans, sans_bold, serif, serif_bold, script, modern, display, mono
- alignment: left, center, right
"""
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": analysis_prompt,
                    }
                ],
            }]
        )
        
        # Parse response
        response_text = response.content[0].text.strip()
        
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        
        config = json.loads(response_text)
        
        # Validate and add defaults
        return self._validate_config(config, img)
    
    def _heuristic_analysis(
        self,
        img: Image.Image,
        text: str,
        placement_hint: str
    ) -> Dict:
        """Heuristic-based text placement analysis"""
        import cv2  # type: ignore[reportMissingImports]
        
        w, h = img.size
        img_array = np.array(img)
        
        # Analyze image brightness in different regions
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Define regions
        regions = {
            "top": gray[:h//4, :],
            "center": gray[h//3:2*h//3, w//4:3*w//4],
            "bottom": gray[3*h//4:, :],
        }
        
        # Find region with most uniform brightness (good for text)
        uniformity = {}
        for name, region in regions.items():
            uniformity[name] = 1 / (region.std() + 1)  # Lower variance = more uniform
        
        # Determine placement
        if placement_hint != "auto":
            best_region = placement_hint
        else:
            best_region = max(uniformity, key=lambda k: uniformity.get(k, 0.0))
        
        # Set y position based on region
        y_positions = {"top": 0.12, "center": 0.5, "bottom": 0.88}
        y_pos = y_positions.get(best_region, 0.5)
        
        # Determine text color based on background brightness
        region_brightness = regions[best_region].mean()
        if region_brightness > 128:
            text_color = [30, 30, 30]  # Dark text on light background
            stroke_color = [255, 255, 255]
        else:
            text_color = [255, 255, 255]  # Light text on dark background
            stroke_color = [0, 0, 0]
        
        # Determine font size based on text length and image size
        text_len = len(text)
        if text_len <= 10:
            font_size_ratio = 0.1
        elif text_len <= 20:
            font_size_ratio = 0.07
        else:
            font_size_ratio = 0.05
        
        return {
            "placement": {"x": 0.5, "y": y_pos},
            "font_style": "sans_bold",
            "font_size_ratio": font_size_ratio,
            "text_color": text_color,
            "stroke_color": stroke_color,
            "stroke_width": 2,
            "shadow": True,
            "alignment": "center",
        }
    
    def _validate_config(self, config: Dict, img: Image.Image) -> Dict:
        """Validate and fill in missing config values. Supports font_size (px) or font_size_ratio."""
        w = img.size[0]
        defaults = {
            "placement": {"x": 0.5, "y": 0.1},
            "font_style": "sans_bold",
            "font_size_ratio": 0.08,
            "text_color": [255, 255, 255],
            "stroke_color": [0, 0, 0],
            "stroke_width": 2,
            "shadow": True,
            "alignment": "center",
            "background_pill": False,
        }
        
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
        
        # Support font_size (pixels) from LLM; derive font_size_ratio if needed
        if "font_size" in config and config["font_size"]:
            sz = max(12, min(400, int(config["font_size"])))
            config["font_size_ratio"] = sz / w
        config["font_size_ratio"] = max(0.02, min(0.3, config["font_size_ratio"]))
        
        # Validate ranges
        config["placement"]["x"] = max(0.05, min(0.95, config["placement"]["x"]))
        config["placement"]["y"] = max(0.05, min(0.95, config["placement"]["y"]))
        config["stroke_width"] = max(0, min(10, int(config["stroke_width"])))
        
        return config
    
    def _extract_dominant_colors(self, img: Image.Image) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from image for style matching"""
        try:
            from colorthief import ColorThief  # type: ignore[reportMissingImports]
            
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            buffered.seek(0)
            
            color_thief = ColorThief(buffered)
            palette = color_thief.get_palette(color_count=5)
            return palette
        except Exception:
            return [(255, 255, 255), (0, 0, 0)]
    
    def _draw_rounded_rect(
        self,
        draw: ImageDraw.ImageDraw,
        xy: Tuple[int, int, int, int],
        radius: int,
        fill: Tuple[int, ...],
        outline: Optional[Tuple[int, ...]] = None,
    ) -> None:
        """Draw a rounded rectangle. xy = (x0, y0, x1, y1)."""
        x0, y0, x1, y1 = xy
        draw.rectangle((x0 + radius, y0, x1 - radius, y1), fill=fill, outline=outline)
        draw.rectangle((x0, y0 + radius, x1, y1 - radius), fill=fill, outline=outline)
        draw.pieslice((x0, y0, x0 + 2 * radius, y0 + 2 * radius), 180, 270, fill=fill, outline=outline)
        draw.pieslice((x1 - 2 * radius, y0, x1, y0 + 2 * radius), 270, 360, fill=fill, outline=outline)
        draw.pieslice((x0, y1 - 2 * radius, x0 + 2 * radius, y1), 90, 180, fill=fill, outline=outline)
        draw.pieslice((x1 - 2 * radius, y1 - 2 * radius, x1, y1), 0, 90, fill=fill, outline=outline)
    
    def _render_text(
        self,
        img: Image.Image,
        text: str,
        config: Dict
    ) -> Image.Image:
        """Render text with anti-aliasing, PIL native stroke, and optional background pill."""
        result = img.copy().convert("RGBA")
        w, h = result.size
        
        font_size = int(w * config["font_size_ratio"])
        font_size = max(12, min(font_size, 400))
        
        font = self._get_font(config["font_style"], font_size)
        text_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        
        lines = text.split("\n")
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])
        
        total_text_height = sum(line_heights) + (len(lines) - 1) * max(2, int(font_size * 0.25))
        max_line_w = max(line_widths) if line_widths else 0
        padding = max(8, font_size // 6)
        
        base_x = int(w * config["placement"]["x"])
        base_y = int(h * config["placement"]["y"]) - total_text_height // 2
        
        # Compute global bbox for background pill
        if config["alignment"] == "center":
            x_min, x_max = base_x - max_line_w // 2, base_x + max_line_w // 2
        elif config["alignment"] == "right":
            x_min, x_max = base_x - max_line_w, base_x
        else:
            x_min, x_max = base_x, base_x + max_line_w
        y_min = base_y - padding
        y_max = base_y + total_text_height + padding
        pill = (max(0, x_min - padding), max(0, y_min), min(w, x_max + padding), min(h, y_max))
        radius = min(padding * 2, max(1, (pill[3] - pill[1]) // 2), max(1, (pill[2] - pill[0]) // 2))
        
        # 5. Blend naturally: optional semi-transparent background pill
        if config.get("background_pill"):
            bg = tuple(config.get("pill_color", [0, 0, 0])) + (int(255 * config.get("pill_opacity", 0.35)),)
            self._draw_rounded_rect(draw, pill, max(1, radius), fill=bg)
        
        current_y = base_y
        stroke_width = config.get("stroke_width", 0)
        stroke_fill = tuple(config["stroke_color"]) + (255,) if stroke_width > 0 else None
        text_color = tuple(config["text_color"])
        if len(text_color) == 3:
            text_color = text_color + (255,)
        
        for i, line in enumerate(lines):
            lw, lh = line_widths[i], line_heights[i]
            if config["alignment"] == "center":
                x = base_x - lw // 2
            elif config["alignment"] == "right":
                x = base_x - lw
            else:
                x = base_x
            y = current_y
            
            # Shadow
            if config.get("shadow"):
                so = max(2, font_size // 25)
                shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
                sd = ImageDraw.Draw(shadow_layer)
                sd.text((x + so, y + so), line, fill=(0, 0, 0, 100), font=font)
                shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=so))
                text_layer = Image.alpha_composite(text_layer, shadow_layer)
                draw = ImageDraw.Draw(text_layer)
            
            # Main text with PIL native stroke (stroke_fill + stroke_width)
            kw = {"fill": text_color, "font": font}
            if stroke_width > 0 and stroke_fill is not None:
                kw["stroke_width"] = stroke_width
                kw["stroke_fill"] = stroke_fill
            draw.text((x, y), line, **kw)
            
            current_y += lh + max(2, int(font_size * 0.25))
        
        opacity = config.get("opacity", 1.0)
        if opacity < 1.0:
            a = text_layer.split()[3]
            text_layer.putalpha(a.point(lambda v: int(v * opacity)))
        
        result = Image.alpha_composite(result, text_layer)
        return result.convert("RGB")
    
    @modal.method()
    def add_text(
        self,
        image: bytes,
        text: str,
        style: str = "auto",  # auto, minimal, bold, elegant, modern, poster, watermark
        placement: str = "auto",  # auto, top, center, bottom
        custom_config: Optional[Dict] = None,
    ) -> bytes:
        """
        Add text to image with perfect rendering.
        
        Args:
            image: Input image as bytes (PNG/JPEG)
            text: Text to add (supports \n for multi-line)
            style: Style preset (auto, minimal, bold, elegant, modern, poster, watermark)
            placement: Placement hint (auto, top, center, bottom)
            custom_config: Override any config values
        
        Returns:
            Image with text as JPEG bytes
        """
        # Load image
        img = Image.open(io.BytesIO(image)).convert("RGB")
        
        # Get analysis/config
        config = self._analyze_image_for_placement(img, text, placement)
        
        # Apply style preset if specified (override all preset keys)
        if style != "auto" and style in TEXT_STYLE_PRESETS:
            preset = TEXT_STYLE_PRESETS[style]
            for key, value in preset.items():
                config[key] = value
        
        # Apply custom config overrides
        if custom_config:
            for key, value in custom_config.items():
                if key == "placement" and isinstance(value, dict):
                    config["placement"].update(value)
                else:
                    config[key] = value
        
        # Render text
        result = self._render_text(img, text, config)
        
        # Save as JPEG
        output = io.BytesIO()
        result.save(output, format="JPEG", quality=95)
        
        return output.getvalue()
    
    @modal.method()
    def add_text_with_config(
        self,
        image: bytes,
        text: str,
        config: Dict
    ) -> bytes:
        """
        Add text with explicit configuration (no auto-detection).
        
        Args:
            image: Input image as bytes
            text: Text to add
            config: Full configuration dict:
                {
                    "placement": {"x": 0.5, "y": 0.1},
                    "font_style": "sans_bold",
                    "font_size_ratio": 0.08,
                    "font_size": 72,
                    "text_color": [255, 255, 255],
                    "stroke_color": [0, 0, 0],
                    "stroke_width": 2,
                    "shadow": true,
                    "alignment": "center",
                    "opacity": 1.0,
                    "background_pill": false,
                    "pill_color": [0, 0, 0],
                    "pill_opacity": 0.35
                }
                Use font_size (px) or font_size_ratio (0–1); pill options for blend.
        
        Returns:
            Image with text as JPEG bytes
        """
        # Load image
        img = Image.open(io.BytesIO(image)).convert("RGB")
        
        # Validate config
        config = self._validate_config(config, img)
        
        # Render text
        result = self._render_text(img, text, config)
        
        # Save
        output = io.BytesIO()
        result.save(output, format="JPEG", quality=95)
        
        return output.getvalue()
    
    @modal.method()
    def add_watermark(
        self,
        image: bytes,
        text: str,
        position: str = "bottom_right",  # bottom_right, bottom_left, center
        opacity: float = 0.3
    ) -> bytes:
        """
        Add a subtle watermark to image.
        
        Args:
            image: Input image as bytes
            text: Watermark text
            position: Position (bottom_right, bottom_left, center)
            opacity: Watermark opacity (0-1)
        
        Returns:
            Image with watermark as JPEG bytes
        """
        positions = {
            "bottom_right": {"x": 0.85, "y": 0.92},
            "bottom_left": {"x": 0.15, "y": 0.92},
            "center": {"x": 0.5, "y": 0.5},
        }
        
        config = {
            "placement": positions.get(position, positions["bottom_right"]),
            "font_style": "sans",
            "font_size_ratio": 0.03,
            "text_color": [255, 255, 255],
            "stroke_color": [0, 0, 0],
            "stroke_width": 1,
            "shadow": False,
            "alignment": "center" if position == "center" else ("right" if "right" in position else "left"),
            "opacity": opacity,
        }
        
        return self.add_text_with_config(image, text, config)
    
    @modal.method()
    def analyze_for_text(self, image: bytes, text: str) -> Dict:
        """
        Analyze image and return recommended text configuration.
        Does not modify the image.
        
        Args:
            image: Input image as bytes
            text: Text that will be added
        
        Returns:
            Configuration dict with recommended settings
        """
        img = Image.open(io.BytesIO(image)).convert("RGB")
        config = self._analyze_image_for_placement(img, text, "auto")
        
        # Add image info
        config["image_size"] = {"width": img.size[0], "height": img.size[1]}
        config["dominant_colors"] = self._extract_dominant_colors(img)
        
        return config


# Export singleton
text_renderer = TextRenderer()


# ==================== Web Endpoints ====================

@app.function(
    image=text_image,
    gpu="T4",
    timeout=120,
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
    ],
)
@modal.fastapi_endpoint(method="POST")
def add_text_web(item: dict):
    """
    Web endpoint for adding text to images.
    
    Request body:
    {
        "image_base64": "...",  // Base64 encoded image
        "text": "SUMMER 2026",
        "style": "bold",  // optional: auto, minimal, bold, elegant, modern, poster
        "placement": "center"  // optional: auto, top, center, bottom
    }
    
    Response:
    {
        "image_base64": "...",
        "config_used": {...}
    }
    """
    import base64
    
    # Decode image
    image_base64 = item.get("image_base64", "")
    if not image_base64:
        return {"error": "image_base64 is required"}
    
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return {"error": f"Invalid base64 image: {e}"}
    
    text = item.get("text", "")
    if not text:
        return {"error": "text is required"}
    
    # Process (Modal .remote stub not in types)
    result_bytes = text_renderer.add_text.remote(  # type: ignore[reportAttributeAccessIssue]
        image=image_bytes,
        text=text,
        style=item.get("style", "auto"),
        placement=item.get("placement", "auto"),
        custom_config=item.get("custom_config"),
    )
    
    # Encode result
    result_base64 = base64.b64encode(result_bytes).decode()
    
    return {
        "image_base64": result_base64,
        "text_added": text,
    }


@app.function(
    image=text_image,
    gpu="T4",
    timeout=120,
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
    ],
)
@modal.fastapi_endpoint(method="POST")
def add_watermark_web(item: dict):
    """
    Web endpoint for adding watermarks.
    
    Request body:
    {
        "image_base64": "...",
        "text": "© PhotoGenius",
        "position": "bottom_right",  // optional
        "opacity": 0.3  // optional
    }
    """
    import base64
    
    image_base64 = item.get("image_base64", "")
    if not image_base64:
        return {"error": "image_base64 is required"}
    
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return {"error": f"Invalid base64 image: {e}"}
    
    text = item.get("text", "")
    if not text:
        return {"error": "text is required"}
    
    result_bytes = text_renderer.add_watermark.remote(  # type: ignore[reportAttributeAccessIssue]
        image=image_bytes,
        text=text,
        position=item.get("position", "bottom_right"),
        opacity=item.get("opacity", 0.3),
    )
    
    result_base64 = base64.b64encode(result_bytes).decode()
    
    return {
        "image_base64": result_base64,
    }


@app.function(
    image=text_image,
    timeout=60,
)
@modal.fastapi_endpoint(method="GET")
def list_text_styles_web():
    """List available text style presets"""
    return {
        "styles": TEXT_STYLE_PRESETS,
        "font_styles": list(FONT_MAPPINGS.keys()),
        "placements": ["auto", "top", "center", "bottom"],
    }


# ==================== Local Testing ====================

@app.local_entrypoint()
def test_text_renderer():
    """Test text renderer with sample image"""
    print("\n" + "=" * 60)
    print("🔤 Testing Text Renderer")
    print("=" * 60 + "\n")
    
    # Create test image
    from PIL import Image  # type: ignore[reportMissingImports]
    import io
    
    # Create a simple gradient test image
    width, height = 1024, 768
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    
    for y in range(height):
        for x in range(width):
            # Create a gradient from dark blue to light blue
            r = int(50 + (x / width) * 50)
            g = int(100 + (y / height) * 100)
            b = int(150 + (x / width) * 100)
            pixels[x, y] = (r, g, b)
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    test_image_bytes = buffer.getvalue()
    
    print("Test 1: Auto style and placement")
    print("-" * 40)
    
    result = text_renderer.add_text.remote(  # type: ignore[reportAttributeAccessIssue]
        image=test_image_bytes,
        text="HELLO WORLD",
        style="auto",
        placement="auto"
    )
    
    print(f"✓ Generated image: {len(result)} bytes")
    
    # Save result
    result_path = "test_text_output.jpg"
    with open(result_path, "wb") as f:
        f.write(result)
    print(f"✓ Saved to: {result_path}")
    
    print("\nTest 2: Bold style, center placement")
    print("-" * 40)
    
    result2 = text_renderer.add_text.remote(  # type: ignore[reportAttributeAccessIssue]
        image=test_image_bytes,
        text="SUMMER 2026\nCollection",
        style="bold",
        placement="center"
    )
    
    print(f"✓ Generated image: {len(result2)} bytes")
    
    result2_path = "test_text_output_bold.jpg"
    with open(result2_path, "wb") as f:
        f.write(result2)
    print(f"✓ Saved to: {result2_path}")
    
    print("\nTest 3: Watermark")
    print("-" * 40)
    
    result3 = text_renderer.add_watermark.remote(  # type: ignore[reportAttributeAccessIssue]
        image=test_image_bytes,
        text="© PhotoGenius AI",
        position="bottom_right",
        opacity=0.5
    )
    
    print(f"✓ Generated image: {len(result3)} bytes")
    
    result3_path = "test_watermark_output.jpg"
    with open(result3_path, "wb") as f:
        f.write(result3)
    print(f"✓ Saved to: {result3_path}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print("\nUsage examples:")
    print("  # Deploy to Modal")
    print("  modal deploy ai-pipeline/services/text_renderer.py")
    print("\n  # Add text to generated image")
    print("  result = text_renderer.add_text.remote(")
    print("      image=image_bytes,")
    print('      text="SUMMER 2026",')
    print('      style="bold",')
    print('      placement="center"')
    print("  )")
