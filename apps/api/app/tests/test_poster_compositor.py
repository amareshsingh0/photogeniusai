from PIL import ImageFont

from app.services.smart.poster_compositor import _draw_text_centered


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
