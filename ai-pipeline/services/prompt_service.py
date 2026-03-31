"""
Dedicated service for prompt parsing and synthesis.

Extracts prompt intelligence from the orchestrator: Claude/fallback parsing,
multimodal synthesis, cache, circuit breaker, confidence scores.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional observability
try:
    from services.observability import (
        CircuitBreaker,
        Metrics,
        StructuredLogger,
        trace_function,
        track_llm_call,
    )
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    track_llm_call = lambda _: (lambda f: f)  # type: ignore[assignment, misc]
    CircuitBreaker = None  # type: ignore[assignment, misc]
    Metrics = None  # type: ignore[assignment, misc]
    StructuredLogger = None  # type: ignore[assignment, misc]


def _logger():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


def _noop_metrics():
    if Metrics is None:
        return
    try:
        Metrics.cache_hits.labels(cache_type="prompt_parse").inc()
    except Exception:
        pass


def _noop_miss():
    if Metrics is None:
        return
    try:
        Metrics.cache_misses.labels(cache_type="prompt_parse").inc()
    except Exception:
        pass


class PromptMode(str, Enum):
    STANDARD = "standard"
    PORTRAIT = "portrait"
    PRODUCT = "product"
    CREATIVE = "creative"
    ARTISTIC = "artistic"
    REALISM = "REALISM"
    ROMANTIC = "ROMANTIC"
    FASHION = "FASHION"
    CINEMATIC = "CINEMATIC"


@dataclass
class ParsedPrompt:
    """Structured prompt representation (orchestrator-compatible)."""

    subject: str
    action: str
    setting: str
    time: str
    lighting: str
    camera: str
    mood: str
    color: str
    style: str
    technical: str
    full_prompt: str
    negative_prompt: str = "blurry, distorted, low quality, ugly"
    confidence: float = 0.9
    parsing_method: str = "claude"
    raw_input: str = ""

    @property
    def final_prompt(self) -> str:
        """Spec alias for full_prompt."""
        return self.full_prompt


class PromptService:
    """Dedicated service for prompt intelligence."""

    def __init__(self, claude_client: Optional[Any] = None):
        self.claude = claude_client
        self.claude_circuit = (
            CircuitBreaker("claude_prompt_parsing") if CircuitBreaker else None
        )
        self.parse_cache: Dict[str, ParsedPrompt] = {}
        _logger().info("PromptService initialized")

    def _cache_key(self, prompt: str, mode: Optional[str]) -> str:
        key_str = f"{prompt}:{mode or 'none'}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    @trace_function("prompt.parse")
    def parse(
        self,
        prompt: str,
        mode: Optional[str] = None,
        use_cache: bool = True,
    ) -> ParsedPrompt:
        """Parse user prompt into structured format."""
        mode = mode or "REALISM"
        if use_cache:
            ck = self._cache_key(prompt, mode)
            if ck in self.parse_cache:
                _logger().info("Prompt parse cache hit")
                _noop_metrics()
                return self.parse_cache[ck]
            _noop_miss()

        try:
            if self.claude_circuit and self.claude:
                parsed = self.claude_circuit.call(
                    self._parse_with_claude, prompt, mode
                )
            else:
                parsed = self._parse_with_claude(prompt, mode)
        except Exception as e:
            _logger().warning(
                "Claude parsing failed, using fallback: %s (prompt_length=%d)"
                % (e, len(prompt))
            )
            parsed = self._fallback_parse(prompt, mode)

        if use_cache:
            self.parse_cache[self._cache_key(prompt, mode)] = parsed
        return parsed

    @track_llm_call("prompt_parsing")
    def _parse_with_claude(self, prompt: str, mode: str) -> ParsedPrompt:
        """Parse prompt using Claude."""
        if not self.claude:
            return self._fallback_parse(prompt, mode)

        system_prompt = """You are a world-class photography director AI. Parse user prompts into detailed structured components for professional photo generation.

