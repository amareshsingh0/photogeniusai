import base64
import io

from PIL import Image
from PIL import ImageFont

from app.services.smart.poster_compositor import _draw_text_centered, poster_compositor


class _FakeDraw:
    def __init__(self) -> None:
        self.calls = []

    def textbbox(self, xy, text, font=None):
        width = max(1, len(text)) * 10
        return (0, 0, width, 20)

    def text(self, xy, text, font=None, fill=None, **kwargs):
        assert "anchor" not in kwargs
        self.calls.append((xy, text, kwargs))


def test_draw_text_centered_multiline_avoids_anchor_kwarg() -> None:
    draw = _FakeDraw()
    font = ImageFont.load_default()

    _draw_text_centered(
        draw=draw,
        text="GRAND\nOPENING",
        font=font,
        canvas_w=500,
        y=120,
        fill=(255, 255, 255, 255),
        shadow=True,
    )

    assert len(draw.calls) == 4


def test_composite_accepts_agent_elements_layout() -> None:
    img = Image.new("RGB", (512, 768), color=(12, 18, 28))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    hero_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    result = poster_compositor.composite(
        hero_b64=hero_b64,
        ad_copy={
            "brand_name": "BEAT FEST",
            "headline": "BEAT FEST 2026",
            "subheadline": "March 15",
            "body": "Feel the pulse of the city.",
            "cta": "CLAIM YOUR RUSH",
        },
        poster_design={
            "accent_color": "#18E0E8",
            "bg_color": "#0A1018",
            "text_color_primary": "#FFFFFF",
            "text_color_secondary": "#C8D6E5",
            "font_style": "bold_tech",
            "copy_space": "top",
            "headline_font": "anton",
            "subheadline_font": "montserrat_bold",
            "body_font": "montserrat_bold",
            "cta_font": "anton",
            "headline_effect": "glow",
            "cta_treatment": "pill",
        },
        elements=[
            {"id": "brand_name", "type": "text", "bounds": {"x": 0.06, "y": 0.05, "w": 0.40, "h": 0.06},
             "style": {"font": "anton", "size_role": "brand", "color": "#FFFFFF", "align": "left"}, "content": "BEAT FEST"},
            {"id": "headline", "type": "text", "bounds": {"x": 0.08, "y": 0.16, "w": 0.84, "h": 0.18},
             "style": {"font": "anton", "size_role": "headline", "color": "#FFFFFF", "align": "center", "effect": "glow"}, "content": "BEAT FEST\n2026"},
            {"id": "subheadline", "type": "text", "bounds": {"x": 0.18, "y": 0.36, "w": 0.64, "h": 0.07},
             "style": {"font": "montserrat_bold", "size_role": "subheadline", "color": "#C8D6E5", "align": "center"}, "content": "March 15"},
            {"id": "cta_button", "type": "shape", "bounds": {"x": 0.14, "y": 0.78, "w": 0.72, "h": 0.08},
             "style": {"fill": "#18E0E8", "radius": 30, "opacity": 1.0}, "content": ""},
            {"id": "cta_text", "type": "text", "bounds": {"x": 0.16, "y": 0.78, "w": 0.68, "h": 0.08},
             "style": {"font": "anton", "size_role": "cta", "color": "#061019", "align": "center"}, "content": "CLAIM YOUR RUSH"},
        ],
        target_width=512,
        target_height=768,
    )

    assert isinstance(result, str)
    assert len(result) > 100
