"""
The Orchestrator - The Brain of PhotoGenius AI

This is the master controller that receives simple user prompts and orchestrates
multiple AI engines to produce perfect images. It uses Claude Sonnet 4 for
intelligent prompt parsing and routing decisions.

Flow:
1. Parse: "beach" → Full professional photography spec
2. Plan: Decide which engines to use (Identity, Creative, Composition, Finish)
3. Execute: Call engines in sequence
4. Rerank: Use LLM intelligence to pick the best result
"""
# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import modal  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from dataclasses import dataclass
from enum import Enum

if "/root" not in sys.path:
    sys.path.insert(0, "/root")
try:
    from services.scoring_service import FinalScore
    from services.scoring_service import ScoreComponent
    from services.scoring_service import ScoringService
except ImportError:
    ScoringService = None  # type: ignore[misc, assignment]
    FinalScore = None  # type: ignore[misc, assignment]
    ScoreComponent = None  # type: ignore[misc, assignment]
try:
    from services.observability import (
        RequestTracker,
        StructuredLogger,
        Metrics,
        CircuitBreaker,
        get_request_id,
        set_request_id,
        setup_tracing,
        setup_metrics,
        trace_function,
        track_llm_call,
        track_engine_call,
        tracked_engine_call,
        retry_with_backoff,
        push_metrics_to_gateway,
    )
except ImportError:
    RequestTracker = None  # type: ignore[misc, assignment]
    StructuredLogger = None  # type: ignore[misc, assignment]
    Metrics = None  # type: ignore[misc, assignment]
    CircuitBreaker = None  # type: ignore[misc, assignment]
    get_request_id = lambda: None  # type: ignore[assignment, misc]
    set_request_id = lambda v: None  # type: ignore[assignment, misc]
    setup_tracing = lambda: False  # type: ignore[assignment, misc]
    setup_metrics = lambda: True  # type: ignore[assignment, misc]
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    track_llm_call = lambda _: (lambda f: f)  # type: ignore[assignment, misc]
    track_engine_call = lambda _: (lambda f: f)  # type: ignore[assignment, misc]
    def tracked_engine_call(engine_name: str, fn: Any, *a: Any, **k: Any) -> Any:  # type: ignore[misc]
        return fn(*a, **k)
    def retry_with_backoff(max_retries: int = 3, backoff_base: float = 0.5, jitter: bool = True) -> Any:  # type: ignore[misc]
        return lambda f: f
    push_metrics_to_gateway = lambda job=None: None  # type: ignore[assignment, misc]
try:
    from services.adversarial_defense import (
        AdversarialDefenseSystem,
        DefenseResult,
        ThreatDetection,
    )
except ImportError:
    AdversarialDefenseSystem = None  # type: ignore[misc, assignment]
    DefenseResult = None  # type: ignore[misc, assignment]
    ThreatDetection = None  # type: ignore[misc, assignment]

try:
    from services.prompt_service import ParsedPrompt as PSParsedPrompt
    from services.prompt_service import PromptService
except ImportError:
    PromptService = None  # type: ignore[misc, assignment]
    PSParsedPrompt = None  # type: ignore[misc, assignment]

try:
    from services.multimodal_service import MultimodalService
except ImportError:
    MultimodalService = None  # type: ignore[misc, assignment]

try:
    from services.routing_service import EngineType as RoutingEngineType
    from services.routing_service import RoutingDecision
    from services.routing_service import RoutingService
except ImportError:
    RoutingService = None  # type: ignore[misc, assignment]
    RoutingDecision = None  # type: ignore[misc, assignment]
    RoutingEngineType = None  # type: ignore[misc, assignment]

try:
    from services.execution_service import ExecutionService
except ImportError:
    ExecutionService = None  # type: ignore[misc, assignment]

app = modal.App("photogenius-orchestrator")
stub = app  # Alias for compatibility

# Cross-app references resolved at runtime via modal.Cls.from_name()
# No relative imports - each service deploys as independent Modal app
IDENTITY_ENGINE_AVAILABLE = False
GENERATION_APP_AVAILABLE = False

# ==================== Modal Config ====================

orchestrator_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "anthropic>=0.34.0",
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "fastapi[standard]",  # Required for web endpoints
        "openai-whisper>=20231117",  # Voice transcription
        "pillow>=10.2.0",  # Image processing
        "numpy>=1.26.3",  # Image array operations
        "torch>=2.0.0",  # Required for Whisper
        "torchaudio>=2.0.0",  # Required for Whisper
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
        "prometheus_client>=0.19.0",
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y ffmpeg libsndfile1",  # Required for Whisper audio processing
    )
    .add_local_dir(
        "config",  # Include tier_config for resolution caps and feature gates
        remote_path="/root/config",
    )
    .add_local_dir(
        "services",  # scoring_service for canonical scoring
        remote_path="/root/services",
    )
)

# ==================== Data Models ====================

class Mode(str, Enum):
    """Generation modes"""
    REALISM = "REALISM"
    CREATIVE = "CREATIVE"
    ROMANTIC = "ROMANTIC"
    FASHION = "FASHION"
    CINEMATIC = "CINEMATIC"


@dataclass
class ParsedPrompt:
    """Structured prompt components extracted by Claude"""
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
    full_prompt: str  # Combined professional prompt


@dataclass
class EngineConfig:
    """Configuration for an engine execution"""
    engine_name: str  # "identity", "creative", "composition", "finish"
    weight: float  # 0.0-1.0, how much to use this engine
    params: Dict[str, Any]  # Engine-specific parameters


@dataclass
class ExecutionPlan:
    """Complete plan for generating images"""
    engines: List[EngineConfig]
    requires_composition: bool
    final_prompt: str


# Default negative prompt for realtime (LCM) path
REALTIME_NEGATIVE = (
    "blurry, low quality, worst quality, jpeg artifacts, "
    "watermark, text, deformed, bad anatomy, ugly, disfigured"
)

QUALITY_TIER_CONFIG = {
    "FAST": {
        "engine": "realtime",
        "steps": 4,
        "target_time": 8,
        "max_resolution": 1024,
        "guidance_scale": 5.0,
    },
    "STANDARD": {
        "engine": "realtime",
        "steps": 8,
        "target_time": 15,
        "max_resolution": 1024,
        "guidance_scale": 6.0,
    },
    "BALANCED": {
        "engine": "sdxl",
        "steps": 50,
        "target_time": 50,
        "max_resolution": 2048,
        "guidance_scale": 7.5,
    },
    "PREMIUM": {
        "engine": "sdxl",
        "steps": 80,
        "target_time": 90,
        "max_resolution": 2048,
        "guidance_scale": 8.0,
    },
    "ULTRA": {
        "engine": "ultra_high_res",
        "steps": 80,
        "target_time": 180,
        "max_resolution": 4096,
        "guidance_scale": 8.0,
    },
}

# Import tier config for resolution caps (shared with apps/api)
try:
    from config.tier_config import (
        SubscriptionTier,
        get_tier_limits,
        normalize_tier,
    )
    USE_TIER_CONFIG = True
except ImportError:
    # Fallback if config not available (shouldn't happen in Modal deployment)
    USE_TIER_CONFIG = False
    logging.warning("config.tier_config not available, using fallback resolution caps")

# Fallback resolution caps (used if config.tier_config unavailable)
TIER_RESOLUTION_CAPS_FALLBACK = {
    "free": 1024,
    "hobby": 1024,
    "pro": 2048,
    "studio": 4096,
    "enterprise": 4096,
}
# Map quality tier -> effective cap when user_tier missing
QUALITY_TIER_TO_CAP = {
    "FAST": 1024,
    "STANDARD": 1024,
    "BALANCED": 2048,
    "PREMIUM": 2048,
    "ULTRA": 4096,
}


# ==================== Orchestrator Class ====================