Rules:
- If user gives 2 words, expand to full professional spec
- Maintain user's core intent always
- Add photographic/cinematic depth using industry terms
- Use specific camera language (85mm, f/2.0, golden hour, rim lighting)
- Return ONLY valid JSON, no explanation
- Be creative but realistic

JSON Format (return ONLY this structure):
{
  "subject": "Who or what is the main subject",
  "action": "What they're doing, pose, movement",
  "setting": "Location, environment, background details",
  "time": "Time of day, golden hour, blue hour, etc.",
  "lighting": "Type, quality, direction (backlight, rim lighting, soft fill, etc.)",
  "camera": "Shot type, lens, focal length, aperture (e.g., 'medium shot, 85mm lens, f/2.0 shallow DOF')",
  "mood": "Emotional tone, feeling, atmosphere",
  "color": "Color palette, grading, tones",
  "style": "Artistic references, inspiration (e.g., 'inspired by Peter Lindbergh')",
  "technical": "Film stock, grain, aesthetic details"
}"""

        user_message = f'''Parse this prompt for {mode} mode photography:

User prompt: "{prompt}"

Expand it into a complete professional photography specification. If the prompt is minimal (like "beach" or "office"), infer professional details like lighting, camera settings, mood, and style. Return ONLY valid JSON.'''

        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        content = response.content[0].text
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            raise ValueError("No JSON found in Claude response")
        parsed_data = json.loads(content[json_start:json_end])

        full_prompt = ", ".join(
            [
                parsed_data.get("subject", ""),
                parsed_data.get("action", ""),
                parsed_data.get("setting", ""),
                parsed_data.get("time", ""),
                parsed_data.get("lighting", ""),
                parsed_data.get("camera", ""),
                parsed_data.get("mood", ""),
                parsed_data.get("color", ""),
                parsed_data.get("style", ""),
                parsed_data.get("technical", ""),
            ]
        )

        return ParsedPrompt(
            subject=parsed_data.get("subject", prompt),
            action=parsed_data.get("action", ""),
            setting=parsed_data.get("setting", ""),
            time=parsed_data.get("time", ""),
            lighting=parsed_data.get("lighting", ""),
            camera=parsed_data.get("camera", ""),
            mood=parsed_data.get("mood", ""),
            color=parsed_data.get("color", ""),
            style=parsed_data.get("style", ""),
            technical=parsed_data.get("technical", ""),
            full_prompt=full_prompt,
            negative_prompt="blurry, distorted, low quality, worst quality, jpeg artifacts, watermark, text, deformed, bad anatomy",
            confidence=0.95,
            parsing_method="claude",
            raw_input=prompt,
        )

    def _fallback_parse(self, prompt: str, mode: str) -> ParsedPrompt:
        """Fallback parsing using rules."""
        _logger().info("Using fallback prompt parsing")
        mode_expansions: Dict[str, Dict[str, str]] = {
            "REALISM": {
                "subject": f"professional {prompt}",
                "action": "natural pose, confident expression",
                "setting": "professional environment",
                "time": "natural lighting, daytime",
                "lighting": "soft, even lighting, professional studio quality",
                "camera": "85mm lens, f/2.0, shallow depth of field",
                "mood": "professional, confident, approachable",
                "color": "natural colors, accurate skin tones, balanced",
                "style": "professional photography, LinkedIn style",
                "technical": "sharp focus, high quality, clean",
            },
            "CREATIVE": {
                "subject": prompt,
                "action": "dynamic pose, expressive movement",
                "setting": "artistic environment, creative backdrop",
                "time": "dramatic lighting, creative time of day",
                "lighting": "creative lighting setup, dramatic shadows",
                "camera": "wide angle, creative composition, unique perspective",
                "mood": "artistic, vibrant, expressive",
                "color": "vibrant colors, high saturation, bold palette",
                "style": "trending on artstation, award winning, concept art",
                "technical": "highly detailed, 4k, masterpiece, cinematic",
            },
            "ROMANTIC": {
                "subject": f"romantic {prompt}",
                "action": "tender pose, intimate moment, gentle interaction",
                "setting": "romantic environment, soft surroundings",
                "time": "golden hour, sunset, soft natural light",
                "lighting": "warm golden light, soft fill, romantic glow",
                "camera": "85mm lens, f/1.8, shallow depth of field, soft focus",
                "mood": "romantic, intimate, tender, dreamy",
                "color": "warm tones, soft pastels, romantic color grading",
                "style": "romantic photography, wedding style, intimate portraiture",
                "technical": "soft focus, film grain, Kodak Portra aesthetic",
            },
            "FASHION": {
                "subject": f"fashion {prompt}",
                "action": "model pose, confident stance, editorial style",
                "setting": "fashion environment, editorial backdrop",
                "time": "studio lighting, controlled environment",
                "lighting": "fashion lighting setup, dramatic shadows, rim lighting",
                "camera": "85mm lens, f/2.8, medium shot, editorial framing",
                "mood": "fashion-forward, confident, stylish, editorial",
                "color": "fashion color palette, bold contrasts, editorial grading",
                "style": "fashion photography, Vogue style, editorial",
                "technical": "sharp focus, high fashion quality, magazine ready",
            },
            "CINEMATIC": {
                "subject": prompt,
                "action": "cinematic pose, dramatic movement, story-driven",
                "setting": "cinematic environment, movie-like backdrop",
                "time": "dramatic time of day, cinematic lighting",
                "lighting": "cinematic lighting, dramatic shadows, film noir style",
                "camera": "anamorphic lens, wide shot, cinematic framing, 2.39:1 aspect",
                "mood": "cinematic, dramatic, story-driven, film-like",
                "color": "cinematic color grading, film look, desaturated shadows",
                "style": "cinematic photography, movie still, film aesthetic",
                "technical": "film grain, cinematic quality, anamorphic bokeh",
            },
        }
        expansion = mode_expansions.get(
            (mode or "REALISM").upper(), mode_expansions["REALISM"]
        )
        full_prompt = ", ".join(expansion.values())
        return ParsedPrompt(
            subject=expansion["subject"],
            action=expansion["action"],
            setting=expansion["setting"],
            time=expansion["time"],
            lighting=expansion["lighting"],
            camera=expansion["camera"],
            mood=expansion["mood"],
            color=expansion["color"],
            style=expansion["style"],
            technical=expansion["technical"],
            full_prompt=full_prompt,
            negative_prompt="blurry, distorted, low quality, ugly",
            confidence=0.6,
            parsing_method="fallback",
            raw_input=prompt,
        )

    @trace_function("prompt.synthesize_multimodal")
    def synthesize_multimodal(
        self,
        text_prompt: Optional[str] = None,
        image_analysis: Optional[str] = None,
        voice_transcript: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> ParsedPrompt:
        """
        Synthesize prompt from multiple modalities (spec API). Returns ParsedPrompt.

        Args:
            text_prompt: Text description
            image_analysis: Analysis of reference image
            voice_transcript: Transcribed voice input
            mode: Generation mode

        Returns:
            ParsedPrompt combining all inputs.
        """
        combined_parts: List[str] = []
        if text_prompt:
            combined_parts.append("Text: %s" % text_prompt)
        if voice_transcript:
            combined_parts.append("Voice: %s" % voice_transcript)
        if image_analysis:
            combined_parts.append("Reference image: %s" % image_analysis)
        combined_input = " | ".join(combined_parts) if combined_parts else ""
        _logger().info(
            "Synthesizing multimodal prompt (has_text=%s, has_image=%s, has_voice=%s)"
            % (bool(text_prompt), bool(image_analysis), bool(voice_transcript))
        )
        try:
            if self.claude_circuit and self.claude:
                return self.claude_circuit.call(
                    self._synthesize_multimodal_with_claude,
                    combined_input,
                    mode or "REALISM",
                )
            return self._synthesize_multimodal_with_claude(
                combined_input, mode or "REALISM"
            )
        except Exception as e:
            _logger().warning("Multimodal synthesis failed, using fallback: %s" % e)
            fallback = " ".join(
                p for p in [text_prompt, voice_transcript, image_analysis] if p
            )
            return self._fallback_parse(fallback or "image", mode or "REALISM")

    @track_llm_call("multimodal_synthesis")
    def _synthesize_multimodal_with_claude(
        self, combined_input: str, mode: str
    ) -> ParsedPrompt:
        """Synthesize multimodal input with Claude; return ParsedPrompt."""
        if not self.claude:
            return self._fallback_parse(combined_input or "image", mode)
        system_prompt = """You are synthesizing multiple inputs into a single coherent image generation prompt.
