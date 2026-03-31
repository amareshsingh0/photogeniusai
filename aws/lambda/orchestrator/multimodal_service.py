"""
Multimodal processing: image analysis (Claude vision), voice transcription (Whisper).

Extracts reference-image and voice handling from the orchestrator.
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from io import BytesIO
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Optional observability
try:
    from services.observability import (
        CircuitBreaker,
        StructuredLogger,
        trace_function,
        track_llm_call,
    )
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    track_llm_call = lambda _: (lambda f: f)  # type: ignore[assignment, misc]
    CircuitBreaker = None  # type: ignore[assignment, misc]
    StructuredLogger = None  # type: ignore[assignment, misc]

try:
    from PIL import Image  # type: ignore[reportMissingImports]

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    Image = None  # type: ignore[assignment, misc]


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


class MultimodalService:
    """Handle image analysis and voice transcription."""

    def __init__(
        self,
        claude_client: Optional[object] = None,
        whisper_model: Optional[object] = None,
    ):
        self.claude = claude_client
        self.whisper = whisper_model
        self.claude_circuit = (
            CircuitBreaker("claude_vision") if CircuitBreaker else None
        )
        self.whisper_circuit = (
            CircuitBreaker("whisper") if CircuitBreaker else None
        )
        _log().info("MultimodalService initialized")

    def _ensure_image_bytes(self, source: Union[str, bytes]) -> bytes:
        """Return image as bytes. source may be path or bytes."""
        if isinstance(source, bytes):
            return source
        with open(source, "rb") as f:
            return f.read()

    def _ensure_audio_path(self, source: Union[str, bytes]) -> str:
        """Return path to audio. If bytes, write to temp file and return path."""
        if isinstance(source, str):
            return source
        suffix = ".wav"
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            os.write(fd, source)
            os.close(fd)
            return path
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            raise

    @trace_function("multimodal.analyze_image")
    def analyze_reference_image(
        self,
        source: Union[str, bytes],
        analysis_focus: str = "general",
        image_num: int = 1,
        *,
        image_path: Optional[Union[str, bytes]] = None,
    ) -> str:
        """
        Analyze reference image with Claude Vision.

        Args:
            source: Path to image file or image bytes (or use image_path= for spec compatibility)
            analysis_focus: general | composition | style | lighting
            image_num: Optional 1-based index for logging
            image_path: Alias for source (spec compatibility).

        Returns:
            Text description of the image.
        """
        s = source if image_path is None else image_path
        _log().info(
            "Analyzing reference image (focus=%s, num=%d)" % (analysis_focus, image_num)
        )
        img_bytes = self._ensure_image_bytes(s)
        try:
            if self.claude_circuit and self.claude:
                return self.claude_circuit.call(
                    self._analyze_with_claude_vision,
                    img_bytes,
                    analysis_focus,
                )
            return self._analyze_with_claude_vision(img_bytes, analysis_focus)
        except Exception as e:
            _log().error("Image analysis failed: %s" % e)
            return "reference image style"

    @track_llm_call("image_analysis")
    def _analyze_with_claude_vision(
        self,
        img_bytes: bytes,
        focus: str,
    ) -> str:
        if not self.claude:
            return "reference image style"
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        media_type = "image/jpeg"
        if len(img_bytes) >= 8 and img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"

        focus_prompts = {
            "general": "Analyze this image for photo generation reference. Extract and describe: 1) Composition (rule of thirds, framing, angle, shot type) 2) Lighting (direction, quality, mood) 3) Color palette and grading 4) Style and aesthetic 5) Implied camera settings 6) Key visual elements. Be specific and technical. Return a structured description that can be used to recreate similar photographic qualities.",
            "composition": "Analyze the composition, framing, and layout of this image.",
            "style": "Describe the artistic style and aesthetic of this image.",
            "lighting": "Analyze the lighting setup and mood of this image.",
        }
        prompt = focus_prompts.get(focus, focus_prompts["general"])

        response = getattr(self.claude, "messages", None)
        if response is None:
            raise RuntimeError("Claude client has no messages API")
        response = response.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text

    @trace_function("multimodal.transcribe_audio")
    def transcribe_voice(
        self,
        source: Union[str, bytes],
        *,
        audio_path: Optional[Union[str, bytes]] = None,
    ) -> str:
        """
        Transcribe voice audio using Whisper.

        Args:
            source: Path to audio file or audio bytes (WAV, MP3, etc.)
            audio_path: Alias for source (spec compatibility).

        Returns:
            Transcribed text.
        """
        s = source if audio_path is None else audio_path
        _log().info("Transcribing voice input")
        path = self._ensure_audio_path(s)
        try:
            if self.whisper_circuit and self.whisper:
                out = self.whisper_circuit.call(
                    self._transcribe_with_whisper, path
                )
            else:
                out = self._transcribe_with_whisper(path)
            return out
        except Exception as e:
            _log().error("Voice transcription failed: %s" % e)
            return ""
        finally:
            if isinstance(s, bytes) and os.path.isfile(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass

    def _transcribe_with_whisper(self, audio_path: str) -> str:
        try:
            import whisper  # type: ignore[reportMissingImports]
        except ImportError:
            return ""
        if not self.whisper:
            try:
                self.whisper = whisper.load_model("base")
            except Exception:
                return ""
        try:
            import torch  # type: ignore[reportMissingImports]
        except ImportError:
            torch = None  # type: ignore[assignment]
        fp16 = bool(torch and getattr(torch.cuda, "is_available", lambda: False)())
        transcribe_fn = getattr(self.whisper, "transcribe", None)
        if transcribe_fn is None:
            return ""
        result = transcribe_fn(
            audio_path,
            language="en",
            fp16=fp16,
        )
        return (result.get("text") or "").strip()