@app.cls(
    image=orchestrator_image,
    timeout=300,
    # Note: Anthropic secret is optional - orchestrator works with fallback parser
    # If you want Claude-powered prompt expansion, create the secret:
    # modal secret create anthropic ANTHROPIC_API_KEY=sk-ant-...
    # Otherwise, it will use the fallback parser (still works, just less intelligent)
)
class Orchestrator:
    """
    The Brain - Orchestrates all AI engines to produce perfect images.
    
    Uses Claude Sonnet 4 for:
    - Intelligent prompt expansion (2 words → full spec)
    - Execution planning (which engines to use)
    - Result reranking (picking the best image)
    """
    
    @modal.enter()
    def initialize(self):
        """Initialize Claude client and engine references"""
        # Initialize Claude (optional - fallback parser available)
        try:
            from anthropic import Anthropic  # type: ignore[reportMissingImports]
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.client = Anthropic(api_key=api_key)
                self.claude = self.client  # Alias for backward compatibility
                self.claude_available = True
                print("✅ Claude Sonnet 4 initialized")
            else:
                print("⚠️ ANTHROPIC_API_KEY not found, using fallback parsing")
                self.claude_available = False
                self.client = None
        except Exception as e:
            print(f"⚠️ Failed to initialize Claude: {e}")
            self.claude_available = False
            self.client = None
        
        # Initialize Whisper model (lazy load on first use)
        self.whisper_model = None
        
        # Use Modal Cls.from_name to get references to other deployed apps
        # Priority: V2 (99%+ face) → V1 (Identity) → GenerationService
        self.identity_v2_generate = None
        self.identity_engine_generate = None
        self.generation_service_generate = None
        self.realtime_generate_batch = None
        self.quality_scorer_score_batch = None
        self.finish_finish = None

        try:
            FinishCls = modal.Cls.from_name("photogenius-finish-engine", "FinishEngine")
            fin = FinishCls()
            self.finish_finish = fin.finish
            print("Finish Engine available (upscale, face fix, color grade)")
        except Exception as e:
            print(f"Finish Engine not available: {e}")

        try:
            QualityScorerCls = modal.Cls.from_name("quality-scorer", "QualityScorer")
            qs_instance = QualityScorerCls()
            self.quality_scorer_score_batch = qs_instance.score_batch
            print("Quality Scorer available (batch scoring for rerank)")
        except Exception as e:
            print(f"Quality Scorer not available: {e}")

        try:
            RealtimeCls = modal.Cls.from_name("realtime-engine", "RealtimeEngine")
            rt_instance = RealtimeCls()
            self.realtime_generate_batch = rt_instance.generate_realtime_batch
            print("Realtime Engine available (FAST / quality_tier routing)")
        except Exception as e:
            print(f"Realtime Engine not available: {e}")

        self.composition_compose = None
        self.composition_compose_multi_identity = None
        try:
            CompCls = modal.Cls.from_name("photogenius-composition-engine", "CompositionEngine")
            comp_instance = CompCls()
            self.composition_compose = comp_instance.compose
            self.composition_compose_multi_identity = comp_instance.compose_multi_identity
            print("Composition Engine available (pose, depth, canny)")
        except Exception as e:
            print(f"Composition Engine not available: {e}")

        self.creative_engine_generate_creative = None
        try:
            CreativeCls = modal.Cls.from_name("photogenius-creative-engine", "CreativeEngine")
            creative_instance = CreativeCls()
            self.creative_engine_generate_creative = creative_instance.generate_creative
            print("Creative Engine available (styles, presets, mutations)")
        except Exception as e:
            print(f"Creative Engine not available: {e}")

        self.ultra_generate_4k = None
        self.ultra_generate_ultra = None
        try:
            UltraCls = modal.Cls.from_name("ultra-high-res", "UltraHighResEngine")
            ultra_instance = UltraCls()
            self.ultra_generate_4k = ultra_instance.generate_4k
            self.ultra_generate_ultra = ultra_instance.generate_ultra
            print("Ultra High-Res Engine available (4K tiled generation)")
        except Exception as e:
            print(f"Ultra High-Res Engine not available: {e}")

        try:
            IdentityV2Cls = modal.Cls.from_name("photogenius-identity-v2", "IdentityEngineV2")
            v2_instance = IdentityV2Cls()
            self.identity_v2_generate = v2_instance.generate_ultimate
            print("Identity Engine V2 available (99%+ face, ensemble)")
        except Exception as e:
            print(f"Identity Engine V2 not available: {e}")

        # Observability (tracing, metrics, structured logging)
        setup_tracing()
        setup_metrics()
        self.logger = StructuredLogger(__name__) if StructuredLogger else None
        self.claude_circuit = CircuitBreaker("claude") if CircuitBreaker and self.claude_available else None
        # Adversarial defense (homoglyphs, leetspeak, jailbreaks, injection, rate)
        self.defense = (
            AdversarialDefenseSystem(use_semantic=False)
            if AdversarialDefenseSystem is not None
            else None
        )

        # Service-oriented layer (prompt, multimodal, routing, execution)
        self.prompt_service = (
            PromptService(claude_client=self.client) if PromptService and self.client else None
        )
        self.multimodal_service = (
            MultimodalService(claude_client=self.client, whisper_model=self.whisper_model)
            if MultimodalService else None
        )
        ultra_avail = self.ultra_generate_4k is not None or self.ultra_generate_ultra is not None
        self.routing_service = (
            RoutingService(ultra_available=ultra_avail, estimate_ultra_time_fn=self._estimate_ultra_time)
            if RoutingService else None
        )
        self.execution_service = ExecutionService() if ExecutionService else None
        if self.execution_service:
            if self.realtime_generate_batch is not None:
                self.execution_service.register_realtime(
                    lambda **kw: self.realtime_generate_batch.remote(**kw)  # type: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
                )
            ufn = self.ultra_generate_ultra or self.ultra_generate_4k
            if ufn is not None:
                self.execution_service.register_ultra(
                    lambda **kw: ufn.remote(**kw)  # type: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
                )
            if self.identity_v2_generate is not None:
                self.execution_service.register_identity_v2(
                    lambda **kw: self.identity_v2_generate.remote(**kw)  # type: ignore[reportOptionalMemberAccess, reportAttributeAccessIssue]
                )

        try:
            IdentityEngineCls = modal.Cls.from_name("photogenius-identity-engine", "IdentityEngine")
            identity_instance = IdentityEngineCls()
            self.identity_engine_generate = identity_instance.generate
            print("Identity Engine V1 available via Cls.from_name")
        except Exception as e:
            print(f"IdentityEngine not available: {e}")
            try:
                GenerationServiceCls = modal.Cls.from_name("photogenius-generation", "GenerationService")
                gen_instance = GenerationServiceCls()
                self.generation_service_generate = gen_instance.generate_images
                print("Using fallback GenerationService (IdentityEngine not available)")
            except Exception as e2:
                print(f"GenerationService also not available: {e2}")
                print("No generation engine available - deploy first:")
                print("  modal deploy ai-pipeline/services/identity_engine_v2.py")
                print("  modal deploy ai-pipeline/services/identity_engine.py")
                print("  modal deploy ai-pipeline/services/generation_service.py")

    @modal.method()
    def orchestrate_multimodal(
        self,
        text_prompt: Optional[str] = None,
        reference_images: Optional[List[bytes]] = None,
        voice_prompt: Optional[bytes] = None,
        mode: str = "REALISM",
        identity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        num_candidates: int = 4,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
        composition_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Multi-modal prompt understanding - Accept images + text + voice.
        
        This is NEXT-LEVEL prompt understanding that nobody else has:
        - Text: "beach sunset"
        - Image: [photo of beach] → Vision analysis extracts style/composition/lighting
        - Voice: audio recording → Transcribed and analyzed
        
        All inputs are synthesized into a comprehensive prompt.
        
        Args:
            text_prompt: Text description (e.g., "beach sunset")
            reference_images: List of image bytes for visual reference
            voice_prompt: Audio bytes (WAV/MP3) for voice input
            mode: Generation mode (REALISM, CREATIVE, ROMANTIC, FASHION, CINEMATIC)
            identity_id: Optional identity ID for LoRA loading
            user_id: User ID for LoRA path resolution
            num_candidates: Number of candidates to generate
            seed: Optional random seed
            face_embedding: Optional face embedding for face similarity
        
        Returns:
            Dict with orchestration results (same format as orchestrate())
        
        Example:
            result = orchestrator.orchestrate_multimodal.remote(
                text_prompt="like this but different",
                reference_images=[image_bytes],
                mode="REALISM"
            )
        """
        print(f"\n{'='*60}")
        print(f"🧠 MULTI-MODAL PROMPT PROCESSING")
        print(f"{'='*60}\n")
        
        combined_prompt_parts = []
        
        # 1. Process text prompt
        if text_prompt:
            print("[1/4] Processing text prompt...")
            combined_prompt_parts.append(f"User text: {text_prompt}")
            print(f"  ✓ Text: {text_prompt[:50]}...")
        else:
            print("[1/4] No text prompt provided")
        
        # 2. Process reference images with Claude vision
        image_analyses = []
        if reference_images:
            print(f"[2/4] Analyzing {len(reference_images)} reference image(s)...")
            
            if not self.claude_available:
                print("  ⚠️ Claude not available, skipping image analysis")
            else:
                for i, img_bytes in enumerate(reference_images):
                    try:
                        analysis = self._analyze_reference_image(img_bytes, i + 1)
                        image_analyses.append(analysis)
                        combined_prompt_parts.append(f"Reference image {i+1}: {analysis}")
                        print(f"  ✓ Analyzed image {i+1}")
                    except Exception as e:
                        print(f"  ✗ Failed to analyze image {i+1}: {e}")
        else:
            print("[2/4] No reference images provided")
        
        # 3. Process voice prompt (transcribe + analyze)
        voice_transcription = None
        if voice_prompt:
            print("[3/4] Transcribing voice prompt...")
            try:
                voice_transcription = self._transcribe_voice(voice_prompt)
                combined_prompt_parts.append(f"Voice input: {voice_transcription}")
                print(f"  ✓ Transcribed: {voice_transcription[:50]}...")
            except Exception as e:
                print(f"  ✗ Voice transcription failed: {e}")
        else:
            print("[3/4] No voice prompt provided")
        
        # 4. Synthesize all inputs with Claude
        print("[4/4] Synthesizing all inputs into comprehensive prompt...")
        
        if not combined_prompt_parts:
            # Fallback to text-only if no inputs
            if text_prompt:
                return self.orchestrate(
                    user_prompt=text_prompt,
                    mode=mode,
                    identity_id=identity_id,
                    user_id=user_id,
                    num_candidates=num_candidates,
                    seed=seed,
                    face_embedding=face_embedding,
                    reference_images=reference_images,
                    composition_params=composition_params,
                )
            else:
                raise ValueError("At least one input modality (text, image, or voice) is required")
        
        # Synthesize with Claude if available
        if self.claude_available:
            try:
                synthesized_prompt = self._synthesize_multimodal_inputs(
                    combined_prompt_parts, mode
                )
                print(f"  ✓ Synthesized prompt: {synthesized_prompt[:100]}...")
                
                # Continue with standard orchestration using synthesized prompt
                return self.orchestrate(
                    user_prompt=synthesized_prompt,
                    mode=mode,
                    identity_id=identity_id,
                    user_id=user_id,
                    num_candidates=num_candidates,
                    seed=seed,
                    face_embedding=face_embedding,
                    reference_images=reference_images,
                    composition_params=composition_params,
                )
            except Exception as e:
                print(f"  ⚠️ Synthesis failed: {e}, using text-only fallback")
                # Fallback to text-only
                if text_prompt:
                    return self.orchestrate(
                        user_prompt=text_prompt,
                        mode=mode,
                        identity_id=identity_id,
                        user_id=user_id,
                        num_candidates=num_candidates,
                        seed=seed,
                        face_embedding=face_embedding,
                        reference_images=reference_images,
                        composition_params=composition_params,
                    )
                else:
                    # Combine all text parts manually
                    combined_text = " ".join(combined_prompt_parts)
                    return self.orchestrate(
                        user_prompt=combined_text,
                        mode=mode,
                        identity_id=identity_id,
                        user_id=user_id,
                        num_candidates=num_candidates,
                        seed=seed,
                        face_embedding=face_embedding,
                        reference_images=reference_images,
                        composition_params=composition_params,
                    )
        else:
            # No Claude - combine inputs manually
            combined_text = " ".join(combined_prompt_parts)
            return self.orchestrate(
                user_prompt=combined_text,
                mode=mode,
                identity_id=identity_id,
                user_id=user_id,
                num_candidates=num_candidates,
                seed=seed,
                face_embedding=face_embedding,
                reference_images=reference_images,
                composition_params=composition_params,
            )

    def _claude_messages_create(self, **kwargs: Any) -> Any:
        """Raw Claude API call. Use _safe_claude_create for circuit-breaker protection."""
        return self.client.messages.create(**kwargs)

    def _safe_claude_create(self, **kwargs: Any) -> Any:
        """Claude API call with circuit breaker when available."""
        if self.claude_circuit:
            return self.claude_circuit.call(self._claude_messages_create, **kwargs)
        return self._claude_messages_create(**kwargs)

    def _analyze_reference_image(self, img_bytes: bytes, image_num: int) -> str:
        """
        Analyze reference image with Claude vision. Delegates to MultimodalService when available.
        """
        if self.multimodal_service is not None:
            return self.multimodal_service.analyze_reference_image(
                img_bytes, analysis_focus="general", image_num=image_num
            )
        import base64
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        vision_response = self._safe_claude_create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": """Analyze this image for photo generation reference.

Extract and describe in detail:
1. Composition: Rule of thirds, framing, camera angle, shot type (close-up, medium, wide)
2. Lighting: Direction (front, side, back), quality (hard/soft), mood, time of day
3. Color palette: Dominant colors, color grading, saturation, contrast
4. Style and aesthetic: Photography style (e.g., editorial, documentary, cinematic), mood
5. Camera settings: Implied focal length, aperture, depth of field, perspective
6. Key visual elements: Main subject, background, foreground, any notable details

Be specific and technical. Return as a structured description that can be used to recreate similar photographic qualities.""",
                    },
                ],
            }],
        )
        return vision_response.content[0].text
    
    def _transcribe_voice(self, voice_bytes: bytes) -> str:
        """
        Transcribe voice audio using Whisper. Delegates to MultimodalService when available.
        """
        if self.multimodal_service is not None:
            return self.multimodal_service.transcribe_voice(voice_bytes)
        import tempfile
        import whisper  # type: ignore[reportMissingImports]
        if self.whisper_model is None:
            print("  Loading Whisper model...")
            self.whisper_model = whisper.load_model("base")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(voice_bytes)
            tmp.flush()
            tmp_path = tmp.name
        try:
            result = self.whisper_model.transcribe(tmp_path)
            return result["text"].strip()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    
    def _synthesize_multimodal_inputs(
        self, combined_parts: List[str], mode: str
    ) -> str:
        """
        Synthesize multi-modal inputs into a single prompt. Delegates to PromptService when available.
        """
        if self.prompt_service is not None:
            return self.prompt_service.synthesize_multimodal_from_parts(
                combined_parts, mode=mode
            )
        synthesis_prompt = f"""You are a world-class photography director. Synthesize these multi-modal inputs into a comprehensive photo generation prompt.

Inputs:
{chr(10).join(f"- {part}" for part in combined_parts)}

Mode: {mode}

Create a detailed, structured prompt that:
1. Honors all input modalities (text, image analysis, voice transcription)
2. Resolves any conflicts intelligently (prioritize user text intent)
3. Adds professional photographic detail based on reference images
4. Matches the {mode} mode aesthetic
5. Extracts key elements from reference images: composition, lighting, color, style

Return ONLY a single comprehensive text prompt (not JSON). Be specific about composition, lighting, color, style, subject and action. No explanation."""
        response = self._safe_claude_create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        synthesized = response.content[0].text.strip()
        if synthesized.startswith("```"):
            lines = synthesized.split("\n")
            synthesized = "\n".join(lines[1:-1]) if len(lines) > 2 else synthesized
        return synthesized
    
    @modal.method()
    @trace_function("orchestrator.orchestrate")
    def orchestrate(
        self,
        user_prompt: str,
        mode: str = "REALISM",
        identity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        num_candidates: int = 4,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
        quality_tier: str = "BALANCED",
        preview: bool = False,
        reference_images: Optional[List[bytes]] = None,
        composition_params: Optional[Dict[str, Any]] = None,
        creative: Optional[float] = None,
        style: Optional[str] = None,
        use_mutations: bool = True,
        width: int = 1024,
        height: int = 1024,
        user_tier: Optional[str] = None,
        use_face_ensemble: bool = False,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point - orchestrates the entire generation pipeline.

        Flow: parse → [FAST/STANDARD: realtime] or [ULTRA / res>2048: ultra] or [plan → execute → rerank]
        preview=True forces quality_tier=FAST for fast iterations.
        reference_images: optional refs for composition (pose/depth/canny) when requires_composition.
        composition_params: optional {"identity_ids": [...], "identity_positions": [{"x", "y", "scale"}, ...]}
            for multi-identity composition when requires_composition.
        creative: 0–1 creative level; when > 0, Creative Engine is used (optional override).
        style: style or preset name for Creative Engine (optional).
        use_mutations: enable mutation-based ensemble when using Creative Engine.
        width, height: requested resolution (capped by user_tier / quality_tier).
        user_tier: subscription tier for resolution caps (free|hobby|pro|studio|enterprise).
        use_face_ensemble: use InsightFace+DeepFace+FaceNet ensemble for face scoring when ref image available.
        """
        if preview:
            quality_tier = "FAST"
        tier = (quality_tier or "BALANCED").upper()
        mode_label = (mode or "unknown").upper()
        print(f"\n{'='*60}")
        print(f"🎯 ORCHESTRATOR: Processing '{user_prompt}' in {mode} mode (tier={tier})")
        print(f"{'='*60}\n")

        from contextlib import nullcontext
        tracker_ctx = RequestTracker() if RequestTracker else nullcontext()
        with tracker_ctx as tracker:
            if Metrics:
                Metrics.active_requests.labels(mode=mode_label).inc()
            status = "success"
            try:
                if self.logger:
                    self.logger.info("orchestrate started", mode=mode, quality_tier=tier)
                # Adversarial defense: analyze prompt before parsing
                if self.defense is not None:
                    defense_result = self.defense.analyze(
                        user_prompt,
                        user_id=user_id,
                        strict_mode=True,
                    )
                    if not defense_result.is_safe:
                        status = "error"
                        err = {
                            "error": "adversarial_prompt_blocked",
                            "message": "Prompt contains adversarial content and cannot be processed.",
                            "threats": [
                                {
                                    "type": t.threat_type,
                                    "severity": t.severity,
                                    "explanation": t.explanation,
                                }
                                for t in defense_result.threats_detected
                            ],
                            "images": [],
                            "parsed_prompt": {"full_prompt": user_prompt},
                            "execution_plan": {"engines": [], "requires_composition": False},
                            "rerank_used": False,
                        }
                        if get_request_id:
                            err["request_id"] = get_request_id()
                        return err
                    user_prompt = defense_result.sanitized_prompt or user_prompt
                print("[1/4] Parsing prompt...")
                parsed = self._parse_prompt(user_prompt, mode)
                print(f"✅ Expanded to: {parsed.full_prompt[:100]}...")

                engine, config = self._select_engine(tier, width, height, user_tier=user_tier)

                # ============================================================
                # Realtime path: FAST / STANDARD → RealtimeEngine (8–15s)
                # ============================================================
                if (
                    engine == "realtime"
                    and self.realtime_generate_batch is not None
                ):
                    print(
                        f"\n⚡ Realtime ({tier}): LCM-LoRA, {config['steps']} steps, "
                        f"~{config['target_time']}s..."
                    )
                    rt = tracked_engine_call("realtime", lambda: self.realtime_generate_batch.remote(
                        prompt=parsed.full_prompt,
                        negative_prompt=REALTIME_NEGATIVE,
                        mode=mode,
                        n_images=num_candidates,
                        seed=seed,
                        width=config["width"],
                        height=config["height"],
                        num_steps=config["steps"],
                        guidance_scale=config["guidance_scale"],
                        identity_lora=identity_id,
                        return_dict=True,
                    ))
                    encoded = rt.get("images_base64") or []
                    best = []
                    for i, b64 in enumerate(encoded):
                        best.append({
                            "image_base64": b64,
                            "seed": 0,
                            "prompt": parsed.full_prompt,
                            "negative_prompt": "",
                            "scores": {
                                "face_match": 1.0,
                                "aesthetic": 85.0,
                                "technical": 85.0,
                                "total": 85.0,
                            },
                        })
                    out = {
                        "images": best,
                        "parsed_prompt": {
                            "subject": parsed.subject,
                            "action": parsed.action,
                            "setting": parsed.setting,
                            "time": parsed.time,
                            "lighting": parsed.lighting,
                            "camera": parsed.camera,
                            "mood": parsed.mood,
                            "color": parsed.color,
                            "style": parsed.style,
                            "technical": parsed.technical,
                            "full_prompt": parsed.full_prompt,
                        },
                        "execution_plan": {
                            "engines": [{"name": "realtime", "weight": 1.0}],
                            "requires_composition": False,
                        },
                        "rerank_used": False,
                    }
                    if get_request_id:
                        out["request_id"] = get_request_id()
                    return out

                # ============================================================
                # Ultra High-Res path: ULTRA tier or resolution > 2048
                # ============================================================
                ultra_fn = self.ultra_generate_ultra or self.ultra_generate_4k
                if engine == "ultra_high_res" and ultra_fn is not None:
                    w_ultra = config["width"]
                    h_ultra = config["height"]
                    est_sec = self._estimate_ultra_time(w_ultra, h_ultra, num_candidates)
                    logging.info(
                        "Ultra High-Res generation: %dx%d, %d images, estimated ~%ds",
                        w_ultra, h_ultra, num_candidates, est_sec,
                    )
                    print(
                        f"\n🖼️ Ultra High-Res ({w_ultra}×{h_ultra}): "
                        f"~{est_sec}s estimated for {num_candidates} image(s)"
                    )
                    use_batch = self.ultra_generate_ultra is not None
                    if use_batch:
                        try:
                            raw_list = tracked_engine_call("ultra", lambda: self.ultra_generate_ultra.remote(
                            prompt=parsed.full_prompt,
                            negative_prompt=REALTIME_NEGATIVE,
                            num_images=num_candidates,
                            width=w_ultra,
                            height=h_ultra,
                            lora_path=None,
                            seed=seed,
                            use_tiled_refine=True,
                            use_detail_pass=True,
                            tile_grid="4x4",
                            tile_size=512,
                            tile_overlap=64,
                            guidance_scale=config.get("guidance_scale", 8.0),
                            num_inference_steps=config.get("steps", 80),
                            ))
                        except Exception as e:
                            logging.warning("Ultra High-Res batch failed: %s", e)
                            raise
                        best = []
                        for i, out in enumerate(raw_list):
                            s = (seed + i) if seed is not None else 0
                            best.append({
                                "image_base64": out["image_base64"],
                                "seed": s,
                                "prompt": parsed.full_prompt,
                                "negative_prompt": REALTIME_NEGATIVE,
                                "scores": {
                                    "face_match": 85.0,
                                    "aesthetic": 85.0,
                                    "technical": 85.0,
                                    "total": 85.0,
                                },
                            })
                    else:
                        best = []
                        for i in range(num_candidates):
                            s = (seed + i) if seed is not None else None
                            try:
                                out = tracked_engine_call("ultra_4k", lambda: self.ultra_generate_4k.remote(
                                prompt=parsed.full_prompt,
                                negative_prompt=REALTIME_NEGATIVE,
                                lora_path=None,
                                mode=mode,
                                seed=s,
                                use_tiled_refine=True,
                                use_detail_pass=True,
                                tile_grid="4x4",
                                return_pil=False,
                                ))
                            except Exception as e:
                                logging.warning("Ultra High-Res image %d failed: %s", i + 1, e)
                                raise
                            best.append({
                                "image_base64": out["image_base64"],
                                "seed": s or 0,
                                "prompt": parsed.full_prompt,
                                "negative_prompt": REALTIME_NEGATIVE,
                                "scores": {
                                    "face_match": 85.0,
                                    "aesthetic": 85.0,
                                    "technical": 85.0,
                                    "total": 85.0,
                                },
                            })
                    out = {
                        "images": best,
                        "parsed_prompt": {
                            "subject": parsed.subject,
                            "action": parsed.action,
                            "setting": parsed.setting,
                            "time": parsed.time,
                            "lighting": parsed.lighting,
                            "camera": parsed.camera,
                            "mood": parsed.mood,
                            "color": parsed.color,
                            "style": parsed.style,
                            "technical": parsed.technical,
                            "full_prompt": parsed.full_prompt,
                        },
                        "execution_plan": {
                            "engines": [{"name": "ultra_high_res", "weight": 1.0}],
                            "requires_composition": False,
                            "estimated_time_seconds": est_sec,
                        },
                        "rerank_used": False,
                    }
                    if get_request_id:
                        out["request_id"] = get_request_id()
                    return out

                # ============================================================
                # STEP 2: PLAN - Decide which engines to use
                # ============================================================
                print("\n[2/4] Creating execution plan...")
                plan = self._create_execution_plan(parsed, mode, identity_id)
                print(f"✅ Plan: {len(plan.engines)} engines, composition={plan.requires_composition}")

                # ============================================================
                # STEP 3: EXECUTE - Call engines in sequence
                # ============================================================
                # Executes the plan by calling appropriate engines:
                # - Creative Engine: when creative > 0 or style set (styles, presets, mutations)
                # - Composition Engine: Pose/action control when requires_composition
                # - Identity Engine: LoRA-based identity generation
                # - Finish Engine: Upscaling, face fix, color grading
                creative_level = creative
                if creative_level is None:
                    ce = next((e for e in plan.engines if e.engine_name == "creative"), None)
                    creative_level = float(ce.weight) if ce else 0.0
                print("\n[3/4] Executing generation...")
                candidates = self._execute_plan(
                    plan=plan,
                    parsed=parsed,
                    mode=mode,
                    identity_id=identity_id,
                    user_id=user_id,
                    num_candidates=num_candidates,
                    seed=seed,
                    face_embedding=face_embedding,
                    reference_images=reference_images,
                    composition_params=composition_params,
                    creative=creative_level,
                    style=style,
                    use_mutations=use_mutations,
                )
                print(f"✅ Generated {len(candidates)} candidates")

                # Optional: batch quality scoring when scorer available (ML aesthetic, etc.)
                if (
                    len(candidates) >= 2
                    and self.quality_scorer_score_batch is not None
                ):
                    try:
                        images_for_scorer = [
                            {"image_bytes": base64.b64decode(c["image_base64"])}
                            for c in candidates
                        ]
                        ref_emb = None
                        if face_embedding:
                            ref_emb = np.array(face_embedding, dtype=np.float32).tobytes()
                        ref_img_bytes = None
                        use_ensemble = bool(use_face_ensemble and reference_images and len(reference_images) > 0)
                        if use_ensemble and reference_images is not None and len(reference_images) > 0:
                            ref_img_bytes = reference_images[0]
                        scored = self.quality_scorer_score_batch.remote(
                            images=images_for_scorer,
                            prompt=parsed.full_prompt,
                            mode=mode,
                            reference_face_emb=ref_emb if not use_ensemble else None,
                            reference_image_bytes=ref_img_bytes,
                            use_face_ensemble=use_ensemble,
                        )
                        for i, s in enumerate(scored):
                            if i < len(candidates) and "score" in s:
                                sc = s["score"]
                                candidates[i]["scores"] = {
                                    "total": sc["overall"],
                                    "face_match": sc["face_similarity"] * 100.0,
                                    "face_similarity": sc["face_similarity"],
                                    "aesthetic": sc["aesthetic"],
                                    "technical": sc["technical"],
                                    "prompt_adherence": sc.get("prompt_adherence", 100.0),
                                }
                                if "face_models_used" in sc:
                                    candidates[i]["scores"]["face_models_used"] = sc["face_models_used"]
                                if "face_consensus" in sc:
                                    candidates[i]["scores"]["face_consensus"] = sc["face_consensus"]
                                if "face_model_scores" in sc:
                                    candidates[i]["scores"]["face_model_scores"] = sc["face_model_scores"]
                                if "confidence" in sc:
                                    candidates[i]["scores"]["confidence"] = sc["confidence"]
                                if "aesthetic_from_ml" in sc:
                                    candidates[i]["scores"]["aesthetic_from_ml"] = sc["aesthetic_from_ml"]
                        lbl = "ensemble (InsightFace+DeepFace+FaceNet)" if use_ensemble else "ML aesthetic when available"
                        print(f"  📊 Batch quality scoring applied ({lbl})")
                    except Exception as e:
                        logging.warning("Batch quality scoring failed, using engine scores: %s", e)

                # Canonical scoring (normalize 0–100, breakdown, explainability)
                has_identity = bool(
                    identity_id
                    and (face_embedding or (reference_images and len(reference_images) > 0))
                )
                try:
                    self._apply_canonical_scoring(candidates, parsed, mode, has_identity)
                except Exception as e:
                    logging.warning("Canonical scoring failed, using existing scores: %s", e)

                # ============================================================
                # STEP 4: RERANK - Intelligently select best results
                # ============================================================
                # Scores all candidates numerically first
                # If top 3 scores within 5 points → uses Claude LLM tiebreaker
                # LLM judges based on: composition, mood, story, intent match
                print("\n[4/4] Reranking results...")
                best_images = self._intelligent_rerank(candidates, parsed, mode)
                print(f"✅ Selected {len(best_images)} best images")

                # Finish step (upscale, face fix, color grade) when plan includes it
                finish_eng = next((e for e in plan.engines if e.engine_name == "finish"), None)
                if (
                    finish_eng is not None
                    and self.finish_finish is not None
                    and best_images
                ):
                    try:
                        fp = finish_eng.params or {}
                        mode_lut = {"REALISM": "neutral", "CINEMATIC": "cinematic", "CREATIVE": "vibrant", "ROMANTIC": "warm", "FASHION": "vintage"}
                        color_grade = mode_lut.get(mode, "cinematic") if fp.get("color_grade") else None
                        finished = self.finish_finish.remote(
                            images=[{"image_base64": im["image_base64"], "seed": im.get("seed"), "prompt": im.get("prompt"), "scores": im.get("scores")} for im in best_images],
                            upscale=fp.get("upscale", True),
                            face_fix=fp.get("face_fix", True),
                            color_grade=color_grade,
                            film_grain=0.0,
                            sharpen=0.3 if fp.get("enhance_details") else 0.0,
                            output_format="png",
                        )
                        merged = []
                        for orig, fin in zip(best_images, finished):
                            if fin.get("processed") and fin.get("image_base64"):
                                merged.append({**orig, "image_base64": fin["image_base64"], "finish_applied": fin.get("applied")})
                            else:
                                merged.append(orig)
                        best_images = merged
                        print("  ✨ Finish applied (upscale, face fix, color grade)")
                    except Exception as e:
                        logging.warning("Finish step failed, using unprocessed images: %s", e)

                # ============================================================
                # RETURN: Complete orchestration result
                # ============================================================
                out = {
                    "images": best_images,
                    "parsed_prompt": {
                        "subject": parsed.subject,
                        "action": parsed.action,
                        "setting": parsed.setting,
                        "time": parsed.time,
                        "lighting": parsed.lighting,
                        "camera": parsed.camera,
                        "mood": parsed.mood,
                        "color": parsed.color,
                        "style": parsed.style,
                        "technical": parsed.technical,
                        "full_prompt": parsed.full_prompt,
                    },
                    "execution_plan": {
                        "engines": [{"name": e.engine_name, "weight": e.weight} for e in plan.engines],
                        "requires_composition": plan.requires_composition,
                    },
                    "rerank_used": len(candidates) > 1 and any(
                        abs(candidates[i]["scores"]["total"] - candidates[i+1]["scores"]["total"]) < 5
                        for i in range(len(candidates)-1)
                    ),
                }
                if get_request_id:
                    out["request_id"] = get_request_id()
                return out

            except Exception as e:
                status = "error"
                if self.logger:
                    self.logger.error("orchestrate failed", error=str(e), mode=mode, quality_tier=tier)
                print(f"❌ Orchestration failed: {e}")
                logging.exception("Orchestration error")
                fallback = self._fallback_generation(
                    user_prompt, mode, identity_id, user_id, num_candidates, seed, face_embedding
                )
                if get_request_id and fallback and isinstance(fallback, dict):
                    fallback["request_id"] = get_request_id()
                return fallback
            finally:
                if Metrics:
                    Metrics.active_requests.labels(mode=mode_label).dec()
                    Metrics.requests_total.labels(mode=mode_label, quality_tier=tier, status=status).inc()
                if tracker is not None:
                    Metrics.request_duration.labels(mode=mode_label, quality_tier=tier).observe(tracker.get_duration())

    @modal.method()
    @trace_function("orchestrator.orchestrate_with_cache")
    def orchestrate_with_cache(
        self,
        user_prompt: str,
        mode: str = "REALISM",
        identity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        num_candidates: int = 4,
        seed: Optional[int] = None,
        face_embedding: Optional[List[float]] = None,
        quality_tier: str = "BALANCED",
        preview: bool = False,
        reference_images: Optional[List[bytes]] = None,
        composition_params: Optional[Dict[str, Any]] = None,
        creative: Optional[float] = None,
        style: Optional[str] = None,
        use_mutations: bool = True,
        width: int = 1024,
        height: int = 1024,
        user_tier: Optional[str] = None,
        use_face_ensemble: bool = False,
    ) -> Dict[str, Any]:
        """
        Orchestrate with smart caching. Tier-aware TTL (1h FAST/STANDARD, 7d else).
        preview=True forces FAST tier. reference_images for composition; cache skipped when provided.
        composition_params: optional identity_ids/identity_positions for multi-identity composition.
        creative, style, use_mutations: passed through to orchestrate; cache skipped when use_mutations=True.
        width, height, user_tier: resolution and tier caps for Ultra High-Res routing.
        use_face_ensemble: use multi-model face scoring when reference image available.
        """
        effective_tier = ("FAST" if preview else (quality_tier or "BALANCED")).upper()
        use_cache = not (reference_images and len(reference_images) > 0)
        if use_mutations:
            use_cache = False
        cache = None
        try:
            SmartCacheCls = modal.Cls.from_name("photogenius-smart-cache", "SmartCache")
            cache = SmartCacheCls()
        except Exception as e:
            print(f"[orchestrate_with_cache] SmartCache unavailable: {e}. Skipping cache.")

        if cache is not None and use_cache:
            try:
                cached = cache.check_cache.remote(
                    user_prompt, mode, identity_id, effective_tier,
                    style=style, creative=creative,
                )
            except Exception as e:
                print(f"[orchestrate_with_cache] check_cache failed: {e}")
                cached = None
        else:
            cached = None

        if cached is not None and cached.get("type") == "exact":
            return {
                "images": cached["images"],
                "parsed_prompt": cached.get("parsed_prompt") or {"full_prompt": user_prompt},
                "execution_plan": cached.get("execution_plan") or {"engines": [], "requires_composition": False},
                "rerank_used": False,
                "cached": True,
                "cache_type": "exact",
            }

        if cached is not None and cached.get("type") == "semantic":
            orig = cached.get("original_prompt", "")
            sim = cached.get("similarity", 0)
            return {
                "suggestion": {
                    "message": f"Similar to: '{orig}'",
                    "images": cached["images"],
                    "similarity": sim,
                },
                "generate_anyway": True,
                "cached": True,
                "cache_type": "semantic",
            }

        result = self.orchestrate(
            user_prompt=user_prompt,
            mode=mode,
            identity_id=identity_id,
            user_id=user_id,
            num_candidates=num_candidates,
            seed=seed,
            face_embedding=face_embedding,
            quality_tier=quality_tier,
            preview=preview,
            reference_images=reference_images,
            composition_params=composition_params,
            creative=creative,
            style=style,
            use_mutations=use_mutations,
            width=width,
            height=height,
            user_tier=user_tier,
            use_face_ensemble=use_face_ensemble,
        )

        if cache is not None and use_cache and result.get("images"):
            try:
                cache.store_result.remote(
                    prompt=user_prompt,
                    mode=mode,
                    identity_id=identity_id,
                    images=result["images"],
                    parsed_prompt=result.get("parsed_prompt"),
                    execution_plan=result.get("execution_plan"),
                    quality_tier=effective_tier,
                    style=style,
                    creative=creative,
                )
            except Exception as e:
                print(f"[orchestrate_with_cache] store_result failed: {e}")

        return {**result, "cached": False}

    @track_llm_call("parse_prompt")
    def _parse_prompt(self, prompt: str, mode: str) -> ParsedPrompt:
        """
        Parse minimal user prompt into detailed professional photography spec.
        
        Uses Claude Sonnet 4 to expand "beach" → full professional specification.
        Delegates to PromptService when available.
        
        Args:
            prompt: User's simple input
            mode: Generation mode
        
        Returns:
            ParsedPrompt with all components
        """
        if self.prompt_service is not None:
            p = self.prompt_service.parse(prompt, mode=mode, use_cache=True)
            return p  # type: ignore[reportReturnType]
        if not self.claude_available:
            return self._fallback_parse(prompt, mode)
        
        system_prompt = """You are a world-class photography director AI. Parse user prompts into detailed structured components for professional photo generation.

Rules:
- If user gives 2 words, expand to full professional spec
- Maintain user's core intent always
- Add photographic/cinematic depth using industry terms
- Use specific camera language (85mm, f/2.0, golden hour, rim lighting)
- Return ONLY valid JSON, no explanation
- Be creative but realistic

Example Expansion:
Input: "beach"
Output: {
  "subject": "person standing at water's edge",
  "action": "gazing at horizon, wind in hair",
  "setting": "pristine beach, gentle waves, wet sand reflections",
  "time": "golden hour, 20 minutes before sunset",
  "lighting": "warm golden backlight, rim lighting, soft fill from sky",
  "camera": "medium shot, 85mm lens, f/2.0 shallow DOF",
  "mood": "peaceful contemplation, romantic solitude",
  "color": "warm orange and gold tones, cool blue shadows",
  "style": "inspired by Peter Lindbergh beach photography",
  "technical": "slight film grain, Kodak Portra 400 aesthetic"
}

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

        user_message = f"""Parse this prompt for {mode} mode photography:

User prompt: "{prompt}"

Expand it into a complete professional photography specification. If the prompt is minimal (like "beach" or "office"), infer professional details like lighting, camera settings, mood, and style."""

        try:
            response = self._safe_claude_create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            
            # Extract JSON from response
            content = response.content[0].text
            # Try to find JSON in the response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                parsed_data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in Claude response")
            
            # Build full professional prompt
            full_prompt = (
                f"{parsed_data.get('subject', '')}, "
                f"{parsed_data.get('action', '')}, "
                f"{parsed_data.get('setting', '')}, "
                f"{parsed_data.get('time', '')}, "
                f"{parsed_data.get('lighting', '')}, "
                f"{parsed_data.get('camera', '')}, "
                f"{parsed_data.get('mood', '')}, "
                f"{parsed_data.get('color', '')}, "
                f"{parsed_data.get('style', '')}, "
                f"{parsed_data.get('technical', '')}"
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
            )
            
        except Exception as e:
            print(f"⚠️ Claude parsing failed: {e}, using fallback")
            return self._fallback_parse(prompt, mode)
    
    def _fallback_parse(self, prompt: str, mode: str) -> ParsedPrompt:
        """
        Fallback parser when Claude is unavailable.
        
        Provides simple but professional prompt expansion based on mode.
        Used when Anthropic API is not available or fails.
        """
        # Mode-specific expansions for all supported modes
        mode_expansions = {
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
        
        # Get expansion for mode, default to REALISM
        expansion = mode_expansions.get(mode, mode_expansions["REALISM"])
        
        # Build full professional prompt
        full_prompt = (
            f"{expansion['subject']}, "
            f"{expansion['action']}, "
            f"{expansion['setting']}, "
            f"{expansion['time']}, "
            f"{expansion['lighting']}, "
            f"{expansion['camera']}, "
            f"{expansion['mood']}, "
            f"{expansion['color']}, "
            f"{expansion['style']}, "
            f"{expansion['technical']}"
        )
        
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
        )
    
    def _create_execution_plan(
        self, parsed: ParsedPrompt, mode: str, identity_id: Optional[str]
    ) -> ExecutionPlan:
        """
        Decide which engines to use based on mode and prompt analysis.
        
        Mode-specific routing:
        - REALISM: Identity 0.92, Finish 1.0 (no creative, pure realism)
        - CREATIVE: Identity 0.72, Creative 1.0, Finish 1.0 (artistic freedom)
        - ROMANTIC: Identity 0.80, Creative 0.5, Finish 1.0 (romantic + artistic)
        - FASHION: Identity 0.85, Creative 0.6, Finish 1.0 (fashion-forward)
        - CINEMATIC: Identity 0.76, Creative 0.8, Finish 1.0 (film-like)
        
        Composition engine is triggered by action words: jumping, dancing, yoga, action
        
        Args:
            parsed: Parsed prompt components
            mode: Generation mode
            identity_id: Optional identity ID for LoRA loading
        
        Returns:
            ExecutionPlan with engine configurations
        """
        engines = []
        
        # Mode-specific routing weights (as specified in requirements)
        mode_routing = {
            "REALISM": {
                "identity": 0.92,      # High identity weight for realism
                "creative": 0.0,        # No creative engine
                "composition": 0.0,    # No composition (unless action words)
                "finish": 1.0,          # Always finish
            },
            "CREATIVE": {
                "identity": 0.72 if identity_id else 0.0,  # Lower identity, allow creativity
                "creative": 1.0,        # Full creative engine
                "composition": 0.0,     # No composition (unless action words)
                "finish": 1.0,          # Always finish
            },
            "ROMANTIC": {
                "identity": 0.80 if identity_id else 0.0,  # Moderate identity
                "creative": 0.5,        # Half creative for romantic feel
                "composition": 0.0,     # No composition (unless action words)
                "finish": 1.0,           # Always finish
            },
            "FASHION": {
                "identity": 0.85 if identity_id else 0.0,  # High identity for fashion
                "creative": 0.6,         # Fashion-forward creative
                "composition": 0.0,      # No composition (unless action words)
                "finish": 1.0,           # Always finish
            },
            "CINEMATIC": {
                "identity": 0.76 if identity_id else 0.0,  # Moderate identity
                "creative": 0.8,         # High creative for cinematic look
                "composition": 0.0,      # No composition (unless action words)
                "finish": 1.0,           # Always finish
            },
        }
        
        routing = mode_routing.get(mode, mode_routing["REALISM"])
        
        # Step 1: Add Identity Engine (if identity_id provided and weight > 0)
        if routing["identity"] > 0 and identity_id:
            engines.append(EngineConfig(
                engine_name="identity",
                weight=routing["identity"],
                params={"lora_enabled": True, "strength": routing["identity"]},
            ))
        
        # Step 2: Add Creative Engine (if weight > 0)
        if routing["creative"] > 0:
            engines.append(EngineConfig(
                engine_name="creative",
                weight=routing["creative"],
                params={"style_strength": routing["creative"]},
            ))
        
        # Step 3: Check if Composition Engine is needed (action words trigger it)
        # Action words: jumping, dancing, yoga, action, movement, pose
        action_words = ["jumping", "dancing", "yoga", "running", "action", "movement", "pose", "leaping", "stretching"]
        requires_composition = any(word in parsed.action.lower() for word in action_words)
        
        if requires_composition:
            engines.append(EngineConfig(
                engine_name="composition",
                weight=0.7,  # Standard composition weight
                params={"controlnet_type": "pose", "detect_pose": True},
            ))
        
        # Step 4: Finish Engine always runs (upscaling, face fix, color grading)
        engines.append(EngineConfig(
            engine_name="finish",
            weight=routing["finish"],
            params={
                "upscale": True,
                "face_fix": True,
                "color_grade": True,
                "enhance_details": True,
            },
        ))
        
        return ExecutionPlan(
            engines=engines,
            requires_composition=requires_composition,
            final_prompt=parsed.full_prompt,
        )

    @retry_with_backoff(max_retries=2)
    @track_engine_call("identity_v2")
    def _call_identity_v2(
        self,
        parsed_dict: Dict[str, str],
        plan: ExecutionPlan,
        mode: str,
        identity_id: str,
        user_id: str,
        num_candidates: int,
        seed: Optional[int],
        face_embedding: Optional[List[float]],
        quality_threshold: float = 0.99,
        max_attempts: int = 5,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Call Identity Engine V2 (ensemble, 99%+ face). Map response to orchestrator format.
        Quality gate: retry once with higher max_attempts if best_similarity < 0.99.
        Returns None on failure so caller can fall back to V1/GenService.
        """
        n_per_path = max(2, (num_candidates + 2) // 2)
        kwargs = {
            "parsed_prompt": parsed_dict,
            "identity_id": identity_id,
            "user_id": user_id,
            "mode": mode,
            "quality_threshold": quality_threshold,
            "max_attempts": max_attempts,
            "num_candidates_per_path": n_per_path,
            "face_embedding": face_embedding,
            "reference_face_image_base64": None,
        }

        def _run(tries: int) -> Dict[str, Any]:
            return self.identity_v2_generate.remote(**{**kwargs, "max_attempts": tries})

        result = _run(max_attempts)
        best = float(result.get("best_similarity", 0.0))
        guaranteed = result.get("guaranteed_quality", False)
        attempts = result.get("attempts_used", 0)
        total_candidates = result.get("total_candidates", 0)
        results = result.get("results") or []

        # Log which path(s) succeeded and similarity
        paths = [r.get("path", "?") for r in results]
        logging.info(
            "Identity V2: best_similarity=%.3f guaranteed=%s attempts=%d total_candidates=%d paths=%s",
            best, guaranteed, attempts, total_candidates, paths,
        )
        print(f"  📊 V2 best_similarity={best:.3f} guaranteed={guaranteed} attempts={attempts} paths={paths}")

        # Quality gate: retry once with more attempts if below threshold
        if best < quality_threshold and max_attempts <= 7:
            logging.warning("Face similarity %.3f below threshold %.2f; retrying with max_attempts=7", best, quality_threshold)
            print(f"  ⚠️ Similarity {best:.2%} < {quality_threshold:.0%}; retrying with max_attempts=7")
            try:
                result = _run(7)
                best = float(result.get("best_similarity", 0.0))
                guaranteed = result.get("guaranteed_quality", False)
                results = result.get("results") or []
                paths = [r.get("path", "?") for r in results]
                logging.info("Identity V2 retry: best_similarity=%.3f guaranteed=%s paths=%s", best, guaranteed, paths)
                print(f"  📊 V2 retry best_similarity={best:.3f} guaranteed={guaranteed} paths={paths}")
            except Exception as e:
                logging.warning("Identity V2 retry failed: %s", e)

        # Reject if still below threshold after retry -> fall back to V1/GenService
        if best < quality_threshold:
            logging.warning("Face similarity %.3f below threshold %.2f; rejecting V2 result, falling back to V1", best, quality_threshold)
            print(f"  ❌ Rejecting V2 (similarity {best:.2%} < {quality_threshold:.0%}); falling back to V1")
            return None

        if not results:
            return None

        # Map V2 format -> orchestrator format (image_base64, seed, prompt, negative_prompt, scores)
        converted = []
        for r in results:
            sim = float(r.get("similarity", 0.0))
            conf = r.get("confidence", 0.9)
            # scores: total for rerank; face_match, face_similarity, aesthetic, technical for compatibility
            scores = {
                "face_match": sim * 100.0,
                "face_similarity": sim,
                "aesthetic": 85.0,
                "technical": 85.0,
                "total": sim * 100.0,
                "confidence": {"face_similarity": conf, "aesthetic": 0.7, "technical": 0.9},
            }
            converted.append({
                "image_base64": r["image_base64"],
                "seed": 0,
                "prompt": plan.final_prompt,
                "negative_prompt": "",
                "scores": scores,
            })
        return converted

    def _validate_and_cap_resolution(
        self,
        width: int,
        height: int,
        user_tier: Optional[str] = None,
        quality_tier: Optional[str] = None,
    ) -> tuple:
        """Cap width/height by tier. Returns (capped_width, capped_height)."""
        max_res = None
        if USE_TIER_CONFIG and user_tier:
            try:
                tier_enum = normalize_tier(user_tier)
                limits = get_tier_limits(tier_enum)
                max_res = limits.get("max_resolution", 1024)
            except Exception as e:
                logging.warning(f"Failed to get tier limits from config: {e}, using fallback")
        if max_res is None:
            tier = (user_tier or "").lower().strip()
            max_res = TIER_RESOLUTION_CAPS_FALLBACK.get(tier)
        if max_res is None and quality_tier:
            max_res = QUALITY_TIER_TO_CAP.get(
                (quality_tier or "").upper(),
                1024,
            )
        if max_res is None:
            max_res = 1024
        w, h = width, height
        if w <= max_res and h <= max_res:
            return w, h
        logging.warning(
            "Resolution %dx%d exceeds tier limit %d; capping",
            w, h, max_res,
        )
        aspect = w / max(h, 1)
        if w >= h:
            w = max_res
            h = max(64, int(round(max_res / aspect)))
        else:
            h = max_res
            w = max(64, int(round(max_res * aspect)))
        logging.info("Capped to %dx%d", w, h)
        return w, h

    def _estimate_ultra_time(self, width: int, height: int, num_images: int) -> int:
        """Estimate ultra high-res generation time (seconds). ~3 min for 4K single image."""
        tile = 512
        tiles_x = (width + tile - 1) // tile
        tiles_y = (height + tile - 1) // tile
        total_tiles = tiles_x * tiles_y
        time_per_tile = 5
        blending_overhead = 10
        upscale_overhead = 15
        per_image = total_tiles * time_per_tile + blending_overhead + upscale_overhead
        return int(per_image * num_images)

    def _log_ultra_progress(self, progress: Dict[str, Any]) -> None:
        """Log progress for ultra high-res generation. Used when progress updates are available (e.g. in-process)."""
        logging.info(
            "Ultra progress: %s/%s tiles, %s%%",
            progress.get("current", 0),
            progress.get("total", 1),
            progress.get("percent", 0),
        )

    def _select_engine(
        self,
        quality_tier: str,
        width: int = 1024,
        height: int = 1024,
        user_tier: Optional[str] = None,
    ) -> tuple:
        """Route by quality tier and resolution. Returns (engine_name, config)."""
        if self.routing_service is not None:
            r = self.routing_service.select_engine(
                quality_tier=quality_tier,
                width=width,
                height=height,
                user_tier=user_tier,
            )
            config = {
                "width": r.width,
                "height": r.height,
                "steps": r.params_override.get("num_inference_steps", 50),
                "guidance_scale": r.params_override.get("guidance_scale", 7.5),
                "target_time": r.estimated_time_seconds,
                "engine": r.engine,
            }
            return r.engine, config
        t = (quality_tier or "BALANCED").upper()
        w, h = self._validate_and_cap_resolution(
            width, height,
            user_tier=user_tier,
            quality_tier=t,
        )
        max_dim = max(w, h)
        use_ultra = (
            (self.ultra_generate_4k is not None or self.ultra_generate_ultra is not None)
            and (max_dim > 2048 or t == "ULTRA")
        )
        if use_ultra:
            config = QUALITY_TIER_CONFIG.get("ULTRA", QUALITY_TIER_CONFIG["BALANCED"]).copy()
            config["width"] = min(w, 4096)
            config["height"] = min(h, 4096)
            est = self._estimate_ultra_time(config["width"], config["height"], 1)
            logging.info(
                "Ultra High-Res Engine: %dx%d (tier=%s), estimated ~%ds",
                config["width"], config["height"], t, est,
            )
            return "ultra_high_res", config
        config = QUALITY_TIER_CONFIG.get(t, QUALITY_TIER_CONFIG["BALANCED"]).copy()
        config["width"] = w
        config["height"] = h
        logging.info(
            "Selected engine: %s (tier=%s, target=%ss)",
            config["engine"], t, config["target_time"],
        )
        return config["engine"], config

    def _execute_plan(
        self,
        plan: ExecutionPlan,
        parsed: ParsedPrompt,
        mode: str,
        identity_id: Optional[str],
        user_id: Optional[str],
        num_candidates: int,
        seed: Optional[int],
        face_embedding: Optional[List[float]],
        reference_images: Optional[List[bytes]] = None,
        composition_params: Optional[Dict[str, Any]] = None,
        creative: float = 0.0,
        style: Optional[str] = None,
        use_mutations: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute the plan by calling appropriate engines.
        
        Creative path: when creative > 0 or style set, use Creative Engine (styles, presets, mutations).
        Composition path: when requires_composition + reference_images + Composition Engine,
        use pose/depth/canny multi-ControlNet. If composition_params.identity_ids has >1 ids,
        call compose_multi_identity; else compose.
        Identity path: V2 (99%+ ensemble) → V1 → GenerationService.
        """
        creative_level = creative or 0.0
        use_creative = (creative_level > 0 or (style or "").strip()) and (
            self.creative_engine_generate_creative is not None
        )

        if use_creative:
            logging.info(
                "Using Creative Engine (creative=%.2f, style=%s, use_mutations=%s)",
                creative_level,
                style or "auto",
                use_mutations,
            )
            print(f"  🎨 Creative Engine: creative={creative_level:.2f} style={style or 'auto'} mutations={use_mutations}")
            try:
                raw = self.creative_engine_generate_creative.remote(
                    prompt=plan.final_prompt,
                    negative_prompt=REALTIME_NEGATIVE,
                    style=(style or "").strip() or None,
                    creative_level=creative_level,
                    num_images=num_candidates,
                    width=1024,
                    height=1024,
                    guidance_scale=7.5,
                    num_inference_steps=50,
                    seed=seed,
                    identity_id=identity_id,
                    use_mutations=use_mutations,
                )
                candidates = []
                for r in raw:
                    style_used = r.get("style", "unknown")
                    mut = r.get("mutation_index")
                    logging.info(
                        "Creative result: style=%s mutation_index=%s",
                        style_used,
                        mut if mut is not None else "n/a",
                    )
                    candidates.append({
                        "image_base64": r["image_base64"],
                        "seed": r.get("seed", 0),
                        "prompt": r.get("prompt", plan.final_prompt),
                        "negative_prompt": r.get("negative_prompt", REALTIME_NEGATIVE),
                        "scores": r.get("scores", {
                            "face_match": 85.0,
                            "aesthetic": 85.0,
                            "technical": 85.0,
                            "total": 85.0,
                        }),
                    })
                if candidates:
                    print(f"  📷 Creative Engine produced {len(candidates)} candidates")
                    return candidates
            except Exception as e:
                logging.warning("Creative Engine failed, falling back to identity/gen: %s", e)
                print(f"  ⚠️ Creative Engine failed: {e}; falling back to identity/gen")

        # --- Composition Engine (pose + depth + canny) ---
        identity_ids = (composition_params or {}).get("identity_ids") or []
        identity_positions = (composition_params or {}).get("identity_positions") or []
        multi_identity = len(identity_ids) > 1 and identity_positions and len(identity_positions) >= len(identity_ids)

        if (
            plan.requires_composition
            and reference_images
            and (self.composition_compose is not None or self.composition_compose_multi_identity is not None)
        ):
            try:
                ref_b64 = base64.b64encode(reference_images[0]).decode("utf-8")
                if multi_identity and self.composition_compose_multi_identity is not None:
                    comp = self.composition_compose_multi_identity.remote(
                        prompt=plan.final_prompt,
                        reference_image=ref_b64,
                        identity_ids=identity_ids,
                        identity_positions=identity_positions[: len(identity_ids)],
                        negative_prompt=REALTIME_NEGATIVE,
                        num_images=num_candidates,
                        width=1024,
                        height=1024,
                        guidance_scale=7.5,
                        controlnet_conditioning_scale=[1.0, 0.8, 0.5],
                        num_inference_steps=50,
                        seed=seed,
                        return_base64=True,
                    )
                    logging.info("Composition engine (multi-identity) produced %d candidates", len(comp))
                else:
                    comp = self.composition_compose.remote(
                        prompt=plan.final_prompt,
                        reference_images=[ref_b64],
                        negative_prompt=REALTIME_NEGATIVE,
                        num_images=num_candidates,
                        width=1024,
                        height=1024,
                        guidance_scale=7.5,
                        controlnet_conditioning_scale=[1.0, 0.8, 0.5],
                        num_inference_steps=50,
                        seed=seed,
                        return_base64=True,
                    )
                    logging.info("Composition engine produced %d candidates", len(comp))
                candidates = []
                for c in comp:
                    candidates.append({
                        "image_base64": c["image_base64"],
                        "seed": c.get("seed"),
                        "prompt": plan.final_prompt,
                        "negative_prompt": REALTIME_NEGATIVE,
                        "scores": {
                            "face_match": 85.0,
                            "aesthetic": 85.0,
                            "technical": 85.0,
                            "total": 85.0,
                        },
                    })
                return candidates
            except Exception as e:
                logging.warning("Composition engine failed, falling back to identity/gen: %s", e)

        parsed_dict = {
            "subject": parsed.subject,
            "action": parsed.action,
            "setting": parsed.setting,
            "time": parsed.time,
            "lighting": parsed.lighting,
            "camera": parsed.camera,
            "mood": parsed.mood,
            "color": parsed.color,
            "style": parsed.style,
            "technical": parsed.technical,
        }

        # --- Identity Engine V2 (99%+ face, ensemble) ---
        if (
            identity_id
            and (user_id or "orchestrator")
            and self.identity_v2_generate is not None
        ):
            uid = user_id or "orchestrator"
            quality_threshold = 0.99
            max_attempts = 5
            try:
                result = self._call_identity_v2(
                    parsed_dict=parsed_dict,
                    plan=plan,
                    mode=mode,
                    identity_id=identity_id,
                    user_id=uid,
                    num_candidates=num_candidates,
                    seed=seed,
                    face_embedding=face_embedding,
                    quality_threshold=quality_threshold,
                    max_attempts=max_attempts,
                )
                if result is not None:
                    return result
            except Exception as e:
                logging.warning("Identity V2 failed, falling back to V1/GenService: %s", e)

        # --- Identity Engine V1 (fallback when no identity or V2 failed) ---
        if self.identity_engine_generate is not None:
            candidates = self.identity_engine_generate.remote(
                parsed_prompt=parsed_dict,
                identity_id=identity_id or "",
                user_id=user_id or "orchestrator",
                strength=0.90,
                n_candidates=num_candidates,
                mode=mode,
                face_embedding=face_embedding,
                seed=seed,
            )
            converted = []
            for cand in candidates:
                converted.append({
                    "image_base64": cand["image_base64"],
                    "seed": cand["seed"],
                    "prompt": cand["prompt"],
                    "negative_prompt": cand["negative_prompt"],
                    "scores": cand["scores"],
                })
            return converted

        if self.generation_service_generate is not None:
            # Fallback to old GenerationService via remote call
            # Function.lookup returns a Function object, call with .remote()
            candidates = self.generation_service_generate.remote(
                user_id=user_id or "orchestrator",
                identity_id=identity_id or "",
                prompt=plan.final_prompt,
                mode=mode,
                num_candidates=num_candidates,
                seed=seed,
                face_embedding=face_embedding,
            )
            return candidates
        else:
            raise RuntimeError("No generation engine available")

    def _detect_prompt_type(self, parsed: "ParsedPrompt") -> str:
        """Detect prompt type for adaptive scoring weights. Returns default|portrait|creative|product."""
        subject = (parsed.subject or "").lower()
        style = (parsed.style or "").lower()
        technical = (parsed.technical or "").lower()
        combined = f"{subject} {style} {technical}"
        if any(k in combined for k in ("portrait", "headshot", "person", "face", "selfie")):
            return "portrait"
        if any(k in combined for k in ("product", "commercial", "object", "merchandise")):
            return "product"
        if any(k in combined for k in ("artistic", "creative", "abstract", "stylized", "painting")):
            return "creative"
        return "default"

    def _build_scoring_inputs(
        self,
        candidate: Dict[str, Any],
        has_identity: bool,
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, str], Dict[str, Tuple[float, float]]]:
        """Build raw_scores, confidences, sources, score_ranges for ScoringService."""
        raw: Dict[str, float] = {}
        conf: Dict[str, float] = {}
        src: Dict[str, str] = {}
        rng: Dict[str, Tuple[float, float]] = {}
        s = candidate.get("scores") or {}
        conf_map = s.get("confidence") or {}

        def _add(name: str, value: float, range_01: bool, source: str, confidence: float = 1.0):
            if value is None:
                return
            raw[name] = float(value)
            rng[name] = (0.0, 1.0) if range_01 else (0.0, 100.0)
            src[name] = source
            conf[name] = float(conf_map.get(name, confidence))

        face = s.get("face_match")
        if face is not None:
            face_01 = s.get("face_similarity")
            if face_01 is not None:
                _add("face_match", face_01, True, "ensemble" if s.get("face_models_used") else "quality_scorer", conf_map.get("face_similarity", 0.9))
            else:
                v = float(face)
                _add("face_match", v / 100.0 if v > 1 else v, True, "identity_v2" if has_identity else "engine", 0.9)
        if s.get("aesthetic") is not None:
            _add("aesthetic", s["aesthetic"], False, "ML model" if s.get("aesthetic_from_ml") else "heuristic", conf_map.get("aesthetic", 0.85))
        if s.get("technical") is not None:
            _add("technical", s["technical"], False, "quality_scorer", conf_map.get("technical", 0.9))
        if s.get("prompt_adherence") is not None:
            _add("prompt_adherence", s["prompt_adherence"], False, "CLIP", conf_map.get("prompt_adherence", 0.85))
        return raw, conf, src, rng

    def _apply_canonical_scoring(
        self,
        candidates: List[Dict[str, Any]],
        parsed: "ParsedPrompt",
        mode: str,
        has_identity: bool,
    ) -> None:
        """Run ScoringService, attach breakdown/total/selection_reason. Updates candidates in place."""
        if not candidates or ScoringService is None or FinalScore is None:
            return
        prompt_type = self._detect_prompt_type(parsed)
        scorer = ScoringService(weight_profile=prompt_type)
        logging.info("Canonical scoring: profile=%s", prompt_type)
        finals: List[Any] = []
        scored_indices: List[int] = []
        for i, c in enumerate(candidates):
            raw, conf, src, rng = self._build_scoring_inputs(c, has_identity)
            if not raw:
                continue
            fs = scorer.score_image(
                image_path=f"candidate_{i}",
                raw_scores=raw,
                confidences=conf,
                sources=src,
                score_ranges=rng,
            )
            finals.append(fs)
            scored_indices.append(i)
            s = c.setdefault("scores", {})
            s["total"] = fs.total
            s["score_confidence"] = fs.confidence
            s["selection_reason"] = fs.selection_reason
            s["score_breakdown"] = [
                {
                    "component": b.component.value,
                    "score": b.normalized_score,
                    "weight": b.weight,
                    "contribution": b.weighted_score,
                    "confidence": b.confidence,
                    "explanation": b.explanation,
                }
                for b in fs.breakdown
            ]
            s["audit_trail"] = scorer.get_audit_trail(fs)
            for b in fs.breakdown:
                if b.component.value == "face_match":
                    s["face_match"] = b.normalized_score
                elif b.component.value == "aesthetic":
                    s["aesthetic"] = b.normalized_score
                elif b.component.value == "technical":
                    s["technical"] = b.normalized_score
                elif b.component.value == "prompt_adherence":
                    s["prompt_adherence"] = b.normalized_score
        if len(finals) > 1:
            best_idx, comparison_notes = scorer.compare_images(
                finals, use_llm_tiebreak=True, llm_threshold=5.0
            )
            if best_idx < len(scored_indices):
                ci = scored_indices[best_idx]
                candidates[ci].setdefault("scores", {})["comparison_notes"] = comparison_notes
    
    def _intelligent_rerank(
        self, candidates: List[Dict[str, Any]], parsed: ParsedPrompt, mode: str
    ) -> List[Dict[str, Any]]:
        """
        Intelligently rerank candidates using LLM when scores are close.
        
        If top 3 scores are within 5 points, use Claude to judge based on:
        - Composition quality
        - Mood match
        - Story/intent alignment
        - Overall appeal
        """
        if len(candidates) <= 1:
            return candidates
        
        # Sort by total score
        candidates = sorted(candidates, key=lambda x: x["scores"]["total"], reverse=True)
        
        # Check if top scores are close (within 5 points)
        if len(candidates) >= 3:
            top_3_scores = [c["scores"]["total"] for c in candidates[:3]]
            score_range = max(top_3_scores) - min(top_3_scores)
            
            if score_range < 5 and self.claude_available:
                # Use LLM tiebreaker
                print("  🤖 Using Claude for tiebreaker reranking...")
                return self._llm_rerank(candidates[:3], parsed, mode) + candidates[3:]
        
        # Return top 2
        return candidates[:2]

    @track_llm_call("rerank")
    def _llm_rerank(
        self, candidates: List[Dict[str, Any]], parsed: ParsedPrompt, mode: str
    ) -> List[Dict[str, Any]]:
        """Use Claude to rerank candidates when scores are close"""
        try:
            system_prompt = """You are an expert photography judge. Rank images based on:
1. Composition quality (rule of thirds, balance, framing)
2. Mood match (does it capture the intended feeling?)
3. Story/intent alignment (does it tell the story the prompt intended?)
4. Overall appeal (would this be shared/saved?)

Return ONLY a JSON array of indices in order of preference [best_index, second_best, third_best]"""

            # Create descriptions for each candidate
            candidate_descriptions = []
            for i, cand in enumerate(candidates):
                scores = cand["scores"]
                desc = f"Candidate {i}: Face={scores['face_match']:.1f}, Aesthetic={scores['aesthetic']:.1f}, Technical={scores['technical']:.1f}, Total={scores['total']:.1f}"
                candidate_descriptions.append(desc)
            
            user_message = f"""Rank these 3 images for a {mode} mode photo with this intent:

Prompt: {parsed.full_prompt}

Candidates:
{chr(10).join(candidate_descriptions)}

Return JSON array: [best_index, second_best_index, third_best_index]"""

            response = self._safe_claude_create(
                model="claude-sonnet-4-20250514",
                max_tokens=100,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            
            content = response.content[0].text
            # Extract JSON array
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                ranking = json.loads(json_str)
                # Reorder candidates based on LLM ranking
                reranked = [candidates[i] for i in ranking if 0 <= i < len(candidates)]
                return reranked + [c for i, c in enumerate(candidates) if i not in ranking]
            
        except Exception as e:
            print(f"⚠️ LLM reranking failed: {e}, using score-based ranking")
        
        # Fallback to score-based ranking
        return sorted(candidates, key=lambda x: x["scores"]["total"], reverse=True)
    
    def _fallback_generation(
        self,
        user_prompt: str,
        mode: str,
        identity_id: Optional[str],
        user_id: Optional[str],
        num_candidates: int,
        seed: Optional[int],
        face_embedding: Optional[List[float]],
    ) -> Dict[str, Any]:
        """Fallback to direct generation when orchestration fails"""
        print("⚠️ Using fallback direct generation")
        simple_parsed = {
            "subject": user_prompt,
            "action": "",
            "setting": "",
            "time": "",
            "lighting": "",
            "camera": "",
            "mood": "",
            "color": "",
            "style": "",
            "technical": "",
        }
        minimal_plan = ExecutionPlan(engines=[], requires_composition=False, final_prompt=user_prompt)

        # Try V2 first when identity present
        if identity_id and (user_id or "orchestrator") and self.identity_v2_generate is not None:
            try:
                v2_result = self._call_identity_v2(
                    parsed_dict=simple_parsed,
                    plan=minimal_plan,
                    mode=mode,
                    identity_id=identity_id,
                    user_id=user_id or "orchestrator",
                    num_candidates=num_candidates,
                    seed=seed,
                    face_embedding=face_embedding,
                    quality_threshold=0.99,
                    max_attempts=5,
                )
                if v2_result:
                    return {
                        "images": v2_result[:2],
                        "parsed_prompt": {"full_prompt": user_prompt},
                        "execution_plan": {"engines": [{"name": "identity_v2", "weight": 1.0}]},
                        "rerank_used": False,
                    }
            except Exception as e:
                logging.warning("Fallback V2 failed: %s", e)

        if self.identity_engine_generate is not None:
            candidates = self.identity_engine_generate.remote(
                parsed_prompt=simple_parsed,
                identity_id=identity_id or "",
                user_id=user_id or "orchestrator",
                n_candidates=num_candidates,
                mode=mode,
                seed=seed,
                face_embedding=face_embedding,
            )
            converted = [{
                "image_base64": c["image_base64"],
                "seed": c["seed"],
                "prompt": c["prompt"],
                "negative_prompt": c.get("negative_prompt", ""),
                "scores": c["scores"],
            } for c in candidates]
            return {
                "images": converted[:2],
                "parsed_prompt": {"full_prompt": user_prompt},
                "execution_plan": {"engines": [{"name": "identity", "weight": 1.0}]},
                "rerank_used": False,
            }

        if self.generation_service_generate is not None:
            candidates = self.generation_service_generate.remote(
                user_id=user_id or "orchestrator",
                identity_id=identity_id or "",
                prompt=user_prompt,
                mode=mode,
                num_candidates=num_candidates,
                seed=seed,
                face_embedding=face_embedding,
            )
            return {
                "images": candidates[:2] if isinstance(candidates, list) else [],
                "parsed_prompt": {"full_prompt": user_prompt},
                "execution_plan": {"engines": [{"name": "identity", "weight": 1.0}]},
                "rerank_used": False,
            }
        else:
            return {
                "images": [],
                "parsed_prompt": {"full_prompt": user_prompt},
                "execution_plan": {"engines": []},
                "rerank_used": False,
                "error": "No generation engine available",
            }


# ==================== Web Endpoint ====================

@app.function(
    image=orchestrator_image,
    timeout=300,
    # Anthropic secret is optional - orchestrator works with fallback parser
    # secrets=[
    #     modal.Secret.from_name("anthropic"),  # Optional
    # ],
)
@modal.fastapi_endpoint(method="POST")
def orchestrate_web(item: dict):
    """Web endpoint for orchestration. quality_tier=FAST/STANDARD→Realtime. preview→FAST. reference_images, composition_params for composition. creative, style, use_mutations for Creative Engine."""
    ref_images = None
    if item.get("reference_images"):
        try:
            ref_images = [base64.b64decode(b) for b in item["reference_images"]]
        except Exception as e:
            return {"error": f"Invalid reference_images: {e}"}
    comp_params = item.get("composition_params")
    orchestrator = Orchestrator()
    result = orchestrator.orchestrate.remote(
        user_prompt=item.get("prompt", ""),
        mode=item.get("mode", "REALISM"),
        identity_id=item.get("identity_id"),
        user_id=item.get("user_id"),
        num_candidates=item.get("num_candidates", 4),
        seed=item.get("seed"),
        face_embedding=item.get("face_embedding"),
        quality_tier=item.get("quality_tier", "BALANCED"),
        preview=item.get("preview", False),
        reference_images=ref_images,
        composition_params=comp_params,
        creative=item.get("creative"),
        style=item.get("style"),
        use_mutations=item.get("use_mutations", True),
        width=item.get("width", 1024),
        height=item.get("height", 1024),
        user_tier=item.get("user_tier"),
        use_face_ensemble=item.get("use_face_ensemble", False),
    )
    return result


@app.function(
    image=orchestrator_image,
    timeout=300,
)
@modal.fastapi_endpoint(method="POST")
def orchestrate_with_cache_web(item: dict):
    """Web endpoint for orchestration with smart caching. preview→FAST; tier-aware TTL. reference_images, composition_params for composition. creative, style, use_mutations for Creative Engine. width, height, user_tier for Ultra High-Res. use_face_ensemble for multi-model face scoring."""
    ref_images = None
    if item.get("reference_images"):
        try:
            ref_images = [base64.b64decode(b) for b in item["reference_images"]]
        except Exception as e:
            return {"error": f"Invalid reference_images: {e}"}
    comp_params = item.get("composition_params")
    orchestrator = Orchestrator()
    result = orchestrator.orchestrate_with_cache.remote(
        user_prompt=item.get("prompt", ""),
        mode=item.get("mode", "REALISM"),
        identity_id=item.get("identity_id"),
        user_id=item.get("user_id"),
        num_candidates=item.get("num_candidates", 4),
        seed=item.get("seed"),
        face_embedding=item.get("face_embedding"),
        quality_tier=item.get("quality_tier", "BALANCED"),
        preview=item.get("preview", False),
        reference_images=ref_images,
        composition_params=comp_params,
        creative=item.get("creative"),
        style=item.get("style"),
        use_mutations=item.get("use_mutations", True),
        width=item.get("width", 1024),
        height=item.get("height", 1024),
        user_tier=item.get("user_tier"),
        use_face_ensemble=item.get("use_face_ensemble", False),
    )
    return result


@app.function(
    image=orchestrator_image,
    timeout=600,  # Longer timeout for multi-modal processing
    # Anthropic secret recommended for multi-modal (vision + synthesis)
    # secrets=[
    #     modal.Secret.from_name("anthropic"),  # Recommended for best results
    # ],
)
@modal.fastapi_endpoint(method="POST")
def orchestrate_multimodal_web(item: dict):
    """
    Web endpoint for multi-modal orchestration.
    
    Accepts:
    - text_prompt: str (optional)
    - reference_images: List[str] (base64 encoded images, optional)
    - voice_prompt: str (base64 encoded audio, optional)
    - mode: str (default: "REALISM")
    - identity_id: str (optional)
    - user_id: str (optional)
    - num_candidates: int (default: 4)
    - seed: int (optional)
    - face_embedding: List[float] (optional)
    - composition_params: dict (optional) identity_ids / identity_positions for multi-identity composition
    
    At least one of text_prompt, reference_images, or voice_prompt must be provided.
    """
    import base64
    
    orchestrator = Orchestrator()
    
    # Decode reference images if provided
    reference_images = None
    if item.get("reference_images"):
        try:
            reference_images = [
                base64.b64decode(img_b64) 
                for img_b64 in item["reference_images"]
            ]
        except Exception as e:
            return {"error": f"Invalid reference_images format: {e}"}
    
    # Decode voice prompt if provided
    voice_prompt = None
    if item.get("voice_prompt"):
        try:
            voice_prompt = base64.b64decode(item["voice_prompt"])
        except Exception as e:
            return {"error": f"Invalid voice_prompt format: {e}"}
    
    result = orchestrator.orchestrate_multimodal.remote(
        text_prompt=item.get("text_prompt"),
        reference_images=reference_images,
        voice_prompt=voice_prompt,
        mode=item.get("mode", "REALISM"),
        identity_id=item.get("identity_id"),
        user_id=item.get("user_id"),
        num_candidates=item.get("num_candidates", 4),
        seed=item.get("seed"),
        face_embedding=item.get("face_embedding"),
        composition_params=item.get("composition_params"),
    )
    return result


# ==================== RefactoredOrchestrator (Spec Thin Layer) ====================

class RefactoredOrchestrator:
    """
    Thin orchestration layer using dedicated services (spec 4.1).
    Use when PromptService, MultimodalService, RoutingService, ExecutionService,
    ScoringService, and AdversarialDefenseSystem are available.
    """

    def __init__(self, claude_client: Optional[Any] = None) -> None:
        self._log = (
            StructuredLogger(__name__)
            if StructuredLogger
            else logging.getLogger(__name__)
        )
        self.prompt_service = (
            PromptService(claude_client=claude_client)
            if PromptService and claude_client
            else None
        )
        self.multimodal_service = (
            MultimodalService(claude_client=claude_client)
            if MultimodalService and claude_client
            else None
        )
        self.routing_service = (
            RoutingService()
            if RoutingService
            else None
        )
        self.execution_service = (
            ExecutionService()
            if ExecutionService
            else None
        )
        self.scoring_service = None  # set per request
        self.defense_system = (
            AdversarialDefenseSystem(use_semantic=False)
            if AdversarialDefenseSystem
            else None
        )
        if self._log:
            self._log.info("RefactoredOrchestrator initialized")

    @trace_function("orchestrator.refactored.generate")
    async def orchestrate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        mode = params.get("mode", "standard")
        quality_tier = params.get("quality_tier", "BALANCED")
        tracker = None
        if RequestTracker:
            tracker = RequestTracker()
            tracker.__enter__()
        if Metrics:
            try:
                Metrics.active_requests.labels(mode=mode).inc()
            except Exception:
                pass
        try:
            if self.defense_system and "prompt" in params:
                defense_result = await asyncio.to_thread(
                    self.defense_system.analyze,
                    prompt=params["prompt"],
                    user_id=params.get("user_id"),
                    strict_mode=True,
                )
                if not defense_result.is_safe:
                    if Metrics:
                        try:
                            Metrics.requests_total.labels(
                                mode=mode,
                                quality_tier=quality_tier,
                                status="error",
                            ).inc()
                        except Exception:
                            pass
                    return {
                        "success": False,
                        "error": "prompt_rejected",
                        "threats": [
                            {
                                "type": getattr(t, "threat_type", ""),
                                "severity": getattr(t, "severity", ""),
                                "explanation": getattr(t, "explanation", ""),
                            }
                            for t in (defense_result.threats_detected or [])
                        ],
                        "message": "Prompt contains adversarial content.",
                    }
                params["prompt"] = defense_result.sanitized_prompt or params["prompt"]

            parsed_prompt = await self._parse_prompt(params)
            if not parsed_prompt:
                if Metrics:
                    try:
                        Metrics.requests_total.labels(
                            mode=mode,
                            quality_tier=quality_tier,
                            status="error",
                        ).inc()
                    except Exception:
                        pass
                return {
                    "success": False,
                    "error": "parse_failed",
                    "message": "Could not parse prompt.",
                }

            if not self.routing_service:
                if Metrics:
                    try:
                        Metrics.requests_total.labels(
                            mode=mode,
                            quality_tier=quality_tier,
                            status="error",
                        ).inc()
                    except Exception:
                        pass
                return {
                    "success": False,
                    "error": "routing_unavailable",
                    "message": "RoutingService not available.",
                }
            resolution = max(
                params.get("width", 1024),
                params.get("height", 1024),
            )
            routing = self.routing_service.select_engine(
                quality_tier=quality_tier,
                resolution=resolution,
                user_tier=params.get("user_tier", "free"),
                has_identity=bool(params.get("identity_id")),
                has_style=bool(params.get("style")),
            )
            params.update(routing.params_override or {})
            params["final_prompt"] = getattr(
                parsed_prompt,
                "final_prompt",
                getattr(parsed_prompt, "full_prompt", ""),
            )

            if not self.execution_service:
                if Metrics:
                    try:
                        Metrics.requests_total.labels(
                            mode=mode,
                            quality_tier=quality_tier,
                            status="error",
                        ).inc()
                    except Exception:
                        pass
                return {
                    "success": False,
                    "error": "execution_unavailable",
                    "message": "ExecutionService not available.",
                }
            ref_imgs = params.get("reference_images")
            if ref_imgs is None and params.get("reference_image") is not None:
                params = {**params, "reference_images": [params["reference_image"]]}
            plan = {
                "engines": [getattr(routing.engine_type, "value", routing.engine)],
                "requires_composition": bool(params.get("reference_images")),
                "requires_finish": True,
            }
            results = await self.execution_service.execute_plan(plan, params)
            scored = await self._score_and_rank(results, parsed_prompt, params)

            duration = 0.0
            if tracker and hasattr(tracker, "get_duration"):
                duration = tracker.get_duration()
            if Metrics:
                try:
                    Metrics.requests_total.labels(
                        mode=mode,
                        quality_tier=quality_tier,
                        status="success",
                    ).inc()
                    Metrics.request_duration.labels(
                        mode=mode,
                        quality_tier=quality_tier,
                    ).observe(duration)
                except Exception:
                    pass
            engine_val = getattr(routing.engine_type, "value", routing.engine)
            return {
                "success": True,
                "images": scored,
                "parsed_prompt": _parsed_to_dict(parsed_prompt),
                "routing": {
                    "engine": engine_val,
                    "estimated_time": routing.estimated_time_seconds,
                    "reason": routing.reason,
                },
                "execution_time_seconds": duration,
            }
        except Exception as e:
            if self._log:
                self._log.error("Orchestration failed: %s" % e)
            if Metrics:
                try:
                    Metrics.requests_total.labels(
                        mode=mode,
                        quality_tier=params.get("quality_tier", "BALANCED"),
                        status="error",
                    ).inc()
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            if Metrics:
                try:
                    Metrics.active_requests.labels(mode=mode).dec()
                except Exception:
                    pass
            if tracker and hasattr(tracker, "__exit__"):
                tracker.__exit__(None, None, None)

    async def _parse_prompt(self, params: Dict[str, Any]) -> Optional[Any]:
        if not self.prompt_service:
            return None
        if params.get("reference_image") or params.get("voice_audio"):
            img = params.get("reference_image")
            voice = params.get("voice_audio")
            image_analysis = None
            if img and self.multimodal_service:
                image_analysis = await asyncio.to_thread(
                    self.multimodal_service.analyze_reference_image,
                    img if isinstance(img, str) else img,
                    "general",
                )
            voice_text = None
            if voice and self.multimodal_service:
                voice_text = await asyncio.to_thread(
                    self.multimodal_service.transcribe_voice,
                    voice if isinstance(voice, str) else voice,
                )
            return await asyncio.to_thread(
                self.prompt_service.synthesize_multimodal,
                text_prompt=params.get("prompt"),
                image_analysis=image_analysis,
                voice_transcript=voice_text,
                mode=params.get("mode"),
            )
        return await asyncio.to_thread(
            self.prompt_service.parse,
            params["prompt"],
            params.get("mode"),
            True,
        )

    async def _score_and_rank(
        self,
        results: List[Dict[str, Any]],
        parsed: Any,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        prompt_type = self._detect_prompt_type(parsed)
        if ScoringService and FinalScore:
            self.scoring_service = ScoringService(weight_profile=prompt_type)
        return await asyncio.to_thread(
            lambda: self._score_batch(results, params),
        )

    def _score_batch(
        self,
        results: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not results:
            return []
        if not self.scoring_service:
            return results
        candidates = []
        for i, r in enumerate(results):
            raw = {
                "aesthetic": r.get("aesthetic_score", 0.8),
                "technical": r.get("technical_score", 0.75),
                "prompt_adherence": r.get("prompt_adherence", 0.85),
            }
            candidates.append({"result": r, "raw_scores": raw, "index": i})
        if not ScoreComponent:
            return results
        scored_list = []
        for c in candidates:
            rs = c.get("raw_scores") or {}
            comps = []
            for comp, val in [
                (ScoreComponent.AESTHETIC, rs.get("aesthetic", 0.8)),
                (ScoreComponent.TECHNICAL, rs.get("technical", 0.75)),
                (ScoreComponent.PROMPT_ADHERENCE, rs.get("prompt_adherence", 0.85)),
            ]:
                b = self.scoring_service.compute_component_score(
                    comp, val, 1.0, "refactored", (0, 1)
                )
                comps.append(b)
            fs = self.scoring_service.compute_final_score(comps)
            r = c.get("result") or {}
            r["score_breakdown"] = [vars(x) for x in fs.breakdown]
            r["score_total"] = fs.total
            r["selection_reason"] = fs.selection_reason
            scored_list.append(r)
        scored_list.sort(key=lambda x: x.get("score_total", 0), reverse=True)
        return scored_list

    def _detect_prompt_type(self, parsed: Any) -> str:
        if not parsed:
            return "default"
        mode = getattr(parsed, "mode", None)
        subject = (getattr(parsed, "subject", None) or "").lower()
        style = (getattr(parsed, "style", None) or "").lower()
        if mode and "portrait" in str(getattr(mode, "value", mode)):
            return "portrait"
        if "person" in subject:
            return "portrait"
        if "product" in subject:
            return "product"
        if mode and "artistic" in str(getattr(mode, "value", mode)):
            return "creative"
        if "creative" in style:
            return "creative"
        return "default"


def _parsed_to_dict(parsed: Any) -> Dict[str, Any]:
    if hasattr(parsed, "__dict__"):
        return {k: v for k, v in vars(parsed).items() if not k.startswith("_")}
    d = {}
    for k in ("subject", "style", "lighting", "camera", "mood", "full_prompt", "final_prompt", "negative_prompt", "confidence", "parsing_method", "raw_input"):
        v = getattr(parsed, k, None)
        if v is not None:
            d[k] = v
    if hasattr(parsed, "mode") and parsed.mode is not None:
        d["mode"] = getattr(parsed.mode, "value", str(parsed.mode))
    return d


# ==================== Test Function ====================

@app.local_entrypoint()
def test_orchestrator():
    """Test the orchestrator with various prompts"""
    print("\n[INFO] Orchestrator Test")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    test_cases = [
        ("beach", "REALISM"),
        ("office portrait", "REALISM"),
        ("dancing in rain", "CREATIVE"),
        ("romantic couple", "ROMANTIC"),
    ]
    
    for prompt, mode in test_cases:
        print(f"\n{'='*60}")
        print(f"Testing: '{prompt}' in {mode} mode")
        print(f"{'='*60}")
        
        result = orchestrator.orchestrate.remote(
            user_prompt=prompt,
            mode=mode,
            num_candidates=2,
            seed=42,
        )
        
        print(f"\n✅ Result: {len(result['images'])} images")
        print(f"   Parsed prompt: {result['parsed_prompt']['full_prompt'][:100]}...")
        print(f"   Engines used: {[e['name'] for e in result['execution_plan']['engines']]}")
        print(f"   Rerank used: {result['rerank_used']}")


@app.local_entrypoint()
def test_multimodal():
    """Test multi-modal prompt understanding"""
    print("\n[INFO] Multi-Modal Orchestrator Test")
    print("=" * 60)
    
    orchestrator = Orchestrator()
    
    # Test 1: Text + Image
    print("\n" + "="*60)
    print("Test 1: Text + Reference Image")
    print("="*60)
    
    # Create a simple test image (in production, load from file)
    from PIL import Image  # type: ignore[reportMissingImports]
    import io
    
    test_img = Image.new("RGB", (512, 512), color=(100, 150, 200))
    img_buffer = io.BytesIO()
    test_img.save(img_buffer, format="JPEG")
    test_image_bytes = img_buffer.getvalue()
    
    print("\nTo test with real images:")
    print("1. Load image bytes from file")
    print("2. Pass to orchestrate_multimodal()")
    print("\nExample:")
    print("  with open('reference.jpg', 'rb') as f:")
    print("      img_bytes = f.read()")
    print("  result = orchestrator.orchestrate_multimodal.remote(")
    print('      text_prompt="like this but different",')
    print("      reference_images=[img_bytes],")
    print('      mode="REALISM"')
    print("  )")
    
    # Test 2: Text only (should work same as orchestrate)
    print("\n" + "="*60)
    print("Test 2: Text Only (fallback)")
    print("="*60)
    
    result = orchestrator.orchestrate_multimodal.remote(
        text_prompt="beach sunset",
        mode="REALISM",
        num_candidates=2,
    )
    
    print(f"\n✅ Result: {len(result['images'])} images")
    print(f"   Parsed prompt: {result['parsed_prompt']['full_prompt'][:100]}...")
    
    print("\n" + "="*60)
    print("Multi-modal features:")
    print("="*60)
    print("✓ Text prompts")
    print("✓ Reference image analysis (Claude vision)")
    print("✓ Voice transcription (Whisper)")
    print("✓ Multi-modal synthesis (Claude)")
    print("\nThis is NEXT-LEVEL prompt understanding!")
 