Combine text, voice, and image analysis into one unified prompt.
Return structured JSON only."""
        user_prompt = f"""Synthesize these inputs into one prompt:

{combined_input}

Mode: {mode or "standard"}

Return JSON:
{{"subject":"...","style":"...","lighting":"...","camera":"...","mood":"...","negative":"..."}}"""
        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text.strip()
        json_str = content
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = json_str[start:end]
        parsed_data = json.loads(json_str)
        full = self._construct_final_prompt(parsed_data)
        return ParsedPrompt(
            subject=parsed_data.get("subject", ""),
            action=parsed_data.get("action", ""),
            setting=parsed_data.get("setting", ""),
            time=parsed_data.get("time", ""),
            lighting=parsed_data.get("lighting", "natural lighting"),
            camera=parsed_data.get("camera", ""),
            mood=parsed_data.get("mood", ""),
            color=parsed_data.get("color", ""),
            style=parsed_data.get("style", "photorealistic"),
            technical=parsed_data.get("technical", ""),
            full_prompt=full,
            negative_prompt=parsed_data.get("negative", "blurry, distorted, low quality"),
            confidence=0.9,
            parsing_method="claude_multimodal",
            raw_input=combined_input,
        )

    def _construct_final_prompt(self, parsed_data: Dict[str, Any]) -> str:
        """Build full_prompt from parsed components."""
        parts = []
        for k in ("subject", "style", "lighting", "camera", "mood", "color"):
            v = parsed_data.get(k)
            if v:
                parts.append(v)
        parts.append("high quality, detailed, professional")
        return ", ".join(parts)

    def synthesize_multimodal_from_parts(
        self,
        combined_parts: List[str],
        mode: str = "REALISM",
    ) -> str:
        """
        Synthesize combined_parts into a single prompt string (orchestrator use).
        Use synthesize_multimodal() for spec API returning ParsedPrompt.
        """
        _logger().info(
            "Synthesizing multimodal from parts (num_parts=%d, mode=%s)"
            % (len(combined_parts), mode)
        )
        if not combined_parts:
            return ""
        synthesis_prompt = f"""You are a world-class photography director. Synthesize these multi-modal inputs into a comprehensive photo generation prompt.

Inputs:
{chr(10).join("- " + p for p in combined_parts)}

Mode: {mode}

Create a detailed, structured prompt. Return ONLY a single comprehensive text prompt (not JSON). Be specific about composition, lighting, color, style, subject and action. No explanation."""
        if not self.claude:
            return " | ".join(combined_parts)
        try:
            if self.claude_circuit:
                out = self.claude_circuit.call(
                    lambda: self._synthesize_with_claude(synthesis_prompt)
                )
            else:
                out = self._synthesize_with_claude(synthesis_prompt)
            return out or " | ".join(combined_parts)
        except Exception as e:
            _logger().warning("Multimodal synthesis failed, using concatenation: %s" % e)
            return " | ".join(combined_parts)

    def _synthesize_with_claude(self, synthesis_prompt: str) -> str:
        if not self.claude:
            return ""
        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return text
